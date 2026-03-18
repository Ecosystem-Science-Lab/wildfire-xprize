# Sensor & Data Access Strategy

**Updated:** 2026-03-18 (revised priorities)

## 1. Core Sensor Stack

The revised plan focuses ruthlessly on three data sources that are available now, require no partnerships, and can be integrated in the first week.

### Rank 1: Himawari-9 AHI (Geostationary -- PRIMARY, Custom Processing)

- **Role:** Continuous trigger layer and characterization backbone
- **Scoring opportunities**: 144 per day (every 10 minutes, 24/7)
- **Sensitivity**: ~1,000-4,000 m2 minimum at NSW latitudes (3-4 km effective pixels)
- **Realistic latency**: 7-15 minutes from observation to data availability (AWS NODD)
- **1-minute scoring feasibility**: NO for the 1-minute-from-overpass metric. Himawari's value is continuous monitoring, rapid alerting, and characterization updates every 10 minutes.
- **Data access**: AWS NODD S3 bucket with SNS push notifications (`NewHimawariNineObject` topic in us-east-1). Event-driven pipeline.
- **Backup access**: JAXA P-Tree (free registration, polling, 5-20 min latency)
- **Processing**: Custom contextual threshold fire detection (see `detection-pipeline.md`)

### Rank 2: VIIRS via DEA Hotspots (LEO -- PRIMARY CONFIRMATION)

- **Role:** Highest-value confirmation layer. Each VIIRS detection matching a Himawari alert upgrades confidence to CONFIRMED.
- **Scoring opportunities**: ~6 per day (3 satellites x ~2 passes each)
- **Sensitivity**: ~100-500 m2 (375 m pixels)
- **Realistic latency**: ~17 minutes minimum after overpass (GA processing pipeline)
- **1-minute scoring feasibility**: NO at 17-min latency. Would require direct broadcast partnership (not load-bearing).
- **Data access**: DEA Hotspots WFS API. Public, no registration required. Poll every 5 minutes.
- **Processing**: Parse GeoJSON point products. No raw VIIRS processing needed.

### Rank 3: FIRMS API (Multi-Sensor -- SAFETY NET)

- **Role:** Catches anything DEA misses. Provides VIIRS, MODIS, and Himawari fire detections from NASA's global processing.
- **Latency**: 30 min for Real-Time (RT), up to 3 hours for Near-Real-Time (NRT)
- **Data access**: FIRMS API with MAP_KEY (free registration). Poll every 2-5 minutes.
- **Processing**: Parse CSV. Spatial/temporal match to existing events.
- **Key value**: If DEA Hotspots has an outage, FIRMS provides backup VIIRS data. If our Himawari processing has issues, FIRMS provides Himawari fire detections from NASA's processing chain.

---

## 2. Week 2 Addition: GK-2A AMI (Cross-Check)

- **Role:** Independent geostationary cross-check from a different viewing angle (128.2E vs 140.7E for Himawari)
- **Why keep it:** The AWS NODD mirror already exists. The incremental engineering cost is trivial once the Himawari pipeline works (same ABI-class instrument, same data format). GK-2A provides genuinely independent confirmation -- different satellite, different operator (KMA), different viewing angle.
- **Why Week 2 (not Week 1):** Focus Week 1 on getting Himawari + fallback working. GK-2A is low-effort once Himawari is stable.
- **Data access**: AWS NODD at `noaa-gk2a-pds`. No SNS push notifications documented -- may need polling.
- **Processing**: Run the same contextual algorithm used for Himawari. Feed detections into the event store as cross-check evidence (different satellite = independent confirmation).
- **NOT a separate detection pipeline.** GK-2A detections feed into the same event store. They upgrade confidence when they independently confirm a Himawari detection.

---

## 3. Dropped Sensors

