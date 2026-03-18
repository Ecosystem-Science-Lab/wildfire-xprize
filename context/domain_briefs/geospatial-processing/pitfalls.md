# Geospatial Processing Pitfalls

## Projection and Coordinate Errors

### Himawari sweep="y" vs GOES sweep="x"

This is the single most common source of geolocation bugs when working with multiple
geostationary sensors. The sweep angle axis determines how the instrument scans:

- **GOES ABI**: `sweep="x"` — the scan mirror sweeps in the E/W direction
- **Himawari AHI**: `sweep="y"` — the scan mirror sweeps in the N/S direction

If you use the wrong sweep axis in your projection definition, the resulting
coordinates will be **reflected** — pixels that should map to Australia will map
to somewhere entirely different. Always check the source sensor before constructing
the pyproj CRS string.

```python
# WRONG: using GOES sweep for Himawari data
bad_crs = "+proj=geos +lon_0=140.7 +h=35785863 +sweep=x"  # x is wrong for Himawari

# CORRECT
him_crs = "+proj=geos +lon_0=140.7 +h=35785863 +sweep=y"
```

### Lat/Lon Axis Order (EPSG:4326)

The formal definition of EPSG:4326 specifies **(latitude, longitude)** order. However,
most geospatial software (GDAL, rasterio, shapely, GeoJSON) uses **(longitude, latitude)**
order by convention. This leads to subtle bugs:

- `pyproj.Transformer` with `always_xy=True` forces lon/lat order regardless of CRS
  definition. Always use this flag.
- GeoJSON spec requires `[longitude, latitude]` order.
- h3 functions use `(lat, lng)` order — the opposite of most GIS tools.
- numpy meshgrid of lon/lat vs shapely Point(lon, lat) — consistent, but easy to swap.

**Rule of thumb**: always label your variables explicitly as `lat` and `lon`, never
use ambiguous names like `coord1`, `coord2`, `x`, `y` for geographic coordinates.

### UTM Zone Boundaries

Landsat and Sentinel-2 tiles are projected in local UTM zones. A fire event near a
UTM zone boundary will have data in two different projections. You cannot directly
compare pixel coordinates from adjacent zones without reprojecting.

NSW spans UTM zones 54-56 (roughly). Tiles near zone boundaries (e.g., around 150 E
which is the 55/56 boundary) need special handling.

## Data Format Pitfalls

### NetCDF4 Scale Factors and Fill Values

NetCDF4 (CF convention) uses `scale_factor` and `add_offset` attributes to pack
floating-point values into integer storage. There are two approaches:

1. **xarray** (recommended): Automatically applies unpacking when you access `.values`.
   Fill values are automatically converted to NaN.
2. **netCDF4 library directly**: Also auto-applies by default with `set_auto_maskandscale(True)`.
3. **Manual access**: If you read raw values (e.g., via `h5py`), you MUST apply:
   `physical = raw * scale_factor + add_offset`

Common mistake: applying the transform twice (once by the library, once manually),
producing nonsensical values.

**Fill values**: GOES ABI uses `_FillValue = 65535` for uint16 radiance. These become
NaN after xarray unpacking. Always check for NaN after reading.

### HDF5 Attribute Encoding (Python 3)

HDF5 files created by different tools may store string attributes as:
- `bytes` objects: `b'some_string'`
- `numpy.bytes_` objects
- `str` objects

In Python 3, comparisons like `attr == 'some_string'` will fail silently if `attr`
is `b'some_string'`. Always decode:

```python
value = f.attrs['key']
if isinstance(value, bytes):
    value = value.decode('utf-8')
```

### VIIRS Bow-Tie Deletion

VIIRS scans create overlapping pixels at the edges of each scan (the "bow-tie" effect).
The instrument firmware deletes some of these duplicate pixels, leaving **fill values
in regular patterns** at the edges of each 32-row scan block. These are NOT missing
data — they are intentional gaps.

If you see regular stripes of missing data in VIIRS imagery, this is bow-tie deletion,
not a data quality problem. Handle by:
- Checking for fill values (65535 or values > 65527 in raw uint16 data)
- Not interpolating across these gaps (they represent real geometric properties)
- Being aware that fire detection sensitivity varies across the scan swath

## Memory and Performance

### Full-Disk Image Sizes

Never load a full-disk geostationary image with all bands into memory at once:

| Sensor | Single Band Full Disk | All Thermal Bands |
|--------|----------------------|-------------------|
| Himawari AHI (2km) | ~120 MB | ~480 MB (4 thermal bands) |
| Himawari AHI (all) | varies | ~8 GB (16 bands) |
| GOES ABI (2km) | ~120 MB | ~480 MB |

**Strategy**: Process only the ROI subset. For Himawari, you can select only the
segments (of 10) that contain your region of interest. NSW is covered by segments
7-9 approximately.

### Reprojection in the Hot Path

