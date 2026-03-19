#!/usr/bin/env python3
"""Extract Himawari BTD time series at known fire locations from the S3 archive.

This is a standalone calibration script for empirically tuning CUSUM parameters.
It downloads Himawari AHI segments, decodes them via satpy, and extracts per-pixel
BT7/BT14/BTD time series at specific (lat, lon) calibration targets.

Usage:
    python scripts/calibration_extract.py                      # Run all targets
    python scripts/calibration_extract.py --target wollemi_fire_onset  # Single target
    python scripts/calibration_extract.py --target wollemi_fire_onset --max-obs 5  # Quick test
    python scripts/calibration_extract.py --analyze-only       # Skip extraction, just analyze
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path so we can import src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.himawari.config import HimawariConfig
from src.himawari.downloader import (
    download_segments,
    list_observations_for_date,
    list_segment_keys,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress noisy third-party logging and runtime warnings
import warnings
warnings.filterwarnings("ignore", message="invalid value encountered in log")


logging.getLogger("satpy").setLevel(logging.WARNING)
logging.getLogger("pyresample").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Calibration targets
# ---------------------------------------------------------------------------

def _load_targets() -> list[dict]:
    """Load calibration targets from JSON file, falling back to hardcoded defaults."""
    import json

    json_path = PROJECT_ROOT / "data" / "calibration" / "sample_targets.json"
    if json_path.exists():
        with open(json_path) as f:
            raw = json.load(f)
        # Normalize to the format the rest of the script expects
        targets = []
        for t in raw:
            target = {
                "label": t["label"],
                "lat": t["lat"],
                "lon": t["lon"],
                "start": t["start"],
                "end": t["end"],
                "firms_first_detection": t.get("firms_first_dt"),
                "sample_interval_min": 10 if t.get("firms_first_frp", 0) > 0 else 30,
            }
            targets.append(target)
        logger.info("Loaded %d targets from %s", len(targets), json_path)
        return targets

    logger.warning("No sample_targets.json found, using hardcoded defaults")
    return [
        {
            "label": "wollemi_fire_onset",
            "lat": -32.35, "lon": 150.35,
            "start": "2025-11-26", "end": "2025-12-02",
            "firms_first_detection": "2025-11-27T13:00:00Z",
            "sample_interval_min": 10,
        },
        {
            "label": "background_grassland",
            "lat": -33.50, "lon": 148.00,
            "start": "2025-12-01", "end": "2025-12-14",
            "firms_first_detection": None,
            "sample_interval_min": 30,
        },
    ]


CALIBRATION_TARGETS = _load_targets()

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

OUTPUT_DIR = PROJECT_ROOT / "data" / "calibration"

# ---------------------------------------------------------------------------
# Cloud mask threshold (BT14 < this means cloud)
# ---------------------------------------------------------------------------

CLOUD_BT14_THRESHOLD_K = 270.0

# ---------------------------------------------------------------------------
# Core extraction logic
# ---------------------------------------------------------------------------


def get_available_observations(
    cfg: HimawariConfig, start_date: str, end_date: str, interval_min: int = 10
) -> list[str]:
    """Query S3 for actual available observations in a date range, then subsample.

    Args:
        cfg: Himawari config (for S3 bucket).
        start_date: "YYYY-MM-DD" format.
        end_date: "YYYY-MM-DD" format.
        interval_min: Sampling interval in minutes. 10 = every obs, 30 = every 3rd.

    Returns:
        List of "YYYYMMDD_HHMM" strings for observations that actually exist on S3.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    all_obs: list[str] = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        day_obs = list_observations_for_date(cfg, date_str)
        all_obs.extend(day_obs)
        current += timedelta(days=1)

    # Subsample if interval > 10 min
    if interval_min > 10:
        step = interval_min // 10
        all_obs = all_obs[::step]

    return all_obs


