#!/usr/bin/env python3
"""Validate the Himawari fire detection pipeline against FIRMS ground truth.

Processes archived Himawari observations through both contextual and CUSUM
detectors, matches detections against FIRMS fire events, and computes
performance metrics: detection rate, latency, early detection rate, false
alarm rate.

Data sources:
  - Himawari cache:  data/himawari_cache/YYYYMMDD_HHMM/*.DAT.bz2
  - FIRMS targets:   data/calibration/fire_targets.json
  - Weather data:    data/weather/silo/ (optional, for stratification)

Outputs:
  - data/validation/results.csv      — per-event matching results
  - data/validation/summary.json     — aggregate performance metrics
  - Console summary with key numbers

Usage:
    # Process everything in the cache
    python scripts/validate_pipeline.py

    # Process a date range
    python scripts/validate_pipeline.py --start-date 20260301 --end-date 20260310

    # Quick test (5 observations)
    python scripts/validate_pipeline.py --max-obs 5

    # Resume from checkpoint
    python scripts/validate_pipeline.py --resume

    # Skip CUSUM (contextual only)
    python scripts/validate_pipeline.py --no-cusum
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.himawari.config import CUSUMConfig, HimawariConfig
from src.himawari.cusum import CUSUMTemporalDetector
from src.himawari.detection import FireDetectionResult, compute_solar_zenith, detect_fires
from src.himawari.masks import compute_cloud_adjacency, compute_cloud_mask, compute_nsw_mask
from src.himawari.static_masks import compute_industrial_mask, compute_water_mask

# Suppress noisy third-party logs and runtime warnings
warnings.filterwarnings("ignore", message="invalid value encountered in log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
logging.getLogger("satpy").setLevel(logging.WARNING)
logging.getLogger("pyresample").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("rasterio").setLevel(logging.WARNING)

# Paths
CACHE_DIR = PROJECT_ROOT / "data" / "himawari_cache"
FIRE_TARGETS_PATH = PROJECT_ROOT / "data" / "calibration" / "fire_targets.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "validation"
CHECKPOINT_PATH = OUTPUT_DIR / "checkpoint.json"

# Matching parameters
MATCH_RADIUS_KM = 5.0  # km — match detection to FIRMS event if within this distance
FALSE_ALARM_WINDOW_HOURS = 24.0  # hours — detection with no FIRMS match within this window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km between two points."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def haversine_km_vectorized(
    lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float
) -> np.ndarray:
    """Vectorized haversine distance from arrays of points to a single point."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def discover_cache_observations(
    cache_dir: Path,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[tuple[str, Path]]:
    """Discover observation directories and loose files in the cache.

    Returns sorted list of (obs_timestamp, obs_dir_or_None) tuples.
    obs_timestamp is "YYYYMMDD_HHMM" format.

    Handles two layouts:
      1. Subdirectory: data/himawari_cache/YYYYMMDD_HHMM/*.DAT.bz2
      2. Loose files:  data/himawari_cache/HS_H09_YYYYMMDD_HHMM_*.DAT.bz2
    """
    observations: dict[str, Path | None] = {}

    # 1. Subdirectories
    for d in cache_dir.iterdir():
        if d.is_dir() and len(d.name) == 13 and "_" in d.name:
            # Validate format: YYYYMMDD_HHMM
            try:
                datetime.strptime(d.name, "%Y%m%d_%H%M")
                observations[d.name] = d
            except ValueError:
                continue

    # 2. Loose files in cache root
    for f in cache_dir.glob("HS_H09_*_B*_FLDK_R20_S*.DAT.bz2"):
        if f.is_file():
            # Extract timestamp from filename: HS_H09_YYYYMMDD_HHMM_B07_...
            parts = f.name.split("_")
            if len(parts) >= 4:
                ts = f"{parts[2]}_{parts[3]}"
                try:
                    datetime.strptime(ts, "%Y%m%d_%H%M")
                    if ts not in observations:
                        observations[ts] = None  # None = loose files in cache root
                except ValueError:
                    continue

    # Filter by date range
    if start_date or end_date:
        filtered = {}
        for ts, path in observations.items():
            date_part = ts.split("_")[0]
            if start_date and date_part < start_date:
                continue
            if end_date and date_part > end_date:
                continue
            filtered[ts] = path
        observations = filtered

    return sorted(observations.items(), key=lambda x: x[0])


def get_observation_files(
    cache_dir: Path, obs_ts: str, obs_dir: Optional[Path]
) -> tuple[list[Path], list[Path]]:
    """Get B07 and B14 files for an observation.

    Returns (b07_files, b14_files). Either list may be empty if files are missing.
    """
    if obs_dir is not None and obs_dir.is_dir():
        # Files in subdirectory
        all_files = list(obs_dir.glob("*.DAT.bz2"))
    else:
        # Loose files in cache root
        all_files = list(cache_dir.glob(f"HS_H09_{obs_ts}_*.DAT.bz2"))

    b07_files = sorted([f for f in all_files if "_B07_" in f.name])
    b14_files = sorted([f for f in all_files if "_B14_" in f.name])
    return b07_files, b14_files


