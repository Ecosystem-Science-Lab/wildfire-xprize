# Sensor & Data Access Strategy

## 1. Sensor Ranking by Scoring Value

The competition scores detection within 1 minute of satellite overpass and characterization within 10 minutes. Each overpass that catches a fire is a scoring opportunity. The sensors are ranked by the product of (scoring opportunities per day) x (detection sensitivity) x (achievable data latency).

### Rank 1: Himawari-9 AHI (Geostationary -- PRIMARY)
- **Scoring opportunities**: 144 per day (every 10 minutes, 24/7)
- **Sensitivity**: ~1,000-4,000 m2 minimum at NSW latitudes (3-4 km effective pixels)
- **Realistic latency**: 7-15 minutes from observation to data availability (JAXA P-Tree: 5-20 min; AWS NODD: similar)
- **1-minute scoring feasibility**: NO for the 1-minute-from-overpass metric, but YES for the ongoing 15-minute characterization updates. Himawari's primary value is continuous monitoring and rapid characterization updates, not 1-minute detection scoring.
- **Strategic role**: Continuous fire monitoring, trigger layer, characterization updates every 10 minutes

### Rank 2: VIIRS (S-NPP + NOAA-20 + NOAA-21 -- WORKHORSE)
- **Scoring opportunities**: ~6 per day (3 day + 3 night passes)
- **Sensitivity**: ~100-500 m2 minimum (375 m pixels)
- **Realistic latency**:
  - Direct broadcast via Australian ground stations: 5-15 min after overpass
  - DEA Hotspots (GA): ~17 min minimum after overpass
  - FIRMS NRT (global): up to 3 hours (NOT suitable for 1-minute scoring)
- **1-minute scoring feasibility**: YES if we can get data within ~30 seconds of ground station reception and run our detection in <30 seconds. Requires partnership with GA/BoM for direct broadcast data.
- **Strategic role**: Highest-value scoring opportunities if we can achieve fast data access. Each of the 6 daily passes is a distinct scoring opportunity.

### Rank 3: Landsat 8/9 OLI+TIRS (HIGH-RESOLUTION -- OPPORTUNISTIC)
- **Scoring opportunities**: 2-4 during the entire 2-week competition (8-day combined revisit)
- **Sensitivity**: ~4 m2 (30 m SWIR, 100 m thermal) -- by far the best
- **Realistic latency**: 4-6 hours via USGS RT tier (standard path); <10 seconds theoretically via FarEarth Observer at Alice Springs (requires partnership)
- **1-minute scoring feasibility**: NO via standard pipeline. THEORETICALLY YES via FarEarth/Alice Springs partnership, but this is the highest-risk, highest-reward option.
- **Strategic role**: If a Landsat overpass coincides with a competition fire, the 30 m resolution gives us detection of fires orders of magnitude smaller than any other sensor. Extremely high scoring value per event, but extremely few events.

### Rank 4: GK-2A AMI (Geostationary -- REDUNDANCY)
- **Scoring opportunities**: 144 per day (same as Himawari)
- **Sensitivity**: Similar to Himawari but slightly worse geometry for NSW (128.2E vs 140.7E)
- **Realistic latency**: AWS NODD mirror available, no SNS push notifications documented
- **1-minute scoring feasibility**: Same constraints as Himawari
- **Strategic role**: Independent cross-check against Himawari. Detections from GK-2A that confirm Himawari detections significantly boost confidence. Detections from GK-2A when Himawari has gaps (maintenance, cloud) provide continuity.

### Rank 5: MODIS (Terra + Aqua -- SUPPLEMENTARY)
- **Scoring opportunities**: ~4 per day (2 satellites x 2 passes, but Aqua overlaps VIIRS timing)
- **Sensitivity**: ~1,000 m2 (1 km pixels)
- **Realistic latency**: Similar to VIIRS (same ground stations). FIRMS NRT: up to 3 hours.
- **Strategic role**: Supplementary confirmation. Terra's drifting orbit (now ~08:30 crossing) provides morning coverage when VIIRS is absent.

### Rank 6: Sentinel-3 SLSTR (SUPPLEMENTARY)
- **Scoring opportunities**: ~2-4 per day
- **Sensitivity**: Similar to MODIS (~1 km)
- **Realistic latency**: ~3 hours via Copernicus
- **Strategic role**: FRP confirmation. Not fast enough for 1-minute scoring.

### Rank 7: Sentinel-2 MSI (CONFIRMATION)
- **Scoring opportunities**: ~0.4 per day (5-day revisit)
- **Sensitivity**: 20 m SWIR (no thermal band)
- **Realistic latency**: 100 min - 3 hours
- **Strategic role**: Post-detection confirmation and perimeter mapping if overpass aligns

