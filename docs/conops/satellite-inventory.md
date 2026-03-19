# Satellite Inventory — XPRIZE Track A Declaration

**Team:** NAU Ecosystem Science Lab
**Date:** March 19, 2026

## Primary Detection (Custom Processing)

| Satellite | Operator | Instrument | Orbit | Altitude | Bands Used | Pixel Resolution | Cadence | Role |
|-----------|----------|------------|-------|----------|------------|-----------------|---------|------|
| Himawari-9 | JMA (Japan) | AHI | GEO (140.7°E) | 35,786 km | B07 (3.9µm), B14 (11.2µm) | 2 km | 10 min | Continuous fire detection — contextual (instant) + CUSUM temporal (accumulated) |

## Confirmation (Processed Products via DEA Hotspots + FIRMS)

| Satellite | Operator | Instrument | Orbit | Altitude | Bands Used | Pixel Resolution | NSW Passes/Day | Role |
|-----------|----------|------------|-------|----------|------------|-----------------|----------------|------|
| NOAA-20 (JPSS-1) | NOAA | VIIRS | LEO (sun-sync) | 824 km | I4 (3.74µm), I5 (11.45µm) | 375 m | ~2 | Confirmation via DEA Hotspots (~17 min) + FIRMS |
| Suomi NPP | NASA/NOAA | VIIRS | LEO (sun-sync) | 824 km | I4 (3.74µm), I5 (11.45µm) | 375 m | ~2 | Confirmation via DEA Hotspots + FIRMS |
| NOAA-21 (JPSS-2) | NOAA | VIIRS | LEO (sun-sync) | 824 km | I4 (3.74µm), I5 (11.45µm) | 375 m | ~2 | Confirmation via DEA Hotspots + FIRMS |
| Terra | NASA | MODIS | LEO (sun-sync) | 705 km | B21/22 (3.9µm), B31 (11µm) | 1 km | ~2 | Supplementary confirmation via FIRMS |
| Aqua | NASA | MODIS | LEO (sun-sync) | 705 km | B21/22 (3.9µm), B31 (11µm) | 1 km | ~2 | Supplementary confirmation via FIRMS |

## Planned Cross-Check (Week 2)

| Satellite | Operator | Instrument | Orbit | Altitude | Bands Used | Pixel Resolution | Cadence | Role |
|-----------|----------|------------|-------|----------|------------|-----------------|---------|------|
| GK-2A | KMA (Korea) | AMI | GEO (128.2°E) | 35,786 km | SWIR (3.8µm), IR (10.5µm) | 2 km | 10 min | Independent geostationary cross-check, different viewing angle |

## Opportunistic (via FIRMS, not custom-processed)

| Satellite | Operator | Instrument | Orbit | Altitude | Resolution | Role |
|-----------|----------|------------|-------|----------|------------|------|
| Landsat 8 | USGS/NASA | OLI/TIRS | LEO (sun-sync) | 705 km | 30m/100m | Via FIRMS (4-6h latency). Rare but high-res confirmation. |
| Landsat 9 | USGS/NASA | OLI-2/TIRS-2 | LEO (sun-sync) | 705 km | 30m/100m | Same as Landsat 8. |

## Data Access Paths

| Access Path | Satellites Covered | Method | Typical Latency | Registration |
|-------------|-------------------|--------|----------------|-------------|
| AWS NODD S3 | Himawari-9, GK-2A | Public unsigned S3 reads | ~13 min | None |
| DEA Hotspots | VIIRS (NOAA-20, NPP, NOAA-21) | WFS API | ~17 min | None |
| FIRMS API | VIIRS, MODIS, Landsat | REST CSV/JSON | 30 min – 3h | MAP_KEY (free) |
| JAXA P-Tree | Himawari-9 (backup) | FTP | ~7-9 min | Free registration |

All data sources are publicly available and legally sourced. No commercial data subscriptions required.
