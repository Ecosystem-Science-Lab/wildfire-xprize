"""Core contextual fire detection algorithm — vectorized numpy/scipy."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from scipy.ndimage import uniform_filter

from .config import HimawariConfig

logger = logging.getLogger(__name__)


@dataclass
class FireDetectionResult:
    """Result of fire detection algorithm."""

    fire_mask: np.ndarray  # 0=no fire, 1=LOW, 2=NOMINAL, 3=HIGH
    n_candidates: int = 0
    n_fires: int = 0
    n_absolute: int = 0
    n_contextual: int = 0
    timing_ms: dict = field(default_factory=dict)


def compute_solar_zenith(
    lats: np.ndarray, lons: np.ndarray, obs_time: datetime
) -> np.ndarray:
    """Compute solar zenith angle array using pyorbital.

    Returns SZA in degrees (float32).
    """
    from pyorbital.astronomy import sun_zenith_angle

    sza = sun_zenith_angle(obs_time, lons, lats)
    return sza.astype(np.float32)


def detect_fires(
    bt7: np.ndarray,
    bt14: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    obs_time: datetime,
    valid_mask: np.ndarray,
    cfg: HimawariConfig,
) -> FireDetectionResult:
    """Run contextual fire detection algorithm.

    Args:
        bt7: Band 7 (3.9µm) brightness temperature in K
        bt14: Band 14 (11.2µm) brightness temperature in K
        lats, lons: Coordinate arrays
        obs_time: Observation time (UTC)
        valid_mask: Boolean mask — True = valid pixel (in NSW, not cloud, not NaN)
        cfg: Detection configuration

    Returns:
        FireDetectionResult with fire_mask and stats.
    """
    import time

    t0 = time.monotonic()
    result = FireDetectionResult(fire_mask=np.zeros(bt7.shape, dtype=np.int8))
    timings = {}

    # Compute BTD
    btd = bt7 - bt14

    # Replace invalid pixels with NaN for background stats
    bt7_valid = np.where(valid_mask, bt7, np.nan)
    bt14_valid = np.where(valid_mask, bt14, np.nan)
    btd_valid = np.where(valid_mask, btd, np.nan)

    # --- Step 0: Solar zenith angle ---
    t1 = time.monotonic()
    sza = compute_solar_zenith(lats, lons, obs_time)
    is_day = sza < cfg.sza_day_night_deg
    timings["sza"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 1: Absolute thresholds → HIGH confidence ---
    t1 = time.monotonic()
    saturated = valid_mask & (bt7 >= cfg.saturated_bt7_k)
    extreme_day = valid_mask & is_day & (bt7 >= cfg.extreme_day_bt7_k)
    extreme_night = valid_mask & (~is_day) & (bt7 >= cfg.extreme_night_bt7_k)
    absolute_fire = saturated | extreme_day | extreme_night
    result.fire_mask[absolute_fire] = 3  # HIGH
    result.n_absolute = int(np.sum(absolute_fire))
    timings["absolute"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 2: Candidate selection ---
    t1 = time.monotonic()
    day_candidate = (
        valid_mask & is_day & (~absolute_fire)
        & (bt7 >= cfg.candidate_day_bt7_k)
        & (btd >= cfg.candidate_day_btd_k)
    )
    night_candidate = (
        valid_mask & (~is_day) & (~absolute_fire)
        & (bt7 >= cfg.candidate_night_bt7_k)
        & (btd >= cfg.candidate_night_btd_k)
    )
    candidates = day_candidate | night_candidate
    result.n_candidates = int(np.sum(candidates))
    timings["candidates"] = round((time.monotonic() - t1) * 1000, 1)

    if result.n_candidates == 0:
        timings["total"] = round((time.monotonic() - t0) * 1000, 1)
        result.timing_ms = timings
        logger.info(
            "Detection complete: %d absolute, 0 candidates, 0 contextual",
            result.n_absolute,
        )
        result.n_fires = result.n_absolute
        return result

    # --- Step 3: Background characterization ---
    t1 = time.monotonic()

    # Background pixels: valid, not candidate, not already absolute fire
    bg_mask = valid_mask & (~candidates) & (~absolute_fire)

    # Try progressively larger windows
    bg_bt7_mean = np.full(bt7.shape, np.nan, dtype=np.float32)
    bg_bt7_std = np.full(bt7.shape, np.nan, dtype=np.float32)
    bg_btd_mean = np.full(bt7.shape, np.nan, dtype=np.float32)
    bg_btd_std = np.full(bt7.shape, np.nan, dtype=np.float32)
    bg_sufficient = np.zeros(bt7.shape, dtype=bool)

    for win_size in cfg.background_window_sizes:
        need_bg = candidates & (~bg_sufficient)
        if not np.any(need_bg):
            break

        # Convolution trick: compute mean and std using uniform_filter
        bg_float = bg_mask.astype(np.float32)
        count = uniform_filter(bg_float, size=win_size, mode="constant", cval=0.0)
        total_pixels = win_size * win_size
        frac = count  # count is already fraction-like from uniform_filter normalization

        # uniform_filter computes mean of the window, so count = fraction of valid bg pixels
        # To get actual count: count * win_size^2
        actual_count = count * total_pixels

        sufficient = actual_count >= (cfg.min_background_fraction * total_pixels)

        # BT7 background stats
        bt7_bg = np.where(bg_mask, bt7, 0.0).astype(np.float32)
        bt7_sum = uniform_filter(bt7_bg, size=win_size, mode="constant", cval=0.0) * total_pixels
        bt7_sq = np.where(bg_mask, bt7 ** 2, 0.0).astype(np.float32)
        bt7_sq_sum = uniform_filter(bt7_sq, size=win_size, mode="constant", cval=0.0) * total_pixels

        safe_count = np.where(actual_count > 0, actual_count, 1.0)
        mean_bt7 = bt7_sum / safe_count
        var_bt7 = bt7_sq_sum / safe_count - mean_bt7 ** 2
        var_bt7 = np.maximum(var_bt7, 0.0)  # Numerical stability
        std_bt7 = np.sqrt(var_bt7)

        # BTD background stats
        btd_bg = np.where(bg_mask, btd, 0.0).astype(np.float32)
        btd_sum = uniform_filter(btd_bg, size=win_size, mode="constant", cval=0.0) * total_pixels
        btd_sq = np.where(bg_mask, btd ** 2, 0.0).astype(np.float32)
        btd_sq_sum = uniform_filter(btd_sq, size=win_size, mode="constant", cval=0.0) * total_pixels

        mean_btd = btd_sum / safe_count
        var_btd = btd_sq_sum / safe_count - mean_btd ** 2
        var_btd = np.maximum(var_btd, 0.0)
        std_btd = np.sqrt(var_btd)

        # Update where newly sufficient
        new_sufficient = sufficient & (~bg_sufficient)
        bg_bt7_mean = np.where(new_sufficient, mean_bt7, bg_bt7_mean)
        bg_bt7_std = np.where(new_sufficient, std_bt7, bg_bt7_std)
        bg_btd_mean = np.where(new_sufficient, mean_btd, bg_btd_mean)
        bg_btd_std = np.where(new_sufficient, std_btd, bg_btd_std)
        bg_sufficient = bg_sufficient | sufficient

    timings["background"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 4: Contextual fire tests ---
    t1 = time.monotonic()

    sigma = np.where(is_day, cfg.sigma_day, cfg.sigma_night)

    contextual_bt7 = bt7 > (bg_bt7_mean + sigma * bg_bt7_std)
    contextual_btd_sigma = btd > (bg_btd_mean + sigma * bg_btd_std)
    contextual_btd_floor = btd > (bg_btd_mean + cfg.btd_floor_k)

    contextual_fire = (
        candidates
        & bg_sufficient
        & contextual_bt7
        & contextual_btd_sigma
        & contextual_btd_floor
    )
    result.n_contextual = int(np.sum(contextual_fire))
    timings["contextual"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 5: Confidence assignment ---
    t1 = time.monotonic()

    # Contextual fires: check BTD anomaly magnitude
    btd_anomaly = btd - bg_btd_mean
    high_btd = contextual_fire & (btd_anomaly > cfg.high_btd_threshold_k)
    low_btd = contextual_fire & (~high_btd)

    result.fire_mask[low_btd] = 1  # LOW
    result.fire_mask[high_btd] = 2  # NOMINAL
    # Absolute fires already set to 3 (HIGH)

    timings["confidence"] = round((time.monotonic() - t1) * 1000, 1)

    result.n_fires = result.n_absolute + result.n_contextual
    timings["total"] = round((time.monotonic() - t0) * 1000, 1)
    result.timing_ms = timings

    logger.info(
        "Detection complete: %d absolute, %d candidates, %d contextual, %d total fires (%.0fms)",
        result.n_absolute,
        result.n_candidates,
        result.n_contextual,
        result.n_fires,
        timings["total"],
    )

    return result
