# Multi-Sensor Overpass Strategy for XPRIZE Track A Finals

**Date:** 2026-03-19
**Competition:** April 9-21, 2026, NSW Australia
**Key insight:** Scoring is per satellite overpass. Every sensor pass where a fire exists and we fail to report it = lost points.

---

## Executive Summary

Our current system plan treats Himawari as the backbone and VIIRS/MODIS via DEA Hotspots + FIRMS as confirmation. This is correct for continuous monitoring but **misses the scoring model**: judges evaluate detection at each satellite overpass. A 10 m^2 fire that VIIRS flies over and we don't report from that pass = a scoring penalty, even if we detected it from Himawari 5 minutes later.

This document inventories every satellite that could observe fires over NSW during the competition, analyzes realistic data access paths and latencies, and recommends which sensors to implement and in what order.

**Bottom line:** We should aim to report detections from ~20-30 LEO overpasses per day across VIIRS, MODIS, Sentinel-3 SLSTR, and potentially Landsat. DEA Hotspots + FIRMS already cover most of these. The incremental effort is knowing *when* each overpass happens so we can match our reports to specific satellite passes.

---

## 1. The Scoring Model: Why Per-Overpass Matters

From the 2026-03-17 all-teams call:
- **1-minute detection is measured from satellite overpass**, not fire ignition
- Each overpass gets its own 1-minute clock
- XPRIZE will time ignitions to coincide with overpasses where possible
- Low confidence detections still count if correct

This means:
1. For every LEO pass over a fire, judges check: did the team detect and report it?
2. Reporting speed relative to the overpass matters (1-min and 10-min thresholds)
3. A fire we detect from Himawari at T+7 min does NOT satisfy the scoring for a VIIRS pass at T+0 unless we also report it from that VIIRS pass
4. We need to know the overpass schedule to (a) know when to expect data, (b) attribute our reports to specific overpasses, and (c) be ready to process data the moment it arrives

---

## 2. Complete Satellite Inventory for NSW Fire Detection (April 2026)

### 2.1 Geostationary Satellites (Continuous)

These are NOT per-overpass scored in the same way as LEO, but provide the continuous backbone.

| Satellite | Instrument | Operator | Position | Cadence | Effective Resolution (NSW) | Status Apr 2026 | Data Path |
|-----------|-----------|----------|----------|---------|---------------------------|-----------------|-----------|
| **Himawari-9** | AHI | JMA | 140.7E | 10 min | 3-4 km | OPERATIONAL | AWS NODD + SNS push, JAXA P-Tree |
| **GK-2A** | AMI | KMA | 128.2E | 10 min | 3-5 km | OPERATIONAL | AWS NODD (noaa-gk2a-pds) |
| **FY-4B** | AGRI | CMA | 123.5E | 15 min | 3-5 km | OPERATIONAL | NSMC (unreliable for NRT) |

**Scoring note:** If geostationary scans count as "overpasses," we have 144 Himawari scoring opportunities per day. Our custom Himawari pipeline handles these. GK-2A adds 144 more if we process it.

### 2.2 VIIRS Constellation (Highest Priority LEO)

| Satellite | NORAD ID | Orbit | LTAN | Approx NSW Day Pass (AEST) | Approx NSW Night Pass (AEST) | Data Path | Typical Latency |
|-----------|----------|-------|------|---------------------------|----------------------------|-----------|----------------|
| **NOAA-21** | 54234 | 834 km SSO | 13:30 | ~13:00-14:00 | ~01:00-02:00 | DEA Hotspots, FIRMS | DEA: ~17-20 min; FIRMS NRT: up to 3 hr |
| **S-NPP** | 37849 | 834 km SSO | 13:30 | ~13:30-14:30 | ~01:30-02:30 | DEA Hotspots, FIRMS | DEA: ~17-20 min; FIRMS NRT: up to 3 hr |
| **NOAA-20** | 43013 | 834 km SSO | 13:30 | ~14:00-15:00 | ~02:00-03:00 | DEA Hotspots, FIRMS | DEA: ~17-20 min; FIRMS NRT: up to 3 hr |

**Total: ~6 VIIRS passes/day over NSW (3 day + 3 night)**

These are our most important LEO scoring opportunities. 375 m resolution detects fires as small as ~100-500 m^2.

**Data access reality:**
- **DEA Hotspots** is the fastest path: ~17-20 min from overpass. GA processes VIIRS direct broadcast data received at Alice Springs.
- **FIRMS NRT** is the backup: up to 3 hours globally (NO RT or URT for Australia).
- **FIRMS URT** (50-second latency) is US/Canada only. NOT available for Australia.
- **AWS NODD JPSS** mirrors VIIRS data but with variable latency (depends on NOAA ground station contact).

**Can we go faster than 17 minutes?** Only via direct broadcast partnership with GA (email sent, probability 20-30%). Without that, 17 min is our floor for VIIRS data.

### 2.3 MODIS (Terra + Aqua)