### Rank 8: FY-4B / FY-3D MERSI (SUPPLEMENTARY)
- **FY-4B**: Geostationary at 123.5E, 15-min cadence, fire products available. Supplementary to Himawari.
- **FY-3D MERSI-II**: 250 m thermal -- best polar-orbiting resolution -- but data access reliability from NSMC is a concern.
- **Strategic role**: Nice-to-have redundancy. Do not depend on for real-time operations.

## 2. Realistic Data Latency for Each Sensor Over NSW

| Sensor | Data Access Path | Realistic Latency | Bottleneck |
|--------|-----------------|-------------------|-----------|
| Himawari-9 | JAXA P-Tree | 5-20 min | JMA processing + transmission |
| Himawari-9 | AWS NODD (noaa-himawari) | 7-15 min (est.) | JMA->NOAA relay |
| GK-2A | AWS NODD (noaa-gk2a-pds) | Similar to Himawari | KMA->NOAA relay |
| VIIRS | Direct broadcast (GA Alice Springs) | 5-15 min | Ground station processing |
| VIIRS | DEA Hotspots | ~17 min minimum | GA processing pipeline |
| VIIRS | FIRMS NRT | Up to 3 hours | Global processing queue |
| MODIS | Direct broadcast | 5-15 min | Same as VIIRS |
| MODIS | FIRMS NRT | Up to 3 hours | Global processing queue |
| Landsat | USGS RT tier | 4-6 hours | Transfer to EROS + processing |
| Landsat | FarEarth Observer (Alice Springs) | <10 seconds | Partnership required |
| Sentinel-2 | Copernicus NRT | 100 min - 3 hours | Ground segment |
| Sentinel-3 | Copernicus NRT | ~3 hours | Ground segment |
| FY-4B | NSMC | Unknown | International access reliability |

## 3. Which Sensors Can Hit the 1-Minute-From-Overpass Window?

The scoring rule states: 1-minute detection is measured from satellite overpass, with each overpass getting its own 1-minute clock. This means we need data + processing completed within 1 minute of the satellite passing over the fire.

**Can hit 1 minute:**
- **VIIRS via direct broadcast** -- IF we have a direct feed from an Australian ground station (GA Alice Springs processes VIIRS RDR) and can run our fire detection algorithm within seconds of data availability. Realistic chain: overpass -> X-band downlink (~5 min pass) -> L0/RDR processing -> our algorithm -> alert. The 5-15 min ground processing latency likely means we CANNOT hit 1 minute from overpass start, but MAY be able to hit 1 minute from the overpass midpoint if we can access partial-pass data.
- **Landsat via FarEarth Observer** -- IF deployed at Alice Springs. FarEarth processes data line-by-line during the pass, achieving <10 second latency. This is the only technology that can genuinely hit 1 minute from overpass.

**Cannot hit 1 minute:**
- **Himawari**: 7-15 minute minimum latency means we're always 6-14 minutes late for the "1 minute from overpass" metric. However, Himawari observations are continuous -- the question is whether judges treat each 10-minute scan as an "overpass."
- **All FIRMS-based data**: Minimum 30 minutes for RT, hours for NRT
- **Copernicus data**: 100+ minutes minimum

**Critical question for XPRIZE**: Does the "1-minute from overpass" scoring apply to geostationary satellites? If Himawari scans NSW every 10 minutes, is each scan an "overpass" with its own 1-minute clock? If YES, then the 7-15 minute Himawari latency means we can never score on Himawari for the 1-minute metric, only for characterization. If NO (geostationary is excluded from overpass scoring), then only LEO passes count.

## 4. Must-Have vs Nice-to-Have Partnerships

### MUST-HAVE
1. **Geoscience Australia / DEA Hotspots** -- Access to near-real-time VIIRS/MODIS fire detections for NSW with ~17 min latency. This is operational and available via WFS without registration. Essential as our baseline VIIRS data source.
   - Contact: earth.observation@ga.gov.au

2. **JAXA P-Tree registration** -- Free registration for Himawari-9 NRT data. Essential for our primary geostationary feed.

3. **NASA FIRMS MAP_KEY** -- Free API key for global active fire data. Essential for cross-validation and supplementary data.

4. **AWS Account in us-east-1** -- Co-located with NODD data mirrors. Essential for low-latency Himawari and VIIRS data ingestion via SNS.

### NICE-TO-HAVE (High Value)
5. **Bureau of Meteorology VIIRS/HRPT direct broadcast** -- BoM operates HRPT stations in Melbourne and Darwin. If they share near-real-time VIIRS SDR/RDR data, we could run our own fire detection within minutes of overpass, potentially hitting the 1-minute window.
   - Contact: satellites@bom.gov.au

6. **CfAT/Viasat Real-Time Earth (Alice Springs)** -- Commercial ground station that receives LEO EO data. Could provide fastest VIIRS data path.