| Sensor | Why Dropped | Alternative |
|--------|-----------|-------------|
| **Sentinel-3 SLSTR** | ~3 hour latency via Copernicus, adds nothing over DEA Hotspots at 17 min | VIIRS via DEA covers the same fires faster |
| **FY-4B** | Data access from NSMC is unreliable for real-time operations | Himawari + GK-2A provide two geostationary sources |
| **FY-3D MERSI** | 250 m is tempting but NSMC data access risk is unacceptable in 22 days | VIIRS at 375 m via DEA is reliable |
| **Raw VIIRS processing** | Direct broadcast partnership is aspirational, not load-bearing | DEA Hotspots at ~17 min is our realistic VIIRS path |
| **Landsat real-time** | FarEarth/Alice Springs partnership not viable at this timeline | Landsat detections via FIRMS (4-6 hr latency) only |
| **Sentinel-2 real-time** | 5-day revisit, no thermal band, marginal value | Via FIRMS/DEA only |
| **MODIS (separate processing)** | Redundant with VIIRS (same orbits), coarser resolution (1 km vs 375 m) | MODIS detections come through FIRMS automatically |

---

## 4. Partnership Opportunities

### HimawariRequest Rapid Scan (2.5-min cadence)

The AHI Target Area scan provides 2.5-minute cadence over a 1000x1000 km box. This would cut our geostationary revisit from 10 min to 2.5 min -- transformative for detection speed.

**Status:** Controlled by JMA, primarily used for typhoons and volcanoes. Requesting it for a 2-week fire competition in NSW requires JMA agreement, likely brokered through BoM (satellites@bom.gov.au).

**Probability:** LOW (10-15%). But the cost of asking is one email. Send it, expect nothing, move on.

### OroraTech Commercial Thermal Alerts

OroraTech claims 3-minute alerts, 4x4m fire detection, ~16+ satellites operational by April 2026. If they would share alerts during the competition window:
- We get an independent, high-resolution thermal detection layer we cannot build ourselves
- It fills our biggest gap (small fires between VIIRS passes)

**Legal:** The R&R says "observations of wildfires shall be made from Space" and "legally-sourced data." It does NOT say "public data only." Commercial data is allowed as long as it is declared and legally obtained.

**Probability:** LOW (10-20%). Contact OroraTech sales. Worst case: they say no.

### Faster DEA Hotspots / GA Partnership

Contact GA (earth.observation@ga.gov.au) about faster DEA Hotspots access or a priority API during the competition window.

**Probability:** MODERATE (20-30%). GA may be supportive given the XPRIZE visibility.

### NOT Pursuing

| Partner | Reason |
|---------|--------|
| Earth Fire Alliance / FireSat | Phase 1 (3 satellites) planned for mid-2026, NOT operational by April 9 |
| FarEarth / Pinkmatter | Landsat real-time at Alice Springs is not viable at 22-day timeline |
| CfAT / Viasat GSaaS | Commercial ground station adds complexity we cannot absorb |

**Design principle:** Design everything around DEA Hotspots as the VIIRS path and AWS NODD as the Himawari path. Any partnership that materializes is pure upside, not load-bearing.

---

## 5. Realistic Data Latency for Core Stack Over NSW

| Sensor | Data Access Path | Realistic Latency | Bottleneck |
|--------|-----------------|-------------------|-----------|
| Himawari-9 | AWS NODD (noaa-himawari) + SNS push | 7-15 min (est.) | JMA->NOAA relay |
| Himawari-9 | JAXA P-Tree (backup) | 5-20 min | JMA processing |
| GK-2A | AWS NODD (noaa-gk2a-pds), polling | ~7-15 min (est.) | KMA->NOAA relay |
| VIIRS | DEA Hotspots WFS | ~17 min minimum | GA processing pipeline |
| VIIRS/MODIS/Himawari | FIRMS API (RT) | ~30 min | Global processing queue |
| VIIRS/MODIS/Landsat | FIRMS API (NRT) | Up to 3 hours | Global processing queue |

**Critical unknown:** Actual AWS NODD Himawari latency. Must measure empirically during Week 1. If consistently >15 minutes, switch to JAXA P-Tree as primary.

