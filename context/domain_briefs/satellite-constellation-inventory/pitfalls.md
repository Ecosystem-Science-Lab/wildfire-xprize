# Pitfalls: Coverage Gaps, Data Access Gotchas, and Risks

## 1. Satellites at Risk of Decommissioning Before/During April 2026

### HIGH RISK

| Satellite | Risk | Details |
|---|---|---|
| **ASTER TIR (Terra)** | ALREADY DEAD | TIR subsystem permanently shut down January 2026 due to Terra power limitations. Thermal control powered off Feb 2026. VNIR-only operation continues. Do NOT plan on ASTER thermal data. |
| **Aqua MODIS** | MODERATE | Free-drift orbit since Dec 2021. Science data collection planned through Sep 2027. Passivation scheduled Nov 2026. Should be operational in April 2026 but orbit is degrading -- overpass timing shifting to later local times, altitude dropping. |
| **Terra MODIS** | MODERATE | Orbit drifting (crossing time shifting from 10:30 to ~08:30 by late 2026). Science data collection planned through Feb 2027. Still operational in April 2026 but with degraded data quality and changing overpass geometry. |

### LOW RISK

| Satellite | Risk | Details |
|---|---|---|
| **Suomi NPP** | LOW | EOL extended to Dec 2028. Orbit drifting but VIIRS still functional. |
| **Himawari-9** | LOW | Experienced anomaly Oct 2025, restored Nov 2025. Now operational again. Backup (Himawari-8) available. Both operational until ~2030. |

### NO RISK

All other satellites in the catalog (NOAA-20, NOAA-21, Sentinel-2B/C, Sentinel-3A/B, MetOp-B/C, FY-3D/E/F, Landsat 8/9, etc.) have no known decommissioning concerns for April 2026.

---

## 2. Data Access Gotchas

### FIRMS Limitations

- **URT (Ultra-Rapid) is US/Canada only.** The <5-minute VIIRS fire detections are NOT available for Australia. Global FIRMS is NRT only (up to ~3 hours latency). This is a critical gap -- you cannot rely on FIRMS for sub-hour VIIRS data over NSW.
- **Rate limits:** 5,000 transactions per 10-minute interval. If polling multiple sources frequently, you could hit this limit.
- **MAP_KEY required:** Must register in advance. Don't wait until competition day.
- **Geostationary fire detections are "provisional."** The Himawari-9 KCL/IPMA fire product in FIRMS is labeled provisional, meaning quality may vary.
- **No Landsat active fire for Australia.** FIRMS Landsat fire detections are US/Canada only. For NSW, you must run your own Landsat fire detection algorithm on L1 data.

### Himawari Data Access

- **HimawariCloud is restricted.** Full-resolution, lowest-latency Himawari data via HimawariCloud is primarily for National Meteorological and Hydrological Services (NMHSs). General users must use JAXA P-Tree or AWS NODD.
- **JAXA P-Tree latency: 5-20 minutes.** This is faster than FIRMS but requires self-processing of raw data. Must implement your own fire detection on L1b data.
- **Commercial use restriction lifted only from Feb 2026.** Data from before Feb 2026 is restricted to non-profit use. Data from Feb 2026 onward is available for commercial use.
- **AWS NODD Himawari bucket.** Verify SNS notification topic is still active and functioning. Test push-driven ingestion well before competition.

### EUMETSAT Data Licensing

- **<1 hour timeliness requires a fee.** EUMETSAT's data policy gates MetOp AVHRR and Meteosat data timeliness. "Recommended" data with <1 hour latency requires an annual flat fee. Data with >1 hour latency is free. This applies to MetOp-B and MetOp-C AVHRR data via EUMETCast.
- **EUMETCast requires receiving equipment** or subscription. Not a simple API call.

### Chinese Satellite Data (FY-3, FY-4)

- **NSMC data center reliability.** International access to the Fengyun data center may have latency, bandwidth, or availability issues. Test thoroughly before depending on it for real-time operations.
- **Language barriers.** Some documentation and interfaces are primarily in Chinese.
- **Data formats may be non-standard.** FY-4B AGRI data format is specific and may require specialized decoders (e.g., geo2grid supports AGRI).

### Russian Satellite Data (Meteor-M)

- **Extremely limited international access.** Official data products from Roshydromet are essentially inaccessible for real-time international use.
- **Direct broadcast only practical path.** Meteor-M transmits on 137 MHz LRPT, receivable by amateur radio stations. However, this requires ground station infrastructure in view of the satellite.
- **No operational fire product** for international users.

### Copernicus Data Latency

- **Sentinel-3 SLSTR FRP is "preliminary operational."** Not a mature product. Quality may be inconsistent. NRT latency ~3 hours makes it too slow for real-time fire detection but useful for confirmation.
- **Sentinel-2 NRT timeliness varies.** The "100 minutes to 3 hours" NRT class is the target, but actual timeliness depends on ground segment loading and the specific ground station that captures the data.

### Direct Broadcast Dependencies

- **Not all Australian stations are publicly accessible.** Geoscience Australia Alice Springs station processes data for DEA Hotspots, but direct access to raw L0 data from this station may not be available to competition participants.
- **CSPP processing required.** Direct broadcast data requires Community Satellite Processing Package (CSPP) to convert raw data streams into usable products. This adds processing overhead and requires setup.

---

## 3. Coverage Gaps

### Temporal Gaps (LEO)