| Satellite | NORAD ID | Orbit | LTAN/LTDN | Approx NSW Day Pass (AEST) | Approx NSW Night Pass (AEST) | Data Path | Typical Latency |
|-----------|----------|-------|-----------|---------------------------|----------------------------|-----------|----------------|
| **Terra** | 25994 | 705 km SSO | LTDN ~08:30-09:00 (drifted from 10:30) | ~09:00-10:00 | ~21:00-22:00 | FIRMS NRT | Up to 3 hr |
| **Aqua** | 27424 | 705 km SSO | LTAN 13:30 | ~13:30-14:30 | ~01:30-02:30 | FIRMS NRT | Up to 3 hr |

**Total: ~4 MODIS passes/day** (but Aqua nearly overlaps VIIRS timing)

**Key point:** Terra MODIS morning pass (~09:00 AEST) is UNIQUE. No other thermal fire sensor covers that time slot with a fire product via FIRMS. This is a scoring opportunity we get for free through FIRMS polling.

**Status concern:** Both Terra and Aqua have degrading orbits. Terra's crossing time has drifted to ~08:30-09:00. Science data collection planned through Feb 2027 (Terra) and Sep 2027 (Aqua). Both should be operational in April 2026 but with degraded quality.

### 2.4 Sentinel-3 SLSTR (Undervalued Opportunity)

| Satellite | NORAD ID | Orbit | LTDN | Approx NSW Day Pass (AEST) | Approx NSW Night Pass (AEST) | Data Path | Typical Latency |
|-----------|----------|-------|------|---------------------------|----------------------------|-----------|----------------|
| **Sentinel-3A** | 41335 | 814 km SSO | 10:00 | ~10:00-11:00 | ~22:00-23:00 | EUMETSAT NRT FRP | ~3 hr |
| **Sentinel-3B** | 43437 | 814 km SSO | 10:00 | ~10:00-11:00 (phase offset from 3A) | ~22:00-23:00 | EUMETSAT NRT FRP | ~3 hr |

**Total: ~2-4 SLSTR passes/day**

**Why this was previously dropped and why we should reconsider:**

We dropped Sentinel-3 SLSTR because of ~3-hour latency, saying it "adds nothing over DEA Hotspots at 17 min." This was wrong in the per-overpass scoring model. SLSTR passes over NSW at a **different time** than VIIRS (~10:00 vs ~13:30). If judges check the SLSTR overpass, the question is: did we report a fire from *that* pass? The fact that we detected it from DEA Hotspots 3 hours earlier from a VIIRS pass is irrelevant -- that was a different overpass.

**Data access:** EUMETSAT Data Store provides Sentinel-3 SLSTR NRT FRP product. Free with registration. ~3-hour latency. The FRP product provides fire location, FRP, and confidence.

**Recommendation:** Add SLSTR FRP polling as a low-effort data source. The NRT FRP product is pre-processed -- we just need to query and ingest it. ~3-hour latency is acceptable because the scoring clock starts at overpass, and 3 hours is within the daily reporting window.

**Important caveat:** 3-hour latency means we CANNOT meet the "1-minute from overpass" scoring criterion for SLSTR. But any detection counts for the "characterization within 10 minutes" and "daily report" scoring dimensions.

### 2.5 Landsat 8 + 9 (Rare but Very High Value)

| Satellite | NORAD ID | Orbit | LTDN | Repeat Cycle | Resolution | Data Path | Typical Latency |
|-----------|----------|-------|------|-------------|------------|-----------|----------------|
| **Landsat 8** | 39084 | 705 km SSO | ~10:12 | 16 days | 100 m TIR, 30 m SWIR | USGS L1 | 4-6 hr (L1 RT) |
| **Landsat 9** | 49260 | 705 km SSO | ~10:12 | 16 days (8-day offset from L8) | 100 m TIR, 30 m SWIR | USGS L1 | 4-6 hr (L1 RT) |

**During the 13-day competition, NSW will have 2-4 Landsat overpass dates.**

Approximate Landsat overpass dates for the competition period (must be verified with USGS acquisition calendar closer to the date):
- Landsat 9: ~Apr 11, Apr 19 (specific paths)
- Landsat 8: ~Apr 11-12, Apr 19-20 (different paths)

NSW requires WRS-2 paths 88-91 -- on any given Landsat overpass date, only one path (185 km swath) is imaged.

**Fire detection capability:** Landsat can detect fires as small as **a few square meters** -- orders of magnitude better than any other sensor. A 10 m^2 fire fills ~0.01% of a 100 m TIRS pixel but still produces a detectable thermal anomaly via sub-pixel analysis.

**Data access reality:**
- **FIRMS Landsat active fire (LFTA):** 30-minute latency from overpass, but currently **North America only**. No announcement of Australia expansion.
- **USGS Level-1 Real-Time scenes:** 4-6 hours after acquisition.
- **Custom Landsat fire processing:** Would require downloading L1 TIRS data and running our own fire detection algorithm. This is feasible but requires development time.

