#!/usr/bin/env python3
"""Pre-initialize the CUSUM Kalman filter by processing archived Himawari observations.

Designed to run incrementally as a daily cron job: each run loads existing CUSUM
state from disk, processes only NEW observations since the last run, and saves
the updated state. Start 2-4 weeks before competition and it builds up the
Kalman filter day by day. If a day fails, the next day catches up automatically.

The output state file (data/cusum_state.npz) is loaded automatically by the
live detection pipeline on startup via CUSUMTemporalDetector.load_state().

Modes:
  --daily            Process yesterday's data only (for cron)
  --start-date/--end-date  Process a specific date range (batch or catch-up)
  (neither)          Auto catch-up: process all days since last run through yesterday

Processing time:
  ~144 observations/day x ~10s each = ~24 min per day of data

Usage:
    # Daily cron (process yesterday's data)
    python scripts/preinit_cusum.py --daily

    # Catch up all missing days since last run through yesterday
    python scripts/preinit_cusum.py

    # Batch: process a specific date range
    python scripts/preinit_cusum.py --start-date 20260312 --end-date 20260408

    # Quick test (3 observations)
    python scripts/preinit_cusum.py --start-date 20260319 --end-date 20260319 --max-obs 3

    # Faster with 30-min sampling
    python scripts/preinit_cusum.py --start-date 20260312 --end-date 20260408 --sample-interval 30

Cron example (run daily at 02:00 AEST = 15:00 UTC previous day):
    0 15 * * * cd /app && python scripts/preinit_cusum.py --daily >> logs/preinit.log 2>&1
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

import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.himawari.config import CUSUMConfig, HimawariConfig
from src.himawari.cusum import CUSUMTemporalDetector
from src.himawari.downloader import (
    list_observations_for_date,
    list_segment_keys,
)
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

# Default paths
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "cusum_state.npz"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "himawari_cache"
METADATA_FILE_SUFFIX = ".meta.json"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-initialize CUSUM Kalman filter from archived Himawari data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Daily cron job (process yesterday)
  python scripts/preinit_cusum.py --daily

  # Catch up all days since last run through yesterday
  python scripts/preinit_cusum.py

  # Batch: specific date range
  python scripts/preinit_cusum.py --start-date 20260312 --end-date 20260408

  # Quick 3-observation test
  python scripts/preinit_cusum.py --start-date 20260319 --end-date 20260319 --max-obs 3

Cron (02:00 AEST daily):
  0 15 * * * cd /app && python scripts/preinit_cusum.py --daily
""",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Process yesterday's data only (designed for cron)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date in YYYYMMDD format (batch mode)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date in YYYYMMDD format (batch mode)",
    )
    parser.add_argument(
        "--sample-interval",
        type=int,
        default=10,
        help="Sampling interval in minutes (default: 10 = every obs; 30 = every 3rd)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Output state file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=str(DEFAULT_CACHE_DIR),
        help=f"Cache directory for downloaded HSD files (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--max-obs",
        type=int,
        default=None,
        help="Maximum total observations to process (for testing)",
    )
    parser.add_argument(
        "--cloud-threshold",
        type=float,
        default=None,
        help="BT14 cloud threshold in K (default: from HimawariConfig)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def date_range(start_str: str, end_str: str) -> list[str]:
    """Generate list of YYYYMMDD date strings from start to end inclusive."""
    start = datetime.strptime(start_str, "%Y%m%d")
    end = datetime.strptime(end_str, "%Y%m%d")
    if start > end:
        return []
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return dates


def download_segments_cached(
    cfg: HimawariConfig,
    segment_keys: dict[str, list[str]],
    cache_dir: Path,
) -> dict[str, list[Path]]:
    """Download HSD segments with file-level caching.

    Files already present in cache_dir (non-empty) are reused without
    re-downloading. Returns {"B07": [path1, path2], "B14": [path3, path4]}.
    """
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    s3 = boto3.client("s3", region_name=cfg.region, config=Config(signature_version=UNSIGNED))

    all_keys = [(band, key) for band, keys in segment_keys.items() for key in keys]
    result: dict[str, list[Path]] = {b: [] for b in cfg.bands}

    for band, key in all_keys:
        filename = key.split("/")[-1]
        local_path = cache_dir / filename
        if local_path.exists() and local_path.stat().st_size > 0:
            result[band].append(local_path)
        else:
            try:
                s3.download_file(cfg.bucket, key, str(local_path))
                result[band].append(local_path)
            except Exception as e:
                if local_path.exists():
                    local_path.unlink()
                raise

    return result


def decode_observation(
    b07_files: list[Path], b14_files: list[Path]
) -> dict | None:
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
        logger.debug("Decode failed: %s", e)
        return None


def save_metadata(
    state_path: Path,
    last_obs_ts: str,
    frame_count: int,
    dates_processed: list[str],
    grid_shape: tuple[int, int] | None = None,
):
    """Save processing metadata alongside the state file for resume/catch-up."""
    meta_path = Path(str(state_path) + METADATA_FILE_SUFFIX)
    meta = {
        "last_obs_timestamp": last_obs_ts,
        "frame_count": frame_count,
        "dates_processed": sorted(set(dates_processed)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if grid_shape is not None:
        meta["grid_shape"] = list(grid_shape)
    meta_path.write_text(json.dumps(meta, indent=2))


def load_metadata(state_path: Path) -> dict | None:
    """Load processing metadata. Returns None if not found or corrupt."""
    meta_path = Path(str(state_path) + METADATA_FILE_SUFFIX)
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text())
    except Exception:
        return None


def resolve_dates_to_process(args: argparse.Namespace, meta: dict | None) -> list[str]:
    """Determine which dates to process based on mode and existing metadata.

    Returns a sorted list of YYYYMMDD date strings.
    """
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")

    if args.daily:
        # --daily: just yesterday
        return [yesterday]

    if args.start_date and args.end_date:
        # Explicit date range (batch mode)
        all_dates = date_range(args.start_date, args.end_date)
        # Skip dates already processed (idempotent)
        if meta:
            already_done = set(meta.get("dates_processed", []))
            new_dates = [d for d in all_dates if d not in already_done]
            if len(new_dates) < len(all_dates):
                logger.info(
                    "Skipping %d already-processed dates (%d remaining)",
                    len(all_dates) - len(new_dates), len(new_dates),
                )
            return new_dates
        return all_dates

    # Auto catch-up mode: process from day after last-processed through yesterday
    if meta:
        last_obs = meta.get("last_obs_timestamp", "")
        already_done = set(meta.get("dates_processed", []))
        if last_obs:
            last_date = last_obs.split("_")[0]
            # Start from day after the last processed date
            start_dt = datetime.strptime(last_date, "%Y%m%d") + timedelta(days=1)
            start_str = start_dt.strftime("%Y%m%d")
            candidate_dates = date_range(start_str, yesterday)
            # Also include any dates in the range that were somehow missed
            new_dates = [d for d in candidate_dates if d not in already_done]
            if new_dates:
                return new_dates
            logger.info("All dates up to yesterday (%s) already processed.", yesterday)
            return []

    # No metadata at all -- can't auto-detect start date
    logger.error(
        "No existing state metadata found. For first run, specify --start-date and --end-date, "
        "or use --daily to start from yesterday."
    )
    sys.exit(1)


def establish_grid(
    him_cfg: HimawariConfig,
    dates: list[str],
    cache_dir: Path,
    sample_interval: int,
) -> tuple[tuple[int, int], np.ndarray, np.ndarray] | None:
    """Download and decode one observation to get the grid shape and coordinates.

    Tries observations from the first date in the list. Returns
    (grid_shape, lats, lons) or None if nothing decodable.
    """
    for date_str in dates:
        day_obs = list_observations_for_date(him_cfg, date_str)
        for obs_ts in day_obs[:5]:  # Try first 5 observations only
            seg_keys = list_segment_keys(him_cfg, obs_ts)
            n_keys = sum(len(v) for v in seg_keys.values())
            if n_keys < len(him_cfg.bands) * len(him_cfg.nsw_segments):
                continue
            try:
                local_files = download_segments_cached(him_cfg, seg_keys, cache_dir)
            except Exception:
                continue
            data = decode_observation(local_files["B07"], local_files["B14"])
            if data is not None:
                shape = data["bt7"].shape
                logger.info(
                    "Grid established from %s: shape=%s (%d pixels)",
                    obs_ts, shape, shape[0] * shape[1],
                )
                return shape, data["lats"], data["lons"]
    return None


def process_day(
    date_str: str,
    him_cfg: HimawariConfig,
    cusum: CUSUMTemporalDetector,
    lons_grid: np.ndarray,
    grid_shape: tuple[int, int],
    cache_dir: Path,
    cloud_threshold: float,
    sample_interval: int,
    max_obs: int | None,
    obs_budget_remaining: int | None,
) -> dict:
    """Process all observations for a single day and update CUSUM state.

    Args:
        obs_budget_remaining: If not None, stop after this many obs total.

    Returns dict with stats: processed, errors, pct_initialized.
    """
    day_obs = list_observations_for_date(him_cfg, date_str)

    # Subsample by interval
    if sample_interval > 10:
        step = max(1, sample_interval // 10)
        day_obs = day_obs[::step]

    # Apply max-obs cap
    if max_obs is not None:
        day_obs = day_obs[:max_obs]
    if obs_budget_remaining is not None:
        day_obs = day_obs[:obs_budget_remaining]

    if not day_obs:
        logger.info("  %s: no observations available", date_str)
        return {"date": date_str, "available": 0, "processed": 0, "errors": 0}

    processed = 0
    errors = 0
    t_day = time.monotonic()

    for obs_idx, obs_ts in enumerate(day_obs):
        # List and validate segment keys
        try:
            seg_keys = list_segment_keys(him_cfg, obs_ts)
        except Exception:
            errors += 1
            continue

        n_keys = sum(len(v) for v in seg_keys.values())
        expected_keys = len(him_cfg.bands) * len(him_cfg.nsw_segments)
        if n_keys < expected_keys:
            errors += 1
            continue

        # Download (with caching)
        try:
            local_files = download_segments_cached(him_cfg, seg_keys, cache_dir)
        except Exception:
            errors += 1
            continue

        # Decode
        data = decode_observation(local_files["B07"], local_files["B14"])
        if data is None:
            errors += 1
            continue

        bt7 = data["bt7"]
        bt14 = data["bt14"]
        obs_time = data["obs_time"]

        # Verify grid shape consistency
        if bt7.shape != grid_shape:
            logger.warning(
                "  Grid shape mismatch at %s: expected %s, got %s",
                obs_ts, grid_shape, bt7.shape,
            )
            errors += 1
            continue

        # Compute masks
        nsw_mask = compute_nsw_mask(data["lats"], data["lons"])
        cloud_mask = compute_cloud_mask(bt14, cloud_threshold)
        cloud_adj = compute_cloud_adjacency(cloud_mask, him_cfg.cloud_adjacency_buffer)
        valid_mask = nsw_mask & (~cloud_adj) & np.isfinite(bt7) & np.isfinite(bt14)

        # Build CUSUM input arrays
        btd_flat = (bt7 - bt14).ravel()
        bt14_flat = bt14.ravel()
        clear_flat = valid_mask.ravel()

        # Day/night via local solar time approximation
        if obs_time.tzinfo is None:
            obs_time_utc = obs_time.replace(tzinfo=timezone.utc)
        else:
            obs_time_utc = obs_time
        obs_unix = obs_time_utc.timestamp()
        utc_hour = (obs_unix % 86400) / 3600.0
        lst_hours = (utc_hour + lons_grid.ravel() / 15.0) % 24.0
        is_day_flat = (lst_hours >= 6.0) & (lst_hours <= 18.0)

        # Feed observation to CUSUM (trains the Kalman filter)
        cusum.update(btd_flat, bt14_flat, clear_flat, is_day_flat, obs_unix)
        processed += 1

        # Periodic progress within large days
        if processed % 50 == 0:
            logger.info(
                "    %s [%d/%d]: %.1f%% initialized",
                obs_ts, processed, len(day_obs), cusum.initialized_fraction * 100,
            )

    day_elapsed = time.monotonic() - t_day
    pct = cusum.initialized_fraction * 100

    logger.info(
        "  Processed %s: %d/%d observations, %d errors, %.1f%% initialized, %.0fs",
        date_str, processed, len(day_obs), errors, pct, day_elapsed,
    )

    return {
        "date": date_str,
        "available": len(day_obs),
        "processed": processed,
        "errors": errors,
        "pct_initialized": round(pct, 1),
        "elapsed_s": round(day_elapsed, 1),
        "last_obs_ts": day_obs[-1] if day_obs else None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    output_path = Path(args.output)
    cache_dir = Path(args.cache_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    him_cfg = HimawariConfig()
    cusum_cfg = CUSUMConfig()
    cloud_threshold = args.cloud_threshold or him_cfg.cloud_bt14_threshold_k

    # Load existing metadata (if any)
    meta = load_metadata(output_path)

    # Determine which dates to process
    dates_to_process = resolve_dates_to_process(args, meta)

    if not dates_to_process:
        logger.info("Nothing to process. State is up to date.")
        return

    logger.info("CUSUM Pre-Initialization")
    logger.info("  Mode: %s", "daily" if args.daily else ("batch" if args.start_date else "catch-up"))
    logger.info("  Dates to process: %d (%s to %s)", len(dates_to_process), dates_to_process[0], dates_to_process[-1])
    logger.info("  Sample interval: %d min", args.sample_interval)
    logger.info("  Output: %s", output_path)
    logger.info("  Cache dir: %s", cache_dir)
    if args.max_obs:
        logger.info("  Max observations: %d (testing mode)", args.max_obs)

    # -----------------------------------------------------------------------
    # Establish grid shape (from metadata or by decoding one observation)
    # -----------------------------------------------------------------------
    grid_shape = None
    lats_grid = None
    lons_grid = None

    if meta and "grid_shape" in meta:
        # Try to get grid from a quick decode (needed for lat/lon arrays)
        saved_shape = tuple(meta["grid_shape"])
        logger.info("Saved grid shape: %s — verifying with live decode...", saved_shape)
        result = establish_grid(him_cfg, dates_to_process, cache_dir, args.sample_interval)
        if result is not None:
            grid_shape, lats_grid, lons_grid = result
            if grid_shape != saved_shape:
                logger.warning(
                    "Grid shape changed from %s to %s! Starting fresh state.",
                    saved_shape, grid_shape,
                )
                meta = None  # Force fresh start
        else:
            logger.error("Cannot decode any observation to verify grid. Aborting.")
            sys.exit(1)
    else:
        # First run or no grid saved
        result = establish_grid(him_cfg, dates_to_process, cache_dir, args.sample_interval)
        if result is None:
            logger.error("Cannot decode any observation to establish grid shape. Aborting.")
            sys.exit(1)
        grid_shape, lats_grid, lons_grid = result

    n_pixels = grid_shape[0] * grid_shape[1]

    # -----------------------------------------------------------------------
    # Create CUSUM detector and load existing state
    # -----------------------------------------------------------------------
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

    # Load existing state (always attempt -- incremental design)
    loaded = cusum.load_state(output_path)
    if loaded:
        logger.info(
            "Loaded existing state: frame %d, %.1f%% initialized",
            cusum.frame_count, cusum.initialized_fraction * 100,
        )
    else:
        logger.info("Starting with fresh CUSUM state.")

    dates_already_done = list(meta.get("dates_processed", [])) if meta else []

    # -----------------------------------------------------------------------
    # Process each day
    # -----------------------------------------------------------------------
    t_start = time.monotonic()
    total_processed = 0
    total_errors = 0
    last_obs_ts = meta.get("last_obs_timestamp", "") if meta else ""
    obs_budget = args.max_obs

    logger.info("=" * 70)

    for day_idx, date_str in enumerate(dates_to_process):
        budget_remaining = None
        if obs_budget is not None:
            budget_remaining = obs_budget - total_processed
            if budget_remaining <= 0:
                logger.info("Reached --max-obs limit (%d). Stopping.", args.max_obs)
                break

        stats = process_day(
            date_str=date_str,
            him_cfg=him_cfg,
            cusum=cusum,
            lons_grid=lons_grid,
            grid_shape=grid_shape,
            cache_dir=cache_dir,
            cloud_threshold=cloud_threshold,
            sample_interval=args.sample_interval,
            max_obs=None,  # per-day max not needed; use budget_remaining
            obs_budget_remaining=budget_remaining,
        )

        total_processed += stats["processed"]
        total_errors += stats["errors"]

        if stats.get("last_obs_ts"):
            last_obs_ts = stats["last_obs_ts"]

        if stats["processed"] > 0:
            dates_already_done.append(date_str)

        # Save state after each day (incremental, crash-safe)
        if stats["processed"] > 0:
            cusum.save_state(output_path)
            save_metadata(
                output_path, last_obs_ts, cusum.frame_count,
                dates_already_done, grid_shape,
            )

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    total_elapsed = time.monotonic() - t_start
    n_init = int(np.sum(cusum.n_obs >= cusum_cfg.min_init_observations))

    logger.info("=" * 70)
    logger.info("CUSUM PRE-INITIALIZATION COMPLETE")
    logger.info("=" * 70)
    logger.info("  Days processed: %d", len(dates_to_process))
    logger.info("  Frames processed: %d", total_processed)
    logger.info("  Frames errored: %d", total_errors)
    logger.info("  Total pixels: %d", n_pixels)
    logger.info(
        "  Pixels initialized (>=%d obs): %d (%.1f%%)",
        cusum_cfg.min_init_observations, n_init, cusum.initialized_fraction * 100,
    )
    logger.info(
        "  Pixels suppressed (water+industrial): %d (%.1f%%)",
        int(np.sum(suppression_mask)), 100 * np.sum(suppression_mask) / n_pixels,
    )
    logger.info("  Median clear-sky obs per pixel: %d", int(np.median(cusum.n_obs)))
    logger.info("  Total time: %.1f min (%.1f hours)", total_elapsed / 60, total_elapsed / 3600)
    if total_processed > 0:
        logger.info("  Avg time per frame: %.1f s", total_elapsed / total_processed)
    if output_path.exists():
        logger.info("  State saved to: %s", output_path)
        logger.info("  State file size: %.1f MB", output_path.stat().st_size / 1e6)


if __name__ == "__main__":
    main()
