"""FIRMS CSV client — polls NASA FIRMS for VIIRS NRT detections."""

from __future__ import annotations

import csv
import hashlib
import io
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..config import settings
from ..models import Detection, Source

logger = logging.getLogger(__name__)

FIRMS_BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# VIIRS sources to poll
FIRMS_SOURCES = [
    ("VIIRS_NOAA20_NRT", "NOAA-20", "VIIRS"),
    ("VIIRS_NOAA21_NRT", "NOAA-21", "VIIRS"),
    ("VIIRS_SNPP_NRT", "Suomi-NPP", "VIIRS"),
    ("MODIS_NRT", "Terra/Aqua", "MODIS"),
]


def _make_source_id(satellite: str, lat: float, lon: float, acq_dt: str) -> str:
    raw = f"FIRMS|{satellite}|{lat}|{lon}|{acq_dt}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def poll_firms() -> list[Detection]:
    """Fetch recent fire detections from FIRMS for NSW bbox."""
    if not settings.firms_map_key:
        logger.warning("FIRMS_MAP_KEY not set, skipping FIRMS poll")
        return []

    west, south, east, north = settings.nsw_bbox
    area_str = f"{west},{south},{east},{north}"

    detections = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for source_key, satellite, instrument in FIRMS_SOURCES:
            try:
                url = f"{FIRMS_BASE_URL}/{settings.firms_map_key}/{source_key}/{area_str}/1"
                resp = await client.get(url)
                resp.raise_for_status()

                text = resp.text.strip()
                if not text or text.startswith("<!") or text.startswith("{"):
                    logger.warning("FIRMS %s returned non-CSV response", source_key)
                    continue

                reader = csv.DictReader(io.StringIO(text))
                count = 0
                for row in reader:
                    det = _parse_firms_row(row, satellite, instrument)
                    if det:
                        detections.append(det)
                        count += 1
                logger.info("FIRMS %s returned %d detections", source_key, count)

            except httpx.HTTPStatusError as e:
                logger.error("FIRMS %s HTTP error: %s", source_key, e)
            except httpx.RequestError as e:
                logger.error("FIRMS %s request error: %s", source_key, e)
            except Exception:
                logger.exception("FIRMS %s unexpected error", source_key)

    return detections


def _parse_firms_row(row: dict, satellite: str, instrument: str) -> Optional[Detection]:
    try:
        lat = float(row.get("latitude", ""))
        lon = float(row.get("longitude", ""))
    except (ValueError, TypeError):
        return None

    # Parse acquisition date + time
    acq_date = row.get("acq_date", "")
    acq_time = row.get("acq_time", "0000")
    if not acq_date:
        return None

    try:
        # acq_time is HHMM format
        acq_time = acq_time.zfill(4)
        dt_str = f"{acq_date} {acq_time[:2]}:{acq_time[2:]}"
        acq_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    # Confidence mapping — VIIRS uses l/n/h, MODIS uses 0-100
    conf_raw = row.get("confidence", "nominal")
    if conf_raw in ("l", "low"):
        confidence = "low"
    elif conf_raw in ("h", "high"):
        confidence = "high"
    elif conf_raw in ("n", "nominal"):
        confidence = "nominal"
    else:
        # Try numeric (MODIS)
        try:
            conf_num = int(conf_raw)
            if conf_num >= 80:
                confidence = "high"
            elif conf_num >= 30:
                confidence = "nominal"
            else:
                confidence = "low"
        except (ValueError, TypeError):
            confidence = "nominal"

    frp = None
    frp_raw = row.get("frp", "")
    if frp_raw:
        try:
            frp = float(frp_raw)
        except ValueError:
            pass

    brightness = None
    bright_raw = row.get("bright_ti4", "") or row.get("brightness", "")
    if bright_raw:
        try:
            brightness = float(bright_raw)
        except ValueError:
            pass

    daynight = row.get("daynight", "")

    source_id = _make_source_id(satellite, lat, lon, acq_dt.isoformat())

    return Detection(
        source_id=source_id,
        source=Source.FIRMS,
        satellite=satellite,
        instrument=instrument,
        latitude=lat,
        longitude=lon,
        acq_datetime=acq_dt,
        confidence=confidence,
        frp=frp,
        brightness=brightness,
        daynight=daynight if daynight else None,
    )
