"""Entry point — FastAPI server with background polling tasks."""

import asyncio
import hashlib
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

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
from .export import export_events_geojson
from .himawari.config import HimawariConfig
from .himawari.poller import poll_himawari_loop
from .himawari import poller as himawari_poller
from .models import Detection, Source, SystemStatus
from .polling import scheduler

logger = logging.getLogger(__name__)

START_TIME = time.time()


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

    yield

    # Shutdown — cancel tasks and wait for them before closing DB
    dea_task.cancel()
    firms_task.cancel()
    tasks = [dea_task, firms_task]
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
