"""Himawari observation processing pipeline — orchestrates download→decode→detect→ingest."""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

import numpy as np

from ..dedup import ingest_batch
from .config import HimawariConfig
from .converter import fire_pixels_to_detections
from .decoder import decode_hsd_to_bt
from .detection import FireDetectionResult, detect_fires
from .downloader import download_segments, list_segment_keys
from .masks import compute_cloud_adjacency, compute_cloud_mask, compute_nsw_mask

logger = logging.getLogger(__name__)


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

    # Step 6: Convert fire pixels to Detection objects (reuse SZA from detection)
    t = time.monotonic()
    detections = fire_pixels_to_detections(
        result.fire_mask, bt7, bt14, lats, lons, obs_time, result.sza, cfg
    )
    timings["convert"] = round((time.monotonic() - t) * 1000, 1)

    # Step 7: Ingest into event store
    t = time.monotonic()
    ingest_stats = await ingest_batch(detections)
    timings["ingest"] = round((time.monotonic() - t) * 1000, 1)

    timings["total"] = round((time.monotonic() - t_start) * 1000, 1)

    logger.info(
        "Himawari observation %s processed: %d detections (%d new, %d dup) in %.1fs | %s",
        obs_timestamp,
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
        "detections_new": ingest_stats["new"],
        "detections_dup": ingest_stats["duplicates"],
        "timings_ms": timings,
    }
