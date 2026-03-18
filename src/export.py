"""GeoJSON export — OGC-compliant FeatureCollection for fire events (RFC 7946)."""

from datetime import datetime, timezone

from .db import get_active_events
from .models import Event


def _to_iso(val) -> str:
    """Ensure ISO 8601 format with T separator."""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    # String from DB — already ISO 8601 with T separator
    return str(val)


def _event_to_feature(event: Event) -> dict:
    """Convert an event to a GeoJSON Feature."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [event.centroid_lon, event.centroid_lat],
        },
        "properties": {
            "id": event.id,
            "status": event.status.value if hasattr(event.status, "value") else event.status,
            "centroid_lat": event.centroid_lat,
            "centroid_lon": event.centroid_lon,
            "location_uncertainty_m": event.location_uncertainty_m,
            "first_detection_time": _to_iso(event.first_detection_time),
            "latest_detection_time": _to_iso(event.latest_detection_time),
            "detection_count": event.detection_count,
            "sources": event.source_set,
            "max_frp": event.max_frp,
            "max_confidence": event.max_confidence,
        },
    }


async def export_events_geojson() -> dict:
    """Generate an OGC-compliant GeoJSON FeatureCollection of active events.

    Follows RFC 7946: no crs member (WGS84 assumed), coordinates in [lon, lat].
    """
    events = await get_active_events()
    features = [_event_to_feature(e) for e in events]

    return {
        "type": "FeatureCollection",
        "name": "NAU_Wildfire_Detections",
        "features": features,
    }
