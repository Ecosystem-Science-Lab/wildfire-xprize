"""S3 listing and download for Himawari-9 AHI HSD segments."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

from .config import HimawariConfig

logger = logging.getLogger(__name__)

# Track processed observations to avoid reprocessing
_processed: set[str] = set()

# Compiled regex for HSD filenames
_HSD_RE = re.compile(
    r"HS_H09_(\d{8})_(\d{4})_B(\d{2})_FLDK_R20_S(\d{4})\.DAT\.bz2$"
)


def _s3_client(cfg: HimawariConfig):
    return boto3.client("s3", region_name=cfg.region, config=Config(signature_version=UNSIGNED))


def list_recent_observations(cfg: HimawariConfig, lookback_min: int = 30) -> list[str]:
    """List observation timestamps from S3 within the lookback window.

    S3 structure: AHI-L1b-FLDK/YYYY/MM/DD/HHMM/ (no intermediate hour folder)

    Returns list of "YYYYMMDD_HHMM" strings, sorted oldest-first.
    """
    s3 = _s3_client(cfg)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=lookback_min)

    # Check today and yesterday (for observations near midnight)
    days_to_check = set()
    days_to_check.add(now.strftime("%Y/%m/%d"))
    prev_day = now - timedelta(days=1)
    days_to_check.add(prev_day.strftime("%Y/%m/%d"))

    observations: set[str] = set()

    for day_path in sorted(days_to_check):
        prefix = f"{cfg.prefix}/{day_path}/"
        date_part = day_path.replace("/", "")  # "20260319"
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=cfg.bucket, Prefix=prefix, Delimiter="/"):
                for cp in page.get("CommonPrefixes", []):
                    # e.g., "AHI-L1b-FLDK/2026/03/19/1600/"
                    obs_folder = cp["Prefix"].rstrip("/").split("/")[-1]  # "1600"
                    if len(obs_folder) == 4 and obs_folder.isdigit():
                        obs_ts = f"{date_part}_{obs_folder}"
                        obs_dt = datetime.strptime(obs_ts, "%Y%m%d_%H%M").replace(tzinfo=timezone.utc)
                        if obs_dt >= cutoff:
                            observations.add(obs_ts)
        except Exception:
            logger.exception("Failed to list S3 prefix: %s", prefix)

    return sorted(observations)


def list_observations_for_date(cfg: HimawariConfig, date_str: str) -> list[str]:
    """List all observation timestamps available on S3 for a given date.

    Args:
        cfg: Himawari configuration.
        date_str: Date in "YYYYMMDD" format.

    Returns:
        List of "YYYYMMDD_HHMM" strings, sorted oldest-first.
    """
    s3 = _s3_client(cfg)
    year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
    prefix = f"{cfg.prefix}/{year}/{month}/{day}/"

    observations: list[str] = []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=cfg.bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                obs_folder = cp["Prefix"].rstrip("/").split("/")[-1]
                if len(obs_folder) == 4 and obs_folder.isdigit():
                    observations.append(f"{date_str}_{obs_folder}")
    except Exception:
        logger.exception("Failed to list S3 observations for date: %s", date_str)

    return sorted(observations)


def list_segment_keys(cfg: HimawariConfig, obs_timestamp: str) -> dict[str, list[str]]:
    """Find S3 keys for NSW segments of required bands for a given observation.

    Args:
        obs_timestamp: "YYYYMMDD_HHMM" format

    Returns:
        {"B07": [key1, key2], "B14": [key3, key4]}
    """
    s3 = _s3_client(cfg)
    date_str, hhmm = obs_timestamp.split("_")
    # S3 structure: AHI-L1b-FLDK/YYYY/MM/DD/HHMM/
    year, month, day = date_str[:4], date_str[4:6], date_str[6:8]
    prefix = f"{cfg.prefix}/{year}/{month}/{day}/{hhmm}/"

    result: dict[str, list[str]] = {b: [] for b in cfg.bands}

    try:
        resp = s3.list_objects_v2(Bucket=cfg.bucket, Prefix=prefix, MaxKeys=1000)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            m = _HSD_RE.search(key)
            if not m:
                continue
            _, _, band_num, segment = m.groups()
            band = f"B{band_num}"
            if band in cfg.bands and segment in cfg.nsw_segments:
                result[band].append(key)
    except Exception:
        logger.exception("Failed to list segment keys for %s", obs_timestamp)

    return result


def download_segments(
    cfg: HimawariConfig, segment_keys: dict[str, list[str]], download_dir: Path
) -> dict[str, list[Path]]:
    """Download HSD segment files from S3 in parallel.

    Returns {"B07": [path1, path2], "B14": [path3, path4]}.
    """
    s3 = _s3_client(cfg)
    all_keys = [(band, key) for band, keys in segment_keys.items() for key in keys]

    result: dict[str, list[Path]] = {b: [] for b in cfg.bands}

    def _download(band_key: tuple[str, str]) -> tuple[str, Path]:
        band, key = band_key
        filename = key.split("/")[-1]
        local_path = download_dir / filename
        s3.download_file(cfg.bucket, key, str(local_path))
        return band, local_path

    with ThreadPoolExecutor(max_workers=4) as pool:
        for band, path in pool.map(_download, all_keys):
            result[band].append(path)

    return result


def mark_processed(obs_timestamp: str) -> None:
    """Mark an observation as processed."""
    _processed.add(obs_timestamp)


def is_processed(obs_timestamp: str) -> bool:
    """Check if an observation was already processed."""
    return obs_timestamp in _processed


def get_processed_count() -> int:
    """Return number of processed observations."""
    return len(_processed)