7. **Landgate/WASTAC (Perth)** -- Near-real-time VIIRS/MODIS quick-look archive. May provide faster data than FIRMS for western NSW overpasses.

### ASPIRATIONAL (Highest Risk, Highest Reward)
8. **Geoscience Australia Alice Springs -- FarEarth Observer deployment** -- If GA permits us to run real-time Landsat processing at Alice Springs during the competition window, we could achieve <10 second Landsat fire detection. This would be a competition-defining capability, but requires significant institutional cooperation.

9. **OroraTech partnership** -- Their commercial constellation (~16+ satellites) provides thermal fire detection with <10 min alerts. A data sharing agreement would give us an additional independent fire detection stream.

## 5. Daily Observation Timeline (Typical Day, AEST)

```
00:00-01:00  Himawari continuous (6 scans) + GK-2A continuous
01:00-03:00  VIIRS night passes (NOAA-21, S-NPP, NOAA-20) -- 3 passes
             BEST NIGHTTIME SCORING WINDOW
02:00-03:00  FY-3D MERSI-II night pass
05:30-06:30  FY-3E MERSI-LL early morning pass
06:00        Sunrise (April NSW)
09:00-10:00  Terra MODIS morning pass (drifted orbit)
09:30-10:30  MetOp AVHRR passes
10:00-11:00  Sentinel-3 SLSTR pass
10:00-10:30  Landsat pass IF PATH ALIGNS (2-4 times in 2 weeks)
10:30-11:00  Sentinel-2 pass IF TILE ALIGNS
13:00-15:00  VIIRS day passes (NOAA-21, S-NPP, NOAA-20) -- 3 passes
             BEST DAYTIME SCORING WINDOW
14:00-15:00  FY-3D MERSI-II day pass + Aqua MODIS
17:00-17:30  Sunset (April NSW)
17:30-18:30  FY-3E MERSI-LL evening pass
21:30-22:30  MetOp AVHRR night passes + Terra MODIS night
22:00-23:00  Sentinel-3 SLSTR night pass
```

**Himawari-9 provides continuous coverage throughout, with 144 observations per day.**

### Estimated scoring opportunities per day:
- Himawari: 144 scan cycles (but latency prevents 1-min scoring -- these count for 10-min characterization)
- VIIRS: 6 passes (3 day + 3 night) -- highest value for 1-min scoring
- MODIS: 4 passes (but 2 overlap with VIIRS timing)
- Other LEO: 4-8 additional passes
- Landsat/Sentinel-2: 0-1 (rare but extremely high value)

**Total LEO scoring opportunities: ~10-18 per day**

## 6. Himawari Strategy

### Primary: AWS NODD with SNS push notifications
- Subscribe to NewHimawariNineObject SNS topic from us-east-1
- Filter for fire-relevant bands (B07, B14, B15)
- Process only NSW segments (Segment 8: ~21-32S, Segment 9: ~32-47S)
- Run contextual + temporal fire detection

### Supplementary: JAXA P-Tree
- Register for access (free, commercial use permitted from Feb 2026)
- Use as fallback if AWS NODD has gaps
- Latency: 5-20 minutes

### GK-2A as independent check
- AWS NODD mirror at noaa-gk2a-pds
- Process same bands with same algorithm
- Independent detection from a different viewing angle provides strong confirmation

### FY-4B as additional redundancy
- Register at NSMC for FY-4B Fire/Hotspot product
- 15-minute cadence
- Use as tertiary check, not primary

## 7. Direct Broadcast vs Cloud Mirrors vs FIRMS

| Sensor | Direct Broadcast | Cloud Mirror (AWS NODD) | FIRMS |
|--------|-----------------|------------------------|-------|
| Himawari-9 | N/A for us | PRIMARY PATH (7-15 min) | Backup (30+ min) |
| VIIRS | BEST PATH if partnership works (5-15 min) | Available but latency uncertain | Backup only (hours) |
| MODIS | Same as VIIRS | Same as VIIRS | Backup only (hours) |
| GK-2A | N/A | SECONDARY PATH | N/A |
| Landsat | BEST PATH via FarEarth (<10s) | Available but 4-6 hours | N/A for Australia |

### Recommended architecture:
1. **Himawari**: Cloud mirror (AWS NODD) with SNS push -- this is our fastest reliable path
2. **VIIRS**: Pursue direct broadcast partnership with GA/BoM as primary; fall back to DEA Hotspots (~17 min) and FIRMS NRT (hours)
3. **GK-2A**: Cloud mirror for independent confirmation
4. **Landsat**: Standard USGS pipeline (4-6 hours) unless FarEarth partnership materializes
5. **FIRMS**: Poll every 2-5 minutes as safety net for all sensors
6. **DEA Hotspots**: Poll WFS every 10 minutes -- this is our most reliable Australian-specific data source requiring no partnerships
