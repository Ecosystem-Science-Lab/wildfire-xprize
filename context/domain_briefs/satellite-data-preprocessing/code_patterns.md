# Code Patterns: satpy, pyresample, rasterio, s2cloudless

## 1. Satpy: Loading and Calibrating Satellite Data

### 1.1 Himawari AHI -- HSD to Brightness Temperature

```python
from satpy import Scene
from glob import glob

# Load AHI HSD files (all segments for a full disk scan)
filenames = glob('/data/himawari8/HS_H08_20260317_0300_B07_FLDK_R20_S*.DAT')
filenames += glob('/data/himawari8/HS_H08_20260317_0300_B13_FLDK_R20_S*.DAT')
filenames += glob('/data/himawari8/HS_H08_20260317_0300_B14_FLDK_R20_S*.DAT')

scn = Scene(filenames=filenames, reader='ahi_hsd')

# Load with brightness temperature calibration (default for IR bands)
scn.load(['B07', 'B13', 'B14'])

# Access data as dask arrays (lazy evaluation)
bt_39 = scn['B07']  # 3.9um brightness temperature
bt_103 = scn['B13']  # 10.3um brightness temperature

# Force computation
bt_39_values = bt_39.values  # numpy array, shape (5500, 5500) for full disk 2km

# Check units and calibration
print(bt_39.attrs['units'])          # 'K'
print(bt_39.attrs['calibration'])    # 'brightness_temperature'
print(bt_39.attrs['area'])           # AreaDefinition for geostationary projection
```

**Specifying calibration explicitly:**
```python
from satpy import DataQuery

# Load radiance instead of brightness temperature
scn.load([DataQuery(name='B07', calibration='radiance')])

# Load reflectance for visible bands
scn.load([DataQuery(name='B03', calibration='reflectance')])
```

**Using GSICS correction coefficients:**
```python
# Apply inter-calibration corrections (matches AHI to IASI)
scn = Scene(filenames=filenames, reader='ahi_hsd',
            reader_kwargs={'calib_mode': 'gsics'})
```

### 1.2 VIIRS SDR -- Loading Fire-Relevant Bands

```python
from satpy import Scene
from glob import glob

# VIIRS SDR files: need both imagery and geolocation files
sdr_files = glob('/data/viirs/SVI04*.h5')  # I4 band imagery
sdr_files += glob('/data/viirs/SVI05*.h5')  # I5 band imagery
sdr_files += glob('/data/viirs/GITCO*.h5')  # Terrain-corrected geolocation

scn = Scene(filenames=sdr_files, reader='viirs_sdr')

# Load I-band data (default calibration: brightness_temperature for IR)
scn.load(['I04', 'I05'])

bt_i4 = scn['I04']  # 3.74um, shape varies by granule (~6400 x 6400 per granule)
bt_i5 = scn['I05']  # 11.45um

# Access geolocation
lons = bt_i4.attrs['area'].lons  # dask array of longitudes
lats = bt_i4.attrs['area'].lats  # dask array of latitudes

# Check for bowtie-deleted pixels (fill values)
import numpy as np
valid_mask = np.isfinite(bt_i4.values)
print(f"Valid pixels: {valid_mask.sum()} / {valid_mask.size}")
```

### 1.3 GOES ABI L1b -- Reading and Converting

```python
from satpy import Scene
from glob import glob

abi_files = glob('/data/goes16/OR_ABI-L1b-RadF-M6C07*.nc')  # Band 7 (3.9um)
abi_files += glob('/data/goes16/OR_ABI-L1b-RadF-M6C13*.nc')  # Band 13 (10.3um)

scn = Scene(filenames=abi_files, reader='abi_l1b')
scn.load(['C07', 'C13'], calibration='brightness_temperature')

bt_39 = scn['C07']
bt_103 = scn['C13']
```

