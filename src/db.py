"""SQLite database layer using aiosqlite."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite

from .config import DB_PATH, DATA_DIR
from .models import Detection, DetectionRow, Event, EventStatus

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    satellite TEXT NOT NULL,
    instrument TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    acq_datetime TEXT NOT NULL,
    confidence TEXT DEFAULT 'nominal',
    frp REAL,
    brightness REAL,
    daynight TEXT,
    event_id INTEGER REFERENCES events(id),
    ingested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_detections_source_id ON detections(source_id);
CREATE INDEX IF NOT EXISTS idx_detections_event_id ON detections(event_id);
CREATE INDEX IF NOT EXISTS idx_detections_acq_datetime ON detections(acq_datetime);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'PROVISIONAL',
    centroid_lat REAL NOT NULL,
    centroid_lon REAL NOT NULL,
    location_uncertainty_m REAL NOT NULL DEFAULT 2000.0,
    first_detection_time TEXT NOT NULL,
    latest_detection_time TEXT NOT NULL,
    detection_count INTEGER NOT NULL DEFAULT 1,
    source_set TEXT NOT NULL DEFAULT '',
    max_frp REAL,
    max_confidence TEXT DEFAULT 'nominal'
);

CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
"""

# Allowed column names for update_event to prevent SQL injection
_EVENT_COLUMNS = frozenset({
    "status", "centroid_lat", "centroid_lon", "location_uncertainty_m",
    "first_detection_time", "latest_detection_time", "detection_count",
    "source_set", "max_frp", "max_confidence",
})

_db: Optional[aiosqlite.Connection] = None
_db_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    global _db
    async with _db_lock:
        if _db is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _db = await aiosqlite.connect(str(DB_PATH))
            _db.row_factory = aiosqlite.Row
            await _db.execute("PRAGMA journal_mode=WAL")
            await _db.executescript(SCHEMA)
            await _db.commit()
            logger.info("Database initialized at %s (WAL mode)", DB_PATH)
    return _db


async def close_db():
    global _db
    async with _db_lock:
        if _db is not None:
            await _db.close()
            _db = None


async def insert_detection(det: Detection) -> Optional[int]:
    """Insert a detection. Returns row id if new, None if duplicate."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    try:
        cursor = await db.execute(
            """INSERT OR IGNORE INTO detections
               (source_id, source, satellite, instrument, latitude, longitude,
                acq_datetime, confidence, frp, brightness, daynight, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                det.source_id, det.source.value, det.satellite, det.instrument,
                det.latitude, det.longitude, det.acq_datetime.isoformat(),
                det.confidence, det.frp, det.brightness, det.daynight, now,
            ),
        )
        await db.commit()
        if cursor.rowcount > 0:
            return cursor.lastrowid
        return None
    except Exception:
        logger.exception("Failed to insert detection %s", det.source_id)
        return None


async def set_detection_event(detection_id: int, event_id: int):
    db = await get_db()
    await db.execute(
        "UPDATE detections SET event_id = ? WHERE id = ?",
        (event_id, detection_id),
    )
    await db.commit()


async def get_detection(detection_id: int) -> Optional[DetectionRow]:
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM detections WHERE id = ?", (detection_id,)
    )
    if row:
        return _row_to_detection(row[0])
    return None


async def get_detections_for_event(event_id: int) -> list[DetectionRow]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM detections WHERE event_id = ? ORDER BY acq_datetime",
        (event_id,),
    )
    return [_row_to_detection(r) for r in rows]


async def get_recent_detections(hours: int = 24) -> list[DetectionRow]:
    db = await get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=int(hours))).isoformat()
    rows = await db.execute_fetchall(
        """SELECT * FROM detections
           WHERE acq_datetime >= ?
           ORDER BY acq_datetime DESC""",
        (cutoff,),
    )
    return [_row_to_detection(r) for r in rows]


async def create_event(det: Detection) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO events
           (status, centroid_lat, centroid_lon, location_uncertainty_m,
            first_detection_time, latest_detection_time,
            detection_count, source_set, max_frp, max_confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            EventStatus.PROVISIONAL.value,
            det.latitude, det.longitude,
            4000.0 if det.source.value == "HIMAWARI" else 2000.0,
            det.acq_datetime.isoformat(), det.acq_datetime.isoformat(),
            1, det.source.value, det.frp, det.confidence,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def get_event(event_id: int) -> Optional[Event]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM events WHERE id = ?", (event_id,)
    )
    if rows:
        return _row_to_event(rows[0])
    return None


async def get_active_events() -> list[Event]:
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT * FROM events
           WHERE status NOT IN ('RETRACTED', 'CLOSED')
           ORDER BY latest_detection_time DESC"""
    )
    return [_row_to_event(r) for r in rows]


async def get_all_events() -> list[Event]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM events ORDER BY latest_detection_time DESC"
    )
    return [_row_to_event(r) for r in rows]


async def update_event(event_id: int, **kwargs):
    # Whitelist column names to prevent SQL injection
    bad_keys = set(kwargs.keys()) - _EVENT_COLUMNS
    if bad_keys:
        raise ValueError(f"Invalid event columns: {bad_keys}")
    db = await get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [event_id]
    await db.execute(f"UPDATE events SET {sets} WHERE id = ?", vals)
    await db.commit()


async def count_detections() -> int:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM detections")
    return rows[0]["cnt"]


async def count_events() -> int:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT COUNT(*) as cnt FROM events")
    return rows[0]["cnt"]


def _row_to_detection(row) -> DetectionRow:
    return DetectionRow(
        id=row["id"],
        source_id=row["source_id"],
        source=row["source"],
        satellite=row["satellite"],
        instrument=row["instrument"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        acq_datetime=row["acq_datetime"],
        confidence=row["confidence"],
        frp=row["frp"],
        brightness=row["brightness"],
        daynight=row["daynight"],
        event_id=row["event_id"],
        ingested_at=row["ingested_at"],
    )


def _row_to_event(row) -> Event:
    return Event(
        id=row["id"],
        status=row["status"],
        centroid_lat=row["centroid_lat"],
        centroid_lon=row["centroid_lon"],
        location_uncertainty_m=row["location_uncertainty_m"],
        first_detection_time=row["first_detection_time"],
        latest_detection_time=row["latest_detection_time"],
        detection_count=row["detection_count"],
        source_set=row["source_set"],
        max_frp=row["max_frp"],
        max_confidence=row["max_confidence"],
    )