def decode_observation(
    b07_files: list[Path], b14_files: list[Path]
) -> Optional[dict]:
    """Decode HSD files to BT arrays cropped to NSW. Returns None on failure."""
    import dask
    from satpy import Scene

    from src.config import settings

    west, south, east, north = settings.nsw_bbox
    all_files = [str(f) for f in b07_files + b14_files]

    try:
        with dask.config.set(scheduler="synchronous"):
            scn = Scene(filenames=all_files, reader="ahi_hsd")
            scn.load(["B07", "B14"])
            scn = scn.crop(ll_bbox=(west, south, east, north))

            bt7 = scn["B07"].values.astype(np.float32)
            bt14 = scn["B14"].values.astype(np.float32)

            area_def = scn["B07"].attrs["area"]
            lons, lats = area_def.get_lonlats()
            lats = lats.astype(np.float32)
            lons = lons.astype(np.float32)

            obs_time = scn["B07"].attrs.get("start_time", None)
            if obs_time is None:
                obs_time = scn["B07"].attrs.get("end_time", datetime.utcnow())

        return {
            "bt7": bt7,
            "bt14": bt14,
            "lats": lats,
            "lons": lons,
            "obs_time": obs_time,
        }
    except Exception as e:
        logger.debug("Decode failed for files %s: %s", all_files[:1], e)
        return None


# ---------------------------------------------------------------------------
# Detection storage
# ---------------------------------------------------------------------------

class DetectionRecord:
    """Lightweight record of a single fire pixel detection."""

    __slots__ = (
        "lat", "lon", "obs_time_utc", "confidence_level", "method",
        "bt7", "bt14", "daynight", "fire_confidence_cusum",
    )

    def __init__(
        self,
        lat: float,
        lon: float,
        obs_time_utc: datetime,
        confidence_level: int,
        method: str,
        bt7: float = 0.0,
        bt14: float = 0.0,
        daynight: str = "?",
        fire_confidence_cusum: float = 0.0,
    ):
        self.lat = lat
        self.lon = lon
        self.obs_time_utc = obs_time_utc
        self.confidence_level = confidence_level
        self.method = method  # "contextual", "cusum", "both"
        self.bt7 = bt7
        self.bt14 = bt14
        self.daynight = daynight
        self.fire_confidence_cusum = fire_confidence_cusum


# ---------------------------------------------------------------------------
# Core processing loop
# ---------------------------------------------------------------------------

