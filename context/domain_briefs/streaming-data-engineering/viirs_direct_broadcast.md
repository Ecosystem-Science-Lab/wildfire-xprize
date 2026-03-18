# VIIRS Direct Broadcast for Near-Real-Time Fire Detection in Australia

## Overview

VIIRS (Visible Infrared Imaging Radiometer Suite) direct broadcast (DB) is the fastest pathway to get polar-orbiting fire detections — potentially under 60 seconds from observation to alert when processed locally, versus 3-6 hours through standard NASA pipelines. For our XPRIZE competition in NSW, partnering with an existing Australian ground station to receive VIIRS DB data is the highest-impact move for Tier 2 confirmation.

---

## 1. How VIIRS Direct Broadcast Works

### The Signal

VIIRS instruments fly on three sun-synchronous polar orbiters:
- **Suomi NPP** (launched 2011)
- **NOAA-20** (launched 2017)
- **NOAA-21** (launched 2022)

All three cross the equator at ~13:30 local solar time (ascending/daytime) and ~01:30 (descending/nighttime). They are spaced roughly equally in orbit, providing ~6 VIIRS overpasses per day for any given location (3 day, 3 night).

### X-Band Downlink Specifications

| Parameter | Value |
|---|---|
| Frequency | 7812.0 MHz (+/- 0.03 MHz) |
| Band | X-band (7750-7850 MHz) |
| Modulation | QPSK (Quadrature Phase Shift Keying) |
| Data rate | 15 Mbps (SNPP/NOAA-20), 20-25 Mbps (NOAA-21+) |
| Encoding | Convolutional + Reed-Solomon FEC |
| Stream name | HRD (High Rate Data) |
| Bandwidth | ~30 MHz occupied |
| Content | All 5 instruments: VIIRS, ATMS, CrIS, OMPS, CERES |

### Key Concept: Continuous Broadcast

Unlike store-and-forward systems, JPSS satellites **continuously broadcast** HRD data as they orbit. Any ground station within line-of-sight (elevation >5 degrees above horizon) can receive the full data stream in real time. This is a "listen and capture" model — no tasking, no scheduling, no authorization needed. The data is unencrypted and freely available.

A single overpass provides ~10-12 minutes of data reception per pass (depending on maximum elevation angle), covering a swath of ~3,000 km width.

### Ground Station Antenna Requirements

| Parameter | Specification |
|---|---|
| Minimum dish diameter | 1.2m (marginal), 2.0-2.4m (recommended) |
| Tracking | Full 2-axis tracking required (Az/El or X/Y) |
| Tracking accuracy | <0.5 degrees for 1.2m dish, relaxed for larger |
| LNA noise figure | <1.5 dB |
| LNA gain | >20 dB |
| System G/T | Sufficient for 15-25 Mbps at X-band |
| Elevation limit | >5 degrees above local horizon |

**Cost estimates for a new station:**
- Complete turnkey X/S-band antenna system: EUR 400,000-500,000
- Ongoing maintenance: ~EUR 7,000/month
- LNA/downconverter equipment: $150-$480 per component
- Processing server: $5,000-$15,000

Building our own station is not practical for the competition timeline. Partnering with an existing station is the way.

---

## 2. Australian VIIRS Direct Broadcast Ground Stations

### 2a. Geoscience Australia — Alice Springs (PRIMARY TARGET)

**Status:** Operational. Already processes VIIRS for DEA Hotspots.

**Facility:** Data Acquisition Facility (DAF), Alice Springs, NT
- Two 9m antennas (ViaSat and Datron models)
- One 3m antenna (Orbital Systems)
- One 2.4m antenna (ESS)
- X-band capable

**What they receive:** Suomi NPP, NOAA-20, NOAA-21, Aqua (MODIS), Terra, Landsat, Sentinel, and others.

**Processing:** Raw telemetry received at Alice Springs is transferred to GA's Data Processing Facility (DPF) in Canberra via fibre optic link. VIIRS data is processed to Raw Data Record (RDR) and then through the fire detection pipeline for DEA Hotspots.

**Latency:** DEA Hotspots quotes "at best, 17 minutes old" from satellite overpass to published hotspot. The full procedure from satellite imaging to hotspot mapping typically takes ~20 minutes. This includes:
- Antenna acquisition + data downlink: ~10-12 min per pass
- Transfer to Canberra via fibre: seconds
- Processing (RDR -> SDR -> fire product): several minutes
- Web service update: minutes

