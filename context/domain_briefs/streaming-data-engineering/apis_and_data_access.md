# APIs and Data Access: Satellite Data Ingestion

## Scope

Concrete endpoints, bucket paths, ARNs, authentication, and data formats for every satellite data source relevant to the wildfire detection system. Competition is in NSW Australia (April 2026), so Himawari-9 is the primary geostationary source; GOES is irrelevant for Australia coverage but documented here for general completeness and potential Western Hemisphere use.

---

## 1. NOAA Open Data Dissemination (NODD) -- AWS

All NOAA satellite data on AWS follows the same pattern: public S3 buckets (no auth required) with SNS topics that fire on every new object. SNS topics only support **SQS and Lambda** subscription protocols (no HTTP/HTTPS/email).

### Measured Latency (from NODD Science Advances paper, 2023)

- **GOES-16 transfer latency** (NOAA on-prem to cloud): 0.2--0.3 seconds
- **GOES-16 end-to-end latency** (data generation to publicly available on S3): ~24 seconds
- **Daily throughput**: >100 TB/day baseline, spikes well above
- **Pipeline technology**: Apache NiFi instances on each cloud provider

---

## 2. GOES ABI Data (Americas coverage -- not for Australia)

GOES-East (GOES-19 as of April 2025) and GOES-West (GOES-18) provide Americas/Atlantic/Pacific coverage. No useful coverage of NSW.

### S3 Buckets

| Satellite | Bucket | ARN | Region |
|-----------|--------|-----|--------|
| GOES-19 (East) | `noaa-goes19` | `arn:aws:s3:::noaa-goes19` | us-east-1 |
| GOES-18 (West) | `noaa-goes18` | `arn:aws:s3:::noaa-goes18` | us-east-1 |
| GOES-16 (decommissioning) | `noaa-goes16` | `arn:aws:s3:::noaa-goes16` | us-east-1 |

### SNS Topic ARNs (New Object Notifications)

| Satellite | SNS Topic ARN |
|-----------|---------------|
| GOES-19 | `arn:aws:sns:us-east-1:123901341784:NewGOES19Object` |
| GOES-18 | `arn:aws:sns:us-east-1:123901341784:NewGOES18Object` |
| GOES-16 | `arn:aws:sns:us-east-1:123901341784:NewGOES16Object` |

**Protocols supported**: SQS and Lambda only (no HTTP/email).

### S3 Path Structure

```
s3://noaa-goes18/<Product>/<Year>/<DayOfYear>/<Hour>/<filename>.nc
```

Example fire product path:
```
s3://noaa-goes18/ABI-L2-FDCF/2026/107/03/OR_ABI-L2-FDCF-M6_G18_s20261070300215_e20261070309534_c20261070310031.nc
```

### File Naming Convention

```
OR_ABI-L2-FDCF-M6_G18_s20261070300215_e20261070309534_c20261070310031.nc
│  │         │  │    │                 │                 │
│  │         │  │    │                 │                 └── c = creation time (YYYYDDDHHMMSSt)
│  │         │  │    │                 └── e = scan end time
│  │         │  │    └── s = scan start time
│  │         │  └── G18 = GOES-18
│  │         └── M6 = Mode 6 (standard flex mode)
│  └── ABI-L2-FDCF = ABI Level 2 Fire Detection Characterization Full Disk
└── OR = Operational Real-time
```

### Key Fire-Relevant Products

| Product Code | Description | Cadence |
|-------------|-------------|---------|
| `ABI-L2-FDCF` | Fire/Hot Spot Characterization, Full Disk | 10 min |
| `ABI-L2-FDCC` | Fire/Hot Spot Characterization, CONUS | 5 min |
| `ABI-L2-FDCM` | Fire/Hot Spot Characterization, Mesoscale | 1 min |
| `ABI-L1b-RadF` | Level 1b Radiances, Full Disk | 10 min |
| `ABI-L2-CMIPC` | Cloud & Moisture Imagery, CONUS | 5 min |

The FDC product contains 4 fields per pixel: fire mask, fire temperature (K), fire area (km^2), fire radiative power (MW). Resolution: 2 km. Format: NetCDF4.

