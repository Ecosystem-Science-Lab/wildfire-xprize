# Data Partnership Strategy for XPRIZE Wildfire Detection

## Context
We need near-real-time satellite data over NSW Australia during a 2-week competition window in mid-April 2026. We cannot deploy our own ground station hardware — we need to partner with organizations that already have the infrastructure.

**Key advantage:** NAU is the only university team in the competition. University-to-university collaborations are easier to establish (shared academic mission, MOU, co-publication) than government or commercial partnerships.

## Critical Data Gaps

### Gap 1: VIIRS Direct Broadcast (~5-15 min latency)
Standard FIRMS NRT for Australia is ~3 hours — too slow for 1-minute-from-overpass scoring. Direct broadcast from a local ground station could deliver processed fire detections within 5-15 minutes of overpass.

**Who might have VIIRS/HRPT receivers in Australia:**
- Bureau of Meteorology (Melbourne, likely has HRPT)
- Geoscience Australia (Canberra)
- Australian universities with space/remote sensing programs
- Antarctic stations with VIIRS line-of-sight to SE Australia passes

### Gap 2: Landsat Real-Time Processing (~seconds latency)
Standard USGS pipeline for Australia is 4-6 hours. FarEarth Observer (Pinkmatter) demonstrated <10 second latency by processing X-band during the satellite pass.

**Key target: Geoscience Australia Alice Springs ground station**
- One of only 5 USGS Landsat Ground Network stations worldwide
- Data currently flows: Alice Springs → Canberra (fibre) → EROS (Sioux Falls) → processing
- If we could process the X-band data stream locally at Alice Springs (or in Canberra before it ships to EROS), we'd have Landsat detections in seconds
- Australia has committed $200M to modernize this facility
- 2-4 Landsat overpasses of NSW during the 2-week competition window, all ~10 AM AEST
- Pitch angle: demonstrate the value of Australia's ground station investment for real-time fire response

### Gap 3: Himawari AHI Faster Access
Current Himawari latency via AWS NODD is ~7-15 minutes. JMA distributes to partner agencies faster.

**Potential targets:**
- BoM receives Himawari data operationally for weather forecasting — their internal feed is likely faster than the public AWS mirror
- JMA direct partnership (institutional, harder to arrange)

## Priority Targets

### Tier 1: Australian Universities (highest probability of success)
- **UNSW Canberra** — strong space engineering program, satellite ground station operations
- **University of Tasmania** — Antarctic/satellite operations, possible VIIRS receivers
- **ANU** — Canberra-based, possible connections to GA
- **RMIT** — aerospace engineering, Melbourne-based
- **University of New South Wales (Sydney)** — remote sensing group

**Pitch:** Joint research collaboration for real-time wildfire detection. Co-authorship on publications. Demonstration of Australian satellite infrastructure for fire response. XPRIZE visibility.

### Tier 2: Government Agencies (slower process, higher value)
- **Geoscience Australia** — Alice Springs ground station, DEA Hotspots, Landsat data pipeline
- **Bureau of Meteorology** — Himawari/VIIRS operational data feeds, DEA Hotspots
- **CSIRO** — research partnership, may have ground station access

**Pitch:** Demonstrate value of Australian earth observation infrastructure. Support bushfire response capability. XPRIZE brings international visibility.

### Tier 3: Commercial (fastest if budget allows)
- **OroraTech** — thermal cubesat constellation, 3-minute alerts, 4×4m fires. Competition partnership?
- **FarEarth/Pinkmatter** — real-time Landsat processing software. Could they deploy at Alice Springs?
- **Fireball International** — Australian wildfire detection company, may have data feeds

## Specific Ask for Alice Springs

**What we need:**
- Access to Landsat X-band data stream at the Alice Springs ground station (or Canberra relay point)
- Permission to run FarEarth Observer or equivalent real-time processing software on the data stream
- Only needed for a 2-week window in April 2026
- Alternatively: a fast data tap at the Canberra relay point before data ships to EROS

**What we offer:**
- XPRIZE competition visibility for Australian space infrastructure
- Demonstration of real-time fire detection from Australian ground stations
- Joint publication on ultra-low-latency satellite fire detection
- Proof of concept that could inform future Australian bushfire response systems

## Timeline
- **Now - June 2025:** Identify specific contacts, make initial approaches
- **July - December 2025:** Establish MOUs, test data access pipelines
- **January - March 2026:** Integration testing with live data feeds
- **April 2026:** Competition window — everything must work

## Open Questions
- Which Australian universities have VIIRS/HRPT direct broadcast receivers? (Perplexity research in progress)
- What is BoM's actual Himawari data latency on their internal feed?
- Could FarEarth Observer be deployed at Alice Springs? What would GA need?
- Are there NOAA POES (NOAA-15/18/19) HRPT receivers in Australia that share data?
- Does the DB (direct broadcast) CSPP software support AHI/Himawari processing?
