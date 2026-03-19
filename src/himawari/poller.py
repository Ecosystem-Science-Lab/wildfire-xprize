"""S3 polling loop for Himawari observations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .config import HimawariConfig
from .downloader import get_processed_count, is_processed, list_recent_observations, mark_processed
from .pipeline import process_observation

logger = logging.getLogger(__name__)

# Shared state for status endpoint
last_poll_himawari: Optional[datetime] = None
last_poll_himawari_ok: bool = False
observations_processed: int = 0


async def poll_himawari_loop(cfg: HimawariConfig) -> None:
    """Infinite polling loop: find new observations on S3 and process them."""
    global last_poll_himawari, last_poll_himawari_ok, observations_processed

    logger.info(
        "Himawari polling started (interval=%ds, lookback=%dmin)",
        cfg.poll_interval_s,
        cfg.max_observation_age_min,
    )

    while True:
        try:
            recent = await asyncio.to_thread(
                list_recent_observations, cfg, cfg.max_observation_age_min
            )
            new_obs = [ts for ts in recent if not is_processed(ts)]

            if new_obs:
                logger.info("Found %d new Himawari observations: %s", len(new_obs), new_obs)

            for obs_ts in new_obs:
                try:
                    stats = await process_observation(obs_ts, cfg)
                    mark_processed(obs_ts)
                    observations_processed = get_processed_count()

                    if stats.get("status") == "ok":
                        logger.info(
                            "Himawari %s: %d fires detected (%d new detections)",
                            obs_ts,
                            stats.get("n_fires", 0),
                            stats.get("detections_new", 0),
                        )
                except Exception:
                    logger.exception("Failed to process Himawari observation %s", obs_ts)

            last_poll_himawari = datetime.now(timezone.utc)
            last_poll_himawari_ok = True

        except Exception:
            last_poll_himawari_ok = False
            logger.exception("Himawari poll cycle failed")

        await asyncio.sleep(cfg.poll_interval_s)
