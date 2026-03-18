# Multi-Sensor Fusion Algorithms

## 1. Temporal Filtering

### 1.1 Per-Pixel Diurnal Baseline (Contextual Approach)

The contextual approach compares a candidate pixel to its neighbors in the same image frame. This is the foundation of MOD14, VNP14IMG, and ABI FDC algorithms.

**Background characterization:**

For each candidate fire pixel, sample an expanding window of neighboring pixels (starting at 3x3, expanding to 21x21 if needed) to compute background statistics:

```python
# Background pixel selection criteria:
# - Not cloud-masked
# - Not water-masked
# - Not already flagged as a potential fire
# - BT_3.9 valid (not saturated, not missing)

def compute_background_stats(candidate_row, candidate_col, bt_mir, bt_tir,
                              cloud_mask, water_mask, fire_mask):
    """Expanding window background characterization."""
    btd = bt_mir - bt_tir

    for window_size in [3, 5, 7, 9, 11, 13, 15, 17, 19, 21]:
        half = window_size // 2
        r0 = max(0, candidate_row - half)
        r1 = min(bt_mir.shape[0], candidate_row + half + 1)
        c0 = max(0, candidate_col - half)
        c1 = min(bt_mir.shape[1], candidate_col + half + 1)

        valid = (
            ~cloud_mask[r0:r1, c0:c1] &
            ~water_mask[r0:r1, c0:c1] &
            ~fire_mask[r0:r1, c0:c1] &
            (bt_mir[r0:r1, c0:c1] > 0)  # valid data
        )

        n_valid = valid.sum()
        # Need at least 25% of window pixels to be valid background
        min_valid = int(0.25 * window_size * window_size)

        if n_valid >= max(min_valid, 8):
            bg_mir = bt_mir[r0:r1, c0:c1][valid]
            bg_tir = bt_tir[r0:r1, c0:c1][valid]
            bg_btd = btd[r0:r1, c0:c1][valid]

            return {
                'bt_mir_mean': bg_mir.mean(),
                'bt_mir_std': bg_mir.std(),
                'bt_tir_mean': bg_tir.mean(),
                'bt_tir_std': bg_tir.std(),
                'btd_mean': bg_btd.mean(),
                'btd_std': bg_btd.std(),
                'bt_mir_mad': np.median(np.abs(bg_mir - np.median(bg_mir))),
                'n_valid': n_valid,
                'window_size': window_size,
            }

    return None  # insufficient background -- flag pixel as unprocessable
```

**Fire detection tests (adapted from MOD14/VNP14IMG):**

```python
def contextual_fire_test(pixel_bt_mir, pixel_bt_tir, bg_stats,
                          is_daytime, solar_zenith, glint_angle):
    """Multi-condition contextual fire detection."""
    btd = pixel_bt_mir - pixel_bt_tir

    # Sun glint screening
    if is_daytime and glint_angle < 10.0:
        return 'GLINT_BLOCKED', 0.0

    # Absolute thresholds (high-confidence fires)
    if not is_daytime and pixel_bt_mir > 320.0:  # Nighttime, strong MIR
        return 'FIRE_ABSOLUTE', 0.95
    if pixel_bt_mir > 367.0:  # Saturated MIR (day or night)
        return 'FIRE_SATURATED', 0.99
    if is_daytime and pixel_bt_mir > 360.0:  # Daytime strong MIR
        return 'FIRE_ABSOLUTE', 0.90

    if bg_stats is None:
        return 'INSUFFICIENT_BG', 0.0

    # Contextual tests -- ALL must pass
    tests_passed = 0
    total_tests = 4

    # Test 1: MIR exceeds background + 3.5 sigma
    if pixel_bt_mir > bg_stats['bt_mir_mean'] + 3.5 * bg_stats['bt_mir_std']:
        tests_passed += 1

    # Test 2: BTD exceeds background + 3.5 sigma
    if btd > bg_stats['btd_mean'] + 3.5 * bg_stats['btd_std']:
        tests_passed += 1

    # Test 3: BTD exceeds background + 6K (absolute floor)
    if btd > bg_stats['btd_mean'] + 6.0:
        tests_passed += 1

    # Test 4: MIR MAD exceeds 5K (variability check)
    if bg_stats['bt_mir_mad'] > 5.0:
        tests_passed += 1

    if tests_passed >= 3:  # Require 3 of 4 tests
        confidence = 0.3 + 0.2 * (tests_passed / total_tests)
        # Boost confidence for strong anomalies
        mir_deviation = (pixel_bt_mir - bg_stats['bt_mir_mean']) / max(bg_stats['bt_mir_std'], 1.0)
        if mir_deviation > 6.0:
            confidence = min(confidence + 0.2, 0.85)
        return 'FIRE_CONTEXTUAL', confidence

    return 'NO_FIRE', 0.0
```

