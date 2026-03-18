# Code Patterns for Historical Fire Data

## 1. FIRMS API: Download Active Fire Data

### Basic FIRMS API Query

```python
import requests
import pandas as pd
from io import StringIO

MAP_KEY = "your_map_key_here"  # Get from https://firms.modaps.eosdis.nasa.gov/api/map_key/
BASE_URL = "https://firms.modaps.eosdis.nasa.gov"

def get_firms_data(source: str, bbox: str, day_range: int, date: str = None) -> pd.DataFrame:
    """
    Download FIRMS active fire data for a bounding box.

    Args:
        source: e.g. 'VIIRS_NOAA20_NRT', 'VIIRS_SNPP_SP', 'MODIS_SP'
        bbox: 'west,south,east,north' e.g. '148,-38,154,-28' for NSW
        day_range: 1-5 days per query
        date: 'YYYY-MM-DD' or None for most recent
    """
    if date:
        url = f"{BASE_URL}/api/area/csv/{MAP_KEY}/{source}/{bbox}/{day_range}/{date}"
    else:
        url = f"{BASE_URL}/api/area/csv/{MAP_KEY}/{source}/{bbox}/{day_range}"

    response = requests.get(url)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))
    return df


# Example: Get NSW VIIRS NOAA-20 fires for 5 days around Black Summer peak
df = get_firms_data(
    source="VIIRS_NOAA20_SP",
    bbox="148,-38,154,-28",
    day_range=5,
    date="2020-01-01"
)

print(f"Found {len(df)} fire detections")
print(df[['latitude', 'longitude', 'bright_ti4', 'confidence', 'frp', 'acq_date']].head())
```

### Batch Download: Full Date Range

```python
from datetime import datetime, timedelta
import time

def download_firms_date_range(
    source: str,
    bbox: str,
    start_date: str,
    end_date: str,
    output_dir: str = "firms_data"
) -> pd.DataFrame:
    """Download FIRMS data across a date range in 5-day chunks."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    all_data = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current < end:
        remaining = (end - current).days
        day_range = min(5, remaining)
        if day_range < 1:
            break

        date_str = current.strftime("%Y-%m-%d")
        print(f"Fetching {source} for {date_str} + {day_range} days...")

        try:
            df = get_firms_data(source, bbox, day_range, date_str)
            if len(df) > 0:
                all_data.append(df)
                df.to_csv(f"{output_dir}/{source}_{date_str}.csv", index=False)
        except Exception as e:
            print(f"Error for {date_str}: {e}")

        current += timedelta(days=day_range)
        time.sleep(1)  # Respect rate limits

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined.to_csv(f"{output_dir}/{source}_combined.csv", index=False)
        return combined
    return pd.DataFrame()


# Download all NSW Black Summer detections
df_all = download_firms_date_range(
    source="VIIRS_SNPP_SP",
    bbox="148,-38,154,-28",
    start_date="2019-07-01",
    end_date="2020-06-30"
)
```

### Filter by Confidence

```python
def filter_firms_quality(df: pd.DataFrame, sensor: str = "viirs") -> pd.DataFrame:
    """
    Filter FIRMS data to high-quality detections only.

    VIIRS confidence is categorical: 'low', 'nominal', 'high'
    MODIS confidence is numeric: 0-100
    """
    if sensor == "viirs":
        # Keep only nominal and high confidence
        mask = df['confidence'].isin(['nominal', 'high', 'n', 'h'])
        filtered = df[mask].copy()
    elif sensor == "modis":
        # Keep confidence >= 30 (nominal threshold)
        filtered = df[df['confidence'] >= 30].copy()
        # Optional: vegetation fires only (type=0)
        if 'type' in filtered.columns:
            filtered = filtered[filtered['type'] == 0]

    print(f"Filtered: {len(df)} -> {len(filtered)} detections")
    return filtered
```

## 2. Google Earth Engine: Fire Data Processing

### Setup and Authentication

```python
import ee

# First time: authenticate
ee.Authenticate()  # Opens browser for OAuth

# Initialize with a project
ee.Initialize(project='your-gee-project-id')
```

### Query MCD64A1 Burned Area

