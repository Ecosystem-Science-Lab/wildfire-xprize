"""Configuration and settings for the wildfire detection system."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "detections.db"
ENV_FILE = PROJECT_ROOT / "config" / "api_keys.env"


class Settings(BaseSettings):
    # FIRMS API
    firms_map_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Polling intervals (seconds)
    poll_interval_dea: int = 300  # 5 minutes
    poll_interval_firms: int = 300  # 5 minutes

    # NSW bounding box (full state: SA border ~141E to coast ~154E)
    nsw_bbox_west: float = 140.9
    nsw_bbox_south: float = -38.0
    nsw_bbox_east: float = 154.0
    nsw_bbox_north: float = -28.0

    # Event association
    event_radius_km: float = 2.0

    # Himawari pipeline
    himawari_enabled: bool = True
    poll_interval_himawari: int = 120
    cusum_enabled: bool = True  # CUSUM temporal fire detection (within Himawari pipeline)

    # Display
    timezone_display: str = "Australia/Sydney"

    model_config = {"env_file": str(ENV_FILE), "extra": "ignore"}

    @property
    def nsw_bbox(self) -> tuple[float, float, float, float]:
        """Returns (west, south, east, north)."""
        return (self.nsw_bbox_west, self.nsw_bbox_south, self.nsw_bbox_east, self.nsw_bbox_north)


settings = Settings()