### 1.2 Multi-Temporal Baseline (Kalman Filter Approach)

For geostationary data with 10-min cadence, model the expected diurnal temperature cycle (DTC) per pixel and detect deviations.

**State vector:** For each pixel, maintain a state estimate of the expected BT_3.9 and its rate of change:

```python
@dataclass
class PixelThermalState:
    """Per-pixel Kalman filter state for diurnal cycle tracking."""
    row: int
    col: int

    # State vector: [BT_predicted, dBT/dt]
    x: np.ndarray  # shape (2,)  [K, K/hour]
    P: np.ndarray  # shape (2,2) covariance matrix

    # History for diurnal model fitting
    bt_history: deque  # (timestamp, bt_value) pairs, last 24-48 hours

    # Diurnal model parameters (fitted from history)
    dtc_amplitude: float = 0.0  # K
    dtc_phase: float = 12.0     # hour of peak (local solar time)
    dtc_offset: float = 280.0   # K, baseline temperature

    last_update: datetime = None
    n_observations: int = 0
    consecutive_anomalies: int = 0

def kalman_predict(state: PixelThermalState, dt_hours: float):
    """Predict next BT based on diurnal model + Kalman state."""
    # State transition: BT evolves linearly between updates
    F = np.array([[1.0, dt_hours],
                  [0.0, 1.0]])

    # Process noise: temperature can change due to weather, clouds clearing, etc.
    q_bt = 2.0    # K^2/hour -- uncertainty in BT prediction
    q_rate = 0.5  # (K/hour)^2 -- uncertainty in rate of change
    Q = np.array([[q_bt * dt_hours, 0],
                  [0, q_rate * dt_hours]])

    state.x = F @ state.x
    state.P = F @ state.P @ F.T + Q

def kalman_update(state: PixelThermalState, bt_observed: float,
                  observation_noise: float = 1.5):
    """Update state with new observation. Return innovation (anomaly magnitude)."""
    H = np.array([[1.0, 0.0]])  # We observe BT directly
    R = observation_noise ** 2   # Observation noise variance

    # Innovation (difference between observed and predicted)
    innovation = bt_observed - H @ state.x

    # Innovation covariance
    S = H @ state.P @ H.T + R

    # Kalman gain
    K = state.P @ H.T / S

    # Only update if NOT a fire (to avoid corrupting the baseline)
    anomaly_sigma = abs(innovation) / np.sqrt(S)

    if anomaly_sigma < 3.0:  # Normal observation -- update state
        state.x = state.x + K.flatten() * innovation
        state.P = (np.eye(2) - K @ H) @ state.P
        state.consecutive_anomalies = 0
    else:
        state.consecutive_anomalies += 1

    state.n_observations += 1
    state.last_update = datetime.utcnow()

    return float(innovation), float(anomaly_sigma)
```

**Fire detection from Kalman innovations:**