```python
def get_burned_area_gee(region_geojson: dict, start_date: str, end_date: str):
    """
    Get MCD64A1 burned area data for a region and time period.

    Args:
        region_geojson: GeoJSON geometry dict
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'
    """
    region = ee.Geometry(region_geojson)

    mcd64 = (ee.ImageCollection('MODIS/061/MCD64A1')
             .filterDate(start_date, end_date)
             .filterBounds(region))

    # Get burn dates (0 = unburned, 1-366 = Julian day)
    burn_dates = mcd64.select('BurnDate')

    # Mosaic all months, keeping latest burn date
    burn_mosaic = burn_dates.max().clip(region)

    # Create binary burned mask (any pixel with BurnDate > 0)
    burned_mask = burn_mosaic.gt(0)

    # Compute burned area in hectares
    area = burned_mask.multiply(ee.Image.pixelArea()).divide(10000)
    total_area = area.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=500,
        maxPixels=1e13
    )

    return burn_mosaic, burned_mask, total_area


# NSW bounding box as GeoJSON
nsw_bbox = {
    "type": "Polygon",
    "coordinates": [[[141, -38], [154, -38], [154, -28], [141, -28], [141, -38]]]
}

burn_img, mask, area = get_burned_area_gee(nsw_bbox, '2019-07-01', '2020-06-30')
print(f"Total burned area: {area.getInfo()} hectares")
```

### Query FIRMS Vector Data from Community Catalog

```python
def get_firms_vectors_gee(year: int, region: ee.Geometry,
                          sensor: str = "viirs") -> ee.FeatureCollection:
    """
    Load FIRMS fire detections as vector points from GEE community catalog.

    Args:
        year: Year of data (VIIRS: 2012-2021, MODIS: 2000-2020)
        region: ee.Geometry to filter
        sensor: 'viirs' or 'modis'
    """
    if sensor == "viirs":
        path = f"projects/sat-io/open-datasets/VIIRS/VNP14IMGTDL_NRT_{year}"
    else:
        path = f"projects/sat-io/open-datasets/MODIS_MCD14DL/MCD14DL_{year}"

    fc = ee.FeatureCollection(path)

    # Filter to region
    fc_filtered = fc.filterBounds(region)

    return fc_filtered


# Get 2020 VIIRS detections for NSW
nsw_geom = ee.Geometry.Rectangle([141, -38, 154, -28])
fires_2020 = get_firms_vectors_gee(2020, nsw_geom, sensor="viirs")
print(f"Fire count: {fires_2020.size().getInfo()}")
```

### Sentinel-2 NBR/dNBR Burn Severity

```python
def compute_dnbr(region: ee.Geometry, pre_start: str, pre_end: str,
                 post_start: str, post_end: str) -> ee.Image:
    """
    Compute differenced NBR (dNBR) from Sentinel-2 pre/post fire imagery.

    Higher dNBR = more severe burn.
    """
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')

    def add_nbr(image):
        nbr = image.normalizedDifference(['B8A', 'B12']).rename('NBR')
        return image.addBands(nbr)

    # Cloud masking using SCL band
    def mask_clouds(image):
        scl = image.select('SCL')
        mask = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return image.updateMask(mask)

    # Pre-fire composite
    pre = (s2.filterBounds(region)
           .filterDate(pre_start, pre_end)
           .map(mask_clouds)
           .map(add_nbr)
           .select('NBR')
           .median()
           .clip(region))

    # Post-fire composite
    post = (s2.filterBounds(region)
            .filterDate(post_start, post_end)
            .map(mask_clouds)
            .map(add_nbr)
            .select('NBR')
            .median()
            .clip(region))

    # dNBR = pre_NBR - post_NBR
    dnbr = pre.subtract(post).rename('dNBR')

    return dnbr


# Example: Gospers Mountain fire (NSW Blue Mountains)
gospers = ee.Geometry.Rectangle([149.5, -33.5, 150.5, -32.5])
dnbr = compute_dnbr(
    gospers,
    pre_start='2019-06-01', pre_end='2019-09-30',
    post_start='2020-02-01', post_end='2020-04-30'
)

# Classify severity
# dNBR thresholds (Key & Benson, 2006):
# < 0.1: Unburned
# 0.1-0.27: Low severity
# 0.27-0.44: Moderate-low
# 0.44-0.66: Moderate-high
# > 0.66: High severity
```

### Export from GEE to Google Drive