**Direct netCDF approach (without satpy):**
```python
import xarray as xr
import numpy as np

ds = xr.open_dataset('/data/goes16/OR_ABI-L1b-RadF-M6C07_G16_*.nc')

# Read radiance
rad = ds['Rad'].values  # radiance in mW/(m2 sr cm-1)

# Read Planck function constants (stored in the file)
fk1 = ds['planck_fk1'].values
fk2 = ds['planck_fk2'].values
bc1 = ds['planck_bc1'].values
bc2 = ds['planck_bc2'].values

# Convert radiance to brightness temperature
rad = np.clip(rad, 1e-10, None)  # avoid log(0)
bt = (fk2 / np.log(fk1 / rad + 1) - bc1) / bc2

# Result is in Kelvin
print(f"BT range: {np.nanmin(bt):.1f} - {np.nanmax(bt):.1f} K")
```

### 1.4 Listing Available Datasets

```python
from satpy import Scene

scn = Scene(filenames=filenames, reader='ahi_hsd')

# See what datasets are available
for ds_id in scn.available_dataset_ids():
    print(ds_id)

# See available composites (RGB combinations)
for comp in scn.available_composite_names():
    print(comp)
```

---

## 2. Pyresample: Geospatial Resampling

### 2.1 Swath to Grid (VIIRS to Uniform Grid)

```python
import numpy as np
from pyresample import geometry, kd_tree

# Source: VIIRS swath geometry
lons_viirs = bt_i4.attrs['area'].lons.values  # from satpy Scene
lats_viirs = bt_i4.attrs['area'].lats.values
swath_def = geometry.SwathDefinition(lons=lons_viirs, lats=lats_viirs)

# Target: uniform lat/lon grid over Australia
area_def = geometry.AreaDefinition(
    'australia_fire',
    'Australia fire detection grid',
    'australia_fire',
    {'proj': 'longlat', 'datum': 'WGS84'},
    3600,  # width (pixels)
    2400,  # height (pixels)
    [110.0, -45.0, 155.0, -10.0]  # extent: [min_lon, min_lat, max_lon, max_lat]
)

# Resample using nearest neighbor
result = kd_tree.resample_nearest(
    swath_def,
    bt_i4.values,
    area_def,
    radius_of_influence=5000,  # meters -- max distance to look for source pixel
    epsilon=0.5,               # approximation factor (0=exact, higher=faster)
    fill_value=np.nan
)
# result shape: (2400, 3600)
```

### 2.2 Resampling with Satpy (Higher-Level)

```python
# After loading data with satpy Scene
scn.load(['I04', 'I05'])

# Resample to a named area or custom AreaDefinition
from pyresample import create_area_def

australia_area = create_area_def(
    'australia',
    {'proj': 'longlat', 'datum': 'WGS84'},
    area_extent=[110.0, -45.0, 155.0, -10.0],
    resolution=0.01  # degrees (~1km)
)

resampled = scn.resample(australia_area, resampler='nearest', radius_of_influence=5000)

# Access resampled data
bt_i4_grid = resampled['I04'].values
```

### 2.3 Grid to Grid (Reprojecting Geostationary to Lat/Lon)

```python
# AHI data is in geostationary projection -- resample to lat/lon
scn.load(['B07'])

# Satpy knows the source projection from the data
resampled = scn.resample(australia_area)
bt_ahi_grid = resampled['B07'].values
```

### 2.4 Caching Resampling Indices

For repeated resampling of the same geometry (e.g., every 10 minutes for Himawari):

```python
from pyresample import kd_tree

# Pre-compute resampling indices (do once)
valid_input, valid_output, index_array, distance_array = kd_tree.get_neighbour_info(
    swath_def, area_def,
    radius_of_influence=5000,
    neighbours=1
)

# Apply resampling (do every time)
result = kd_tree.get_sample_from_neighbour_info(
    'nn',  # nearest neighbor
    area_def.shape,
    bt_i4.values,
    valid_input, valid_output,
    index_array,
    fill_value=np.nan
)
```

