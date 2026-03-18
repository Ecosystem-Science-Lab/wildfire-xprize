# Code Patterns for Geospatial Satellite Data Processing

## Reading GOES ABI NetCDF4

```python
import xarray as xr
import numpy as np

def read_goes_abi(filepath: str) -> dict:
    """
    Read GOES ABI L1b radiance file and convert to brightness temperature.
    Returns dict with 'bt' (2D array), 'x' (1D radians), 'y' (1D radians),
    and 'proj_info' (dict of projection attributes).
    """
    ds = xr.open_dataset(filepath, engine='netcdf4')

    # Extract radiance (auto-applies scale_factor and add_offset)
    rad = ds['Rad'].values.astype(np.float32)

    # Planck function inversion: radiance -> brightness temperature
    fk1 = ds['planck_fk1'].values
    fk2 = ds['planck_fk2'].values
    bc1 = ds['bc1'].values
    bc2 = ds['bc2'].values

    bt = (fk2 / np.log((fk1 / rad) + 1) - bc1) / bc2

    # Data quality flag: 0 = good, 1 = conditionally usable, 2-3 = bad
    dqf = ds['DQF'].values
    bt[dqf > 1] = np.nan

    # Projection info for coordinate transforms
    proj = ds['goes_imager_projection']
    proj_info = {
        'lon_0': float(proj.attrs['longitude_of_projection_origin']),
        'h': float(proj.attrs['perspective_point_height']),
        'sweep': proj.attrs['sweep_angle_axis'],
        'semi_major': float(proj.attrs['semi_major_axis']),
        'semi_minor': float(proj.attrs['semi_minor_axis']),
    }

    result = {
        'bt': bt,
        'x': ds['x'].values,
        'y': ds['y'].values,
        'proj_info': proj_info,
    }
    ds.close()
    return result


def goes_fixed_grid_to_latlon(x, y, proj_info):
    """
    Convert GOES ABI fixed grid coordinates (radians) to lat/lon.
    x, y can be 1D arrays (will be meshgridded) or 2D arrays.
    Returns (lat, lon) in degrees, with NaN for off-Earth pixels.
    """
    if x.ndim == 1 and y.ndim == 1:
        x2d, y2d = np.meshgrid(x, y)
    else:
        x2d, y2d = x, y

    H = proj_info['h'] + proj_info['semi_major']
    r_eq = proj_info['semi_major']
    r_pol = proj_info['semi_minor']
    lambda_0 = np.radians(proj_info['lon_0'])

    sin_x = np.sin(x2d)
    cos_x = np.cos(x2d)
    sin_y = np.sin(y2d)
    cos_y = np.cos(y2d)

    a = sin_x**2 + cos_x**2 * (cos_y**2 + (r_eq / r_pol)**2 * sin_y**2)
    b = -2.0 * H * cos_x * cos_y
    c = H**2 - r_eq**2

    discriminant = b**2 - 4.0 * a * c
    # Off-Earth pixels have negative discriminant
    valid = discriminant >= 0

    r_s = np.full_like(a, np.nan)
    r_s[valid] = (-b[valid] - np.sqrt(discriminant[valid])) / (2.0 * a[valid])

    s_x = r_s * cos_x * cos_y
    s_y = -r_s * sin_x
    s_z = r_s * cos_x * sin_y

    lat = np.degrees(np.arctan((r_eq / r_pol)**2 * s_z / np.sqrt((H - s_x)**2 + s_y**2)))
    lon = np.degrees(lambda_0 - np.arctan(s_y / (H - s_x)))

    return lat, lon
```

## Reading VIIRS HDF5 SDR