```python
def export_to_drive(image: ee.Image, region: ee.Geometry,
                    description: str, scale: int = 500):
    """Export a GEE image to Google Drive."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        region=region,
        scale=scale,
        crs='EPSG:4326',
        maxPixels=1e13,
        fileFormat='GeoTIFF'
    )
    task.start()
    print(f"Export started: {description}")
    return task


# Export burned area map
export_to_drive(mask, nsw_geom, 'nsw_burned_2019_2020', scale=500)
```

## 3. Copernicus CDS: Fire Danger Indices

### Setup

```bash
pip install cdsapi
```

Create `~/.cdsapirc`:
```
url: https://cds.climate.copernicus.eu/api
key: YOUR_UID:YOUR_API_KEY
```

### Download Fire Danger Data

```python
import cdsapi

def download_fire_danger(year: int, months: list, output_file: str):
    """
    Download CEMS fire danger indices from Copernicus CDS.

    Includes: FWI, FFMC, DMC, DC, ISI, BUI, and FFDI (Australia-specific).
    """
    c = cdsapi.Client()

    c.retrieve(
        'cems-fire-historical-v1',
        {
            'product_type': 'reanalysis',
            'variable': [
                'fire_weather_index',
                'fine_fuel_moisture_code',
                'duff_moisture_code',
                'drought_code',
                'initial_spread_index',
                'buildup_index',
                'fire_daily_severity_rating',
            ],
            'year': str(year),
            'month': [str(m).zfill(2) for m in months],
            'day': [str(d).zfill(2) for d in range(1, 32)],
            'dataset_version': 'v4.0',  # Check for latest version
            'format': 'netcdf',
        },
        output_file
    )
    print(f"Downloaded to {output_file}")


# Download Black Summer fire weather
download_fire_danger(2019, [10, 11, 12], 'fire_danger_2019_OND.nc')
download_fire_danger(2020, [1, 2, 3], 'fire_danger_2020_JFM.nc')
```

### Download ERA5 Weather Data

```python
def download_era5_fire_weather(year: int, months: list,
                                bbox: list, output_file: str):
    """
    Download ERA5 variables relevant to fire weather.

    bbox: [north, west, south, east] e.g. [-28, 141, -38, 154] for NSW
    """
    c = cdsapi.Client()

    c.retrieve(
        'reanalysis-era5-single-levels',
        {
            'product_type': 'reanalysis',
            'variable': [
                '2m_temperature',
                '2m_dewpoint_temperature',
                '10m_u_component_of_wind',
                '10m_v_component_of_wind',
                'total_precipitation',
                'surface_solar_radiation_downwards',
            ],
            'year': str(year),
            'month': [str(m).zfill(2) for m in months],
            'day': [str(d).zfill(2) for d in range(1, 32)],
            'time': ['06:00', '12:00', '18:00'],  # Key fire weather times
            'area': bbox,  # [N, W, S, E]
            'format': 'netcdf',
        },
        output_file
    )


download_era5_fire_weather(
    2019, [12],
    [-28, 141, -38, 154],  # NSW
    'era5_nsw_dec2019.nc'
)
```

## 4. AppEEARS API: Download MCD64A1

