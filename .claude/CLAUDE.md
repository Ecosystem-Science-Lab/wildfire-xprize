# Wildfire XPRIZE Detection System

## Project Overview
Low-latency wildfire detection system for XPRIZE Track A finals (April 9-21, 2026, NSW Australia). Uses public satellite data to detect fires, report within ~10 minutes, with <5% false positive rate.

**Competition timeline:** 22 days remaining as of March 18, 2026. Finals Application (CONOPS) due March 31.

## Key Documents
- `docs/plan/SYSTEM-PLAN.md` — **START HERE.** Unified system architecture, v2.0 (revised after external review)
- `docs/plan/revised-priorities-evaluation.md` — Team evaluation of revised priorities with Week 1 checklist
- `docs/plan/detection-pipeline.md` — Detection pipeline design
- `docs/plan/fusion-confidence.md` — Fusion, confidence scoring, event lifecycle
- `docs/plan/sensor-strategy.md` — Which sensors, why, and how to access them
- `docs/plan/red-team-analysis.md` — Risks, failure modes, competitive analysis
- `docs/deep-research-report.md` — Original ChatGPT deep research on system design
- `docs/partnership-strategy.md` — Data partnership strategy and contacts
- `docs/alice-springs-ground-station-research.md` — GA Alice Springs facility details
- `docs/outreach-emails.md` — Partnership email drafts (BoM, GA)

## Architecture (v2.0 — revised)
Two-path system with fallback-first design:

**Primary:** Raw Himawari-9 AHI → custom contextual fire detection → provisional alerts
**Fallback:** DEA Hotspots + FIRMS polling → deduplication → alerts (built FIRST as insurance)
**Confirmation:** VIIRS/MODIS via DEA Hotspots + FIRMS, GK-2A cross-check (Week 2)

Both paths feed a shared event store. Judge portal displays whichever source detects first.

### Alert Philosophy (critical design decision)
- **Immediate provisional alerts** on first credible AHI detection (don't wait for confirmation)
- Tiered: extreme anomalies (BT>360K) instant HIGH confidence; moderate anomalies get 10-min hold
- Upgrade/retract on subsequent frames
- "Low confidence detections still count if correct" (per XPRIZE all-teams call)

### Confidence Ladder (rule-based, NOT Bayesian)
PROVISIONAL → LIKELY → CONFIRMED → MONITORING → CLOSED (+ RETRACTED)
One observation = one evidence contribution (no double-counting across FIRMS/DEA/custom pipeline)

## API Keys and Data Access
Credentials in `config/api_keys.env`:
- **FIRMS MAP_KEY** — NASA fire detections API (5000 req/10min)
- **JAXA P-Tree** — FTP access to Himawari HSD data (backup to AWS NODD)
- **Copernicus CDSE** — OAuth access to Sentinel-2/3 data

### Data Sources (priority order)
1. **Himawari-9 AHI** via AWS NODD SNS push (primary, ~7-15 min latency)
2. **DEA Hotspots** WFS polling (VIIRS/MODIS, ~17 min, no registration needed)
3. **FIRMS API** polling (VIIRS/MODIS/Landsat, MAP_KEY required, ~3hr NRT for Australia)
4. **JAXA P-Tree** FTP (Himawari backup, ~7-9 min latency)
5. **GK-2A** via AWS NODD (Week 2 cross-check)

## Domain Experts
Technical domain knowledge lives in `context/domain_briefs/{domain}/`. Each domain has 5 standard files plus any domain-specific custom files:

### Standard files (always present):
- `DOMAIN.md` — Scope, relevance to our system, key concepts
- `algorithms.md` — Pseudocode, reference implementations, key parameters
- `apis_and_data_access.md` — Endpoints, auth, rate limits, data formats
- `code_patterns.md` — Libraries, implementation patterns, frameworks
- `pitfalls.md` — What breaks in practice, edge cases, gotchas

### Custom files (added per domain as needed):
Domains may include additional files for topics that don't fit neatly into the standard 5. Examples: `sensor_specifications.md`, `thresholds_reference.md`, `training_data_catalog.md`, `perplexity_research.md` (raw research output). Check each domain directory for its full contents.

### Available domains:
- `satellite-remote-sensing` — Sensor physics, bands, orbits, resolution tradeoffs
- `satellite-data-preprocessing` — Orthorectification, atmospheric correction, radiometric calibration, cloud masking
- `fire-detection-algorithms` — Contextual thresholds, FRP, sub-pixel detection, VIIRS/GOES algorithms
- `streaming-data-engineering` — Event-driven ingestion, SNS/SQS, cloud mirrors, latency optimization
- `multi-sensor-fusion` — Cross-sensor corroboration, confidence scoring, false positive reduction
- `ml-remote-sensing` — CNN classifiers, anomaly detection, training data strategies
- `geospatial-processing` — Native grids, projections, raster I/O, STAC/FIRMS APIs
- `historical-fire-data` — Fire archives, burned area products, Australian fire ecology, training data construction
- `satellite-constellation-inventory` — Exhaustive catalog of every satellite that can observe NSW with fire-relevant capability

Use `/consult-expert` to invoke a domain expert. Use `/research-domain` to build or update one.

## Implementation Priorities (revised v2.0)
1. ~~Send partnership emails~~ (Done: BoM, GA, OroraTech)
2. ~~Register for APIs~~ (Done: FIRMS, JAXA P-Tree, Copernicus)
3. **Build fallback system** (DEA+FIRMS polling → dedup → event store → portal → GeoJSON)
4. **Build Himawari pipeline** (AWS SNS → SQS → HSD decode → contextual detection → alerts)
5. **Event store + confidence ladder + portal integration**
6. **DEA/FIRMS as confirmation layer** (cross-match with custom detections)
7. **Daily report automation** (OGC GeoJSON, due 20:00 AEST daily during competition)
8. **CONOPS + Finals Application** (due March 31)
9. (stretch) ML classifier
10. (stretch) CUSUM temporal detection

## Key Constraints
- Public satellite data primarily (commercial allowed if declared and legally sourced)
- Finals in NSW Australia — Himawari AHI is the primary geostationary source
- Target: <10 seconds from data arrival to preliminary alert
- False positive rate <5%
- Must produce OGC-compliant reports loadable in ArcGIS
- Judge portal is THE product — build it early, not late

## Conventions
- Process in native sensor grids (avoid reprojection in hot path)
- Label alerts by timeliness class and sensor lineage
- Use push-based delivery (SNS/webhooks) over polling where possible
- Honest characterization: uncertainty circles, not decorative perimeters
- One observation = one evidence contribution (provenance tracking)