def find_nearest_pixel(
    lats: np.ndarray, lons: np.ndarray, target_lat: float, target_lon: float
) -> tuple[int, int, float]:
    """Find the nearest pixel to the target lat/lon.

    Returns (row, col, distance_deg).
    """
    dist = np.sqrt((lats - target_lat) ** 2 + (lons - target_lon) ** 2)
    idx = np.nanargmin(dist)
    row, col = np.unravel_index(idx, lats.shape)
    return int(row), int(col), float(dist[row, col])


def is_daytime(obs_time: datetime, lon: float) -> bool:
    """Approximate day/night based on local solar time."""
    utc_hour = obs_time.hour + obs_time.minute / 60.0
    lst = (utc_hour + lon / 15.0) % 24.0
    return 6.0 <= lst <= 18.0


def decode_and_extract(
    cfg: HimawariConfig,
    obs_ts: str,
    targets: list[dict],
    cache_dir: Path,
) -> list[dict]:
    """Download, decode one observation, and extract pixel values for all targets.

    Returns a list of dicts (one per target) with extracted values, or empty list
    on failure.
    """
    import dask
    from satpy import Scene

    # Download segments
    seg_keys = list_segment_keys(cfg, obs_ts)

    # Check we got all required files (2 bands x 2 segments = 4 files)
    total_keys = sum(len(v) for v in seg_keys.values())
    if total_keys < 4:
        return []  # Incomplete observation, skip

    try:
        downloaded = download_segments(cfg, seg_keys, cache_dir)
    except Exception as e:
        logger.debug("Download failed for %s: %s", obs_ts, e)
        return []

    b07_files = downloaded.get("B07", [])
    b14_files = downloaded.get("B14", [])
    if not b07_files or not b14_files:
        return []

    # Decode with satpy (crop to NSW)
    west, south, east, north = 140.9, -38.0, 154.0, -28.0
    all_files = [str(f) for f in b07_files + b14_files]

    try:
        with dask.config.set(scheduler="synchronous"):
            scn = Scene(filenames=all_files, reader="ahi_hsd")
            scn.load(["B07", "B14"])
            scn = scn.crop(ll_bbox=(west, south, east, north))

            bt7 = scn["B07"].values.astype(np.float32)
            bt14 = scn["B14"].values.astype(np.float32)

            area_def = scn["B07"].attrs["area"]
            lons_arr, lats_arr = area_def.get_lonlats()
            lats_arr = lats_arr.astype(np.float32)
            lons_arr = lons_arr.astype(np.float32)

            obs_time = scn["B07"].attrs.get("start_time", None)
            if obs_time is None:
                # Parse from timestamp string
                obs_time = datetime.strptime(obs_ts, "%Y%m%d_%H%M").replace(
                    tzinfo=timezone.utc
                )
            elif obs_time.tzinfo is None:
                obs_time = obs_time.replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.debug("Decode failed for %s: %s", obs_ts, e)
        return []
    finally:
        # Clean up downloaded files to save disk space
        for f in b07_files + b14_files:
            try:
                f.unlink()
            except OSError:
                pass

    # Extract pixel values for each target
    results = []
    for target in targets:
        row, col, dist = find_nearest_pixel(
            lats_arr, lons_arr, target["lat"], target["lon"]
        )

        # Sanity check: AHI 2km pixel, so distance should be < ~0.03 deg
        if dist > 0.05:
            logger.warning(
                "Target %s: nearest pixel %.4f deg away -- grid alignment issue?",
                target["label"],
                dist,
            )

        bt7_val = float(bt7[row, col])
        bt14_val = float(bt14[row, col])
        btd_val = bt7_val - bt14_val
        cloud_flag = 1 if bt14_val < CLOUD_BT14_THRESHOLD_K else 0
        day_flag = 1 if is_daytime(obs_time, target["lon"]) else 0

        results.append(
            {
                "label": target["label"],
                "obs_time": obs_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "bt7": round(bt7_val, 2),
                "bt14": round(bt14_val, 2),
                "btd": round(btd_val, 2),
                "cloud_flag": cloud_flag,
                "is_day": day_flag,
                "pixel_row": row,
                "pixel_col": col,
                "pixel_dist_deg": round(dist, 4),
            }
        )

    return results