**Recommendation:** Pre-compute exact Landsat overpass dates/paths for NSW during the competition. On those dates, pull L1 data from USGS as fast as possible and run a simple thermal anomaly detection. Even at 4-6 hour latency, this counts for daily report scoring. The spatial resolution advantage (detecting ~1 m^2 fires) is enormous.

### 2.6 ECOSTRESS (ISS) -- Detailed Analysis

| Field | Detail |
|-------|--------|
| **Platform** | ISS (International Space Station) |
| **Instrument** | PHyTIR (Prototype Hyperspectral Infrared Imager Thermal Infrared Radiometer) |
| **Orbit** | 420 km, 51.6 deg inclination, non-sun-synchronous, ~92 min period |
| **Resolution** | 38 m (in-track) x 69 m (cross-track), temp sensitivity <= 0.1 K |
| **Spectral** | 5 thermal bands in 8-12.5 um range (TIR only, no MWIR/SWIR) |
| **Swath** | 384 km |
| **Coverage** | -53.6S to +53.6N latitude -- NSW (-28 to -37S) is covered |
| **Revisit** | 1-5 days, irregular (ISS orbit precesses with ~63-day nodal precession) |
| **Status Apr 2026** | OPERATIONAL. Approved through FY2026, potential extension to FY2029 pending 2026 Senior Review. |

#### Can ECOSTRESS detect 10 m^2 fires?

**Yes, in principle.** At 69 m resolution, a 10 m^2 fire fills ~0.2% of the pixel area. However:

- ECOSTRESS has **TIR bands only (8-12.5 um)**, not MWIR (3-4 um). Fire detection is far more effective in the MWIR because the Planck function peaks near 4 um for fire temperatures (600-1200 K), giving a much stronger fire-vs-background contrast.
- In the TIR (11 um), a 10 m^2 fire at 800 K occupying 0.2% of a 69 m pixel would raise the pixel-average brightness temperature by approximately 1-3 K above ambient, depending on background temperature. This is detectable given ECOSTRESS's 0.1 K thermal sensitivity.
- For comparison, VIIRS I4 (3.74 um, 375 m) sees that same fire at a smaller pixel fraction (~0.007%) but with much higher per-unit-area radiance contrast at MWIR wavelengths -- and has a validated fire product.
- **No validated fire product exists for ECOSTRESS.** Any fire detection would require a custom algorithm applied to L1B radiance or L2 LST data.

**Assessment:** ECOSTRESS *could* detect a 10 m^2 fire as a thermal anomaly, especially at night when the background is cold. But it would require custom processing and there is no operational fire product.

#### ISS orbit over NSW in April 2026

The ISS orbit precesses continuously. In a 13-day competition window:
- ISS will pass over NSW approximately **3-8 times** (varies with the precession phase)
- Overpass times shift by ~20 minutes earlier each day
- Passes can be at **any local time** (day or night) -- unlike sun-synchronous satellites
- Exact times cannot be predicted more than ~2 weeks in advance from TLEs

The 384 km swath means not every pass over NSW will image the competition fire locations. Some passes may be at extreme viewing angles. Realistic useful observation count: **2-5 during the 13-day competition.**

#### Data latency -- the fatal problem

| Product Level | Latency from Observation | Content |
|--------------|--------------------------|---------|
| L1B Radiance | ~4 hours | Raw calibrated radiance |
| L2 LST | ~1 day | Land surface temperature (requires atmo reanalysis) |
| L3/L4 ET, WUE | 3-5 days | Evapotranspiration (not relevant for fire) |

**There is no NRT ECOSTRESS product.** ECOSTRESS is not part of NASA LANCE. L1B radiance data becomes available approximately 4 hours after acquisition. L2 LST takes approximately 1 day because it depends on atmospheric reanalysis data.

Even L1B at 4 hours is usable for daily report scoring (reports due 20:00 AEST), but NOT for the 1-minute or 10-minute scoring criteria.

#### ECOSTRESS recommendation

| Factor | Assessment |
|--------|-----------|
| Fire detection capability | MODERATE-HIGH (69 m TIR, 0.1 K sensitivity, but no MWIR band) |
| Coverage of NSW | YES (within ISS inclination limits) |
| Expected passes during competition | 2-5 usable |
| Data latency | POOR (~4 hr for L1B, ~1 day for L2) |
| Fire product availability | NONE (custom algorithm required) |
| NRT data path | NONE |
| Implementation effort | HIGH (custom algorithm on unfamiliar data format) |
| Scoring value | LOW (2-5 passes at 4+ hr latency) |
| **Overall priority** | **LOW -- do not implement unless all higher-priority sensors are done** |

ECOSTRESS is a stretch goal. The 2-5 passes at 4-hour latency with no fire product and a custom algorithm requirement makes this poor ROI compared to Sentinel-3 SLSTR (2-4 passes/day with a pre-built fire product) or Landsat (similar resolution, better spectral bands for fire, pre-built algorithms).

