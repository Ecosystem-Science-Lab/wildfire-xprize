# Code Patterns for Multi-Sensor Fire Detection Fusion

## 1. Complete Pipeline Orchestrator

```python
"""
Multi-sensor fire detection pipeline orchestrator.

Implements the Trigger -> Refine -> Confirm cascade with
event tracking and confidence aggregation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the multi-sensor fusion pipeline."""
    # Stage 1: Trigger
    ahi_scan_interval_min: int = 10
    ahi_anomaly_threshold_day_k: float = 360.0   # Absolute BT_3.9 threshold (daytime)
    ahi_anomaly_threshold_night_k: float = 320.0  # Absolute BT_3.9 threshold (nighttime)
    ahi_contextual_sigma: float = 3.5             # Sigma multiplier for contextual test
    ahi_btd_floor_k: float = 6.0                  # Minimum BTD anomaly above background
    glint_angle_threshold: float = 10.0           # Degrees -- block if below

    # Stage 2: Refine
    persistence_window_frames: int = 3             # Number of consecutive frames to check
    persistence_required_detections: int = 2       # Min detections in window
    max_persistence_gap_min: int = 30              # Max gap before resetting persistence

    # Stage 3: Confirm
    viirs_match_radius_km: float = 3.0             # Spatial match radius for VIIRS
    modis_match_radius_km: float = 5.0             # Spatial match radius for MODIS
    highres_match_radius_km: float = 1.5           # For Landsat/Sentinel-2
    cross_sensor_time_window_hours: float = 3.0    # Max time offset for matching
    firms_query_interval_min: int = 30             # How often to poll FIRMS

    # Event tracking
    event_spatial_radius_km: float = 5.0
    event_inactivity_timeout_hours: float = 120.0  # 5 days (FEDS standard)
    event_merge_overlap_ratio: float = 0.3

    # Confidence
    min_confidence_for_alert: float = 0.50         # Nominal tier threshold
    min_confidence_for_immediate_alert: float = 0.85  # High tier


class FusionPipeline:
    """Main orchestrator for the multi-sensor fire detection pipeline."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.event_store = FireEventStore(
            spatial_match_radius_km=config.event_spatial_radius_km,
            inactivity_timeout_hours=config.event_inactivity_timeout_hours,
            merge_overlap_threshold=config.event_merge_overlap_ratio,
        )
        self.persistence_trackers: dict[tuple, PersistenceTracker] = {}
        self.pixel_states: dict[tuple, PixelThermalState] = {}

        # Pre-loaded ancillary data
        self.sta_mask = None        # Static Thermal Anomaly mask (GeoDataFrame)
        self.land_cover = None      # Land cover raster
        self.volcano_db = None      # Volcano locations (GeoDataFrame)

    def process_ahi_frame(self, bt_mir, bt_tir, metadata):
        """Process a single AHI full-disk frame (Stage 1 + Stage 2).

        Args:
            bt_mir: 2D array, Band 7 brightness temperature (K)
            bt_tir: 2D array, Band 14 brightness temperature (K)
            metadata: dict with timestamp, solar_zenith_array, area_def, etc.

        Returns:
            list of candidate fire events (new or updated)
        """
        timestamp = metadata['timestamp']
        is_daytime = metadata.get('solar_zenith_array', None)
        candidates = []

        # Stage 1: Pixel-level anomaly detection
        cloud_mask = self._compute_cloud_mask(bt_mir, bt_tir, metadata)
        water_mask = metadata.get('water_mask', None)

        # Vectorized absolute threshold check (fast pre-filter)
        if is_daytime is not None:
            day_candidates = (bt_mir > self.config.ahi_anomaly_threshold_day_k) & is_daytime & ~cloud_mask
            night_candidates = (bt_mir > self.config.ahi_anomaly_threshold_night_k) & ~is_daytime & ~cloud_mask
            potential_fire = day_candidates | night_candidates
        else:
            potential_fire = (bt_mir > self.config.ahi_anomaly_threshold_night_k) & ~cloud_mask

        # Run contextual tests on potential fire pixels
        fire_pixels = []
        rows, cols = np.where(potential_fire)

        fire_mask = np.zeros_like(bt_mir, dtype=bool)
        for row, col in zip(rows, cols):
            if water_mask is not None and water_mask[row, col]:
                continue

            bg = compute_background_stats(row, col, bt_mir, bt_tir,
                                           cloud_mask,
                                           water_mask if water_mask is not None else np.zeros_like(cloud_mask),
                                           fire_mask)

            pixel_is_day = bool(is_daytime[row, col]) if is_daytime is not None else True
            glint_angle = metadata.get('glint_angle_array', np.full_like(bt_mir, 90.0))[row, col]

            result, confidence = contextual_fire_test(
                bt_mir[row, col], bt_tir[row, col], bg,
                pixel_is_day, 0.0, glint_angle
            )

            if result.startswith('FIRE'):
                fire_mask[row, col] = True
                lat, lon = self._pixel_to_latlon(row, col, metadata['area_def'])
                fire_pixels.append({
                    'row': row, 'col': col,
                    'lat': lat, 'lon': lon,
                    'bt_mir': float(bt_mir[row, col]),
                    'bt_tir': float(bt_tir[row, col]),
                    'btd': float(bt_mir[row, col] - bt_tir[row, col]),
                    'confidence': confidence,
                    'detection_type': result,
                    'is_daytime': pixel_is_day,
                })

        # Stage 2: Temporal persistence check
        for pixel in fire_pixels:
            key = (pixel['row'], pixel['col'])
            if key not in self.persistence_trackers:
                self.persistence_trackers[key] = PersistenceTracker(
                    pixel_key=key, detections=deque(maxlen=6)
                )

            tracker = self.persistence_trackers[key]
            tracker.add_frame(timestamp, True, pixel['confidence'],
                              pixel['bt_mir'], pixel['btd'])

            persistence_result, persistence_conf = tracker.evaluate_persistence(
                n_required=self.config.persistence_required_detections,
                window_frames=self.config.persistence_window_frames,
            )

            if persistence_result and persistence_result != 'NO_PERSISTENCE':
                # Build evidence list
                evidence = [self._anomaly_to_evidence(pixel)]
                evidence.append(self._persistence_to_evidence(persistence_result))
                evidence.extend(self._check_false_positive_indicators(pixel))

                # Create detection object
                detection = FireDetection(
                    sensor='AHI',
                    lat=pixel['lat'],
                    lon=pixel['lon'],
                    timestamp=timestamp,
                    brightness_mir=pixel['bt_mir'],
                    brightness_tir=pixel['bt_tir'],
                    btd=pixel['btd'],
                    frp=0.0,  # FRP not directly available from raw AHI
                    confidence=max(pixel['confidence'], persistence_conf),
                    confidence_label=self._confidence_to_label(
                        max(pixel['confidence'], persistence_conf)),
                    scan_size_m=2000,
                    track_size_m=2000,
                    day_night='D' if pixel['is_daytime'] else 'N',
                )

                # Ingest into event store
                event = self.event_store.ingest_detection(detection, evidence)
                candidates.append(event)

        # Update persistence trackers for non-fire pixels (mark as non-detection)
        for key, tracker in self.persistence_trackers.items():
            if key not in [(p['row'], p['col']) for p in fire_pixels]:
                tracker.add_frame(timestamp, False, 0.0, 0.0, 0.0)

        # Expire old events
        self.event_store.expire_inactive(timestamp)

        return candidates

    def process_firms_data(self, firms_df, timestamp):
        """Process FIRMS NRT data for cross-sensor confirmation (Stage 3).

        Args:
            firms_df: DataFrame from FIRMS API query
            timestamp: current processing time

        Returns:
            list of events that were confirmed or updated
        """
        confirmed_events = []

        for _, row in firms_df.iterrows():
            detection = self._firms_row_to_detection(row)

            # Check against existing events
            matching_events = self.event_store._spatial_search(
                detection.lat, detection.lon,
                self.config.viirs_match_radius_km
            )

            if matching_events:
                for event in matching_events:
                    evidence = self._firms_detection_evidence(row)
                    event.add_detection(detection)
                    self.event_store._update_state(event, evidence)
                    confirmed_events.append(event)
            else:
                # New detection from FIRMS with no AHI trigger
                # This can happen if the fire is too small for AHI
                evidence = self._firms_detection_evidence(row)
                event = self.event_store.ingest_detection(detection, evidence)
                confirmed_events.append(event)

        return confirmed_events

    def get_alerts(self):
        """Return events that meet the alerting threshold."""
        alerts = []
        for event in self.event_store.events.values():
            if event.state == EventState.REJECTED:
                continue
            if event.combined_confidence >= self.config.min_confidence_for_alert:
                alerts.append({
                    'event_id': event.event_id,
                    'state': event.state.value,
                    'confidence': event.combined_confidence,
                    'tier': event.confidence_tier,
                    'lat': event.centroid_lat,
                    'lon': event.centroid_lon,
                    'area_km2': event.area_km2,
                    'first_detected': event.first_detected,
                    'last_detected': event.last_detected,
                    'sensors': list(event.confirming_sensors),
                    'frp_trend': event.frp_trend,
                    'immediate': event.combined_confidence >= self.config.min_confidence_for_immediate_alert,
                })
        return sorted(alerts, key=lambda a: a['confidence'], reverse=True)

    # --- Helper methods ---

    def _anomaly_to_evidence(self, pixel):
        if pixel['bt_mir'] > 360:
            return 'ahi_strong_anomaly'
        elif pixel['confidence'] > 0.5:
            return 'ahi_moderate_anomaly'
        return 'ahi_weak_anomaly'

    def _persistence_to_evidence(self, result):
        mapping = {
            'PERSISTENT_GROWING': 'persistent_growing',
            'PERSISTENT_STABLE': 'persistent_3_of_3',
            'PERSISTENT': 'persistent_2_of_3',
            'TRANSIENT': 'transient_1_of_3',
        }
        return mapping.get(result, 'persistent_2_of_3')

    def _check_false_positive_indicators(self, pixel):
        """Check ancillary data for false positive indicators."""
        indicators = []

        if self.sta_mask is not None:
            if check_against_sta(pixel['lat'], pixel['lon'], self.sta_mask):
                indicators.append('known_industrial')

        # Add land cover checks, volcano checks, etc.
        return indicators

    def _confidence_to_label(self, conf):
        if conf >= 0.80:
            return 'high'
        elif conf >= 0.30:
            return 'nominal'
        return 'low'

    def _firms_row_to_detection(self, row):
        """Convert a FIRMS DataFrame row to a FireDetection."""
        sensor_map = {
            'N': 'VIIRS_SNPP', 'N20': 'VIIRS_N20', 'N21': 'VIIRS_N21',
            'T': 'MODIS_TERRA', 'A': 'MODIS_AQUA',
        }
        sensor = sensor_map.get(row.get('satellite', ''), 'UNKNOWN')

        # Handle VIIRS vs MODIS confidence field differences
        if isinstance(row.get('confidence'), str):
            # VIIRS: low/nominal/high
            conf_map = {'low': 0.20, 'nominal': 0.60, 'high': 0.90}
            confidence = conf_map.get(row['confidence'], 0.5)
            confidence_label = row['confidence']
        else:
            # MODIS: 0-100 numeric
            confidence = row.get('confidence', 50) / 100.0
            if confidence >= 0.80:
                confidence_label = 'high'
            elif confidence >= 0.30:
                confidence_label = 'nominal'
            else:
                confidence_label = 'low'

        # Parse timestamp
        acq_date = str(row.get('acq_date', ''))
        acq_time = str(row.get('acq_time', '0000')).zfill(4)
        try:
            ts = datetime.strptime(f"{acq_date} {acq_time}", "%Y-%m-%d %H%M")
        except ValueError:
            ts = datetime.utcnow()

        # Brightness temperature fields differ by sensor
        bt_mir = row.get('bright_ti4', row.get('brightness', 0.0))
        bt_tir = row.get('bright_ti5', row.get('bright_t31', 0.0))

        return FireDetection(
            sensor=sensor,
            lat=row['latitude'],
            lon=row['longitude'],
            timestamp=ts,
            brightness_mir=float(bt_mir),
            brightness_tir=float(bt_tir),
            btd=float(bt_mir) - float(bt_tir) if bt_tir else 0.0,
            frp=float(row.get('frp', 0.0)),
            confidence=confidence,
            confidence_label=confidence_label,
            scan_size_m=float(row.get('scan', 375)),
            track_size_m=float(row.get('track', 375)),
            day_night=row.get('daynight', 'D'),
        )

    def _firms_detection_evidence(self, row):
        """Generate evidence list from a FIRMS detection."""
        evidence = []
        conf = row.get('confidence', 'nominal')
        if isinstance(conf, str):
            evidence.append(f'viirs_{conf}')
        else:
            if conf >= 80:
                evidence.append('viirs_high_confidence')
            elif conf >= 30:
                evidence.append('viirs_nominal')
            else:
                evidence.append('viirs_low')
        evidence.append('firms_nrt_match')
        return evidence

    def _pixel_to_latlon(self, row, col, area_def):
        """Convert pixel coordinates to lat/lon using pyresample area definition."""
        # area_def is a pyresample AreaDefinition
        lon, lat = area_def.get_lonlat_from_array_coordinates(col, row)
        return float(lat), float(lon)

    def _compute_cloud_mask(self, bt_mir, bt_tir, metadata):
        """Simple cloud mask from brightness temperatures."""
        ref_vis = metadata.get('ref_vis', None)

        # TIR-based cloud test (always available)
        cloud = bt_tir < 265.0

        # Combined visible + TIR test (daytime only)
        if ref_vis is not None:
            cloud |= ((ref_vis > 0.4) & (bt_tir < 295.0))

        return cloud
```