```python
def temporal_fire_test(state: PixelThermalState, bt_observed: float,
                       btd_observed: float, btd_baseline: float):
    """Detect fire as significant positive deviation from predicted DTC."""
    innovation, anomaly_sigma = kalman_update(state, bt_observed)

    # Primary test: BT significantly above predicted baseline
    if innovation > 0 and anomaly_sigma > 4.0:
        # Additional check: BTD also anomalous
        btd_anomaly = btd_observed - btd_baseline
        if btd_anomaly > 5.0:  # BTD at least 5K above baseline
            confidence = min(0.3 + 0.1 * (anomaly_sigma - 4.0), 0.80)
            return 'FIRE_TEMPORAL', confidence, anomaly_sigma

    # Persistence boost: consecutive anomalies across frames
    if state.consecutive_anomalies >= 2:
        if innovation > 0 and anomaly_sigma > 3.0:
            return 'FIRE_PERSISTENT', 0.60, anomaly_sigma

    return 'NO_FIRE', 0.0, anomaly_sigma
```

### 1.3 Frame-to-Frame Persistence Filter

For geostationary data, check detection consistency across consecutive 10-min scans:

```python
@dataclass
class PersistenceTracker:
    """Track detection consistency across consecutive geostationary frames."""
    pixel_key: tuple  # (row, col)
    detections: deque  # (timestamp, confidence, bt_mir, btd) -- maxlen=6 (1 hour)

    def add_frame(self, timestamp, detected: bool, confidence: float,
                  bt_mir: float, btd: float):
        self.detections.append((timestamp, detected, confidence, bt_mir, btd))

    def evaluate_persistence(self, n_required: int = 2, window_frames: int = 3):
        """Check if detection persists across recent frames.

        Default: require 2 detections in 3 consecutive frames (20-30 min).
        """
        recent = list(self.detections)[-window_frames:]
        if len(recent) < window_frames:
            return None, 0.0  # insufficient frames

        n_detected = sum(1 for _, det, _, _, _ in recent if det)

        if n_detected >= n_required:
            # Check intensity trend
            bt_values = [bt for _, det, _, bt, _ in recent if det]
            if len(bt_values) >= 2:
                trend = bt_values[-1] - bt_values[0]  # positive = intensifying
                if trend > 0:
                    return 'PERSISTENT_GROWING', 0.75
                else:
                    return 'PERSISTENT_STABLE', 0.65
            return 'PERSISTENT', 0.60

        elif n_detected == 1 and window_frames >= 3:
            # Single detection in window -- could be transient
            return 'TRANSIENT', 0.20

        return 'NO_PERSISTENCE', 0.0
```

## 2. Spatial Matching Across Sensors

### 2.1 Resolution-Aware Uncertainty Model

Each sensor detection has an uncertainty footprint that depends on pixel size and scan angle:

```python
@dataclass
class DetectionUncertainty:
    """Model the spatial uncertainty of a fire detection."""
    center_lat: float
    center_lon: float

    # Pixel footprint (meters)
    scan_size: float   # along-scan dimension
    track_size: float  # along-track dimension

    # Geolocation error (meters, 1-sigma)
    geoloc_error: float

    # Scan angle (degrees from nadir)
    scan_angle: float

    @property
    def uncertainty_radius_m(self):
        """Combined uncertainty as circular radius (conservative)."""
        pixel_radius = max(self.scan_size, self.track_size) / 2.0
        return np.sqrt(pixel_radius**2 + self.geoloc_error**2)

    def to_buffer_degrees(self):
        """Convert uncertainty radius to approximate degrees for buffering."""
        # 1 degree latitude ~ 111 km
        # 1 degree longitude ~ 111 km * cos(lat)
        r_m = self.uncertainty_radius_m
        lat_deg = r_m / 111_000
        lon_deg = r_m / (111_000 * np.cos(np.radians(self.center_lat)))
        return lat_deg, lon_deg

# Default uncertainty parameters per sensor
SENSOR_UNCERTAINTIES = {
    'AHI': {
        'scan_size_nadir': 2000,   # meters
        'track_size_nadir': 2000,
        'geoloc_error': 1000,       # meters, 1-sigma
        'pixel_growth_factor': 1.5, # at NSW VZA ~33 deg
    },
    'VIIRS_I': {
        'scan_size_nadir': 375,
        'track_size_nadir': 375,
        'geoloc_error': 375,
        # VIIRS pixel grows ~2x at edge due to aggregation scheme
        # At 31.6 deg scan angle: 3:1 -> 2:1 aggregation
        # At 44.7 deg scan angle: 2:1 -> 1:1 aggregation
        # Maximum growth: ~1.6 km x 1.6 km at 56 deg
    },
    'MODIS': {
        'scan_size_nadir': 1000,
        'track_size_nadir': 1000,
        'geoloc_error': 500,
        # MODIS pixel grows to ~2 km track x ~4.8 km scan at edge
    },
    'LANDSAT_OLI': {
        'scan_size_nadir': 30,
        'track_size_nadir': 30,
        'geoloc_error': 50,
    },
    'SENTINEL2_MSI': {
        'scan_size_nadir': 20,   # SWIR bands B11, B12
        'track_size_nadir': 20,
        'geoloc_error': 20,
    },
}
```

