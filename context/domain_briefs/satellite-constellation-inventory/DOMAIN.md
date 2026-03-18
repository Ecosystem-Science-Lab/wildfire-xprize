# Satellite Constellation Overview for NSW Wildfire Detection

## Coverage Summary

NSW Australia (-28 to -37S, 148-154E) is observed by a remarkably dense constellation of fire-capable satellites, anchored by geostationary continuous monitoring and supplemented by a fleet of polar-orbiting sensors.

### Geostationary Coverage (Continuous, 24/7)

Three geostationary satellites provide continuous fire monitoring over NSW:

1. **Himawari-9** (140.7E) -- PRIMARY. 10-minute full-disk cadence. 2 km nadir resolution (3-4 km effective at NSW latitudes due to ~35-43 deg view zenith angle). FIRMS integration. AWS NODD mirror. This is the single most important sensor for continuous fire detection over NSW.

2. **GEO-KOMPSAT-2A / GK-2A** (128.2E) -- SECONDARY. 10-minute cadence. 2 km IR channels. Data freely available on AWS NODD. Slightly worse view geometry than Himawari for NSW but provides valuable redundancy and independent detection.

3. **FY-4B** (123.5E) -- SUPPLEMENTARY. 15-minute cadence. 2-4 km thermal channels (improved from FY-4A). Fire/Hotspot product available. Free data via NSMC. Further west than GK-2A, slightly worse geometry for NSW.

**FY-4A** (104.7E) provides marginal coverage at extreme view angles. INSAT, Meteosat (IODC), GOES-West, and EWS-G2 do NOT usefully cover NSW.

### Coverage Gap Analysis

There is NO significant geostationary gap over NSW. Himawari-9 provides primary coverage with excellent geometry, and GK-2A and FY-4B provide redundancy. The 10-minute cadence from Himawari is the temporal bottleneck for geostationary fire detection.

At NSW latitudes (35-43 deg view zenith angle from Himawari), effective pixel size is ~3-4 km for thermal channels. This means minimum detectable fire size from geostationary orbit over NSW is roughly 1,000-4,000 m2 under favorable conditions (clear sky, low background, nighttime preferred).

### Polar-Orbiting Coverage (High-Resolution, Periodic)

The LEO constellation provides approximately **20-30 useful overpasses per day** across all thermal-capable satellites:

**Tier 1 -- Operational fire products, well-characterized latency:**
- **VIIRS** (S-NPP + NOAA-20 + NOAA-21): ~6 passes/day combined. 375m resolution. Best-in-class active fire product. Data via FIRMS, AWS NODD, direct broadcast.
- **MODIS** (Terra + Aqua): ~4 passes/day combined. 1 km. Degrading orbits but still operational through April 2026.
- **Sentinel-3 SLSTR** (3A + 3B): ~2 passes/day. 1 km. FRP product (preliminary operational).
- **MetOp AVHRR** (B + C): ~4 passes/day. 1.1 km. No dedicated fire product but algorithms exist.

**Tier 2 -- Operational but with data access challenges:**
- **FY-3D/3E/3F MERSI**: ~6 passes/day combined. 250m thermal -- best spatial resolution of any operational polar-orbiting thermal fire sensor. Validated fire product. Data access from NSMC may have latency/reliability concerns for real-time operations.
- **Meteor-M N2-3/N2-4 MSU-MR**: ~4 passes/day. 1 km. Very limited international data access.

**Tier 3 -- Sparse revisit but very high resolution:**
- **Landsat 8 + 9**: ~8-day revisit per location. 100m thermal, 30m SWIR. Can detect fires of a few square meters. Essential for confirmation/detail when overpass aligns.
- **ECOSTRESS** (ISS): Variable 1-5 day revisit. 69x38m thermal. Irregular overpass times (non-sun-synchronous). No fire product.
- **Sentinel-2B + 2C**: ~5-day revisit. 20m SWIR. No thermal band. Fire detection via SWIR saturation.

**Tier 4 -- Supplementary:**
- **Sentinel-5P TROPOMI**: Daily. Smoke/aerosol tracking via UV Aerosol Index and CO.
- **OMPS**: Daily. Coarse aerosol index for large smoke plumes.
- **Sentinel-1A + 1C**: 2-4 day revisit. Burn scar mapping via SAR. Not real-time fire detection.

### Commercial/CubeSat Constellation

- **OroraTech**: Operational since Apr 2025. Growing constellation (~16+ satellites by April 2026). MWIR+LWIR thermal. <10 min alert latency. Commercial service (pricing unclear).
- **FireSat (Muon/EFA)**: Protoflight launched Jun 2025. Phase 1 (3 sats) planned mid-2026 -- likely NOT operational by April 2026. 80m resolution, 6-band IR, fire-optimized.
- **SatVu HotSat**: HotSat-2/3 planned 2025-2026. 3.5m thermal. Tasked imaging. Not continuous monitoring.

