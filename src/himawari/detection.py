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
    sza: np.ndarray  # Solar zenith angle (degrees) — reused by converter
    n_candidates: int = 0
    n_fires: int = 0
    n_absolute: int = 0
    n_contextual: int = 0
    n_glint_downgraded: int = 0
    n_water_rejected: int = 0
    n_insufficient_bg: int = 0
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


def _compute_glint_angle(
    lats: np.ndarray, lons: np.ndarray, obs_time: datetime
) -> np.ndarray:
    """Compute sun glint angle for a geostationary satellite.

    Glint angle = angle between specular reflection direction and satellite view.
    For geostationary satellite at 140.7°E (Himawari-9), sub-satellite point is
    on the equator. Approximation uses solar geometry and satellite viewing geometry.

    Returns glint angle in degrees (float32). Lower = more glint risk.
    """
    from pyorbital.astronomy import sun_zenith_angle, get_alt_az

    # Solar position
    sun_alt, sun_az = get_alt_az(obs_time, lons, lats)
    sun_zen = 90.0 - sun_alt  # zenith = 90 - altitude

    # Satellite viewing geometry for Himawari-9 at 140.7°E
    sat_lon = 140.7
    sat_alt_km = 35786.0  # GEO altitude

    lat_r = np.radians(lats)
    dlon_r = np.radians(lons - sat_lon)

    # Satellite zenith angle from ground point
    cos_gamma = np.cos(lat_r) * np.cos(dlon_r)
    re = 6371.0
    sat_zen = np.degrees(np.arctan2(
        np.sqrt(1.0 - cos_gamma ** 2),
        cos_gamma - re / (re + sat_alt_km)
    ))

    # Satellite azimuth (from north)
    sat_az = np.degrees(np.arctan2(np.sin(dlon_r), -np.sin(lat_r) * np.cos(dlon_r)))

    # Glint angle: angular distance between specular reflection and satellite
    # Specular reflection has same zenith as sun, azimuth rotated 180°
    sun_zen_r = np.radians(sun_zen)
    sat_zen_r = np.radians(sat_zen)
    sun_az_r = np.radians(sun_az)
    sat_az_r = np.radians(sat_az)

    # Specular direction: zenith = sun_zen, azimuth = sun_az + 180
    cos_glint = (
        np.cos(sun_zen_r) * np.cos(sat_zen_r)
        + np.sin(sun_zen_r) * np.sin(sat_zen_r) * np.cos(sun_az_r - sat_az_r + np.pi)
    )
    cos_glint = np.clip(cos_glint, -1.0, 1.0)
    glint_angle = np.degrees(np.arccos(cos_glint))

    return glint_angle.astype(np.float32)


