# Fire Detection Algorithms

## Overview
Fire detection from satellite imagery relies on the physics of thermal emission: active fires emit strongly in the mid-infrared (MIR, ~3.5-4.0 μm) relative to their surroundings, creating a detectable contrast even when the fire occupies a tiny fraction of a pixel. All operational algorithms exploit the brightness temperature difference between a MIR channel and a longer-wave thermal IR (TIR, ~10-12 μm) channel, combined with contextual tests against local background statistics.

## Why This Matters for Our System
Fire detection algorithms are the core of our XPRIZE system. We need to implement or adapt these algorithms to run in real-time (<10 seconds from data arrival to alert). The key challenge is balancing sensitivity (detecting small fires quickly) against false positive rate (<5% target). For NSW Australia, we need algorithms tuned for:
- Hot, bright Australian summer backgrounds (surface temps >320 K)
- Eucalypt forest fire behavior (intense flaming fronts)
- Mixed vegetation (grassland, woodland, forest)
- Himawari AHI as primary geostationary sensor (2 km pixels)
- VIIRS as primary polar-orbiting sensor (375 m pixels)

## Key Concepts

### Sub-pixel fire detection
A fire can be detected even when much smaller than a pixel because the Planck function is highly nonlinear — a small hot object (800-1200 K fire) contributes disproportionately to MIR radiance relative to a warm background (300 K). The key observable is the brightness temperature difference ΔT = BT_MIR - BT_TIR, which is elevated for fire-containing pixels because MIR is more sensitive to temperature than TIR.

### Detection vs characterization
- **Detection**: Binary fire/no-fire classification using threshold and contextual tests
- **Characterization**: Estimating sub-pixel fire area, temperature, and Fire Radiative Power (FRP) using dual-band Dozier-style inversion or single-band FRP methods

### Algorithm families
1. **Contextual threshold** (VIIRS VNP14IMG, MODIS MOD14): Fixed + dynamic thresholds relative to local background statistics. Fast, transparent, well-validated.
2. **Geostationary contextual + temporal** (GOES ABI FDCA, Himawari WF_ABI): Similar contextual approach but adds temporal persistence/filtering across successive frames. Exploits high cadence.
3. **ML-based** (Pass 2 in our pipeline): Lightweight CNN to reclassify candidates from Pass 1, reducing false positives.

## Operational Algorithms We Need to Implement/Adapt

### Tier 1: Geostationary (Himawari AHI)
- Primary sensor for fast alerting (~10 min cadence)
- Band 7 (3.9 μm, 2 km) and Band 14 (11.2 μm, 2 km)
- Need to adapt GOES FDCA-style algorithm for AHI
- Minimum detectable fire: ~900-4000 m² depending on conditions

### Tier 2: Polar-orbiting (VIIRS)
- Higher spatial resolution (375 m) for confirmation and small fire detection
- I4 (3.74 μm) and I5 (11.45 μm) bands
- VNP14IMG algorithm is well-documented and directly applicable
- Minimum detectable fire: sub-pixel, routinely ~100s of m²

### Tier 3: High-resolution (Landsat, Sentinel-2)
- Opportunistic confirmation at 30 m / 20 m resolution
- Can detect fires of a few m² at overpass time
- Sparse revisit — not for initial detection

## Relevance to XPRIZE Scoring
- Detection time is measured from ignition, but we can only detect from data arrival
- Sub-minute processing is achievable; the bottleneck is sensor cadence and data latency
- False positive rate <5% requires multi-stage filtering (contextual + temporal + ML)
- Spatial accuracy matters for scoring — geostationary gives km-scale location, polar gives sub-km