Reprojecting raster data (e.g., from geostationary to equirectangular) involves:
1. Computing new coordinates for every output pixel
2. Interpolating source pixel values

This is expensive — typically 0.5-2 seconds for a full-disk image. For real-time
fire detection with a sub-10-second budget, avoid reprojection entirely in the
detection pipeline:

- **Work in native sensor coordinates** for initial fire detection
- Precompute lat/lon lookup tables at startup (one-time cost)
- Only convert fire pixel coordinates to lat/lon for the final alert (point transform
  is nearly free)

### COG vs Regular GeoTIFF

**Cloud-Optimized GeoTIFF (COG)** includes internal tiling and overviews that allow
efficient partial reads from HTTP/S3. A regular GeoTIFF stored on S3 requires
downloading the entire file to read a small region.

Always check if your data source provides COGs. If you're generating intermediate
GeoTIFFs, create them as COGs:

```python
# Writing a COG
with rasterio.open('output.tif', 'w', driver='COG',
                   height=h, width=w, count=1, dtype='float32',
                   crs='EPSG:4326', transform=transform) as dst:
    dst.write(data, 1)
```

## Multi-Tile and Multi-Sensor Issues

### Sentinel-2 Tile Boundary Duplication

Sentinel-2 tiles overlap by ~5 km at their edges. A fire near a tile boundary will
appear in **two tiles** from the same overpass. Without deduplication, you will
generate duplicate fire alerts.

**Solution**: After detecting fires, deduplicate using H3 cells or by checking if
fire detections from different tiles are within a threshold distance (e.g., 500 m)
and from the same acquisition time.

### Temporal Alignment Across Sensors

Different sensors observe the same location at different times:
- Himawari: every 10 min
- GOES: every 10-15 min (but limited view of Australia)
- VIIRS: 1-2 passes per day over NSW
- Sentinel-2: every 5 days per satellite (2 satellites = every 2-3 days)
- Landsat: every 16 days

A "simultaneous" detection from Himawari and VIIRS may actually be 5+ minutes apart.
Always track observation timestamps, not just processing timestamps.

### Sentinel-3 SLSTR Dual-View Geometry

SLSTR has nadir and oblique viewing geometries, each stored as separate datasets.
The oblique view covers a different ground footprint and has different pixel sizes.
For fire detection, use the nadir view (S7, S8 channels) unless specifically needing
the fire-dedicated channels (F1, F2) which are also nadir.

## Numerical Precision

### Brightness Temperature Edge Cases

The Planck function inversion can produce invalid results if:
- Radiance is zero or negative (masked/space pixels) — produces inf or nan in the log
- Radiance is at saturation (detector saturated by hot fire) — BT will clip at ~400 K
  for standard channels, ~500 K for fire channels

Always guard:
```python
rad = np.where(rad > 0, rad, np.nan)
bt = fk2 / np.log(fk1 / rad + 1)
```

### H3 Resolution Mismatch

Using too fine an H3 resolution wastes memory and computation. Using too coarse a
resolution merges distinct fire events:

- Sensor pixel size ~2 km (AHI, GOES): use H3 resolution 7 (~2.5 km edge length)
- Sensor pixel size ~375 m (VIIRS I-band): use H3 resolution 9 (~175 m edge length)
- Fire event grouping: use H3 resolution 5 (~15 km edge length)

Do not use resolution 15 (the finest) — each cell is ~0.9 m^2 and there are an
impractical number of cells in any meaningful area.

## Platform-Specific Issues

### GDAL/rasterio Environment Variables

When reading from S3 or HTTP, GDAL needs specific configuration to perform well:
```python
import rasterio
env = rasterio.Env(
    GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',  # don't list entire S3 directories
    AWS_NO_SIGN_REQUEST='YES',                   # for public buckets
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES',
    VSI_CACHE='TRUE',
)
```

Without `GDAL_DISABLE_READDIR_ON_OPEN`, opening a single file on S3 can trigger
a full directory listing, which is extremely slow for buckets with thousands of files.

### satpy Reader Selection

satpy auto-detects the correct reader from filenames, but this can fail if filenames
are renamed or if multiple readers match. Always specify the reader explicitly:

```python
# Explicit reader — reliable
scn = Scene(reader='ahi_hsd', filenames=files)

# Auto-detect — can fail or pick the wrong reader
scn = Scene(filenames=files)  # don't do this in production
```

### Thread Safety

- `pyproj.Transformer.transform()`: Thread-safe after construction.
- `rasterio.open()`: NOT thread-safe. Use separate file handles per thread, or
  use `rasterio.Env()` context manager in each thread.
- `h5py.File`: NOT thread-safe by default. Use `h5py.File(..., swmr=True)` for
  concurrent reads, or serialize access.
- `xarray.open_dataset()`: Creates thread-safe dataset objects, but the underlying
  file handle may not be thread-safe. Use `chunks={}` to enable dask-backed lazy
  loading for concurrent access.
