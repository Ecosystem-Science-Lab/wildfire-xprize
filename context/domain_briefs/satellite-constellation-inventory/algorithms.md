# Satellite Overpass Prediction and View Geometry Algorithms

## 1. TLE-Based Overpass Prediction

### What are TLEs?

Two-Line Element sets (TLEs) describe satellite orbits in a compact format. They encode orbital parameters (inclination, RAAN, eccentricity, argument of perigee, mean anomaly, mean motion) and are used with the SGP4/SDP4 propagation model to predict satellite positions.

**TLE Sources:**
- **CelesTrak** (celestrak.org/NORAD/elements/) -- primary source for most users
- **Space-Track** (space-track.org) -- official NORAD catalog, requires registration
- **TLE API** (tle.ivanstanojevic.me) -- REST API wrapper

**Important:** TLEs degrade in accuracy over time. For reliable predictions, use TLEs within ~2 weeks of their epoch date. Refresh TLEs regularly.

### Key NORAD Catalog Numbers for Fire Satellites

| Satellite | NORAD ID | CelesTrak Group |
|---|---|---|
| Suomi NPP | 37849 | weather |
| NOAA-20 | 43013 | weather |
| NOAA-21 | 54234 | weather |
| Terra | 25994 | resource |
| Aqua | 27424 | resource |
| Sentinel-3A | 41335 | resource |
| Sentinel-3B | 43437 | resource |
| MetOp-B | 38771 | weather |
| MetOp-C | 43689 | weather |
| Landsat 8 | 39084 | resource |
| Landsat 9 | 49260 | resource |
| Sentinel-2B | 42063 | resource |
| Sentinel-2C | TBD (2024 launch) | resource |
| Sentinel-1A | 39634 | resource |
| Sentinel-1C | TBD (2024 launch) | resource |
| Sentinel-5P | 42969 | resource |
| Meteor-M N2-3 | 57166 | weather |

### Python Libraries for Overpass Prediction

#### Option 1: pyorbital (satpy ecosystem)

pyorbital is designed specifically for satellite remote sensing applications. It directly supports overpass calculations.

```python
from pyorbital.orbital import Orbital
from datetime import datetime

# Define observer location (central NSW)
lat, lon = -33.0, 150.0  # approximate center of NSW

# Load satellite TLE
orb = Orbital("SUOMI NPP")  # auto-fetches from CelesTrak

# Get next overpasses
passes = orb.get_next_passes(
    datetime.utcnow(),
    24,            # hours to search
    lon, lat, 0,   # longitude, latitude, altitude (m)
    tol=0.001,     # tolerance in seconds
    horizon=0      # minimum elevation (degrees)
)

for rise_time, rise_azimuth, max_alt_time, max_alt, set_time, set_azimuth in passes:
    print(f"Rise: {rise_time}, Max alt: {max_alt:.1f} deg at {max_alt_time}, Set: {set_time}")
```

**Note:** pyorbital only supports LEO satellites. Not suitable for geostationary.

#### Option 2: Skyfield (general-purpose)

Skyfield is more flexible and supports higher-precision calculations.

```python
from skyfield.api import load, EarthSatellite, wgs84
from skyfield import almanac

ts = load.timescale()

# Load TLE data
stations_url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=weather&FORMAT=tle'
satellites = load.tle_file(stations_url)

# Find specific satellite
by_name = {sat.name: sat for sat in satellites}
satellite = by_name['SUOMI NPP']

# Define observer
nsw_center = wgs84.latlon(-33.0, 150.0)

# Find overpass events
t0 = ts.now()
t1 = ts.tt_jd(t0.tt + 1.0)  # search 1 day

# Find events (rise, culminate, set)
t, events = satellite.find_events(nsw_center, t0, t1, altitude_degrees=0.0)

for ti, event in zip(t, events):
    name = ('rise', 'culminate', 'set')[event]
    print(f'{ti.utc_iso()} {name}')
```

#### Option 3: sgp4 (low-level, fastest)

For high-performance batch calculations:

```python
from sgp4.api import Satrec, jday
from sgp4 import exporter

# Parse TLE directly
s = '1 37849U 11061A   26076.50000000  .00000100  00000-0  50000-4 0  9999'
t = '2 37849  98.7200 100.0000 0001500  90.0000 270.0000 14.19552000000000'
satellite = Satrec.twoline2rv(s, t)

# Propagate to specific time
jd, fr = jday(2026, 4, 15, 12, 0, 0)  # April 15, 2026 12:00 UTC
e, r, v = satellite.sgp4(jd, fr)
# r = [x, y, z] position in km (TEME frame)
# v = [vx, vy, vz] velocity in km/s
```

### Batch Overpass Scheduling

For the competition window, pre-compute all overpasses:

```python
from pyorbital.orbital import Orbital
from datetime import datetime, timedelta
import json

# NSW bounding box corners
nsw_corners = [
    (-28, 148), (-28, 154),
    (-37, 148), (-37, 154),
    (-32.5, 151)  # center
]

satellites = [
    "SUOMI NPP", "NOAA 20", "NOAA 21",
    "TERRA", "AQUA",
    "SENTINEL-3A", "SENTINEL-3B",
    "METOP-B", "METOP-C",
    "LANDSAT 8", "LANDSAT 9",
]

start = datetime(2026, 4, 10, 0, 0, 0)
hours = 14 * 24  # 2-week window

schedule = {}
for sat_name in satellites:
    try:
        orb = Orbital(sat_name)
        passes = []
        for lat, lon in nsw_corners:
            corner_passes = orb.get_next_passes(
                start, hours, lon, lat, 0, horizon=5
            )
            for p in corner_passes:
                passes.append({
                    'rise': p[0].isoformat(),
                    'max_alt_time': p[2].isoformat(),
                    'max_alt_deg': p[3],
                    'set': p[4].isoformat(),
                    'corner': (lat, lon)
                })
        schedule[sat_name] = passes
    except Exception as e:
        schedule[sat_name] = f"Error: {e}"

# Save schedule
with open('nsw_overpass_schedule.json', 'w') as f:
    json.dump(schedule, f, indent=2)
```

## 2. View Geometry Calculations

### Geostationary View Angle

For geostationary satellites, the view zenith angle (VZA) from satellite to ground point is fixed and depends only on the ground point's latitude and longitude relative to the sub-satellite point.

```python
import numpy as np

def geostationary_vza(sat_lon, ground_lat, ground_lon):
    """
    Calculate View Zenith Angle from a geostationary satellite.

    Parameters:
        sat_lon: satellite longitude (degrees East)
        ground_lat: ground point latitude (degrees, negative for South)
        ground_lon: ground point longitude (degrees East)

    Returns:
        VZA in degrees
    """
    Re = 6371.0  # Earth radius (km)
    h = 35786.0  # GEO altitude (km)

    lat_r = np.radians(ground_lat)
    dlon_r = np.radians(ground_lon - sat_lon)

    # Cosine of central angle
    cos_gamma = np.cos(lat_r) * np.cos(dlon_r)

    # Distance from satellite to ground point
    d = np.sqrt(Re**2 + (Re + h)**2 - 2 * Re * (Re + h) * cos_gamma)

    # View zenith angle
    sin_vza = (Re + h) * np.sin(np.arccos(cos_gamma)) / d
    vza = np.degrees(np.arcsin(sin_vza))

    return vza

# NSW examples
print("Himawari-9 (140.7E) VZA for NSW:")
for lat in [-28, -32.5, -37]:
    for lon in [148, 151, 154]:
        vza = geostationary_vza(140.7, lat, lon)
        print(f"  ({lat}, {lon}): VZA = {vza:.1f} deg")

print("\nGK-2A (128.2E) VZA for NSW:")
for lat in [-28, -32.5, -37]:
    for lon in [148, 151, 154]:
        vza = geostationary_vza(128.2, lat, lon)
        print(f"  ({lat}, {lon}): VZA = {vza:.1f} deg")
```

### Effective Pixel Size at View Angle

Geostationary pixel size grows with VZA:

```python
def effective_pixel_size(nadir_resolution_km, vza_deg):
    """
    Approximate effective pixel size at a given view zenith angle.

    The pixel stretches in the along-scan and cross-scan directions.
    This gives a rough estimate of the effective footprint.
    """
    vza_r = np.radians(vza_deg)

    # Along-scan: pixel stretches by 1/cos(VZA)
    # Cross-scan: additional geometric stretching
    # Simplified: effective area ~ nadir_area / cos^3(VZA)
    # Effective linear dimension ~ nadir / cos^1.5(VZA)

    stretch_factor = 1.0 / np.cos(vza_r)**1.5
    return nadir_resolution_km * stretch_factor

# Himawari AHI: 2 km nadir resolution for thermal bands
for vza in [35, 40, 43, 50]:
    eff = effective_pixel_size(2.0, vza)
    print(f"VZA {vza} deg: effective pixel ~ {eff:.1f} km")
```

### LEO View Geometry (Scan Angle)

For polar-orbiting sensors, view geometry depends on the scan angle from nadir:

```python
def viirs_pixel_size(scan_angle_deg):
    """
    VIIRS I-band pixel size vs scan angle.
    At nadir: 375m
    At edge of swath (~56 deg): approximately 800m along-track, 800m cross-track
    (VIIRS uses onboard pixel aggregation to limit pixel growth)
    """
    # VIIRS has a unique design that limits pixel growth at edge of scan
    # Unlike MODIS which has severe "bow-tie" distortion
    # Approximate I-band effective resolution
    theta = np.radians(scan_angle_deg)

    # Simplified model (VIIRS limits growth to ~2x at edge)
    growth = 1.0 + 1.0 * (np.sin(theta))**2
    return 375 * growth  # meters

for angle in [0, 10, 20, 30, 40, 50, 56]:
    size = viirs_pixel_size(angle)
    print(f"VIIRS I-band at {angle} deg scan: ~{size:.0f} m")
```