---

## 6. Daily Observation Timeline (Typical Day, AEST)

```
00:00-01:00  Himawari continuous (6 scans) + GK-2A continuous
01:00-03:00  VIIRS night passes (NOAA-21, S-NPP, NOAA-20) -- 3 passes
             BEST NIGHTTIME SCORING WINDOW
06:00        Sunrise (April NSW)
09:00-10:00  Terra MODIS morning pass (drifted orbit)
10:00-10:30  Landsat pass IF PATH ALIGNS (2-4 times in 2 weeks)
13:00-15:00  VIIRS day passes (NOAA-21, S-NPP, NOAA-20) -- 3 passes
             BEST DAYTIME SCORING WINDOW
17:00-17:30  Sunset (April NSW)
```

**Himawari-9 provides continuous coverage throughout, with 144 observations per day.**

### Estimated scoring opportunities per day:

- **Himawari:** 144 scan cycles (too much latency for 1-min scoring; primary value is trigger + characterization)
- **VIIRS:** 6 passes (3 day + 3 night) -- highest value scoring opportunities
- **MODIS:** 4 passes (2 overlap with VIIRS timing) -- via FIRMS
- **Landsat:** 0-1 per competition (rare but high value if it aligns) -- via FIRMS

---

## 7. Data Architecture

### Primary: AWS NODD with SNS Push (Himawari)

```
SNS Topic (NewHimawariNineObject)
    |
    v
SQS Queue (filtered for B07, B14, NSW segments)
    |
    v
Processing Lambda/ECS
    |
    v
Pass 0 (decode) -> Pass 1 (contextual detection) -> Alert Policy -> Event Store
```

### Primary: Polling (DEA Hotspots + FIRMS)

```
Every 5 minutes:
    DEA Hotspots WFS query (NSW bounding box) -> Parse GeoJSON -> Event Store
    FIRMS API query (NSW bounding box) -> Parse CSV -> Event Store
```

### Backup: JAXA P-Tree (Himawari)

If AWS NODD is down or latency is unacceptable:
- Switch to JAXA P-Tree
- Poll every 5 minutes for new Himawari data
- Same downstream processing

### GK-2A (Week 2)

```
Poll AWS NODD (noaa-gk2a-pds) for new files
    |
    v
Same processing as Himawari
    |
    v
Cross-check feed into Event Store (not separate pipeline)
```

---

## 8. Must-Have vs Nice-to-Have Resources

### Available Now (No Partnership Needed)

| Resource | Access Path | Status |
|----------|-----------|--------|
| Himawari-9 data | AWS NODD S3 bucket + SNS | Public, available |
| GK-2A data | AWS NODD S3 bucket | Public, available |
| VIIRS/MODIS fire detections | DEA Hotspots WFS | Public, no registration |
| VIIRS/MODIS fire detections | FIRMS API (MAP_KEY) | Free registration |
| Himawari NRT data | JAXA P-Tree | Free registration |
| AWS compute (us-east-1) | AWS account | Team account |

### Partnership Emails Sent (Day 1, March 18)

| Partner | Contact | What We Asked | Expected Response Time |
|---------|---------|---------------|----------------------|
| BoM | satellites@bom.gov.au | HimawariRequest Target Area + faster Himawari | 1-2 weeks |
| OroraTech | sales contact | Trial/pilot during competition | 1 week |
| GA | earth.observation@ga.gov.au | Faster DEA Hotspots or priority API | 1-2 weeks |

### Infrastructure Requirements

| Resource | Priority | Status |
|----------|---------|--------|
| AWS account in us-east-1 | Week 1 Day 1 | SET UP TODAY |
| FIRMS MAP_KEY | Week 1 Day 1 | REGISTER TODAY |
| JAXA P-Tree registration | Week 1 Day 1 | REGISTER TODAY |
| Domain/hosting for judge portal | Week 1 Day 2-3 | Standard web deployment |