```python
import h5py
import numpy as np

def read_viirs_iband(sdr_path: str, geo_path: str, band: int = 4) -> dict:
    """
    Read VIIRS I-band SDR and geolocation.
    band: 4 (3.74 um) or 5 (11.45 um) for fire detection.
    Returns dict with 'bt', 'lat', 'lon', 'quality'.
    """
    band_group = f'All_Data/VIIRS-I{band}-SDR_All'

    with h5py.File(sdr_path, 'r') as f:
        bt_raw = f[f'{band_group}/BrightnessTemperature'][:]
        factors = f[f'{band_group}/BrightnessTemperatureFactors'][:]
        qf = f[f'{band_group}/QF1_VIIRSI{band}SDR'][:]

    # Apply scale and offset: factors = [scale, offset] pairs per scan
    # Each pair applies to 32 detector rows (one scan)
    nscans = bt_raw.shape[0] // 32
    bt = np.zeros_like(bt_raw, dtype=np.float32)
    for i in range(nscans):
        row_start = i * 32
        row_end = (i + 1) * 32
        scale = factors[i * 2]
        offset = factors[i * 2 + 1]
        bt[row_start:row_end] = bt_raw[row_start:row_end] * scale + offset

    # Fill values: 65535 (uint16 max) indicates missing/fill
    bt[bt_raw >= 65528] = np.nan

    # Read geolocation
    with h5py.File(geo_path, 'r') as f:
        lat = f['All_Data/VIIRS-IMG-GEO-TC_All/Latitude'][:]
        lon = f['All_Data/VIIRS-IMG-GEO-TC_All/Longitude'][:]
        sat_zen = f['All_Data/VIIRS-IMG-GEO-TC_All/SatelliteZenithAngle'][:]
        sol_zen = f['All_Data/VIIRS-IMG-GEO-TC_All/SolarZenithAngle'][:]

    # Fill value for geolocation
    lat[lat < -90] = np.nan
    lon[lon < -180] = np.nan

    return {
        'bt': bt,
        'lat': lat,
        'lon': lon,
        'satellite_zenith': sat_zen,
        'solar_zenith': sol_zen,
        'quality': qf,
    }


def subset_viirs_to_roi(data: dict, bbox: tuple) -> dict:
    """
    Subset VIIRS swath data to a geographic bounding box.
    bbox: (west, south, east, north)
    Returns subsetted dict or None if no pixels in ROI.
    """
    west, south, east, north = bbox
    mask = (
        (data['lat'] >= south) & (data['lat'] <= north) &
        (data['lon'] >= west) & (data['lon'] <= east) &
        np.isfinite(data['lat'])
    )

    if not mask.any():
        return None

    # Find bounding rows/cols to extract a rectangular sub-array
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    r_slice = slice(rows[0], rows[-1] + 1)
    c_slice = slice(cols[0], cols[-1] + 1)

    return {
        'bt': data['bt'][r_slice, c_slice],
        'lat': data['lat'][r_slice, c_slice],
        'lon': data['lon'][r_slice, c_slice],
        'satellite_zenith': data['satellite_zenith'][r_slice, c_slice],
        'solar_zenith': data['solar_zenith'][r_slice, c_slice],
        'quality': data['quality'][r_slice, c_slice],
        'roi_mask': mask[r_slice, c_slice],
    }
```

## Reading Himawari AHI HSD via satpy

```python
import glob
from satpy import Scene
import numpy as np

def read_himawari_band(data_dir: str, timestamp: str, band: int) -> dict:
    """
    Read Himawari AHI band from HSD segment files using satpy.
    timestamp: 'YYYYMMDD_HHMM' format
    band: 7 (3.9 um) or 14 (11.2 um) for fire detection
    Returns dict with 'bt' (2D xarray DataArray with area definition).
    """
    # HSD files: 10 segments per band, named S0110 through S1010
    pattern = f'{data_dir}/HS_H09_{timestamp}_B{band:02d}_FLDK_R20_S*10.DAT'
    filenames = sorted(glob.glob(pattern))

    if len(filenames) != 10:
        raise FileNotFoundError(
            f"Expected 10 segments for B{band:02d}, found {len(filenames)}"
        )

    scn = Scene(reader='ahi_hsd', filenames=filenames)
    dataset_name = f'B{band:02d}'
    scn.load([dataset_name])

    # satpy returns an xarray DataArray with an AreaDefinition attached
    da = scn[dataset_name]

    # The DataArray has .attrs['area'] which is a pyresample AreaDefinition
    # for the geostationary projection
    return {
        'bt': da,
        'area_def': da.attrs['area'],
        'time': da.attrs.get('start_time'),
    }


def himawari_crop_to_roi(scene_data: dict, bbox: tuple) -> dict:
    """
    Crop Himawari data to a bounding box using pyresample.
    bbox: (west, south, east, north) in degrees
    """
    from pyresample import create_area_def
    from satpy import Scene

    west, south, east, north = bbox
    # The scene data's AreaDefinition can be cropped
    area = scene_data['area_def']

    # Get lat/lon for every pixel in the area
    lons, lats = area.get_lonlats()

    # Create mask for ROI
    mask = (lats >= south) & (lats <= north) & (lons >= west) & (lons <= east)

    if not mask.any():
        return None

    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]

    bt = scene_data['bt'].values[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
    lat = lats[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]
    lon = lons[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1]

    return {
        'bt': bt,
        'lat': lat,
        'lon': lon,
        'roi_mask': mask[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1],
    }
```