### 2.2 Spatial Matching Algorithm

```python
from shapely.geometry import Point
from shapely.ops import unary_union
import geopandas as gpd

def match_detections_cross_sensor(trigger_detection, candidate_detections,
                                   max_time_offset_hours=3.0):
    """Match a geostationary trigger to polar-orbiting detections.

    Args:
        trigger_detection: dict with lat, lon, time, sensor, uncertainty
        candidate_detections: list of dicts from other sensors
        max_time_offset_hours: maximum temporal separation

    Returns:
        list of matched detections with match quality scores
    """
    trigger_point = Point(trigger_detection['lon'], trigger_detection['lat'])
    uncertainty = trigger_detection['uncertainty']

    # Create uncertainty buffer (in degrees)
    lat_buf, lon_buf = uncertainty.to_buffer_degrees()
    # Use the larger of the two for a circular buffer (conservative)
    buffer_deg = max(lat_buf, lon_buf)
    trigger_buffer = trigger_point.buffer(buffer_deg)

    matches = []
    for candidate in candidate_detections:
        # Temporal check
        dt = abs((candidate['time'] - trigger_detection['time']).total_seconds()) / 3600
        if dt > max_time_offset_hours:
            continue

        candidate_point = Point(candidate['lon'], candidate['lat'])

        # Also create buffer for candidate's own uncertainty
        cand_uncertainty = candidate.get('uncertainty')
        if cand_uncertainty:
            cand_lat_buf, cand_lon_buf = cand_uncertainty.to_buffer_degrees()
            cand_buffer = candidate_point.buffer(max(cand_lat_buf, cand_lon_buf))
        else:
            cand_buffer = candidate_point.buffer(0.005)  # ~500m default

        # Match if buffers intersect
        if trigger_buffer.intersects(cand_buffer):
            # Compute match quality
            distance_deg = trigger_point.distance(candidate_point)
            distance_km = distance_deg * 111.0  # approximate

            match_quality = {
                'candidate': candidate,
                'distance_km': distance_km,
                'time_offset_hours': dt,
                'spatial_score': max(0, 1.0 - distance_km / (buffer_deg * 111)),
                'temporal_score': max(0, 1.0 - dt / max_time_offset_hours),
                'resolution_gain': trigger_detection['uncertainty'].scan_size /
                                   max(candidate.get('scan_size', 375), 1),
            }
            matches.append(match_quality)

    # Sort by combined score (spatial + temporal)
    matches.sort(key=lambda m: m['spatial_score'] + m['temporal_score'], reverse=True)
    return matches
```

## 3. Bayesian Confidence Aggregation

### 3.1 Log-Odds Evidence Framework