def load_existing_csv(label: str) -> set[str]:
    """Load previously extracted observation times from CSV to enable resumption."""
    csv_path = OUTPUT_DIR / f"{label}.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            return set(df["obs_time"].astype(str))
        except Exception:
            return set()
    return set()


def save_results(label: str, rows: list[dict]) -> Path:
    """Append extraction results to CSV, deduplicating on obs_time."""
    csv_path = OUTPUT_DIR / f"{label}.csv"

    new_df = pd.DataFrame(rows)
    if csv_path.exists():
        existing_df = pd.read_csv(csv_path)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["obs_time"], keep="last")
    else:
        combined = new_df

    combined = combined.sort_values("obs_time").reset_index(drop=True)
    combined.to_csv(csv_path, index=False)
    return csv_path


def extract_target(
    target: dict,
    cfg: HimawariConfig,
    max_obs: int | None = None,
) -> Path | None:
    """Extract full time series for one calibration target.

    Returns path to output CSV, or None on failure.
    """
    label = target["label"]
    logger.info(
        "=== Extracting: %s (%.2f, %.2f) from %s to %s ===",
        label,
        target["lat"],
        target["lon"],
        target["start"],
        target["end"],
    )

    # Query S3 for actual available observations (avoids wasting time on gaps)
    interval = target.get("sample_interval_min", 10)
    logger.info("  Querying S3 for available observations...")
    all_timestamps = get_available_observations(
        cfg, target["start"], target["end"], interval
    )
    logger.info("  Found %d observations on S3", len(all_timestamps))

    # Skip already-extracted observations
    existing_times = load_existing_csv(label)
    timestamps_to_process = []
    for ts in all_timestamps:
        # Convert YYYYMMDD_HHMM to ISO format for comparison
        dt = datetime.strptime(ts, "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
        iso_str = dt.strftime("%Y-%m-%dT%H:%M:%S")
        if iso_str not in existing_times:
            timestamps_to_process.append(ts)

    if not timestamps_to_process:
        logger.info("  All %d observations already extracted for %s", len(all_timestamps), label)
        return OUTPUT_DIR / f"{label}.csv"

    if max_obs is not None:
        timestamps_to_process = timestamps_to_process[:max_obs]

    total = len(timestamps_to_process)
    logger.info(
        "  %d observations to process (%d already done, %d total expected)",
        total,
        len(existing_times),
        len(all_timestamps),
    )

    # Estimate time
    est_seconds = total * 15  # ~15s per observation (download + decode)
    est_hours = est_seconds / 3600
    if est_hours > 0.5:
        logger.info("  Estimated time: %.1f hours", est_hours)

    # Process observations with a temp directory for downloads
    all_rows: list[dict] = []
    t_start = time.monotonic()
    success_count = 0
    fail_count = 0

    with tempfile.TemporaryDirectory(prefix="himawari_cal_") as tmpdir:
        cache_dir = Path(tmpdir)

        for i, obs_ts in enumerate(timestamps_to_process):
            t_obs = time.monotonic()

            results = decode_and_extract(cfg, obs_ts, [target], cache_dir)

            if results:
                all_rows.extend(results)
                success_count += 1
            else:
                # Record a NaN row for missing observations
                dt = datetime.strptime(obs_ts, "%Y%m%d_%H%M").replace(
                    tzinfo=timezone.utc
                )
                all_rows.append(
                    {
                        "label": label,
                        "obs_time": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                        "bt7": np.nan,
                        "bt14": np.nan,
                        "btd": np.nan,
                        "cloud_flag": -1,
                        "is_day": 1 if is_daytime(dt, target["lon"]) else 0,
                        "pixel_row": -1,
                        "pixel_col": -1,
                        "pixel_dist_deg": np.nan,
                    }
                )
                fail_count += 1

            # Progress report every 10 observations
            if (i + 1) % 10 == 0 or i == total - 1:
                elapsed = time.monotonic() - t_start
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - i - 1) / rate if rate > 0 else 0
                logger.info(
                    "  [%d/%d] %s | ok=%d fail=%d | %.1f obs/min | ETA %.0f min",
                    i + 1,
                    total,
                    obs_ts,
                    success_count,
                    fail_count,
                    rate * 60,
                    remaining / 60,
                )

            # Save intermediate results every 50 observations
            if (i + 1) % 50 == 0 and all_rows:
                save_results(label, all_rows)
                all_rows = []
                logger.info("  (intermediate save)")

    # Final save
    if all_rows:
        csv_path = save_results(label, all_rows)
    else:
        csv_path = OUTPUT_DIR / f"{label}.csv"

    elapsed = time.monotonic() - t_start
    logger.info(
        "  Done: %d ok, %d failed in %.1f min. Saved to %s",
        success_count,
        fail_count,
        elapsed / 60,
        csv_path,
    )
    return csv_path


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze_target(target: dict) -> dict | None:
    """Analyze extracted time series for one calibration target.

    Returns summary dict, or None if no data.
    """
    label = target["label"]
    csv_path = OUTPUT_DIR / f"{label}.csv"
    if not csv_path.exists():
        logger.warning("  No data file for %s", label)
        return None

    df = pd.read_csv(csv_path)
    df["obs_time"] = pd.to_datetime(df["obs_time"])

    # Filter out missing observations
    valid = df[df["btd"].notna()].copy()
    if valid.empty:
        logger.warning("  No valid observations for %s", label)
        return None

    total_obs = len(df)
    valid_obs = len(valid)
    missing_obs = total_obs - valid_obs

    # Cloud statistics
    clear = valid[valid["cloud_flag"] == 0]
    cloud_frac = 1.0 - len(clear) / len(valid) if len(valid) > 0 else 1.0

    # BTD statistics (clear-sky only)
    btd_mean = float(clear["btd"].mean()) if len(clear) > 0 else np.nan
    btd_std = float(clear["btd"].std()) if len(clear) > 0 else np.nan
    btd_min = float(clear["btd"].min()) if len(clear) > 0 else np.nan
    btd_max = float(clear["btd"].max()) if len(clear) > 0 else np.nan

    # Day/night split
    clear_day = clear[clear["is_day"] == 1]
    clear_night = clear[clear["is_day"] == 0]
    btd_day_mean = float(clear_day["btd"].mean()) if len(clear_day) > 0 else np.nan
    btd_day_std = float(clear_day["btd"].std()) if len(clear_day) > 0 else np.nan
    btd_night_mean = (
        float(clear_night["btd"].mean()) if len(clear_night) > 0 else np.nan
    )
    btd_night_std = (
        float(clear_night["btd"].std()) if len(clear_night) > 0 else np.nan
    )

    summary = {
        "label": label,
        "total_obs": total_obs,
        "valid_obs": valid_obs,
        "missing_obs": missing_obs,
        "cloud_fraction": round(cloud_frac, 3),
        "btd_mean": round(btd_mean, 2) if np.isfinite(btd_mean) else None,
        "btd_std": round(btd_std, 2) if np.isfinite(btd_std) else None,
        "btd_min": round(btd_min, 2) if np.isfinite(btd_min) else None,
        "btd_max": round(btd_max, 2) if np.isfinite(btd_max) else None,
        "btd_day_mean": round(btd_day_mean, 2) if np.isfinite(btd_day_mean) else None,
        "btd_day_std": round(btd_day_std, 2) if np.isfinite(btd_day_std) else None,
        "btd_night_mean": (
            round(btd_night_mean, 2) if np.isfinite(btd_night_mean) else None
        ),
        "btd_night_std": (
            round(btd_night_std, 2) if np.isfinite(btd_night_std) else None
        ),
    }

    print(f"\n--- {label} ---")
    print(f"  Observations: {valid_obs} valid / {total_obs} total ({missing_obs} missing)")
    print(f"  Cloud fraction: {cloud_frac:.1%}")
    print(f"  BTD (clear-sky): mean={btd_mean:.2f} K, std={btd_std:.2f} K, range=[{btd_min:.2f}, {btd_max:.2f}]")
    if np.isfinite(btd_day_mean):
        print(f"  BTD day:   mean={btd_day_mean:.2f} K, std={btd_day_std:.2f} K  (n={len(clear_day)})")
    if np.isfinite(btd_night_mean):
        print(f"  BTD night: mean={btd_night_mean:.2f} K, std={btd_night_std:.2f} K  (n={len(clear_night)})")

    # For fire targets: find early detection signal
    firms_first = target.get("firms_first_detection")
    if firms_first and np.isfinite(btd_mean) and np.isfinite(btd_std):
        firms_dt = datetime.fromisoformat(firms_first.replace("Z", "+00:00"))

        # Look for BTD exceedances in clear-sky observations
        for sigma_mult in [2.0, 3.0, 4.0, 5.0]:
            threshold = btd_mean + sigma_mult * btd_std
            exceedances = clear[clear["btd"] > threshold]
            if not exceedances.empty:
                first_exc = exceedances.iloc[0]
                first_exc_time = first_exc["obs_time"]
                if isinstance(first_exc_time, str):
                    first_exc_time = pd.to_datetime(first_exc_time)
                if first_exc_time.tzinfo is None:
                    first_exc_time = first_exc_time.tz_localize("UTC")

                delta = firms_dt - first_exc_time
                hours_before = delta.total_seconds() / 3600

                if hours_before > 0:
                    print(
                        f"  ** BTD exceeded {sigma_mult:.0f}sigma ({threshold:.1f} K) "
                        f"at {first_exc_time} -- {hours_before:.1f}h BEFORE FIRMS **"
                    )
                else:
                    print(
                        f"  BTD exceeded {sigma_mult:.0f}sigma ({threshold:.1f} K) "
                        f"at {first_exc_time} -- {abs(hours_before):.1f}h AFTER FIRMS"
                    )
            else:
                print(f"  BTD never exceeded {sigma_mult:.0f}sigma ({threshold:.1f} K) in clear-sky data")

        # Use the background target's stats for a better comparison
        # (compute background stats separately if available)
        _analyze_against_background(target, clear, firms_dt)

    return summary