def run_validation(
    cache_dir: Path,
    fire_targets: list[dict],
    start_date: Optional[str],
    end_date: Optional[str],
    max_obs: Optional[int],
    enable_cusum: bool,
    resume: bool,
) -> tuple[list[DetectionRecord], list[dict]]:
    """Process archived observations and collect all detections.

    Returns (all_detections, processing_stats).
    """
    him_cfg = HimawariConfig()
    cusum_cfg = CUSUMConfig()

    # Discover observations in cache
    observations = discover_cache_observations(cache_dir, start_date, end_date)
    logger.info("Found %d observations in cache (%s to %s)",
                len(observations),
                observations[0][0] if observations else "N/A",
                observations[-1][0] if observations else "N/A")

    if not observations:
        logger.error("No observations found in cache!")
        return [], []

    # Load checkpoint for resume
    processed_set: set[str] = set()
    all_detections: list[DetectionRecord] = []
    if resume and CHECKPOINT_PATH.exists():
        try:
            cp = json.loads(CHECKPOINT_PATH.read_text())
            processed_set = set(cp.get("processed_observations", []))
            logger.info("Resuming: %d observations already processed", len(processed_set))
            # Load existing detections from CSV
            det_csv = OUTPUT_DIR / "detections_raw.csv"
            if det_csv.exists():
                df = pd.read_csv(det_csv)
                for _, row in df.iterrows():
                    all_detections.append(DetectionRecord(
                        lat=row["lat"], lon=row["lon"],
                        obs_time_utc=datetime.fromisoformat(row["obs_time_utc"]),
                        confidence_level=int(row["confidence_level"]),
                        method=row["method"],
                        bt7=float(row.get("bt7", 0)),
                        bt14=float(row.get("bt14", 0)),
                        daynight=str(row.get("daynight", "?")),
                        fire_confidence_cusum=float(row.get("fire_confidence_cusum", 0)),
                    ))
                logger.info("Loaded %d existing detections from checkpoint", len(all_detections))
        except Exception as e:
            logger.warning("Failed to load checkpoint: %s — starting fresh", e)
            processed_set = set()
            all_detections = []

    # Filter out already-processed observations
    if processed_set:
        observations = [(ts, d) for ts, d in observations if ts not in processed_set]
        logger.info("%d observations remaining after resume filter", len(observations))

    if max_obs is not None:
        observations = observations[:max_obs]
        logger.info("Limited to %d observations (--max-obs)", max_obs)

    if not observations:
        logger.info("All observations already processed.")
        return all_detections, []

    # Decode first observation to establish grid
    logger.info("Establishing grid from first decodable observation...")
    grid_shape = None
    lats_grid = None
    lons_grid = None

    for obs_ts, obs_dir in observations[:10]:
        b07_files, b14_files = get_observation_files(cache_dir, obs_ts, obs_dir)
        if len(b07_files) < 2 or len(b14_files) < 2:
            continue
        data = decode_observation(b07_files, b14_files)
        if data is not None:
            grid_shape = data["bt7"].shape
            lats_grid = data["lats"]
            lons_grid = data["lons"]
            logger.info("Grid established: shape=%s (%d pixels)", grid_shape, grid_shape[0] * grid_shape[1])
            break

    if grid_shape is None:
        logger.error("Cannot decode any observation to establish grid. Aborting.")
        return all_detections, []

    # Initialize CUSUM detector
    cusum: Optional[CUSUMTemporalDetector] = None
    if enable_cusum:
        n_pixels = grid_shape[0] * grid_shape[1]
        pixel_lons = lons_grid.ravel().astype(np.float32)
        water_mask = compute_water_mask(lats_grid, lons_grid)
        industrial_mask = compute_industrial_mask(lats_grid, lons_grid)
        suppression_mask = (water_mask | industrial_mask).ravel()

        cusum = CUSUMTemporalDetector(
            n_pixels=n_pixels,
            pixel_lons=pixel_lons,
            cfg=cusum_cfg,
            suppression_mask=suppression_mask,
        )
        cusum.set_grid_shape(grid_shape[0], grid_shape[1])

        # If resuming, try to load CUSUM state
        cusum_state_path = OUTPUT_DIR / "cusum_validation_state.npz"
        if resume and cusum_state_path.exists():
            loaded = cusum.load_state(cusum_state_path)
            if loaded:
                logger.info("Loaded CUSUM state: frame %d, %.1f%% initialized",
                            cusum.frame_count, cusum.initialized_fraction * 100)

        logger.info("CUSUM detector initialized: %d pixels", n_pixels)

    # Processing loop
    n_total = len(observations)
    t_start = time.monotonic()
    n_processed = 0
    n_errors = 0
    n_detections_contextual = 0
    n_detections_cusum = 0
    stats_list: list[dict] = []
    newly_processed: list[str] = []

    for obs_idx, (obs_ts, obs_dir) in enumerate(observations):
        t_obs = time.monotonic()

        # Get files
        b07_files, b14_files = get_observation_files(cache_dir, obs_ts, obs_dir)
        if len(b07_files) < 2 or len(b14_files) < 2:
            n_errors += 1
            logger.debug("Incomplete observation %s: B07=%d, B14=%d files",
                         obs_ts, len(b07_files), len(b14_files))
            newly_processed.append(obs_ts)
            continue

        # Decode
        data = decode_observation(b07_files, b14_files)
        if data is None:
            n_errors += 1
            newly_processed.append(obs_ts)
            continue

        bt7 = data["bt7"]
        bt14 = data["bt14"]
        lats = data["lats"]
        lons = data["lons"]
        obs_time = data["obs_time"]

        # Verify grid shape
        if bt7.shape != grid_shape:
            logger.warning("Grid shape mismatch at %s: expected %s, got %s",
                           obs_ts, grid_shape, bt7.shape)
            n_errors += 1
            newly_processed.append(obs_ts)
            continue

        # Ensure obs_time is tz-aware
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        # Compute masks
        nsw_mask = compute_nsw_mask(lats, lons)
        cloud_mask = compute_cloud_mask(bt14, him_cfg.cloud_bt14_threshold_k)
        cloud_adj = compute_cloud_adjacency(cloud_mask, him_cfg.cloud_adjacency_buffer)
        valid_mask = nsw_mask & (~cloud_adj) & np.isfinite(bt7) & np.isfinite(bt14)

        # --- Contextual detection ---
        result: FireDetectionResult = detect_fires(
            bt7, bt14, lats, lons, obs_time, valid_mask, him_cfg
        )

        sza = result.sza
        is_day = sza < him_cfg.sza_day_night_deg

        # Extract contextual detections
        ctx_fire_rows, ctx_fire_cols = np.where(result.fire_mask > 0)
        ctx_positions = set()
        for i in range(len(ctx_fire_rows)):
            r, c = int(ctx_fire_rows[i]), int(ctx_fire_cols[i])
            lat_det = float(lats[r, c])
            lon_det = float(lons[r, c])
            conf_level = int(result.fire_mask[r, c])
            dn = "D" if is_day[r, c] else "N"
            ctx_positions.add((r, c))

            all_detections.append(DetectionRecord(
                lat=lat_det, lon=lon_det,
                obs_time_utc=obs_time,
                confidence_level=conf_level,
                method="contextual",
                bt7=float(bt7[r, c]),
                bt14=float(bt14[r, c]),
                daynight=dn,
            ))
            n_detections_contextual += 1

        # --- CUSUM detection ---
        cusum_fire_indices: set[int] = set()
        if cusum is not None:
            btd_flat = (bt7 - bt14).ravel()
            bt14_flat = bt14.ravel()
            clear_flat = valid_mask.ravel()
            is_day_flat = is_day.ravel()
            obs_unix = obs_time.timestamp()

            cusum_result = cusum.update(
                btd_flat, bt14_flat, clear_flat, is_day_flat, obs_unix
            )

            # Extract CUSUM detections
            cusum_candidates = cusum_result["fire_candidates"]
            cusum_indices = np.where(cusum_candidates)[0]
            fire_confidence = cusum_result["fire_confidence"]

            for idx in cusum_indices:
                r, c = divmod(int(idx), grid_shape[1])
                cusum_fire_indices.add((r, c))
                lat_det = float(lats[r, c])
                lon_det = float(lons[r, c])
                dn = "D" if is_day_flat[idx] else "N"
                conf_cusum = float(fire_confidence[idx]) if np.isfinite(fire_confidence[idx]) else 0.0

                # Check if also detected by contextual
                if (r, c) in ctx_positions:
                    # Already recorded as contextual — upgrade to "both"
                    # Find the last detection at this position and update
                    for det in reversed(all_detections):
                        if (det.lat == lat_det and det.lon == lon_det
                                and det.obs_time_utc == obs_time
                                and det.method == "contextual"):
                            det.method = "both"
                            det.fire_confidence_cusum = conf_cusum
                            break
                else:
                    all_detections.append(DetectionRecord(
                        lat=lat_det, lon=lon_det,
                        obs_time_utc=obs_time,
                        confidence_level=0,  # CUSUM-only has no contextual confidence
                        method="cusum",
                        bt7=float(bt7[r, c]),
                        bt14=float(bt14[r, c]),
                        daynight=dn,
                        fire_confidence_cusum=conf_cusum,
                    ))
                    n_detections_cusum += 1

        n_processed += 1
        newly_processed.append(obs_ts)
        obs_elapsed = time.monotonic() - t_obs

        obs_stats = {
            "obs_ts": obs_ts,
            "n_ctx": result.n_fires,
            "n_cusum": len(cusum_fire_indices) if cusum is not None else 0,
            "n_valid": int(np.sum(valid_mask)),
            "n_cloud": int(np.sum(cloud_mask & nsw_mask)),
            "elapsed_ms": round(obs_elapsed * 1000, 1),
        }
        stats_list.append(obs_stats)

        # Progress every 10 observations
        if (n_processed % 10 == 0) or (obs_idx == n_total - 1):
            elapsed = time.monotonic() - t_start
            rate = n_processed / elapsed if elapsed > 0 else 0
            remaining = (n_total - obs_idx - 1) / rate if rate > 0 else 0
            cusum_init_pct = cusum.initialized_fraction * 100 if cusum else 0
            logger.info(
                "[%d/%d] %s | ctx=%d cusum=%d | %.1f obs/min | "
                "CUSUM init=%.0f%% | ETA %.0f min | errors=%d",
                obs_idx + 1, n_total, obs_ts,
                result.n_fires,
                len(cusum_fire_indices) if cusum else 0,
                rate * 60,
                cusum_init_pct,
                remaining / 60,
                n_errors,
            )

        # Checkpoint every 50 observations
        if n_processed % 50 == 0 and n_processed > 0:
            _save_checkpoint(
                processed_set | set(newly_processed),
                all_detections,
                cusum,
            )

    # Final checkpoint
    _save_checkpoint(
        processed_set | set(newly_processed),
        all_detections,
        cusum,
    )

    total_elapsed = time.monotonic() - t_start
    logger.info("")
    logger.info("=" * 70)
    logger.info("PROCESSING COMPLETE")
    logger.info("=" * 70)
    logger.info("  Observations processed: %d", n_processed)
    logger.info("  Observations errored: %d", n_errors)
    logger.info("  Total detections: %d (contextual=%d, cusum-only=%d)",
                len(all_detections), n_detections_contextual, n_detections_cusum)
    logger.info("  Total time: %.1f min", total_elapsed / 60)
    if n_processed > 0:
        logger.info("  Avg time per observation: %.1f s", total_elapsed / n_processed)

    return all_detections, stats_list


