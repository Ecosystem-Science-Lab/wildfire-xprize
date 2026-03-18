# Code Patterns for Satellite Fire Detection

## Core Python Libraries

| Library | Purpose | Install |
|---------|---------|---------|
| `satpy` | Read and process satellite data from many formats | `pip install satpy` |
| `pyresample` | Reproject/resample satellite swath and area data | `pip install pyresample` |
| `pyspectral` | Spectral calculations, solar/thermal decomposition | `pip install pyspectral` |
| `pyorbital` | Orbital mechanics, overpass prediction, sun angles | `pip install pyorbital` |
| `himawari_api` | Download/query Himawari data from AWS | `pip install himawari_api` |
| `xarray` | N-dimensional labeled arrays (underlying Satpy data) | `pip install xarray` |
| `netCDF4` | Read NetCDF4/HDF5 satellite products | `pip install netCDF4` |
| `h5py` | Read HDF5 files directly | `pip install h5py` |
| `pyhdf` | Read HDF4 files (MODIS) | `pip install pyhdf` |
| `rioxarray` | GeoTIFF I/O with xarray | `pip install rioxarray` |
| `pystac_client` | STAC API client (Copernicus, others) | `pip install pystac-client` |
| `sentinelhub` | Sentinel Hub API client | `pip install sentinelhub` |
| `boto3` | AWS S3 access for NODD data | `pip install boto3` |

All of these belong to the **Pytroll** ecosystem (satpy, pyresample, pyspectral, pyorbital) or the standard geospatial Python stack.

## Reading Himawari AHI Data with Satpy

### From Himawari Standard Data (HSD) Files

```python
from satpy import Scene
from glob import glob

# HSD files have names like: HS_H09_20260401_0300_B07_FLDK_R20_S0110.DAT
files = glob("/data/himawari/HS_H09_20260401_0300_B*_FLDK_*.DAT")

scn = Scene(filenames=files, reader="ahi_hsd")

# Load fire-relevant bands as brightness temperature (default calibration)
scn.load(["B07", "B14", "B15"])

# Access as xarray DataArray
bt_3_9 = scn["B07"]   # Brightness temperature at 3.9 um
bt_11_2 = scn["B14"]  # Brightness temperature at 11.2 um

print(bt_3_9.attrs)   # Metadata including calibration, area definition
print(bt_3_9.shape)   # (5500, 5500) for full disk at 2 km
```

### Brightness Temperature Difference (Fire Signal)

```python
import numpy as np

# The core fire detection signal
delta_bt = bt_3_9 - bt_11_2

# Simple threshold-based fire candidate detection
fire_candidates = (bt_3_9 > 310) & (delta_bt > 10)  # Daytime thresholds
# Night: bt_3_9 > 295, delta_bt > 5

# Get lat/lon coordinates
lons, lats = bt_3_9.attrs["area"].get_lonlats()
```

### Resampling to a Regular Grid

```python
from pyresample import create_area_def

# Define an area over NSW
nsw_area = create_area_def(
    "nsw_fire",
    {"proj": "eqc", "ellps": "WGS84"},
    area_extent=[145.0, -38.0, 155.0, -28.0],  # [west, south, east, north]
    resolution=0.02,  # ~2 km in degrees
    units="degrees",
)

# Resample scene to NSW area
local = scn.resample(nsw_area, resampler="nearest")
bt_3_9_nsw = local["B07"]
```

## Reading VIIRS Data with Satpy

### From SDR (Sensor Data Record) Files

```python
from satpy import Scene
from glob import glob

# VIIRS SDR files (HDF5)
files = glob("/data/viirs/SVI04*.h5") + glob("/data/viirs/SVI05*.h5") + \
        glob("/data/viirs/GITCO*.h5")  # I-band geolocation

scn = Scene(filenames=files, reader="viirs_sdr")

# Load I-band channels
scn.load(["I04", "I05"])

bt_i4 = scn["I04"]   # 3.74 um BT
bt_i5 = scn["I05"]   # 11.45 um BT
```

### From VIIRS Active Fire Product (NetCDF4)