For geostationary data with a fixed viewing geometry, the indices only need to be computed once and can be reused for every subsequent scan.

---

## 3. Rasterio: GeoTIFF I/O and Reprojection

### 3.1 Reading Landsat Thermal Bands

```python
import rasterio
import numpy as np

# Read Band 10 (thermal)
with rasterio.open('/data/landsat/LC08_L1TP_091084_20260315_B10.TIF') as src:
    dn = src.read(1).astype(np.float32)
    profile = src.profile
    transform = src.transform
    crs = src.crs

# Read calibration coefficients from MTL
# (parse MTL.txt or use a library like landsat-util)
M_L = 3.3420E-04    # RADIANCE_MULT_BAND_10
A_L = 0.10000       # RADIANCE_ADD_BAND_10
K1 = 774.8853       # K1_CONSTANT_BAND_10
K2 = 1321.0789      # K2_CONSTANT_BAND_10

# DN to TOA radiance
radiance = M_L * dn + A_L

# Radiance to brightness temperature
bt = K2 / np.log(K1 / radiance + 1)

# Mask no-data
bt[dn == 0] = np.nan
```

### 3.2 Applying a Land/Water Mask

```python
import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np

# Read land/water mask
with rasterio.open('/data/ancillary/MOD44W_australia.tif') as mask_src:
    water_mask = mask_src.read(1)
    mask_profile = mask_src.profile

# If mask has different CRS/resolution than your data, reproject
with rasterio.open('/data/landsat/LC08_B10.TIF') as data_src:
    # Create empty array matching data dimensions
    aligned_mask = np.empty(
        (data_src.height, data_src.width),
        dtype=water_mask.dtype
    )

    reproject(
        source=water_mask,
        destination=aligned_mask,
        src_transform=mask_profile['transform'],
        src_crs=mask_profile['crs'],
        dst_transform=data_src.transform,
        dst_crs=data_src.crs,
        resampling=Resampling.nearest
    )

# Apply mask: set water pixels to NaN
is_water = aligned_mask == 1  # MOD44W: 1=water, 0=land
bt[is_water] = np.nan
```

### 3.3 Reprojecting Between CRS

```python
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

dst_crs = 'EPSG:32755'  # UTM Zone 55S (NSW, Australia)

with rasterio.open('input.tif') as src:
    transform, width, height = calculate_default_transform(
        src.crs, dst_crs, src.width, src.height, *src.bounds
    )

    kwargs = src.profile.copy()
    kwargs.update({
        'crs': dst_crs,
        'transform': transform,
        'width': width,
        'height': height
    })

    with rasterio.open('output_utm.tif', 'w', **kwargs) as dst:
        for i in range(1, src.count + 1):
            reproject(
                source=rasterio.band(src, i),
                destination=rasterio.band(dst, i),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest
            )
```

### 3.4 Writing Fire Detection Results to GeoTIFF

```python
import rasterio
import numpy as np

# Assume fire_mask is a 2D boolean array aligned with your input raster
fire_mask = (bt_i4 > 325) & (bt_i4 - bt_i5 > 10)  # simplified example

with rasterio.open('fire_detections.tif', 'w',
                   driver='GTiff',
                   height=fire_mask.shape[0],
                   width=fire_mask.shape[1],
                   count=1,
                   dtype='uint8',
                   crs=crs,
                   transform=transform,
                   compress='deflate') as dst:
    dst.write(fire_mask.astype(np.uint8), 1)
```

---

## 4. s2cloudless: Cloud Detection for Sentinel-2

### 4.1 Basic Usage