## 2. Spatial Matching with GeoPandas

```python
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd

def create_detection_geodataframe(detections: list[dict]) -> gpd.GeoDataFrame:
    """Convert detection dicts to a GeoDataFrame with uncertainty buffers.

    Each detection gets:
      - point geometry (center)
      - buffer geometry (uncertainty footprint)
    """
    records = []
    for det in detections:
        point = Point(det['lon'], det['lat'])

        # Compute buffer size based on sensor
        sensor = det.get('sensor', 'UNKNOWN')
        params = SENSOR_UNCERTAINTIES.get(sensor, SENSOR_UNCERTAINTIES.get('VIIRS_I'))
        scan_m = det.get('scan_size_m', params['scan_size_nadir'])
        track_m = det.get('track_size_m', params['track_size_nadir'])
        geoloc_err = params['geoloc_error']

        uncertainty_m = np.sqrt((max(scan_m, track_m) / 2) ** 2 + geoloc_err ** 2)
        buffer_deg = uncertainty_m / 111_000  # Approximate

        records.append({
            'geometry': point,
            'buffer_geometry': point.buffer(buffer_deg),
            'uncertainty_m': uncertainty_m,
            **det,
        })

    gdf = gpd.GeoDataFrame(records, crs='EPSG:4326')
    return gdf


def spatial_join_cross_sensor(trigger_gdf: gpd.GeoDataFrame,
                                confirm_gdf: gpd.GeoDataFrame,
                                max_time_offset_hours: float = 3.0) -> gpd.GeoDataFrame:
    """Join trigger detections with confirming detections using spatial overlap.

    Uses buffer geometries for resolution-aware matching.
    """
    # Set buffer geometry as active geometry for the join
    trigger_buffered = trigger_gdf.set_geometry('buffer_geometry')
    confirm_buffered = confirm_gdf.set_geometry('buffer_geometry')

    # Spatial join: find all pairs where buffers intersect
    joined = gpd.sjoin(trigger_buffered, confirm_buffered,
                       how='left', predicate='intersects',
                       lsuffix='trigger', rsuffix='confirm')

    # Filter by temporal proximity
    if 'timestamp_trigger' in joined.columns and 'timestamp_confirm' in joined.columns:
        joined['time_offset_h'] = (
            (joined['timestamp_trigger'] - joined['timestamp_confirm'])
            .abs()
            .dt.total_seconds() / 3600
        )
        joined = joined[joined['time_offset_h'] <= max_time_offset_hours]

    return joined
```