**DEA Hotspots data access:**
- WMS: available
- WFS: available
- KML/GeoJSON: last 3 days
- AWS file access: hotspots.dea.ga.gov.au/files
- Secure portal for emergency managers: hotspots.dea.ga.gov.au/login

**Contact:** earth.observation@ga.gov.au

**Partnership angle:** GA already provides DEA Hotspots as a national bushfire service. The ~17-minute latency is already good but the data goes through Canberra first. A partnership could involve:
1. Getting real-time feed of VIIRS RDR/SDR data from Alice Springs directly (bypassing Canberra DPF)
2. Running our own CSPP fire algorithm on their raw data stream
3. Accessing DEA Hotspots via API with priority/low-latency access
4. Co-locating a processing server at the Alice Springs DAF

### 2b. Bureau of Meteorology — Darwin (Shoal Bay) and Melbourne

**Status:** Operational. Receives polar-orbiting satellite data but focused on meteorological products (NWP, SST), not fire detection.

**Darwin (Shoal Bay):** Three satellite receiving antenna systems installed October 2015 by Av-Comm. Receives data from NOAA polar orbiters, Feng Yun-2 geostationary, and others. L-band and X-band capable.

**Melbourne:** BoM's Satellite Remote Sensing facility. Part of the IMOS SST Sub-Facility. Processes HRPT/VIIRS data for sea surface temperature products. Led by Helen Beggs and colleagues.

**Other BoM stations:** Crib Point (VIC), Learmonth (WA), Casey and Davis (Antarctica) — all with Orbital Systems 2.4m antennas for polar-orbiting reception.

**AP-RARS/DBNet:** BoM participates in the WMO Direct Broadcast Network for Asia-Pacific. Data from BoM HRPT stations is redistributed in near-real-time via GTS to NWP centres globally.

**Contact:** satellites@bom.gov.au (Satellite Operations group, AP-RARS/DBNet)

**Partnership angle:** BoM has the antenna infrastructure but their processing chains are optimized for meteorological products. A partnership would likely involve:
1. Receiving raw VIIRS data stream from their antennas
2. Running our own fire detection processing on it
3. Leveraging their Melbourne or Darwin stations for NSW overpasses
4. Challenge: BoM may be less receptive to non-meteorological research uses

### 2c. WASTAC / Landgate — Perth (Murdoch University)

**Status:** Operational. L-band and X-band receiver at Murdoch University (moved from original Curtin University location).

**Operator:** Western Australian Satellite Technology and Applications Consortium (WASTAC) members include Landgate, CSIRO, BoM, Curtin University, Murdoch University.

**Capabilities:** Near-real-time "quick-look" archive of VIIRS, MODIS, and AVHRR data. Archive coverage: 1983 (AVHRR), 2001 (MODIS), 2012 (VIIRS).

**Fire products:** Landgate operates MyFireWatch (myfirewatch.landgate.wa.gov.au) and FireWatch Pro — operational bushfire early-warning tools for Western Australia.

**Contact:** Professor Mervyn Lynch, Department of Imaging and Applied Physics, Curtin University (key VIIRS contact for WASTAC).

**Partnership angle:** WASTAC has deep VIIRS DB experience and fire detection focus, but Perth is on the wrong side of the continent for NSW coverage. A VIIRS pass visible from Perth will generally not cover NSW, and vice versa. Useful as a technical advisor / software partner rather than a data source for NSW.

### 2d. CfAT / Viasat Real-Time Earth — Alice Springs

**Status:** Operational (since July 2020). Commercial Ground-Station-as-a-Service.

**Facility:** CfAT Space Precinct, Alice Springs (23.76S, 133.88E)
- Two 7.3m full-motion antennas
- L/S/X/Ka-band capable
- Aboriginal-owned facility (CfAT Satellite Enterprises Pty Ltd)
- Financed by Indigenous Business Australia (IBA)
- 250+ cloud-free days per year, clear 5-degree horizon

**Operator:** CfAT Satellite Enterprises (Indigenous not-for-profit) with Viasat managing operations as part of their global Real-Time Earth network.

**Services:** Pay-per-use GSaaS model. Supports LEO, MEO, and GEO satellite downlink. Already serves CSIRO's NovaSAR-1 facility.

