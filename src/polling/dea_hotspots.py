"""DEA Hotspots WFS client — polls Geoscience Australia's Digital Earth Australia hotspots service."""

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from ..config import settings
from ..models import Detection, Source

logger = logging.getLogger(__name__)

# DEA Hotspots WFS endpoint
DEA_WFS_URL = "https://hotspots.dea.ga.gov.au/geoserver/public/wfs"


def _make_source_id(satellite: str, lat: float, lon: float, acq_dt: str) -> str:
    raw = f"DEA|{satellite}|{lat}|{lon}|{acq_dt}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def poll_dea_hotspots() -> list[Detection]:
    """Fetch recent hotspots from DEA WFS for NSW bbox."""
    west, south, east, north = settings.nsw_bbox
    bbox_str = f"{south},{west},{north},{east},EPSG:4326"

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "public:hotspots_three_days",
        "outputFormat": "application/json",
        "bbox": bbox_str,
        "srsName": "EPSG:4326",
        "count": "5000",
    }

    detections = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(DEA_WFS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])
        logger.info("DEA Hotspots returned %d features", len(features))

        for feat in features:
            try:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [None, None])

                if coords[0] is None or coords[1] is None:
                    continue

                lon, lat = float(coords[0]), float(coords[1])

                # Parse datetime — DEA uses various formats
                dt_str = props.get("datetime") or props.get("start_dt") or props.get("ingestion_datetime")
                if not dt_str:
                    continue
                try:
                    acq_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    logger.warning("Could not parse datetime: %s", dt_str)
                    continue

                if acq_dt.tzinfo is None:
                    acq_dt = acq_dt.replace(tzinfo=timezone.utc)

                satellite = props.get("satellite", "UNKNOWN")
                instrument = props.get("instrument", "UNKNOWN")
                confidence_val = props.get("confidence", "nominal")
                # DEA uses numeric confidence 0-100 sometimes
                if isinstance(confidence_val, (int, float)):
                    if confidence_val >= 80:
                        confidence_val = "high"
                    elif confidence_val >= 30:
                        confidence_val = "nominal"
                    else:
                        confidence_val = "low"

                frp = props.get("power") or props.get("frp")
                if frp is not None:
                    frp = float(frp)

                brightness = props.get("temp_kelvin") or props.get("brightness")
                if brightness is not None:
                    brightness = float(brightness)

                source_id = _make_source_id(satellite, lat, lon, acq_dt.isoformat())

                detections.append(Detection(
                    source_id=source_id,
                    source=Source.DEA,
                    satellite=satellite,
                    instrument=instrument,
                    latitude=lat,
                    longitude=lon,
                    acq_datetime=acq_dt,
                    confidence=str(confidence_val),
                    frp=frp,
                    brightness=brightness,
                    daynight=props.get("daynight"),
                ))
            except Exception:
                logger.warning("Failed to parse DEA feature, skipping", exc_info=True)
                continue

    except httpx.HTTPStatusError as e:
        logger.error("DEA Hotspots HTTP error: %s", e)
    except httpx.RequestError as e:
        logger.error("DEA Hotspots request error: %s", e)
    except Exception:
        logger.exception("DEA Hotspots unexpected error")

    return detections