## Reading Landsat GeoTIFF via rasterio

```python
import rasterio
from rasterio.windows import from_bounds
import numpy as np

def read_landsat_thermal(band_path: str, mtl_path: str,
                         bbox: tuple = None) -> dict:
    """
    Read Landsat 8/9 thermal band and convert to brightness temperature.
    band_path: path to B10 GeoTIFF
    mtl_path: path to MTL.txt metadata file
    bbox: optional (west, south, east, north) for windowed read
    """
    # Parse calibration constants from MTL
    cal = parse_landsat_mtl(mtl_path)

    with rasterio.open(band_path) as src:
        if bbox:
            window = from_bounds(*bbox, transform=src.transform)
            dn = src.read(1, window=window).astype(np.float32)
            transform = src.window_transform(window)
        else:
            dn = src.read(1).astype(np.float32)
            transform = src.transform

        crs = src.crs
        nodata = src.nodata

    # Digital number to radiance
    radiance = dn * cal['RADIANCE_MULT_BAND_10'] + cal['RADIANCE_ADD_BAND_10']

    # Radiance to brightness temperature (inverse Planck)
    bt = cal['K2_CONSTANT_BAND_10'] / np.log(
        cal['K1_CONSTANT_BAND_10'] / radiance + 1
    )

    # Mask nodata
    if nodata is not None:
        bt[dn == nodata] = np.nan
    bt[dn == 0] = np.nan

    return {
        'bt': bt,
        'transform': transform,
        'crs': crs,
    }


def parse_landsat_mtl(mtl_path: str) -> dict:
    """Parse Landsat MTL.txt file for calibration constants."""
    cal = {}
    keys_of_interest = [
        'RADIANCE_MULT_BAND_10', 'RADIANCE_ADD_BAND_10',
        'K1_CONSTANT_BAND_10', 'K2_CONSTANT_BAND_10',
        'RADIANCE_MULT_BAND_6', 'RADIANCE_ADD_BAND_6',  # SWIR1
        'RADIANCE_MULT_BAND_7', 'RADIANCE_ADD_BAND_7',  # SWIR2
    ]
    with open(mtl_path) as f:
        for line in f:
            line = line.strip()
            for key in keys_of_interest:
                if line.startswith(key):
                    cal[key] = float(line.split('=')[1].strip())
    return cal


def landsat_pixel_to_latlon(row: int, col: int, transform, crs) -> tuple:
    """Convert pixel row/col to WGS84 lat/lon."""
    from pyproj import Transformer
    # Affine transform: pixel -> projected coordinates (UTM)
    x, y = rasterio.transform.xy(transform, row, col)
    # Project to WGS84
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(x, y)
    return lat, lon
```

## Reading Sentinel-2 JP2

