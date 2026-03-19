#!/usr/bin/env python3
"""Bulk download Himawari-9 AHI segments from AWS NODD S3.

Downloads B07 + B14 NSW segments (S0810, S0910) for a date range.
Uses parallel S3 downloads for speed. Resumable — skips existing files.

Usage:
    # Download last 3 weeks (for CUSUM pre-initialization)
    python scripts/bulk_download.py --start 20260226 --end 20260319

    # Download specific date range
    python scripts/bulk_download.py --start 20251126 --end 20251202

    # Download every 30 min instead of every 10 min
    python scripts/bulk_download.py --start 20260301 --end 20260319 --interval 30

    # Use more parallel workers
    python scripts/bulk_download.py --start 20260301 --end 20260319 --workers 16

    # Dry run — just count files
    python scripts/bulk_download.py --start 20260301 --end 20260319 --dry-run

Files are saved to data/himawari_cache/ organized as:
    data/himawari_cache/YYYYMMDD_HHMM/HS_H09_...DAT.bz2
"""

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "himawari_cache"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# S3 config
BUCKET = "noaa-himawari9"
PREFIX = "AHI-L1b-FLDK"
REGION = "us-east-1"
BANDS = ["B07", "B14"]
SEGMENTS = ["S0810", "S0910"]


def get_s3_client():
    return boto3.client("s3", region_name=REGION, config=Config(
        signature_version=UNSIGNED,
        max_pool_connections=50,
        retries={"max_attempts": 3, "mode": "adaptive"},
    ))


def list_observations_for_date(s3, date_str):
    """List all observation timestamps on S3 for a date (YYYYMMDD)."""
    year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
    prefix = f"{PREFIX}/{year}/{month}/{day}/"
    observations = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                folder = cp["Prefix"].rstrip("/").split("/")[-1]
                if len(folder) == 4 and folder.isdigit():
                    observations.append(f"{date_str}_{folder}")
    except Exception as e:
        log.error("Failed to list %s: %s", date_str, e)
    return sorted(observations)


def build_download_list(s3, start_date, end_date, interval_min=10):
    """Build list of (s3_key, local_path) tuples to download."""
    downloads = []
    current = start_date

    while current <= end_date:
        date_str = current.strftime("%Y%m%d")
        log.info("Listing observations for %s...", date_str)
        obs_list = list_observations_for_date(s3, date_str)

        # Sample at interval
        step = max(1, interval_min // 10)
        sampled = obs_list[::step]

        for obs_ts in sampled:
            obs_dir = CACHE_DIR / obs_ts
            date_part, hhmm = obs_ts.split("_")
            year, month, day = date_part[:4], date_part[4:6], date_part[6:8]

            for band in BANDS:
                for seg in SEGMENTS:
                    fname = f"HS_H09_{obs_ts}_{band}_FLDK_R20_{seg}.DAT.bz2"
                    s3_key = f"{PREFIX}/{year}/{month}/{day}/{hhmm}/{fname}"
                    local_path = obs_dir / fname

                    # Skip if already downloaded and non-empty
                    if local_path.exists() and local_path.stat().st_size > 0:
                        continue

                    downloads.append((s3_key, local_path))

        current += timedelta(days=1)

    return downloads


def download_one(s3, s3_key, local_path):
    """Download a single file. Returns (key, success, size, elapsed_ms)."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        t0 = time.monotonic()
        s3.download_file(BUCKET, s3_key, str(local_path))
        elapsed = (time.monotonic() - t0) * 1000
        size = local_path.stat().st_size
        return (s3_key, True, size, elapsed)
    except Exception as e:
        # Clean up partial file
        if local_path.exists():
            local_path.unlink()
        return (s3_key, False, 0, 0)


def main():
    parser = argparse.ArgumentParser(description="Bulk download Himawari-9 AHI segments")
    parser.add_argument("--start", required=True, help="Start date YYYYMMDD")
    parser.add_argument("--end", required=True, help="End date YYYYMMDD")
    parser.add_argument("--interval", type=int, default=10,
                        help="Sampling interval in minutes (default: 10)")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel download workers (default: 8)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Just count files, don't download")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y%m%d")
    end = datetime.strptime(args.end, "%Y%m%d")
    days = (end - start).days + 1

    log.info("Bulk download: %s to %s (%d days, %d-min interval, %d workers)",
             args.start, args.end, days, args.interval, args.workers)
    log.info("Cache directory: %s", CACHE_DIR)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    s3 = get_s3_client()

    # Build download list
    log.info("Building download list...")
    downloads = build_download_list(s3, start, end, args.interval)

    if not downloads:
        log.info("Nothing to download — all files already cached!")
        # Count what we have
        cached = sum(1 for _ in CACHE_DIR.rglob("*.DAT.bz2"))
        log.info("Cached files: %d", cached)
        return

    total_files = len(downloads)
    # Estimate: ~1.8MB per file average
    est_size_gb = total_files * 1.8 / 1024
    # Estimate: ~500ms per file with parallelism
    est_time_min = total_files * 0.5 / args.workers / 60

    log.info("Files to download: %d (est. %.1f GB, ~%.0f min with %d workers)",
             total_files, est_size_gb, est_time_min, args.workers)

    if args.dry_run:
        log.info("Dry run — not downloading.")
        obs_count = len(set(str(p.parent.name) for _, p in downloads))
        log.info("Observations: %d, Files per obs: %d", obs_count, total_files // max(obs_count, 1))
        return

    # Download with progress
    t_start = time.monotonic()
    completed = 0
    failed = 0
    total_bytes = 0

    # Create a fresh S3 client per worker thread (boto3 clients aren't thread-safe)
    def worker_download(item):
        s3_thread = get_s3_client()
        return download_one(s3_thread, item[0], item[1])

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(worker_download, dl): dl for dl in downloads}

        for future in as_completed(futures):
            s3_key, success, size, elapsed = future.result()
            completed += 1

            if success:
                total_bytes += size
            else:
                failed += 1
                fname = s3_key.split("/")[-1]
                log.warning("FAILED: %s", fname)

            # Progress every 50 files
            if completed % 50 == 0 or completed == total_files:
                elapsed_total = time.monotonic() - t_start
                rate = completed / elapsed_total
                remaining = (total_files - completed) / rate if rate > 0 else 0
                speed_mb = total_bytes / elapsed_total / 1024 / 1024
                log.info(
                    "[%d/%d] %.1f files/s, %.1f MB/s, %.1f GB downloaded, "
                    "ETA %.0f min, %d failed",
                    completed, total_files, rate, speed_mb,
                    total_bytes / 1024 / 1024 / 1024,
                    remaining / 60, failed,
                )

    elapsed_total = time.monotonic() - t_start
    log.info("")
    log.info("=== DONE ===")
    log.info("Downloaded: %d files (%.1f GB) in %.1f min",
             completed - failed, total_bytes / 1024 / 1024 / 1024, elapsed_total / 60)
    log.info("Failed: %d", failed)
    log.info("Speed: %.1f files/s, %.1f MB/s",
             (completed - failed) / elapsed_total,
             total_bytes / elapsed_total / 1024 / 1024)
    log.info("Cache: %s", CACHE_DIR)


if __name__ == "__main__":
    main()