def _save_checkpoint(
    processed_set: set[str],
    all_detections: list[DetectionRecord],
    cusum: Optional[CUSUMTemporalDetector],
):
    """Save checkpoint for resume capability."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Save processed observation list
    cp = {
        "processed_observations": sorted(processed_set),
        "n_detections": len(all_detections),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    CHECKPOINT_PATH.write_text(json.dumps(cp, indent=2))

    # Save raw detections
    det_rows = []
    for d in all_detections:
        det_rows.append({
            "lat": d.lat,
            "lon": d.lon,
            "obs_time_utc": d.obs_time_utc.isoformat(),
            "confidence_level": d.confidence_level,
            "method": d.method,
            "bt7": d.bt7,
            "bt14": d.bt14,
            "daynight": d.daynight,
            "fire_confidence_cusum": d.fire_confidence_cusum,
        })
    if det_rows:
        pd.DataFrame(det_rows).to_csv(OUTPUT_DIR / "detections_raw.csv", index=False)

    # Save CUSUM state
    if cusum is not None:
        cusum.save_state(OUTPUT_DIR / "cusum_validation_state.npz")


# ---------------------------------------------------------------------------
# Matching and metrics
# ---------------------------------------------------------------------------

def match_detections_to_firms(
    all_detections: list[DetectionRecord],
    fire_targets: list[dict],
    match_radius_km: float = MATCH_RADIUS_KM,
) -> pd.DataFrame:
    """Match detections to FIRMS fire events and compute per-event results.

    For each FIRMS event, finds the earliest detection within match_radius_km.

    Returns a DataFrame with one row per FIRMS event.
    """
    logger.info("Matching %d detections against %d FIRMS events (radius=%.1f km)...",
                len(all_detections), len(fire_targets), match_radius_km)

    # Pre-compute detection arrays for fast matching
    if not all_detections:
        det_lats = np.array([])
        det_lons = np.array([])
        det_times = np.array([])
    else:
        det_lats = np.array([d.lat for d in all_detections])
        det_lons = np.array([d.lon for d in all_detections])
        det_times = np.array([d.obs_time_utc.timestamp() for d in all_detections])

    results = []

    for fire in fire_targets:
        firms_dt_str = fire.get("firms_first_dt")
        if firms_dt_str is None:
            continue

        # Parse FIRMS detection time
        firms_dt = datetime.fromisoformat(firms_dt_str)
        if firms_dt.tzinfo is None:
            firms_dt = firms_dt.replace(tzinfo=timezone.utc)
        firms_ts = firms_dt.timestamp()

        fire_lat = fire["lat"]
        fire_lon = fire["lon"]
        fire_frp = fire.get("firms_first_frp", 0)
        fire_conf = fire.get("firms_first_conf", "?")
        fire_dn = fire.get("firms_first_dn", "?")
        fire_n_det = fire.get("n_detections", 0)
        fire_duration = fire.get("duration_hours", 0)

        # Find all detections within radius
        if len(det_lats) == 0:
            matched = False
            first_det_time = None
            first_det_method = None
            first_det_conf = None
            latency_min = None
        else:
            distances = haversine_km_vectorized(det_lats, det_lons, fire_lat, fire_lon)
            within_radius = distances <= match_radius_km

            if np.any(within_radius):
                # Among matches, find the earliest detection
                match_indices = np.where(within_radius)[0]
                match_times = det_times[match_indices]
                earliest_idx = match_indices[np.argmin(match_times)]
                earliest_det = all_detections[earliest_idx]

                matched = True
                first_det_time = earliest_det.obs_time_utc
                first_det_method = earliest_det.method
                first_det_conf = earliest_det.confidence_level
                latency_min = (first_det_time.timestamp() - firms_ts) / 60.0

                # Count detections by method
                n_ctx_matches = sum(
                    1 for i in match_indices
                    if all_detections[i].method in ("contextual", "both")
                )
                n_cusum_matches = sum(
                    1 for i in match_indices
                    if all_detections[i].method in ("cusum", "both")
                )
            else:
                matched = False
                first_det_time = None
                first_det_method = None
                first_det_conf = None
                latency_min = None
                n_ctx_matches = 0
                n_cusum_matches = 0

        results.append({
            "fire_label": fire["label"],
            "fire_lat": fire_lat,
            "fire_lon": fire_lon,
            "firms_first_dt": firms_dt.isoformat(),
            "firms_frp": fire_frp,
            "firms_conf": fire_conf,
            "firms_dn": fire_dn,
            "firms_n_detections": fire_n_det,
            "firms_duration_hours": fire_duration,
            "matched": matched,
            "our_first_dt": first_det_time.isoformat() if first_det_time else None,
            "our_first_method": first_det_method,
            "our_first_conf_level": first_det_conf,
            "latency_min": round(latency_min, 1) if latency_min is not None else None,
            "early_detection": latency_min is not None and latency_min < 0,
            "n_ctx_matches": n_ctx_matches if matched else 0,
            "n_cusum_matches": n_cusum_matches if matched else 0,
        })

    return pd.DataFrame(results)


def compute_false_alarms(
    all_detections: list[DetectionRecord],
    fire_targets: list[dict],
    match_radius_km: float = MATCH_RADIUS_KM,
    window_hours: float = FALSE_ALARM_WINDOW_HOURS,
) -> pd.DataFrame:
    """Identify detections with no FIRMS event within radius and time window.

    A detection is a false alarm if there is no FIRMS event within match_radius_km
    that has a firms_first_dt within +/- window_hours of the detection time.

    Returns DataFrame of false alarm detections.
    """
    if not all_detections or not fire_targets:
        return pd.DataFrame()

    # Build FIRMS lookup arrays
    firms_lats = []
    firms_lons = []
    firms_times = []
    for f in fire_targets:
        dt_str = f.get("firms_first_dt")
        if dt_str is None:
            continue
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        firms_lats.append(f["lat"])
        firms_lons.append(f["lon"])
        firms_times.append(dt.timestamp())

    firms_lats = np.array(firms_lats)
    firms_lons = np.array(firms_lons)
    firms_times = np.array(firms_times)
    window_s = window_hours * 3600

    false_alarms = []
    for det in all_detections:
        det_ts = det.obs_time_utc.timestamp()

        # Check distance to all FIRMS events
        distances = haversine_km_vectorized(firms_lats, firms_lons, det.lat, det.lon)
        near = distances <= match_radius_km

        if np.any(near):
            # Check if any near event is within time window
            near_times = firms_times[near]
            time_diffs = np.abs(near_times - det_ts)
            if np.any(time_diffs <= window_s):
                continue  # Matched — not a false alarm

        false_alarms.append({
            "lat": det.lat,
            "lon": det.lon,
            "obs_time_utc": det.obs_time_utc.isoformat(),
            "method": det.method,
            "confidence_level": det.confidence_level,
            "bt7": det.bt7,
            "bt14": det.bt14,
            "daynight": det.daynight,
        })

    return pd.DataFrame(false_alarms)


def compute_summary(
    results_df: pd.DataFrame,
    false_alarms_df: pd.DataFrame,
    all_detections: list[DetectionRecord],
    match_radius_km: float = MATCH_RADIUS_KM,
) -> dict:
    """Compute aggregate performance metrics."""

    n_firms_events = len(results_df)
    if n_firms_events == 0:
        return {"error": "No FIRMS events to evaluate against"}

    matched = results_df["matched"]
    n_matched = int(matched.sum())
    n_missed = n_firms_events - n_matched

    # Detection rate
    detection_rate = n_matched / n_firms_events

    # Latency distribution (only matched events)
    latencies = results_df.loc[matched, "latency_min"].dropna()

    # Early detections (negative latency = before FIRMS)
    early = results_df["early_detection"].fillna(False)
    n_early = int(early.sum())
    early_rate = n_early / n_firms_events if n_firms_events > 0 else 0

    # False alarm rate
    n_total_detections = len(all_detections)
    n_false_alarms = len(false_alarms_df)
    # Deduplicate false alarms by unique (lat, lon, time) clusters
    # Use a simpler metric: fraction of detections that are false alarms
    false_alarm_rate = n_false_alarms / n_total_detections if n_total_detections > 0 else 0

    # --- Stratification ---

    # By fire size (FRP)
    frp_bins = [0, 2, 5, 10, 25, 50, 100, 1000]
    frp_labels = ["0-2", "2-5", "5-10", "10-25", "25-50", "50-100", "100+"]
    results_df = results_df.copy()
    results_df["frp_bin"] = pd.cut(
        results_df["firms_frp"], bins=frp_bins, labels=frp_labels, right=False
    )
    frp_stats = {}
    for label in frp_labels:
        subset = results_df[results_df["frp_bin"] == label]
        if len(subset) > 0:
            frp_stats[label] = {
                "n_events": len(subset),
                "n_detected": int(subset["matched"].sum()),
                "detection_rate": round(float(subset["matched"].mean()), 3),
                "median_latency_min": round(float(subset.loc[subset["matched"], "latency_min"].median()), 1) if subset["matched"].any() else None,
            }

    # By day/night
    dn_stats = {}
    for dn in ["D", "N"]:
        subset = results_df[results_df["firms_dn"] == dn]
        if len(subset) > 0:
            dn_stats[dn] = {
                "n_events": len(subset),
                "n_detected": int(subset["matched"].sum()),
                "detection_rate": round(float(subset["matched"].mean()), 3),
            }

    # By method (who detected first)
    method_stats = {}
    if n_matched > 0:
        method_counts = results_df.loc[matched, "our_first_method"].value_counts().to_dict()
        method_stats = {k: int(v) for k, v in method_counts.items()}

    summary = {
        "n_firms_events": n_firms_events,
        "n_detected": n_matched,
        "n_missed": n_missed,
        "detection_rate": round(detection_rate, 4),
        "n_early_detections": n_early,
        "early_detection_rate": round(early_rate, 4),
        "n_total_detections": n_total_detections,
        "n_false_alarms": n_false_alarms,
        "false_alarm_rate": round(false_alarm_rate, 4),
        "latency_minutes": {
            "mean": round(float(latencies.mean()), 1) if len(latencies) > 0 else None,
            "median": round(float(latencies.median()), 1) if len(latencies) > 0 else None,
            "p10": round(float(latencies.quantile(0.10)), 1) if len(latencies) > 0 else None,
            "p25": round(float(latencies.quantile(0.25)), 1) if len(latencies) > 0 else None,
            "p75": round(float(latencies.quantile(0.75)), 1) if len(latencies) > 0 else None,
            "p90": round(float(latencies.quantile(0.90)), 1) if len(latencies) > 0 else None,
            "min": round(float(latencies.min()), 1) if len(latencies) > 0 else None,
            "max": round(float(latencies.max()), 1) if len(latencies) > 0 else None,
        },
        "by_frp": frp_stats,
        "by_day_night": dn_stats,
        "by_method_first_detected": method_stats,
        "match_radius_km": match_radius_km,
        "false_alarm_window_hours": FALSE_ALARM_WINDOW_HOURS,
    }

    return summary


def print_summary(summary: dict, results_df: pd.DataFrame):
    """Print a formatted console summary."""
    print()
    print("=" * 70)
    print("  PIPELINE VALIDATION RESULTS")
    print("=" * 70)
    print()

    n = summary["n_firms_events"]
    det = summary["n_detected"]
    miss = summary["n_missed"]
    rate = summary["detection_rate"]
    print(f"  FIRMS events evaluated:     {n}")
    print(f"  Detected:                   {det} ({rate:.1%})")
    print(f"  Missed:                     {miss}")
    print()

    early = summary["n_early_detections"]
    early_rate = summary["early_detection_rate"]
    print(f"  Early detections (before FIRMS): {early} ({early_rate:.1%})")
    print()

    lat = summary["latency_minutes"]
    if lat["median"] is not None:
        print(f"  Latency (minutes, detection - FIRMS):")
        print(f"    Median:  {lat['median']:+.1f}")
        print(f"    Mean:    {lat['mean']:+.1f}")
        print(f"    P10:     {lat['p10']:+.1f}")
        print(f"    P90:     {lat['p90']:+.1f}")
        print(f"    Range:   [{lat['min']:+.1f}, {lat['max']:+.1f}]")
        print(f"    (negative = detected BEFORE FIRMS)")
    print()

    n_det = summary["n_total_detections"]
    n_fa = summary["n_false_alarms"]
    fa_rate = summary["false_alarm_rate"]
    print(f"  Total detections (all obs):  {n_det}")
    print(f"  False alarms:               {n_fa} ({fa_rate:.1%})")
    print()

    # By FRP
    frp = summary.get("by_frp", {})
    if frp:
        print("  Detection rate by fire size (FRP, MW):")
        print(f"    {'FRP range':<12} {'Events':>8} {'Detected':>10} {'Rate':>8} {'Med. lat.':>10}")
        print(f"    {'-'*12} {'-'*8} {'-'*10} {'-'*8} {'-'*10}")
        for label, stats in frp.items():
            med = f"{stats['median_latency_min']:+.0f} min" if stats["median_latency_min"] is not None else "n/a"
            print(f"    {label:<12} {stats['n_events']:>8} {stats['n_detected']:>10} "
                  f"{stats['detection_rate']:>7.0%} {med:>10}")
        print()

    # By day/night
    dn = summary.get("by_day_night", {})
    if dn:
        print("  Detection rate by day/night:")
        for label, stats in dn.items():
            name = "Day" if label == "D" else "Night"
            print(f"    {name:<8} {stats['n_events']:>6} events, "
                  f"{stats['n_detected']:>6} detected ({stats['detection_rate']:.0%})")
        print()

    # By method
    method = summary.get("by_method_first_detected", {})
    if method:
        print("  First detection method:")
        for m, count in sorted(method.items(), key=lambda x: -x[1]):
            print(f"    {m:<15} {count}")
        print()

    print("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate Himawari fire detection pipeline against FIRMS ground truth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--start-date", type=str, default=None,
        help="Start date YYYYMMDD (default: earliest in cache)",
    )
    parser.add_argument(
        "--end-date", type=str, default=None,
        help="End date YYYYMMDD (default: latest in cache)",
    )
    parser.add_argument(
        "--max-obs", type=int, default=None,
        help="Maximum observations to process (for testing)",
    )
    parser.add_argument(
        "--no-cusum", action="store_true",
        help="Disable CUSUM detector (contextual only)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from checkpoint file",
    )
    parser.add_argument(
        "--match-radius", type=float, default=MATCH_RADIUS_KM,
        help=f"FIRMS matching radius in km (default: {MATCH_RADIUS_KM})",
    )
    parser.add_argument(
        "--cache-dir", type=str, default=str(CACHE_DIR),
        help=f"Cache directory (default: {CACHE_DIR})",
    )
    parser.add_argument(
        "--analyze-only", action="store_true",
        help="Skip processing, just analyze existing detections_raw.csv",
    )
    args = parser.parse_args()

    match_radius_km = args.match_radius

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir)

    # Load FIRMS fire targets
    logger.info("Loading FIRMS fire targets from %s", FIRE_TARGETS_PATH)
    with open(FIRE_TARGETS_PATH) as f:
        fire_targets = json.load(f)

    # Filter to events with FIRMS datetime
    fire_targets = [ft for ft in fire_targets if ft.get("firms_first_dt") is not None]
    logger.info("Loaded %d FIRMS fire events (with detection times)", len(fire_targets))

    if not args.analyze_only:
        # Run processing
        all_detections, stats_list = run_validation(
            cache_dir=cache_dir,
            fire_targets=fire_targets,
            start_date=args.start_date,
            end_date=args.end_date,
            max_obs=args.max_obs,
            enable_cusum=not args.no_cusum,
            resume=args.resume,
        )
    else:
        # Load existing detections
        det_csv = OUTPUT_DIR / "detections_raw.csv"
        if not det_csv.exists():
            logger.error("No detections_raw.csv found. Run without --analyze-only first.")
            sys.exit(1)
        df = pd.read_csv(det_csv)
        all_detections = []
        for _, row in df.iterrows():
            all_detections.append(DetectionRecord(
                lat=row["lat"], lon=row["lon"],
                obs_time_utc=datetime.fromisoformat(row["obs_time_utc"]),
                confidence_level=int(row["confidence_level"]),
                method=row["method"],
                bt7=float(row.get("bt7", 0)),
                bt14=float(row.get("bt14", 0)),
                daynight=str(row.get("daynight", "?")),
                fire_confidence_cusum=float(row.get("fire_confidence_cusum", 0)),
            ))
        logger.info("Loaded %d detections from %s", len(all_detections), det_csv)

    # Filter fire targets to those within the processed observation time range.
    # Use the cache date range (from args or discovered) rather than detection
    # times, so that even with 0 detections we only evaluate relevant FIRMS events.
    cache_obs = discover_cache_observations(
        cache_dir,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    if cache_obs:
        first_ts = cache_obs[0][0]
        last_ts = cache_obs[-1][0]
        obs_start = datetime.strptime(first_ts, "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
        obs_end = datetime.strptime(last_ts, "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
        logger.info("Observation time range (cache): %s to %s", obs_start, obs_end)

        # Only evaluate FIRMS events whose first detection falls within
        # a window that we could plausibly have observed (obs_start - 24h to obs_end + 24h)
        window = timedelta(hours=24)
        eligible_targets = []
        for ft in fire_targets:
            dt = datetime.fromisoformat(ft["firms_first_dt"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if (obs_start - window) <= dt <= (obs_end + window):
                eligible_targets.append(ft)

        logger.info("FIRMS events within observation window: %d of %d",
                     len(eligible_targets), len(fire_targets))
        fire_targets_eval = eligible_targets
    else:
        fire_targets_eval = fire_targets

    # Match detections to FIRMS events
    results_df = match_detections_to_firms(all_detections, fire_targets_eval, match_radius_km)

    # Compute false alarms
    false_alarms_df = compute_false_alarms(
        all_detections, fire_targets_eval, match_radius_km, FALSE_ALARM_WINDOW_HOURS
    )

    # Compute summary metrics
    summary = compute_summary(results_df, false_alarms_df, all_detections, match_radius_km)

    # Save outputs
    results_df.to_csv(OUTPUT_DIR / "results.csv", index=False)
    logger.info("Saved per-event results to %s", OUTPUT_DIR / "results.csv")

    if not false_alarms_df.empty:
        false_alarms_df.to_csv(OUTPUT_DIR / "false_alarms.csv", index=False)
        logger.info("Saved false alarms to %s", OUTPUT_DIR / "false_alarms.csv")

    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    logger.info("Saved summary to %s", summary_path)

    # Print console summary
    print_summary(summary, results_df)


if __name__ == "__main__":
    main()