- **No VIIRS pass for ~2-3 hours at a time.** Despite 3 VIIRS satellites, there are periods of 2-3 hours between NSW overpasses. During these windows, only geostationary satellites provide coverage.
- **Geostationary 10-minute cadence is the floor.** Between VIIRS passes, the fastest fire detection possible is via Himawari-9 with 10-minute full-disk cycle. A fire igniting between Himawari scans may not be detected for up to 10 minutes.
- **Nighttime SWIR gap.** Sentinel-2 SWIR-based fire detection requires solar illumination. At night, only thermal sensors (VIIRS I4/I5, Himawari MIR/TIR, MODIS, SLSTR) are effective.

### Spatial Gaps

- **Geostationary pixel size at NSW latitudes: 3-4 km.** Minimum detectable fire size from Himawari over NSW is approximately 1,000-4,000 m2 under favorable conditions. Small fires (<1,000 m2) will be missed by geostationary sensors.
- **VIIRS 375m has known edge-of-swath gaps.** While VIIRS has better pixel growth control than MODIS, there can be small gaps between adjacent swaths at certain latitudes.
- **Landsat/Sentinel-2 narrow swaths.** Landsat (185 km swath) and Sentinel-2 (290 km swath) may miss a fire entirely between revisits. NSW is ~600 km wide, so a single Landsat pass covers only a strip.

### Atmospheric/Environmental Gaps

- **Cloud cover blocks ALL optical/thermal sensors.** Geostationary and polar-orbiting thermal sensors cannot detect fires through thick cloud. SAR (Sentinel-1) can see through clouds but cannot detect active fires.
- **Sun glint causes false positives.** Geostationary MIR bands are affected by solar reflections off water/land in specific sun-satellite geometry configurations. Mid-afternoon observations over eastern Australia can be affected.
- **Smoke itself can obscure detections.** Large established fires produce smoke that can interfere with detection of new ignitions nearby. SWIR (Sentinel-2, Landsat, WorldView-3) penetrates smoke better than TIR.

---

## 4. Algorithm and Processing Pitfalls

### False Positive Sources

- **Hot bare ground / desert surfaces.** Western NSW has semi-arid terrain that heats significantly during the day. Background temperature in April (autumn) is lower than summer, but still a concern for afternoon geostationary observations.
- **Urban heat islands.** Sydney, Newcastle, Wollongong metropolitan areas generate thermal signatures that can trigger false positives without proper masking.
- **Industrial facilities.** Power plants, smelters, refineries produce hot spots that algorithms must mask. NSW has several large power stations.
- **Sun glint on water.** Coastal NSW and inland water bodies can produce bright MIR returns that mimic fire signatures.
- **Cloud edges.** Rapidly clearing cloud can cause brightness temperature gradients that resemble fire-edge signatures.

### Orbit Degradation Effects

- **Terra/Aqua overpass timing drift.** As orbits degrade, overpass times shift. Fire detection algorithms calibrated to specific diurnal temperature cycles may need adjustment. Terra's crossing time will be ~08:30 instead of 10:30 by late 2026 -- this means different solar illumination and background temperatures.
- **Swath narrowing.** As Terra/Aqua lose altitude, swath width slightly narrows, potentially creating gaps in coverage that didn't exist before.

### Data Format Challenges

- **Multiple coordinate systems.** Geostationary data uses fixed-grid projections centered on the sub-satellite point. Polar-orbiting data uses sensor-centric scan coordinates. Converting between systems for multi-sensor fusion requires careful handling.
- **Different fire product formats.** FIRMS CSV format differs between VIIRS, MODIS, and geostationary sources. Field names and meanings vary (e.g., "brightness" vs "bright_ti4", "confidence" levels have different scales).
- **Reprojection artifacts.** Resampling geostationary pixels (3-4 km at NSW) onto a fine grid introduces interpolation errors. Work in native sensor coordinates when possible.

---

## 5. Competition-Specific Risks

### Scoring Timing Ambiguity

- The competition scores based on detection within "1 minute from overpass" -- but the exact definition of "overpass" and "data availability" may differ from your internal tracking. Clarify with XPRIZE whether this means:
  - 1 minute from the satellite passing overhead?
  - 1 minute from data being made available on a specific platform?
  - 1 minute from the fire actually occurring?

### Network Reliability

- **Internet connectivity in NSW field sites.** Competition scoring may depend on connectivity from the field to cloud infrastructure. Ensure redundant connectivity.
- **AWS/cloud outages.** NODD data depends on AWS availability. A cloud outage during the competition could cut off geostationary data feeds.

### Pre-Competition Preparation Failures

- **Stale TLEs.** If you pre-compute overpass schedules using TLEs from weeks before the competition, predictions may be off by minutes. Refresh TLEs the day before.
- **API key expiration/rate limiting.** FIRMS MAP_KEYs and Copernicus tokens can expire. Test all authentication before the competition.
- **Untested data pipelines.** A data source that works in testing may fail under competition conditions (different time of year, different fire behavior, different data volumes).

---

## 6. Licensing and Legal Constraints Summary

| Data Source | License | Restriction |
|---|---|---|
| NOAA (GOES, JPSS, Himawari NODD) | Open use | Attribution requested; no endorsement implied |
| Copernicus (Sentinel-1/2/3/5P) | Open access | Copernicus terms and conditions |
| USGS Landsat | Public domain | None |
| NASA Earthdata / FIRMS | Open access | MAP_KEY rate limits |
| JAXA P-Tree (Himawari) | Free registration | Commercial use from Feb 2026 |
| EUMETSAT (MetOp, Meteosat) | Conditional free | <1h timeliness requires fee |
| NSMC Fengyun (FY-3, FY-4) | Free registration | WMO data policy |
| OroraTech | Commercial | Paid service |
| FireSat | TBD | Early adopter program |
| SatVu | Commercial | Paid service |
| Planet | Commercial EULA | Not public domain |
| WorldView-3 | Commercial | Very expensive |
