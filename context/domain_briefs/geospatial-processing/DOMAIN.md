# Geospatial Processing for Satellite Fire Detection

## Overview

This domain covers the ingestion, decoding, georeferencing, and spatial manipulation of
satellite imagery from multiple sensor platforms for real-time wildfire detection. The
core challenge is converting raw instrument data — stored in format-specific binary
containers — into georeferenced brightness temperature arrays that downstream fire
detection algorithms can consume, all within a sub-10-second processing budget.

## Key Concepts

### Raster Data Formats

| Format   | Sensors          | Library          | Notes |
|----------|------------------|------------------|-------|
| HSD      | Himawari AHI     | satpy            | Proprietary binary, 10 segments per full-disk band |
| NetCDF4  | GOES ABI         | xarray, netCDF4  | CF-compliant, self-describing metadata |
| HDF5     | VIIRS SDR        | h5py, satpy      | Hierarchical groups, multiple granules per file |
| GeoTIFF  | Landsat          | rasterio         | Single-band files with embedded CRS and transform |
| JP2/SAFE | Sentinel-2 MSI   | rasterio, satpy  | JPEG2000 tiles within SAFE directory structure |
| NetCDF4  | Sentinel-3 SLSTR | xarray, satpy    | Similar to GOES but different variable conventions |
| COG      | Analysis-ready   | rasterio         | Cloud-optimized GeoTIFF — efficient range reads from S3 |

### Coordinate Reference Systems

Satellite data arrives in sensor-native coordinate systems that must be understood
before any geolocation work:

- **Geostationary projection**: Used by GOES ABI and Himawari AHI. Data lives in a
  "fixed grid" defined by angular scan positions (radians) relative to the satellite's
  sub-satellite point. Requires satellite height and sweep axis to convert to lat/lon.
- **Swath-based geolocation**: VIIRS and SLSTR provide explicit lat/lon arrays in
  companion geolocation files. No projection math needed, but arrays are large.
- **UTM zones**: Landsat and Sentinel-2 deliver data projected into local UTM zones.
  Australia spans UTM zones 49-56 (EPSG:32649 through EPSG:32656).
- **WGS84 (EPSG:4326)**: The common geographic CRS. All sensor data eventually maps
  to lat/lon for cross-sensor comparison and alert generation.

### Spatial Indexing

For fast geospatial queries (is this fire pixel inside the competition area?):

- **H3** (Uber): Hierarchical hexagonal grid. Resolution 5 cells (~252 km^2) for
  regional event grouping, resolution 9 (~0.1 km^2) for precise fire location.
- **S2 Geometry** (Google): Hierarchical cell system on the sphere. Used internally
  by Earth Engine and BigQuery GIS.
- **R-tree**: Classic spatial index for bounding box queries. Used by shapely/geopandas
  for point-in-polygon tests against competition area boundaries.

### Key Processing Stages

1. **Decode**: Read raw bytes from format-specific containers into numpy arrays.
2. **Calibrate**: Apply gain, offset, Planck function coefficients to convert raw
   counts to radiance or brightness temperature.
3. **Geolocate**: Map each pixel to geographic coordinates (either by projection math
   or lookup from geolocation arrays).
4. **Subset**: Extract only the region of interest (e.g., NSW, Australia) to minimize
   memory and compute.
5. **Resample** (optional): Regrid to a common grid only if multi-sensor fusion
   requires it. Avoid in the hot detection path.

## Relevance to XPRIZE Wildfire Detection

The competition scores on detection latency (time from ignition to alert). Geospatial
processing sits directly in the critical path:

- **Data arrival to pixel values**: Must decode and calibrate within 1-2 seconds.
- **Geolocation**: Must identify which pixels fall within the competition area without
  processing the entire disk image (full-disk Himawari = ~5500x5500 per band).
- **Spatial filtering**: Only process pixels in or near NSW, Australia (roughly
  bbox [148, -37, 154, -28]) to avoid wasting compute on irrelevant regions.
- **Alert coordinates**: Final fire alerts must include accurate lat/lon coordinates
  for scoring against known ignition points.

## Key Libraries

| Library      | Purpose                                           | Install |
|--------------|---------------------------------------------------|---------|
| `rasterio`   | GeoTIFF/JP2 reading, windowed reads, transforms   | `pip install rasterio` |
| `xarray`     | NetCDF4/HDF5 array access with labeled dimensions | `pip install xarray netcdf4` |
| `h5py`       | Low-level HDF5 access (VIIRS SDR)                 | `pip install h5py` |
| `satpy`      | Multi-format satellite reader (AHI HSD, VIIRS, SLSTR) | `pip install satpy` |
| `pyresample` | Fast resampling between grids/swaths              | `pip install pyresample` |
| `pyproj`     | CRS definitions and coordinate transforms         | `pip install pyproj` |
| `shapely`    | Geometric operations (point-in-polygon)           | `pip install shapely` |
| `geopandas`  | GeoDataFrame for vector data with spatial index    | `pip install geopandas` |
| `h3`         | Uber H3 hexagonal spatial index                   | `pip install h3` |
| `pystac-client` | STAC API catalog search                        | `pip install pystac-client` |
| `s3fs`       | S3-backed file access for cloud-hosted data        | `pip install s3fs` |

## Performance Constraints

- Full-disk Himawari AHI across all 16 bands: ~8 GB. Never load all at once.
- GOES ABI full-disk single band: ~120 MB. Manageable, but windowed reads are faster.
- VIIRS granule (6 minutes of data): ~200 MB per band with geolocation.
- Target: decode + calibrate + geolocate + spatial filter under 2 seconds per scene.
- Use memory-mapped I/O where possible (rasterio, h5py default behavior).
- Process segments/tiles independently to parallelize across CPU cores.

## File Organization Convention

Satellite data files follow agency naming conventions that encode metadata:
- GOES: `OR_ABI-L1b-RadF-M6C07_G16_s20261010000_e20261010005_c20261010006.nc`
- Himawari: `HS_H09_20260401_0000_B07_FLDK_R20_S0110.DAT`
- VIIRS: `SVI04_j01_d20260401_t0000000_e0006000_b00001_c20260401010000.h5`

Parse these filenames to extract timestamp, band, and segment info without opening
the file — this saves significant I/O in the data ingestion pipeline.