```python
from s2cloudless import S2PixelCloudDetector
import numpy as np

# Initialize detector
cloud_detector = S2PixelCloudDetector(
    threshold=0.4,       # cloud probability threshold
    average_over=4,      # averaging window size
    dilation_size=2,     # morphological dilation radius
    all_bands=True       # use all 13 bands (False = use 10 bands)
)

# Prepare input: shape must be (n_images, height, width, n_bands)
# Required bands (in order): B01, B02, B04, B05, B08, B8A, B09, B10, B11, B12
# Values must be in [0, 1] range (divide by 10000 for Sentinel-2 L1C)

# Read bands with rasterio
import rasterio
band_names = ['B01', 'B02', 'B04', 'B05', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12']
bands = []
for b in band_names:
    with rasterio.open(f'/data/sentinel2/{b}.jp2') as src:
        data = src.read(1).astype(np.float32) / 10000.0
        bands.append(data)

# Stack and reshape: (1, H, W, 10)
input_data = np.stack(bands, axis=-1)[np.newaxis, ...]

# Get cloud probability map
cloud_probs = cloud_detector.get_cloud_probability_maps(input_data)
# shape: (1, H, W), values in [0, 1]

# Get binary cloud mask
cloud_mask = cloud_detector.get_cloud_masks(input_data)
# shape: (1, H, W), values: 0 (clear) or 1 (cloud)
```

### 4.2 Handling Multi-Resolution Bands

Sentinel-2 bands have different resolutions (10m, 20m, 60m). s2cloudless needs all bands at the same resolution.

```python
from rasterio.warp import reproject, Resampling
import rasterio
import numpy as np

target_resolution = 60  # meters -- use lowest resolution for speed

def read_and_resample(filepath, target_shape):
    """Read a band and resample to target shape."""
    with rasterio.open(filepath) as src:
        data = src.read(1, out_shape=target_shape, resampling=Resampling.bilinear)
    return data.astype(np.float32) / 10000.0

# Get target shape from 60m band
with rasterio.open('/data/sentinel2/B01.jp2') as src:
    target_shape = (src.height, src.width)

# Read all bands at 60m resolution
bands = []
for b in ['B01', 'B02', 'B04', 'B05', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12']:
    bands.append(read_and_resample(f'/data/sentinel2/{b}.jp2', target_shape))

input_data = np.stack(bands, axis=-1)[np.newaxis, ...]
```

### 4.3 Using Sentinel-2 SCL (Scene Classification Layer) Instead

If processing L2A data, the SCL band provides a pre-computed classification:

```python
import rasterio

with rasterio.open('/data/sentinel2/SCL.jp2') as src:
    scl = src.read(1)

# SCL classes relevant to fire detection:
# 0: No data
# 3: Cloud shadow
# 7: Unclassified  (could be smoke)
# 8: Cloud medium probability
# 9: Cloud high probability
# 10: Thin cirrus

cloud_mask = np.isin(scl, [8, 9, 10])
shadow_mask = scl == 3
clear_mask = np.isin(scl, [4, 5, 6])  # 4=vegetation, 5=bare soil, 6=water
```

---

## 5. Complete Pipeline Example: Himawari Fire Detection