**Viasat RTE global network:** 10 stations on 5 continents (Accra, Alice Springs, Cordoba, Fairbanks, Guildford UK, Hokkaido, Pretoria, Pendergrass GA USA, Pitea Sweden, Ushuaia).

**Contact:**
- Viasat RTE sales: RTEservices@viasat.com
- CfAT: https://www.cfat.org.au/cfat-se

**Partnership angle:** This is the commercial option. Could potentially:
1. Contract Viasat RTE to downlink JPSS/VIIRS passes over Australia
2. Receive raw X-band data via their infrastructure
3. Process with our own CSPP pipeline
4. Pay-per-pass pricing model (cost unknown, must request quote)
5. Their Alice Springs location gives central Australian coverage — good for NSW

### 2e. CSIRO — Hobart

**Status:** Historical HRPT reception. Now primarily data processing partner via IMOS.

**Role:** CSIRO operates the NovaSAR-1 national facility (using CfAT/Viasat Alice Springs for downlink). Hobart-based remote sensing team is a key partner in IMOS satellite SST processing.

**Partnership angle:** CSIRO has deep remote sensing processing expertise but limited direct reception for VIIRS. Better as a technical/algorithmic partner.

---

## 3. The CSPP Processing Pipeline

### What is CSPP?

The Community Satellite Processing Package (CSPP) is a free, open-source software suite from the University of Wisconsin-Madison (CIMSS/SSEC), funded by the JPSS program. It converts raw direct broadcast telemetry into science-ready products, including active fire detections.

### Processing Chain: Antenna to Fire Detections

```
Raw X-band signal from antenna
        |
        v
[Demodulator/Front-end] -- hardware, produces CADU frames
        |
        v
[RT-STPS] -- Real-Time Software Telemetry Processing System
    Input: Raw telemetry (CADU frames)
    Output: Level 0 Raw Data Records (RDR) in HDF5
    Supports: All JPSS missions and sensors
        |
        v
[CSPP SDR v4.0] -- Calibration & Geolocation
    Input: RDR files
    Output: Sensor Data Records (SDR) in HDF5
        - Calibrated radiances/reflectances
        - Geolocation (lat/lon per pixel)
        - Terrain-corrected geolocation
    Requires: Ancillary data (predictive ephemeris, etc.)
        |
        v
[CSPP VIIRS Active Fire v2.1] -- Fire Detection Algorithm
    Input: SDR files (I-band and M-band)
    Output:
        - NetCDF4 fire mask (confidence, lat/lon, BT, FRP)
        - ASCII text file (one line per fire pixel)
    Algorithms:
        - I-band (375m): NESDIS/STAR version
        - M-band (750m): NDE operational version
        |
        v
[CSPP Polar2Grid v3.0] -- Visualization (optional)
    Input: SDR or EDR files
    Output: GeoTIFF imagery, reprojected maps
    Use: Create false-color fire images, burn scar maps
```

### System Requirements

**CSPP SDR v4.0 (the heavy lifter):**

| Resource | Minimum | Production (continuous ops) |
|---|---|---|
| CPU | 64-bit Intel/AMD, 8 cores | 64 cores |
| RAM | 32 GB + 4 GB per processing core | 256 GB |
| Disk | 100 GB | 8 TB |
| OS | CentOS 7.9 or Rocky Linux 8.7+ | Rocky Linux 8 |
| Network | Internet for ancillary data | Dedicated connection |

**CSPP VIIRS Active Fire v2.1 (lighter):**

| Resource | Requirement |
|---|---|
| CPU | 64-bit Intel or AMD |
| RAM | 16 GB |
| Disk | 6 GB + data storage |
| OS | Rocky Linux 8 (tested on CentOS 7.9) |

**RT-STPS v7.0:**
- Linux 64-bit
- Minimal compute requirements (primarily I/O bound)
- Available from NOAA Field Terminal Support (distributed via CSPP)

### Processing Time Benchmarks

**CSPP SDR (7 granules / 10 minutes of VIIRS data):**
- 1 CPU core: 11.6 minutes
- 2 CPU cores: 6.8 minutes
- 4 CPU cores: 4.0 minutes
- 8 CPU cores: 3.3 minutes

