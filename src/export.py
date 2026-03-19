"""GeoJSON export — OGC-compliant FeatureCollection for fire events (RFC 7946).

Provides two modes:
  1. Live export (export_events_geojson) — used by portal's /api/events/geojson endpoint
  2. Daily report snapshot (generate_daily_report_geojson) — timestamped, with metadata,
     for XPRIZE daily submission (due 20:00 AEST)
"""

import json
import logging
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .config import DATA_DIR
from .db import get_active_events, get_all_events
from .models import Event

logger = logging.getLogger(__name__)

SYSTEM_VERSION = "2.0.0"
TEAM_NAME = "NAU Wildfire Detection"
COMPETITION_START = date(2026, 4, 9)
COMPETITION_END = date(2026, 4, 21)
AEST = ZoneInfo("Australia/Sydney")
REPORTS_DIR = DATA_DIR / "reports"


def _to_iso(val) -> str:
    """Ensure ISO 8601 format with T separator and timezone."""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    # String from DB — already ISO 8601 with T separator
    return str(val)


def _competition_day(report_date: date) -> Optional[int]:
    """Return competition day number (1-13), or None if outside competition window."""
    delta = (report_date - COMPETITION_START).days + 1
    if 1 <= delta <= (COMPETITION_END - COMPETITION_START).days + 1:
        return delta
    return None


def _uncertainty_circle_geometry(lat: float, lon: float, radius_m: float,
                                  num_points: int = 32) -> dict:
    """Generate a GeoJSON Polygon approximating an uncertainty circle.

    Uses a simple equirectangular approximation, which is fine for the small
    radii involved (typically 375m–4000m).
    """
    # Degrees per meter at this latitude
    lat_rad = math.radians(lat)
    deg_per_m_lat = 1.0 / 111_320.0
    deg_per_m_lon = 1.0 / (111_320.0 * math.cos(lat_rad))

    coords = []
    for i in range(num_points + 1):
        angle = 2 * math.pi * i / num_points
        dlat = radius_m * math.sin(angle) * deg_per_m_lat
        dlon = radius_m * math.cos(angle) * deg_per_m_lon
        coords.append([round(lon + dlon, 7), round(lat + dlat, 7)])

    return {
        "type": "Polygon",
        "coordinates": [coords],
    }


def _event_to_feature(event: Event, include_uncertainty_geometry: bool = False) -> dict:
    """Convert an event to a GeoJSON Feature.

    Args:
        event: Fire event from the database.
        include_uncertainty_geometry: If True, use GeometryCollection with both
            the centroid point and the uncertainty circle polygon. If False,
            use a simple Point (for portal compatibility).
    """
    status_val = event.status.value if hasattr(event.status, "value") else event.status

    properties = {
        "event_id": event.id,
        "status": status_val,
        "centroid_lat": event.centroid_lat,
        "centroid_lon": event.centroid_lon,
        "location_uncertainty_m": event.location_uncertainty_m,
        "first_detection_time": _to_iso(event.first_detection_time),
        "latest_detection_time": _to_iso(event.latest_detection_time),
        "detection_count": event.detection_count,
        "sources": event.source_set,
        "max_frp": event.max_frp,
        "max_confidence": event.max_confidence,
    }

    if include_uncertainty_geometry:
        geometry = {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "type": "Point",
                    "coordinates": [event.centroid_lon, event.centroid_lat],
                },
                _uncertainty_circle_geometry(
                    event.centroid_lat,
                    event.centroid_lon,
                    event.location_uncertainty_m,
                ),
            ],
        }
    else:
        geometry = {
            "type": "Point",
            "coordinates": [event.centroid_lon, event.centroid_lat],
        }

    return {
        "type": "Feature",
        "id": event.id,
        "geometry": geometry,
        "properties": properties,
    }


async def export_events_geojson() -> dict:
    """Generate an OGC-compliant GeoJSON FeatureCollection of active events.

    Follows RFC 7946: no crs member (WGS84 assumed), coordinates in [lon, lat].
    Used by the live portal endpoint — kept lightweight for frequent polling.
    """
    events = await get_active_events()
    features = [_event_to_feature(e, include_uncertainty_geometry=False) for e in events]

    return {
        "type": "FeatureCollection",
        "name": "NAU_Wildfire_Detections",
        "features": features,
    }


