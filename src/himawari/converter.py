"""Convert fire detection pixels to Detection objects for the event store."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import numpy as np

from ..models import Detection, Source
from .config import HimawariConfig

logger = logging.getLogger(__name__)

_CONFIDENCE_MAP = {1: "low", 2: "nominal", 3: "high"}


def fire_pixels_to_detections(
    fire_mask: np.ndarray,
    bt7: np.ndarray,
    bt14: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    obs_time: datetime,
    sza: np.ndarray,
    cfg: HimawariConfig,
) -> list[Detection]:
    """Convert fire mask pixels into Detection objects.

    Args:
        fire_mask: Array with 0=no fire, 1=LOW, 2=NOMINAL, 3=HIGH
        bt7, bt14: Brightness temperature arrays
        lats, lons: Coordinate arrays
        obs_time: Observation time (UTC)
        sza: Solar zenith angle array
        cfg: Pipeline configuration

    Returns:
        List of Detection objects ready for ingest_detection().
    """
    fire_rows, fire_cols = np.where(fire_mask > 0)
    detections: list[Detection] = []

    # Ensure obs_time is timezone-aware
    if obs_time.tzinfo is None:
        obs_time = obs_time.replace(tzinfo=timezone.utc)

    for i in range(len(fire_rows)):
        r, c = int(fire_rows[i]), int(fire_cols[i])
        lat = float(lats[r, c])
        lon = float(lons[r, c])
        confidence_level = int(fire_mask[r, c])
        confidence = _CONFIDENCE_MAP.get(confidence_level, "low")
        brightness = float(bt7[r, c])
        daynight = "D" if sza[r, c] < cfg.sza_day_night_deg else "N"

        # Unique source ID
        source_id = hashlib.sha256(
            f"HIMAWARI|{lat:.4f}|{lon:.4f}|{obs_time.isoformat()}".encode()
        ).hexdigest()

        det = Detection(
            source_id=source_id,
            source=Source.HIMAWARI,
            satellite="Himawari-9",
            instrument="AHI",
            latitude=lat,
            longitude=lon,
            acq_datetime=obs_time,
            confidence=confidence,
            frp=None,  # AHI doesn't directly provide FRP at this stage
            brightness=brightness,
            daynight=daynight,
        )
        detections.append(det)

    logger.info(
        "Converted %d fire pixels to detections (obs_time=%s)",
        len(detections),
        obs_time.isoformat(),
    )
    return detections