### Scanning Modes

| Mode | Description |
|------|-------------|
| M3 | Full Disk + CONUS + 2 Mesoscale |
| M4 | Full Disk only (every 5 min) |
| M6 | Flex mode (current standard operational mode) |

### Access (no auth required)

```bash
aws s3 ls --no-sign-request s3://noaa-goes18/ABI-L2-FDCF/2026/107/
```

---

## 3. Himawari-9 AHI Data (PRIMARY for NSW competition)

Himawari-9 is the operational geostationary satellite at 140.7E, covering East Asia, Australia, and Western Pacific. This is the primary geostationary data source for NSW.

### S3 Buckets

| Satellite | Bucket | ARN | Region |
|-----------|--------|-----|--------|
| Himawari-9 | `noaa-himawari9` | `arn:aws:s3:::noaa-himawari9` | us-east-1 |
| Himawari-8 (historical) | `noaa-himawari8` | `arn:aws:s3:::noaa-himawari8` | us-east-1 |

### SNS Topic ARNs

| Satellite | SNS Topic ARN |
|-----------|---------------|
| Himawari-9 | `arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject` |
| Himawari-8 | `arn:aws:sns:us-east-1:123901341784:NewHimawari8Object` |

**Protocols supported**: SQS and Lambda only.

### Scan Cadence

| Region | Cadence | Notes |
|--------|---------|-------|
| Full Disk (FLDK) | 10 min | Covers entire visible Earth disk |
| Regions 1, 2, 3 | 2.5 min | Japan and target areas |
| Regions 4, 5 | 30 sec | Landmark/calibration |

For NSW wildfire detection, **Full Disk at 10-minute cadence** is the relevant product unless JMA designates NSW as a target region.

### S3 Path Structure

```
s3://noaa-himawari9/AHI-L1b-FLDK/<year>/<month>/<day>/<hour><minute>/
```

### File Format

- **Himawari Standard Data (HSD)** format, `.DAT` extension
- File naming: `HS_H09_YYYYMMDD_HHMM_B##_R###_R##_S####.DAT`
  - `HS` = Himawari Standard format
  - `H09` = Himawari-9
  - `B##` = Band number (01--16)
  - `R###` = Resolution indicator
  - `S####` = Segment number (full disk is split into 10 segments)
- Band 7 (3.9 um MWIR) is the primary fire detection band at 2 km resolution

### AHI Bands Relevant to Fire Detection

| Band | Wavelength (um) | Resolution | Fire Use |
|------|----------------|------------|----------|
| B03 | 0.64 | 500 m | Smoke/cloud masking |
| B07 | 3.9 | 2 km | Primary fire detection (MWIR) |
| B14 | 11.2 | 2 km | Background temperature |
| B15 | 12.4 | 2 km | Split window cloud masking |

### Estimated Data Latency

NODD handles ~41,000 files/day from JMA. End-to-end latency is not as well documented as GOES but NODD adds <1 second of transfer latency; the bottleneck is JMA's ground processing and relay to NOAA. Expect **2--5 minutes** from observation to S3 availability (based on JMA processing pipeline). This is significantly worse than GOES's ~24 seconds because data must traverse JMA -> NOAA -> AWS rather than NOAA ground station -> AWS directly.

### Alternative Access: JMA HimawariCloud

For lower latency (potentially faster than NODD), authorized NMHSs can access HimawariCloud directly from JMA via HTTP 1.1. This requires registration with JMA. Data is served from JMA infrastructure, not AWS. URL patterns use HTTP GET with wget-compatible paths.

- Contact: JMA Meteorological Satellite Center
- Protocol: HTTP 1.1 (wget/curl compatible)
- Requirement: Must be an NMHS or have JMA authorization

---

## 4. JPSS/VIIRS Data (LEO polar orbiters)

VIIRS on NOAA-20 and NOAA-21 provides 375m fire detection. These are polar orbiters, so coverage of any given point is periodic (typically 2--4 overpasses/day at mid-latitudes), not continuous.

### S3 Buckets