```python
import requests
import json
import time
import os

APPEEARS_API = "https://appeears.earthdatacloud.nasa.gov/api"

class AppEEARSClient:
    def __init__(self, username: str, password: str):
        """Authenticate with Earthdata credentials."""
        response = requests.post(
            f"{APPEEARS_API}/login",
            auth=(username, password)
        )
        response.raise_for_status()
        self.token = response.json()['token']
        self.headers = {'Authorization': f'Bearer {self.token}'}

    def submit_area_request(self, task_name: str, geojson: dict,
                            product: str, layers: list,
                            start_date: str, end_date: str) -> str:
        """
        Submit an area extraction request.

        Args:
            product: e.g. 'MCD64A1.061'
            layers: e.g. ['BurnDate', 'Uncertainty']
        """
        task = {
            'task_type': 'area',
            'task_name': task_name,
            'params': {
                'dates': [
                    {'startDate': start_date, 'endDate': end_date}
                ],
                'layers': [
                    {'product': product, 'layer': layer}
                    for layer in layers
                ],
                'geo': geojson,
                'output': {
                    'format': {'type': 'geotiff'},
                    'projection': 'geographic'
                }
            }
        }

        response = requests.post(
            f"{APPEEARS_API}/task",
            json=task,
            headers=self.headers
        )
        response.raise_for_status()
        task_id = response.json()['task_id']
        print(f"Submitted task: {task_id}")
        return task_id

    def wait_for_task(self, task_id: str, poll_interval: int = 30):
        """Poll task status until completion."""
        while True:
            response = requests.get(
                f"{APPEEARS_API}/task/{task_id}",
                headers=self.headers
            )
            status = response.json()['status']
            print(f"Task {task_id}: {status}")

            if status == 'done':
                return True
            elif status == 'error':
                raise RuntimeError(f"Task failed: {response.json()}")

            time.sleep(poll_interval)

    def download_files(self, task_id: str, output_dir: str):
        """Download all files from a completed task."""
        os.makedirs(output_dir, exist_ok=True)

        response = requests.get(
            f"{APPEEARS_API}/bundle/{task_id}",
            headers=self.headers
        )
        files = response.json()['files']

        for f in files:
            file_id = f['file_id']
            filename = f['file_name']
            filepath = os.path.join(output_dir, filename)

            dl_response = requests.get(
                f"{APPEEARS_API}/bundle/{task_id}/{file_id}",
                headers=self.headers,
                allow_redirects=True
            )

            with open(filepath, 'wb') as out:
                out.write(dl_response.content)
            print(f"Downloaded: {filename}")


# Usage
client = AppEEARSClient("earthdata_username", "earthdata_password")

nsw_geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[141, -38], [154, -38], [154, -28], [141, -28], [141, -38]]]
        }
    }]
}

task_id = client.submit_area_request(
    task_name="NSW_BurnedArea_BlackSummer",
    geojson=nsw_geojson,
    product="MCD64A1.061",
    layers=["BurnDate", "Uncertainty", "QA"],
    start_date="07-01-2019",
    end_date="06-30-2020"
)

client.wait_for_task(task_id)
client.download_files(task_id, "appeears_output/nsw_burned")
```

## 5. GFED5: Read and Process NetCDF

```python
import xarray as xr
import numpy as np

def load_gfed5_burned_area(filepath: str, lat_range: tuple = None,
                            lon_range: tuple = None) -> xr.Dataset:
    """
    Load GFED5 monthly burned area data.

    Args:
        filepath: Path to GFED5 NetCDF file
        lat_range: (min_lat, max_lat) e.g. (-38, -28) for NSW
        lon_range: (min_lon, max_lon) e.g. (141, 154) for NSW
    """
    ds = xr.open_dataset(filepath)

    if lat_range:
        ds = ds.sel(lat=slice(*lat_range))
    if lon_range:
        ds = ds.sel(lon=slice(*lon_range))

    return ds


def compute_annual_burned_area(ds: xr.Dataset, year: int) -> xr.DataArray:
    """Sum monthly burned area fractions for a given year."""
    annual = ds['burned_area'].sel(time=str(year)).sum(dim='time')
    return annual


# Load and analyze
ds = load_gfed5_burned_area(
    'GFED5.1_monthly_burned_area.nc',
    lat_range=(-38, -28),
    lon_range=(141, 154)
)

# Compare Black Summer to previous years
for year in range(2015, 2021):
    annual = compute_annual_burned_area(ds, year)
    total = float(annual.sum())
    print(f"{year}: {total:.4f} burned fraction")
```

## 6. NSW Fire History: Load and Process Shapefiles

```python
import geopandas as gpd

def load_nsw_fire_history(shapefile_path: str) -> gpd.GeoDataFrame:
    """
    Load NPWS fire history shapefile.

    Fields include: FireType (1=Wildfire, 2=Prescribed), Year, Area_ha, geometry
    """
    gdf = gpd.read_file(shapefile_path)
    print(f"Loaded {len(gdf)} fire records")
    print(f"Columns: {list(gdf.columns)}")
    print(f"Year range: {gdf['Year'].min()} - {gdf['Year'].max()}")
    return gdf


def filter_fires_by_period(gdf: gpd.GeoDataFrame, start_year: int,
                            end_year: int, fire_type: int = None) -> gpd.GeoDataFrame:
    """
    Filter fire history by year range and optionally fire type.

    fire_type: 1=Wildfire, 2=Prescribed Burn
    """
    mask = (gdf['Year'] >= start_year) & (gdf['Year'] <= end_year)
    if fire_type is not None:
        mask = mask & (gdf['FireType'] == fire_type)
    return gdf[mask].copy()


def compute_fire_frequency(gdf: gpd.GeoDataFrame, grid_size_deg: float = 0.1):
    """
    Compute fire frequency (number of fires per grid cell) for spatial priors.
    """
    import numpy as np
    from shapely.geometry import box

    minx, miny, maxx, maxy = gdf.total_bounds

    lons = np.arange(minx, maxx, grid_size_deg)
    lats = np.arange(miny, maxy, grid_size_deg)

    frequency = np.zeros((len(lats), len(lons)))

    for i, lat in enumerate(lats):
        for j, lon in enumerate(lons):
            cell = box(lon, lat, lon + grid_size_deg, lat + grid_size_deg)
            count = gdf[gdf.intersects(cell)].shape[0]
            frequency[i, j] = count

    return frequency, lons, lats


# Load and analyze
gdf = load_nsw_fire_history("fire_npwsfirehistory/FireHistory.shp")

# Get all wildfires in last 20 years
recent_wildfires = filter_fires_by_period(gdf, 2004, 2024, fire_type=1)
print(f"Recent wildfires: {len(recent_wildfires)}")
print(f"Total area: {recent_wildfires['Area_ha'].sum():,.0f} hectares")
```

