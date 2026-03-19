"""Himawari AHI detection pipeline configuration — all tunable constants."""

from pydantic import BaseModel


class CUSUMConfig(BaseModel):
    """Configuration for the CUSUM temporal fire detection module.

    The CUSUM detector maintains a per-pixel Kalman-filtered harmonic model of
    expected BTD (BT7 - BT14) at each time of day, and runs a one-sided upper
    CUSUM on normalized residuals to flag persistent positive anomalies.
    """

    enabled: bool = True

    # --- Kalman filter ---
    # Initial diagonal variance for [T_mean, a1, b1, a2, b2, beta]
    initial_variance: list[float] = [25.0, 4.0, 4.0, 1.0, 1.0, 1.0]
    # Process noise std per parameter per time step.
    # Deliberately slow adaptation so the model can't chase fire anomalies.
    # Mean drifts ~0.001K/step = 0.14K/day (vs 1.4K/day before).
    # 6th element (beta, BT14 anomaly covariate) has slow process noise.
    process_noise_std: list[float] = [0.001, 0.0001, 0.0001, 0.00005, 0.00005, 0.0001]
    # Observation noise variance (K^2) — daytime vs nighttime
    R_day: float = 0.25
    R_night: float = 0.09
    # Legacy hard gate — replaced by soft Bayesian weighting (1 - P(fire)).
    # Retained for backward compatibility but not used in current update logic.
    fire_gate_sigma: float = 2.0
    # Minimum clear-sky observations before CUSUM is activated for a pixel
    min_init_observations: int = 48  # ~8 hours of clear sky at 10-min cadence

    # --- CUSUM decision rule ---
    k_ref: float = 0.5          # Reference value (sigma units) — slow CUSUM for small fires
    h_threshold: float = 12.0   # Decision threshold (sigma units) — legacy, not used for triggering
    k_ref_fast: float = 1.5     # Reference value for fast CUSUM — large fires in minutes
    h_threshold_fast: float = 5.0  # Decision threshold for fast CUSUM — legacy, not used for triggering
    # Note: actual trigger is P(fire) >= detection_probability_threshold,
    # which maps to S_max ≈ 5.76 with current cusum_to_logodds_scale and fire_prior.
    tau_decay_hours: float = 3.0  # Exponential decay time constant during cloud gaps

    # --- BT14 EMA ---
    bt14_ema_tau_hours: float = 4.0  # EMA time constant for BT14 background

    # --- BT14 rejection ---
    bt14_rejection_threshold: float = 3.0  # Suppress if BT14 also anomalous
    bt14_rejection_max: float = 6.0  # Don't suppress extreme BT14 (could be large fire)

    # --- Alert criteria ---
    anomaly_z_threshold: float = 1.0   # z-score above which a frame counts as anomalous
    min_consecutive_anomalies: int = 6  # Tracked for diagnostics only; not used in detection
                                        # decision (CUSUM already handles temporal accumulation)
    require_adjacent: bool = True       # Require >= 1 neighboring pixel also flagged

    # --- Bayesian fire confidence parameters ---
    fire_prior: float = 1e-5           # Prior P(fire) per pixel per frame
    cusum_to_logodds_scale: float = 2.0  # Scale factor: log_odds += scale * S_max
    min_kalman_weight: float = 0.01    # Minimum Kalman gain scaling (prevents total freeze)
    detection_probability_threshold: float = 0.5  # P(fire) threshold for candidate detection
    display_probability_threshold: float = 0.05   # P(fire) threshold for portal display
    bt14_ema_fire_threshold: float = 0.5  # Skip BT14 EMA update when fire_confidence >= this

    # --- Training data store ---
    training_store_enabled: bool = False  # Enable per-frame training data recording
    training_store_dir: str = "data/training"  # Directory for parquet training files
    training_store_background_sample_rate: float = 0.01  # Fraction of background pixels to sample

    # --- State persistence ---
    state_file: str = "data/cusum_state.npz"
    save_interval: int = 1  # Save state every N observation frames


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
    # BT14 contextual offset — daytime only (VNP14IMG Step 8: BT5 > BT5B + δ5B + offset)
    # Negative value = weak test (BT14 just needs to be roughly at/above background)
    bt14_contextual_offset_k: float = -4.0

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

    # --- Temporal persistence filter ---
    temporal_filter_enabled: bool = True
    temporal_window_size: int = 3  # Number of recent frames to buffer
    temporal_min_persistence: int = 2  # Min frames a pixel must appear in
    temporal_distance_threshold_km: float = 4.0  # "Same pixel" matching radius
    temporal_bypass_high_confidence: bool = True  # HIGH (absolute) skip filter

    # --- CUSUM temporal detection ---
    cusum: CUSUMConfig = CUSUMConfig()