**One exception:** If we pursue ECOSTRESS, the best use case is downloading L1B radiance on known overpass dates and running a simple brightness temperature anomaly detector. At 69 m resolution and 0.1 K sensitivity, even a crude threshold (pixel BT > ambient + 3K) would flag active fires. But this is only worth doing for 2-5 passes across 13 days.

### 2.7 Sentinel-2B + 2C (SWIR-only fire detection)

| Satellite | NORAD ID | Orbit | LTDN | Revisit | Resolution | Data Path | Latency |
|-----------|----------|-------|------|---------|------------|-----------|---------|
| **Sentinel-2B** | 42063 | 786 km SSO | 10:30 | 5 days combined | 20 m SWIR (B11, B12) | Copernicus Data Space | 100 min - 3 hr NRT |
| **Sentinel-2C** | TBD | 786 km SSO | 10:30 | 5 days combined | 20 m SWIR | Copernicus Data Space | 100 min - 3 hr NRT |

**Competition coverage:** 2-3 Sentinel-2 passes over any given NSW fire location during the 13-day window.

**Fire detection:** Sentinel-2 has NO thermal bands. Active fire detection relies on SWIR band saturation (fires > ~600 K saturate B12 at 2.19 um). This works for daytime detection of active flaming fires. It cannot detect smoldering fires or fires at night.

**Recommendation:** LOW priority. The 5-day revisit means 2-3 scoring opportunities total. SWIR fire detection requires custom processing. The 20 m resolution is excellent but the limited revisit and daytime-only constraint makes this marginal.

### 2.8 MetOp-B/C AVHRR

| Satellite | NORAD ID | Orbit | LTDN | Approx NSW Passes (AEST) | Resolution | Data Path | Latency |
|-----------|----------|-------|------|--------------------------|------------|-----------|---------|
| **MetOp-B** | 38771 | 817 km SSO | 09:30 | ~09:30-10:30, ~21:30-22:30 | 1.1 km | EUMETSAT Data Store | ~47 min avg |
| **MetOp-C** | 43689 | 817 km SSO | 09:30 | ~09:30-10:30 (offset from B) | 1.1 km | EUMETSAT Data Store | ~47 min avg |

**Total: ~4 AVHRR passes/day**

**Critical update (June 2025):** NOAA-19 AVHRR used in DEA Hotspots was discontinued from June 16, 2025. The AVHRR night-time layer in DEA Hotspots will no longer be available from NOAA-19. MetOp AVHRR is NOT currently ingested into DEA Hotspots for Australia. This means MetOp AVHRR fire detections require custom processing or a different data path.

**Data access:** EUMETSAT Data Store provides AVHRR data. The <1 hour timeliness data may require a fee; >1 hour data is free. No operational fire product from EUMETSAT.

**Recommendation:** LOW-MODERATE priority. 1.1 km resolution is comparable to MODIS. No operational fire product. Morning timing (~09:30 AEST) partially overlaps with the Terra MODIS window. Implementation effort is moderate (need custom fire detection on AVHRR). Defer unless critical morning gap needs filling.

### 2.9 FY-3D/E/F MERSI (Chinese LEO)

| Satellite | Instrument | LTDN | Resolution | Approx NSW Passes (AEST) |
|-----------|-----------|------|------------|--------------------------|
| **FY-3D** | MERSI-II | 14:00 | 250 m TIR | ~14:00-15:00, ~02:00-03:00 |
| **FY-3E** | MERSI-LL | 05:30 | 250 m | ~05:30-06:30, ~17:30-18:30 |
| **FY-3F** | MERSI | 10:00 | TBD | ~10:00-11:00, ~22:00-23:00 |

**Total: ~6 MERSI passes/day**

**250 m thermal resolution is the best of any operational polar-orbiting sensor.** Better than VIIRS (375 m). FY-3D has a validated global fire product with >94% accuracy.

**The problem is data access.** NSMC data center (satellite.nsmc.org.cn) may have latency, reliability, and language barriers for real-time international access. We cannot depend on this for a time-critical competition.

**Unique value of FY-3E:** The 05:30 LTDN fills the early morning gap (05:30-06:30 AEST) that no other sensor covers. If we could access FY-3E MERSI-LL data reliably, this would be a unique scoring opportunity.

**Recommendation:** LOW priority due to data access risk. Worth testing NSMC access before the competition -- if it works reliably, the 250 m resolution and unique timing make FY-3D/E very valuable. But do not make this load-bearing.

### 2.10 OroraTech (Commercial CubeSats)

| Field | Detail |
|-------|--------|
| **Constellation** | 8 OTC-P1 satellites (launched Mar 2025) + FOREST sats + 4 SAFIRE Gen4 payloads (launched Jan 2026) |
| **Resolution** | ~200-500 m estimated, detects 4x4 m fires |
| **Swath** | ~400 km |
| **Data** | Commercial platform, <10 min alert latency |
| **Status** | OPERATIONAL (commissioning ongoing for newer sats) |