## 3. FIRMS Polling Service

```python
import asyncio
import aiohttp

class FIRMSPoller:
    """Periodically poll FIRMS API for new fire detections."""

    def __init__(self, map_key: str, bbox: tuple,
                 poll_interval_min: int = 30,
                 sources: list[str] = None):
        self.map_key = map_key
        self.bbox = bbox  # (west, south, east, north)
        self.poll_interval_sec = poll_interval_min * 60
        self.sources = sources or [
            'VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'VIIRS_NOAA21_NRT', 'MODIS_NRT'
        ]
        self.last_seen_detections: set = set()  # (lat, lon, acq_date, acq_time) tuples
        self._callbacks = []

    def on_new_detections(self, callback):
        """Register a callback for new detections."""
        self._callbacks.append(callback)

    async def run(self):
        """Main polling loop."""
        while True:
            try:
                new_detections = await self._poll_once()
                if new_detections is not None and len(new_detections) > 0:
                    for callback in self._callbacks:
                        await callback(new_detections)
            except Exception as e:
                logger.error(f"FIRMS poll error: {e}")

            await asyncio.sleep(self.poll_interval_sec)

    async def _poll_once(self) -> pd.DataFrame:
        """Single poll iteration."""
        all_new = []

        async with aiohttp.ClientSession() as session:
            for source in self.sources:
                w, s, e, n = self.bbox
                url = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
                       f"{self.map_key}/{source}/{w},{s},{e},{n}/1")

                async with session.get(url) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if text.strip():
                            from io import StringIO
                            df = pd.read_csv(StringIO(text))
                            df['source'] = source

                            # Deduplicate against previously seen detections
                            new_mask = ~df.apply(
                                lambda r: (r['latitude'], r['longitude'],
                                           r.get('acq_date', ''), r.get('acq_time', ''))
                                          in self.last_seen_detections,
                                axis=1
                            )
                            new_df = df[new_mask]

                            # Update seen set
                            for _, r in new_df.iterrows():
                                self.last_seen_detections.add(
                                    (r['latitude'], r['longitude'],
                                     r.get('acq_date', ''), r.get('acq_time', ''))
                                )

                            all_new.append(new_df)
                    else:
                        logger.warning(f"FIRMS {source} returned {resp.status}")

        return pd.concat(all_new, ignore_index=True) if all_new else None
```