def _compute_water_mask(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Simple water mask based on distance to coast.

    Uses a coarse check: reject pixels that are clearly ocean based on
    NSW's coastline. Pixels east of the coast + small buffer are water.
    This is a rough approximation; a proper land/sea mask would be better.

    Returns boolean array — True = water pixel.
    """
    # NSW coastline approximation: east boundary varies by latitude
    # Simple model: coast is roughly at these longitudes
    # -28 to -33: ~153.5°E
    # -33 to -37: ~151°E (Sydney to border region)
    # -37 to -38: ~150°E (far south)
    # Add 0.05° buffer (~5km) for coastal pixels
    coast_lon = np.where(
        lats > -33.0,
        153.6,
        np.where(lats > -37.0, 151.5, 150.3),
    )
    return lons > coast_lon


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
        bt7: Band 7 (3.9um) brightness temperature in K
        bt14: Band 14 (11.2um) brightness temperature in K
        lats, lons: Coordinate arrays
        obs_time: Observation time (UTC)
        valid_mask: Boolean mask — True = valid pixel (in NSW, not cloud, not NaN)
        cfg: Detection configuration

    Returns:
        FireDetectionResult with fire_mask, sza, and stats.
    """
    import time

    t0 = time.monotonic()
    timings = {}

    # Compute BTD
    btd = bt7 - bt14

    # --- Step 0: Solar zenith angle ---
    t1 = time.monotonic()
    sza = compute_solar_zenith(lats, lons, obs_time)
    is_day = sza < cfg.sza_day_night_deg
    timings["sza"] = round((time.monotonic() - t1) * 1000, 1)

    result = FireDetectionResult(
        fire_mask=np.zeros(bt7.shape, dtype=np.int8),
        sza=sza,
    )

    # --- Step 0b: Water mask ---
    t1 = time.monotonic()
    water_mask = _compute_water_mask(lats, lons)
    valid_land = valid_mask & (~water_mask)
    result.n_water_rejected = int(np.sum(valid_mask & water_mask))
    timings["water_mask"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 0c: Sun glint zone (daytime only) ---
    # Instead of blanket rejection, flag glint-zone pixels for confidence downgrade.
    # Fires near water should be detected at low confidence, not missed entirely.
    t1 = time.monotonic()
    glint_zone = np.zeros(bt7.shape, dtype=bool)
    if np.any(valid_land & is_day):
        glint_angle = _compute_glint_angle(lats, lons, obs_time)
        glint_zone = is_day & (glint_angle < cfg.sun_glint_angle_deg)
    timings["glint"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 1: Absolute thresholds → HIGH confidence ---
    t1 = time.monotonic()
    saturated = valid_land & (bt7 >= cfg.saturated_bt7_k)
    extreme_day = valid_land & is_day & (bt7 >= cfg.extreme_day_bt7_k)
    extreme_night = valid_land & (~is_day) & (bt7 >= cfg.extreme_night_bt7_k)
    absolute_fire = saturated | extreme_day | extreme_night
    result.fire_mask[absolute_fire] = 3  # HIGH
    result.n_absolute = int(np.sum(absolute_fire))
    timings["absolute"] = round((time.monotonic() - t1) * 1000, 1)

    # --- Step 2: Candidate selection ---
    t1 = time.monotonic()
    day_candidate = (
        valid_land & is_day & (~absolute_fire)
        & (bt7 >= cfg.candidate_day_bt7_k)
        & (btd >= cfg.candidate_day_btd_k)
    )
    night_candidate = (
        valid_land & (~is_day) & (~absolute_fire)
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
            "Detection complete: %d absolute, 0 candidates, 0 contextual "
            "(%d water, %d glint rejected)",
            result.n_absolute, result.n_water_rejected, result.n_glint_rejected,
        )
        result.n_fires = result.n_absolute
        return result

    # --- Step 3: Background characterization ---
    t1 = time.monotonic()

    # Background fire exclusion: hot pixels that aren't fire candidates
    # but would contaminate background statistics
    bg_fire_day = (
        is_day & (bt7 >= cfg.bg_fire_day_bt7_k) & (btd >= cfg.bg_fire_day_btd_k)
    )
    bg_fire_night = (
        (~is_day) & (bt7 >= cfg.bg_fire_night_bt7_k) & (btd >= cfg.bg_fire_night_btd_k)
    )
    bg_fire_exclude = bg_fire_day | bg_fire_night

    # Background pixels: valid land, not candidate, not absolute fire, not bg fire
    bg_mask = valid_land & (~candidates) & (~absolute_fire) & (~bg_fire_exclude)

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

        # uniform_filter computes mean of the window, so count = fraction of valid bg pixels
        # To get actual count: count * win_size^2
        actual_count = count * total_pixels

        sufficient = actual_count >= (cfg.min_background_fraction * total_pixels)

        # BT7 background stats (float64 to avoid catastrophic cancellation in variance)
        bt7_bg = np.where(bg_mask, bt7, 0.0).astype(np.float64)
        bt7_sum = uniform_filter(bt7_bg, size=win_size, mode="constant", cval=0.0) * total_pixels
        bt7_sq = np.where(bg_mask, bt7.astype(np.float64) ** 2, 0.0)
        bt7_sq_sum = uniform_filter(bt7_sq, size=win_size, mode="constant", cval=0.0) * total_pixels

        safe_count = np.where(actual_count > 0, actual_count, 1.0).astype(np.float64)
        mean_bt7 = (bt7_sum / safe_count).astype(np.float32)
        var_bt7 = bt7_sq_sum / safe_count - (bt7_sum / safe_count) ** 2
        var_bt7 = np.maximum(var_bt7, 0.0)
        std_bt7 = np.sqrt(var_bt7).astype(np.float32)
        std_bt7 = np.maximum(std_bt7, cfg.min_background_std_k)  # Floor

        # BTD background stats (float64 for same reason)
        btd_bg = np.where(bg_mask, btd, 0.0).astype(np.float64)
        btd_sum = uniform_filter(btd_bg, size=win_size, mode="constant", cval=0.0) * total_pixels
        btd_sq = np.where(bg_mask, btd.astype(np.float64) ** 2, 0.0)
        btd_sq_sum = uniform_filter(btd_sq, size=win_size, mode="constant", cval=0.0) * total_pixels

        mean_btd = (btd_sum / safe_count).astype(np.float32)
        var_btd = btd_sq_sum / safe_count - (btd_sum / safe_count) ** 2
        var_btd = np.maximum(var_btd, 0.0)
        std_btd = np.sqrt(var_btd).astype(np.float32)
        std_btd = np.maximum(std_btd, cfg.min_background_std_k)  # Floor

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
    btd_floor = np.where(is_day, cfg.btd_floor_day_k, cfg.btd_floor_night_k)
    contextual_btd_floor = btd > (bg_btd_mean + btd_floor)

    # Absolute BT7 floor per spec (prevents warm non-fire pixels at night)
    bt7_floor = np.where(
        is_day, cfg.contextual_floor_day_bt7_k, cfg.contextual_floor_night_bt7_k
    )
    contextual_bt7_floor = bt7 >= bt7_floor

    contextual_fire = (
        candidates
        & bg_sufficient
        & contextual_bt7
        & contextual_btd_sigma
        & contextual_btd_floor
        & contextual_bt7_floor
    )
    result.n_contextual = int(np.sum(contextual_fire))

    # Track candidates with insufficient background (silently dropped)
    insufficient_bg = candidates & (~bg_sufficient)
    result.n_insufficient_bg = int(np.sum(insufficient_bg))
    if result.n_insufficient_bg > 0:
        logger.warning(
            "%d candidate pixels had insufficient background — unclassified",
            result.n_insufficient_bg,
        )

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

    # Glint-zone downgrade: NOMINAL→LOW in glint zones (fires near water
    # should be detected at low confidence rather than missed)
    glint_downgrade = (result.fire_mask == 2) & glint_zone
    result.fire_mask[glint_downgrade] = 1  # NOMINAL → LOW
    result.n_glint_downgraded = int(np.sum(glint_downgrade))

    timings["confidence"] = round((time.monotonic() - t1) * 1000, 1)

    result.n_fires = result.n_absolute + result.n_contextual
    timings["total"] = round((time.monotonic() - t0) * 1000, 1)
    result.timing_ms = timings

    logger.info(
        "Detection complete: %d absolute, %d candidates, %d contextual, %d total fires "
        "(%d water rejected, %d glint downgraded, %d insufficient bg) (%.0fms)",
        result.n_absolute,
        result.n_candidates,
        result.n_contextual,
        result.n_fires,
        result.n_water_rejected,
        result.n_glint_downgraded,
        result.n_insufficient_bg,
        timings["total"],
    )

    return result