```python
"""
Minimal preprocessing pipeline for Himawari-8 AHI fire detection.
Processes a single 10-minute full-disk scan.
"""
import numpy as np
from satpy import Scene
from glob import glob
import time

def preprocess_himawari_for_fire(data_dir, timestamp, land_water_mask_path):
    """
    Args:
        data_dir: directory containing HSD files
        timestamp: e.g., '20260317_0300'
        land_water_mask_path: path to pre-computed land/water mask GeoTIFF

    Returns:
        dict with bt_39, bt_103, bt_112, cloud_mask, land_mask, lons, lats
    """
    t0 = time.time()

    # --- Step 1: Load and calibrate ---
    pattern = f'{data_dir}/HS_H08_{timestamp}_B*_FLDK_R20_S*.DAT'
    filenames = glob(pattern)

    scn = Scene(filenames=filenames, reader='ahi_hsd')
    scn.load(['B07', 'B13', 'B14'])  # 3.9um, 10.3um, 11.2um

    bt_39 = scn['B07'].values    # brightness temperature, K
    bt_103 = scn['B13'].values
    bt_112 = scn['B14'].values

    # Get geolocation
    area = scn['B07'].attrs['area']
    lons, lats = area.get_lonlats()

    t1 = time.time()
    print(f"Load + calibrate: {t1-t0:.1f}s")

    # --- Step 2: Cloud masking (fast spectral tests) ---
    cloud_mask = np.zeros_like(bt_103, dtype=bool)

    # Cold cloud test
    cloud_mask |= bt_103 < 265.0

    # Cirrus / semi-transparent cloud (split window)
    cloud_mask |= (bt_103 - bt_112) > 2.5

    # Warm low cloud (3.9 - 10.3 difference, daytime only)
    solar_zenith = 90 - np.abs(lats)  # rough approximation; use pyorbital for accurate
    is_day = solar_zenith < 85
    cloud_mask |= is_day & ((bt_39 - bt_103) > 20.0)

    # Spatial uniformity (high BT variance = cloud edges)
    from scipy.ndimage import uniform_filter
    bt_mean = uniform_filter(bt_103, size=5)
    bt_sq_mean = uniform_filter(bt_103**2, size=5)
    bt_std = np.sqrt(np.maximum(bt_sq_mean - bt_mean**2, 0))
    cloud_mask |= bt_std > 4.0

    t2 = time.time()
    print(f"Cloud masking: {t2-t1:.1f}s")

    # --- Step 3: Land/water masking ---
    # Pre-computed mask aligned to AHI grid (do alignment once, save result)
    import rasterio
    with rasterio.open(land_water_mask_path) as src:
        land_mask = src.read(1).astype(bool)  # True = land

    t3 = time.time()
    print(f"Land/water mask: {t3-t2:.1f}s")

    # --- Step 4: Mask invalid data ---
    valid = np.isfinite(bt_39) & np.isfinite(bt_103) & np.isfinite(bt_112)

    return {
        'bt_39': bt_39,
        'bt_103': bt_103,
        'bt_112': bt_112,
        'cloud_mask': cloud_mask,
        'land_mask': land_mask,
        'valid': valid,
        'lons': lons,
        'lats': lats,
        'is_day': is_day,
        'timestamp': timestamp,
    }


def detect_fires_contextual(preprocessed, window_size=21):
    """
    Simple contextual fire detection on preprocessed AHI data.
    Based on MOD14/VNP14 approach adapted for geostationary.
    """
    bt_39 = preprocessed['bt_39']
    bt_103 = preprocessed['bt_103']
    cloud = preprocessed['cloud_mask']
    land = preprocessed['land_mask']
    valid = preprocessed['valid']
    is_day = preprocessed['is_day']

    delta_t = bt_39 - bt_103

    # Absolute threshold test (candidate selection)
    candidates_day = is_day & (bt_39 > 325.0) & land & ~cloud & valid
    candidates_night = ~is_day & (bt_39 > 310.0) & land & ~cloud & valid
    candidates = candidates_day | candidates_night

    # Background statistics (mean and stdev of non-fire, non-cloud land pixels)
    from scipy.ndimage import uniform_filter

    # Create background mask (valid land, not cloud, not candidate)
    bg_mask = land & ~cloud & valid & ~candidates
    bg_bt39 = np.where(bg_mask, bt_39, np.nan)
    bg_delta = np.where(bg_mask, delta_t, np.nan)

    # Compute local mean and std (ignoring NaN would be ideal;
    # uniform_filter doesn't handle NaN, so use a workaround)
    bg_bt39_filled = np.where(bg_mask, bt_39, 0)
    bg_count = uniform_filter(bg_mask.astype(float), size=window_size)
    bg_count = np.maximum(bg_count, 1e-10)

    bg_mean_39 = uniform_filter(bg_bt39_filled, size=window_size) / bg_count
    bg_var_39 = uniform_filter(bg_bt39_filled**2, size=window_size) / bg_count - bg_mean_39**2
    bg_std_39 = np.sqrt(np.maximum(bg_var_39, 0))

    bg_delta_filled = np.where(bg_mask, delta_t, 0)
    bg_mean_delta = uniform_filter(bg_delta_filled, size=window_size) / bg_count
    bg_var_delta = uniform_filter(bg_delta_filled**2, size=window_size) / bg_count - bg_mean_delta**2
    bg_std_delta = np.sqrt(np.maximum(bg_var_delta, 0))

    # Contextual tests
    enough_bg = (bg_count * window_size**2) >= 10  # at least 10 valid background pixels

    fire_mask = candidates & enough_bg & (
        (bt_39 > bg_mean_39 + 3 * bg_std_39) &
        (delta_t > bg_mean_delta + 3 * bg_std_delta) &
        (bt_39 > bg_mean_39 + 6)  # minimum absolute difference
    )

    return fire_mask
```