**Assessment:** OroraTech is the only commercial thermal constellation likely to be fully operational by April 2026 with meaningful coverage. Their ~16+ operational satellites should provide multiple daily passes over NSW. The 4x4 m fire detection capability would be extremely valuable.

**Status:** Partnership email sent. If OroraTech provides data access, this becomes our highest-value supplementary source. Without partnership, this is inaccessible (commercial service, pricing not disclosed).

### 2.11 Other Sensors (Low/No Priority)

| Sensor | Why Low Priority |
|--------|-----------------|
| **ASTER TIR (Terra)** | DEAD. Permanently shut down January 2026. |
| **Meteor-M N2-3/N2-4** | Data access for international users is essentially inaccessible |
| **Sentinel-5P TROPOMI** | Smoke/aerosol tracking only, not fire detection. 5.5 km resolution. |
| **OMPS** | Coarse aerosol product only |
| **Sentinel-1 SAR** | Burn scar mapping, not active fire detection |
| **Planet Doves** | No thermal/SWIR bands |
| **WorldView-3** | Commercial, tasked imaging, extremely expensive |
| **TRISHNA** | Not launched yet |
| **LSTM/SBG-TIR** | Not launched yet |
| **FireSat (Muon/EFA)** | Probably not operational by April 2026 |

---

## 3. Overpass Schedule and Prediction

### 3.1 Why we need a precise overpass schedule

1. **Match reports to overpasses:** Judges score per-overpass. We need to tag each detection with the satellite pass it came from.
2. **Anticipate data arrival:** Knowing when a VIIRS pass occurs lets us start polling DEA Hotspots at exactly the right time (overpass + 17 min).
3. **Predict scoring windows:** If we know a Landsat pass is happening on April 11 at 10:15 AEST, we can have special processing ready.
4. **Gap awareness:** Know when we rely only on geostationary coverage and when LEO passes cluster.

### 3.2 How to build the overpass schedule

**Tools:**
- `pyorbital` (Python): SGP4 propagation from TLEs, computes rise/set/max elevation for any ground location
- `skyfield` (Python): Higher-accuracy satellite position computation
- CelesTrak TLE data: https://celestrak.org/NORAD/elements/ (free, updated daily)

**TLE groups to download:**
- `weather` -- VIIRS (S-NPP, NOAA-20, NOAA-21), MODIS (Terra, Aqua), MetOp-B/C
- `resource` -- Landsat 8/9, Sentinel-2B/2C, Sentinel-3A/3B
- `stations` -- ISS (for ECOSTRESS)

**Schedule computation:**
```
For each satellite in FIRE_SATELLITES:
    Download current TLE from CelesTrak
    Compute all passes over NSW center (-32.5, 151.0) for April 9-21, 2026
    Filter passes with max elevation > 5 degrees
    Record: rise_time, max_elevation_time, set_time, sensor, resolution
Sort all passes by time
Export as JSON for use in detection scheduler
```

A reference implementation exists in `context/domain_briefs/satellite-constellation-inventory/code_patterns.md`.

### 3.3 TLE refresh schedule

| When | Action |
|------|--------|
| 2 weeks before competition (Mar 26) | Initial TLE download, compute full schedule |
| 3 days before (Apr 6) | Refresh TLEs, recompute, compare to initial |
| Day before (Apr 8) | Final TLE refresh, lock in schedule for days 1-3 |
| Daily during competition | Refresh TLEs, update schedule for remaining days |

**ISS/ECOSTRESS note:** ISS orbit is actively maintained with periodic reboosts. TLE accuracy degrades faster than for passive satellites. Refresh ISS TLEs more frequently (every 1-2 days) if ECOSTRESS is being used.

### 3.4 Estimated daily overpass timeline (typical day, AEST)