def _analyze_against_background(
    target: dict, clear_fire_df: pd.DataFrame, firms_dt: datetime
) -> None:
    """Compare fire target BTD against a background reference's statistics.

    Looks for a matching background target (same lat/lon, "background" in label)
    and uses its statistics as the baseline for anomaly detection.
    """
    # Find matching background target
    bg_target = None
    for t in CALIBRATION_TARGETS:
        if (
            t["label"] != target["label"]
            and abs(t["lat"] - target["lat"]) < 0.01
            and abs(t["lon"] - target["lon"]) < 0.01
            and t.get("firms_first_detection") is None
        ):
            bg_target = t
            break

    if bg_target is None:
        return

    bg_csv = OUTPUT_DIR / f"{bg_target['label']}.csv"
    if not bg_csv.exists():
        return

    bg_df = pd.read_csv(bg_csv)
    bg_clear = bg_df[(bg_df["btd"].notna()) & (bg_df["cloud_flag"] == 0)]
    if bg_clear.empty:
        return

    bg_mean = float(bg_clear["btd"].mean())
    bg_std = float(bg_clear["btd"].std())
    if bg_std < 0.01:
        return

    print(f"\n  Comparison against background ({bg_target['label']}):")
    print(f"    Background BTD: mean={bg_mean:.2f} K, std={bg_std:.2f} K")

    for sigma_mult in [2.0, 3.0, 4.0, 5.0]:
        threshold = bg_mean + sigma_mult * bg_std
        exceedances = clear_fire_df[clear_fire_df["btd"] > threshold]
        if not exceedances.empty:
            first_exc = exceedances.iloc[0]
            first_exc_time = first_exc["obs_time"]
            if isinstance(first_exc_time, str):
                first_exc_time = pd.to_datetime(first_exc_time)
            if first_exc_time.tzinfo is None:
                first_exc_time = first_exc_time.tz_localize("UTC")

            delta = firms_dt - first_exc_time
            hours_before = delta.total_seconds() / 3600

            if hours_before > 0:
                print(
                    f"    ** BTD exceeded bg+{sigma_mult:.0f}sigma ({threshold:.1f} K) "
                    f"at {first_exc_time} -- {hours_before:.1f}h BEFORE FIRMS **"
                )
            else:
                print(
                    f"    BTD exceeded bg+{sigma_mult:.0f}sigma ({threshold:.1f} K) "
                    f"at {first_exc_time} -- {abs(hours_before):.1f}h AFTER FIRMS"
                )


