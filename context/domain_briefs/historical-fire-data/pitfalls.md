# Pitfalls: Data Quality Issues, Known Gaps, and Australian-Specific Gotchas

## 1. FIRMS Active Fire Detection Issues

### False Positives

**Sun glint contamination:**
- Daytime low-confidence VIIRS pixels are frequently caused by solar reflection off bright/reflective surfaces (metallic roofs, solar panels, water bodies)
- The algorithms use slightly more conservative tests near sun glint zones, but false alarms persist
- Mitigation: filter to nominal/high confidence for training data; low-confidence daytime pixels should not be treated as fire

**Industrial heat sources:**
- Steel mills, power plants, refineries, gas flares produce persistent thermal anomalies
- MODIS `type` field flags these: type=2 (static land source), type=3 (offshore)
- VIIRS does not have a `type` field -- you must filter these manually using known industrial site locations
- For NSW: check against known power stations (e.g., Liddell, Eraring, Mt Piper)

**Volcanic/geothermal:**
- Less relevant for NSW but important if training on global data
- MODIS type=1 flags volcanic sources

**South Atlantic Magnetic Anomaly:**
- Causes spurious VIIRS detections from radiation hitting the sensor
- Flagged as low-confidence, but ~2-3 pixels per night slip through as nominal confidence
- Not a concern for Australia (affects South America/Atlantic primarily)

### False Negatives

**Understory/ground fires:**
- Fires burning beneath forest canopy may not produce enough thermal signal for satellite detection
- Common in peat/swamp fires and low-intensity prescribed burns
- VIIRS 375m is better than MODIS 1km at detecting small/low-intensity fires

**Cloud cover:**
- Satellites cannot detect fires under clouds
- During fire weather events, pyrocumulonimbus clouds from large fires can obscure adjacent fires
- Cross-reference with multiple satellites and overpasses to mitigate

**Temporal gaps:**
- Polar-orbiting satellites pass over a given location only ~4 times per day (2 daytime, 2 nighttime for VIIRS with SNPP + NOAA-20)
- A fire can ignite, spread, and die between overpasses without ever being detected
- This is a fundamental limitation of using FIRMS for ignition detection training

**Edge-of-swath degradation:**
- Pixel size grows significantly at scan edges: VIIRS 375m at nadir becomes ~800m at edge
- MODIS 1km at nadir becomes ~2km x ~5km at extreme scan angles
- `scan` and `track` fields report actual pixel dimensions -- use these to assess detection quality

### Undocumented Algorithmic Issues

**Nighttime low-confidence gap:**
- Recent research (2025) identified that VIIRS has zero low-confidence fire detections at night across 21.5M detections analyzed over one year
- This is undocumented algorithmic filtering, not a physical phenomenon
- Affects 27.9% of all VIIRS fire detections
- Implication: nighttime fire detection statistics are artificially skewed toward higher confidence

### NRT vs Standard Processing

- Near Real-Time (NRT) data is available within hours but has lower positional accuracy
- Standard Processing (SP) data replaces NRT after ~5 months with improved geolocation
- If building historical training sets, always use SP data
- For recent events, NRT is all that is available -- flag these samples as lower quality

## 2. MCD64A1 Burned Area Limitations

### Temporal Resolution

- Monthly product: a fire that burns January 15 is recorded as "January burn" but the exact date within the month has uncertainty
- `BurnDate` provides approximate Julian day but `Uncertainty` can be +/- 8 days
- For training data that needs precise temporal matching, use FIRMS active fire points instead

### Omission in Low-Intensity Burns

- Algorithm relies on surface reflectance change, which may be subtle for low-severity burns
- Grassland fires that green up quickly (weeks) may be missed if the monthly composite catches the regrowth
- Prescribed burns with low severity are systematically undercounted

### Commission in Agricultural Areas

- Crop harvesting and stubble burning can be falsely identified as wildfire burned area
- Less relevant for NSW forest fires but important for western NSW agricultural zones
- Cross-reference with land cover data to exclude cropland pixels

### Spatial Resolution

- 500m pixels miss fires smaller than ~25 hectares
- Fine-scale fire patterns (fire breaks, unburned islands within fire perimeters) are not resolved
- For high-resolution ground truth, use FESM (10m) or Sentinel-2 derived dNBR (20m)

## 3. GFED Limitations

### Coarse Resolution

- 0.25 deg (~25 km) resolution is too coarse for pixel-level fire detection training
- Useful only for regional statistics, fire season characterization, and emissions modeling
- Pre-2001 data (1997-2000) drops to 1.0 deg resolution

### Smoothing and Aggregation

- Monthly aggregation masks day-to-day fire dynamics
- Burned area fractions are averaged over large grid cells, losing spatial detail
- Cannot distinguish individual fire events within a grid cell

## 4. Australian-Specific Data Gotchas

### Coordinate Systems

- NPWS Fire History shapefiles use GDA94 (EPSG:4283) or GDA2020 (EPSG:7844), not WGS84
- The difference between GDA94 and WGS84 is small (~1m) but GDA2020 differs more
- Always reproject to a common CRS before matching with satellite data
- FIRMS data is in WGS84

### SEED Portal Quirks

- Downloads may require accepting license terms each time
- Large shapefiles can timeout on download; use direct download links
- Some datasets have incomplete metadata about update frequency
- FESM rasters are delivered as zip files containing both .tif and .img formats