```
TIME (AEST)  SENSOR              RESOLUTION  DATA PATH              LATENCY
-----------  ------------------  ----------  ---------------------  --------
00:00-24:00  Himawari-9 AHI      3-4 km      AWS NODD (custom)      7-15 min
00:00-24:00  GK-2A AMI           3-5 km      AWS NODD (custom)      7-15 min

~01:00       NOAA-21 VIIRS       375 m       DEA Hotspots           ~17 min
~01:30       S-NPP VIIRS         375 m       DEA Hotspots           ~17 min
~02:00       NOAA-20 VIIRS       375 m       DEA Hotspots           ~17 min
~02:00       FY-3D MERSI-II      250 m       NSMC (if accessible)   Hours
~02:00       Aqua MODIS          1 km        FIRMS NRT              Up to 3 hr

~05:30       FY-3E MERSI-LL      250 m       NSMC (if accessible)   Hours

~09:00       Terra MODIS         1 km        FIRMS NRT              Up to 3 hr
~09:30       MetOp-B/C AVHRR     1.1 km      EUMETSAT               ~47 min
~10:00       Sentinel-3A/B SLSTR 1 km        EUMETSAT NRT FRP       ~3 hr
~10:12       Landsat 8 or 9      100 m TIR   USGS L1 RT             4-6 hr
~10:30       Sentinel-2B/C       20 m SWIR   Copernicus NRT         100 min - 3 hr

~13:00       NOAA-21 VIIRS       375 m       DEA Hotspots           ~17 min
~13:30       S-NPP VIIRS         375 m       DEA Hotspots           ~17 min
~14:00       NOAA-20 VIIRS       375 m       DEA Hotspots           ~17 min
~14:00       FY-3D MERSI-II      250 m       NSMC (if accessible)   Hours
~14:00       Aqua MODIS          1 km        FIRMS NRT              Up to 3 hr

~17:30       FY-3E MERSI-LL      250 m       NSMC (if accessible)   Hours

~21:30       MetOp-B/C AVHRR     1.1 km      EUMETSAT               ~47 min
~22:00       Terra MODIS         1 km        FIRMS NRT              Up to 3 hr
~22:00       Sentinel-3A/B SLSTR 1 km        EUMETSAT NRT FRP       ~3 hr

VARIABLE     ECOSTRESS (ISS)     69 m TIR    LP DAAC                ~4 hr
RARE         Landsat 8/9         100 m TIR   USGS                   4-6 hr
```

---

## 4. End-to-End Latency Analysis

For each sensor, the full chain is: observation -> downlink -> processing -> data_available -> our_download -> our_processing -> report

### 4.1 Sensors accessible within scoring windows

| Sensor | Observation to Data Available | Our Processing | Total Latency | Meets 1-min? | Meets 10-min? | Meets Daily? |
|--------|-------------------------------|---------------|---------------|-------------|--------------|-------------|
| Himawari-9 (custom) | 7-15 min | 3-5 sec | **7-15 min** | NO | SOMETIMES | YES |
| VIIRS via DEA Hotspots | ~17-20 min | <30 sec | **17-20 min** | NO | NO | YES |
| VIIRS via FIRMS NRT | Up to 3 hr | <30 sec | **Up to 3 hr** | NO | NO | YES |
| MODIS via FIRMS NRT | Up to 3 hr | <30 sec | **Up to 3 hr** | NO | NO | YES |
| GK-2A (custom) | ~7-15 min | 3-5 sec | **7-15 min** | NO | SOMETIMES | YES |
| Sentinel-3 SLSTR FRP | ~3 hr | <30 sec | **~3 hr** | NO | NO | YES |
| Landsat (custom L1) | 4-6 hr | ~1-5 min | **4-6 hr** | NO | NO | YES |
| ECOSTRESS (L1B) | ~4 hr | ~1-5 min | **~4 hr** | NO | NO | YES |
| Sentinel-2 (NRT) | 100 min - 3 hr | ~1-5 min | **2-4 hr** | NO | NO | YES |
| MetOp AVHRR | ~47 min | ~1-2 min | **~50 min** | NO | NO | YES |

**Key finding:** No sensor meets the 1-minute criterion from our data access paths. Only Himawari and GK-2A sometimes meet 10 minutes. Everything contributes to daily reports.

### 4.2 Fastest achievable latency per sensor

| Sensor | Fastest Possible Path | Latency | Requires |
|--------|----------------------|---------|----------|
| Himawari-9 | AWS NODD SNS push + custom processing | ~7 min | Our custom pipeline (building) |
| VIIRS | GA direct broadcast | ~5-10 min | Partnership with GA (uncertain) |
| VIIRS | DEA Hotspots polling | ~17 min | Nothing (already building) |
| GK-2A | AWS NODD polling + custom processing | ~7-15 min | Same algorithm as Himawari (Week 2) |
| MODIS | FIRMS RT | ~30 min (if available for AU) | FIRMS access (have) |
| Sentinel-3 SLSTR | EUMETSAT NRT FRP | ~3 hr | EUMETSAT registration |
| Landsat | Custom L1 processing | ~4-6 hr | USGS account + custom algorithm |

---

## 5. Priority Ranking: What to Implement and When

### Tier 1: Already Building / Zero Additional Effort (Week 1)

These are already in our pipeline via DEA Hotspots + FIRMS polling:

| Source | Sensors Covered | Implementation |
|--------|----------------|----------------|
| DEA Hotspots WFS | VIIRS (S-NPP, NOAA-20, NOAA-21), Himawari | Poll every 5 min (already building) |
| FIRMS API | VIIRS NRT, MODIS NRT, Himawari NRT | Poll every 5 min (already building) |
| Himawari-9 custom | AHI B07/B14 | AWS NODD SNS pipeline (building) |

**Scoring coverage: ~6 VIIRS + ~4 MODIS + 144 Himawari = ~154 overpass-level observations/day**

### Tier 2: Low Effort, Real Scoring Value (Week 2)

