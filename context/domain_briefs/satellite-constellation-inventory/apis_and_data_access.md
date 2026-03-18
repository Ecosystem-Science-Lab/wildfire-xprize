# APIs and Data Access for Fire Detection Satellites

## Priority 1: Fastest Data Sources for NSW

### 1. NASA FIRMS (Fire Information for Resource Management System)

**What it provides:** Near-real-time active fire detections from VIIRS, MODIS, and geostationary satellites (including Himawari).

**Registration:**
- Get a MAP_KEY at: https://firms.modaps.eosdis.nasa.gov/api/map_key/
- Free. Rate limit: 5,000 transactions per 10-minute interval.

**API Endpoints:**
- Area query: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{area}/{days}`
- Data availability: `https://firms.modaps.eosdis.nasa.gov/api/data_availability/`
- KML fire footprints: `https://firms.modaps.eosdis.nasa.gov/api/kml_fire_footprints/`

**Data sources available:**
- `VIIRS_SNPP_NRT` -- Suomi NPP VIIRS NRT
- `VIIRS_NOAA20_NRT` -- NOAA-20 VIIRS NRT
- `VIIRS_NOAA21_NRT` -- NOAA-21 VIIRS NRT
- `MODIS_NRT` -- Combined Terra/Aqua MODIS NRT
- `LANDSAT_NRT` -- Landsat active fire (US/Canada only)
- Geostationary sources (Himawari, GOES, Meteosat) via FIRMS

**Output formats:** CSV, SHP, KML, JSON

**Latency:**
- VIIRS/MODIS global NRT: up to ~3 hours
- VIIRS RT: ~30 min (where available)
- VIIRS URT: ~5 min (US/Canada only -- NOT available for Australia)
- Geostationary (Himawari): ~30 min post-observation

**NSW bounding box for queries:** `-37,-28,148,154` (S,N,W,E) or use country code `AUS`

---

### 2. AWS NODD -- Himawari Data (Push-enabled)

**What it provides:** Near-real-time Himawari-8/9 full-resolution imagery.

**S3 Bucket:** `s3://noaa-himawari` (region: varies)
- Registry: https://registry.opendata.aws/noaa-himawari/

**Access:** No subscription required. Open data.

**SNS Notifications:** Check registry for SNS topic ARN for new-object notifications (enables push-driven ingestion).

**Data format:** Himawari Standard Data (HSD) format. NetCDF also available.

**Latency:** Near-real-time mirroring from JMA. Expect data within minutes of JMA release.

**Licensing:** Open use. Attribution to NOAA/JMA requested. No implied endorsement.

---

### 3. AWS NODD -- GK-2A Data

**What it provides:** GK-2A AMI full-disk imagery.

**S3 Bucket:** `s3://noaa-gk2a-pds`
- Registry: https://registry.opendata.aws/noaa-gk2a-pds/

**Access:** No subscription required. Open data.

**Data:** AMI full-disk every 10 min. 4 visible + 12 IR channels.

**Contact:** nodd@noaa.gov for questions.

---

### 4. AWS NODD -- JPSS (VIIRS) Data (Push-enabled)

**What it provides:** Near-real-time VIIRS/JPSS data (S-NPP, NOAA-20, NOAA-21).

**S3 Buckets:** JPSS S3 buckets via NODD
- Registry: search for "JPSS" at https://registry.opendata.aws/

**SNS Notifications:** Available for push-driven ingestion.

**Latency:** Variable. Dependent on uplink to NOAA ground stations (Norway, Alaska, Antarctica, New Mexico). Upstream SDR production within ~80 min.

---

### 5. JAXA P-Tree (Himawari Archive + NRT)

**What it provides:** Himawari Standard Data and JAXA-derived geophysical products.

**Registration:** https://www.eorc.jaxa.jp/ptree/registration_top.html
- Free registration. Email verification required.

**Data access:** FTP download after login. NRT + archive from March 2015.

**Latency:** 5-20 minutes after observation (real-time data).

**Licensing:** From Feb 1, 2026: commercial use permitted. Before that: non-profit only.

---

### 6. Digital Earth Australia Hotspots

**What it provides:** Integrated Australian hotspot monitoring from Himawari, VIIRS, MODIS, AVHRR.

**Web interface:** https://hotspots.dea.ga.gov.au/

**Web services:**
- WMS (Web Map Service): for visualization
- WFS (Web Feature Service): for data download/integration

**Update frequency:** Every 10 minutes.

**API/download:** Available. No registration required.

---

## Priority 2: Medium-Latency Data Sources

### 7. Copernicus Data Space Ecosystem (Sentinel-2, Sentinel-3, Sentinel-1, Sentinel-5P)

**What it provides:** All Copernicus Sentinel mission data.

**Portal:** https://dataspace.copernicus.eu/

**Registration:** Free account registration required.

**APIs:**
- STAC API for catalog search
- OData API for product download
- openEO API for server-side processing
- Sentinel Hub APIs (OAuth-based) for visualization and processing
- All require access token (generated after registration)

**Relevant products:**
- Sentinel-3 SLSTR FRP (Fire Radiative Power) -- NRT ~3 hours
- Sentinel-2 MSI L1C/L2A -- NRT 100 min - 3 hours
- Sentinel-1 GRD/SLC -- for burn area mapping
- Sentinel-5P TROPOMI -- aerosol/smoke products

