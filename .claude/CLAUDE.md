# Wildfire XPRIZE Detection System

## Project Overview
Low-latency wildfire detection system for XPRIZE Track A finals (April 2026, NSW Australia). Uses public satellite data to detect fires within ~1 minute, report within ~10 minutes, with <5% false positive rate.

See `docs/deep-research-report.md` for the full system design from ChatGPT deep research.

## Architecture
Two-tier satellite fusion system:
- **Tier 1 (fast alerting):** Geostationary thermal imagery (Himawari AHI primary for NSW) with push-based ingestion
- **Tier 2 (confirmation):** Polar-orbiting active fire detections (VIIRS, MODIS) + high-resolution (Landsat, Sentinel-2)

Detection pipeline: trigger (seconds) -> refine (minutes) -> confirm (tens of minutes)

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

## Key Constraints
- Public satellite data only (no commercial imagery)
- Finals in NSW Australia — Himawari AHI is the primary geostationary source
- Target: <10 seconds from data arrival to preliminary alert
- Must handle burst capacity during major fire events

## Conventions
- Process in native sensor grids (avoid reprojection in hot path)
- Label alerts by timeliness class and sensor lineage
- Use push-based delivery (SNS/webhooks) over polling where possible
