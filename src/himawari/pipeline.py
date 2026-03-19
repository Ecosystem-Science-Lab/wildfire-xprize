"""Himawari observation processing pipeline — orchestrates download→decode→detect→ingest."""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

import numpy as np

from ..dedup import ingest_batch
from .config import HimawariConfig
from .converter import fire_pixels_to_detections
from .cusum import CUSUMTemporalDetector, cusum_to_detections, merge_detections
from .training_store import TrainingStore
from .decoder import decode_hsd_to_bt
from .detection import FireDetectionResult, detect_fires
from .downloader import download_segments, list_segment_keys
from .masks import compute_cloud_adjacency, compute_cloud_mask, compute_nsw_mask
from .persistence import TemporalFilter
from .static_masks import compute_industrial_mask, compute_water_mask

logger = logging.getLogger(__name__)

# Module-level temporal filter instance. Persists across observations to
# maintain the rolling buffer. Initialized on first use via _get_filter().
_temporal_filter: Optional[TemporalFilter] = None
_temporal_filter_cfg_hash: Optional[int] = None

# Module-level CUSUM detector. Persists across observations to maintain
# per-pixel Kalman and CUSUM state. Initialized on first use.
_cusum_detector: Optional[CUSUMTemporalDetector] = None
_cusum_grid_key: Optional[tuple] = None  # (shape, cusum_config_hash)

# Module-level training store. Persists across observations to buffer
# training data within a single day. Initialized on first use.
_training_store: Optional[TrainingStore] = None


def _get_temporal_filter(cfg: HimawariConfig) -> TemporalFilter:
    """Get or create the module-level TemporalFilter, reinitializing if config changed."""
    global _temporal_filter, _temporal_filter_cfg_hash

    cfg_hash = hash((
        cfg.temporal_window_size,
        cfg.temporal_min_persistence,
        cfg.temporal_distance_threshold_km,
        cfg.temporal_bypass_high_confidence,
    ))

    if _temporal_filter is None or _temporal_filter_cfg_hash != cfg_hash:
        _temporal_filter = TemporalFilter(
            window_size=cfg.temporal_window_size,
            min_persistence=cfg.temporal_min_persistence,
            distance_threshold_km=cfg.temporal_distance_threshold_km,
            bypass_high_confidence=cfg.temporal_bypass_high_confidence,
        )
        _temporal_filter_cfg_hash = cfg_hash
        logger.info(
            "Temporal filter initialized: window=%d, min_persistence=%d, "
            "distance=%.1fkm, bypass_high=%s",
            cfg.temporal_window_size,
            cfg.temporal_min_persistence,
            cfg.temporal_distance_threshold_km,
            cfg.temporal_bypass_high_confidence,
        )

    return _temporal_filter


