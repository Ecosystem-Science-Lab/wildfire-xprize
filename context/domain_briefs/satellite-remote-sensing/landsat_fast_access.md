# Landsat 8/9 Fast Access for Fire Detection in Australia (NSW)

Research date: 2026-03-17

## Executive Summary

**Landsat cannot realistically contribute to "1-minute-from-overpass" scoring in Australia.** The fastest existing operational pipeline (FIRMS LFTA) achieves 30-60 minutes but is restricted to North America. For Australian scenes, the standard USGS pipeline delivers data in 4-6 hours. However, a research-grade direct-reception approach (FarEarth Observer / Pinkmatter) has demonstrated <10-second latency from sensor line acquisition to fire detection -- this would require deployment at the Alice Springs ground station with cooperation from Geoscience Australia.

**Bottom line for competition scoring:** Landsat offers ~30m fire detection resolution (vastly superior to VIIRS/MODIS) but only ~8-day revisit. If a Landsat overpass happens to coincide with a competition fire, the detection resolution is excellent but the fastest realistic access pathway for Australia is 4-6 hours (USGS RT tier) or ~48 hours (DEA NRT ARD). Direct-reception fire detection (<10 seconds) is technically proven but would require a custom deployment at Alice Springs.

---

## 1. WRS-2 Path/Row Tiles Covering NSW

### Approximate Coverage

NSW spans roughly -28 to -37°S latitude, 148-154°E longitude. The WRS-2 system has 233 paths, each ~1.545° apart at the equator (360°/233). Paths are numbered east to west.

Known reference point: **(-34.6°S, 146.5°E) = Path 92, Row 84** (from LatLongToWRS Python tool).

The approximate WRS-2 tiles covering the NSW competition area:

| Path | Approximate Center Longitude | Coverage |
|------|------------------------------|----------|
| 89   | ~151.1°E                     | Sydney, central coast, Blue Mountains |
| 90   | ~149.6°E                     | Canberra, southern highlands |
| 91   | ~148.0°E                     | Western slopes, Snowy Mountains |
| 92   | ~146.5°E                     | Western NSW (Wagga, Griffith) |

Row numbers for NSW latitudes:
- **Row 82**: ~-28 to -30°S (northern NSW)
- **Row 83**: ~-30 to -32°S (Hunter Valley, central NSW)
- **Row 84**: ~-32 to -34°S (Sydney, Blue Mountains, southern tablelands)
- **Row 85**: ~-34 to -36°S (south coast, ACT region)

**Total: roughly 12-16 path/row tiles cover the NSW competition area.**

### Tools for Precise Lookup
- **USGS Landsat Acquisition Tool**: https://landsat.usgs.gov/landsat_acq (has coordinate-to-path/row converter)
- **LatLongToWRS Python**: https://github.com/robintw/LatLongToWRS
- **DEA SatPaths API**: https://satpathapi.dea.ga.gov.au/user-guide (Landsat 8 NORAD ID: 39084, Landsat 9: 49260)

---

## 2. Overpass Timing for NSW

### Equator Crossing Time
- Both Landsat 8 and 9: **10:12 AM local solar time** (+/- 5 minutes), descending node (north to south).

### NSW Overpass Time
- Real observed data: **Landsat 8 over NSW site at -31.5°S, 147.0°E was at 00:01:33 UTC** (2025-06-21), which is **10:01 AM AEST**.
- For mid-April 2026, NSW is on **AEDT (UTC+11)** until first Sunday in April, then **AEST (UTC+10)**.
- Mid-April overpasses will be approximately **~23:50-00:10 UTC**, which is **~9:50-10:10 AM AEST**.

### Combined Revisit
- Landsat 8 alone: 16-day repeat cycle
- Landsat 9 alone: 16-day repeat cycle, offset by 8 days from L8
- **Combined L8+L9: ~8-day revisit** at mid-latitudes

### Predicting April 2026 Overpass Dates

