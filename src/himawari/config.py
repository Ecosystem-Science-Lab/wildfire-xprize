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
    btd_floor_k: float = 6.0
    min_background_fraction: float = 0.25
    background_window_sizes: list[int] = [11, 15, 21]

    # --- Cloud masking ---
    cloud_bt14_threshold_k: float = 265.0
    cloud_adjacency_buffer: int = 2

    # --- Sun glint ---
    sun_glint_angle_deg: float = 12.0

    # --- Output ---
    location_uncertainty_m: float = 4000.0

    # --- Confidence mapping ---
    high_btd_threshold_k: float = 15.0  # BTD anomaly > this → NOMINAL→HIGH promotion

    # Day/night SZA boundary
    sza_day_night_deg: float = 85.0
