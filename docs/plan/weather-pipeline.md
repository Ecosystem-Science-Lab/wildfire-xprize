# Weather Data Pipeline Design

**Date:** 2026-03-19
**Purpose:** Supply near-real-time weather context to the fire detection pipeline during XPRIZE competition (April 9-21, 2026, NSW Australia)

---

## 1. Why Weather Data Matters

Weather variables serve two purposes in our system:

1. **False positive reduction.** A pixel that looks hot is less suspicious when the ambient temperature is 38C, the humidity is 12%, and there has been no rain for three weeks. Conversely, a marginal thermal anomaly during cool, humid conditions is more likely a real fire signal. Weather context helps the ML classifier (and potentially the contextual detector) distinguish fire from hot background.

2. **Fire danger context for characterization.** The McArthur Forest Fire Danger Index (FFDI) and its inputs (temperature, humidity, wind, drought factor) are the standard Australian fire danger metrics. Displaying FFDI on the judge portal alongside our detections shows domain awareness and helps judges interpret alert urgency.

### What we need

| Variable | Why | Temporal Resolution | Spatial Resolution |
|----------|-----|--------------------|--------------------|
| Air temperature (2m) | Hot ground confuses thermal detection; FFDI input | Hourly or better | ~10 km sufficient |
| Relative humidity (2m) | Dry conditions = higher fire risk; FFDI input | Hourly or better | ~10 km sufficient |
| Wind speed & direction (10m) | Fire spread context; FFDI input | Hourly or better | ~10 km sufficient |
| Recent rainfall | Drought factor proxy; fuel moisture | Daily accumulation | ~10 km sufficient |
| Land surface temperature (LST) | Background temperature baseline for thermal anomaly | Sub-hourly | ~2 km (from AHI directly) |

**We do NOT need weather data at AHI pixel resolution for most variables.** Temperature, humidity, and wind vary over scales of 10-50 km in flat terrain, so gridded NWP data at ~12-25 km resolution is more than adequate. The only variable where sub-pixel resolution matters is LST, and we already have that from our own BT14 observations.

---

## 2. Data Source Evaluation

### 2.1 Open-Meteo BOM API (PRIMARY -- Recommended)

Open-Meteo provides free access to BOM ACCESS-G model output via a simple REST API at `https://api.open-meteo.com/v1/bom`.