**Full chain (raw data to fire product):**
- Published benchmark: ~36 minutes total (from raw telemetry through RDR, SDR, to fire product) — this is on modest hardware with standard configuration
- Optimized/production: 5-15 minutes end-to-end is achievable with good hardware and pipeline parallelism
- SSEC URT system: <60 seconds (but uses micro-granule processing during overpass, not post-pass batch)

### Software Access

All CSPP software is **free and open source** (GPL v3 for scripts, binary executables included):
- Download: https://cimss.ssec.wisc.edu/cspp/download/
- CSPP SDR v4.0: https://cimss.ssec.wisc.edu/cspp/jpss_sdr_v4.0.shtml
- CSPP VIIRS Active Fire v2.1: https://cimss.ssec.wisc.edu/cspp/viirs_fire_v2.1.shtml
- RT-STPS v7.0: https://cimss.ssec.wisc.edu/cspp/rt_stps_v7.0_patch1.shtml
- Polar2Grid v3.0: https://cimss.ssec.wisc.edu/cspp/polar2grid_v3.0.shtml
- Docker container: https://github.com/cynici/cspp

---

## 4. Latency Analysis: What's Actually Achievable?

### Latency Tiers

| Approach | Latency (overpass to fire detection) | Notes |
|---|---|---|
| **Ultra Real-Time (SSEC/FIRMS URT)** | 25-50 seconds | Micro-granule processing during overpass. Currently US-only (SSEC antenna network). |
| **Local DB processing (optimized)** | 5-15 minutes | Process complete pass locally with CSPP. Requires antenna + server co-location. |
| **DEA Hotspots (GA Alice Springs)** | 17-20 minutes | Operational Australian system. Data goes Alice Springs -> Canberra -> web. |
| **NASA LANCE/FIRMS NRT** | 60-120 minutes | Global product via Svalbard/McMurdo downlink + central processing. |
| **NASA FIRMS standard** | 3-6 hours | Full science processing pipeline. |

### The Ultra Real-Time Approach (SSEC Model)

The University of Wisconsin SSEC system achieves <60-second latency by:
1. Streaming DB data from multiple antennas to a central server in real-time
2. Processing "micro-granules" (tiny chunks of data) as they arrive — not waiting for the full pass
3. Running Level 0 -> Level 1 -> fire detection on each micro-granule immediately
4. Using the same fire algorithm code as LANCE

**MODIS detections:** ~25 seconds latency
**VIIRS detections:** ~50 seconds latency

This system currently only covers CONUS + Hawaii + Puerto Rico using SSEC's existing DB antenna network. **It does not cover Australia.** But the architecture could be replicated with an Australian antenna partner.

### Our Target: Replicating URT in Australia

If we partner with an Australian DB station (GA Alice Springs or CfAT/Viasat), we could potentially achieve:
- **5-15 minutes** with standard CSPP batch processing after full pass
- **1-3 minutes** with micro-granule streaming (requires custom integration with the antenna front-end)
- **<60 seconds** only if we can get raw CADU frame streaming in real-time (requires deep antenna integration)

The 5-15 minute tier is realistic for the competition timeline. Sub-minute requires significant custom engineering.

---

## 5. Partnership Strategy

### Option A: Geoscience Australia DEA Hotspots (Lowest Effort)

**What:** Get API access to DEA Hotspots and consume their VIIRS fire detections.

**Latency:** ~17-20 minutes from overpass.

**Effort:** Minimal. Fill in access request form. Contact earth.observation@ga.gov.au.

**Pros:** Already operational, covers all of Australia, uses VIIRS + MODIS + Himawari-9, free.

**Cons:** 17-20 min latency is slower than our target. No control over processing. Dependent on their pipeline. Not clear if they expose detection coordinates before web publication.

**Action items:**
1. Email earth.observation@ga.gov.au requesting API access and documentation
2. Ask about WFS endpoint for programmatic access to raw hotspot coordinates
3. Ask about latency for API vs. web interface
4. Ask if they can expose VIIRS SDR or fire products directly (before their pipeline)

### Option B: GA Alice Springs Raw Data Feed (Medium Effort)

**What:** Partner with GA to receive raw VIIRS data (RDR or SDR level) directly from their Alice Springs DAF, bypassing the Canberra DPF pipeline. Run our own CSPP fire processing.

**Latency:** 5-15 minutes from overpass.