def _get_cusum_detector(
    cfg: HimawariConfig,
    grid_shape: tuple[int, int],
    lats: np.ndarray,
    lons: np.ndarray,
    valid_mask: np.ndarray,
) -> CUSUMTemporalDetector:
    """Get or create the module-level CUSUMTemporalDetector.

    Re-creates the detector if the grid shape or config changes.  On first
    creation (or re-creation), attempts to load persisted state from disk.
    """
    global _cusum_detector, _cusum_grid_key

    cusum_cfg = cfg.cusum
    cfg_hash = hash((
        cusum_cfg.k_ref,
        cusum_cfg.h_threshold,
        cusum_cfg.k_ref_fast,
        cusum_cfg.h_threshold_fast,
        cusum_cfg.fire_gate_sigma,
        cusum_cfg.min_init_observations,
        cusum_cfg.tau_decay_hours,
        cusum_cfg.anomaly_z_threshold,
        cusum_cfg.min_consecutive_anomalies,
        cusum_cfg.require_adjacent,
        tuple(cusum_cfg.initial_variance),
        tuple(cusum_cfg.process_noise_std),
        cusum_cfg.R_day,
        cusum_cfg.R_night,
        cusum_cfg.bt14_ema_tau_hours,
        cusum_cfg.bt14_rejection_threshold,
        cusum_cfg.bt14_rejection_max,
        cusum_cfg.fire_prior,
        cusum_cfg.cusum_to_logodds_scale,
        cusum_cfg.min_kalman_weight,
        cusum_cfg.detection_probability_threshold,
    ))
    grid_key = (grid_shape, cfg_hash)

    if _cusum_detector is not None and _cusum_grid_key == grid_key:
        return _cusum_detector

    # Build suppression mask (water + industrial) on the full grid
    water = compute_water_mask(lats, lons)
    industrial = compute_industrial_mask(lats, lons)
    suppression = (water | industrial).ravel()

    n_pixels = grid_shape[0] * grid_shape[1]
    pixel_lons = lons.ravel().astype(np.float32)

    _cusum_detector = CUSUMTemporalDetector(
        n_pixels=n_pixels,
        pixel_lons=pixel_lons,
        cfg=cusum_cfg,
        suppression_mask=suppression,
    )
    _cusum_detector.set_grid_shape(grid_shape[0], grid_shape[1])

    # Try to restore persisted state
    _cusum_detector.load_state()

    _cusum_grid_key = grid_key
    logger.info(
        "CUSUM detector initialized: %d pixels, grid %s, %.1f%% already initialized",
        n_pixels, grid_shape, _cusum_detector.initialized_fraction * 100,
    )

    return _cusum_detector