| Property | Details |
|----------|---------|
| **Model** | ACCESS-G (BOM's global NWP model), ~12 km resolution |
| **Update frequency** | 4x daily (00Z, 06Z, 12Z, 18Z) |
| **Latency** | Forecasts available within ~2-4 hours of model run time |
| **Variables available** | `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `precipitation`, `soil_temperature_0_to_7cm`, `soil_moisture_0_to_7cm`, plus many more |
| **Forecast horizon** | Up to 10 days |
| **Format** | JSON, hourly time series |
| **Rate limits (free)** | 10,000 calls/day, 5,000/hour, 600/minute |
| **Auth** | None required (free, non-commercial) |
| **Reliability** | Third-party service, no SLA for free tier |

**Why this is the primary source:** Zero setup cost, no API key needed, returns exactly the variables we need in an easy-to-parse format. A single API call per grid point returns a full 7-day hourly forecast. We can query a sparse grid of ~20-30 points covering NSW and interpolate, using well under 1% of the daily rate limit.

**Limitations:** This is forecast data, not observations. For the first few hours after a model run, the "forecast" at T+0 to T+3 is essentially analysis data (very close to reality). But beyond T+6, it diverges from actual conditions. Since the model updates 4x/day and we only need the most recent few hours, the effective weather data is always from a recent analysis cycle with minimal forecast drift.

**Concern:** Open-Meteo noted that BOM open-data delivery was "temporarily suspended" and being resumed. We need to verify the `/v1/bom` endpoint is active before relying on it. If BOM data is unavailable through Open-Meteo, the generic `/v1/forecast` endpoint uses ECMWF IFS and GFS models, which also cover Australia at comparable resolution.

### 2.2 BOM Automatic Weather Station Observations (SECONDARY)

BOM operates ~200+ automatic weather stations across NSW, reporting at 30-minute intervals, with data available as JSON.

| Property | Details |
|----------|---------|
| **Endpoint** | `http://www.bom.gov.au/fwo/IDN60901/IDN60901.{station_id}.json` |
| **Temporal resolution** | Half-hourly observations, 72-hour history |
| **Variables** | Temperature, dew point (for RH calculation), wind speed/direction/gust, rainfall, pressure |
| **Latency** | Near-real-time (~minutes) |
| **Format** | JSON (row-major or column-major) |
| **Auth** | None (public) |
| **Reliability** | Official government data; individual stations may have outages |

**Why this is secondary rather than primary:** Station data is point-based and requires spatial interpolation to cover the entire NSW fire area. The station network is dense near population centers but sparse in remote western NSW. Interpolation to a regular grid introduces errors in data-sparse regions. However, the data is *observed* (not forecast), so it serves as ground truth to validate the Open-Meteo gridded data and as a fallback if Open-Meteo is down.

**Station coverage for NSW:** There are roughly 150-200 active AWS in NSW. Coastal and Sydney/Hunter regions have stations every 20-30 km. Western NSW has stations only at towns, with gaps of 100+ km. For the competition, the ignition zones are expected to be in accessible areas (roads, fire tracks), so station density should be adequate for interpolation in most fire scenarios.

### 2.3 SILO Gridded Climate Data (NOT SUITABLE for NRT)

SILO provides daily gridded (0.05 degree, ~5 km) climate surfaces for all of Australia, derived from station observations via kriging/splining. Hosted on AWS S3.

| Property | Details |
|----------|---------|
| **Latency** | Data available for "yesterday" -- 1 day lag |
| **Temporal resolution** | Daily |
| **Variables** | Max/min temperature, rainfall, evaporation, radiation, VP deficit |
| **Spatial resolution** | 0.05 degrees (~5 km) |

**Verdict:** Too slow for real-time operations (1-day lag, daily resolution). However, SILO is useful for two things:
1. **Pre-competition drought factor calculation.** Download the rainfall and evaporation history for the 3 months before competition (January-March 2026) to compute the Keetch-Byram Drought Index (KBDI) or Soil Dryness Index as inputs to FFDI.
2. **Historical weather baselines.** Compare April 2026 conditions against April climatology to understand if conditions are unusually dry/hot.

### 2.4 ERA5 / ERA5T Reanalysis (NOT SUITABLE for NRT)

| Property | Details |
|----------|---------|
| **ERA5** | ~3 month latency, 0.25 degree, hourly |
| **ERA5T** | ~5 day latency, same resolution |

**Verdict:** Both are too slow for real-time use during the competition. ERA5T's 5-day lag means data from April 9 would not be available until April 14. However, ERA5 is excellent for:
1. **Kalman filter pre-initialization.** If CUSUM is implemented, the Kalman background model benefits from weather-aware initialization. ERA5 hourly data for March 2026 (available by early April) can provide the atmospheric context for the pre-competition initialization period.
2. **Historical validation.** Compare our weather pipeline output against ERA5 for past April periods to assess accuracy.

### 2.5 Direct ACCESS-G NWP from BOM/NCI (ASPIRATIONAL)

BOM's ACCESS-G model output is available in GRIB2/NetCDF format through NCI's THREDDS/OPeNDAP servers, at full ~12 km resolution with all model levels and variables.

| Property | Details |
|----------|---------|
| **Access** | NCI THREDDS server (requires NCI account) |
| **Format** | GRIB2, NetCDF4 |
| **Variables** | Full NWP model output (~100+ variables) |
| **Update** | 4x daily |

**Verdict:** This is the "proper" way to get ACCESS-G data but requires NCI account setup and GRIB parsing infrastructure. Not worth the engineering overhead when Open-Meteo provides the same model's output via a trivial JSON API. Only consider if Open-Meteo is unreliable.

---

## 3. Recommended Architecture

### Design Principles

1. **Weather data is a feature input, not a detection trigger.** The fire detection pipeline must function without weather data. Weather provides context that improves accuracy, but its absence must not block detection.
2. **Gridded forecast data is primary; station observations are secondary/validation.**
3. **Pre-compute and cache.** Weather data changes slowly (hourly). Fetch it on a schedule and cache the latest grid. Detection pipeline reads from cache, never blocks on weather fetch.
4. **Degrade gracefully.** If weather data is stale (>6 hours old) or unavailable, the pipeline continues with slightly reduced accuracy. Log a warning, do not halt.

### Data Flow

```
                    +-----------------------+
                    | Open-Meteo BOM API    |  (PRIMARY)
                    | /v1/bom endpoint      |
                    | 4x/day model updates  |
                    +-----------+-----------+
                                |
                        Poll every 60 min
                                |
                                v
                    +-----------+-----------+
                    | Weather Fetcher       |
                    | - Query ~25 grid pts  |
                    | - Parse JSON          |
                    | - Interpolate to      |
                    |   AHI 2km grid (IDW)  |
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    | Weather Cache         |  (in-memory + disk)
                    | - Latest hourly grid  |
                    | - temp_2m, rh_2m,     |
                    |   wind_spd, wind_dir, |
                    |   precip_sum, ffdi    |
                    | - Timestamp + staleness|
                    +-----------+-----------+
                          |             |
              +-----------+             +---------------+
              |                                         |
              v                                         v
    +---------+---------+                    +----------+----------+
    | Fire Detection    |                    | Judge Portal        |
    | Pipeline          |                    | - FFDI overlay      |
    | - ML classifier   |                    | - Wind barbs        |
    |   weather features|                    | - Current conditions|
    | - FP scoring      |                    +---------------------+
    +-------------------+

                    +-----------------------+
                    | BOM Station JSON      |  (SECONDARY)
                    | IDN60901 endpoints    |
                    +-----------+-----------+
                                |
                        Poll every 30 min
                        (~50 key stations)
                                |
                                v
                    +-----------+-----------+
                    | Station Cache         |
                    | - Point observations  |
                    | - Validation against  |
                    |   gridded data        |
                    | - Fallback if primary |
                    |   is down             |
                    +-----------+-----------+
```

### Grid Design

We do NOT need weather data at every AHI pixel. Instead, we define a coarse weather grid and interpolate:

**Weather query grid:** ~25-30 points on a regular 1-degree grid covering NSW (roughly 28-37S, 141-154E). This gives us a ~100 km weather grid that we interpolate down to the AHI pixel grid using inverse distance weighting (IDW).

```
Latitude range:  -28 to -37 (10 rows at 1-degree spacing)
Longitude range: 141 to 154 (14 columns at 1-degree spacing)
Total grid points: ~140 (but many are ocean/out of NSW)
Active land points: ~80-100
```

At 100 points with 1 API call per point per hour, that is 2,400 calls/day -- well within the 10,000/day Open-Meteo limit. We can reduce this further by batching (Open-Meteo supports multiple locations in a single call) or by querying less frequently (every 2 hours is sufficient since ACCESS-G only updates 4x/day).

**Interpolation to AHI grid:** Use scipy `griddata` with linear interpolation or inverse distance weighting. The NSW AHI grid is roughly 500x700 pixels (~350,000 pixels). Interpolating from 100 weather points to 350K pixels takes <100ms with scipy -- negligible.

### Station Selection (Secondary Source)

Select ~50 key BOM stations across NSW for the secondary/validation feed. Priority stations:

1. **Stations near expected fire zones** (western NSW grasslands, Blue Mountains, North Coast forests)
2. **Stations with reliable AWS reporting** (airport stations are highest quality)
3. **Stations providing geographic coverage** (at least one per ~100 km in data-sparse western NSW)

Station IDs are fixed and can be hardcoded. The JSON endpoint returns 72 hours of half-hourly data per call, so each station needs only 1 call per polling cycle.

---

## 4. Weather Variables and Integration

### 4.1 Variables to Fetch

From Open-Meteo `/v1/bom`:

```python
WEATHER_VARIABLES = {
    "hourly": [
        "temperature_2m",           # Air temperature at 2m (C)
        "relative_humidity_2m",     # Relative humidity at 2m (%)
        "wind_speed_10m",           # Wind speed at 10m (km/h)
        "wind_direction_10m",       # Wind direction at 10m (degrees)
        "wind_gusts_10m",           # Wind gusts at 10m (km/h)
        "precipitation",            # Precipitation sum for preceding hour (mm)
        "soil_temperature_0_to_7cm",# Soil surface temperature (C)
        "soil_moisture_0_to_7cm",   # Soil moisture (m3/m3)
        "cloud_cover",              # Total cloud cover (%) -- useful for detection context
    ],
}
```

From BOM station JSON (fields in `observations.data[]`):

```python
STATION_FIELDS = {
    "air_temp",          # Air temperature (C)
    "dewpt",             # Dew point (C) -- compute RH from this
    "wind_spd_kmh",      # Wind speed (km/h)
    "wind_dir",          # Wind direction (degrees)
    "gust_kmh",          # Wind gust (km/h)
    "rain_trace",        # Rainfall since 9am (mm) -- "Trace" means <0.2mm
    "press_msl",         # Mean sea level pressure (hPa)
    "rel_hum",           # Relative humidity (%) -- if available directly
}
```

### 4.2 Derived Variables

**McArthur Forest Fire Danger Index (FFDI):**

```python
import math

def compute_ffdi(temperature_c, relative_humidity, wind_speed_kmh, drought_factor):
    """
    McArthur Mark 5 Forest Fire Danger Index.

    Args:
        temperature_c: Air temperature in Celsius
        relative_humidity: Relative humidity in %
        wind_speed_kmh: Wind speed at 10m in km/h
        drought_factor: Drought factor (0-10), derived from KBDI or soil dryness

    Returns:
        FFDI value (0-100+, where 100 = extreme)
    """
    ffdi = 2.0 * math.exp(
        -0.450
        + 0.987 * math.log(drought_factor + 0.001)
        - 0.0345 * relative_humidity
        + 0.0338 * temperature_c
        + 0.0234 * wind_speed_kmh
    )
    return max(0.0, ffdi)
```

The drought factor (DF) is the trickiest component. It requires cumulative rainfall history (weeks to months). Options:
1. **Pre-compute from SILO:** Download SILO daily rainfall for Jan-March 2026, compute KBDI or Mount's Soil Dryness Index, then update daily during competition using BOM station rainfall.
2. **Use BOM FFDI directly:** BOM publishes fire danger ratings for NSW districts. We could scrape these as a simpler alternative to computing our own FFDI.
3. **Use soil moisture as proxy:** Open-Meteo provides `soil_moisture_0_to_7cm` from ACCESS-G. Low soil moisture correlates with high drought factor. Less rigorous than KBDI but zero historical data dependency.

**Recommendation:** Use approach (3) -- soil moisture from ACCESS-G -- as the operational drought proxy during competition. Pre-compute KBDI from SILO for validation and portal display. This avoids the complexity of maintaining a running KBDI calculation from station data.

**Background temperature anomaly context:**

For each fire pixel, compute how far the ambient air temperature is from the diurnal norm. A detection at BT7=320K when the air temperature is 40C is less notable than the same detection when the air temperature is 10C. This can be a simple feature for the ML classifier:

```python
temp_anomaly_context = bt7_observed - (ambient_air_temp_c + 273.15)
```

### 4.3 Integration Points in the Detection Pipeline

Weather data enters the pipeline at three points:

**Point 1: ML classifier features (if implemented)**

The ML classifier (stretch goal, Pass 2) receives a feature vector per fire candidate. Weather features added:

```python
weather_features = {
    "ambient_temp_c": float,        # Interpolated air temp at pixel location
    "relative_humidity_pct": float,  # Interpolated RH at pixel location
    "wind_speed_kmh": float,         # Interpolated wind speed
    "soil_moisture": float,          # Interpolated soil moisture
    "ffdi": float,                   # Computed FFDI at pixel location
    "cloud_cover_pct": float,        # Interpolated cloud cover (cross-check with our cloud mask)
    "hours_since_rain": float,       # Hours since last rainfall > 1mm at nearest station
}
```

These features help the classifier learn that, e.g., hot pixels in cool humid conditions with recent rain are more likely false positives (industrial, sun glint) than fire.

**Point 2: Confidence scoring adjustment**

Weather can modulate the confidence ladder. During extreme fire weather (FFDI > 50), lower the threshold for upgrading from PROVISIONAL to LIKELY -- the base rate of real fires is higher, so the prior shifts. During mild weather (FFDI < 5), require stricter evidence.

```python
# Example: adjust temporal persistence requirement based on FFDI
if ffdi >= 50:  # Extreme fire danger
    min_persistence = 1  # Single frame sufficient for LIKELY
elif ffdi >= 25:  # Very High
    min_persistence = 2  # Standard
else:
    min_persistence = 3  # Require more evidence in low-danger conditions
```

This is a tunable policy decision. Start conservative (no weather adjustment) and add it if testing shows it helps.

**Point 3: Portal display**

The judge portal shows weather context alongside detections:
- Current FFDI as a color-coded overlay on the map (green/yellow/orange/red/purple)
- Wind barbs at selected stations
- "Current conditions" sidebar: temperature, RH, wind, last rainfall

This is pure display, not detection logic. But it makes the portal look professional and helps judges assess our detections in context.

---

## 5. Polling Schedule and Latency

### Open-Meteo (Primary)

| Parameter | Value |
|-----------|-------|
| Poll interval | 60 minutes |
| Stagger across grid points | 100 points over 60 sec (avoid burst) |
| Data freshness | T-0 to T-4 hours (depending on model cycle) |
| Acceptable staleness | Up to 6 hours before warning |
| Critical staleness | 12 hours -- switch to station-only mode |

**Implementation:** Single async task in the existing polling scheduler (alongside DEA and FIRMS polls). Fetch all grid points, parse, interpolate, store in cache. Total fetch time ~30-60 sec (100 HTTP calls with ~300ms latency each, parallelized).

### BOM Stations (Secondary)

| Parameter | Value |
|-----------|-------|
| Poll interval | 30 minutes |
| Number of stations | ~50 |
| Data freshness | Near-real-time (~minutes from observation) |
| Acceptable staleness | Up to 2 hours before warning |

**Implementation:** Fetch 50 station JSON files in parallel. Parse temperature, humidity, wind, rainfall. Store as point observations in the station cache. Each response contains 72 hours of data, so even if a poll fails, we have a deep buffer.

### Pre-Competition Setup

Before April 9:
1. Download SILO rainfall data for NSW (Jan-March 2026) for KBDI initialization
2. Verify Open-Meteo `/v1/bom` endpoint returns valid data for NSW grid points
3. Compile list of ~50 BOM station IDs and verify JSON endpoints are active
4. Test weather-to-AHI-grid interpolation pipeline end-to-end
5. Compute initial drought factor / FFDI from SILO + BOM historical data

---

## 6. Storage Format

### Weather Grid Cache (In-Memory)

```python
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

@dataclass
class WeatherGrid:
    """Cached weather data interpolated to AHI pixel grid."""
    timestamp: datetime                    # When this weather data is valid for
    fetch_time: datetime                   # When we fetched it
    model_run: str                         # e.g. "ACCESS-G 2026-04-10T12Z"

    # Arrays shaped (n_rows, n_cols) matching AHI NSW grid
    temperature_2m_c: np.ndarray           # Air temperature (C)
    relative_humidity_2m_pct: np.ndarray   # Relative humidity (%)
    wind_speed_10m_kmh: np.ndarray         # Wind speed (km/h)
    wind_direction_10m_deg: np.ndarray     # Wind direction (degrees)
    wind_gusts_10m_kmh: np.ndarray         # Wind gusts (km/h)
    precipitation_mm: np.ndarray           # Precip in last hour (mm)
    soil_moisture: np.ndarray              # Soil moisture (m3/m3)
    cloud_cover_pct: np.ndarray            # Cloud cover (%)
    ffdi: np.ndarray                       # Computed FFDI

    def staleness_minutes(self) -> float:
        return (datetime.utcnow() - self.fetch_time).total_seconds() / 60

    def is_stale(self, max_minutes: float = 360) -> bool:
        return self.staleness_minutes() > max_minutes
```

### Station Cache (In-Memory)

```python
@dataclass
class StationObservation:
    station_id: str
    station_name: str
    lat: float
    lon: float
    obs_time: datetime
    air_temp_c: float | None
    relative_humidity_pct: float | None
    wind_speed_kmh: float | None
    wind_direction_deg: float | None
    wind_gust_kmh: float | None
    rainfall_since_9am_mm: float | None
    pressure_msl_hpa: float | None
```

### Disk Persistence

Write the weather grid to a NetCDF or simple NPZ file every hour. This provides:
1. Recovery after restart without waiting for the next weather fetch
2. Historical record for post-competition analysis
3. Training data for the ML classifier (weather conditions at the time of each detection)

---

## 7. Graceful Degradation

The weather pipeline has three failure modes and corresponding degradation strategies:

### Mode 1: Open-Meteo API down

**Detection:** HTTP error or timeout on fetch. **Response:** Switch to station-only mode. Interpolate from the ~50 BOM station observations using IDW. Quality is lower in data-sparse regions but sufficient for most NSW fire zones. Log a prominent warning.

### Mode 2: BOM station endpoints down

**Detection:** HTTP errors on station fetches. **Response:** Continue with Open-Meteo gridded data only. We lose the observational validation but the forecast data is still useful. Individual station failures are expected (some stations have intermittent outages); only raise an alarm if >50% of stations fail simultaneously.

### Mode 3: All weather data unavailable

**Detection:** Both Open-Meteo and BOM stations are unreachable. **Response:** Use the last cached weather grid (if <12 hours old). If the cache is older than 12 hours, mark weather data as unavailable. The detection pipeline continues without weather features:
- ML classifier uses default/neutral values for weather features (or omits them)
- FFDI overlay on portal shows "Weather data unavailable"
- Confidence scoring reverts to weather-agnostic mode (no FFDI-based threshold adjustment)

**Key design constraint:** The fire detection pipeline must NEVER block or fail because weather data is unavailable. Weather is an enhancement, not a dependency.

---

## 8. Configuration

Add to the existing config structure (compatible with `src/himawari/config.py` pattern):

```python
from pydantic import BaseModel

class WeatherConfig(BaseModel):
    """Configuration for the weather data pipeline."""

    # Open-Meteo (primary)
    openmeteo_enabled: bool = True
    openmeteo_base_url: str = "https://api.open-meteo.com/v1/bom"
    openmeteo_fallback_url: str = "https://api.open-meteo.com/v1/forecast"
    openmeteo_poll_interval_s: int = 3600  # 1 hour
    openmeteo_timeout_s: int = 30

    # Weather grid bounds (NSW bounding box, 1-degree spacing)
    grid_lat_min: float = -37.0
    grid_lat_max: float = -28.0
    grid_lon_min: float = 141.0
    grid_lon_max: float = 154.0
    grid_spacing_deg: float = 1.0

    # BOM stations (secondary)
    bom_stations_enabled: bool = True
    bom_station_base_url: str = "http://www.bom.gov.au/fwo/IDN60901/IDN60901.{station_id}.json"
    bom_station_poll_interval_s: int = 1800  # 30 minutes
    bom_station_timeout_s: int = 15
    # Station IDs loaded from a separate config file
    bom_station_ids_file: str = "config/nsw_weather_stations.json"

    # Cache and staleness
    max_grid_staleness_min: float = 360.0  # 6 hours before warning
    critical_staleness_min: float = 720.0  # 12 hours before disabling weather features
    cache_dir: str = "data/weather"

    # FFDI computation
    drought_factor_default: float = 7.0  # Conservative default (high fire danger)
    drought_factor_source: str = "soil_moisture"  # "soil_moisture" | "kbdi" | "fixed"

    # Integration
    ffdi_confidence_adjustment: bool = False  # Start disabled, enable after testing
    ffdi_extreme_threshold: float = 50.0
    ffdi_low_threshold: float = 5.0
```

---

## 9. Integration with Existing Scheduler

The weather polling tasks fit naturally into the existing `src/polling/scheduler.py` pattern:

```python
# In scheduler.py, add alongside poll_dea_loop and poll_firms_loop:

async def poll_weather_loop(interval: int):
    """Poll weather data on interval."""
    global last_poll_weather, last_poll_weather_ok
    while True:
        try:
            logger.info("Polling weather data...")
            grid = await fetch_openmeteo_grid()
            interpolated = interpolate_to_ahi_grid(grid)
            weather_cache.update(interpolated)
            last_poll_weather = datetime.now(timezone.utc)
            last_poll_weather_ok = True
            logger.info("Weather poll complete: %d grid points, FFDI range %.1f-%.1f",
                        len(grid), interpolated.ffdi.min(), interpolated.ffdi.max())
        except Exception:
            last_poll_weather_ok = False
            logger.exception("Weather poll failed")
        await asyncio.sleep(interval)

async def poll_bom_stations_loop(interval: int):
    """Poll BOM weather station observations on interval."""
    global last_poll_stations, last_poll_stations_ok
    while True:
        try:
            logger.info("Polling BOM stations...")
            observations = await fetch_bom_stations()
            station_cache.update(observations)
            last_poll_stations = datetime.now(timezone.utc)
            last_poll_stations_ok = True
            logger.info("Station poll complete: %d stations reporting",
                        len([o for o in observations if o.air_temp_c is not None]))
        except Exception:
            last_poll_stations_ok = False
            logger.exception("Station poll failed")
        await asyncio.sleep(interval)
```

---

## 10. Land Surface Temperature from AHI (Free Bonus)

We already have the data for land surface temperature -- BT14 (11.2 um) from every Himawari observation. BT14 is not precisely LST (it includes atmospheric effects and emissivity differences), but for fire detection context it serves the same purpose: telling us how hot the ground is.

The CUSUM detector already tracks a per-pixel BT14 background via an EMA (`bt14_ema_tau_hours: 4.0`). This gives us a built-in "is the ground unusually hot right now?" signal at 2 km resolution and 10-minute updates -- far better temporal resolution than any weather API can provide.

**No additional LST data source is needed.** The AHI BT14 field and its EMA background provide the land surface temperature context natively.

---

## 11. Implementation Priority and Effort

| Task | Effort | Priority | Dependencies |
|------|--------|----------|--------------|
| Open-Meteo fetcher + JSON parsing | 2-3 hours | Medium | None |
| IDW interpolation to AHI grid | 1-2 hours | Medium | AHI grid geometry (already available) |
| Weather grid cache (in-memory) | 1 hour | Medium | None |
| FFDI computation | 1 hour | Medium | Weather grid |
| Scheduler integration | 30 min | Medium | Existing scheduler |
| BOM station fetcher | 2-3 hours | Low | Station ID list |
| Station spatial interpolation (fallback) | 2 hours | Low | Station fetcher |
| Portal FFDI overlay | 2-3 hours | Low | Weather grid + portal |
| ML classifier weather features | 1-2 hours | Low (stretch) | ML classifier (stretch goal) |
| FFDI-based confidence adjustment | 1 hour | Low (stretch) | Weather grid + tuning data |
| KBDI pre-computation from SILO | 3-4 hours | Low | SILO download |

**Total estimated effort: ~8-10 hours for the core weather pipeline (Open-Meteo + cache + FFDI + scheduler). An additional ~8-10 hours for all secondary/stretch items.**

**Recommended implementation timing:** Week 2 (March 25-31), after the core Himawari pipeline and portal are stable. Weather data is a "nice to have" enhancement, not a Week 1 critical path item.

---

## 12. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Open-Meteo `/v1/bom` endpoint unavailable | Moderate | Low | Fall back to `/v1/forecast` (ECMWF IFS model); fall back to BOM station interpolation |
| BOM station JSON endpoints change format | Low | Low | Pin to known-good station IDs; monitor for format changes during pre-competition testing |
| Weather data does not improve ML classifier | Moderate | Low | Weather features are additive; classifier still works without them |
| FFDI-based confidence adjustment causes more harm than good | Moderate | Medium | Start disabled; enable only after validation on historical data |
| Rate-limiting on Open-Meteo free tier | Low | Low | We use <25% of daily limit; can reduce poll frequency if needed |
| Network partition during competition | Low | High | Use cached data (up to 12 hours); detection pipeline degrades gracefully |

---

## 13. Summary

| Component | Source | Update Frequency | Latency | Role |
|-----------|--------|-----------------|---------|------|
| Gridded weather (T, RH, wind, rain, soil) | Open-Meteo `/v1/bom` (ACCESS-G) | Hourly poll | 2-4 hr from model run | Primary: ML features, FFDI, portal |
| Station observations (T, RH, wind, rain) | BOM JSON `IDN60901` | 30-min poll | Near-real-time | Secondary: validation, fallback |
| Land surface temperature | AHI BT14 (already in pipeline) | 10-min (native) | 7-15 min | Built-in: ground temp baseline |
| Drought factor / antecedent rainfall | SILO + BOM daily | Pre-computed + daily update | 1 day for SILO | Pre-competition setup: KBDI/DF |
| Reanalysis for Kalman init | ERA5 (if CUSUM implemented) | One-time download | 5-day lag (ERA5T) | Pre-competition: CUSUM initialization |

The weather pipeline is a moderate-effort enhancement that adds meaningful value through false positive reduction, fire danger context, and professional portal display. It is not on the critical path for Week 1 but should be implemented in Week 2 alongside the event store and confidence ladder work.
