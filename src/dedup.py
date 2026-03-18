"""Detection deduplication and event association."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

from .config import settings
from .db import (
    create_event,
    get_active_events,
    get_detections_for_event,
    insert_detection,
    set_detection_event,
    update_event,
)
from .events import evaluate_confidence
from .models import Detection, Event, EventStatus

logger = logging.getLogger(__name__)


def _ensure_datetime(val) -> datetime:
    """Convert string or datetime to datetime."""
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return val


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    a = min(max(a, 0.0), 1.0)  # Clamp for FP stability
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def ingest_detection(det: Detection) -> dict:
    """Ingest a single detection: dedup, associate with event, update confidence.

    Returns dict with keys: new (bool), detection_id, event_id, event_status.
    """
    # Insert — returns None if duplicate
    det_id = await insert_detection(det)
    if det_id is None:
        return {"new": False, "detection_id": None, "event_id": None, "event_status": None}

    # Find nearest active event within radius
    active_events = await get_active_events()
    nearest_event: Optional[Event] = None
    nearest_dist = float("inf")

    for event in active_events:
        dist = haversine_km(det.latitude, det.longitude, event.centroid_lat, event.centroid_lon)
        if dist < settings.event_radius_km and dist < nearest_dist:
            nearest_event = event
            nearest_dist = dist

    if nearest_event is not None:
        # Associate with existing event
        event_id = nearest_event.id
        await set_detection_event(det_id, event_id)

        # Update event metadata
        new_count = nearest_event.detection_count + 1
        sources = set(nearest_event.source_set.split(",")) if nearest_event.source_set else set()
        sources.add(det.source.value)
        source_set = ",".join(sorted(sources))

        # Update centroid (running average)
        new_lat = (nearest_event.centroid_lat * nearest_event.detection_count + det.latitude) / new_count
        new_lon = (nearest_event.centroid_lon * nearest_event.detection_count + det.longitude) / new_count

        # max_frp: preserve 0.0 as valid, only use None when both are None
        evt_frp = nearest_event.max_frp
        det_frp = det.frp
        if evt_frp is not None and det_frp is not None:
            max_frp = max(evt_frp, det_frp)
        elif evt_frp is not None:
            max_frp = evt_frp
        elif det_frp is not None:
            max_frp = det_frp
        else:
            max_frp = None

        max_conf = _higher_confidence(nearest_event.max_confidence, det.confidence)

        # Ensure datetime comparison works (both as datetime objects)
        evt_first = _ensure_datetime(nearest_event.first_detection_time)
        evt_latest = _ensure_datetime(nearest_event.latest_detection_time)
        det_time = _ensure_datetime(det.acq_datetime)

        first_time = min(evt_first, det_time)
        latest_time = max(evt_latest, det_time)

        await update_event(
            event_id,
            centroid_lat=new_lat,
            centroid_lon=new_lon,
            detection_count=new_count,
            source_set=source_set,
            max_frp=max_frp,
            max_confidence=max_conf,
            first_detection_time=first_time.isoformat(),
            latest_detection_time=latest_time.isoformat(),
        )

        # Re-evaluate confidence
        detections = await get_detections_for_event(event_id)
        new_status = evaluate_confidence(detections, source_set)
        # Only upgrade, never downgrade
        current = nearest_event.status
        if _status_rank(new_status) > _status_rank(current):
            await update_event(event_id, status=new_status.value)
            event_status = new_status.value
        else:
            event_status = current.value if isinstance(current, EventStatus) else current

    else:
        # Create new event
        event_id = await create_event(det)
        await set_detection_event(det_id, event_id)
        event_status = "PROVISIONAL"

    return {
        "new": True,
        "detection_id": det_id,
        "event_id": event_id,
        "event_status": event_status,
    }


async def ingest_batch(detections: list[Detection]) -> dict:
    """Ingest a batch of detections. Returns summary stats."""
    new_count = 0
    dup_count = 0
    for det in detections:
        result = await ingest_detection(det)
        if result["new"]:
            new_count += 1
        else:
            dup_count += 1
    return {"new": new_count, "duplicates": dup_count, "total": len(detections)}


_CONFIDENCE_RANK = {"low": 0, "nominal": 1, "high": 2}


def _higher_confidence(a: str, b: str) -> str:
    return a if _CONFIDENCE_RANK.get(a, 0) >= _CONFIDENCE_RANK.get(b, 0) else b


_STATUS_RANK = {
    "RETRACTED": -1,
    "CLOSED": 0,
    "PROVISIONAL": 1,
    "LIKELY": 2,
    "CONFIRMED": 3,
    "MONITORING": 4,
}


def _status_rank(status) -> int:
    if hasattr(status, "value"):
        return _STATUS_RANK.get(status.value, 0)
    return _STATUS_RANK.get(str(status), 0)