```python
import netCDF4 as nc
import numpy as np

# VNP14IMG -- VIIRS 375m active fire product
ds = nc.Dataset("/data/viirs/VNP14IMG.A2026091.0130.002.nc")

# Extract fire pixel data
fire_mask = ds.variables["fire mask"][:]
lats = ds.variables["FP_latitude"][:]
lons = ds.variables["FP_longitude"][:]
frp = ds.variables["FP_power"][:]
confidence = ds.variables["FP_confidence"][:]
bt_i4 = ds.variables["FP_T4"][:]
bt_i5 = ds.variables["FP_T5"][:]

# Filter for high confidence
high_conf = confidence >= 80  # nominal + high
fire_lats = lats[high_conf]
fire_lons = lons[high_conf]
fire_frp = frp[high_conf]
```

## Reading MODIS Fire Products

### HDF4 Format (MOD14/MYD14)

```python
from pyhdf.SD import SD, SDC
import numpy as np

# MOD14 -- MODIS fire product (HDF4)
hdf = SD("/data/modis/MOD14.A2026091.0130.061.hdf", SDC.READ)

fire_mask = hdf.select("fire mask")[:]
# Values: 0-2 not processed, 3 non-fire water, 4 cloud, 5 non-fire land,
#         6 unknown, 7 fire (low), 8 fire (nominal), 9 fire (high)

bt_21 = hdf.select("EV_Band21")[:]   # 3.96 um
bt_31 = hdf.select("EV_Band31")[:]   # 11.03 um

hdf.end()
```

### Via xarray (if converted to NetCDF4)

```python
import xarray as xr

ds = xr.open_dataset("/data/modis/MOD14.nc")
```

## FIRMS API Access

### Python Client

```python
import requests
import pandas as pd
from io import StringIO

MAP_KEY = "your_map_key_here"
SOURCE = "VIIRS_NOAA20_NRT"
BBOX = "148,-37,154,-28"  # NSW: west,south,east,north
DAYS = "1"

url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{BBOX}/{DAYS}"

response = requests.get(url)
if response.status_code == 200:
    df = pd.read_csv(StringIO(response.text))
    print(f"Found {len(df)} fire detections")
    print(df[["latitude", "longitude", "bright_ti4", "bright_ti5",
              "confidence", "frp", "acq_date", "acq_time"]].head())
```

### Polling Loop for Near-Real-Time Monitoring

```python
import time
import hashlib

def poll_firms(map_key, source, bbox, interval_seconds=300):
    """Poll FIRMS API for new fire detections."""
    seen_hashes = set()

    while True:
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/1"
        response = requests.get(url)

        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text))

            for _, row in df.iterrows():
                # Create unique hash for each detection
                row_hash = hashlib.md5(
                    f"{row['latitude']:.4f}_{row['longitude']:.4f}_{row['acq_date']}_{row['acq_time']}".encode()
                ).hexdigest()

                if row_hash not in seen_hashes:
                    seen_hashes.add(row_hash)
                    yield row  # New detection

        time.sleep(interval_seconds)
```

## AWS S3 Push-Based Ingestion (Himawari / VIIRS)

### Subscribe to SNS and Process via SQS

```python
import boto3
import json

# Create SQS queue and subscribe to Himawari SNS topic
sqs = boto3.client("sqs", region_name="us-east-1")
sns = boto3.client("sns", region_name="us-east-1")

# Create queue
queue = sqs.create_queue(QueueName="himawari-fire-detection")
queue_url = queue["QueueUrl"]
queue_arn = sqs.get_queue_attributes(
    QueueUrl=queue_url,
    AttributeNames=["QueueArn"]
)["Attributes"]["QueueArn"]

# Subscribe to Himawari-9 SNS topic
sns.subscribe(
    TopicArn="arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject",
    Protocol="sqs",
    Endpoint=queue_arn,
)

# Poll SQS for new data notifications
s3 = boto3.client("s3", region_name="us-east-1")

while True:
    messages = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,  # Long polling
    )

    for msg in messages.get("Messages", []):
        body = json.loads(msg["Body"])
        sns_message = json.loads(body["Message"])

        for record in sns_message.get("Records", []):
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]

            # Filter for fire-relevant bands (B07 = 3.9um)
            if "B07" in key and "FLDK" in key:
                # Download and process
                obj = s3.get_object(Bucket=bucket, Key=key)
                data = obj["Body"].read()
                process_fire_detection(data, key)

        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=msg["ReceiptHandle"],
        )
```