**Latency:**
- Sentinel-3: ~3 hours after sensing
- Sentinel-2 NRT: 100 min - 3 hours
- Sentinel-2 Nominal: 3-24 hours

---

### 8. USGS EarthExplorer / Landsat

**What it provides:** Landsat 8 and 9 data (OLI/TIRS).

**Portal:** https://earthexplorer.usgs.gov/

**Cloud access:**
- AWS S3: Landsat Collection 2 (open data)
- Google Earth Engine: Full Landsat archive

**Registration:** USGS EROS account required (free).

**Latency:** Level-1 Real-Time scenes: ~4-6 hours after acquisition. Standard: 12-24 hours.

**Licensing:** Public domain (USGS).

---

### 9. NASA Earthdata / LANCE

**What it provides:** Near-real-time data from NASA missions (MODIS, VIIRS, OMPS, etc.).

**Portal:** https://www.earthdata.nasa.gov/

**Registration:** NASA Earthdata Login required (free).

**LANCE NRT:**
- MODIS NRT: https://lance.modaps.eosdis.nasa.gov/
- VIIRS Land NRT: https://www.earthdata.nasa.gov/data/instruments/viirs/land-near-real-time-data
- OMPS NRT aerosol index via LANCE

**Latency:** LANCE NRT typically 1-3 hours.

---

### 10. ECOSTRESS Data

**Portal:** https://e4ftl01.cr.usgs.gov/ECOSTRESS/

**Access:** NASA Earthdata Login required.

**Products:** Land surface temperature and emissivity at 70m resolution.

**Latency:** Hours to days (no NRT fire product).

---

## Priority 3: Supplementary / Research-Grade Sources

### 11. NSMC Fengyun Satellite Data Center (FY-3, FY-4)

**What it provides:** FY-3D/3E/3F and FY-4A/4B data and products.

**Portal:** https://satellite.nsmc.org.cn/ (also http://data.nsmc.org.cn)

**Registration:** Free registration for international users.

**Data push:** Bulk users can request FTP push delivery.

**Products:** FY-3D global active fire product. FY-4A/4B Fire/Hotspot (FHS) product.

**Latency:** Near real-time data available. Actual latency for international users may vary.

**Note:** Data access reliability from China may be a concern for real-time competition use. Test thoroughly before depending on it.

---

### 12. EUMETSAT (MetOp AVHRR, Meteosat)

**Portal:** https://user.eumetsat.int/

**Data Store:** https://data.eumetsat.int/

**Registration:** Required. Free for most data with >1 hour latency.

**EUMETCast:** Broadcast-based NRT delivery (requires receiving equipment or subscription).

**Licensing constraint:** EUMETSAT "Recommended" data with <1 hour timeliness generally requires annual fee. Data with >1 hour latency is free to end users.

**MetOp AVHRR products:** Available via Data Store and EUMETCast.

**Latency:** Average ~47 min for MetOp products.

---

### 13. OroraTech Wildfire Solution

**Portal:** https://ororatech.com/

**Access:** Commercial service. Web interface + API.

**Products:** Active fire detection, fire perimeter, heat maps, alerts.

**Latency:** <10 min from detection to alert.

**Pricing:** Not publicly disclosed. Contact OroraTech directly.

**Note:** May be worth contacting for competition partnership/data access agreement.

---

### 14. Direct Broadcast (Australian Ground Stations)

**What it provides:** Real-time satellite data from polar-orbiting satellites as they pass over Australia.

**Australian stations receiving satellite data:**
- **Geoscience Australia, Alice Springs** -- receives MODIS, AVHRR, VIIRS (processes L0 MODIS, NOAA HDF AVHRR, VIIRS RDR)
- **AIMS, Townsville (QLD)** -- receives NOAA AVHRR, MODIS (Terra/Aqua), Suomi NPP
- **Bureau of Meteorology** -- stations in Perth, Melbourne, Darwin

**Processing:** CSPP (Community Satellite Processing Package) for converting direct broadcast to science products.

**Latency:** ~5-15 minutes after overpass (fastest possible path for VIIRS/MODIS data).

**Relevance:** This is the FASTEST way to get VIIRS data for NSW -- if the ground station captures the pass. Alice Springs is well-positioned for NSW overpasses.

---

## Quick Reference: Registration Checklist

| Service | URL | Registration | Priority |
|---|---|---|---|
| NASA FIRMS API | firms.modaps.eosdis.nasa.gov/api/map_key/ | MAP_KEY request | CRITICAL |
| NASA Earthdata Login | urs.earthdata.nasa.gov | Account creation | CRITICAL |
| JAXA P-Tree | eorc.jaxa.jp/ptree/registration_top.html | Email registration | HIGH |
| Copernicus Data Space | dataspace.copernicus.eu | Account creation | HIGH |
| USGS EROS | ers.cr.usgs.gov/register | Account creation | MEDIUM |
| NSMC Fengyun | satellite.nsmc.org.cn | Registration | MEDIUM |
| EUMETSAT | user.eumetsat.int | Account creation | LOW |
| OroraTech | ororatech.com | Commercial inquiry | OPTIONAL |
| DEA Hotspots | hotspots.dea.ga.gov.au | None required | HIGH |
| AWS (NODD data) | aws.amazon.com | AWS account | HIGH |