async def generate_daily_report_geojson(
    report_date: Optional[date] = None,
    include_closed: bool = True,
) -> dict:
    """Generate a daily report GeoJSON with full OGC compliance and metadata.

    This is a *snapshot* — all events are captured at report generation time.
    Intended for XPRIZE daily submission.

    Args:
        report_date: The date this report covers. Defaults to today in AEST.
        include_closed: Whether to include CLOSED/RETRACTED events.

    Returns:
        A GeoJSON FeatureCollection dict with metadata properties.
    """
    now_utc = datetime.now(timezone.utc)
    now_aest = now_utc.astimezone(AEST)

    if report_date is None:
        report_date = now_aest.date()

    comp_day = _competition_day(report_date)

    if include_closed:
        events = await get_all_events()
    else:
        events = await get_active_events()

    features = [_event_to_feature(e, include_uncertainty_geometry=True) for e in events]

    # Count events by status for summary
    status_counts: dict[str, int] = {}
    for e in events:
        s = e.status.value if hasattr(e.status, "value") else e.status
        status_counts[s] = status_counts.get(s, 0) + 1

    # Build the FeatureCollection with metadata
    # Note: RFC 7946 says CRS is always WGS84 and the "crs" member is removed.
    # However, ArcGIS and many GIS tools expect it. We include it as a
    # foreign member for practical compatibility while remaining RFC 7946 valid
    # (foreign members are allowed).
    geojson = {
        "type": "FeatureCollection",
        "name": "NAU_Wildfire_Daily_Report",
        "crs": {
            "type": "name",
            "properties": {
                "name": "urn:ogc:def:crs:EPSG::4326"
            }
        },
        "metadata": {
            "team": TEAM_NAME,
            "system_version": SYSTEM_VERSION,
            "report_date": report_date.isoformat(),
            "competition_day": comp_day,
            "generation_time_utc": now_utc.isoformat(),
            "generation_time_aest": now_aest.isoformat(),
            "total_events": len(events),
            "status_summary": status_counts,
            "coordinate_reference_system": "EPSG:4326 (WGS84)",
            "note": "All coordinates are [longitude, latitude] per RFC 7946. "
                    "Uncertainty circles are approximate (equirectangular projection).",
        },
        "features": features,
    }

    return geojson


def _generate_markdown_summary(
    events: list[Event],
    report_date: date,
    generation_time: datetime,
    geojson_path: Path,
) -> str:
    """Generate a human-readable markdown summary of the daily report."""
    comp_day = _competition_day(report_date)
    comp_day_str = f"Day {comp_day}" if comp_day else "Pre-competition"

    # Status counts
    status_counts: dict[str, int] = {}
    for e in events:
        s = e.status.value if hasattr(e.status, "value") else e.status
        status_counts[s] = status_counts.get(s, 0) + 1

    active_statuses = {"PROVISIONAL", "LIKELY", "CONFIRMED", "MONITORING"}
    active_events = [e for e in events
                     if (e.status.value if hasattr(e.status, "value") else e.status)
                     in active_statuses]

    lines = [
        f"# Daily Fire Report — {report_date.isoformat()} ({comp_day_str})",
        "",
        f"**Generated:** {generation_time.astimezone(AEST).strftime('%Y-%m-%d %H:%M:%S AEST')}  ",
        f"**System:** {TEAM_NAME} v{SYSTEM_VERSION}  ",
        f"**GeoJSON:** `{geojson_path.name}`",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total events | {len(events)} |",
        f"| Active events | {len(active_events)} |",
    ]

    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.append("")

    if active_events:
        lines.extend([
            "## Active Fire Events",
            "",
            "| ID | Status | Lat | Lon | Confidence | Detections | Sources | First Detected | FRP |",
            "|----|--------|-----|-----|------------|------------|---------|----------------|-----|",
        ])
        for e in active_events:
            first_dt = _to_iso(e.first_detection_time)
            status_val = e.status.value if hasattr(e.status, "value") else e.status
            frp_str = f"{e.max_frp:.1f}" if e.max_frp else "—"
            lines.append(
                f"| {e.id} | {status_val} | {e.centroid_lat:.4f} | "
                f"{e.centroid_lon:.4f} | {e.max_confidence} | "
                f"{e.detection_count} | {e.source_set} | {first_dt} | {frp_str} |"
            )
        lines.append("")
    else:
        lines.extend(["## Active Fire Events", "", "No active fire events.", ""])

    lines.extend([
        "---",
        f"*Report generated automatically by {TEAM_NAME} system.*",
    ])

    return "\n".join(lines)


async def save_daily_report(
    report_date: Optional[date] = None,
    include_closed: bool = True,
) -> dict:
    """Generate and save the daily report (GeoJSON + markdown summary).

    Args:
        report_date: Date to report on. Defaults to today (AEST).
        include_closed: Whether to include closed/retracted events.

    Returns:
        Dict with report metadata: date, paths, event count, generation time.
    """
    now_utc = datetime.now(timezone.utc)
    now_aest = now_utc.astimezone(AEST)

    if report_date is None:
        report_date = now_aest.date()

    # Ensure reports directory exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate GeoJSON
    geojson = await generate_daily_report_geojson(
        report_date=report_date,
        include_closed=include_closed,
    )

    # File paths
    date_str = report_date.isoformat()
    geojson_path = REPORTS_DIR / f"{date_str}_daily_report.geojson"
    summary_path = REPORTS_DIR / f"{date_str}_daily_report.md"

    # Save GeoJSON
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2, default=str)
    logger.info("Saved GeoJSON report: %s (%d events)",
                geojson_path, len(geojson["features"]))

    # Get event list for markdown (re-query to avoid coupling)
    if include_closed:
        events = await get_all_events()
    else:
        events = await get_active_events()

    # Save markdown summary
    md_content = _generate_markdown_summary(events, report_date, now_utc, geojson_path)
    with open(summary_path, "w") as f:
        f.write(md_content)
    logger.info("Saved markdown summary: %s", summary_path)

    return {
        "date": date_str,
        "competition_day": _competition_day(report_date),
        "geojson_path": str(geojson_path),
        "summary_path": str(summary_path),
        "n_events": len(geojson["features"]),
        "generation_time_utc": now_utc.isoformat(),
        "generation_time_aest": now_aest.isoformat(),
    }
