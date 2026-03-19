"""CUSUM temporal fire detection — per-pixel Kalman-filtered diurnal model with
sequential change detection.

Each pixel maintains a 5-parameter harmonic model of expected BTD (BT7 - BT14)
as a function of local solar time.  A one-sided upper CUSUM on normalized
residuals flags persistent positive BTD anomalies (fire signature: 3.9 um
responds more strongly to sub-pixel fire than 11.2 um).

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

# Number of Kalman state parameters: [T_mean, a1, b1, a2, b2]
_N_PARAMS = 5


def _build_H(lst_hours: np.ndarray) -> np.ndarray:
    """Build the observation matrix H for each pixel.

    Args:
        lst_hours: Local solar time in hours, shape (n,).

    Returns:
        H array of shape (n, 5).  Each row is
        [1, cos(wt), sin(wt), cos(2wt), sin(2wt)].
    """
    wt = _OMEGA * lst_hours
    H = np.empty((lst_hours.shape[0], _N_PARAMS), dtype=np.float64)
    H[:, 0] = 1.0
    H[:, 1] = np.cos(wt)
    H[:, 2] = np.sin(wt)
    H[:, 3] = np.cos(2.0 * wt)
    H[:, 4] = np.sin(2.0 * wt)
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
        # x: state vector (n, 5) — float64 for numerical precision
        self.x = np.zeros((n_pixels, _N_PARAMS), dtype=np.float64)
        # P: covariance (n, 5, 5) — initialized to prior variance
        self.P = np.zeros((n_pixels, _N_PARAMS, _N_PARAMS), dtype=np.float64)
        for i, var in enumerate(cfg.initial_variance):
            self.P[:, i, i] = var

        # Process noise Q (diagonal, constant) — built once
        self.Q = np.zeros((_N_PARAMS, _N_PARAMS), dtype=np.float64)
        for i, std in enumerate(cfg.process_noise_std):
            self.Q[i, i] = std ** 2

        # --- CUSUM state ---
        self.S = np.zeros(n_pixels, dtype=np.float32)  # CUSUM statistic
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
                fire_candidates  — bool array (n_pixels,)
                residuals        — float array (n_pixels,), normalized z-scores
                cusum_values     — float array (n_pixels,), current S statistic
                n_candidates     — int, total candidate count
                n_initialized    — int, pixels with sufficient observations
                timing_ms        — float, wall-clock time for this call
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

        # Replace NaN in btd with 0 for safe arithmetic (clear_mask gates usage)
        btd_safe = np.where(np.isfinite(btd), btd, 0.0)

        # --- Compute local solar time ---
        utc_hour = (obs_time_unix % 86400) / 3600.0
        lst_hours = (utc_hour + self.pixel_lons / 15.0) % 24.0

        # --- Build observation matrix H (n, 5) ---
        H = _build_H(lst_hours.astype(np.float64))

        # --- Kalman prediction step ---
        # F = I, so x_pred = x, P_pred = P + Q
        P_pred = self.P + self.Q[np.newaxis, :, :]  # (n, 5, 5)

        # --- Predicted BTD and innovation ---
        # y_pred = H @ x  (per-pixel dot product)
        y_pred = np.einsum("ij,ij->i", H, self.x)  # (n,)

        # Innovation (residual)
        innovation = btd_safe - y_pred  # (n,)

        # Innovation variance: S_innov = H @ P_pred @ H^T + R  (scalar per pixel)
        # Compute H @ P_pred first: (n, 5)
        HP = np.einsum("ij,ijk->ik", H, P_pred)  # (n, 5)
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

        # --- Identify which pixels to update via Kalman ---
        # Gate: skip Kalman update if z > fire_gate_sigma (possible fire contamination)
        fire_gated = z > cfg.fire_gate_sigma
        update_mask = clear & (~fire_gated)

        # Also require the pixel is not suppressed for Kalman *gating* purposes,
        # but we still update suppressed pixels' background models (they just
        # can't produce fire candidates).  Actually, let's update all clear
        # non-gated pixels including suppressed ones.

        # --- Kalman update (vectorized, only for update_mask pixels) ---
        if np.any(update_mask):
            idx = np.where(update_mask)[0]

            H_u = H[idx]           # (m, 5)
            HP_u = HP[idx]         # (m, 5)
            S_u = S_innov[idx]     # (m,)
            innov_u = innovation[idx]  # (m,)

            # Kalman gain K = P_pred @ H^T / S_innov  →  shape (m, 5)
            K = HP_u.T  # This is P_pred @ H^T already transposed wrong...
            # Correction: HP = H @ P_pred, so P_pred @ H^T = HP^T
            # Actually: HP[i] = H[i] @ P_pred[i], shape (5,)
            # P_pred @ H^T = P_pred[i] @ H[i]^T, which is a column vector.
            # Since HP = H @ P_pred, P @ H^T = (H @ P)^T is NOT right because
            # (H @ P)^T = P^T @ H^T = P @ H^T (P is symmetric).  So HP^T per
            # pixel is what we want.
            #
            # K_i = P_pred_i @ H_i^T / S_innov_i
            # We have HP_u_i = H_i @ P_pred_i (row vector of length 5)
            # Due to symmetry: P_pred_i @ H_i^T = (H_i @ P_pred_i)^T = HP_u_i^T
            # But HP_u_i is already a 1-D array of length 5, so no transpose needed.
            # K_i = HP_u_i / S_innov_i (element-wise, shape (5,))
            K = HP_u / S_u[:, np.newaxis]  # (m, 5)

            # State update: x = x + K * innovation
            self.x[idx] += K * innov_u[:, np.newaxis]

            # Covariance update: P = (I - K @ H) @ P_pred
            # K @ H: (m, 5, 1) @ (m, 1, 5) → (m, 5, 5)
            KH = K[:, :, np.newaxis] * H_u[:, np.newaxis, :]  # (m, 5, 5)
            I_KH = np.eye(_N_PARAMS, dtype=np.float64)[np.newaxis, :, :] - KH  # (m, 5, 5)
            self.P[idx] = np.einsum("mij,mjk->mik", I_KH, P_pred[idx])

            # Increment observation count
            self.n_obs[idx] += 1
            self.last_clear_time[idx] = obs_time_unix

        # For prediction-only pixels (cloudy but not clear), P grows via Q.
        # We already computed P_pred = P + Q. For pixels that weren't updated,
        # store P_pred back.
        not_updated = ~update_mask
        # But only for pixels that were clear and gated (fire_gated) — for
        # truly cloudy pixels, we should also let P grow.  Actually, let's
        # always propagate P for all non-updated pixels.
        self.P[not_updated] = P_pred[not_updated]

        # --- CUSUM decay for cloudy pixels ---
        cloudy = ~clear
        if np.any(cloudy):
            dt_since_clear = obs_time_unix - self.last_clear_time  # seconds
            # Only decay where we have a valid last_clear_time
            has_history = cloudy & np.isfinite(self.last_clear_time)
            if np.any(has_history):
                tau_s = cfg.tau_decay_hours * 3600.0
                decay = np.exp(-dt_since_clear[has_history] / tau_s).astype(np.float32)
                self.S[has_history] *= decay
                # Also decay consecutive anomaly count
                self.consecutive_anomalies[has_history] = 0

        # --- CUSUM update for clear pixels ---
        initialized = self.n_obs >= cfg.min_init_observations  # (n,)
        cusum_eligible = clear & initialized

        # Store residuals (z-scores) for output; NaN where not eligible
        residuals_out = np.full(n, np.nan, dtype=np.float32)

        if np.any(cusum_eligible):
            idx_c = np.where(cusum_eligible)[0]
            z_c = z[idx_c].astype(np.float32)
            residuals_out[idx_c] = z_c

            # CUSUM update: S = max(0, S + z - k_ref)
            self.S[idx_c] = np.maximum(0.0, self.S[idx_c] + z_c - cfg.k_ref)

            # Track consecutive anomalies (z > anomaly_z_threshold)
            anomalous = z_c > cfg.anomaly_z_threshold
            # Reset counter where not anomalous, increment where anomalous
            self.consecutive_anomalies[idx_c] = np.where(
                anomalous,
                self.consecutive_anomalies[idx_c] + 1,
                0,
            ).astype(np.int16)

        # --- Fire candidate identification ---
        # CUSUM statistic exceeds threshold (accumulated evidence from multiple frames).
        # Consecutive anomaly count is tracked for diagnostics but not used for
        # candidacy — CUSUM already provides optimal multi-frame accumulation.
        cusum_triggered = self.S >= cfg.h_threshold
        candidates = cusum_eligible & cusum_triggered

        # Suppress water/industrial pixels
        candidates &= ~self.suppression_mask

        # --- Adjacent pixel requirement ---
        if cfg.require_adjacent and np.any(candidates):
            candidates = self._apply_adjacency_filter(candidates)

        # --- Auto-reset detected pixels ---
        # After detection, reset CUSUM to prevent re-firing on the same event.
        # The pixel must re-accumulate evidence for a new detection.
        if np.any(candidates):
            self.S[candidates] = 0.0
            self.consecutive_anomalies[candidates] = 0

        n_candidates = int(np.sum(candidates))
        n_initialized = int(np.sum(initialized))

        self._frame_count += 1

        elapsed_ms = (time.monotonic() - t0) * 1000.0

        if n_candidates > 0:
            logger.info(
                "CUSUM update: %d fire candidates, %d/%d pixels initialized (%.1fms)",
                n_candidates, n_initialized, n, elapsed_ms,
            )
        else:
            logger.debug(
                "CUSUM update: 0 candidates, %d/%d initialized (%.1fms)",
                n_initialized, n, elapsed_ms,
            )

        return {
            "fire_candidates": candidates,
            "residuals": residuals_out,
            "cusum_values": self.S.copy(),
            "n_candidates": n_candidates,
            "n_initialized": n_initialized,
            "timing_ms": round(elapsed_ms, 2),
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
            S=self.S,
            n_obs=self.n_obs,
            last_clear_time=self.last_clear_time,
            consecutive_anomalies=self.consecutive_anomalies,
            frame_count=np.array([self._frame_count]),
            # Metadata for validation on load
            n_pixels=np.array([self.n]),
        )
        logger.info("CUSUM state saved to %s (%d pixels, frame %d)", path, self.n, self._frame_count)

    def load_state(self, path: Optional[Path] = None) -> bool:
        """Load state from .npz file.  Returns True on success, False otherwise."""
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

            self.x = data["x"].astype(np.float64)
            self.P = data["P"].astype(np.float64)
            self.S = data["S"].astype(np.float32)
            self.n_obs = data["n_obs"].astype(np.int32)
            self.last_clear_time = data["last_clear_time"].astype(np.float64)
            self.consecutive_anomalies = data["consecutive_anomalies"].astype(np.int16)
            self._frame_count = int(data["frame_count"][0])

            logger.info(
                "CUSUM state loaded from %s (frame %d, %d/%d initialized)",
                path, self._frame_count, int(np.sum(self.n_obs >= self.cfg.min_init_observations)), self.n,
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
        self.S[idx] = 0.0
        self.n_obs[idx] = 0
        self.last_clear_time[idx] = np.nan
        self.consecutive_anomalies[idx] = 0

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