| Satellite | Bucket | ARN | Region |
|-----------|--------|-----|--------|
| NOAA-20 | `noaa-nesdis-n20-pds` | `arn:aws:s3:::noaa-nesdis-n20-pds` | us-east-1 |
| NOAA-21 | `noaa-nesdis-n21-pds` | `arn:aws:s3:::noaa-nesdis-n21-pds` | us-east-1 |
| Suomi NPP | `noaa-nesdis-snpp-pds` | `arn:aws:s3:::noaa-nesdis-snpp-pds` | us-east-1 |
| Dev/Blended | `noaa-jpss` | `arn:aws:s3:::noaa-jpss` | us-east-1 |

### SNS Topic ARNs

| Satellite | SNS Topic ARN |
|-----------|---------------|
| NOAA-20 | `arn:aws:sns:us-east-1:709902155096:NewNOAA20Object` |
| NOAA-21 | `arn:aws:sns:us-east-1:709902155096:NewNOAA21Object` |
| Suomi NPP | `arn:aws:sns:us-east-1:709902155096:NewSNPPObject` |
| Dev | `arn:aws:sns:us-east-1:709902155096:NewJPSSObject` |

**Note different AWS account**: JPSS topics are in account `709902155096`, while GOES/Himawari topics are in `123901341784`.

**Protocols supported**: SQS and Lambda only.

### VIIRS Active Fire Products in S3

The VIIRS Active Fire EDR (Environmental Data Record) is available within the satellite-specific buckets. Files are NetCDF4 format, aggregated into 10-minute TAR files containing 7 granules (~86 seconds each). Key products:

- `VIIRS_AF_I-band` -- 375m resolution active fire detections
- `VIIRS_AF_M-band` -- 750m resolution active fire detections

### Access

```bash
aws s3 ls --no-sign-request s3://noaa-nesdis-n20-pds/
```

---

## 5. NASA FIRMS API (Active Fire Aggregated Data)

FIRMS provides processed active fire detections from multiple sensors via a simple REST API. This is NOT raw satellite data -- it's processed fire point data.

### Registration

1. Go to: `https://firms.modaps.eosdis.nasa.gov/api/map_key/`
2. Submit email address
3. Receive 32-character MAP_KEY by email

### Rate Limits

- 5,000 transactions per 10-minute interval
- Large requests may count as multiple transactions
- Contact FIRMS for higher limits

### Data Timeliness Tiers

| Tier | Latency from observation | Availability |
|------|------------------------|--------------|
| **URT** (Ultra Real-Time) | <60 seconds (US only), ~50 sec for VIIRS | Rolls off after 6 hours |
| **RT** (Real-Time) | ~30 minutes | Rolls off after 6 hours |
| **NRT** (Near Real-Time) | <3 hours | Replaces URT/RT data |
| **SP** (Standard Product) | Days to weeks | Permanent archive |

**Critical note**: URT data is US/Canada only via direct broadcast ground stations. For NSW Australia, expect NRT latency (~3 hours) at best.

### Area API Endpoint

**Base URL**: `https://firms.modaps.eosdis.nasa.gov/api/area/`

**URL pattern**:
```
https://firms.modaps.eosdis.nasa.gov/api/area/{format}/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}
https://firms.modaps.eosdis.nasa.gov/api/area/{format}/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}/{DATE}
```

**Parameters**:

| Parameter | Values | Example |
|-----------|--------|---------|
| `format` | `csv`, `kml` | `csv` |
| `MAP_KEY` | 32-char key | `e13b4abcdef1234567890abcdef12345` |
| `SOURCE` | See table below | `VIIRS_NOAA20_NRT` |
| `AREA` | `west,south,east,north` or `world` | `148,-37,154,-28` (NSW) |
| `DAY_RANGE` | 1--10 | `1` |
| `DATE` (optional) | `YYYY-MM-DD` | `2026-04-15` |

**Available Sources**:

| Source | Sensor | Satellite | Data Tier |
|--------|--------|-----------|-----------|
| `MODIS_NRT` | MODIS | Terra/Aqua | NRT |
| `MODIS_SP` | MODIS | Terra/Aqua | Standard |
| `VIIRS_SNPP_NRT` | VIIRS | Suomi NPP | NRT |
| `VIIRS_SNPP_SP` | VIIRS | Suomi NPP | Standard |
| `VIIRS_NOAA20_NRT` | VIIRS | NOAA-20 | NRT |
| `VIIRS_NOAA20_SP` | VIIRS | NOAA-20 | Standard |
| `VIIRS_NOAA21_NRT` | VIIRS | NOAA-21 | NRT |
| `LANDSAT_NRT` | OLI | Landsat 8/9 | NRT (US/Canada only) |

**Example request for NSW fires**:
```
https://firms.modaps.eosdis.nasa.gov/api/area/csv/YOUR_MAP_KEY/VIIRS_NOAA20_NRT/148,-37,154,-28/1
```

### CSV Output Columns

#### VIIRS CSV Columns

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `latitude` | float | degrees | Center of 375m fire pixel |
| `longitude` | float | degrees | Center of 375m fire pixel |
| `bright_ti4` | float | Kelvin | I-4 channel (3.74 um) brightness temperature |
| `scan` | float | meters | Along-scan pixel dimension |
| `track` | float | meters | Along-track pixel dimension |
| `acq_date` | date | YYYY-MM-DD | Acquisition date |
| `acq_time` | time | HH:MM UTC | Satellite overpass time |
| `satellite` | string | code | `N` (NPP), `N20`, `N21` |
| `confidence` | string | category | `low`, `nominal`, `high` |
| `version` | string | text | e.g., `2.0NRT` |
| `bright_ti5` | float | Kelvin | I-5 channel brightness temperature |
| `frp` | float | MW | Fire radiative power |
| `daynight` | char | code | `D` or `N` |

#### MODIS CSV Columns

| Column | Type | Units | Description |
|--------|------|-------|-------------|
| `latitude` | float | degrees | Center of 1km fire pixel |
| `longitude` | float | degrees | Center of 1km fire pixel |
| `brightness` | float | Kelvin | Channel 21/22 brightness temperature |
| `scan` | float | km | Along-scan pixel dimension |
| `track` | float | km | Along-track pixel dimension |
| `acq_date` | date | YYYY-MM-DD | Acquisition date |
| `acq_time` | time | HH:MM UTC | Satellite overpass time |
| `satellite` | char | code | `A` (Aqua) or `T` (Terra) |
| `confidence` | int | percent | 0--100 fire detection quality |
| `version` | string | text | e.g., `6.1NRT` |
| `bright_t31` | float | Kelvin | Channel 31 brightness temperature |
| `frp` | float | MW | Fire radiative power |
| `type` | int | code | 0=vegetation, 1=volcano, 2=static land, 3=offshore |
| `daynight` | char | code | `D` or `N` |

### Data Availability API

Check which dates have data available:
```
https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{MAP_KEY}/{SOURCE}
```

### Update Cadence

- FIRMS fire maps update every **5 minutes**
- SHP/KML/CSV bulk files update every **60 minutes**

---

## 6. Copernicus Data Space -- Sentinel-3 SLSTR Fire Products

Sentinel-3A and 3B carry the SLSTR instrument which produces fire radiative power (FRP) products at 1 km resolution.

### STAC API

**Base URL**: `https://stac.dataspace.copernicus.eu/v1/`

**Key endpoints**:
- `GET /collections` -- list all collections
- `GET /collections/{collection_id}/items` -- browse items
- `POST /search` -- search across collections
- `GET /collections/{collection_id}/queryables` -- filterable attributes

**Browser UI**: `https://browser.stac.dataspace.copernicus.eu`

### Relevant Sentinel-3 SLSTR Collections

| Collection | Description |
|-----------|-------------|
| Sentinel-3 SLSTR Level-2 FRP (NRT) | Near real-time fire radiative power |
| Sentinel-3 SLSTR Level-1 RBT (NRT) | Radiance/brightness temperatures |

### STAC Search Example

```
POST https://stac.dataspace.copernicus.eu/v1/search
Content-Type: application/json

{
  "collections": ["sentinel-3-slstr-frp"],
  "bbox": [148, -37, 154, -28],
  "datetime": "2026-04-15T00:00:00Z/2026-04-16T00:00:00Z",
  "limit": 50
}
```