async def process_observation(obs_timestamp: str, cfg: HimawariConfig) -> dict:
    """Process a single Himawari observation end-to-end.

    Args:
        obs_timestamp: "YYYYMMDD_HHMM" format
        cfg: Pipeline configuration

    Returns:
        dict with stats and timing breakdown.
    """
    import asyncio

    t_start = time.monotonic()
    timings: dict[str, float] = {}

    # Step 1: List segment keys
    t = time.monotonic()
    segment_keys = await asyncio.to_thread(list_segment_keys, cfg, obs_timestamp)
    timings["list_keys"] = round((time.monotonic() - t) * 1000, 1)

    # Validate we have all expected files
    expected = len(cfg.bands) * len(cfg.nsw_segments)
    actual = sum(len(v) for v in segment_keys.values())
    if actual < expected:
        logger.warning(
            "Observation %s: expected %d segment files, found %d — skipping",
            obs_timestamp, expected, actual,
        )
        return {"obs": obs_timestamp, "status": "incomplete", "files_found": actual}

    # Step 2: Download segments to temp directory
    with tempfile.TemporaryDirectory(prefix="himawari_") as tmpdir:
        t = time.monotonic()
        local_files = await asyncio.to_thread(
            download_segments, cfg, segment_keys, Path(tmpdir)
        )
        timings["download"] = round((time.monotonic() - t) * 1000, 1)

        # Step 3: Decode HSD to brightness temperature arrays
        t = time.monotonic()
        data = await asyncio.to_thread(
            decode_hsd_to_bt, local_files["B07"], local_files["B14"]
        )
        timings["decode"] = round((time.monotonic() - t) * 1000, 1)

    # Decoder already crops to NSW bbox
    bt7 = data["bt7"]
    bt14 = data["bt14"]
    lats = data["lats"]
    lons = data["lons"]
    obs_time = data["obs_time"]

    logger.info(
        "Observation %s: decoded array shape %s", obs_timestamp, bt7.shape,
    )

    # Step 4: Build masks (on pre-cropped arrays)
    t = time.monotonic()
    nsw_mask = compute_nsw_mask(lats, lons)
    cloud_mask = compute_cloud_mask(bt14, cfg.cloud_bt14_threshold_k)
    cloud_adj = compute_cloud_adjacency(cloud_mask, cfg.cloud_adjacency_buffer)

    # Valid = in NSW, not cloud/adjacent, finite BT values
    valid_mask = nsw_mask & (~cloud_adj) & np.isfinite(bt7) & np.isfinite(bt14)
    timings["masks"] = round((time.monotonic() - t) * 1000, 1)

    n_valid = int(np.sum(valid_mask))
    n_cloud = int(np.sum(cloud_mask & nsw_mask))
    logger.info(
        "Observation %s: %d valid pixels, %d cloud pixels in NSW",
        obs_timestamp, n_valid, n_cloud,
    )

    # Step 5: Run fire detection
    t = time.monotonic()
    result: FireDetectionResult = await asyncio.to_thread(
        detect_fires, bt7, bt14, lats, lons, obs_time, valid_mask, cfg
    )
    timings["detection"] = round((time.monotonic() - t) * 1000, 1)

    # Step 5b: CUSUM temporal detection (runs parallel to contextual)
    cusum_stats: dict = {}
    cusum_detections: list = []
    if cfg.cusum.enabled:
        t = time.monotonic()
        cusum = _get_cusum_detector(cfg, bt7.shape, lats, lons, valid_mask)

        # Flatten arrays for CUSUM (operates on 1-D arrays)
        btd_flat = (bt7 - bt14).ravel()
        bt14_flat_arr = bt14.ravel()
        clear_flat = valid_mask.ravel()
        is_day_flat = (result.sza < cfg.sza_day_night_deg).ravel()
        obs_time_unix = obs_time.replace(
            tzinfo=__import__("datetime").timezone.utc
        ).timestamp() if obs_time.tzinfo is None else obs_time.timestamp()

        cusum_result = await asyncio.to_thread(
            cusum.update,
            btd_flat,
            bt14_flat_arr,
            clear_flat,
            is_day_flat,
            obs_time_unix,
        )

        # Extract fire probability stats for reporting
        fp = cusum_result.get("fire_probability")
        max_prob = float(np.nanmax(fp)) if fp is not None and np.any(np.isfinite(fp)) else 0.0
        n_display = 0
        if fp is not None:
            n_display = int(np.sum(
                np.isfinite(fp) & (fp >= cfg.cusum.display_probability_threshold)
            ))

        cusum_stats = {
            "n_candidates": cusum_result["n_candidates"],
            "n_bt14_rejected": cusum_result["n_bt14_rejected"],
            "n_initialized": cusum_result["n_initialized"],
            "initialized_pct": round(cusum.initialized_fraction * 100, 1),
            "max_fire_probability": round(max_prob, 6),
            "n_display_threshold": n_display,
            "timing_ms": cusum_result["timing_ms"],
        }
        timings["cusum"] = round((time.monotonic() - t) * 1000, 1)

        # Convert CUSUM candidates to Detection objects
        if cusum_result["n_candidates"] > 0:
            cusum_detections = cusum_to_detections(
                cusum_result,
                lats.ravel(),
                lons.ravel(),
                bt7.ravel(),
                bt14.ravel(),
                obs_time,
                result.sza.ravel(),
                cfg,
            )

        # Record training data if enabled
        if cfg.cusum.training_store_enabled:
            global _training_store
            if _training_store is None:
                _training_store = TrainingStore(
                    output_dir=cfg.cusum.training_store_dir,
                    background_sample_rate=cfg.cusum.training_store_background_sample_rate,
                )
            diag = cusum_result.get("diagnostics", {})
            try:
                # Compute predicted BTD for training features
                # btd_predicted = btd_observed - residual * sigma
                # We approximate: btd_predicted = btd - (z * sigma) but we
                # don't have sigma readily; use btd - innovation instead.
                # Simpler: btd_predicted = btd_flat - innovation residual (unnormalized)
                # For now, use btd_flat - z_scores * sqrt(R) as approximation
                btd_pred_approx = btd_flat - np.where(
                    np.isfinite(cusum_result["residuals"]),
                    cusum_result["residuals"],
                    0.0,
                ).astype(np.float64) * np.sqrt(np.where(is_day_flat, cfg.cusum.R_day, cfg.cusum.R_night))

                _training_store.record_frame(
                    obs_time=obs_time,
                    lats=lats.ravel(),
                    lons=lons.ravel(),
                    bt7=bt7.ravel(),
                    bt14=bt14.ravel(),
                    btd=btd_flat,
                    btd_predicted=btd_pred_approx.astype(np.float32),
                    z_scores=cusum_result["residuals"],
                    fire_prob=cusum_result["fire_probability"],
                    cusum_slow=diag.get("S_slow", cusum_result["cusum_values_slow"]),
                    cusum_fast=diag.get("S_fast", cusum_result["cusum_values_fast"]),
                    bt14_anomaly=diag.get("bt14_anomaly", np.zeros_like(btd_flat, dtype=np.float32)),
                    kalman_weight=diag.get("kalman_weight", np.ones_like(btd_flat, dtype=np.float32)),
                    cloud_mask=~clear_flat,
                    is_day=is_day_flat,
                )
            except Exception:
                logger.warning("Failed to record training data", exc_info=True)

        # Persist state periodically
        if cfg.cusum.save_interval > 0 and cusum.frame_count % cfg.cusum.save_interval == 0:
            try:
                cusum.save_state()
            except Exception:
                logger.warning("Failed to save CUSUM state", exc_info=True)

    # Step 6: Convert fire pixels to Detection objects (reuse SZA from detection)
    t = time.monotonic()
    detections = fire_pixels_to_detections(
        result.fire_mask, bt7, bt14, lats, lons, obs_time, result.sza, cfg
    )

    # Merge contextual + CUSUM detections (dedup same-pixel, boost corroborated)
    if cusum_detections:
        detections = merge_detections(detections, cusum_detections)

    timings["convert"] = round((time.monotonic() - t) * 1000, 1)
    n_raw_detections = len(detections)

    # Step 6b: Temporal persistence filter — reduces false positives by
    # requiring fire pixels to appear in multiple consecutive frames.
    # HIGH confidence (absolute threshold) detections bypass this filter.
    filter_stats: dict = {}
    if cfg.temporal_filter_enabled and detections:
        t = time.monotonic()
        tf = _get_temporal_filter(cfg)
        detections, filter_stats = tf.filter_detections(detections, obs_time)
        timings["temporal_filter"] = round((time.monotonic() - t) * 1000, 1)
    elif cfg.temporal_filter_enabled:
        # No detections, but still update the buffer with an empty frame
        # so the window slides correctly.
        t = time.monotonic()
        tf = _get_temporal_filter(cfg)
        detections, filter_stats = tf.filter_detections([], obs_time)
        timings["temporal_filter"] = round((time.monotonic() - t) * 1000, 1)

    # Step 7: Ingest into event store
    t = time.monotonic()
    ingest_stats = await ingest_batch(detections)
    timings["ingest"] = round((time.monotonic() - t) * 1000, 1)

    timings["total"] = round((time.monotonic() - t_start) * 1000, 1)

    logger.info(
        "Himawari observation %s processed: %d detections → %d after filter "
        "(%d new, %d dup) in %.1fs | %s",
        obs_timestamp,
        n_raw_detections,
        len(detections),
        ingest_stats["new"],
        ingest_stats["duplicates"],
        timings["total"] / 1000,
        " ".join(f"{k}={v}ms" for k, v in timings.items()),
    )

    return {
        "obs": obs_timestamp,
        "status": "ok",
        "n_fires": result.n_fires,
        "n_absolute": result.n_absolute,
        "n_contextual": result.n_contextual,
        "n_candidates": result.n_candidates,
        "n_raw_detections": n_raw_detections,
        "detections_new": ingest_stats["new"],
        "detections_dup": ingest_stats["duplicates"],
        "temporal_filter": filter_stats,
        "cusum": cusum_stats,
        "timings_ms": timings,
    }