## 4. False Positive Filter Chain

```python
class FalsePositiveFilterChain:
    """Chain of filters to reject false positive fire detections."""

    def __init__(self):
        self.filters: list[callable] = []

    def add_filter(self, filter_fn):
        """Register a filter. Returns (keep: bool, reason: str)."""
        self.filters.append(filter_fn)

    def apply(self, detection: FireDetection, context: dict) -> tuple[bool, list[str]]:
        """Apply all filters. Return (keep, list_of_rejection_reasons)."""
        rejections = []
        for filter_fn in self.filters:
            keep, reason = filter_fn(detection, context)
            if not keep:
                rejections.append(reason)
        # Detection passes if no filter rejected it
        return len(rejections) == 0, rejections


def sun_glint_filter(detection: FireDetection, context: dict) -> tuple[bool, str]:
    """Reject daytime detections in sun glint geometry."""
    if detection.day_night == 'N':
        return True, ''
    glint_angle = context.get('glint_angle', 90.0)
    if glint_angle < 10.0:
        return False, f'sun_glint (angle={glint_angle:.1f})'
    return True, ''


def static_anomaly_filter(detection: FireDetection, context: dict) -> tuple[bool, str]:
    """Reject detections matching known industrial/volcanic heat sources."""
    sta_mask = context.get('sta_mask')
    if sta_mask is None:
        return True, ''
    if check_against_sta(detection.lat, detection.lon, sta_mask):
        return False, 'static_thermal_anomaly'
    return True, ''


def temporal_transience_filter(detection: FireDetection, context: dict) -> tuple[bool, str]:
    """Reject single-frame detections without persistence."""
    persistence_result = context.get('persistence_result', 'UNKNOWN')
    if persistence_result == 'TRANSIENT':
        return False, 'transient_detection (1 of 3 frames)'
    return True, ''


def land_cover_filter(detection: FireDetection, context: dict) -> tuple[bool, str]:
    """Flag detections over non-vegetated surfaces."""
    land_cover_class = context.get('land_cover_class', -1)
    # WorldCover classes where fire is unlikely:
    non_fire_classes = {
        50: 'built_up',
        60: 'bare_sparse_vegetation',
        70: 'snow_ice',
        80: 'permanent_water',
        90: 'herbaceous_wetland',
        100: 'moss_lichen',
    }
    if land_cover_class in non_fire_classes:
        # Don't reject outright but flag for reduced confidence
        # Only reject for water/ice
        if land_cover_class in (70, 80):
            return False, f'non_fire_surface ({non_fire_classes[land_cover_class]})'
    return True, ''


def desert_daytime_filter(detection: FireDetection, context: dict) -> tuple[bool, str]:
    """Apply stricter thresholds for daytime detections in arid areas."""
    if detection.day_night == 'N':
        return True, ''
    land_cover_class = context.get('land_cover_class', -1)
    if land_cover_class == 60:  # Bare/sparse vegetation
        # Require stronger BTD for arid daytime
        if detection.btd < 15.0:  # Normal fires produce BTD >> 15K
            return False, f'desert_daytime (BTD={detection.btd:.1f}K too low)'
    return True, ''


# Assemble filter chain
def build_filter_chain() -> FalsePositiveFilterChain:
    chain = FalsePositiveFilterChain()
    chain.add_filter(sun_glint_filter)
    chain.add_filter(static_anomaly_filter)
    chain.add_filter(temporal_transience_filter)
    chain.add_filter(land_cover_filter)
    chain.add_filter(desert_daytime_filter)
    return chain
```