```python
import math

# Prior: base rate of fire occurrence for a random pixel in fire season
# In Australian fire-prone areas, ~0.001 probability per pixel per day
PRIOR_LOG_ODDS = math.log(0.001 / 0.999)  # ~ -6.9

# Log-likelihood ratios (LLR) for each evidence source
# Positive LLR = evidence supports fire; negative = evidence against fire
LLR_TABLE = {
    # Geostationary detection strength
    'ahi_strong_anomaly':       4.0,   # BT_3.9 > 360K or > mean + 6*sigma
    'ahi_moderate_anomaly':     2.5,   # BT_3.9 > mean + 4*sigma
    'ahi_weak_anomaly':         1.0,   # BT_3.9 > mean + 3*sigma
    'ahi_no_anomaly':          -2.0,   # No detection where expected

    # Temporal persistence
    'persistent_3_of_3':        2.0,   # Detected in all 3 consecutive frames
    'persistent_2_of_3':        1.5,   # Detected in 2 of 3 frames
    'persistent_growing':       2.5,   # Detected and intensifying
    'transient_1_of_3':        -1.5,   # Only 1 of 3 frames (likely FP)

    # Polar-orbiting confirmation
    'viirs_high_confidence':    4.0,   # VIIRS high confidence detection
    'viirs_nominal':            3.0,   # VIIRS nominal confidence
    'viirs_low':                1.0,   # VIIRS low confidence
    'viirs_no_detection':      -1.5,   # VIIRS overpass, no detection (could be below VIIRS threshold)
    'modis_detection':          2.5,   # MODIS fire detection

    # High-resolution confirmation
    'landsat_thermal_anomaly':  5.0,   # Landsat detects thermal anomaly
    'sentinel2_hotspot':        4.5,   # Sentinel-2 SWIR anomaly

    # FIRMS cross-check
    'firms_nrt_match':          3.0,   # FIRMS NRT has detection nearby
    'firms_nrt_no_match':      -0.5,   # FIRMS NRT has no detection (may be timing)

    # False positive indicators (negative = evidence against fire)
    'sun_glint_zone':          -3.0,   # Pixel in sun glint geometry
    'known_industrial':        -4.0,   # Matches static thermal anomaly mask
    'known_volcanic':          -4.0,   # Near known volcano with activity
    'desert_bare_soil':        -1.0,   # Arid land cover, daytime
    'water_body':              -2.0,   # Over water (unless known gas flare)

    # Contextual factors (moderate influence)
    'high_fire_danger_rating':  0.5,   # Fire weather index is elevated
    'fire_season':              0.3,   # Within normal fire season
    'vegetation_present':       0.5,   # Land cover supports fire
    'recent_lightning':         1.0,   # Lightning detected within 24h, 10km
}

def compute_confidence(evidence_list: list[str], prior_log_odds=PRIOR_LOG_ODDS):
    """Compute fire probability from accumulated evidence.

    Args:
        evidence_list: list of evidence keys from LLR_TABLE
        prior_log_odds: prior log-odds of fire

    Returns:
        probability: float in [0, 1]
        log_odds: float
        tier: str ('high', 'nominal', 'low', 'rejected')
    """
    log_odds = prior_log_odds

    for evidence in evidence_list:
        if evidence in LLR_TABLE:
            log_odds += LLR_TABLE[evidence]

    # Convert to probability
    probability = 1.0 / (1.0 + math.exp(-log_odds))

    # Classify into tiers
    if probability >= 0.85:
        tier = 'high'
    elif probability >= 0.50:
        tier = 'nominal'
    elif probability >= 0.20:
        tier = 'low'
    else:
        tier = 'rejected'

    return probability, log_odds, tier
```

### 3.2 Dempster-Shafer Alternative

For situations where evidence sources may conflict (e.g., AHI says fire but VIIRS says no fire), Dempster-Shafer theory provides explicit handling of uncertainty:

```python
def dempster_shafer_combine(m1: dict, m2: dict):
    """Combine two mass functions using Dempster's rule.

    Args:
        m1, m2: dicts mapping hypothesis sets to mass values.
                 Keys are frozensets: frozenset({'fire'}), frozenset({'no_fire'}),
                 frozenset({'fire', 'no_fire'}) for uncertainty.
                 Values sum to 1.0.

    Returns:
        combined mass function
    """
    fire = frozenset({'fire'})
    no_fire = frozenset({'no_fire'})
    theta = frozenset({'fire', 'no_fire'})  # uncertainty

    # Compute all pairwise intersections
    combined = {}
    conflict = 0.0

    for a, ma in m1.items():
        for b, mb in m2.items():
            intersection = a & b
            if len(intersection) == 0:
                conflict += ma * mb
            else:
                combined[intersection] = combined.get(intersection, 0.0) + ma * mb

    # Normalize by (1 - conflict)
    if conflict >= 1.0:
        raise ValueError("Total conflict -- sources completely disagree")

    normalization = 1.0 / (1.0 - conflict)
    for key in combined:
        combined[key] *= normalization

    return combined, conflict

# Example: AHI detects fire (moderate confidence), VIIRS sees nothing
m_ahi = {
    frozenset({'fire'}):            0.6,
    frozenset({'no_fire'}):         0.1,
    frozenset({'fire', 'no_fire'}): 0.3,  # uncertainty
}

m_viirs_no_detect = {
    frozenset({'fire'}):            0.05,  # small chance VIIRS missed it
    frozenset({'no_fire'}):         0.5,
    frozenset({'fire', 'no_fire'}): 0.45,  # substantial uncertainty (fire may be too small for VIIRS)
}
# combined, conflict = dempster_shafer_combine(m_ahi, m_viirs_no_detect)
# High conflict indicates the sources disagree -- warrants investigation
```

## 4. Event Tracking State Machine

### 4.1 Fire Event Data Structure

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from shapely.geometry import MultiPoint
from shapely import concave_hull

class EventState(Enum):
    CANDIDATE = 'candidate'       # Single detection, unconfirmed
    ACTIVE = 'active'             # Confirmed by persistence or cross-sensor
    GROWING = 'growing'           # Area/intensity increasing
    STABLE = 'stable'             # Active but not growing
    DECLINING = 'declining'       # Intensity decreasing
    EXTINGUISHED = 'extinguished' # No detections for > inactivity_timeout
    REJECTED = 'rejected'         # Determined to be false positive

@dataclass
class FireDetection:
    """Single detection from any sensor."""
    sensor: str             # 'AHI', 'VIIRS_SNPP', 'VIIRS_N20', 'MODIS', 'LANDSAT', 'SENTINEL2'
    lat: float
    lon: float
    timestamp: datetime
    brightness_mir: float   # BT in MIR band (K)
    brightness_tir: float   # BT in TIR band (K) -- may be NaN for some sensors
    btd: float              # MIR - TIR
    frp: float              # Fire Radiative Power (MW) -- 0 if not available
    confidence: float       # Sensor-native confidence (0-1 normalized)
    confidence_label: str   # 'low', 'nominal', 'high'
    scan_size_m: float      # Pixel scan dimension (meters)
    track_size_m: float     # Pixel track dimension (meters)
    day_night: str          # 'D' or 'N'

