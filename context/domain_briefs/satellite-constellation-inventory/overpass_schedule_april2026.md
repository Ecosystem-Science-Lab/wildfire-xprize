# Satellite Overpass Schedule for NSW, Mid-April 2026

## Overview

This document provides the best estimates for satellite overpasses and observation windows over NSW Australia during a representative 2-week window in mid-April 2026 (approximately April 10-24, 2026).

**Important:** Exact overpass times for LEO satellites must be computed from current TLEs closer to the competition date. The times listed here are approximate based on orbital parameters and will shift by minutes to tens of minutes depending on TLE freshness.

---

## 1. Geostationary Satellites (Continuous -- No Schedule Needed)

These satellites observe NSW continuously. Their scan cadence is fixed and predictable.

### Himawari-9 (140.7E) -- PRIMARY

| Parameter | Value |
|---|---|
| Scan cadence | Full disk every 10 minutes |
| Scan pattern | North-to-south sweep |
| NSW scan timing | Approximately 6-8 minutes after scan start |
| Data availability | 5-20 min after observation (JAXA P-Tree) |
| Daily observations | 144 full-disk scans per day |
| Night/day | Both. Thermal channels work 24/7. |

**Approximate NSW observation times (UTC) for every scan:**
00:06, 00:16, 00:26, 00:36, 00:46, 00:56, 01:06, 01:16, ... (every 10 minutes, 24/7)

**Convert to AEST (UTC+10):** Add 10 hours.
10:06, 10:16, 10:26, ... AEST (every 10 minutes, 24/7)

### GK-2A (128.2E)

| Parameter | Value |
|---|---|
| Scan cadence | Full disk every 10 minutes |
| NSW scan timing | Similar to Himawari |
| Daily observations | 144 full-disk scans per day |

### FY-4B (123.5E)

| Parameter | Value |
|---|---|
| Scan cadence | Full disk every 15 minutes |
| Daily observations | 96 full-disk scans per day |

---

## 2. Sun-Synchronous LEO Satellites -- Approximate Overpass Times

### Key Concept: Local Solar Time

Sun-synchronous satellites cross the equator at a nearly constant local solar time. The actual clock time of an overpass depends on the observer's longitude. NSW spans 148-154E, so local solar time leads UTC by approximately 10 hours (AEST = UTC + 10).

For each satellite, there are two passes per day at the equator:
- **Ascending node** (northbound): typically the daytime pass for afternoon satellites
- **Descending node** (southbound): typically the nighttime pass for afternoon satellites

At NSW latitudes (-28 to -37S), overpass times shift slightly from the equatorial crossing time.

### VIIRS Constellation (S-NPP, NOAA-20, NOAA-21)

**Equatorial crossing:** LTAN 13:30 (ascending), LTDN 01:30 (descending)

The three VIIRS satellites are spaced roughly evenly in the same orbital plane:
- NOAA-21 leads
- S-NPP is in the middle
- NOAA-20 trails

**Approximate NSW overpass local solar times:**
- Daytime (ascending): ~13:30-14:30 local solar time (early-mid afternoon)
- Nighttime (descending): ~01:30-02:30 local solar time (after midnight)

**Approximate AEST times for NSW center (151E):**
- Daytime passes: approximately 13:30-14:30 AEST (varies by exact orbit)
- Nighttime passes: approximately 01:30-02:30 AEST

**Estimated daily VIIRS passes over NSW (all 3 satellites combined):**

| Time Window (AEST) | Satellite | Pass Type | Notes |
|---|---|---|---|
| ~01:00-02:00 | NOAA-21 | Descending (night) | ~50 min before S-NPP |
| ~01:30-02:30 | S-NPP | Descending (night) | |
| ~02:00-03:00 | NOAA-20 | Descending (night) | ~50 min after S-NPP |
| ~13:00-14:00 | NOAA-21 | Ascending (day) | ~50 min before S-NPP |
| ~13:30-14:30 | S-NPP | Ascending (day) | |
| ~14:00-15:00 | NOAA-20 | Ascending (day) | ~50 min after S-NPP |

**Total: ~6 VIIRS passes per day over NSW** (3 day + 3 night)

**Gap analysis:** The longest VIIRS gap is roughly 10-11 hours (from the last afternoon pass ~15:00 to the first night pass ~01:00, and from the last night pass ~03:00 to the first afternoon pass ~13:00).

### MODIS (Terra + Aqua)

**Terra (orbit degrading):**
- Nominal LTDN: 10:30 (but drifting to ~08:30-09:00 by April 2026)
- Approximate NSW daytime pass: ~09:00-10:00 AEST (earlier than nominal due to drift)
- Approximate NSW nighttime pass: ~21:00-22:00 AEST