The USGS Landsat Acquisition Tool (https://landsat.usgs.gov/landsat_acq) shows scheduled paths for any date. To predict:
1. Find a known acquisition date for the target path
2. Add multiples of 16 days for the same satellite
3. The other satellite passes 8 days offset

For a 16-day competition window (mid-April 2026), any given NSW location will get:
- **1-2 Landsat 8 overpasses**
- **1-2 Landsat 9 overpasses**
- **Total: 2-4 overpasses** over the competition area

**The spectator.earth tool** (https://spectator.earth/satellite-acquisition-plan-viewer/) and **DEA SatPaths API** can also predict overpasses. Note: SatPaths predictions >10 days out are "indicative only" due to TLE accuracy limitations.

---

## 3. Daytime Fire Detection Considerations

Landsat overpasses occur at ~10 AM local time (daytime only for descending/imaging passes).

### Daytime Challenges
- **Solar reflection in SWIR**: The detected radiance is a mixture of reflected solar radiation and emitted thermal radiation. At 10 AM, the solar component can mask weak fire signals.
- **Higher background temperatures**: Urban surfaces and bare soil are warmer during daytime, increasing false alarm rates.
- **SWIR band saturation**: OLI Band 7 (2.1-2.3 μm SWIR) can saturate at 30m resolution over high-reflectance surfaces.

### Mitigations
- **NIR subtraction**: Band 5 (NIR) is mostly unresponsive to fire but correlates with SWIR over fire-free surfaces -- used to separate emissive vs. reflected components.
- **TIRS thermal bands**: Bands 10-11 (10.6-12.5 μm) at 100m native resolution (resampled to 30m) provide thermal anomaly detection independent of solar reflection.
- **Multi-band algorithm**: The LFTA algorithm uses a combination of SWIR and thermal bands to detect fires as small as a few square meters.

### Bottom Line
Daytime detection is harder than nighttime but the LFTA algorithm routinely detects fires during daytime overpasses. The 30m resolution of Landsat means even small fires produce strong per-pixel signals.

---

## 4. Data Access Pathways (Ranked by Speed)

### Path A: Direct Reception + Real-Time Processing (~10 seconds)

**FarEarth Observer (Pinkmatter Solutions)**
- Connects to ground station demodulator, processes live X-band data stream
- **Latency: <10 seconds** from sensor line acquisition to fire anomaly detection
- Processes variable-size image segments during satellite pass, before acquisition completes
- Throughput exceeds Landsat 8's 400 Mbit/s downlink speed
- Agencies in "Europe, North-America, Asia, Africa and Australia" use FarEarth software
- **Status**: Research/commercial product; NOT currently deployed for operational Australian fire detection
- **Requirement**: Would need deployment at Alice Springs DAF with GA cooperation

**USGS EarthNow! / FarEarth Global Observer**
- Live view of Landsat data during downlink at USGS ground stations including Alice Springs
- https://earthnow.usgs.gov/observer/ and https://live.farearth.com/observer/
- Provides visualization but not operational fire product output

### Path B: FIRMS LFTA NRT Product (30-60 minutes) -- NOT AVAILABLE FOR AUSTRALIA

**NASA LANCE FIRMS Landsat Fire and Thermal Anomaly (LFTA)**
- **Latency: 30-60 minutes** from satellite overpass to fire detection availability
- 30m resolution active fire detections
- **Coverage: North America ONLY** (CONUS, southern Canada, northern Mexico)
- Limited by direct readout at USGS EROS Ground Station, Sioux Falls, SD
- Expansion to other ground stations (including Alice Springs) is "being investigated" but no timeline
- https://www.earthdata.nasa.gov/news/feature-articles/landsat-fire-thermal-anomaly-data-added-firms

### Path C: USGS Level-1 RT (Real-Time) Tier (4-6 hours)

**Standard USGS Processing Pipeline**
- All Landsat 8/9 data globally is processed through EROS (Sioux Falls, SD)
- **Data flow**: Satellite → Alice Springs X-band downlink → Transfer to EROS (via internet/fibre) → Processing → Available for download
- **Latency: 4-6 hours** after acquisition
- Available as Level-1 product with predicted ephemeris (lower geometric accuracy)
- RT scenes are reprocessed into Tier 1/Tier 2 after 14-26 days
- **Global coverage** -- this applies to Australian scenes
- https://www.usgs.gov/landsat-missions/landsat-collection-2-level-1-data

### Path D: AWS S3 / Cloud Access (4-6+ hours)

**Landsat Collection 2 on AWS**
- Bucket: `s3://usgs-landsat/collection02/` (Requester Pays, us-west-2)
- SNS notification on new scene: `arn:aws:sns:us-west-2:673253540267:public-c2-notify-v2`
- **Latency: "within hours of production"** -- i.e., after USGS processing, so 4-6+ hours total
- ~680 new scenes added daily
- Cloud-Optimized GeoTIFF format
- Can subscribe to SNS for automated triggers
- https://registry.opendata.aws/usgs-landsat/

### Path E: Google Earth Engine (4-6+ hours)

**Landsat 8/9 Collection 2 T1+RT**
- RT tier data ingested "upon downlink" but actual latency mirrors USGS processing
- Global coverage including Australia
- Dataset: `LANDSAT/LC08/C02/T1_RT` and `LANDSAT/LC09/C02/T1_RT`
- No built-in automated trigger for new scene arrival (would need to poll)
- https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_RT

### Path F: Digital Earth Australia NRT ARD (~48 hours)

**Geoscience Australia DEA Pipeline**
- Alice Springs DAF → fibre optic → DPF Canberra → ARD processing
- **NRT maturity level: ~48 hours** after image capture
- Uses climatological ancillary data (lower quality than final ARD)
- Final ARD produced after 23+ days when definitive ancillaries available
- Not designed for rapid fire detection; designed for scientific analysis
- https://knowledge.dea.ga.gov.au/data/product/dea-surface-reflectance-landsat-9-oli-tirs/

---

## 5. Ground Station Infrastructure in Australia

### Alice Springs Data Acquisition Facility (ASA)

- **Operator**: Geoscience Australia
- **Coordinates**: -23.7589°S, 133.8822°E
- **Equipment**: Two 9m antennas, one 3m antenna, one 2.4m antenna
- **Role**: One of 5 USGS Landsat Ground Network stations (with Sioux Falls, Gilmore Creek AK, Neustrelitz Germany, Svalbard Norway)
- **Coverage**: Entire Australian continent, most of Papua New Guinea, eastern Indonesia
- **Data flow**:
  1. X-band science data downlinked during satellite pass
  2. Transferred to GA Data Processing Facility in Canberra via fibre optic
  3. Also transferred to USGS EROS (Sioux Falls) as Mission Data for DPAS processing
- **History**: Operating since 1979 (40+ years)
- **Key fact**: Australia has committed $200M to modernize facilities

### Sentinel/DEA Hotspots System

- GA operates DEA Hotspots (formerly Sentinel) -- a national bushfire monitoring system
- Uses **MODIS, VIIRS, and Himawari-9 AHI** (NOT Landsat)
- Updated every 10 minutes (from Himawari geostationary data)
- Minimum 17-minute latency from satellite pass to hotspot availability
- https://hotspots.dea.ga.gov.au/
- Plans to incorporate "near-real-time feeds of DEA ARD products from Landsat 8 and 9" but this appears to be at the ~48-hour DEA NRT latency, not minutes

---

## 6. Realistic Assessment for Competition

### Can Landsat contribute to 1-minute-from-overpass scoring?

**No, not through any existing operational pipeline.** The fastest operational product (FIRMS LFTA, 30-60 min) does not cover Australia. The fastest available pathway for Australian Landsat data is the USGS RT tier at 4-6 hours.

### Theoretical fast path (requires custom work)

The FarEarth Observer technology has demonstrated <10-second latency from sensor acquisition to fire detection. If deployed at Alice Springs with GA cooperation, this could theoretically deliver fire detections within seconds of the satellite passing over the competition area. This would require:
1. Access to the Alice Springs X-band demodulator output
2. Deployment of FarEarth Observer or equivalent real-time processing software
3. Integration of a fire detection algorithm (similar to LFTA)
4. Agreement with Geoscience Australia

### Strategic value even at 4-6 hour latency

Even at 4-6 hours, Landsat provides:
- **30m resolution** fire detection (vs 375m VIIRS, 1km MODIS, 2km Himawari)
- Confirmation and precise geolocation of fires detected by other sensors
- Detailed fire perimeter mapping

### Overpass probability during competition

For a ~2-week competition window in mid-April 2026:
- Any given location: 2-4 combined L8/L9 overpasses
- Across the full NSW competition area: potentially 1 overpass every 1-2 days on different paths
- **Timing is fixed at ~10 AM AEST** -- fires would need to be burning at that time

---

## 7. Key References

- USGS Landsat Ground Stations: https://www.usgs.gov/landsat-missions/usgs-landsat-ground-stations
- Alice Springs Station: https://landsat.usgs.gov/ASA
- USGS Landsat Collection 2 Level-1: https://www.usgs.gov/landsat-missions/landsat-collection-2-level-1-data
- FIRMS Landsat LFTA: https://www.earthdata.nasa.gov/news/feature-articles/landsat-fire-thermal-anomaly-data-added-firms
- FIRMS LFTA Blog: https://www.earthdata.nasa.gov/news/blog/new-near-real-time-product-firms-landsat-active-fire-data
- FarEarth Observer (real-time processing): Böhme et al. 2015, ISPRS Archives https://isprs-archives.copernicus.org/articles/XL-7-W3/765/2015/
- Landsat on AWS: https://registry.opendata.aws/usgs-landsat/
- DEA SatPaths API: https://satpathapi.dea.ga.gov.au/user-guide
- DEA Hotspots: https://hotspots.dea.ga.gov.au/
- DEA Surface Reflectance (Landsat 9): https://knowledge.dea.ga.gov.au/data/product/dea-surface-reflectance-landsat-9-oli-tirs/
- Landsat Acquisition Tool: https://landsat.usgs.gov/landsat_acq
- Spectator.earth Overpass Viewer: https://spectator.earth/satellite-acquisition-plan-viewer/
- GA Ground Station Network: https://www.ga.gov.au/scientific-topics/space/our-satellite-and-ground-station-network
- GEE Landsat 8 RT: https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_RT
- 40 Years of Landsat at Alice Springs: https://www.usgs.gov/landsat-missions/november-15-2019-celebrating-40-years-landsat-alice-springs-ground-station

---

## 8. Latency Summary Table

| Pathway | Latency | Coverage | Resolution | Status |
|---------|---------|----------|------------|--------|
| FarEarth Observer (direct reception) | <10 seconds | Requires ground station | 30m | Research/commercial; not deployed for AU fire ops |
| FIRMS LFTA | 30-60 minutes | North America ONLY | 30m | Operational; no AU coverage |
| USGS Level-1 RT | 4-6 hours | Global | 30m | Operational |
| AWS S3 (post-USGS processing) | 4-6+ hours | Global | 30m | Operational |
| Google Earth Engine RT | 4-6+ hours | Global | 30m | Operational |
| DEA NRT ARD | ~48 hours | Australia | 30m | Operational |
| DEA Final ARD | 23+ days | Australia | 30m | Operational |