## Brightness Temperature Calculation from Raw Radiance

### Using Physical Constants

```python
import numpy as np

# Physical constants
h = 6.62607015e-34   # Planck constant (J*s)
c = 2.99792458e8     # Speed of light (m/s)
k_B = 1.380649e-23   # Boltzmann constant (J/K)

# Derived constants for radiance calculations
c1 = 2 * h * c**2    # 1.191e-16 W*m^2/sr
c2 = h * c / k_B     # 0.014388 m*K

def planck_radiance(wavelength_um, temperature_K):
    """Planck function: spectral radiance B(lambda, T).

    Args:
        wavelength_um: wavelength in micrometers
        temperature_K: temperature in Kelvin

    Returns:
        Spectral radiance in W/(m^2 sr um)
    """
    lam = wavelength_um * 1e-6  # Convert to meters
    exponent = c2 / (lam * temperature_K)
    # Clip to avoid overflow
    exponent = np.clip(exponent, 0, 500)
    radiance = c1 / (lam**5 * (np.exp(exponent) - 1))
    # Convert from W/(m^2 sr m) to W/(m^2 sr um)
    return radiance * 1e-6

def brightness_temperature(wavelength_um, radiance_W_m2_sr_um):
    """Invert Planck function to get brightness temperature.

    Args:
        wavelength_um: wavelength in micrometers
        radiance_W_m2_sr_um: spectral radiance in W/(m^2 sr um)

    Returns:
        Brightness temperature in Kelvin
    """
    lam = wavelength_um * 1e-6  # Convert to meters
    L = radiance_W_m2_sr_um * 1e6  # Convert to W/(m^2 sr m)
    T = c2 / (lam * np.log(1 + c1 / (lam**5 * L)))
    return T
```

### Sub-Pixel Fire Fraction Estimation

```python
def estimate_fire_fraction(bt_mir, bt_tir, bt_bg_mir, bt_bg_tir,
                           lambda_mir=3.9, lambda_tir=11.2):
    """Estimate sub-pixel fire fraction using bi-spectral method.

    Args:
        bt_mir: Observed MWIR brightness temperature (K)
        bt_tir: Observed TIR brightness temperature (K)
        bt_bg_mir: Background MWIR brightness temperature (K)
        bt_bg_tir: Background TIR brightness temperature (K)
        lambda_mir: MWIR wavelength (um)
        lambda_tir: TIR wavelength (um)

    Returns:
        Tuple of (fire_temperature_K, fire_fraction)
    """
    from scipy.optimize import fsolve

    L_mir_obs = planck_radiance(lambda_mir, bt_mir)
    L_tir_obs = planck_radiance(lambda_tir, bt_tir)
    L_mir_bg = planck_radiance(lambda_mir, bt_bg_mir)
    L_tir_bg = planck_radiance(lambda_tir, bt_bg_tir)

    def equations(vars):
        T_fire, p = vars
        L_mir_model = p * planck_radiance(lambda_mir, T_fire) + (1 - p) * L_mir_bg
        L_tir_model = p * planck_radiance(lambda_tir, T_fire) + (1 - p) * L_tir_bg
        return [L_mir_model - L_mir_obs, L_tir_model - L_tir_obs]

    # Initial guess: 800K fire, 0.001 fraction
    T_fire, p = fsolve(equations, [800, 0.001])

    return T_fire, max(0, min(1, p))
```

## Coordinate System Handling

### Himawari AHI (Fixed Grid)

AHI uses a **fixed grid** in geostationary projection. Each band's data is on a regular grid in satellite-relative coordinates (column, row), which maps to (longitude, latitude) via the geostationary projection.

