"""CUSUM temporal fire detection — per-pixel Kalman-filtered diurnal model with
sequential change detection.

Each pixel maintains a 6-parameter harmonic model of expected BTD (BT7 - BT14)
as a function of local solar time plus a BT14 anomaly covariate:

  BTD_pred = T_mean + a1*cos(wt) + b1*sin(wt) + a2*cos(2wt) + b2*sin(2wt) + beta*BT14_anom

The beta coefficient captures land-surface temperature covariates: when a heat
wave raises BT14, the model predicts the corresponding BTD shift, keeping the
residual flat and avoiding false alarms.  Fires raise BTD without proportional
BT14 increases, so the residual stays positive and CUSUM accumulates.

Dual-rate CUSUM (S_slow, S_fast) on normalized residuals flags persistent
positive BTD anomalies.  S_slow (k=0.5, h=12) catches small fires over hours;
S_fast (k=1.5, h=5) catches large fires in minutes.  A BT14 rejection
criterion suppresses candidates where BT14 is itself anomalously warm
(weather-driven), unless the anomaly is extreme (possible large fire heating
the BT14 channel).

A Bayesian probability interpretation layer converts the CUSUM S statistic
(which is a log-likelihood ratio) into a posterior fire probability:

  P(fire | obs) = 1 / (1 + (1/prior_odds) * exp(-alpha * S_max))

This replaces hard detection thresholds with smooth probability estimates.
The Kalman gain is also softly weighted by (1 - P(fire)), so that pixels
with high fire probability have their background model frozen (protecting
against fire contamination), while normal pixels get full Kalman updates.

All state arrays are flat (n_pixels,) over the NSW-cropped grid.  Operations
are fully vectorized with numpy — no per-pixel Python loops.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from ..models import Detection, Source
from .config import CUSUMConfig, HimawariConfig
from .static_masks import compute_industrial_mask, compute_water_mask

logger = logging.getLogger(__name__)

# Harmonic angular frequency: one full cycle per 24 hours
_OMEGA = 2.0 * np.pi / 24.0

# Number of Kalman state parameters: [T_mean, a1, b1, a2, b2, beta]
_N_PARAMS = 6


def _build_H(lst_hours: np.ndarray, bt14_anom: np.ndarray) -> np.ndarray:
    """Build the observation matrix H for each pixel.

    Args:
        lst_hours: Local solar time in hours, shape (n,).
        bt14_anom: BT14 anomaly (BT14 - BT14_ema), shape (n,).

    Returns:
        H array of shape (n, 6).  Each row is
        [1, cos(wt), sin(wt), cos(2wt), sin(2wt), bt14_anom].
    """
    wt = _OMEGA * lst_hours
    H = np.empty((lst_hours.shape[0], _N_PARAMS), dtype=np.float64)
    H[:, 0] = 1.0
    H[:, 1] = np.cos(wt)
    H[:, 2] = np.sin(wt)
    H[:, 3] = np.cos(2.0 * wt)
    H[:, 4] = np.sin(2.0 * wt)
    H[:, 5] = bt14_anom
    return H


class CUSUMTemporalDetector:
    """Per-pixel CUSUM fire detector backed by Kalman-filtered diurnal BTD model.

    All internal arrays are 1-D with length *n_pixels* (the flattened NSW grid).
    The caller is responsible for flattening/unflattening as needed.
    """

    def __init__(
        self,
        n_pixels: int,
        pixel_lons: np.ndarray,
        cfg: CUSUMConfig,
        suppression_mask: Optional[np.ndarray] = None,
    ):
        """
        Args:
            n_pixels: Number of pixels in the flattened grid.
            pixel_lons: Longitude of each pixel, shape (n_pixels,), used to
                compute local solar time.
            cfg: CUSUM configuration parameters.
            suppression_mask: Optional boolean array (n_pixels,).  True means
                the pixel should be suppressed (water body / industrial site).
                CUSUM candidates at suppressed locations are discarded.
        """
        self.n = n_pixels
        self.cfg = cfg

        # Pixel longitudes (float32 is fine for LST computation)
        self.pixel_lons = np.asarray(pixel_lons, dtype=np.float32).ravel()
        if self.pixel_lons.shape[0] != n_pixels:
            raise ValueError(
                f"pixel_lons length {self.pixel_lons.shape[0]} != n_pixels {n_pixels}"
            )

        # Suppression mask (water + industrial)
        if suppression_mask is not None:
            self.suppression_mask = np.asarray(suppression_mask, dtype=bool).ravel()
        else:
            self.suppression_mask = np.zeros(n_pixels, dtype=bool)

        # --- Kalman filter state ---
        # x: state vector (n, 6) — float64 for numerical precision
        self.x = np.zeros((n_pixels, _N_PARAMS), dtype=np.float64)
        # P: covariance (n, 6, 6) — initialized to prior variance
        self.P = np.zeros((n_pixels, _N_PARAMS, _N_PARAMS), dtype=np.float64)
        for i, var in enumerate(cfg.initial_variance):
            self.P[:, i, i] = var

        # Process noise Q (diagonal, constant) — built once
        self.Q = np.zeros((_N_PARAMS, _N_PARAMS), dtype=np.float64)
        for i, std in enumerate(cfg.process_noise_std):
            self.Q[i, i] = std ** 2

        # --- BT14 exponential moving average state ---
        self.bt14_ema = np.full(n_pixels, np.nan, dtype=np.float64)
        # Running variance of BT14 via Welford's online algorithm
        self.bt14_ema_var = np.zeros(n_pixels, dtype=np.float64)
        self._bt14_var_count = np.zeros(n_pixels, dtype=np.int32)
        self._bt14_var_mean = np.zeros(n_pixels, dtype=np.float64)
        self._bt14_var_m2 = np.zeros(n_pixels, dtype=np.float64)

        # --- CUSUM state (dual-rate) ---
        self.S_slow = np.zeros(n_pixels, dtype=np.float32)  # Slow CUSUM (small fires)
        self.S_fast = np.zeros(n_pixels, dtype=np.float32)  # Fast CUSUM (large fires)
        self.n_obs = np.zeros(n_pixels, dtype=np.int32)  # clear-sky obs count
        self.last_clear_time = np.full(n_pixels, np.nan, dtype=np.float64)  # UNIX timestamp
        self.consecutive_anomalies = np.zeros(n_pixels, dtype=np.int16)

        # Frame counter (for periodic state saves)
        self._frame_count = 0

    def update(
        self,
        btd_flat: np.ndarray,
        bt14_flat: np.ndarray,
        clear_mask: np.ndarray,
        is_day: np.ndarray,
        obs_time_unix: float,
    ) -> dict:
        """Process one observation frame.

        Args:
            btd_flat: BT7 - BT14 values, shape (n_pixels,).  NaN for invalid.
            bt14_flat: BT14 values, shape (n_pixels,).  Used only for metadata.
            clear_mask: Boolean, shape (n_pixels,).  True = clear-sky valid pixel.
            is_day: Boolean, shape (n_pixels,).  True = daytime pixel.
            obs_time_unix: Observation time as UNIX timestamp (seconds since epoch).

        Returns:
            Dictionary with:
                fire_candidates    — bool array (n_pixels,)
                fire_probability   — float32 array (n_pixels,), Bayesian P(fire);
                                     NaN for uninitialized pixels
                residuals          — float array (n_pixels,), normalized z-scores
                cusum_values_slow  — float array (n_pixels,), S_slow statistic
                cusum_values_fast  — float array (n_pixels,), S_fast statistic
                n_candidates       — int, total candidate count
                n_bt14_rejected    — int, candidates suppressed by BT14 criterion
                n_initialized      — int, pixels with sufficient observations
                timing_ms          — float, wall-clock time for this call
                diagnostics        — dict with per-pixel arrays for training/calibration
        """
        t0 = time.monotonic()
        cfg = self.cfg
        n = self.n

        # Sanitize inputs
        btd = np.asarray(btd_flat, dtype=np.float64).ravel()
        clear = np.asarray(clear_mask, dtype=bool).ravel()
        day = np.asarray(is_day, dtype=bool).ravel()

        if btd.shape[0] != n or clear.shape[0] != n or day.shape[0] != n:
            raise ValueError(
                f"Input array length mismatch: btd={btd.shape[0]}, "
                f"clear={clear.shape[0]}, day={day.shape[0]}, expected {n}"
            )

        # Sanitize BT14
        bt14 = np.asarray(bt14_flat, dtype=np.float64).ravel()

        # Replace NaN in btd with 0 for safe arithmetic (clear_mask gates usage)
        btd_safe = np.where(np.isfinite(btd), btd, 0.0)
        bt14_safe = np.where(np.isfinite(bt14), bt14, 0.0)

        # --- Update BT14 EMA (clear-sky pixels only) ---
        # Initialize EMA to first observed value where not yet set
        ema_uninit = clear & np.isnan(self.bt14_ema)
        if np.any(ema_uninit):
            self.bt14_ema[ema_uninit] = bt14_safe[ema_uninit]

        # Compute EMA alpha from time since last clear observation
        dt = obs_time_unix - np.where(
            np.isfinite(self.last_clear_time), self.last_clear_time, obs_time_unix
        )
        dt = np.maximum(dt, 1.0)  # floor at 1 second to avoid division issues
        tau_s = cfg.bt14_ema_tau_hours * 3600.0
        alpha_ema = 1.0 - np.exp(-dt / tau_s)

        ema_update_mask = clear & np.isfinite(self.bt14_ema)
        if np.any(ema_update_mask):
            idx_ema = np.where(ema_update_mask)[0]
            self.bt14_ema[idx_ema] = (
                alpha_ema[idx_ema] * bt14_safe[idx_ema]
                + (1.0 - alpha_ema[idx_ema]) * self.bt14_ema[idx_ema]
            )

        # Update BT14 running variance via Welford's online algorithm (clear-sky only)
        if np.any(ema_update_mask):
            idx_w = np.where(ema_update_mask)[0]
            self._bt14_var_count[idx_w] += 1
            delta = bt14_safe[idx_w] - self._bt14_var_mean[idx_w]
            self._bt14_var_mean[idx_w] += delta / self._bt14_var_count[idx_w]
            delta2 = bt14_safe[idx_w] - self._bt14_var_mean[idx_w]
            self._bt14_var_m2[idx_w] += delta * delta2
            # Variance = M2 / count (use population variance; floor at 1.0 K^2)
            valid_count = self._bt14_var_count[idx_w] >= 2
            if np.any(valid_count):
                idx_valid = idx_w[valid_count]
                self.bt14_ema_var[idx_valid] = np.maximum(
                    self._bt14_var_m2[idx_valid] / self._bt14_var_count[idx_valid],
                    1.0,
                )

        # BT14 anomaly for Kalman observation matrix
        bt14_anom = np.where(
            np.isfinite(self.bt14_ema), bt14_safe - self.bt14_ema, 0.0
        )

        # --- Compute local solar time ---
        utc_hour = (obs_time_unix % 86400) / 3600.0
        lst_hours = (utc_hour + self.pixel_lons / 15.0) % 24.0

        # --- Build observation matrix H (n, 6) ---
        H = _build_H(lst_hours.astype(np.float64), bt14_anom)

        # --- Kalman prediction step ---
        # F = I, so x_pred = x, P_pred = P + Q
        P_pred = self.P + self.Q[np.newaxis, :, :]  # (n, 6, 6)

        # --- Predicted BTD and innovation ---
        # y_pred = H @ x  (per-pixel dot product)
        y_pred = np.einsum("ij,ij->i", H, self.x)  # (n,)

        # Innovation (residual)
        innovation = btd_safe - y_pred  # (n,)

        # Innovation variance: S_innov = H @ P_pred @ H^T + R  (scalar per pixel)
        # Compute H @ P_pred first: (n, 6)
        HP = np.einsum("ij,ijk->ik", H, P_pred)  # (n, 6)
        # Then H @ P_pred @ H^T: scalar per pixel
        S_innov = np.einsum("ij,ij->i", HP, H)  # (n,)

        # Observation noise R depends on day/night
        R = np.where(day, cfg.R_day, cfg.R_night)
        S_innov += R
        # Safety: floor at small positive value
        S_innov = np.maximum(S_innov, 1e-6)

        sigma_pred = np.sqrt(S_innov)  # (n,)

        # Normalized residual
        z = innovation / sigma_pred  # (n,)

        # --- Bayesian fire probability from CUSUM statistics ---
        # S is a log-likelihood ratio; convert to posterior P(fire).
        S_max = np.maximum(self.S_slow, self.S_fast).astype(np.float64)
        log_prior_odds = np.log(cfg.fire_prior / (1.0 - cfg.fire_prior))
        log_posterior_odds = log_prior_odds + cfg.cusum_to_logodds_scale * S_max
        # Clip to prevent overflow in exp() for very negative values
        log_posterior_odds = np.clip(log_posterior_odds, -50.0, 50.0)
        fire_probability = (1.0 / (1.0 + np.exp(-log_posterior_odds))).astype(np.float32)
        # NaN for uninitialized pixels (no meaningful probability yet)
        uninit_mask = self.n_obs < cfg.min_init_observations
        fire_probability[uninit_mask] = np.float32(np.nan)

        # --- Soft Bayesian Kalman weighting ---
        # Instead of hard-gating (skip update if z > fire_gate_sigma),
        # scale the Kalman gain by (1 - P(fire)).  High fire probability
        # suppresses model updates, protecting the background model.
        kalman_weight = np.where(
            np.isfinite(fire_probability),
            1.0 - fire_probability,
            1.0,  # uninitialized pixels get full update
        ).astype(np.float64)
        kalman_weight = np.maximum(kalman_weight, cfg.min_kalman_weight)

        # Update all clear pixels (no hard gate — soft weighting replaces it)
        update_mask = clear.copy()

        # --- Kalman update (vectorized, only for clear pixels) ---
        if np.any(update_mask):
            idx = np.where(update_mask)[0]

            H_u = H[idx]           # (m, 6)
            HP_u = HP[idx]         # (m, 6)
            S_u = S_innov[idx]     # (m,)
            innov_u = innovation[idx]  # (m,)

            # Kalman gain K = P_pred @ H^T / S_innov, scaled by (1 - P(fire))
            K = (HP_u / S_u[:, np.newaxis]) * kalman_weight[idx, np.newaxis]  # (m, 6)

            # State update: x = x + K * innovation
            self.x[idx] += K * innov_u[:, np.newaxis]

            # Covariance update: P = (I - K @ H) @ P_pred
            # K @ H: (m, 6, 1) @ (m, 1, 6) → (m, 6, 6)
            KH = K[:, :, np.newaxis] * H_u[:, np.newaxis, :]  # (m, 6, 6)
            I_KH = np.eye(_N_PARAMS, dtype=np.float64)[np.newaxis, :, :] - KH  # (m, 6, 6)
            self.P[idx] = np.einsum("mij,mjk->mik", I_KH, P_pred[idx])

            # Increment observation count
            self.n_obs[idx] += 1
            self.last_clear_time[idx] = obs_time_unix

        # For prediction-only pixels (cloudy), P grows via Q.
        not_updated = ~update_mask
        self.P[not_updated] = P_pred[not_updated]

        # --- CUSUM decay for cloudy pixels ---
        cloudy = ~clear
        if np.any(cloudy):
            dt_since_clear = obs_time_unix - self.last_clear_time  # seconds
            # Only decay where we have a valid last_clear_time
            has_history = cloudy & np.isfinite(self.last_clear_time)
            if np.any(has_history):
                tau_decay_s = cfg.tau_decay_hours * 3600.0
                decay = np.exp(-dt_since_clear[has_history] / tau_decay_s).astype(np.float32)
                self.S_slow[has_history] *= decay
                self.S_fast[has_history] *= decay
                # Also decay consecutive anomaly count
                self.consecutive_anomalies[has_history] = 0

        # --- Dual-rate CUSUM update for clear pixels ---
        initialized = self.n_obs >= cfg.min_init_observations  # (n,)
        cusum_eligible = clear & initialized

        # Store residuals (z-scores) for output; NaN where not eligible
        residuals_out = np.full(n, np.nan, dtype=np.float32)

        if np.any(cusum_eligible):
            idx_c = np.where(cusum_eligible)[0]
            z_c = z[idx_c].astype(np.float32)
            residuals_out[idx_c] = z_c

            # Dual CUSUM update
            self.S_slow[idx_c] = np.maximum(0.0, self.S_slow[idx_c] + z_c - cfg.k_ref)
            self.S_fast[idx_c] = np.maximum(0.0, self.S_fast[idx_c] + z_c - cfg.k_ref_fast)

            # Track consecutive anomalies (z > anomaly_z_threshold)
            anomalous = z_c > cfg.anomaly_z_threshold
            # Reset counter where not anomalous, increment where anomalous
            self.consecutive_anomalies[idx_c] = np.where(
                anomalous,
                self.consecutive_anomalies[idx_c] + 1,
                0,
            ).astype(np.int16)

        # --- Fire candidate identification (Bayesian) ---
        # Use posterior fire probability instead of hard CUSUM thresholds.
        # A pixel is a candidate when P(fire) >= detection_probability_threshold.
        prob_triggered = np.isfinite(fire_probability) & (
            fire_probability >= cfg.detection_probability_threshold
        )
        candidates = cusum_eligible & prob_triggered

        # --- BT14 rejection criterion ---
        # Suppress candidates where BT14 is anomalously warm (weather, not fire)
        # UNLESS BT14 anomaly is extreme (could be a large fire heating BT14 too).
        n_bt14_rejected = 0
        if np.any(candidates):
            sigma_bt14 = np.sqrt(np.maximum(self.bt14_ema_var, 1.0))  # floor at 1K
            bt14_z = bt14_anom / sigma_bt14  # (n,)

            # Suppress if bt14_rejection_threshold <= bt14_z < bt14_rejection_max
            bt14_suppress = (
                candidates
                & (bt14_z > cfg.bt14_rejection_threshold)
                & (bt14_z < cfg.bt14_rejection_max)
            )
            n_bt14_rejected = int(np.sum(bt14_suppress))
            candidates &= ~bt14_suppress

        # Suppress water/industrial pixels
        candidates &= ~self.suppression_mask

        # --- Adjacent pixel requirement ---
        if cfg.require_adjacent and np.any(candidates):
            candidates = self._apply_adjacency_filter(candidates)

        # --- Auto-reset detected pixels ---
        # After detection, reset both CUSUM statistics to prevent re-firing.
        # The pixel must re-accumulate evidence for a new detection.
        if np.any(candidates):
            self.S_slow[candidates] = 0.0
            self.S_fast[candidates] = 0.0
            self.consecutive_anomalies[candidates] = 0

        n_candidates = int(np.sum(candidates))
        n_initialized = int(np.sum(initialized))

        self._frame_count += 1

        elapsed_ms = (time.monotonic() - t0) * 1000.0

        if n_candidates > 0:
            max_prob = float(np.nanmax(fire_probability))
            logger.info(
                "CUSUM update: %d fire candidates (%d BT14-rejected), "
                "max P(fire)=%.4f, %d/%d pixels initialized (%.1fms)",
                n_candidates, n_bt14_rejected, max_prob,
                n_initialized, n, elapsed_ms,
            )
        else:
            logger.debug(
                "CUSUM update: 0 candidates (%d BT14-rejected), %d/%d initialized (%.1fms)",
                n_bt14_rejected, n_initialized, n, elapsed_ms,
            )

        return {
            "fire_candidates": candidates,
            "fire_probability": fire_probability,  # (n_pixels,) float32
            "residuals": residuals_out,
            "cusum_values_slow": self.S_slow.copy(),
            "cusum_values_fast": self.S_fast.copy(),
            "n_candidates": n_candidates,
            "n_bt14_rejected": n_bt14_rejected,
            "n_initialized": n_initialized,
            "timing_ms": round(elapsed_ms, 2),
            "diagnostics": {
                "fire_probability": fire_probability,
                "z_scores": residuals_out,
                "S_slow": self.S_slow.copy(),
                "S_fast": self.S_fast.copy(),
                "bt14_anomaly": bt14_anom.astype(np.float32),
                "kalman_weight": kalman_weight.astype(np.float32),
                "obs_time_unix": obs_time_unix,
            },
        }

    def _apply_adjacency_filter(self, candidates: np.ndarray) -> np.ndarray:
        """Require at least one adjacent pixel to also be flagged.

        This uses the grid shape stored when the detector was created via
        set_grid_shape().  Falls back to no filtering if shape is unknown.
        """
        if not hasattr(self, "_grid_shape") or self._grid_shape is None:
            return candidates

        from scipy.ndimage import binary_dilation

        rows, cols = self._grid_shape
        cand_2d = candidates.reshape(rows, cols)

        # Structuring element: 8-connected neighborhood
        struct = np.ones((3, 3), dtype=bool)
        struct[1, 1] = False  # exclude center

        # Dilate to find pixels adjacent to any candidate
        neighbors = binary_dilation(cand_2d, structure=struct, border_value=False)

        # Keep only candidates that have at least one neighbor also flagged
        has_neighbor = cand_2d & neighbors
        return has_neighbor.ravel()

    def set_grid_shape(self, rows: int, cols: int) -> None:
        """Set the 2-D grid shape for adjacency filtering.

        Must be called before update() if require_adjacent is True.
        """
        if rows * cols != self.n:
            raise ValueError(
                f"Grid shape {rows}x{cols} = {rows * cols} != n_pixels {self.n}"
            )
        self._grid_shape = (rows, cols)

    def save_state(self, path: Optional[Path] = None) -> None:
        """Persist all state arrays to an .npz file."""
        path = Path(path or self.cfg.state_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        np.savez_compressed(
            str(path),
            x=self.x,
            P=self.P,
            S_slow=self.S_slow,
            S_fast=self.S_fast,
            n_obs=self.n_obs,
            last_clear_time=self.last_clear_time,
            consecutive_anomalies=self.consecutive_anomalies,
            bt14_ema=self.bt14_ema,
            bt14_ema_var=self.bt14_ema_var,
            bt14_var_count=self._bt14_var_count,
            bt14_var_mean=self._bt14_var_mean,
            bt14_var_m2=self._bt14_var_m2,
            frame_count=np.array([self._frame_count]),
            # Metadata for validation on load
            n_pixels=np.array([self.n]),
            state_version=np.array([2]),  # v2: 6-param Kalman + dual CUSUM
        )
        logger.info("CUSUM state saved to %s (%d pixels, frame %d)", path, self.n, self._frame_count)

    def load_state(self, path: Optional[Path] = None) -> bool:
        """Load state from .npz file.  Returns True on success, False otherwise.

        Handles backward compatibility: v1 state files (5-param Kalman, single
        CUSUM) are detected and discarded with a warning.
        """
        path = Path(path or self.cfg.state_file)
        if not path.exists():
            logger.info("No CUSUM state file at %s — starting fresh", path)
            return False

        try:
            data = np.load(str(path))

            saved_n = int(data["n_pixels"][0])
            if saved_n != self.n:
                logger.warning(
                    "CUSUM state pixel count mismatch: saved %d vs current %d — discarding",
                    saved_n, self.n,
                )
                return False

            # Check state version — v1 (5-param) is incompatible with v2 (6-param)
            state_version = int(data["state_version"][0]) if "state_version" in data else 1
            if state_version < 2:
                logger.warning(
                    "CUSUM state file is v%d (5-param Kalman) — incompatible with "
                    "v2 (6-param); discarding and starting fresh",
                    state_version,
                )
                return False

            self.x = data["x"].astype(np.float64)
            self.P = data["P"].astype(np.float64)
            self.S_slow = data["S_slow"].astype(np.float32)
            self.S_fast = data["S_fast"].astype(np.float32)
            self.n_obs = data["n_obs"].astype(np.int32)
            self.last_clear_time = data["last_clear_time"].astype(np.float64)
            self.consecutive_anomalies = data["consecutive_anomalies"].astype(np.int16)
            self.bt14_ema = data["bt14_ema"].astype(np.float64)
            self.bt14_ema_var = data["bt14_ema_var"].astype(np.float64)
            self._bt14_var_count = data["bt14_var_count"].astype(np.int32)
            self._bt14_var_mean = data["bt14_var_mean"].astype(np.float64)
            self._bt14_var_m2 = data["bt14_var_m2"].astype(np.float64)
            self._frame_count = int(data["frame_count"][0])

            logger.info(
                "CUSUM state loaded from %s (v%d, frame %d, %d/%d initialized)",
                path, state_version, self._frame_count,
                int(np.sum(self.n_obs >= self.cfg.min_init_observations)), self.n,
            )
            return True

        except Exception:
            logger.warning("Failed to load CUSUM state from %s — starting fresh", path, exc_info=True)
            return False

    def reset_pixels(self, indices: np.ndarray) -> None:
        """Reset CUSUM and Kalman state for specific pixels.

        Useful after a confirmed fire is resolved, so the pixel can re-learn
        its background model.

        Args:
            indices: 1-D integer array of pixel indices to reset.
        """
        idx = np.asarray(indices, dtype=np.intp).ravel()
        if idx.size == 0:
            return

        self.x[idx] = 0.0
        self.P[idx, :, :] = 0.0
        for i, var in enumerate(self.cfg.initial_variance):
            self.P[idx, i, i] = var
        self.S_slow[idx] = 0.0
        self.S_fast[idx] = 0.0
        self.n_obs[idx] = 0
        self.last_clear_time[idx] = np.nan
        self.consecutive_anomalies[idx] = 0
        self.bt14_ema[idx] = np.nan
        self.bt14_ema_var[idx] = 0.0
        self._bt14_var_count[idx] = 0
        self._bt14_var_mean[idx] = 0.0
        self._bt14_var_m2[idx] = 0.0

        logger.info("Reset %d CUSUM pixels", idx.size)

    @property
    def initialized_fraction(self) -> float:
        """Fraction of pixels that have enough observations to run CUSUM."""
        if self.n == 0:
            return 0.0
        return float(np.sum(self.n_obs >= self.cfg.min_init_observations)) / self.n

    @property
    def frame_count(self) -> int:
        return self._frame_count


# ---------------------------------------------------------------------------
# Conversion helpers — turn CUSUM candidates into Detection objects
# ---------------------------------------------------------------------------

def cusum_to_detections(
    cusum_result: dict,
    lats_flat: np.ndarray,
    lons_flat: np.ndarray,
    bt7_flat: np.ndarray,
    bt14_flat: np.ndarray,
    obs_time: datetime,
    sza_flat: np.ndarray,
    cfg: HimawariConfig,
) -> list[Detection]:
    """Convert CUSUM fire candidates to Detection objects.

    Args:
        cusum_result: Dict returned by CUSUMTemporalDetector.update().
        lats_flat, lons_flat: Flattened coordinate arrays.
        bt7_flat, bt14_flat: Flattened brightness temperature arrays.
        obs_time: Observation time (UTC).
        sza_flat: Flattened solar zenith angle array.
        cfg: Himawari pipeline configuration.

    Returns:
        List of Detection objects with source "HIMAWARI" and CUSUM-specific IDs.
    """
    candidates = cusum_result["fire_candidates"]
    indices = np.where(candidates)[0]

    if len(indices) == 0:
        return []

    # Ensure obs_time is timezone-aware
    if obs_time.tzinfo is None:
        obs_time = obs_time.replace(tzinfo=timezone.utc)

    detections: list[Detection] = []

    for idx in indices:
        lat = float(lats_flat[idx])
        lon = float(lons_flat[idx])
        brightness = float(bt7_flat[idx])
        daynight = "D" if sza_flat[idx] < cfg.sza_day_night_deg else "N"

        source_id = hashlib.sha256(
            f"HIMAWARI_CUSUM|{lat:.4f}|{lon:.4f}|{obs_time.isoformat()}".encode()
        ).hexdigest()

        det = Detection(
            source_id=source_id,
            source=Source.HIMAWARI,
            satellite="Himawari-9",
            instrument="AHI",
            latitude=lat,
            longitude=lon,
            acq_datetime=obs_time,
            confidence="low",  # CUSUM-only detections start at low confidence
            frp=None,
            brightness=brightness,
            daynight=daynight,
        )
        detections.append(det)

    logger.info(
        "CUSUM produced %d detections (obs_time=%s)",
        len(detections), obs_time.isoformat(),
    )
    return detections


def merge_detections(
    contextual: list[Detection],
    cusum: list[Detection],
    match_radius_deg: float = 0.02,
) -> list[Detection]:
    """Merge contextual and CUSUM detection lists, avoiding duplicates.

    When both methods flag the same pixel (within match_radius_deg):
    - Keep the contextual detection (typically higher confidence).
    - Boost its confidence if it was "low" → "nominal" (corroboration bonus).

    CUSUM detections that don't overlap with any contextual detection are
    appended as-is (confidence "low").

    Args:
        contextual: Detections from the contextual algorithm.
        cusum: Detections from the CUSUM algorithm.
        match_radius_deg: Maximum lat/lon distance to consider a match.
            Default 0.02 deg ~ 2 km, roughly one AHI pixel.

    Returns:
        Merged detection list.
    """
    if not cusum:
        return contextual
    if not contextual:
        return cusum

    # Build lookup of contextual positions for fast matching
    ctx_positions = np.array(
        [(d.latitude, d.longitude) for d in contextual], dtype=np.float64
    )

    merged = list(contextual)  # start with all contextual
    cusum_matched = set()

    for ci, cdet in enumerate(cusum):
        # Check distance to all contextual detections
        dlat = ctx_positions[:, 0] - cdet.latitude
        dlon = ctx_positions[:, 1] - cdet.longitude
        dist = np.sqrt(dlat ** 2 + dlon ** 2)
        min_idx = np.argmin(dist)

        if dist[min_idx] <= match_radius_deg:
            # Match found — boost contextual confidence if low
            ctx_det = merged[min_idx]
            if ctx_det.confidence == "low":
                # Corroboration: upgrade low → nominal
                merged[min_idx] = ctx_det.model_copy(update={"confidence": "nominal"})
            cusum_matched.add(ci)
        else:
            # No overlap — add CUSUM detection as-is
            merged.append(cdet)

    n_boosted = len(cusum_matched)
    n_new = len(cusum) - n_boosted
    if n_boosted > 0 or n_new > 0:
        logger.info(
            "Merge: %d contextual, %d CUSUM — %d boosted, %d new CUSUM-only",
            len(contextual), len(cusum), n_boosted, n_new,
        )

    return merged
