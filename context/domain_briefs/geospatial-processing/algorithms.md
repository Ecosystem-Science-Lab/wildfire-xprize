# Geospatial Algorithms for Satellite Fire Detection

## Coordinate Transforms

### GOES ABI Fixed Grid to Lat/Lon

GOES ABI stores data in a "fixed grid" coordinate system where pixel positions are
angular offsets (in radians) from the satellite sub-point. The NetCDF files contain
`x` and `y` coordinate variables in radians.

**Projection parameters** (from file attributes):
- `perspective_point_height`: 35786023.0 m (satellite altitude)
- `semi_major_axis`: 6378137.0 m
- `semi_minor_axis`: 6356752.31414 m (GRS80 ellipsoid)
- `longitude_of_projection_origin`: -75.0 (GOES-East) or -137.0 (GOES-West)
- `sweep_angle_axis`: "x" (GOES uses x-axis sweep)

**Conversion formulas** (GOES-R PUG Algorithm):

```
# Given x, y in radians from the fixed grid
H = perspective_point_height + semi_major_axis  # distance from Earth center to satellite
r_eq = semi_major_axis
r_pol = semi_minor_axis

lambda_0 = longitude_of_projection_origin (radians)

# Intermediate values
a = sin(x)^2 + cos(x)^2 * (cos(y)^2 + (r_eq/r_pol)^2 * sin(y)^2)
b = -2 * H * cos(x) * cos(y)
c = H^2 - r_eq^2

r_s = (-b - sqrt(b^2 - 4*a*c)) / (2*a)    # distance from satellite to pixel

s_x = r_s * cos(x) * cos(y)
s_y = -r_s * sin(x)
s_z = r_s * cos(x) * sin(y)

lat = arctan((r_eq/r_pol)^2 * s_z / sqrt((H - s_x)^2 + s_y^2))
lon = lambda_0 - arctan(s_y / (H - s_x))
```

Where `b^2 - 4ac < 0` indicates the pixel is off the Earth disk (space).

### Himawari AHI Geostationary Projection

Himawari uses the same geostationary projection math but with different parameters:
- `longitude_of_projection_origin`: 140.7 E
- `sweep_angle_axis`: "y" (Himawari uses y-axis sweep)
- `perspective_point_height`: 35785863.0 m

The **sweep axis difference** between GOES (x) and Himawari (y) means the x and y
scan angles are transposed. Getting this wrong produces coordinates that are reflected
across the sub-satellite point. With pyproj:

```
# GOES-East
goes_crs = "+proj=geos +lon_0=-75.0 +h=35786023 +sweep=x +ellps=GRS80"

# Himawari-9
him_crs = "+proj=geos +lon_0=140.7 +h=35785863 +sweep=y +ellps=WGS84"
```

### Using pyproj for Transforms

```python
from pyproj import Transformer

# Geostationary (Himawari) to WGS84
transformer = Transformer.from_crs(
    "+proj=geos +lon_0=140.7 +h=35785863 +sweep=y +ellps=WGS84",
    "EPSG:4326",
    always_xy=True  # forces lon, lat order (not lat, lon)
)
lon, lat = transformer.transform(x_rad * sat_height, y_rad * sat_height)
# Note: geos projection expects meters (angle * height), not raw radians
```

### Swath-Based Geolocation (VIIRS, SLSTR)

VIIRS and Sentinel-3 SLSTR do not use a fixed projection. Each pixel has explicit
latitude and longitude stored in companion geolocation files:

- VIIRS: `GITCO` (I-band terrain-corrected geolocation) or `GMTCO` (M-band)
- SLSTR: geodetic coordinates embedded in the product

No projection math needed. Read the lat/lon arrays and use them as lookup tables.
The trade-off is large memory footprint for these arrays.

## Region-of-Interest Subsetting

### Windowed Reading (Projected Data)

For data with a defined affine transform (GeoTIFF, projected NetCDF), compute the
pixel window corresponding to the geographic bounding box:

```python
import rasterio
from rasterio.windows import from_bounds

# NSW bounding box (approximate)
NSW_BBOX = (148.0, -37.0, 154.0, -28.0)  # (west, south, east, north)

with rasterio.open('landsat_band.tif') as src:
    window = from_bounds(*NSW_BBOX, transform=src.transform)
    data = src.read(1, window=window)
    win_transform = src.window_transform(window)
```

### Geostationary ROI via Precomputed Bounds

For geostationary sensors, precompute the x/y radian ranges that correspond to the
target area and slice directly:

```python
# Precompute once at startup
transformer_to_geos = Transformer.from_crs("EPSG:4326", him_crs, always_xy=True)
x_min, y_min = transformer_to_geos.transform(148.0, -37.0)
x_max, y_max = transformer_to_geos.transform(154.0, -28.0)

# Convert from meters back to pixel indices using the fixed grid spacing
# AHI Band 7 (2km resolution): 5500 x 5500 pixels for full disk
col_min = int((x_min / sat_height - x_offset) / x_scale)
col_max = int((x_max / sat_height - x_offset) / x_scale)
# ... similarly for rows
```

### Swath Subsetting (VIIRS)

For swath data, there is no regular grid. Subset by:
1. Read the geolocation arrays (lat, lon).
2. Create a boolean mask: `mask = (lat >= -37) & (lat <= -28) & (lon >= 148) & (lon <= 154)`.
3. Apply mask to data arrays.
4. If no pixels fall in the ROI, skip the granule entirely.

Optimization: check the bounding box of the granule from filename metadata or file
attributes before loading full geolocation arrays.

## Spatial Indexing

### H3 Hexagonal Index

H3 provides a hierarchical hexagonal tiling of the globe. Useful for:
- Grouping nearby fire detections into events
- Fast spatial lookups without complex geometry
- Consistent cell areas (unlike lat/lon grids at different latitudes)

**Resolution selection:**
| Resolution | Avg Area     | Use Case |
|------------|-------------|----------|
| 3          | ~12,400 km^2 | Continental-scale monitoring regions |
| 5          | ~253 km^2    | Fire event grouping / regional summary |
| 7          | ~5.2 km^2    | Fire perimeter tracking |
| 9          | ~0.105 km^2  | Individual fire pixel precision |
| 11         | ~0.002 km^2  | Sub-pixel precision (overkill for most sensors) |

For fire detection at 2km sensor resolution (AHI, GOES), H3 resolution 7 aligns
well with pixel size. For 375m VIIRS, resolution 9 is appropriate.

### R-tree for Boundary Checks

```python
from shapely.geometry import Point, shape
from shapely.strtree import STRtree
import geopandas as gpd

# Load competition area boundary
boundary = gpd.read_file('nsw_boundary.geojson')
tree = STRtree(boundary.geometry.tolist())

# Check if fire pixel is in competition area
point = Point(151.0, -33.5)
results = tree.query(point)
is_in_area = any(boundary.geometry.iloc[i].contains(point) for i in results)
```

### Precomputed Lookup Grids

For fixed-grid sensors (GOES, Himawari), the most performant approach is a precomputed
boolean mask at the sensor's native resolution:

1. At startup, compute lat/lon for every pixel in the ROI region of the fixed grid.
2. Create a boolean mask: `in_competition_area[row, col] = True/False`.
3. During processing, just index with `data[in_competition_area]`.

This eliminates all runtime geometry checks for fixed-grid sensors.

## Resampling Methods

### When to Resample

- **Detection pipeline**: Do NOT resample. Work in native sensor coordinates.
  Resampling adds latency and can smear hot pixel signals.
- **Multi-sensor fusion**: Resample to a common grid only when combining detections
  from different sensors for confirmation.
- **Visualization/output**: Resample to a standard grid (e.g., 0.01-degree) for
  display and reporting.

### Resampling Approaches

**Nearest neighbor** (pyresample `NearestNeighbour`):
- Fastest. Preserves original pixel values.
- Use for categorical data (fire/no-fire masks) and for brightness temperatures
  where exact values matter for thresholding.

**Bilinear interpolation** (pyresample `BilinearInterpolator`):
- Smoother output. Produces intermediate values.
- Appropriate for background temperature fields, not for fire detection pixels.

**Bucket resampling** (pyresample `BucketResampler`):
- Aggregates multiple source pixels into target grid cells.
- Useful for downscaling high-res data (e.g., VIIRS 375m to 2km grid).

```python
from pyresample import create_area_def
from pyresample.kd_tree import resample_nearest

target_area = create_area_def(
    'nsw_region',
    {'proj': 'longlat', 'datum': 'WGS84'},
    area_extent=[148, -37, 154, -28],
    resolution=0.02  # ~2km at this latitude
)

result = resample_nearest(
    source_area_def,
    source_data,
    target_area,
    radius_of_influence=5000,  # meters
    fill_value=np.nan
)
```

## Distance and Area Calculations

On the curved Earth surface at the latitudes relevant to NSW (~28-37 S):
- 1 degree latitude ~ 111 km (constant)
- 1 degree longitude ~ 93-98 km (varies with latitude)
- For accurate distances, use the Vincenty or Haversine formula
- For small areas (< 100 km), a simple equirectangular approximation works:

```python
import numpy as np

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
```