```python
from pyresample import AreaDefinition

# Himawari full disk area definition (2 km bands)
himawari_area = AreaDefinition(
    "himawari_fldk",
    "Himawari Full Disk",
    "geos",
    {
        "proj": "geos",
        "lon_0": 140.7,       # Subsatellite longitude
        "h": 35785863,        # Satellite altitude (m)
        "x_0": 0,
        "y_0": 0,
        "a": 6378137,         # WGS84 semi-major axis
        "b": 6356752.3,       # WGS84 semi-minor axis
        "sweep": "y",         # Himawari uses y-axis sweep
    },
    5500, 5500,  # Grid size for 2 km bands
    (-5499999.901, -5499999.901, 5499999.901, 5499999.901),
)
```

**Note:** Himawari uses `sweep="y"` (Y-axis sweep), while GOES uses `sweep="x"`. This is a critical difference when computing projections.

### VIIRS (Swath Data)

VIIRS data comes as **swath granules** with embedded geolocation (lat/lon per pixel).

```python
# Satpy handles geolocation automatically via SwathDefinition
scn = Scene(filenames=viirs_files, reader="viirs_sdr")
scn.load(["I04"])

# The area attribute is a SwathDefinition
swath = scn["I04"].attrs["area"]
lons, lats = swath.get_lonlats()

# To resample to a regular grid:
from pyresample import create_area_def

target = create_area_def("nsw", {"proj": "eqc"}, resolution=0.005,
                          area_extent=[145, -38, 155, -28], units="degrees")
resampled = scn.resample(target)
```

### MODIS (Swath Data, HDF4)

Similar to VIIRS but in HDF4 format. Geolocation is in MOD03/MYD03 files.

```python
scn = Scene(filenames=modis_files, reader="modis_l1b")
scn.load(["21", "31"])  # Band 21 (3.96 um), Band 31 (11.03 um)
```

### Sentinel-2 (Tiled UTM)

Sentinel-2 data is delivered in UTM-projected tiles (100x100 km MGRS tiles).

```python
import rioxarray

# Each band is a separate GeoTIFF within the SAFE directory
b12 = rioxarray.open_rasterio(
    "/data/sentinel2/S2B_MSIL2A_.../R20m/B12.jp2"
)  # 20 m resolution, UTM projection

b11 = rioxarray.open_rasterio(
    "/data/sentinel2/S2B_MSIL2A_.../R20m/B11.jp2"
)

# Compute SWIR fire index
swir_ratio = (b12 - b11) / (b12 + b11)
```

## View Geometry Calculation

### Compute Himawari View Zenith Angle for a Ground Point

```python
import numpy as np

def himawari_vza(lat_deg, lon_deg, sat_lon=140.7, sat_height_km=35786):
    """Compute view zenith angle from Himawari to a ground point.

    Args:
        lat_deg: Ground point latitude (degrees)
        lon_deg: Ground point longitude (degrees)
        sat_lon: Subsatellite longitude (degrees)
        sat_height_km: Satellite altitude (km)

    Returns:
        View zenith angle in degrees
    """
    R_E = 6371.0  # Earth radius (km)

    lat = np.radians(lat_deg)
    dlon = np.radians(lon_deg - sat_lon)

    # Central angle between subsatellite point and ground point
    cos_gamma = np.cos(lat) * np.cos(dlon)
    gamma = np.arccos(np.clip(cos_gamma, -1, 1))

    # Distance from satellite to ground point
    H = sat_height_km + R_E
    d = np.sqrt(R_E**2 + H**2 - 2 * R_E * H * cos_gamma)

    # View zenith angle (at the ground point)
    sin_vza = (H / d) * np.sin(gamma)
    vza = np.arcsin(np.clip(sin_vza, -1, 1))

    return np.degrees(vza)

# Examples for NSW locations
locations = {
    "Sydney": (-33.87, 151.21),
    "Canberra": (-35.28, 149.13),
    "Melbourne": (-37.81, 144.96),
    "Brisbane": (-27.47, 153.03),
}

for name, (lat, lon) in locations.items():
    vza = himawari_vza(lat, lon)
    pixel_factor = 1 / np.cos(np.radians(vza))**2  # Approximate enlargement
    print(f"{name}: VZA = {vza:.1f} deg, pixel factor = {pixel_factor:.2f}x")
```