**Effort:** Moderate. Requires formal partnership agreement with GA. Need to deploy processing server (could be co-located at Alice Springs or receive data via network).

**Pros:** Control over processing. Can optimize for fire detection latency. Full resolution data access.

**Cons:** Requires GA cooperation. May need to navigate government procurement/agreement processes. Need server infrastructure.

**Action items:**
1. Contact earth.observation@ga.gov.au with a partnership proposal
2. Frame as supporting national bushfire capability (aligns with their mission)
3. Propose a research collaboration through NAU (university-to-government agency)
4. Ask ANGSTT (angstt.gov.au/contact-us) to help facilitate
5. Investigate if GA would allow co-location of a processing server at Alice Springs DAF

### Option C: CfAT/Viasat Commercial GSaaS (Medium Effort, Higher Cost)

**What:** Contract CfAT/Viasat Real-Time Earth to downlink JPSS VIIRS passes over Australia and deliver raw data to us.

**Latency:** 5-15 minutes from overpass (antenna to our processing).

**Effort:** Moderate. Commercial contract. Need our own CSPP processing infrastructure.

**Pros:** Commercial reliability. Pay-per-use model. Professional antenna operations. No government bureaucracy.

**Cons:** Cost unknown (must request quote). Still need our own processing. Alice Springs location is good but ~1,700 km from NSW.

**Action items:**
1. Email RTEservices@viasat.com requesting quote for JPSS/VIIRS pass downlinks
2. Specify: Suomi NPP, NOAA-20, NOAA-21 passes visible from Alice Springs
3. Ask about data delivery options (raw CADU frames, RDR, real-time streaming)
4. Ask about CfAT's community/research pricing vs. commercial rates
5. Also contact CfAT directly: https://www.cfat.org.au/cfat-se

### Option D: BoM Satellite Operations (Hard, Uncertain)

**What:** Partner with BoM to receive VIIRS data from their Darwin or Melbourne stations.

**Latency:** 5-15 minutes with own processing.

**Effort:** High. BoM is a government agency focused on weather services. Fire detection is outside their core mission.

**Contact:** satellites@bom.gov.au

**Pros:** Melbourne station may see more NSW overpasses than Alice Springs.

**Cons:** BoM may not be receptive. Their data sharing is primarily through WMO mechanisms. Would need bilateral agreement.

### Option E: Build/Deploy Own Antenna (Highest Effort, Not Recommended)

**What:** Deploy a 2.4m X-band tracking antenna somewhere in eastern Australia.

**Cost:** EUR 400,000-500,000 for turnkey system + processing server + ongoing maintenance.

**Latency:** Could achieve sub-minute with real-time streaming and micro-granule processing.

**Effort:** Extreme. 6-12 months minimum to procure, deploy, commission.

**Verdict:** Not feasible for April 2026 competition timeline unless we find a university partner who already has the hardware.

### Recommended Strategy

1. **Immediately:** Apply for DEA Hotspots API access (Option A). This is our baseline Tier 2 data source.
2. **This month:** Contact GA about raw data feed partnership (Option B). Frame as bushfire safety research through NAU.
3. **In parallel:** Request Viasat RTE pricing (Option C) as a commercial backup.
4. **Stretch goal:** If GA partnership works, deploy optimized CSPP pipeline on co-located or networked server to get to 5-10 minute latency.

---

## 6. Reference: VIIRS Passes Over NSW

### Orbital Parameters
- Orbit altitude: ~824 km
- Orbit period: ~101 minutes
- Inclination: 98.7 degrees (sun-synchronous)
- Swath width: ~3,000 km
- Equator crossing: 13:30 local ascending (day), 01:30 descending (night)

### NSW Coverage from Alice Springs

Alice Springs (23.7S, 133.9E) can see satellites above 5 degrees elevation out to ~2,800 km radius. Sydney is ~2,100 km from Alice Springs. This means:

- **Most** VIIRS passes that cover NSW will be visible from Alice Springs
- Some extreme eastern passes (satellite approaching from the Pacific) may be below the horizon from Alice Springs but would be received by GA/BoM Melbourne or a hypothetical eastern station
- Coverage is not 100% for NSW from a single central Australian station

### Daily Pass Count
With 3 VIIRS satellites (SNPP, NOAA-20, NOAA-21), expect ~6 passes per day over NSW:
- 3 daytime (ascending, ~13:30 local solar time +/- 90 min spread)
- 3 nighttime (descending, ~01:30 local solar time)