@dataclass
class FireEvent:
    """Tracked fire event accumulating detections over time."""
    event_id: str
    state: EventState = EventState.CANDIDATE

    # Detections
    detections: list[FireDetection] = field(default_factory=list)

    # Timing
    first_detected: datetime = None
    last_detected: datetime = None
    last_state_change: datetime = None

    # Geometry (updated as detections accumulate)
    centroid_lat: float = 0.0
    centroid_lon: float = 0.0
    geometry: object = None          # Shapely geometry (alpha hull)
    area_km2: float = 0.0

    # Confidence
    combined_confidence: float = 0.0
    confidence_tier: str = 'low'
    evidence_log: list[str] = field(default_factory=list)

    # Sensors that have contributed
    confirming_sensors: set = field(default_factory=set)

    # Intensity tracking
    peak_frp: float = 0.0
    current_frp: float = 0.0
    frp_trend: str = 'unknown'  # 'increasing', 'stable', 'decreasing'

    def add_detection(self, detection: FireDetection):
        self.detections.append(detection)
        self.confirming_sensors.add(detection.sensor)

        if self.first_detected is None:
            self.first_detected = detection.timestamp
        self.last_detected = detection.timestamp

        if detection.frp > self.peak_frp:
            self.peak_frp = detection.frp
        self.current_frp = detection.frp

        self._update_geometry()
        self._update_frp_trend()

    def _update_geometry(self):
        """Recompute geometry from all detection points."""
        if len(self.detections) < 1:
            return

        points = [(d.lon, d.lat) for d in self.detections]
        self.centroid_lon = sum(p[0] for p in points) / len(points)
        self.centroid_lat = sum(p[1] for p in points) / len(points)

        if len(points) >= 3:
            mp = MultiPoint(points)
            # Alpha hull (concave hull) -- ratio controls concavity
            # ratio=0.3 is a reasonable default for fire shapes
            self.geometry = concave_hull(mp, ratio=0.3)
            # Approximate area in km^2
            # At ~33S latitude: 1 deg lat ~ 111 km, 1 deg lon ~ 93 km
            if self.geometry.area > 0:
                self.area_km2 = self.geometry.area * 111 * 93
        elif len(points) == 2:
            from shapely.geometry import LineString
            self.geometry = LineString(points).buffer(0.01)  # ~1km buffer
        else:
            self.geometry = Point(points[0]).buffer(0.01)

    def _update_frp_trend(self):
        """Assess FRP trend from recent detections."""
        recent = [d for d in self.detections[-10:] if d.frp > 0]
        if len(recent) < 3:
            self.frp_trend = 'unknown'
            return

        frp_values = [d.frp for d in recent]
        # Simple linear trend
        slope = (frp_values[-1] - frp_values[0]) / max(len(frp_values) - 1, 1)
        if slope > 0.5:  # MW per detection step
            self.frp_trend = 'increasing'
        elif slope < -0.5:
            self.frp_trend = 'decreasing'
        else:
            self.frp_trend = 'stable'
```

### 4.2 Event Store and Association Logic

```python
from uuid import uuid4

class FireEventStore:
    """In-memory store for active fire events with spatial indexing."""

    def __init__(self,
                 spatial_match_radius_km=5.0,
                 inactivity_timeout_hours=120,  # 5 days (FEDS standard)
                 merge_overlap_threshold=0.3):
        self.events: dict[str, FireEvent] = {}
        self.spatial_match_radius_km = spatial_match_radius_km
        self.inactivity_timeout_hours = inactivity_timeout_hours
        self.merge_overlap_threshold = merge_overlap_threshold

    def ingest_detection(self, detection: FireDetection,
                          evidence: list[str]) -> FireEvent:
        """Process a new detection: associate with existing event or create new."""

        # 1. Find candidate events within spatial radius
        candidates = self._spatial_search(
            detection.lat, detection.lon,
            self.spatial_match_radius_km
        )

        # 2. Filter by temporal proximity
        candidates = [
            e for e in candidates
            if (detection.timestamp - e.last_detected).total_seconds() / 3600
               < self.inactivity_timeout_hours
            and e.state not in (EventState.EXTINGUISHED, EventState.REJECTED)
        ]

        if candidates:
            # 3a. Associate with nearest active event
            best = min(candidates,
                       key=lambda e: self._distance_km(
                           detection.lat, detection.lon,
                           e.centroid_lat, e.centroid_lon))
            best.add_detection(detection)
            self._update_state(best, evidence)
            self._check_merges(best)
            return best
        else:
            # 3b. Create new event
            event = FireEvent(
                event_id=str(uuid4())[:12],
                state=EventState.CANDIDATE,
            )
            event.add_detection(detection)
            event.combined_confidence, _, event.confidence_tier = compute_confidence(evidence)
            event.evidence_log = evidence.copy()
            self.events[event.event_id] = event
            return event

    def _spatial_search(self, lat, lon, radius_km):
        """Find events within radius_km of the given point.

        For production, use an R-tree spatial index. Brute force shown here.
        """
        results = []
        for event in self.events.values():
            dist = self._distance_km(lat, lon, event.centroid_lat, event.centroid_lon)
            if dist <= radius_km:
                results.append(event)
        return results

    def _update_state(self, event: FireEvent, new_evidence: list[str]):
        """Update event state based on new detection and evidence."""
        event.evidence_log.extend(new_evidence)
        event.combined_confidence, _, event.confidence_tier = compute_confidence(
            event.evidence_log
        )

        n_sensors = len(event.confirming_sensors)
        n_detections = len(event.detections)

        # State transitions
        if event.state == EventState.CANDIDATE:
            if event.confidence_tier in ('high', 'nominal') or n_sensors >= 2:
                event.state = EventState.ACTIVE
                event.last_state_change = event.last_detected

        elif event.state == EventState.ACTIVE:
            if event.frp_trend == 'increasing' or event.area_km2 > 1.0:
                event.state = EventState.GROWING
                event.last_state_change = event.last_detected

        elif event.state == EventState.GROWING:
            if event.frp_trend == 'decreasing':
                event.state = EventState.DECLINING
                event.last_state_change = event.last_detected
            elif event.frp_trend == 'stable':
                event.state = EventState.STABLE
                event.last_state_change = event.last_detected

    def _check_merges(self, event: FireEvent):
        """Merge events whose geometries overlap significantly."""
        if event.geometry is None:
            return

        to_merge = []
        for other_id, other in self.events.items():
            if other_id == event.event_id or other.geometry is None:
                continue
            if other.state in (EventState.EXTINGUISHED, EventState.REJECTED):
                continue

            if event.geometry.intersects(other.geometry):
                intersection_area = event.geometry.intersection(other.geometry).area
                smaller_area = min(event.geometry.area, other.geometry.area)
                if smaller_area > 0:
                    overlap_ratio = intersection_area / smaller_area
                    if overlap_ratio > self.merge_overlap_threshold:
                        to_merge.append(other_id)

        for merge_id in to_merge:
            other = self.events.pop(merge_id)
            for det in other.detections:
                event.add_detection(det)
            event.confirming_sensors.update(other.confirming_sensors)
            event.evidence_log.extend(other.evidence_log)

    def expire_inactive(self, current_time: datetime):
        """Mark events with no recent detections as extinguished."""
        for event in self.events.values():
            if event.state in (EventState.EXTINGUISHED, EventState.REJECTED):
                continue

            hours_since = (current_time - event.last_detected).total_seconds() / 3600
            if hours_since > self.inactivity_timeout_hours:
                event.state = EventState.EXTINGUISHED
                event.last_state_change = current_time

    @staticmethod
    def _distance_km(lat1, lon1, lat2, lon2):
        """Approximate distance in km using equirectangular projection."""
        dlat = (lat2 - lat1) * 111.0
        dlon = (lon2 - lon1) * 111.0 * math.cos(math.radians((lat1 + lat2) / 2))
        return math.sqrt(dlat**2 + dlon**2)