### VIIRS Overpass Prediction

```python
from pyorbital.orbital import Orbital
from datetime import datetime, timedelta

# Predict VIIRS (NOAA-20) overpasses for Sydney
orb = Orbital("NOAA 20")  # Uses TLE from Celestrak

# Get passes for next 24 hours
sydney_lat, sydney_lon, sydney_alt = -33.87, 151.21, 0.0
start_time = datetime(2026, 4, 1, 0, 0, 0)

passes = orb.get_next_passes(
    start_time,
    24,  # hours
    sydney_lon, sydney_lat, sydney_alt,
    horizon=5,  # minimum elevation (degrees)
)

for rise_time, max_elev_time, set_time, rise_az, max_elev, set_az in passes:
    print(f"Pass: {rise_time} to {set_time}, max elevation: {max_elev:.1f} deg")
```

## Putting It Together: Minimal Himawari Fire Detection Pipeline

```python
"""Minimal fire detection pipeline for Himawari AHI data."""

from satpy import Scene
from glob import glob
import numpy as np

def detect_fires_ahi(data_dir, bt_threshold_day=310, bt_threshold_night=295,
                     delta_bt_threshold=10, context_window=21):
    """Simple contextual fire detection on AHI full disk data.

    Returns list of (lat, lon, bt_3_9, delta_bt, confidence) tuples.
    """
    files = glob(f"{data_dir}/HS_H09_*_B07_FLDK_*.DAT") + \
            glob(f"{data_dir}/HS_H09_*_B14_FLDK_*.DAT")

    scn = Scene(filenames=files, reader="ahi_hsd")
    scn.load(["B07", "B14"])

    bt7 = scn["B07"].values    # 3.9 um BT
    bt14 = scn["B14"].values   # 11.2 um BT

    # Mask invalid data
    valid = np.isfinite(bt7) & np.isfinite(bt14)

    # Brightness temperature difference
    delta_bt = bt7 - bt14

    # Simple threshold (use night threshold as default)
    candidates = valid & (bt7 > bt_threshold_night) & (delta_bt > delta_bt_threshold)

    # Contextual test: compare each candidate to its local background
    fires = []
    area = scn["B07"].attrs["area"]
    lons, lats = area.get_lonlats()

    half_w = context_window // 2
    rows, cols = np.where(candidates)

    for r, c in zip(rows, cols):
        # Extract background window
        r0, r1 = max(0, r - half_w), min(bt7.shape[0], r + half_w + 1)
        c0, c1 = max(0, c - half_w), min(bt7.shape[1], c + half_w + 1)

        bg_mask = valid[r0:r1, c0:c1] & ~candidates[r0:r1, c0:c1]
        if bg_mask.sum() < 10:
            continue

        bg_bt7 = bt7[r0:r1, c0:c1][bg_mask]
        bg_delta = delta_bt[r0:r1, c0:c1][bg_mask]

        bt7_mean = np.mean(bg_bt7)
        bt7_mad = np.mean(np.abs(bg_bt7 - bt7_mean))
        delta_mean = np.mean(bg_delta)
        delta_mad = np.mean(np.abs(bg_delta - delta_mean))

        # Contextual thresholds
        if (bt7[r, c] > bt7_mean + max(3 * bt7_mad, 6)) and \
           (delta_bt[r, c] > delta_mean + max(3 * delta_mad, 4)):

            conf = "high" if bt7[r, c] > 360 else \
                   "nominal" if (bt7[r, c] - bt7_mean) > 15 else "low"

            fires.append({
                "lat": float(lats[r, c]),
                "lon": float(lons[r, c]),
                "bt_3_9": float(bt7[r, c]),
                "bt_11_2": float(bt14[r, c]),
                "delta_bt": float(delta_bt[r, c]),
                "confidence": conf,
            })

    return fires
```