## 5. Alert Output Format

```python
from dataclasses import dataclass, asdict
import json

@dataclass
class FireAlert:
    """Structured fire alert for downstream consumers."""
    event_id: str
    alert_time: str          # ISO 8601
    confidence: float        # 0-1
    confidence_tier: str     # 'high', 'nominal', 'low'

    # Location
    latitude: float
    longitude: float
    area_km2: float
    geometry_wkt: str        # Well-Known Text of fire perimeter

    # Timing
    first_detected: str      # ISO 8601
    last_detected: str
    duration_minutes: float

    # Intensity
    peak_frp_mw: float
    current_frp_mw: float
    frp_trend: str           # 'increasing', 'stable', 'decreasing'

    # Evidence
    confirming_sensors: list[str]
    n_detections: int
    event_state: str

    def to_json(self):
        return json.dumps(asdict(self), indent=2)

    def to_geojson_feature(self):
        """Convert to GeoJSON Feature for map display."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": {
                k: v for k, v in asdict(self).items()
                if k not in ('latitude', 'longitude', 'geometry_wkt')
            }
        }
```

## 6. Confidence Calibration Helper

```python
class ConfidenceCalibrator:
    """Track prediction vs outcome to calibrate confidence scores.

    After deployment, use verified fire reports to adjust LLR values.
    """

    def __init__(self):
        self.predictions: list[tuple[float, bool]] = []  # (confidence, was_real_fire)

    def record(self, confidence: float, verified_fire: bool):
        self.predictions.append((confidence, verified_fire))

    def compute_calibration_curve(self, n_bins=10):
        """Compute reliability diagram data."""
        if not self.predictions:
            return []

        predictions = sorted(self.predictions, key=lambda x: x[0])
        bin_size = len(predictions) // n_bins

        bins = []
        for i in range(0, len(predictions), max(bin_size, 1)):
            batch = predictions[i:i + bin_size]
            if not batch:
                continue
            mean_predicted = sum(c for c, _ in batch) / len(batch)
            fraction_positive = sum(1 for _, v in batch if v) / len(batch)
            bins.append({
                'predicted_confidence': mean_predicted,
                'observed_frequency': fraction_positive,
                'n_samples': len(batch),
            })

        return bins

    def compute_false_positive_rate(self, threshold=0.50):
        """FP rate at a given confidence threshold."""
        above_threshold = [(c, v) for c, v in self.predictions if c >= threshold]
        if not above_threshold:
            return 0.0
        fp = sum(1 for _, v in above_threshold if not v)
        return fp / len(above_threshold)

    def suggest_threshold_for_fpr(self, target_fpr=0.05):
        """Find confidence threshold that achieves target false positive rate."""
        for threshold in np.arange(0.0, 1.01, 0.01):
            fpr = self.compute_false_positive_rate(threshold)
            if fpr <= target_fpr:
                return threshold
        return 1.0  # Cannot achieve target
```
