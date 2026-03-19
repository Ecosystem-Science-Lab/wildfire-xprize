"""Decode Himawari HSD files to brightness temperature arrays via satpy."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from ..config import settings

logger = logging.getLogger(__name__)


def decode_hsd_to_bt(
    b07_files: list[Path], b14_files: list[Path]
) -> dict[str, any]:
    """Decode HSD segment files to brightness temperature arrays, cropped to NSW.

    Uses satpy's crop() to produce compact arrays covering only the NSW bbox,
    and synchronous dask scheduler to avoid task-graph overhead.

    Args:
        b07_files: Paths to Band 7 (3.9um) HSD .DAT.bz2 files
        b14_files: Paths to Band 14 (11.2um) HSD .DAT.bz2 files

    Returns:
        dict with keys:
            bt7: np.ndarray (float32) — Band 7 brightness temps in K
            bt14: np.ndarray (float32) — Band 14 brightness temps in K
            lats: np.ndarray (float32)
            lons: np.ndarray (float32)
            obs_time: datetime (UTC)
    """
    import dask
    from satpy import Scene

    all_files = [str(f) for f in b07_files + b14_files]
    logger.info("Decoding %d HSD files with satpy (cropped to NSW)", len(all_files))

    west, south, east, north = settings.nsw_bbox

    with dask.config.set(scheduler="synchronous"):
        scn = Scene(filenames=all_files, reader="ahi_hsd")
        scn.load(["B07", "B14"])

        # Crop to NSW bounding box before computing arrays
        scn = scn.crop(ll_bbox=(west, south, east, north))

        # Extract data arrays
        bt7 = scn["B07"].values.astype(np.float32)
        bt14 = scn["B14"].values.astype(np.float32)

        # Get lat/lon from cropped area definition
        area_def = scn["B07"].attrs["area"]
        lons, lats = area_def.get_lonlats()
        lats = lats.astype(np.float32)
        lons = lons.astype(np.float32)

        # Get observation time from metadata
        obs_time = scn["B07"].attrs.get("start_time", None)
        if obs_time is None:
            obs_time = scn["B07"].attrs.get("end_time", datetime.utcnow())

    logger.info(
        "Decoded: shape=%s, BT7 range=[%.1f, %.1f]K, obs_time=%s",
        bt7.shape,
        float(np.nanmin(bt7)),
        float(np.nanmax(bt7)),
        obs_time,
    )

    return {
        "bt7": bt7,
        "bt14": bt14,
        "lats": lats,
        "lons": lons,
        "obs_time": obs_time,
    }