```python
import rasterio
import numpy as np
from pathlib import Path

def read_sentinel2_fire_bands(safe_dir: str, bbox: tuple = None) -> dict:
    """
    Read Sentinel-2 L2A SWIR bands for fire detection.
    safe_dir: path to .SAFE directory
    Returns B12, B11, B8A at 20m resolution.
    """
    safe_path = Path(safe_dir)
    # Find the 20m band directory
    granule_dirs = list(safe_path.glob('GRANULE/*/IMG_DATA/R20m'))
    if not granule_dirs:
        raise FileNotFoundError(f"No R20m directory found in {safe_dir}")

    img_dir = granule_dirs[0]

    bands = {}
    for band_name in ['B12', 'B11', 'B8A', 'SCL']:
        band_files = list(img_dir.glob(f'*_{band_name}_20m.jp2'))
        if not band_files:
            continue

        with rasterio.open(str(band_files[0])) as src:
            if bbox:
                window = from_bounds(*bbox, transform=src.transform)
                data = src.read(1, window=window).astype(np.float32)
                transform = src.window_transform(window)
            else:
                data = src.read(1).astype(np.float32)
                transform = src.transform
            crs = src.crs

        # L2A reflectance: stored as uint16, divide by 10000 to get reflectance
        if band_name != 'SCL':
            data[data == 0] = np.nan  # nodata
            data = data / 10000.0

        bands[band_name] = data

    return {
        'bands': bands,
        'transform': transform,
        'crs': crs,
    }
```

## Spatial Indexing with H3

```python
import h3
import numpy as np
from typing import List, Tuple

def fire_pixels_to_h3(lats: np.ndarray, lons: np.ndarray,
                       resolution: int = 7) -> List[str]:
    """
    Convert fire pixel coordinates to H3 cell indices.
    resolution 7 ~ 5.2 km^2 (good match for 2km sensor pixels)
    resolution 9 ~ 0.1 km^2 (good for 375m VIIRS pixels)
    """
    cells = set()
    for lat, lon in zip(lats.flat, lons.flat):
        if np.isfinite(lat) and np.isfinite(lon):
            cell = h3.latlng_to_cell(float(lat), float(lon), resolution)
            cells.add(cell)
    return list(cells)


def h3_cluster_fires(fire_cells: List[str], resolution: int = 5) -> dict:
    """
    Group fire detections by coarser H3 cells for event-level tracking.
    Returns dict mapping parent cell -> list of child cells.
    """
    clusters = {}
    for cell in fire_cells:
        parent = h3.cell_to_parent(cell, resolution)
        if parent not in clusters:
            clusters[parent] = []
        clusters[parent].append(cell)
    return clusters


def build_roi_h3_set(bbox: tuple, resolution: int = 5) -> set:
    """
    Precompute the set of H3 cells covering a bounding box.
    Use for fast "is this pixel in our ROI?" checks.
    """
    from shapely.geometry import box
    west, south, east, north = bbox
    roi_polygon = box(west, south, east, north)

    # h3.polygon_to_cells expects a list of (lat, lng) pairs for the outer ring
    coords = list(roi_polygon.exterior.coords)
    h3_polygon = h3.H3Poly([(lat, lon) for lon, lat in coords])
    cells = h3.h3shape_to_cells(h3_polygon, resolution)
    return set(cells)
```

## Coordinate Transforms and Utilities

```python
from pyproj import Transformer, CRS
import numpy as np

# Reusable transformer instances (create once, use many times)
# Important: Transformer objects are thread-safe for .transform() calls

WGS84_TO_HIMAWARI = Transformer.from_crs(
    "EPSG:4326",
    "+proj=geos +lon_0=140.7 +h=35785863 +sweep=y +ellps=WGS84",
    always_xy=True  # lon, lat order
)

WGS84_TO_GOES_EAST = Transformer.from_crs(
    "EPSG:4326",
    "+proj=geos +lon_0=-75.0 +h=35786023 +sweep=x +ellps=GRS80",
    always_xy=True
)

HIMAWARI_TO_WGS84 = Transformer.from_crs(
    "+proj=geos +lon_0=140.7 +h=35785863 +sweep=y +ellps=WGS84",
    "EPSG:4326",
    always_xy=True
)


def precompute_latlon_grid(area_def) -> Tuple[np.ndarray, np.ndarray]:
    """
    Precompute lat/lon arrays for a pyresample AreaDefinition.
    Cache these at startup to avoid recomputation per scene.
    """
    lons, lats = area_def.get_lonlats()
    return lats.astype(np.float32), lons.astype(np.float32)


def precompute_roi_mask(lats: np.ndarray, lons: np.ndarray,
                         bbox: tuple) -> np.ndarray:
    """
    Build a boolean mask for pixels within a geographic bounding box.
    Precompute once at startup for fixed-grid sensors.
    """
    west, south, east, north = bbox
    return (
        (lats >= south) & (lats <= north) &
        (lons >= west) & (lons <= east) &
        np.isfinite(lats)
    )
```

