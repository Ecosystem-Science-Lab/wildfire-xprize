"""Static masks for water bodies and industrial heat sources in NSW.

Water mask: hybrid of global-land-mask (1km ocean) + GSHHS (3km inland water).
Industrial mask: 24 known thermal hotspot sites with 4km buffer radius.

Both are computed once from lat/lon arrays and cached per grid shape.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Cache by grid shape
_water_mask_cache: dict[tuple[int, int], np.ndarray] = {}
_industrial_mask_cache: dict[tuple[int, int], np.ndarray] = {}

# GSHHS land/water mask GeoTIFF (used by satpy/pytroll for AHI composites)
_GSHHS_PATH = Path(__file__).parent.parent.parent / "data" / "gshhs_land_water_mask_3km_i.tif"


def compute_water_mask(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Compute water mask using hybrid ocean + inland water approach.

    - Ocean: global-land-mask at ~1km resolution (precise coastline)
    - Inland water: GSHHS GeoTIFF at ~3km resolution (lakes, reservoirs)
    - Combined: ocean OR (GSHHS-water AND NOT ocean) → catches inland water

    Returns boolean array — True = water pixel.
    """
    shape = lats.shape
    if shape in _water_mask_cache:
        return _water_mask_cache[shape]

    # 1. Ocean from global-land-mask (1km, fast vectorized)
    from global_land_mask import globe
    ocean = globe.is_ocean(lats, lons)
    n_ocean = int(np.sum(ocean))

    # 2. Inland water from GSHHS GeoTIFF
    n_inland = 0
    inland_water = np.zeros(shape, dtype=bool)

    if _GSHHS_PATH.exists():
        try:
            import rasterio

            with rasterio.open(str(_GSHHS_PATH)) as src:
                data = src.read(1)  # 0=water, 100=land
                inv = ~src.transform

                cols, rows = inv * (
                    lons.ravel().astype(np.float64),
                    lats.ravel().astype(np.float64),
                )
                rows = np.clip(np.round(rows).astype(int), 0, data.shape[0] - 1)
                cols = np.clip(np.round(cols).astype(int), 0, data.shape[1] - 1)

                gshhs_water = (data[rows, cols] == 0).reshape(shape)

            # Inland water = GSHHS says water, but globe says land
            inland_water = gshhs_water & (~ocean)
            n_inland = int(np.sum(inland_water))
        except Exception:
            logger.warning("Failed to load GSHHS mask from %s", _GSHHS_PATH, exc_info=True)
    else:
        logger.warning(
            "GSHHS mask not found at %s — inland water bodies won't be masked. "
            "Download from https://zenodo.org/records/10076199/files/gshhs_land_water_mask_3km_i.tif",
            _GSHHS_PATH,
        )

    water = ocean | inland_water

    logger.info(
        "Water mask: %d pixels (%d ocean, %d inland) of %d total",
        int(np.sum(water)), n_ocean, n_inland, water.size,
    )

    _water_mask_cache[shape] = water
    return water


# --- Known industrial heat sources in NSW ---
# Sources: Wikipedia List of power stations in NSW, Global Energy Monitor,
# DEA Hotspots persistent anomaly data, FIRMS static thermal anomalies.
# Each entry: (name, lat, lon, type)
INDUSTRIAL_SITES = [
    # Tier 1 — Almost certain to trigger at 2km (coal power, steelworks, smelter)
    ("Bayswater Power Station", -32.3958, 150.9492, "coal_power"),
    ("Eraring Power Station", -33.0617, 151.5198, "coal_power"),
    ("Vales Point Power Station", -33.16, 151.5446, "coal_power"),
    ("Mount Piper Power Station", -33.3586, 150.0316, "coal_power"),
    ("BlueScope Port Kembla Steelworks", -34.4638, 150.8862, "steelworks"),
    ("Tallawarra Power Station", -34.5226, 150.8071, "gas_power"),
    ("Tomago Aluminium Smelter", -32.8248, 151.7245, "smelter"),
    # Tier 2 — Intermittent triggers (gas peakers, chemical plants, EAF)
    ("Colongra Power Station", -33.21, 151.5448, "gas_power"),
    ("Uranquinty Power Station", -35.1802, 147.2157, "gas_power"),
    ("Kurri Kurri Power Station", -32.8174, 151.4830, "gas_power"),
    ("Smithfield Energy Facility", -33.85, 150.9495, "gas_power"),
    ("Orica Kooragang Island", -32.868, 151.774, "chemical"),
    ("InfraBuild Rooty Hill", -33.766, 150.8498, "steelworks"),
    # Tier 3 — Unlikely at 2km but documented in fire products
    ("Boral Berrima Cement Works", -34.5099, 150.3365, "cement"),
    ("Shoalhaven Starches Cogen", -34.8497, 150.6109, "industrial"),
    ("Mt Arthur Coal Mine", -32.3339, 150.8526, "coal_mine"),
    ("Hunter Valley Operations Mine", -32.5237, 151.0066, "coal_mine"),
    ("Mt Thorley-Warkworth Mine", -32.607, 151.090, "coal_mine"),
    ("Bulga Coal Mine", -32.6835, 151.0827, "coal_mine"),
    ("Liddell Power Station (closed)", -32.3715, 150.978, "decommissioned"),
    # Far north NSW sugar mills (seasonal Jun-Dec)
    ("Condong Sugar Mill", -28.3141, 153.4388, "sugar_mill"),
    ("Broadwater Sugar Mill", -29.017, 153.433, "sugar_mill"),
    ("Harwood Sugar Mill", -29.4259, 153.2478, "sugar_mill"),
]

INDUSTRIAL_BUFFER_KM = 4.0


def compute_industrial_mask(
    lats: np.ndarray, lons: np.ndarray, buffer_km: float = INDUSTRIAL_BUFFER_KM
) -> np.ndarray:
    """Compute mask of known industrial heat source locations.

    Returns boolean array — True = within buffer of industrial site.
    Industrial detections are not hard-rejected but confidence-downgraded.
    """
    shape = lats.shape
    if shape in _industrial_mask_cache:
        return _industrial_mask_cache[shape]

    industrial = np.zeros(shape, dtype=bool)

    for name, slat, slon, stype in INDUSTRIAL_SITES:
        cos_lat = math.cos(math.radians(slat))
        dlat_deg = buffer_km / 111.0
        dlon_deg = buffer_km / (111.0 * cos_lat)
        near = (
            ((lats - slat) / dlat_deg) ** 2
            + ((lons - slon) / dlon_deg) ** 2
        ) <= 1.0
        industrial |= near

    n_industrial = int(np.sum(industrial))
    logger.info("Industrial mask: %d pixels near %d sites", n_industrial, len(INDUSTRIAL_SITES))

    _industrial_mask_cache[shape] = industrial
    return industrial