## 7. Building a Training Dataset Pipeline

```python
"""
Complete pipeline: FIRMS detections -> matched satellite imagery -> training patches.
This example uses GEE to match FIRMS points to Sentinel-2 imagery.
"""
import ee
import numpy as np

ee.Initialize(project='your-project')

def build_training_sample(firms_point: ee.Feature, buffer_m: int = 2560,
                          days_before: int = 5, days_after: int = 5):
    """
    For a FIRMS detection point, extract a paired positive/negative sample.

    Returns:
        positive: Sentinel-2 patch from fire date
        negative: Sentinel-2 patch from 60 days before fire (fire-free)
    """
    # Get fire date and location
    fire_date = ee.Date(firms_point.get('Acq_Date'))
    fire_geom = firms_point.geometry().buffer(buffer_m)

    # Get Sentinel-2 image closest to fire date
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')

    positive_img = (s2.filterBounds(fire_geom)
                    .filterDate(fire_date.advance(-days_before, 'day'),
                               fire_date.advance(days_after, 'day'))
                    .sort('system:time_start')
                    .first())

    # Get negative sample: 60 days before fire
    neg_date = fire_date.advance(-60, 'day')
    negative_img = (s2.filterBounds(fire_geom)
                    .filterDate(neg_date.advance(-days_before, 'day'),
                                neg_date.advance(days_after, 'day'))
                    .sort('system:time_start')
                    .first())

    return positive_img, negative_img, fire_geom


def export_training_patches(firms_fc: ee.FeatureCollection,
                            output_prefix: str,
                            max_samples: int = 1000,
                            patch_size_m: int = 2560,
                            scale: int = 10):
    """
    Export training patches to Google Drive.

    Each FIRMS point generates:
      - {prefix}_pos_{id}.tif: fire-present patch
      - {prefix}_neg_{id}.tif: fire-absent patch (same location, different date)
    """
    bands = ['B2', 'B3', 'B4', 'B8', 'B8A', 'B11', 'B12']

    # Sample N fire points
    sample = firms_fc.limit(max_samples)
    sample_list = sample.toList(max_samples)

    for i in range(max_samples):
        point = ee.Feature(sample_list.get(i))
        pos_img, neg_img, region = build_training_sample(point, patch_size_m)

        if pos_img is not None and neg_img is not None:
            # Export positive patch
            ee.batch.Export.image.toDrive(
                image=pos_img.select(bands),
                description=f"{output_prefix}_pos_{i}",
                region=region,
                scale=scale,
                crs='EPSG:4326',
                fileFormat='GeoTIFF'
            ).start()

            # Export negative patch
            ee.batch.Export.image.toDrive(
                image=neg_img.select(bands),
                description=f"{output_prefix}_neg_{i}",
                region=region,
                scale=scale,
                crs='EPSG:4326',
                fileFormat='GeoTIFF'
            ).start()


# Run pipeline
nsw = ee.Geometry.Rectangle([148, -36, 152, -32])
fires = ee.FeatureCollection(
    "projects/sat-io/open-datasets/VIIRS/VNP14IMGTDL_NRT_2020"
).filterBounds(nsw)

# Filter to high confidence
fires_hc = fires.filter(ee.Filter.eq('Confidence', 'high'))

export_training_patches(fires_hc, 'nsw_training', max_samples=500)
```