## 3. Sun-Synchronous Orbit Overpass Time Estimation

For sun-synchronous satellites, the local solar time of overpass is approximately constant. The actual overpass time at a specific location depends on latitude:

```python
def estimate_local_overpass_time(equator_crossing_time_hours, latitude_deg, ascending=True):
    """
    Estimate local solar time of overpass for a sun-synchronous satellite.

    This is approximate -- actual times depend on exact orbit geometry.
    For accurate times, use TLE propagation.

    Parameters:
        equator_crossing_time_hours: LTAN or LTDN in hours (e.g., 13.5 for 13:30)
        latitude_deg: observer latitude (negative for South)
        ascending: True for ascending node pass, False for descending
    """
    # The equatorial crossing time is the reference
    # At higher latitudes, the overpass time shifts slightly
    # but remains close to the equatorial crossing time
    # For SSO, the shift is typically <30 minutes for latitudes up to 60 deg

    if not ascending:
        # Descending node is 12 hours offset
        crossing = equator_crossing_time_hours + 12.0
        if crossing >= 24:
            crossing -= 24
    else:
        crossing = equator_crossing_time_hours

    # Rough latitude adjustment (orbit geometry causes slight time shift)
    # This is a simplification -- real shift depends on orbit inclination and exact geometry
    lat_rad = np.radians(abs(latitude_deg))
    time_shift = 0.5 * np.sin(lat_rad)  # rough hours adjustment

    local_time = crossing + time_shift
    if local_time >= 24:
        local_time -= 24

    hours = int(local_time)
    minutes = int((local_time - hours) * 60)
    return f"{hours:02d}:{minutes:02d} local solar time (approximate)"

# Approximate NSW overpass times
print("Approximate local overpass times for NSW (-33 deg):")
print(f"VIIRS (LTAN 13:30, ascending): {estimate_local_overpass_time(13.5, -33, True)}")
print(f"VIIRS (LTAN 13:30, descending): {estimate_local_overpass_time(13.5, -33, False)}")
print(f"MODIS Terra (LTDN 10:30, descending): {estimate_local_overpass_time(10.5, -33, False)}")
print(f"MODIS Terra (ascending): {estimate_local_overpass_time(10.5, -33, True)}")
print(f"Sentinel-3 (LTDN 10:00, descending): {estimate_local_overpass_time(10.0, -33, False)}")
print(f"MetOp (LTDN 09:30, descending): {estimate_local_overpass_time(9.5, -33, False)}")
print(f"Landsat (LTDN 10:12, descending): {estimate_local_overpass_time(10.2, -33, False)}")
```

## 4. Competition Window Planning

### Key Principle

For the XPRIZE competition in mid-April 2026, you need to:

1. **Pre-compute all LEO overpasses** for the 2-week competition window using fresh TLEs obtained just before the competition.
2. **Know the exact timing** of each VIIRS, MODIS, Landsat, Sentinel-3, SLSTR, and Sentinel-2 pass over the competition area.
3. **For each overpass**, calculate the view geometry (scan angle, pixel size) at the fire locations.
4. **Prioritize processing** based on which satellite passes first -- the scoring is "1 minute from overpass," so you need to detect and report within 1 minute of data becoming available.

### Geostationary Timing

Geostationary satellites have fixed, known imaging cadence:
- **Himawari-9**: Full disk every 10 minutes, starting at :00 of each 10-min block (00:00, 00:10, 00:20, etc. UTC). The scan sweeps from north to south. NSW will be imaged roughly in the middle of each scan.
- **GK-2A**: Full disk every 10 minutes (similar cadence).
- **FY-4B**: Full disk every 15 minutes.

For Himawari, the scan timeline within each 10-min window is:
- Scan starts at the top (north) of the disk
- Takes ~10 min to complete full disk
- NSW latitude (~30-37S) is scanned roughly 6-8 minutes after scan start
- Data transmission and product generation follow immediately

### ISS-Based Sensors (ECOSTRESS)

ECOSTRESS overpass prediction requires ISS TLE data. The ISS orbit precesses (not sun-synchronous), so overpass times shift continuously. Use TLE propagation for each day individually:

```python
# ISS NORAD ID: 25544
orb = Orbital("ISS (ZARYA)")  # ECOSTRESS is on ISS
passes = orb.get_next_passes(datetime(2026, 4, 10), 14*24, 150, -33, 0)
```

Note: ISS inclination (51.6 deg) limits coverage to latitudes within ~52 deg. All of NSW is covered, but overpass times and ground tracks are unpredictable weeks in advance.
