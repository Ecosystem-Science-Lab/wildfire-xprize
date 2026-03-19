"""Pydantic models and enums for the wildfire detection system."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Source(str, Enum):
    DEA = "DEA"
    FIRMS = "FIRMS"
    HIMAWARI = "HIMAWARI"


class EventStatus(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    LIKELY = "LIKELY"
    CONFIRMED = "CONFIRMED"
    MONITORING = "MONITORING"
    RETRACTED = "RETRACTED"
    CLOSED = "CLOSED"


class Detection(BaseModel):
    source_id: str
    source: Source
    satellite: str
    instrument: str
    latitude: float
    longitude: float
    acq_datetime: datetime
    confidence: str = "nominal"
    frp: Optional[float] = None
    brightness: Optional[float] = None
    daynight: Optional[str] = None


class DetectionRow(Detection):
    id: int
    event_id: Optional[int] = None
    ingested_at: datetime


class Event(BaseModel):
    id: int
    status: EventStatus
    centroid_lat: float
    centroid_lon: float
    location_uncertainty_m: float
    first_detection_time: datetime
    latest_detection_time: datetime
    detection_count: int
    source_set: str
    max_frp: Optional[float] = None
    max_confidence: str = "nominal"


class SystemStatus(BaseModel):
    uptime_seconds: float
    total_detections: int
    total_events: int
    active_events: int
    last_poll_dea: Optional[datetime] = None
    last_poll_firms: Optional[datetime] = None
    last_poll_dea_ok: bool = False
    last_poll_firms_ok: bool = False
    last_poll_himawari: Optional[datetime] = None
    last_poll_himawari_ok: bool = False
    himawari_observations_processed: int = 0
