"""Entry point — FastAPI server with background polling tasks."""

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import (
    close_db,
    count_detections,
    count_events,
    get_active_events,
    get_all_events,
    get_detections_for_event,
    get_event,
    get_recent_detections,
)
from .dedup import ingest_detection
from .export import REPORTS_DIR, export_events_geojson, save_daily_report
from .himawari.config import HimawariConfig
from .himawari.poller import poll_himawari_loop
from .himawari import pipeline as himawari_pipeline
from .himawari import poller as himawari_poller
from .models import Detection, Source, SystemStatus
from .polling import scheduler

AEST = ZoneInfo("Australia/Sydney")

logger = logging.getLogger(__name__)

START_TIME = time.time()


async def daily_report_loop():
    """Background task: generate daily report at 19:50 AEST (10 min before deadline).

    The XPRIZE competition requires daily reports due at 20:00 AEST.
    We generate at 19:50 to leave buffer for any issues.
    """
    while True:
        try:
            now_aest = datetime.now(timezone.utc).astimezone(AEST)
            target = now_aest.replace(hour=19, minute=50, second=0, microsecond=0)
            if now_aest >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now_aest).total_seconds()
            logger.info(
                "Daily report scheduler: next report in %.0f seconds (at %s AEST)",
                wait_seconds,
                target.strftime("%Y-%m-%d %H:%M"),
            )
            await asyncio.sleep(wait_seconds)

            # Generate the report for today (AEST date)
            report_date = datetime.now(timezone.utc).astimezone(AEST).date()
            logger.info("Generating scheduled daily report for %s", report_date)
            result = await save_daily_report(report_date=report_date)
            logger.info(
                "Daily report generated: %d events, saved to %s",
                result["n_events"],
                result["geojson_path"],
            )
        except asyncio.CancelledError:
            logger.info("Daily report scheduler cancelled")
            break
        except Exception:
            logger.exception("Error generating daily report — will retry tomorrow")
            # Sleep a bit to avoid tight error loops, then continue
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background polling on startup, cleanup on shutdown."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("Starting NAU Wildfire Detection System")
    logger.info("NSW bbox: %s", settings.nsw_bbox)
    logger.info("FIRMS key: %s", "configured" if settings.firms_map_key else "NOT SET")

    # Start polling loops
    dea_task = asyncio.create_task(scheduler.poll_dea_loop(settings.poll_interval_dea))
    firms_task = asyncio.create_task(scheduler.poll_firms_loop(settings.poll_interval_firms))

    # Start Himawari pipeline if enabled
    himawari_task = None
    if settings.himawari_enabled:
        himawari_cfg = HimawariConfig(poll_interval_s=settings.poll_interval_himawari)
        himawari_task = asyncio.create_task(poll_himawari_loop(himawari_cfg))
        logger.info("Himawari pipeline enabled (poll every %ds)", settings.poll_interval_himawari)
    else:
        logger.info("Himawari pipeline disabled")

    # Start daily report scheduler (generates at 19:50 AEST daily)
    report_task = asyncio.create_task(daily_report_loop())
    logger.info("Daily report scheduler started (19:50 AEST)")

    yield

    # Shutdown — cancel tasks and wait for them before closing DB
    dea_task.cancel()
    firms_task.cancel()
    report_task.cancel()
    tasks = [dea_task, firms_task, report_task]
    if himawari_task is not None:
        himawari_task.cancel()
        tasks.append(himawari_task)
    await asyncio.gather(*tasks, return_exceptions=True)
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="NAU Wildfire Detection System",
    description="XPRIZE wildfire detection fallback system",
    lifespan=lifespan,
)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def portal():
    """Serve the Leaflet portal."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/events")
async def api_events(include_closed: bool = Query(False)):
    """Get fire events."""
    if include_closed:
        events = await get_all_events()
    else:
        events = await get_active_events()
    return [e.model_dump() for e in events]


@app.get("/api/events/geojson")
async def api_events_geojson():
    """Get events as OGC GeoJSON FeatureCollection."""
    geojson = await export_events_geojson()
    return JSONResponse(content=geojson, media_type="application/geo+json")


@app.post("/api/reports/generate")
async def generate_report_now(
    report_date: str = Query(None, description="Report date (YYYY-MM-DD). Defaults to today AEST."),
):
    """Generate a daily report on demand.

    Produces both a GeoJSON file (OGC-compliant, loadable in ArcGIS) and
    a human-readable markdown summary. Files are saved to data/reports/.
    """
    try:
        if report_date:
            d = date.fromisoformat(report_date)
        else:
            d = None
        result = await save_daily_report(report_date=d)
        return result
    except ValueError:
        return JSONResponse(
            {"error": f"Invalid date format: {report_date!r} (expected YYYY-MM-DD)"},
            status_code=400,
        )
    except Exception as exc:
        logger.exception("Failed to generate daily report")
        return JSONResponse(
            {"error": f"Report generation failed: {exc}"},
            status_code=500,
        )


@app.get("/api/reports")
async def list_reports():
    """List all generated daily reports.

    Returns a list of reports with date, file paths, event count, and
    generation time. Sorted by date descending (most recent first).
    """
    if not REPORTS_DIR.exists():
        return []

    reports = []
    for geojson_file in sorted(REPORTS_DIR.glob("*_daily_report.geojson"), reverse=True):
        date_str = geojson_file.name.split("_daily_report")[0]
        summary_file = REPORTS_DIR / f"{date_str}_daily_report.md"

        # Read the GeoJSON to extract metadata
        try:
            with open(geojson_file) as f:
                data = json.load(f)
            metadata = data.get("metadata", {})
            n_events = len(data.get("features", []))
            reports.append({
                "date": date_str,
                "competition_day": metadata.get("competition_day"),
                "geojson_path": str(geojson_file),
                "summary_path": str(summary_file) if summary_file.exists() else None,
                "n_events": n_events,
                "generation_time_utc": metadata.get("generation_time_utc"),
                "generation_time_aest": metadata.get("generation_time_aest"),
            })
        except Exception:
            # If we can't read the file, include minimal info
            reports.append({
                "date": date_str,
                "competition_day": None,
                "geojson_path": str(geojson_file),
                "summary_path": str(summary_file) if summary_file.exists() else None,
                "n_events": None,
                "generation_time_utc": None,
                "generation_time_aest": None,
            })

    return reports


@app.get("/api/events/{event_id}")
async def api_event_detail(event_id: int):
    """Get a single event with its detections."""
    event = await get_event(event_id)
    if not event:
        return JSONResponse({"error": "Event not found"}, status_code=404)
    detections = await get_detections_for_event(event_id)
    return {
        "event": event.model_dump(),
        "detections": [d.model_dump() for d in detections],
    }


@app.get("/api/detections")
async def api_detections(hours: int = Query(24, ge=1, le=168)):
    """Get raw detections from the last N hours."""
    dets = await get_recent_detections(hours)
    return [d.model_dump() for d in dets]


@app.get("/api/status")
async def api_status():
    """System health and status."""
    status = SystemStatus(
        uptime_seconds=round(time.time() - START_TIME, 1),
        total_detections=await count_detections(),
        total_events=await count_events(),
        active_events=len(await get_active_events()),
        last_poll_dea=scheduler.last_poll_dea,
        last_poll_firms=scheduler.last_poll_firms,
        last_poll_dea_ok=scheduler.last_poll_dea_ok,
        last_poll_firms_ok=scheduler.last_poll_firms_ok,
        last_poll_himawari=himawari_poller.last_poll_himawari,
        last_poll_himawari_ok=himawari_poller.last_poll_himawari_ok,
        himawari_observations_processed=himawari_poller.observations_processed,
    )
    return status.model_dump()


@app.get("/api/cusum/heatmap")
async def api_cusum_heatmap():
    """Get current CUSUM fire probability grid for heatmap display.

    Returns pixels where P(fire) exceeds the display threshold, suitable
    for rendering as a circle-marker heatmap layer on the portal map.
    """
    latest = himawari_pipeline._latest_cusum_result
    if latest is None:
        return JSONResponse(content={
            "obs_time": None,
            "pixels": [],
            "initialized_pct": 0.0,
            "n_above_display_threshold": 0,
            "max_fire_probability": 0.0,
        })

    cusum_result = latest["cusum_result"]
    lats = latest["lats_flat"]
    lons = latest["lons_flat"]
    obs_time = latest["obs_time"]
    stats = latest["cusum_stats"]
    threshold = latest["display_probability_threshold"]

    fp = cusum_result["fire_probability"]
    s_slow = cusum_result["cusum_values_slow"]
    s_fast = cusum_result["cusum_values_fast"]

    # Select pixels above display threshold with finite probability
    mask = np.isfinite(fp) & (fp >= threshold)
    indices = np.where(mask)[0]

    pixels = []
    for idx in indices:
        pixels.append({
            "lat": round(float(lats[idx]), 4),
            "lon": round(float(lons[idx]), 4),
            "probability": round(float(fp[idx]), 4),
            "s_slow": round(float(s_slow[idx]), 2),
            "s_fast": round(float(s_fast[idx]), 2),
        })

    obs_time_str = None
    if obs_time is not None:
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)
        obs_time_str = obs_time.isoformat()

    max_prob = float(np.nanmax(fp)) if np.any(np.isfinite(fp)) else 0.0

    return JSONResponse(content={
        "obs_time": obs_time_str,
        "pixels": pixels,
        "initialized_pct": stats.get("initialized_pct", 0.0),
        "n_above_display_threshold": len(pixels),
        "max_fire_probability": round(max_prob, 6),
    })


@app.get("/health")
async def health():
    """Lightweight liveness probe."""
    return {"status": "ok"}


@app.post("/api/test-fire")
async def api_test_fire(
    lat: float = Query(-33.5, description="Latitude"),
    lon: float = Query(150.5, description="Longitude"),
    confidence: str = Query("high", description="Confidence level"),
    frp: float = Query(50.0, description="Fire Radiative Power"),
):
    """Insert a synthetic detection for testing. Only available in debug mode."""
    if not settings.debug:
        return JSONResponse({"error": "Test fires disabled in production"}, status_code=403)

    now = datetime.now(timezone.utc)
    source_id = hashlib.sha256(f"TEST|{lat}|{lon}|{now.isoformat()}".encode()).hexdigest()

    det = Detection(
        source_id=source_id,
        source=Source.FIRMS,
        satellite="TEST",
        instrument="SYNTHETIC",
        latitude=lat,
        longitude=lon,
        acq_datetime=now,
        confidence=confidence,
        frp=frp,
        brightness=350.0,
        daynight="D",
    )

    result = await ingest_detection(det)
    return result


def main():
    uvicorn.run(
        "src.__main__:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