def run_cusum_on_timeseries(target: dict) -> Path | None:
    """Run single-pixel CUSUM on the extracted time series and save enriched CSV.

    This produces the "cusum-enriched" version of the CSV with columns:
    obs_time, bt7, bt14, btd, btd_predicted, residual, z_score, cusum_S, cloud_flag, is_day

    Returns path to enriched CSV, or None if insufficient data.
    """
    from src.himawari.config import CUSUMConfig

    label = target["label"]
    csv_path = OUTPUT_DIR / f"{label}.csv"
    if not csv_path.exists():
        return None

    df = pd.read_csv(csv_path)
    df["obs_time"] = pd.to_datetime(df["obs_time"])

    if len(df) < 10:
        logger.info("  Too few observations for CUSUM on %s", label)
        return None

    cfg = CUSUMConfig()
    lon = target["lon"]

    # Single-pixel Kalman + CUSUM state
    x = np.zeros(5, dtype=np.float64)  # [T_mean, a1, b1, a2, b2]
    P = np.diag(cfg.initial_variance).astype(np.float64)
    Q = np.diag([s**2 for s in cfg.process_noise_std]).astype(np.float64)
    S_cusum = 0.0
    n_obs_count = 0

    results = []

    for _, row in df.iterrows():
        obs_time = row["obs_time"]
        btd = row["btd"]
        cloud_flag = row["cloud_flag"]
        is_day = row["is_day"]

        # Handle missing / cloudy data
        if pd.isna(btd) or cloud_flag != 0:
            results.append(
                {
                    "obs_time": obs_time,
                    "bt7": row["bt7"],
                    "bt14": row["bt14"],
                    "btd": btd,
                    "btd_predicted": np.nan,
                    "residual": np.nan,
                    "z_score": np.nan,
                    "cusum_S": S_cusum,
                    "cloud_flag": cloud_flag,
                    "is_day": is_day,
                }
            )
            continue

        # Compute local solar time
        if isinstance(obs_time, str):
            obs_dt = datetime.fromisoformat(obs_time)
        else:
            obs_dt = obs_time.to_pydatetime()
        utc_hour = obs_dt.hour + obs_dt.minute / 60.0
        lst = (utc_hour + lon / 15.0) % 24.0

        # Observation vector H
        omega = 2.0 * np.pi / 24.0
        wt = omega * lst
        H = np.array([1.0, np.cos(wt), np.sin(wt), np.cos(2 * wt), np.sin(2 * wt)])

        # Prediction
        P_pred = P + Q
        y_pred = H @ x
        residual = btd - y_pred

        # Innovation variance
        R = cfg.R_day if is_day else cfg.R_night
        S_innov = H @ P_pred @ H.T + R
        S_innov = max(S_innov, 1e-6)
        sigma_pred = np.sqrt(S_innov)
        z = residual / sigma_pred

        # CUSUM update (only after initialization period)
        if n_obs_count >= cfg.min_init_observations:
            S_cusum = max(0.0, S_cusum + z - cfg.k_ref)
        else:
            S_cusum = 0.0

        results.append(
            {
                "obs_time": obs_time,
                "bt7": row["bt7"],
                "bt14": row["bt14"],
                "btd": btd,
                "btd_predicted": round(float(y_pred), 3),
                "residual": round(float(residual), 3),
                "z_score": round(float(z), 3),
                "cusum_S": round(float(S_cusum), 3),
                "cloud_flag": cloud_flag,
                "is_day": is_day,
            }
        )

        # Kalman update (skip if z > fire_gate_sigma to avoid contamination)
        if abs(z) < cfg.fire_gate_sigma:
            K = P_pred @ H.T / S_innov
            x = x + K * residual
            KH = np.outer(K, H)
            P = (np.eye(5) - KH) @ P_pred
            n_obs_count += 1
        else:
            P = P_pred  # Propagate uncertainty but don't update state

    enriched_df = pd.DataFrame(results)
    out_path = OUTPUT_DIR / f"{label}_cusum.csv"
    enriched_df.to_csv(out_path, index=False)

    # Print CUSUM summary
    valid_z = enriched_df["z_score"].dropna()
    max_cusum = enriched_df["cusum_S"].max()
    print(f"\n  CUSUM analysis for {label}:")
    print(f"    Kalman initialized after {cfg.min_init_observations} clear obs")
    print(f"    z-score: mean={valid_z.mean():.2f}, std={valid_z.std():.2f}, max={valid_z.max():.2f}")
    print(f"    Max CUSUM S: {max_cusum:.1f} (threshold: {cfg.h_threshold})")

    # Check if CUSUM would have fired
    triggered = enriched_df[enriched_df["cusum_S"] >= cfg.h_threshold]
    if not triggered.empty:
        first_trigger = triggered.iloc[0]["obs_time"]
        print(f"    CUSUM TRIGGERED at {first_trigger}")

        firms_first = target.get("firms_first_detection")
        if firms_first:
            firms_dt = datetime.fromisoformat(firms_first.replace("Z", "+00:00"))
            if isinstance(first_trigger, str):
                first_trigger = pd.to_datetime(first_trigger)
            if first_trigger.tzinfo is None:
                first_trigger = first_trigger.tz_localize("UTC")
            delta = firms_dt - first_trigger
            hours = delta.total_seconds() / 3600
            if hours > 0:
                print(f"    ** CUSUM detection {hours:.1f}h BEFORE FIRMS **")
            else:
                print(f"    CUSUM detection {abs(hours):.1f}h AFTER FIRMS")
    else:
        print(f"    CUSUM did NOT trigger (max S={max_cusum:.1f} < threshold {cfg.h_threshold})")

    logger.info("  CUSUM-enriched CSV saved to %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Extract Himawari BTD time series at calibration targets"
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Extract only this target label (default: all)",
    )
    parser.add_argument(
        "--max-obs",
        type=int,
        default=None,
        help="Maximum observations to process per target (for testing)",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip extraction, only run analysis on existing CSVs",
    )
    parser.add_argument(
        "--skip-cusum",
        action="store_true",
        help="Skip CUSUM analysis after extraction",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Filter targets
    if args.target:
        targets = [t for t in CALIBRATION_TARGETS if t["label"] == args.target]
        if not targets:
            available = [t["label"] for t in CALIBRATION_TARGETS]
            print(f"Unknown target '{args.target}'. Available: {available}")
            sys.exit(1)
    else:
        targets = CALIBRATION_TARGETS

    cfg = HimawariConfig()

    # Extraction phase
    if not args.analyze_only:
        for target in targets:
            try:
                extract_target(target, cfg, max_obs=args.max_obs)
            except KeyboardInterrupt:
                logger.info("Interrupted -- partial results saved.")
                break
            except Exception:
                logger.exception("Failed to extract %s", target["label"])

    # Analysis phase
    print("\n" + "=" * 70)
    print("CALIBRATION ANALYSIS")
    print("=" * 70)

    summaries = []
    for target in targets:
        summary = analyze_target(target)
        if summary:
            summaries.append(summary)

    # CUSUM analysis
    if not args.skip_cusum:
        print("\n" + "=" * 70)
        print("CUSUM MODEL ANALYSIS")
        print("=" * 70)

        for target in targets:
            try:
                run_cusum_on_timeseries(target)
            except Exception:
                logger.exception("CUSUM analysis failed for %s", target["label"])

    # Save summary table
    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_path = OUTPUT_DIR / "summary.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