| Source | Sensors Covered | Effort | Scoring Value |
|--------|----------------|--------|---------------|
| **GK-2A custom processing** | GK-2A AMI | Low (same algorithm as Himawari) | +144 geo observations/day |
| **Overpass schedule computation** | All LEO | Low (Python script, ~1 day) | Enables per-overpass reporting |
| **Sentinel-3 SLSTR FRP polling** | Sentinel-3A, 3B | Low (EUMETSAT API query) | +2-4 LEO passes/day at unique times |
| **FIRMS Himawari NRT** | Himawari-9 | Zero (already in FIRMS poll) | Backup for custom pipeline |

### Tier 3: Moderate Effort, Moderate Value (Week 2-3)

| Source | Sensors Covered | Effort | Scoring Value |
|--------|----------------|--------|---------------|
| **Landsat overpass pre-computation** | Landsat 8, 9 | Low (compute dates) | Know when to expect data |
| **Landsat L1 custom fire detection** | Landsat 8, 9 TIRS | Moderate (L1 download + thermal anomaly algorithm) | 2-4 passes total, but detects m^2 fires |
| **Sentinel-2 SWIR fire detection** | Sentinel-2B, 2C | Moderate (download + SWIR threshold) | 2-3 passes total, 20 m daytime only |

### Tier 4: High Effort / Uncertain Value (Week 3+ / Stretch)

| Source | Sensors Covered | Effort | Scoring Value |
|--------|----------------|--------|---------------|
| **ECOSTRESS custom fire detection** | ECOSTRESS PHyTIR | High (custom algorithm, unfamiliar format) | 2-5 passes at 4+ hr latency |
| **FY-3D MERSI fire product** | FY-3D MERSI-II | Moderate (NSMC access + integration) | 2-4 passes/day at 250 m IF data works |
| **MetOp AVHRR fire detection** | MetOp-B, C | Moderate (custom algorithm on AVHRR) | 4 passes/day at 1.1 km |
| **OroraTech partnership** | OroraTech fleet | Zero (if partnership) / Impossible (if not) | Multiple daily passes at ~200-500 m |

### Tier 5: Do Not Implement

| Source | Why |
|--------|-----|
| Meteor-M MSU-MR | Data inaccessible internationally |
| FY-4B AGRI | Data access unreliable |
| ASTER TIR | Dead |
| Sentinel-1 SAR | Not active fire detection |
| Planet Doves | No thermal/SWIR |
| TRISHNA, LSTM, SBG-TIR | Not launched |

---

## 6. Specific Recommendations

### 6.1 Build an overpass schedule (Priority: HIGH, Effort: LOW)

This is the single highest-ROI action item from this analysis. Write a Python script that:
1. Downloads fresh TLEs from CelesTrak for all fire-relevant satellites
2. Computes all passes over NSW for the competition window (April 9-21)
3. Outputs a JSON schedule with: satellite, sensor, rise/max/set times (UTC and AEST), max elevation
4. Tags each overpass with expected data latency and data source

Use this schedule to:
- Know exactly when to start polling DEA Hotspots after each VIIRS pass
- Know when Landsat and Sentinel-2 passes occur (rare but high-value)
- Attribute our fire reports to specific satellite overpasses in daily reports
- Display upcoming passes in the judge portal

### 6.2 Add Sentinel-3 SLSTR FRP (Priority: MODERATE, Effort: LOW)

Poll EUMETSAT Data Store for Sentinel-3 SLSTR NRT FRP products over NSW. This gives us 2-4 extra scoring opportunities per day at a time (~10:00, ~22:00 AEST) not covered by VIIRS.

Implementation:
1. Register at EUMETSAT Data Store (if not done via Copernicus CDSE)
2. Query the NRT FRP product API every 30 min
3. Parse fire detections (location, FRP, confidence)
4. Feed into event store as SLSTR-sourced detections

### 6.3 Pre-compute Landsat passes (Priority: MODERATE, Effort: LOW)

Determine exact Landsat 8/9 overpass dates and WRS-2 paths that cover the competition area during April 9-21. On those dates:
1. Monitor USGS for L1 Real-Time scene availability
2. Download TIRS data as soon as available (4-6 hr)
3. Run thermal anomaly detection (bright pixel > background + threshold)
4. Report any fires found -- at 100 m resolution, this detects fires invisible to every other sensor except ECOSTRESS

### 6.4 ECOSTRESS: Deprioritize (Priority: LOW)

ECOSTRESS is not worth the implementation effort given:
- Only 2-5 usable passes in 13 days
- ~4-hour data latency (L1B)
- No fire product (requires custom algorithm development)
- TIR-only bands (no MWIR for optimal fire contrast)
- Unfamiliar HDF5 data format

If all Tier 1-3 sensors are implemented and working, AND there is spare time, consider a minimal ECOSTRESS implementation: download L1B on known ISS overpass dates, apply a simple BT anomaly threshold, report anything flagged. But this is the last thing to build.