---

## 7. The SSEC URT Architecture (What We'd Want to Replicate)

The University of Wisconsin SSEC system is the gold standard for low-latency VIIRS fire detection. Key architectural elements:

1. **Multiple DB antennas** across CONUS stream data to a central server at UW-Madison
2. **Real-time streaming:** Data flows as it is received, not stored-and-forwarded
3. **Micro-granule processing:** Data is chopped into tiny time slices (~6 seconds of VIIRS data each) and processed immediately
4. **Pipeline:** Level 0 (CADU) -> Level 0 (RDR via RT-STPS) -> Level 1 (SDR via CSPP SDR) -> Level 2 (fire via CSPP fire) — all on the micro-granule
5. **Merge and deduplicate:** Data from overlapping antennas is combined
6. **Output:** CSV fire detections delivered to FIRMS via API

**Key contact:** Space Science and Engineering Center (SSEC), University of Wisconsin-Madison. The CSPP team there is funded by JPSS and supportive of international DB users.

**CSPP support:** cspp.ssec@ssec.wisc.edu

---

## 8. Relevant Contacts Summary

| Organization | Contact | Purpose |
|---|---|---|
| GA Digital Earth Australia | earth.observation@ga.gov.au | DEA Hotspots API access, raw data partnership |
| BoM Satellite Operations | satellites@bom.gov.au | DB station data access |
| Viasat Real-Time Earth | RTEservices@viasat.com | Commercial GSaaS quote |
| CfAT Satellite Enterprises | https://www.cfat.org.au/cfat-se | Alice Springs facility |
| CSPP team (UW-Madison) | cspp.ssec@ssec.wisc.edu | CSPP software support |
| ANGSTT | angstt.gov.au/contact-us | National ground segment coordination |
| Landgate / WASTAC | myfirewatch.landgate.wa.gov.au | WA fire detection, VIIRS DB expertise |
| Prof Mervyn Lynch (Curtin) | Curtin University, Dept of Imaging & Applied Physics | WASTAC VIIRS expertise |
| Australian Space Agency | via ANGSTT | High-level coordination |
| GINA (Univ of Alaska Fairbanks) | gina.alaska.edu | Reference implementation of VIIRS DB for fire |

---

## 9. Key References

- CSPP Main Page: https://cimss.ssec.wisc.edu/cspp/
- CSPP SDR v4.0: https://cimss.ssec.wisc.edu/cspp/jpss_sdr_v4.0.shtml
- CSPP VIIRS Active Fire v2.1: https://cimss.ssec.wisc.edu/cspp/viirs_fire_v2.1.shtml
- RT-STPS v7.0: https://cimss.ssec.wisc.edu/cspp/rt_stps_v7.0_patch1.shtml
- Polar2Grid v3.0: https://cimss.ssec.wisc.edu/cspp/polar2grid_v3.0.shtml
- FIRMS URT announcement: https://www.earthdata.nasa.gov/news/feature-articles/firms-adds-ultra-real-time-data-from-modis-viirs
- DEA Hotspots: https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/
- GA Ground Stations: https://www.ga.gov.au/scientific-topics/space/our-satellite-and-ground-station-network
- Viasat RTE: https://www.viasat.com/government/antenna-systems/real-time-earth/
- ANGSTT Network: https://www.angstt.gov.au/network
- JPSS HRD ICD: https://www.nesdis.noaa.gov/s3/2022-03/JPSS-1SCHRDtoDBSRFICDRevA-470-REF-00184February9,2015.pdf
- Suomi NPP on eoPortal: https://www.eoportal.org/satellite-missions/suomi-npp
- X-band primer (amateur): https://www.a-centauri.com/articoli/an-x-band-primer
- GINA Alaska VIIRS fire: https://gina.alaska.edu/training-resources/wildfire-resources/
- Urbanski et al. 2018 (VIIRS DB fire mapping): https://www.sciencedirect.com/science/article/abs/pii/S0034425718304553
- WASTAC: http://www.wastac.wa.gov.au/
- Landgate FireWatch: https://myfirewatch.landgate.wa.gov.au/
- BoM AP-RARS: https://www.bom.gov.au/australia/satellite/rars.shtml