### Estimated Daily Observation Budget for NSW (April 2026)

| Source | Passes/day | Resolution | Detection type |
|---|---|---|---|
| Himawari-9 | 144 frames/day | 3-4 km | Continuous thermal |
| GK-2A | 144 frames/day | 3-5 km | Continuous thermal |
| FY-4B | 96 frames/day | 3-5 km | Continuous thermal |
| VIIRS (3 sats) | ~6 passes | 375 m | Thermal fire product |
| MODIS (2 sats) | ~4 passes | 1 km | Thermal fire product |
| SLSTR (2 sats) | ~2 passes | 1 km | Thermal FRP |
| AVHRR (2 sats) | ~4 passes | 1.1 km | Thermal (custom alg) |
| MERSI (3 sats) | ~6 passes | 250 m | Thermal fire product |
| MSU-MR (2 sats) | ~4 passes | 1 km | Thermal (limited) |
| Landsat (2 sats) | 0.25/day avg | 100 m | Thermal + SWIR |
| Sentinel-2 (2 sats) | 0.4/day avg | 20 m SWIR | SWIR only |
| OroraTech | Variable | ~200-500 m | Thermal alerts |

### Key Operational Realities

1. **Himawari-9 is the anchor.** 10-minute cadence, FIRMS integration, AWS NODD access make it the fastest path to continuous fire alerting over NSW. Processing raw L1b AHI data enables detection within minutes of observation.

2. **VIIRS is the workhorse for confirmation.** 375m resolution, validated fire products, and ~6 passes/day give the best balance of revisit and sensitivity. Direct broadcast via Australian ground stations (Alice Springs, Townsville) provides fastest data access (~5-15 min after overpass).

3. **FY-3D MERSI-II has the best spatial resolution** of any operational polar-orbiting thermal fire sensor (250m), but data access reliability from NSMC is a concern for real-time operations.

4. **Landsat provides the smallest fire detection** capability (few m2) but only at 8-day intervals. Must be treated as opportunistic confirmation.

5. **Data access is the real bottleneck**, not sensor availability. The difference between 5-minute and 3-hour latency for the same VIIRS overpass depends entirely on whether you use direct broadcast or wait for FIRMS NRT processing.

6. **Satellites near end-of-life in April 2026**: Terra MODIS (orbit degrading, science ends Feb 2027), Aqua MODIS (passivation Nov 2026), S-NPP (EOL Dec 2028 -- still fine). ASTER TIR is already permanently off.

7. **Digital Earth Australia Hotspots** (hotspots.dea.ga.gov.au) is Geoscience Australia's national bushfire monitoring system. It ingests Himawari, VIIRS, MODIS, and AVHRR data, updates every 10 minutes, provides WMS/WFS services, and requires no registration. This is a valuable secondary data source and validation reference specific to Australia.

### Strategic Recommendations for the Competition

1. **Primary detection path:** Himawari-9 raw L1b data (via AWS NODD or JAXA P-Tree) with self-implemented fire detection algorithm. Target: detection within 2-5 minutes of observation for fires >1,000 m2.

2. **LEO confirmation path:** VIIRS active fire products via FIRMS or direct broadcast. Schedule processing around predicted overpasses. Target: confirmation/refinement within 15 minutes of overpass for fires >100 m2.

3. **High-resolution opportunistic path:** Landsat TIRS + OLI when overpass aligns. Pre-compute exact Landsat pass dates for the competition area. Target: detection of fires as small as a few m2 at overpass time.

4. **Pre-competition setup:** Register for all APIs (FIRMS MAP_KEY, JAXA P-Tree, Copernicus, NASA Earthdata). Test all data pipelines end-to-end. Compute and cache overpass schedules. Set up AWS infrastructure co-located with NODD buckets (us-east-1).

5. **Redundancy:** Use DEA Hotspots and GK-2A as independent cross-checks. Do not depend on any single data source.

### Satellite Count Summary

- **Geostationary with NSW coverage:** 3 operational (Himawari-9, GK-2A, FY-4B), plus 2 marginal/backup (Himawari-8, FY-4A)
- **LEO thermal fire-capable:** ~18 satellite platforms (VIIRS x3, MODIS x2, SLSTR x2, AVHRR x2, MERSI x3, MSU-MR x2, Landsat x2, ECOSTRESS x1, OroraTech fleet)
- **LEO SWIR fire-capable:** 4 platforms (Sentinel-2B, 2C, Landsat 8, 9)
- **Smoke/aerosol:** 2 platforms (Sentinel-5P TROPOMI, S-NPP/NOAA-20 OMPS)
- **SAR (burn area):** 3 platforms (Sentinel-1A, 1C, ALOS-2)
- **Total unique platforms with fire-relevant capability covering NSW: 30+**