### 6.5 Explore faster DEA Hotspots access (Priority: HIGH, Effort: ZERO)

Follow up on the GA partnership email (sent March 18). If GA can provide:
- Priority API access with lower latency
- Direct broadcast VIIRS data feed
- Faster processing for the competition window

This could cut VIIRS latency from ~17 min to ~5-10 min, potentially meeting the 10-minute scoring criterion.

### 6.6 Daily report optimization

Include in daily reports:
- Every detected fire, with attribution to specific satellite overpasses
- For each overpass that covered a fire: which satellite, what time, what we detected
- Pre-computed overpass schedule as supporting documentation
- This shows judges we are tracking EVERY sensor pass, not just our primary sources

---

## 7. Gap Analysis: What We Cannot Cover

| Gap | Description | Mitigation |
|-----|-------------|-----------|
| **1-minute criterion** | No sensor data reaches us within 1 minute of overpass | Only possible with direct broadcast (GA partnership) or commercial data (OroraTech). Unlikely to achieve. |
| **10-minute criterion for LEO** | DEA Hotspots at 17 min is too slow | GA partnership is the only path. Himawari sometimes meets 10 min but is geostationary. |
| **Small fires (< 100 m^2) between VIIRS passes** | Himawari cannot see fires < ~1000 m^2 | Only Landsat (rare), ECOSTRESS (rare), or OroraTech (commercial) can fill this gap. Accept this limitation. |
| **Morning 06:00-09:00 AEST** | No LEO thermal fire product in this window | FY-3E MERSI-LL (if accessible) or MetOp AVHRR (requires custom processing). Himawari covers this continuously. |
| **Cloud-covered fires** | All optical/thermal sensors are blocked | Cannot mitigate. Same constraint for all teams. SAR could theoretically help but not for active fire detection. |
| **ECOSTRESS-specific passes** | If judges score ECOSTRESS overpasses and we don't detect from them | ECOSTRESS passes are rare and data latency is high. Accept this as a minor scoring loss. |

---

## 8. Implementation Checklist

### Before Competition (March 19 - April 8)

- [ ] Build overpass prediction script using pyorbital + CelesTrak TLEs
- [ ] Compute preliminary overpass schedule for April 9-21
- [ ] Pre-compute Landsat 8/9 pass dates and WRS-2 paths for NSW
- [ ] Register at EUMETSAT Data Store for Sentinel-3 SLSTR FRP access
- [ ] Test EUMETSAT NRT FRP API access and parse fire detection format
- [ ] Test NSMC data access for FY-3D (assess reliability, do not depend on it)
- [ ] Follow up on GA partnership email
- [ ] Follow up on OroraTech partnership email

### Competition Week 1 (April 9-15)

- [ ] Refresh TLEs on April 8, compute final overpass schedule
- [ ] Deploy overpass-aware polling: start DEA Hotspots checks at overpass + 15 min
- [ ] Begin Sentinel-3 SLSTR FRP polling (every 30 min)
- [ ] Daily TLE refresh, update schedule
- [ ] On Landsat overpass dates: monitor for L1 data, run fire detection

### Competition Week 2 (April 16-21)

- [ ] Continue all Week 1 operations
- [ ] If capacity permits: attempt ECOSTRESS L1B download on ISS pass dates
- [ ] Fine-tune per-overpass reporting in daily reports
- [ ] If OroraTech partnership materialized: integrate their alert feed

---

## 9. Summary: Expected Scoring Opportunities Per Day

| Source | Passes/Day | Resolution | Latency | Priority |
|--------|-----------|------------|---------|----------|
| Himawari-9 (custom) | 144 | 3-4 km | 7-15 min | CORE (building) |
| VIIRS via DEA Hotspots | ~6 | 375 m | ~17-20 min | CORE (building) |
| MODIS via FIRMS | ~4 | 1 km | Up to 3 hr | CORE (building) |
| GK-2A (custom) | 144 | 3-5 km | 7-15 min | TIER 2 (Week 2) |
| Sentinel-3 SLSTR FRP | 2-4 | 1 km | ~3 hr | TIER 2 (add) |
| Landsat 8/9 | 0.15-0.3 avg | 100 m | 4-6 hr | TIER 3 (on pass dates) |
| Sentinel-2 | 0.15-0.2 avg | 20 m SWIR | 2-4 hr | TIER 3 (on pass dates) |
| ECOSTRESS | 0.15-0.4 avg | 69 m | ~4 hr | TIER 4 (stretch) |
| OroraTech | Variable | ~200-500 m | <10 min | TIER 4 (needs partnership) |

**Total addressable scoring opportunities: ~300+ per day** (mostly geostationary), with **~12-18 LEO overpass scoring opportunities per day** from sensors we can realistically access.

**Our realistic coverage with Tier 1+2 implementation: Himawari (continuous) + ~6 VIIRS + ~4 MODIS + ~2-4 SLSTR + GK-2A (continuous) = comprehensive coverage of all major scoring windows.**