**Filter with CQL2 (GET)**:
```
/v1/collections/sentinel-3-slstr-frp/items?filter-lang=cql2-text&filter=S_INTERSECTS(geometry, POLYGON((148 -37, 154 -37, 154 -28, 148 -28, 148 -37)))
```

### Authentication

- STAC catalog browsing: no auth required
- Product download: requires access token from Copernicus Data Space Ecosystem
  - Register at: `https://dataspace.copernicus.eu/`
  - OAuth2 token endpoint for programmatic access

### Sentinel-3 SLSTR FRP Product Details

- **Latency**: NRT product generated in <2.5 hours from observation
- **Granule duration**: 5-minute segments
- **Resolution**: 1 km (fire detection), 500m (nighttime SWIR fire product)
- **Files**: `FRP_in.nc` (nadir view fires), `FRP_an.nc`/`FRP_bn.nc` (oblique view, 500m, nighttime)
- **Format**: NetCDF

### Legacy Endpoint (DEPRECATED)

`https://catalogue.dataspace.copernicus.eu/stac` -- deprecated since Nov 17, 2025. Use the `stac.dataspace.copernicus.eu` endpoint above.

---

## 7. Sentinel-2 MSI (Optical, 20m SWIR)

Sentinel-2 has 20m SWIR bands useful for fire detection but is NOT a fire-specific product. Revisit time is ~5 days per satellite (2 satellites = ~2.5 days). Not useful for real-time detection, but can confirm/characterize fires detected by other sensors.

### STAC Access

Same Copernicus Data Space STAC API as above:

```
POST https://stac.dataspace.copernicus.eu/v1/search
{
  "collections": ["sentinel-2-l2a"],
  "bbox": [148, -37, 154, -28],
  "datetime": "2026-04-15T00:00:00Z/2026-04-16T00:00:00Z",
  "filter": {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 30]},
  "limit": 50
}
```

---

## 8. SNS Notification Message Format

All NOAA NODD SNS notifications follow standard AWS S3 event notification format. When consumed via SQS, the message is triple-nested JSON:

**Layer 1: SQS envelope** -> **Layer 2: SNS message** -> **Layer 3: S3 event Records**

The S3 event Records contain:

```json
{
  "Records": [{
    "eventVersion": "2.1",
    "eventSource": "aws:s3",
    "awsRegion": "us-east-1",
    "eventTime": "2026-04-15T03:10:03.000Z",
    "eventName": "ObjectCreated:Put",
    "s3": {
      "bucket": {
        "name": "noaa-himawari9",
        "arn": "arn:aws:s3:::noaa-himawari9"
      },
      "object": {
        "key": "AHI-L1b-FLDK/2026/04/15/0300/HS_H09_20260415_0300_B07_R201_R20_S0101.DAT",
        "size": 12345678
      }
    }
  }]
}
```

**Important**: The object key is URL-encoded in the notification. Decode before constructing S3 paths.

---

## 9. Quick Reference: Which Sources for NSW Competition

| Source | Type | Resolution | Cadence | Latency to AWS | Fire Product? |
|--------|------|-----------|---------|----------------|--------------|
| **Himawari-9 AHI** | GEO | 2 km | 10 min | ~2--5 min (est.) | No standard product; run own algorithm |
| **VIIRS (NOAA-20/21)** | LEO | 375 m | 2--4x/day | NRT: <3 hrs; NODD raw: minutes | AF EDR in S3 |
| **FIRMS API** | Aggregated | Various | NRT: 3 hrs | N/A | Yes (processed points) |
| **Sentinel-3 SLSTR** | LEO | 1 km | ~1x/day | <2.5 hrs NRT | FRP product |
| **Sentinel-2 MSI** | LEO | 20 m | ~2.5 days | Hours | No; raw SWIR |

The winning strategy is Himawari-9 for continuous monitoring (10-min cadence with own fire algorithm on raw bands) supplemented by VIIRS for higher-resolution confirmation when overpasses occur.