**Aqua:**
- LTAN: 13:30 (similar to VIIRS, slightly different due to orbit drift)
- Approximate NSW daytime pass: ~13:30-14:30 AEST
- Approximate NSW nighttime pass: ~01:30-02:30 AEST
- Note: Aqua MODIS overpass nearly coincides with VIIRS passes (same orbit plane)

**Total: ~4 MODIS passes per day over NSW** (but Aqua largely overlaps with VIIRS timing)

### Sentinel-3A/B SLSTR

**LTDN: 10:00**
- Approximate NSW daytime pass: ~10:00-11:00 AEST
- Approximate NSW nighttime pass: ~22:00-23:00 AEST
- Sentinel-3A and 3B are separated by 140 deg in the same orbit plane

**Total: ~2-4 SLSTR passes per day over NSW** (varies with orbit geometry)

### MetOp-B/C AVHRR

**LTDN: 09:30**
- Approximate NSW daytime pass: ~09:30-10:30 AEST
- Approximate NSW nighttime pass: ~21:30-22:30 AEST
- Two satellites provide better coverage

**Total: ~4 AVHRR passes per day over NSW**

### FY-3D MERSI-II

**LTDN: 14:00**
- Approximate NSW daytime pass: ~14:00-15:00 AEST
- Approximate NSW nighttime pass: ~02:00-03:00 AEST

**Total: ~2 MERSI-II passes per day over NSW**

### FY-3E MERSI-LL

**LTDN: ~05:30 (early morning orbit)**
- Approximate NSW early morning pass: ~05:30-06:30 AEST
- Approximate NSW evening pass: ~17:30-18:30 AEST
- Fills the early morning gap left by other satellites

**Total: ~2 MERSI-LL passes per day over NSW**

### Landsat 8 + 9

**LTDN: ~10:12**
- Approximate NSW daytime pass: ~10:12-10:30 AEST
- 16-day repeat cycle per satellite, 8-day offset between Landsat 8 and 9
- NSW requires multiple paths/rows; a given location is imaged approximately every 8 days

**Overpass dates for NSW center in April 2026:**

Landsat paths over NSW include WRS-2 paths 88-91, rows 79-84. For a specific location (e.g., -33S, 151E / Sydney area), approximate Landsat overpass dates in April 2026 (must be verified with USGS acquisition calendar):

- Landsat 8: approximately Apr 11, Apr 27 (16-day cycle)
- Landsat 9: approximately Apr 3, Apr 19 (16-day cycle, 8-day offset)

**For the full NSW area, there will be Landsat coverage on most days**, but any specific fire location may only be imaged 1-2 times in the 2-week window.

### Sentinel-2B + 2C

**LTDN: 10:30**
- Approximate NSW daytime pass: ~10:30-11:00 AEST
- 5-day combined revisit for any location
- Multiple tiles cover NSW

**Approximate Sentinel-2 passes over a specific NSW location: every 5 days**

### Sentinel-5P TROPOMI

**LTAN: 13:30**
- Daily global coverage
- ~5.5 x 3.5 km resolution for aerosol products
- One daytime pass per day over NSW

---

## 3. Non-Sun-Synchronous Orbits (Unpredictable Schedule)

### ECOSTRESS (ISS)

**Orbit:** 51.6 deg inclination, ~420 km altitude, ~92 min period

The ISS orbit precesses, meaning overpass times shift continuously. In a 2-week window, ECOSTRESS may observe NSW 3-7 times, but at different local times.

**Cannot be predicted months in advance.** Must use current ISS TLEs to predict overpasses within ~2 weeks of the competition.

**Typical ISS overpass characteristics for NSW:**
- Duration: ~5-7 minutes per pass
- Swath: 384 km
- Local time: can be any time (day or night) -- shifts by ~20 minutes earlier each day

---

## 4. Combined Overpass Timeline (Typical Day)

This shows a typical 24-hour cycle of satellite observations over NSW center (-33S, 151E) in mid-April 2026, in AEST:

| AEST | Satellite | Sensor | Resolution | Type |
|---|---|---|---|---|
| 00:00+ | Himawari-9 | AHI | 3-4 km | GEO (continuous) |
| ~01:00 | NOAA-21 | VIIRS | 375 m | LEO night |
| ~01:30 | S-NPP | VIIRS + OMPS | 375 m | LEO night |
| ~02:00 | NOAA-20 | VIIRS + OMPS | 375 m | LEO night |
| ~02:00 | FY-3D | MERSI-II | 250 m | LEO night |
| ~05:30 | FY-3E | MERSI-LL | 250 m | LEO early AM |
| ~09:00 | Terra | MODIS | 1 km | LEO morning (drifted) |
| ~09:30 | MetOp-B or C | AVHRR | 1.1 km | LEO morning |
| ~10:00 | Sentinel-3A or 3B | SLSTR | 1 km | LEO morning |
| ~10:12 | Landsat 8 or 9 | TIRS+OLI | 100m/30m | LEO (if path aligns) |
| ~10:30 | Sentinel-2B or 2C | MSI | 20m SWIR | LEO (if tile aligns) |
| ~10:30 | MetOp-C or B | AVHRR | 1.1 km | LEO morning |
| ~13:00 | NOAA-21 | VIIRS | 375 m | LEO afternoon |
| ~13:30 | S-NPP | VIIRS + OMPS | 375 m | LEO afternoon |
| ~13:30 | Sentinel-5P | TROPOMI | 5.5 km | LEO (aerosol) |
| ~14:00 | NOAA-20 | VIIRS | 375 m | LEO afternoon |
| ~14:00 | FY-3D | MERSI-II | 250 m | LEO afternoon |
| ~14:00 | Aqua | MODIS | 1 km | LEO afternoon |
| ~17:30 | FY-3E | MERSI-LL | 250 m | LEO evening |
| ~21:30 | MetOp-B or C | AVHRR | 1.1 km | LEO night |
| ~22:00 | Terra | MODIS | 1 km | LEO night (drifted) |
| ~22:00 | Sentinel-3A or 3B | SLSTR | 1 km | LEO night |

**Continuous geostationary observations from Himawari-9 (and GK-2A, FY-4B) fill ALL gaps.**

---

## 5. Worst-Case Detection Latency by Time of Day

| Time of Day (AEST) | Best Available Sensor | Expected Detection Latency |
|---|---|---|
| 00:00-01:00 | Himawari-9 (GEO) | 10-30 min |
| 01:00-03:00 | VIIRS (3 night passes) | 5-15 min (direct broadcast) |
| 03:00-05:00 | Himawari-9 (GEO) | 10-30 min |
| 05:00-06:30 | FY-3E MERSI-LL + Himawari | 10-30 min (Himawari), hours (MERSI) |
| 06:30-09:00 | Himawari-9 (GEO) | 10-30 min |
| 09:00-11:00 | Multiple LEO (MODIS, AVHRR, SLSTR, Landsat, S2) | 5-60 min |
| 11:00-13:00 | Himawari-9 (GEO) | 10-30 min |
| 13:00-15:00 | VIIRS (3 day passes) + MODIS | 5-15 min (direct broadcast) |
| 15:00-17:00 | Himawari-9 (GEO) | 10-30 min |
| 17:00-18:30 | FY-3E MERSI-LL + Himawari | 10-30 min |
| 18:30-21:00 | Himawari-9 (GEO) | 10-30 min |
| 21:00-00:00 | MetOp AVHRR + SLSTR + Terra + Himawari | 10-60 min |

**Absolute worst case:** A small fire (<1,000 m2) igniting between VIIRS passes during a cloudy period could go undetected for hours. The geostationary sensors would detect it only if it grows large enough (~1,000-4,000 m2) or if clouds clear.

---

## 6. April 2026 Solar and Environmental Context

| Parameter | April 2026 Value for NSW |
|---|---|
| Season | Autumn (Southern Hemisphere) |
| Day length | ~11-12 hours |
| Sunrise (Sydney) | ~06:00-06:30 AEST |
| Sunset (Sydney) | ~17:15-17:30 AEST |
| Solar elevation at noon | ~40-50 deg |
| Background temperature | Moderate (cooler than summer) |
| Fire risk | Declining from summer peak but still present |
| Cloud climatology | Variable; April is transition from summer thunderstorms to winter rain patterns |

**Solar geometry affects:**
- SWIR fire detection (Sentinel-2, Landsat) only works during daylight
- Sun glint risk is lower in autumn than summer
- Geostationary MIR background is lower at night (better fire detection sensitivity)
- VIIRS DNB nighttime fire detection benefits from longer nights in April vs summer

---

## 7. Pre-Competition TLE Refresh Checklist

1. **2 weeks before competition:** Download fresh TLEs from CelesTrak for all satellites. Run initial overpass schedule computation.
2. **3 days before:** Refresh TLEs. Recompute schedule. Compare with earlier predictions to assess drift.
3. **Day of competition start:** Final TLE refresh. Lock in overpass schedule for the first 2-3 days.
4. **Daily during competition:** Refresh TLEs daily to maintain prediction accuracy for days 3+.

**CelesTrak TLE groups to download:**
- `weather` (VIIRS, MODIS, MetOp, Meteor-M)
- `resource` (Landsat, Sentinel-2/3, ALOS-2)
- `stations` (ISS for ECOSTRESS)

**URL pattern:** `https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle`
