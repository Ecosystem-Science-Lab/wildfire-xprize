"""Himawari AHI detection pipeline configuration — all tunable constants."""

from pydantic import BaseModel


class HimawariConfig(BaseModel):
    """Configuration for Himawari-9 AHI fire detection pipeline."""

    # S3 source
    bucket: str = "noaa-himawari9"
    prefix: str = "AHI-L1b-FLDK"
    region: str = "us-east-1"

    # Polling
    poll_interval_s: int = 120
    max_observation_age_min: int = 30

    # Bands and segments
    bands: list[str] = ["B07", "B14"]
    nsw_segments: list[str] = ["0810", "0910"]

    # --- Absolute thresholds (skip contextual) ---
    saturated_bt7_k: float = 400.0
    extreme_night_bt7_k: float = 320.0
    extreme_day_bt7_k: float = 360.0

    # --- Candidate selection thresholds ---
    # Night (SZA >= 85°)
    candidate_night_bt7_k: float = 290.0
    candidate_night_btd_k: float = 10.0
    # Day (SZA < 85°)
    candidate_day_bt7_k: float = 315.0
    candidate_day_btd_k: float = 22.0

    # --- Contextual thresholds ---
    sigma_day: float = 3.5
    sigma_night: float = 3.0
    btd_floor_day_k: float = 10.0
    btd_floor_night_k: float = 8.0
    min_background_fraction: float = 0.25
    background_window_sizes: list[int] = [11, 15, 21, 31]
    # Absolute BT7 floor for contextual fires (per spec Step 5)
    contextual_floor_day_bt7_k: float = 310.0
    contextual_floor_night_bt7_k: float = 295.0
    # Minimum background std to prevent false positives in homogeneous terrain
    min_background_std_k: float = 2.0

    # --- Background fire exclusion (excluded from bg stats, not flagged as fire) ---
    bg_fire_day_bt7_k: float = 335.0
    bg_fire_day_btd_k: float = 30.0
    bg_fire_night_bt7_k: float = 300.0
    bg_fire_night_btd_k: float = 10.0

    # --- Cloud masking ---
    cloud_bt14_threshold_k: float = 270.0  # Raised from 265 to catch warm/thin clouds
    cloud_adjacency_buffer: int = 2

    # --- Sun glint ---
    sun_glint_angle_deg: float = 12.0

    # --- Output ---
    location_uncertainty_m: float = 4000.0

    # --- Confidence mapping ---
    high_btd_threshold_k: float = 15.0  # BTD anomaly > this → NOMINAL→HIGH promotion

    # Day/night SZA boundary
    sza_day_night_deg: float = 85.0