---

## 6. Utility: Brightness Temperature Conversion (No Satpy)

For cases where you want to avoid the satpy dependency:

```python
import numpy as np

def planck_bt(radiance, wavelength_um):
    """Convert spectral radiance to brightness temperature using Planck function.

    Args:
        radiance: spectral radiance in W/m^2/sr/um
        wavelength_um: central wavelength in micrometers

    Returns:
        brightness temperature in Kelvin
    """
    h = 6.62607015e-34   # Planck constant (J*s)
    c = 2.99792458e8     # speed of light (m/s)
    k = 1.380649e-23     # Boltzmann constant (J/K)

    wl = wavelength_um * 1e-6  # convert to meters

    # Convert radiance from W/m^2/sr/um to W/m^2/sr/m
    rad_si = radiance * 1e6

    # Inverse Planck function
    bt = (h * c / (k * wl)) / np.log(1 + (2 * h * c**2) / (rad_si * wl**5))

    return bt


def goes_abi_rad_to_bt(radiance, fk1, fk2, bc1, bc2):
    """Convert GOES ABI radiance to brightness temperature.

    All constants come from the L1b netCDF file.
    Radiance units: mW/(m^2 sr cm^-1)
    """
    radiance = np.clip(radiance, 1e-10, None)
    return (fk2 / np.log(fk1 / radiance + 1) - bc1) / bc2


def landsat_dn_to_bt(dn, M_L, A_L, K1, K2):
    """Convert Landsat DN to brightness temperature.

    All constants from MTL.txt metadata file.
    """
    radiance = M_L * dn + A_L
    radiance = np.clip(radiance, 1e-10, None)
    return K2 / np.log(K1 / radiance + 1)
```

---

## 7. Downloading Data from AWS (No Credentials)

```python
import s3fs
from datetime import datetime

def list_himawari_files(dt, band=7):
    """List Himawari-8 HSD files on AWS for a given datetime and band."""
    fs = s3fs.S3FileSystem(anon=True)

    path = f"noaa-himawari8/AHI-L1b-FLDK/{dt.year}/{dt.month:02d}/{dt.day:02d}/"
    path += f"{dt.hour:02d}{(dt.minute // 10) * 10:02d}/"

    # List files matching band
    band_str = f"B{band:02d}"
    files = [f for f in fs.ls(path) if band_str in f]
    return files


def download_himawari_band(dt, band, local_dir):
    """Download all segments for a band."""
    fs = s3fs.S3FileSystem(anon=True)
    files = list_himawari_files(dt, band)

    for f in files:
        local_path = f"{local_dir}/{f.split('/')[-1]}"
        fs.get(f, local_path)

    return len(files)


def list_goes_files(dt, satellite=16, band=7, product='RadF'):
    """List GOES ABI L1b files on AWS."""
    fs = s3fs.S3FileSystem(anon=True)

    doy = dt.timetuple().tm_yday
    path = f"noaa-goes{satellite}/ABI-L1b-{product}/{dt.year}/{doy:03d}/{dt.hour:02d}/"

    band_str = f"C{band:02d}"
    files = [f for f in fs.ls(path) if band_str in f]
    return files
```
