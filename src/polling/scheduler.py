"""Polling loop orchestrator — runs DEA and FIRMS polls on schedule."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from ..dedup import ingest_batch
from .dea_hotspots import poll_dea_hotspots
from .firms import poll_firms

logger = logging.getLogger(__name__)

# Shared state for status endpoint
last_poll_dea: Optional[datetime] = None
last_poll_firms: Optional[datetime] = None
last_poll_dea_ok: bool = False
last_poll_firms_ok: bool = False


async def poll_dea_loop(interval: int):
    """Poll DEA Hotspots on interval."""
    global last_poll_dea, last_poll_dea_ok
    while True:
        try:
            logger.info("Polling DEA Hotspots...")
            detections = await poll_dea_hotspots()
            stats = await ingest_batch(detections)
            last_poll_dea = datetime.now(timezone.utc)
            last_poll_dea_ok = True
            logger.info(
                "DEA poll complete: %d new, %d duplicates",
                stats["new"], stats["duplicates"],
            )
        except Exception:
            last_poll_dea_ok = False
            logger.exception("DEA poll failed")
        await asyncio.sleep(interval)


async def poll_firms_loop(interval: int):
    """Poll FIRMS on interval."""
    global last_poll_firms, last_poll_firms_ok
    while True:
        try:
            logger.info("Polling FIRMS...")
            detections = await poll_firms()
            stats = await ingest_batch(detections)
            last_poll_firms = datetime.now(timezone.utc)
            last_poll_firms_ok = True
            logger.info(
                "FIRMS poll complete: %d new, %d duplicates",
                stats["new"], stats["duplicates"],
            )
        except Exception:
            last_poll_firms_ok = False
            logger.exception("FIRMS poll failed")
        await asyncio.sleep(interval)