### Fire Type Ambiguity

- NSW records distinguish "wildfire" from "prescribed burn" but the boundary is sometimes unclear
- Some prescribed burns that escape control become wildfires
- Some wildfires are reclassified as "managed" fires
- For ML training: decide whether prescribed burns are positive or negative samples based on detection goals

### Time Zone Issues

- FIRMS `acq_time` is UTC; Australian Eastern Standard Time is UTC+10 (UTC+11 during daylight saving)
- A fire detected at UTC 03:00 corresponds to 13:00-14:00 AEST (early afternoon)
- Critical when matching to Bureau of Meteorology weather observations (reported in local time)
- NSW observes daylight saving (first Sunday in October to first Sunday in April)

### Black Summer Data Saturation

- The 2019-2020 fire season was so extreme that it risks dominating any Australian fire training dataset
- Models trained primarily on Black Summer data may not generalize to "normal" fire seasons
- Fire behavior during Black Summer included unprecedented spotting distances (>30 km), deep flaming zones, and pyroconvective events that are not typical
- Deliberately include data from 2012-2018 (more typical fire seasons) in training

### Prescribed Burn Seasonality

- Most prescribed burns in NSW occur March-May (autumn) and occasionally in winter
- This creates a bimodal fire signal: summer wildfires (high intensity) and autumn prescribed burns (low intensity)
- The competition is in April -- the prescribed burn season may produce confounding thermal signatures

## 5. Satellite-Specific Temporal Biases

### MODIS/VIIRS Overpass Times

| Satellite | Ascending (daytime) | Descending (nighttime) |
|-----------|-------------------|----------------------|
| Terra (MODIS) | ~10:30 local | ~22:30 local |
| Aqua (MODIS) | ~13:30 local | ~01:30 local |
| VIIRS S-NPP | ~13:30 local | ~01:30 local |
| VIIRS NOAA-20 | ~13:30 local | ~01:30 local |
| VIIRS NOAA-21 | ~13:30 local | ~01:30 local |

- Fires peak in intensity 14:00-18:00 local, after the afternoon overpass
- The 13:30 overpass catches fires early in their daily peak
- No polar-orbiting satellite captures the late-afternoon fire maximum
- Geostationary satellites (Himawari-8/9) fill this gap but at lower spatial resolution (~2 km)

### Sentinel-2 Revisit Gaps

- 5-day revisit (with two Sentinel-2 satellites) means fires can burn unobserved for days
- Cloud cover further reduces usable image frequency
- In temperate NSW, winter months have more cloud cover, reducing Sentinel-2 availability
- For training data: ensure sufficient cloud-free imagery exists before including a fire event

## 6. Cross-Dataset Consistency Issues

### Spatial Alignment

- Different products use different grids: MODIS sinusoidal, WGS84 lat/lon, local projections
- Reprojection introduces interpolation artifacts, especially for coarse data
- When combining FIRMS (points in WGS84) with MCD64A1 (MODIS sinusoidal tiles), reproject to a common grid

### Temporal Definitions

- "Daily" fire data from FIRMS corresponds to satellite overpass times, not calendar days
- MCD64A1 "monthly" composites can use observations from adjacent months for gap-filling
- GFED "monthly" burned area may include fires from the previous month if detection was delayed

### Confidence and Quality Flags

- MODIS confidence is 0-100% (continuous)
- VIIRS confidence is categorical (low/nominal/high) with no numeric equivalent
- MCD64A1 has a complex QA bitmask
- These different schemes make cross-sensor analysis tricky; normalize to a common quality scale

## 7. Computational Pitfalls

### GEE Quota and Timeout

- GEE has computation time limits: complex operations over large areas will timeout
- Export to Drive/Cloud Storage for large-scale processing
- Break NSW into smaller tiles for batch processing
- Use `.limit()` when testing on FeatureCollections to avoid memory errors

### FIRMS API Rate Limiting

- 5,000 transactions per 10 minutes
- A single large request may consume multiple transactions
- For bulk historical downloads, use the archive download tool instead of the API
- Implement exponential backoff for rate limit errors

### File Sizes

- Full FIRMS CSV for Australia for one year: ~50-200 MB depending on fire season severity
- MCD64A1 for all NSW tiles for one year: ~2-5 GB (HDF format)
- FESM 2019/20 statewide raster: several GB at 10m resolution
- ERA5 hourly data for one year over NSW: ~10-50 GB
- Plan storage and processing accordingly

## 8. Legal and Licensing

### Open Data
- FIRMS: Free, no restrictions on use
- MCD64A1: Free, no restrictions on use, sale, or redistribution
- GFED: Free for research
- ERA5: Free via Copernicus license (check terms for commercial use)
- GEE: Free for research; commercial use requires Google Cloud licensing

### Restricted or Licensed Data
- SEED NSW datasets: Available under license; check metadata for attribution requirements
- BOM data: Some products free (FTP); commercial-grade data requires payment
- RFS operational data (ICON, BRIMS): Not publicly available in raw form

### Attribution Requirements
- NASA data: Cite the relevant data product DOI
- Copernicus data: Attribution to C3S/CEMS required
- NSW government data: Attribution per Creative Commons license terms