```

## 5. Diurnal Temperature Cycle (DTC) Fitting

For long-term temporal baselines used in the Kalman filter approach:

```python
def fit_diurnal_cycle(times_hours: np.ndarray, bt_values: np.ndarray):
    """Fit a simple sinusoidal DTC model to brightness temperature observations.

    Model: BT(t) = offset + amplitude * cos(2*pi*(t - phase)/24)

    Args:
        times_hours: local solar time in hours (0-24)
        bt_values: brightness temperatures (K)

    Returns:
        dict with offset, amplitude, phase parameters
    """
    from scipy.optimize import curve_fit

    def dtc_model(t, offset, amplitude, phase):
        return offset + amplitude * np.cos(2 * np.pi * (t - phase) / 24.0)

    # Initial guesses
    p0 = [np.median(bt_values),
          (np.max(bt_values) - np.min(bt_values)) / 2,
          14.0]  # peak around 2pm local time

    try:
        popt, pcov = curve_fit(dtc_model, times_hours, bt_values, p0=p0,
                                bounds=([200, 0, 0], [350, 50, 24]))
        return {
            'offset': popt[0],
            'amplitude': popt[1],
            'phase': popt[2],
            'residual_std': np.std(bt_values - dtc_model(times_hours, *popt)),
        }
    except RuntimeError:
        # Fallback: use simple statistics
        return {
            'offset': np.median(bt_values),
            'amplitude': (np.percentile(bt_values, 95) - np.percentile(bt_values, 5)) / 2,
            'phase': 14.0,
            'residual_std': np.std(bt_values),
        }
```