## 8. FESM (Black Summer) Processing

```python
import rasterio
import numpy as np

def load_fesm(tif_path: str) -> tuple:
    """
    Load Fire Extent and Severity Mapping (FESM) GeoTIFF.

    FESM classes (typical):
        0: Unburnt
        1: Low severity
        2: Moderate severity
        3: High severity
        4: Very high severity (canopy consumed)

    Returns:
        data: 2D numpy array of severity classes
        transform: Affine transform for georeferencing
        crs: Coordinate reference system
    """
    with rasterio.open(tif_path) as src:
        data = src.read(1)
        transform = src.transform
        crs = src.crs
        bounds = src.bounds

    # Summary statistics
    unique, counts = np.unique(data[data > 0], return_counts=True)
    total_burned_pixels = counts.sum()
    pixel_area_ha = abs(transform[0] * transform[4]) / 10000  # 10m pixel -> hectares

    print(f"Total burned area: {total_burned_pixels * pixel_area_ha:,.0f} ha")
    for cls, count in zip(unique, counts):
        print(f"  Class {cls}: {count * pixel_area_ha:,.0f} ha ({count/total_burned_pixels*100:.1f}%)")

    return data, transform, crs


def create_binary_mask(fesm_data: np.ndarray, min_severity: int = 1) -> np.ndarray:
    """Create binary burned/unburned mask from FESM severity data."""
    return (fesm_data >= min_severity).astype(np.uint8)


# Usage
severity, transform, crs = load_fesm("FESM_2019_20.tif")
binary = create_binary_mask(severity, min_severity=2)  # Moderate+ severity
```

## 9. Compute FFDI from Weather Data

```python
import numpy as np

def compute_kbdi(temp_max: float, annual_rainfall: float,
                 daily_rainfall: float, kbdi_yesterday: float) -> float:
    """
    Compute Keetch-Byram Drought Index (KBDI).

    Args:
        temp_max: Daily maximum temperature (Celsius)
        annual_rainfall: Mean annual rainfall (mm)
        daily_rainfall: Today's rainfall (mm), with 5mm subtracted for interception
        kbdi_yesterday: Previous day's KBDI value
    """
    # Effective rainfall (subtract 5mm interception)
    eff_rain = max(0, daily_rainfall - 5.0)
    kbdi_after_rain = max(0, kbdi_yesterday - eff_rain)

    # Evapotranspiration factor
    if temp_max > 0:
        et = (
            (203.2 - kbdi_after_rain) *
            (0.968 * np.exp(0.0875 * temp_max + 1.5552) - 8.30) /
            (1 + 10.88 * np.exp(-0.001736 * annual_rainfall))
        ) * 0.001
        et = max(0, et)
    else:
        et = 0

    return kbdi_after_rain + et


def compute_drought_factor(kbdi: float, days_since_rain: int,
                           rain_amount: float) -> float:
    """Compute drought factor from KBDI and recent rainfall."""
    # Simplified Griffiths (1999) formulation
    x = min(kbdi, 200) / 40.0
    if days_since_rain < 1:
        df = 0.0
    else:
        df = min(10.0, x * (1.0 - np.exp(-days_since_rain / 2.0)))
    return df


def compute_ffdi(temp: float, rh: float, wind_speed: float,
                 drought_factor: float) -> float:
    """
    Compute McArthur Forest Fire Danger Index (FFDI).

    Args:
        temp: Temperature (Celsius)
        rh: Relative humidity (%)
        wind_speed: 10m open wind speed (km/h)
        drought_factor: Drought factor (0-10)

    Returns:
        FFDI value. Categories:
        0-5: Low-Moderate
        5-12: High
        12-24: Very High
        24-50: Severe
        50-100: Extreme
        100+: Catastrophic
    """
    ffdi = 2.0 * np.exp(
        -0.450 + 0.987 * np.log(drought_factor + 0.001)
        - 0.0345 * rh
        + 0.0338 * temp
        + 0.0234 * wind_speed
    )
    return max(0, ffdi)


# Example: Catastrophic conditions during Black Summer
ffdi = compute_ffdi(
    temp=45.0,       # 45 degrees C
    rh=8.0,          # 8% relative humidity
    wind_speed=60.0, # 60 km/h wind
    drought_factor=10.0  # Maximum drought
)
print(f"FFDI: {ffdi:.1f}")  # Will be well above 100 (Catastrophic)
```