## Windowed Reading from Cloud-Optimized GeoTIFF (COG)

```python
import rasterio
from rasterio.windows import from_bounds

def read_cog_region(url: str, bbox: tuple) -> tuple:
    """
    Read only the region of interest from a COG on S3 or HTTP.
    This makes a minimal number of HTTP range requests.
    url: 's3://bucket/path/file.tif' or 'https://...'
    bbox: (west, south, east, north)
    """
    env = rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
        AWS_NO_SIGN_REQUEST='YES',
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES',
        GDAL_HTTP_MULTIPLEX='YES',
        VSI_CACHE='TRUE',
        VSI_CACHE_SIZE=5000000,  # 5 MB cache
    )

    with env:
        with rasterio.open(url) as src:
            window = from_bounds(*bbox, transform=src.transform)
            data = src.read(1, window=window)
            transform = src.window_transform(window)
            return data, transform, src.crs
```

## STAC Catalog Search

```python
from pystac_client import Client
from datetime import datetime, timedelta

def search_sentinel2(bbox: tuple, start_date: str, end_date: str,
                      max_cloud: int = 50) -> list:
    """
    Search Copernicus Data Space for Sentinel-2 L2A scenes.
    Returns list of STAC items.
    """
    catalog = Client.open("https://catalogue.dataspace.copernicus.eu/stac")

    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=list(bbox),
        datetime=f"{start_date}/{end_date}",
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=500,
    )

    items = list(search.items())
    # Sort by datetime
    items.sort(key=lambda x: x.datetime)
    return items


def search_sentinel3_slstr(bbox: tuple, start_date: str,
                            end_date: str) -> list:
    """Search for Sentinel-3 SLSTR L1B scenes."""
    catalog = Client.open("https://catalogue.dataspace.copernicus.eu/stac")

    search = catalog.search(
        collections=["sentinel-3-slstr-l1b"],
        bbox=list(bbox),
        datetime=f"{start_date}/{end_date}",
        max_items=500,
    )

    return list(search.items())
```

## Resampling Between Grids

```python
from pyresample import create_area_def, geometry
from pyresample.kd_tree import resample_nearest
import numpy as np

def resample_swath_to_grid(lats: np.ndarray, lons: np.ndarray,
                            data: np.ndarray, bbox: tuple,
                            resolution_deg: float = 0.005) -> dict:
    """
    Resample swath data (e.g., VIIRS) to a regular lat/lon grid.
    Only use for visualization or multi-sensor fusion, NOT in the detection
    hot path.
    """
    west, south, east, north = bbox

    # Define source swath geometry
    swath_def = geometry.SwathDefinition(lons=lons, lats=lats)

    # Define target regular grid
    target_def = create_area_def(
        'target_grid',
        {'proj': 'longlat', 'datum': 'WGS84'},
        area_extent=[west, south, east, north],
        resolution=resolution_deg,
    )

    # Nearest neighbor resampling
    result = resample_nearest(
        swath_def, data, target_def,
        radius_of_influence=1000,  # meters
        fill_value=np.nan,
        epsilon=0.5,  # trade accuracy for speed
    )

    target_lons, target_lats = target_def.get_lonlats()

    return {
        'data': result,
        'lats': target_lats,
        'lons': target_lons,
        'area_def': target_def,
    }
```
