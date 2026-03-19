"""Spatial and cloud masking for Himawari AHI data."""

from __future__ import annotations

import logging

import numpy as np
from scipy.ndimage import binary_dilation

from ..config import settings

logger = logging.getLogger(__name__)

# Cache masks by grid shape (geostationary grid is fixed)
_nsw_mask_cache: dict[tuple[int, int], np.ndarray] = {}


def compute_nsw_mask(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Compute boolean mask for pixels within NSW bounding box.

    Returns:
        Boolean array — True = within NSW bbox.
    """
    shape = lats.shape
    if shape in _nsw_mask_cache:
        return _nsw_mask_cache[shape]

    west, south, east, north = settings.nsw_bbox
    mask = (
        (lats >= south)
        & (lats <= north)
        & (lons >= west)
        & (lons <= east)
        & np.isfinite(lats)
        & np.isfinite(lons)
    )

    _nsw_mask_cache[shape] = mask
    n_pixels = int(np.sum(mask))
    logger.info("NSW mask: %d pixels of %d total", n_pixels, mask.size)
    return mask


def compute_cloud_mask(bt14: np.ndarray, threshold: float = 265.0) -> np.ndarray:
    """Compute cloud mask from Band 14 brightness temperatures.

    Returns:
        Boolean array — True = cloud pixel.
    """
    return bt14 < threshold


def compute_cloud_adjacency(cloud_mask: np.ndarray, buffer: int = 2) -> np.ndarray:
    """Dilate cloud mask to create adjacency buffer.

    Returns:
        Boolean array — True = cloud or cloud-adjacent pixel.
    """
    struct = np.ones((2 * buffer + 1, 2 * buffer + 1), dtype=bool)
    return binary_dilation(cloud_mask, structure=struct)
