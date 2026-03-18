# Satellite Constellation Inventory for NSW Wildfire Detection

**Target area:** NSW Australia, approximately -28 to -37S, 148-154E
**Competition window:** Mid-April 2026
**Last updated:** March 2026

---

## 1. GEOSTATIONARY SATELLITES

### 1.1 Himawari-9 (PRIMARY for NSW)

| Field | Detail |
|---|---|
| **Operator** | JMA (Japan Meteorological Agency) |
| **Orbit** | GEO, 140.7E |
| **Altitude** | ~35,786 km |
| **Fire-relevant instruments** | Advanced Himawari Imager (AHI): 16 bands, 0.47-13.3 um. Fire uses Band 7 (3.9 um MIR, 2 km nadir) + Band 14 (11.2 um TIR, 2 km nadir). Visible bands (0.5-1 km) for smoke. |
| **Coverage of NSW** | Full coverage. View zenith angle ~35-43 deg for NSW latitudes (-28 to -37S). Effective pixel size degrades from 2 km nadir to ~3-4 km at NSW latitudes. |
| **Revisit frequency** | Full disk every 10 min. Japan region every 2.5 min. No dedicated rapid-scan sector for Australia, but 10-min cadence is continuous 24/7. |
| **Data access** | JAXA P-Tree system (free registration, NRT + archive); HimawariCast (DVB broadcast, ~16-17 min latency); HimawariCloud (full data, primarily for NMHSs); AWS NODD S3 bucket (noaa-himawari); FIRMS geostationary fire detections. From Feb 2026, JAXA data available for commercial use. |
| **Data latency** | JAXA P-Tree: 5-20 min after observation. HimawariCast: ~16-17 min from observation start. FIRMS Himawari fire detections: ~30 min post-observation. AWS NODD: near real-time mirroring. |
| **Fire products** | FIRMS provides filtered geostationary active fire detections (Himawari-9 KCL/IPMA, provisional). DEA Hotspots (Geoscience Australia) ingests Himawari data. Research algorithms (modified MOD14, ML-augmented) published. |
| **Viability for 1-min scoring** | HIGH for detection timing (10-min cadence, continuous). Fire product latency ~30 min via FIRMS; raw data via JAXA P-Tree ~5-20 min. Self-processing L1b could achieve detection within minutes of data arrival. |
| **Status April 2026** | OPERATIONAL. Restored to primary operations Nov 2025 after Oct 2025 anomaly. Himawari-8 available as backup at same longitude. Both satellites operational until ~2030. Himawari-10 delayed to FY2030. |
| **Public/free data** | Yes. JAXA P-Tree free registration. AWS NODD open data. FIRMS free with MAP_KEY. Commercial use of JAXA data permitted from Feb 2026. |

### 1.2 Himawari-8 (BACKUP)

| Field | Detail |
|---|---|
| **Operator** | JMA |
| **Orbit** | GEO, 140.7E (co-located with Himawari-9) |
| **Fire-relevant instruments** | Identical AHI to Himawari-9 |
| **Coverage of NSW** | Identical to Himawari-9 |
| **Revisit frequency** | Same as Himawari-9 when active |
| **Data access** | Same pathways as Himawari-9 |
| **Data latency** | Same as Himawari-9 |
| **Fire products** | Same as Himawari-9 |
| **Viability for 1-min scoring** | Same as Himawari-9 (only active when Himawari-9 is down) |
| **Status April 2026** | STANDBY/BACKUP. Returned to backup role Nov 2025 after brief primary duty (Oct-Nov 2025). Available for emergency switchover. Operational until ~2030. |
| **Public/free data** | Yes, when serving as primary |

### 1.3 GEO-KOMPSAT-2A (GK-2A)

| Field | Detail |
|---|---|
| **Operator** | KMA (Korea Meteorological Administration) |
| **Orbit** | GEO, 128.2E |
| **Altitude** | ~35,786 km |
| **Fire-relevant instruments** | Advanced Meteorological Imager (AMI): 16 channels. Visible 0.5-1 km, IR 2 km. Similar spectral coverage to AHI. MIR ~3.8 um and TIR ~10.8, 12.3 um for fire detection. |
| **Coverage of NSW** | Yes. NSW is within AMI full-disk coverage. View angle slightly higher than Himawari (satellite is further north-west relative to NSW). Effective pixel size ~3-5 km for NSW. |
| **Revisit frequency** | Full disk every 10 min. Korean Peninsula every 2 min. Flexible target area scanning available. |
| **Data access** | AWS NODD S3 bucket (noaa-gk2a-pds) -- publicly available, no subscription required. NMSC Korea data portal. |
| **Data latency** | AWS NODD: near real-time. KMA products follow similar timeline to Himawari. |
| **Fire products** | KMA has published fire monitoring algorithms for GK-2A. FIRMS does not currently include GK-2A fire products. Research-level products available. |
| **Viability for 1-min scoring** | MODERATE. Provides supplementary geostationary coverage with similar cadence to Himawari. Slightly worse view geometry for NSW. Data freely available on AWS. |
| **Status April 2026** | OPERATIONAL. Launched Dec 2018, operational since Jul 2019. No announced end-of-life issues. |
| **Public/free data** | Yes. AWS NODD open data program. |

### 1.4 FY-4B (Fengyun-4B)

| Field | Detail |
|---|---|
| **Operator** | CMA (China Meteorological Administration) / NSMC |
| **Orbit** | GEO, 123.5E |
| **Altitude** | ~35,786 km |
| **Fire-relevant instruments** | AGRI (Advanced Geosynchronous Radiation Imager): 14 bands. VIS 500m-1km, NIR 1-2km, IR 2-4km. MIR ~3.7 um and TIR ~10.8, 12.0 um. FY-4B improved to 2 km for thermal channels (vs 4 km on FY-4A). |
| **Coverage of NSW** | Yes. At 123.5E, NSW falls well within the full disk. View angle similar to GK-2A. Effective pixel size ~3-5 km for NSW thermal channels. |
| **Revisit frequency** | Full disk every 15 min. China region more frequently. |
| **Data access** | NSMC Fengyun Satellite Data Center (satellite.nsmc.org.cn) -- free registration for international users. CMACast broadcast. Data push to FTP for bulk users. |
| **Data latency** | Fengyun data center: near real-time data available. CMACast: broadcast-based delivery. Typical latency not well documented for international users. |
| **Fire products** | FY-4A/4B Fire/Hotspot (FHS) product at 2 km, 15-min cadence. Self-adaptive threshold fire monitoring algorithm published. Accuracy >94% globally. |
| **Viability for 1-min scoring** | MODERATE. Useful supplementary geostationary view. 15-min cadence slightly slower than Himawari/GK-2A. Data access for international users may have reliability concerns. |
| **Status April 2026** | OPERATIONAL. Launched Jun 2021. |
| **Public/free data** | Yes. Free registration at NSMC data center. Follows WMO Unified Data Policy. |

### 1.5 FY-4A (Fengyun-4A)

| Field | Detail |
|---|---|
| **Operator** | CMA / NSMC |
| **Orbit** | GEO, 104.7E (relocated from 99.5E in 2018) |
| **Fire-relevant instruments** | AGRI: 14 bands. VIS 1km, NIR 2km, IR 4km. Thermal channels at 4 km (coarser than FY-4B). |
| **Coverage of NSW** | Marginal. At 104.7E, NSW is at the eastern edge of the disk. Very high view angles. Pixel degradation significant. |
| **Revisit frequency** | Full disk every 15 min |
| **Data access** | Same as FY-4B (NSMC data center) |
| **Fire products** | FY-4A FHS product. Validated but coarser than FY-4B. |
| **Viability for 1-min scoring** | LOW. Poor viewing geometry for NSW from 104.7E. FY-4B is preferred. |
| **Status April 2026** | OPERATIONAL but secondary to FY-4B. |
| **Public/free data** | Yes |

### 1.6 INSAT-3D / INSAT-3DR

| Field | Detail |
|---|---|
| **Operator** | ISRO (India) / IMD |
| **Orbit** | GEO. INSAT-3D at 82E, INSAT-3DR at 74E |
| **Fire-relevant instruments** | Imager: 6 channels including MIR (3.9 um) and TIR (10.7, 12.0 um). Resolution: 4x4 km for thermal channels. |
| **Coverage of NSW** | NO. At 74-82E, eastern Australia (~150E) is far beyond the usable field of view. View zenith angle would exceed 65-70 deg, making data unusable. |
| **Revisit frequency** | 15-30 min full disk |
| **Viability for 1-min scoring** | NONE. Does not cover NSW. |
| **Status April 2026** | Operational for Indian region. Not relevant for NSW. |
| **Public/free data** | N/A for NSW |

### 1.7 Meteosat-9 (IODC)

| Field | Detail |
|---|---|
| **Operator** | EUMETSAT |
| **Orbit** | GEO, 45.5E (Indian Ocean Data Coverage) |
| **Fire-relevant instruments** | SEVIRI: 12 channels. MIR 3.9 um, TIR 10.8/12.0 um. 3 km at nadir (pixel grows with view angle). |
| **Coverage of NSW** | NO. At 45.5E, NSW is far beyond the eastern edge of the IODC disk. View zenith angle far exceeds usable limits. |
| **Viability for 1-min scoring** | NONE. Does not cover NSW. |
| **Status April 2026** | Operational for Indian Ocean region. |
| **Public/free data** | N/A for NSW |

### 1.8 MTG-I1 (Meteosat-12) / Meteosat Third Generation

| Field | Detail |
|---|---|
| **Operator** | EUMETSAT |
| **Orbit** | GEO, ~0E (prime meridian) |
| **Fire-relevant instruments** | FCI (Flexible Combined Imager): improved resolution vs SEVIRI. Enhanced fire detection capability with thermal-IR channels. |
| **Coverage of NSW** | NO. At 0E, NSW is well outside the coverage disk. |
| **Viability for 1-min scoring** | NONE. Does not cover NSW. |
| **Status April 2026** | Operational since Dec 2024. MTG-I2 planned for 2026. Neither covers NSW. |
| **Public/free data** | N/A for NSW |

### 1.9 GOES-18 (GOES-West)

| Field | Detail |
|---|---|
| **Operator** | NOAA |
| **Orbit** | GEO, 137.2W |
| **Fire-relevant instruments** | ABI (Advanced Baseline Imager): 16 bands, 2 km IR. |
| **Coverage of NSW** | NO. At 137.2W (222.8E), Australia is on the far western edge of the full disk. GOES-West extends "to New Zealand" per NOAA, but NSW would be at extreme view angles with severely degraded resolution. Practically unusable for fire detection. |
| **Viability for 1-min scoring** | NEGLIGIBLE. Extreme viewing angle makes fire detection impractical for NSW. |
| **Status April 2026** | Operational. Not relevant for NSW. |

### 1.10 EWS-G2 (formerly GOES-15)

| Field | Detail |
|---|---|
| **Operator** | US Space Force |
| **Orbit** | GEO, ~70E (Indian Ocean) |
| **Fire-relevant instruments** | Legacy GOES imager: 5 channels, MIR 3.9 um, TIR 10.7 um. Much coarser than modern imagers (~4 km). |
| **Coverage of NSW** | NO. At ~70E, NSW is outside the usable field of view. |
| **Viability for 1-min scoring** | NONE. Does not cover NSW. Military-controlled data. |
| **Status April 2026** | Operational for military weather. Not publicly accessible. |
| **Public/free data** | No. Military controlled. |

---

## 2. POLAR-ORBITING SATELLITES (Fire Detection Workhorses)

### 2.1 VIIRS on Suomi NPP

| Field | Detail |
|---|---|
| **Operator** | NASA / NOAA |
| **Orbit** | LEO Sun-synchronous. Altitude ~834 km. Inclination 98.7 deg. LTAN 13:30 (ascending). Period ~101 min. |
| **NORAD ID** | 37849 |
| **Fire-relevant instruments** | VIIRS: 22 bands. Fire detection uses I4 (3.74 um, 375m), I5 (11.45 um, 375m), M13 (4.05 um, 750m). Day-Night Band (DNB, 750m) for nighttime fire via visible light. Swath 3,060 km. |
| **Coverage of NSW** | Full coverage. Multiple passes per day at NSW latitudes. Both ascending (afternoon ~13:30 local) and descending (nighttime ~01:30 local) passes useful. |
| **Revisit frequency** | ~2 passes/day over NSW (day + night). With NOAA-20 and NOAA-21, combined ~6 passes/day from VIIRS constellation. |
| **Data access** | AWS NODD JPSS S3 buckets + SNS push notifications. NASA LANCE/FIRMS (MAP_KEY required). Direct broadcast via CSPP. Geoscience Australia Alice Springs ground station receives VIIRS direct broadcast. |
| **Data latency** | FIRMS global NRT: up to ~3 hours. FIRMS RT: ~30 min. Direct broadcast (Australian ground stations): ~5-15 min after overpass. AWS NODD: depends on uplink to NOAA ground stations. |
| **Fire products** | VIIRS I-Band 375m Active Fire product (VNP14IMG). VIIRS M-Band active fire (VNP14). Available via FIRMS API. DEA Hotspots ingests VIIRS. |
| **Viability for 1-min scoring** | HIGH for overpasses. 375m resolution is excellent for fire detection. Latency depends on data path: direct broadcast is fastest (~5-15 min), FIRMS NRT is slower. Key is knowing exact overpass times. |
| **Status April 2026** | OPERATIONAL. EOL extended to Dec 2028. Orbit drifting but still functional. |
| **Public/free data** | Yes. Open access via NOAA, NASA FIRMS, AWS NODD. |

### 2.2 VIIRS on NOAA-20

| Field | Detail |
|---|---|
| **Operator** | NOAA / NASA |
| **Orbit** | LEO Sun-synchronous. Altitude ~834 km. Inclination 98.7 deg. LTAN 13:30 (ascending). Same orbit plane as S-NPP, ~50 min offset from NOAA-21. |
| **NORAD ID** | 43013 |
| **Fire-relevant instruments** | Identical VIIRS to S-NPP. I4/I5/M13 bands + DNB. 375m/750m. Swath 3,060 km. |
| **Coverage of NSW** | Full coverage. ~2 passes/day. |
| **Revisit frequency** | ~2 passes/day. Phased with S-NPP and NOAA-21 for ~6 VIIRS passes/day total. |
| **Data access** | Same as S-NPP (AWS NODD, FIRMS, direct broadcast, DEA Hotspots). |
| **Data latency** | Same pathways as S-NPP. |
| **Fire products** | VIIRS 375m Active Fire (VJ114IMG). Same product family as S-NPP. |
| **Viability for 1-min scoring** | HIGH. Same as S-NPP. |
| **Status April 2026** | OPERATIONAL. Primary JPSS satellite. No end-of-life concerns. |
| **Public/free data** | Yes |

### 2.3 VIIRS on NOAA-21

| Field | Detail |
|---|---|
| **Operator** | NOAA / NASA |
| **Orbit** | LEO Sun-synchronous. Altitude ~834 km. Inclination 98.7 deg. LTAN 13:30. Between S-NPP and NOAA-20 in orbit, ~50 min ahead of NOAA-20. |
| **NORAD ID** | 54234 |
| **Fire-relevant instruments** | Identical VIIRS. I4/I5/M13 + DNB. 375m/750m. |
| **Coverage of NSW** | Full coverage. ~2 passes/day. |
| **Revisit frequency** | ~2 passes/day. Provides additional coverage between S-NPP and NOAA-20 passes. |
| **Data access** | Same as S-NPP/NOAA-20. |
| **Fire products** | VIIRS 375m Active Fire. Available via FIRMS. |
| **Viability for 1-min scoring** | HIGH. Adds to VIIRS constellation density. |
| **Status April 2026** | OPERATIONAL. Launched Nov 2022. No concerns. |
| **Public/free data** | Yes |

### 2.4 MODIS on Terra

| Field | Detail |
|---|---|
| **Operator** | NASA |
| **Orbit** | LEO Sun-synchronous. Nominal altitude 705 km (drifting to ~702 km by late 2026). Inclination 98.2 deg. LTAN 10:30 (descending, but drifting to ~08:30 by late 2026). Period ~99 min. |
| **NORAD ID** | 25994 |
| **Fire-relevant instruments** | MODIS: 36 bands. Fire uses Band 21/22 (3.96 um, 1 km), Band 31 (11.03 um, 1 km), Band 32 (12.02 um, 1 km). Swath 2,330 km. |
| **Coverage of NSW** | Full coverage but degrading. Orbit drift changing overpass timing and narrowing swath slightly. |
| **Revisit frequency** | ~2 passes/day, but increasing gaps as orbit degrades |
| **Data access** | FIRMS (MAP_KEY), LANCE NRT. Direct broadcast via CSPP (Australian ground stations). |
| **Data latency** | FIRMS NRT: up to ~3 hours. Direct broadcast: ~5-15 min. |
| **Fire products** | MOD14 (Terra) Active Fire product, 1 km. Available via FIRMS. |
| **Viability for 1-min scoring** | MODERATE. 1 km resolution, degrading orbit. Still detects fires ~1000 m2. ASTER TIR permanently shut down Jan 2026 -- only MODIS remains on Terra. |
| **Status April 2026** | DEGRADING. Orbit drifting (crossing time shifting from 10:30 to ~08:30). Science data collection planned to end Feb 2027. ASTER TIR permanently off since Jan 2026. MOPITT off since Apr 2025. Will still be operating in April 2026 but with degraded capabilities. |
| **Public/free data** | Yes. Public domain. |

### 2.5 MODIS on Aqua

| Field | Detail |
|---|---|
| **Operator** | NASA |
| **Orbit** | LEO Sun-synchronous. Nominal altitude 705 km (descending, free-drift since Dec 2021). Inclination 98.2 deg. LTAN 13:30 (ascending, drifting later). Period ~99 min. |
| **NORAD ID** | 27424 |
| **Fire-relevant instruments** | Identical MODIS to Terra. 36 bands, 1 km fire channels. |
| **Coverage of NSW** | Full coverage, but orbit degrading. |
| **Revisit frequency** | ~2 passes/day, degrading |
| **Data access** | Same as Terra MODIS. FIRMS, LANCE, direct broadcast. |
| **Data latency** | Same as Terra MODIS. |
| **Fire products** | MYD14 (Aqua) Active Fire product, 1 km. |
| **Viability for 1-min scoring** | MODERATE. Same 1 km resolution as Terra. Orbit degradation underway. |
| **Status April 2026** | DEGRADING. Free-drift orbit since Dec 2021. Science data collection planned to end Sep 2027. Passivation scheduled Nov 2026. Should still be operational in April 2026 but with increasing orbit uncertainty. |
| **Public/free data** | Yes. Public domain. |

### 2.6 Sentinel-3A SLSTR

| Field | Detail |
|---|---|
| **Operator** | ESA / EUMETSAT (Copernicus) |
| **Orbit** | LEO Sun-synchronous. Altitude 814 km. Inclination 98.6 deg. LTDN 10:00 (descending node). Period ~100 min. Repeat cycle 27 days. |
| **NORAD ID** | 41335 |
| **Fire-relevant instruments** | SLSTR (Sea and Land Surface Temperature Radiometer): 9 bands + 2 dedicated fire bands. Fire-relevant: F1 (3.74 um, 1 km), F2 (10.85 um, 1 km), plus additional TIR bands at 1 km. Dual-view (nadir + oblique) capability. Swath 1,420 km (nadir), 750 km (oblique). |
| **Coverage of NSW** | Full coverage. |
| **Revisit frequency** | ~1 pass/day at NSW latitudes (varies). With Sentinel-3B, coverage improves. |
| **Data access** | Copernicus Data Space Ecosystem (dataspace.copernicus.eu) -- free registration. STAC/openEO/Sentinel Hub APIs. EUMETSAT for NRT fire products. LAADS DAAC. |
| **Data latency** | NRT: ~3 hours after sensing. SLSTR FRP product is "preliminary operational". |
| **Fire products** | Copernicus Sentinel-3 NRT Fire Radiative Power (FRP) product. Nighttime algorithm operational since 2020. Daytime from 2022. Both still labeled "preliminary operational". |
| **Viability for 1-min scoring** | MODERATE. 1 km thermal resolution. FRP product provides fire location and intensity. NRT latency ~3 hours is slow for competition scoring. |
| **Status April 2026** | OPERATIONAL. Sentinel-3C launch planned Oct 2026 (will add to constellation). |
| **Public/free data** | Yes. Copernicus open access. |

### 2.7 Sentinel-3B SLSTR

| Field | Detail |
|---|---|
| **Operator** | ESA / EUMETSAT |
| **Orbit** | Same orbit plane as Sentinel-3A, 140 deg phase difference. Altitude 814 km. LTDN 10:00. |
| **NORAD ID** | 43437 |
| **Fire-relevant instruments** | Identical SLSTR to Sentinel-3A. |
| **Coverage of NSW** | Full coverage. Complements Sentinel-3A. |
| **Revisit frequency** | Combined with 3A: improved revisit at NSW latitudes. |
| **Data access** | Same as Sentinel-3A. |
| **Fire products** | Same as Sentinel-3A. |
| **Status April 2026** | OPERATIONAL. |
| **Public/free data** | Yes |

### 2.8 MetOp-B (AVHRR)

| Field | Detail |
|---|---|
| **Operator** | EUMETSAT |
| **Orbit** | LEO Sun-synchronous. Altitude 817 km. Inclination 98.7 deg. LTDN 09:30. Period 101 min. Repeat cycle 29 days. |
| **NORAD ID** | 38771 |
| **Fire-relevant instruments** | AVHRR/3: 6 channels. Channel 3B (3.55-3.93 um, 1.1 km), Channel 4 (10.3-11.3 um, 1.1 km), Channel 5 (11.5-12.5 um, 1.1 km). Swath ~2,900 km. |
| **Coverage of NSW** | Full coverage. Morning overpass. |
| **Revisit frequency** | ~2 passes/day (morning + early AM). With MetOp-C, ~4 AVHRR passes/day. |
| **Data access** | EUMETSAT Data Store. EUMETCast broadcast. NOAA OSPO. |
| **Data latency** | Average product timeliness ~47 min. EUMETCast near real-time. |
| **Fire products** | AVHRR has fire detection capability but no dedicated operational global fire product from EUMETSAT. DEA Hotspots may ingest AVHRR. Custom algorithms needed. |
| **Viability for 1-min scoring** | LOW-MODERATE. 1 km resolution, comparable to MODIS. No operational fire product simplifies nothing. Timeliness ~47 min is acceptable. |
| **Status April 2026** | OPERATIONAL. Out-of-plane maneuvers in Sep 2025 extend mission to ~2030. |
| **Public/free data** | Yes, with registration. EUMETSAT data policy applies (generally free for >1h latency; <1h may require fee). |

### 2.9 MetOp-C (AVHRR)

| Field | Detail |
|---|---|
| **Operator** | EUMETSAT |
| **Orbit** | Same orbit type as MetOp-B. Altitude 817 km. LTDN 09:30. |
| **NORAD ID** | 43689 |
| **Fire-relevant instruments** | Identical AVHRR/3 to MetOp-B. |
| **Coverage of NSW** | Full coverage. |
| **Data access** | Same as MetOp-B. |
| **Status April 2026** | OPERATIONAL. |
| **Public/free data** | Same as MetOp-B |

### 2.10 FY-3D (MERSI-II)

| Field | Detail |
|---|---|
| **Operator** | CMA / NSMC |
| **Orbit** | LEO Sun-synchronous. Altitude 836 km. Inclination 98.75 deg. LTDN 14:00. Period ~101 min. |
| **Fire-relevant instruments** | MERSI-II: 25 channels. Fire-relevant: 3.8 um (250 m), 4.05 um (250 m), 10.8 um (250 m), 12.0 um (250 m). The 250m far-infrared channels are a notable advantage. Swath ~2,900 km. |
| **Coverage of NSW** | Full coverage. Afternoon overpass. |
| **Revisit frequency** | ~2 passes/day over NSW. |
| **Data access** | NSMC Fengyun Satellite Data Center (data.nsmc.org.cn). Free registration. FTP push for bulk users. CMACast. Direct broadcast (AHRPT). |
| **Data latency** | Near real-time via data center. Direct broadcast enables rapid processing. |
| **Fire products** | FY-3D global active fire product (published in ESSD). Accuracy >94% globally including Australia. Comparable methodology to MODIS MOD14. |
| **Viability for 1-min scoring** | MODERATE-HIGH. 250m thermal channels are exceptional (better than VIIRS 375m for spatial resolution). Fire product validated. Data access from China may have latency/reliability concerns for real-time operations. |
| **Status April 2026** | OPERATIONAL. Launched Nov 2017. |
| **Public/free data** | Yes. Free via NSMC. |

### 2.11 FY-3E (MERSI-LL)

| Field | Detail |
|---|---|
| **Operator** | CMA / NSMC |
| **Orbit** | LEO Sun-synchronous. Altitude 836 km. LTDN ~05:30 (early morning orbit). |
| **Fire-relevant instruments** | MERSI-LL: Specialized low-light instrument. Panchromatic low-light band (LLB) + 6 IR bands inherited from FY-3D. Enhanced dusk/dawn fire detection. |
| **Coverage of NSW** | Full coverage. Early morning/late afternoon passes. |
| **Revisit frequency** | ~2 passes/day. Fills early morning gap not covered by other sun-synchronous satellites. |
| **Data access** | NSMC Fengyun Satellite Data Center. |
| **Fire products** | Enhanced nighttime/dusk fire monitoring via MERSI-LL low-light capability. |
| **Viability for 1-min scoring** | MODERATE. Unique early morning coverage. Low-light capability useful for nighttime fire detection. |
| **Status April 2026** | OPERATIONAL. Launched Jul 2021. |
| **Public/free data** | Yes |

### 2.12 FY-3F (MERSI)

| Field | Detail |
|---|---|
| **Operator** | CMA / NSMC |
| **Orbit** | LEO Sun-synchronous. Altitude 836 km. LTDN ~10:00. |
| **Fire-relevant instruments** | MERSI instrument (details TBC, likely similar to MERSI-II with improvements). |
| **Coverage of NSW** | Full coverage. Morning overpass. |
| **Status April 2026** | OPERATIONAL. Launched Aug 2023. |
| **Public/free data** | Yes via NSMC |

### 2.13 Meteor-M N2-3

| Field | Detail |
|---|---|
| **Operator** | Roscosmos / Roshydromet (Russia) |
| **Orbit** | LEO Sun-synchronous. Altitude ~830 km. Inclination 98.6 deg. |
| **NORAD ID** | 57166 |
| **Fire-relevant instruments** | MSU-MR: 6 channels (VIS, NIR, SWIR, TIR). 1 km resolution across all channels. Swath ~2,800 km. Channels include 3.5-4.1 um (MIR) and 10.5-11.5 um, 11.5-12.5 um (TIR). |
| **Coverage of NSW** | Full coverage. |
| **Revisit frequency** | ~2 passes/day |
| **Data access** | LRPT broadcast at 137 MHz (receivable by amateur stations). HRPT broadcast. Russian data centers (Planeta). Limited international data sharing. |
| **Data latency** | Direct broadcast: immediate for local stations. Official products: unclear for international users. |
| **Fire products** | No dedicated international fire product. MSU-MR data could be processed with custom algorithms. |
| **Viability for 1-min scoring** | LOW. Data access for international users is unreliable. No operational fire product for Australia. |
| **Status April 2026** | OPERATIONAL. EOL June 2028. |
| **Public/free data** | Direct broadcast is open. Official products have limited international access. |

### 2.14 Meteor-M N2-4

| Field | Detail |
|---|---|
| **Operator** | Roscosmos / Roshydromet |
| **Orbit** | LEO Sun-synchronous. Altitude ~830 km. |
| **NORAD ID** | TBD (launched Feb 2024) |
| **Fire-relevant instruments** | MSU-MR (same as N2-3) |
| **Coverage of NSW** | Full coverage |
| **Status April 2026** | OPERATIONAL. Launched Feb 2024. |
| **Public/free data** | Same limitations as N2-3 |

---

## 3. HIGH-RESOLUTION THERMAL

### 3.1 Landsat 8 (OLI + TIRS)

| Field | Detail |
|---|---|
| **Operator** | USGS / NASA |
| **Orbit** | LEO Sun-synchronous. Altitude 705 km. Inclination 98.2 deg. Equatorial crossing ~10:12 AM local time (descending). Period 99 min. Repeat cycle 16 days. |
| **NORAD ID** | 39084 |
| **Fire-relevant instruments** | TIRS: Band 10 (10.6-11.2 um, 100 m), Band 11 (11.5-12.5 um, 100 m). OLI: Band 7 (2.11-2.29 um SWIR, 30 m), Band 6 (1.57-1.65 um SWIR, 30 m). Swath 185 km. |
| **Coverage of NSW** | Full coverage, but narrow swath means sparse revisit. |
| **Revisit frequency** | 16-day repeat cycle. Combined with Landsat 9: 8-day offset. Any given NSW location imaged every ~8 days. |
| **Data access** | USGS EarthExplorer. AWS S3 (Landsat Collection 2). Google Earth Engine. FIRMS Landsat active fire (US/Canada only for FIRMS NRT). |
| **Data latency** | Level-1 Real-Time scenes: ~4-6 hours after acquisition. Standard processing: 12-24 hours. |
| **Fire products** | Landsat active fire algorithm can detect fires "as small as a few square meters." Available via FIRMS for US/Canada. For NSW, custom processing of L1 data required. |
| **Viability for 1-min scoring** | LOW (revisit) but HIGH (sensitivity). 100m thermal + 30m SWIR enables detection of very small fires at overpass time. 8-day revisit means this is a confirmation/detail tool, not continuous monitoring. Must know overpass schedule. |
| **Status April 2026** | OPERATIONAL. Launched Feb 2013. No announced end-of-life. |
| **Public/free data** | Yes. Public domain (USGS). |

### 3.2 Landsat 9 (OLI-2 + TIRS-2)

| Field | Detail |
|---|---|
| **Operator** | USGS / NASA |
| **Orbit** | Same orbit as Landsat 8. 8-day offset. Equatorial crossing ~10:12 AM. |
| **NORAD ID** | 49260 |
| **Fire-relevant instruments** | Identical bands to Landsat 8. TIRS-2: 100m thermal. OLI-2: 30m SWIR. |
| **Coverage of NSW** | Same as Landsat 8, but offset timing. |
| **Revisit frequency** | Combined with Landsat 8: ~8-day revisit for any NSW location. |
| **Data access** | Same as Landsat 8. |
| **Fire products** | Same capability as Landsat 8. |
| **Status April 2026** | OPERATIONAL. Launched Sep 2021. |
| **Public/free data** | Yes. Public domain. |

### 3.3 ECOSTRESS (ISS)

| Field | Detail |
|---|---|
| **Operator** | NASA / JPL |
| **Orbit** | ISS orbit. Altitude ~420 km. Inclination 51.6 deg. Non-sun-synchronous (precessing). |
| **Fire-relevant instruments** | PHyTIR: 5 thermal bands in 8-12.5 um range. Resolution 69 m x 38 m (cross-track x down-track). Swath 384 km. |
| **Coverage of NSW** | Coverage limited by ISS inclination (51.6 deg), which restricts coverage to latitudes between ~52N and ~52S. NSW (-28 to -37S) IS covered, but overpass times and frequency are irregular due to ISS precession. |
| **Revisit frequency** | Variable, 1-5 day revisit depending on ISS orbit precession. Not predictable long-term via TLE alone. Overpass times shift throughout the ISS orbit cycle. |
| **Data access** | NASA LP DAAC (e4ftl01.cr.usgs.gov/ECOSTRESS/). NASA Earthdata. |
| **Data latency** | NRT latency TBD. Standard products: hours to days. |
| **Fire products** | No dedicated fire product. LST/emissivity products at 70m. Could be processed for fire detection with custom algorithms. |
| **Viability for 1-min scoring** | LOW. No fire product. Irregular overpass times. 70m thermal resolution is excellent but limited by unpredictable revisit. Potential noise issues (May-Jul 2025 data quality issue noted). |
| **Status April 2026** | OPERATIONAL (extended). Approved through FY2026 with potential to FY2029 pending 2026 Senior Review. |
| **Public/free data** | Yes. NASA open access. |

### 3.4 ASTER TIR (Terra)

| Field | Detail |
|---|---|
| **Operator** | NASA / METI (Japan) |
| **Orbit** | Same as Terra MODIS (705 km, 10:30 descending) |
| **Fire-relevant instruments** | TIR subsystem: 5 bands in 8-12 um, 90m resolution. **PERMANENTLY SHUT DOWN** January 2026 due to Terra power limitations. VNIR still operating. |
| **Coverage of NSW** | N/A -- TIR off |
| **Viability for 1-min scoring** | NONE. TIR permanently off since Jan 2026. |
| **Status April 2026** | TIR DECOMMISSIONED. Not available. |

### 3.5 TRISHNA

| Field | Detail |
|---|---|
| **Operator** | CNES / ISRO |
| **Orbit** | LEO Sun-synchronous. ~761 km. |
| **Fire-relevant instruments** | TIR: 4 thermal bands, 57 m resolution. VSWIR: 7 bands. |
| **Coverage of NSW** | Would cover NSW globally. |
| **Revisit frequency** | 3-day revisit at equator (more at higher latitudes). |
| **Status April 2026** | NOT YET LAUNCHED. Launch planned 2026-2027 (PSLV). Unlikely to be operational by April 2026. |
| **Public/free data** | TBD |

### 3.6 LSTM (Land Surface Temperature Monitoring / Sentinel-8)

| Field | Detail |
|---|---|
| **Operator** | ESA (Copernicus) |
| **Orbit** | LEO polar |
| **Fire-relevant instruments** | TIR + SWIR + VNIR. High-resolution thermal (significantly finer than current Landsat). |
| **Status April 2026** | NOT YET LAUNCHED. Launch planned Dec 2028. Not available for April 2026. |

### 3.7 SBG-TIR (Surface Biology and Geology)

| Field | Detail |
|---|---|
| **Operator** | NASA |
| **Orbit** | LEO. 60m thermal, 935 km swath, 3-day revisit. |
| **Status April 2026** | NOT YET LAUNCHED. Launch planned Sep 2029. Not available for April 2026. |

---

## 4. SWIR-CAPABLE (Fire through band saturation)

### 4.1 Sentinel-2B

| Field | Detail |
|---|---|
| **Operator** | ESA (Copernicus) |
| **Orbit** | LEO Sun-synchronous. Altitude 786 km. Inclination 98.62 deg. LTDN 10:30. Period ~100 min. 10-day repeat cycle. |
| **Fire-relevant instruments** | MSI: 13 bands. Fire-relevant: B12 (2.19 um SWIR, 20m), B11 (1.61 um SWIR, 20m), B8A (0.865 um NIR, 20m). No thermal bands. Swath 290 km. Active fire detection via SWIR saturation (fires >600K saturate SWIR bands). |
| **Coverage of NSW** | Full coverage. |
| **Revisit frequency** | 5-day revisit with Sentinel-2B + 2C combined (phased 180 deg). |
| **Data access** | Copernicus Data Space Ecosystem (free). Sentinel Hub APIs. Google Earth Engine. |
| **Data latency** | NRT: 100 min - 3 hours. Nominal: 3-24 hours. "Real-Time" class: less than 100 min (definition exists; availability varies). |
| **Fire products** | No official active fire product. SWIR-based fire/smoke detection algorithms published. Burn area mapping (dNBR). |
| **Viability for 1-min scoring** | LOW-MODERATE. 20m SWIR detects active fires through band saturation. No thermal band limits nighttime capability. 5-day revisit is sparse. Best as confirmation/detail. |
| **Status April 2026** | OPERATIONAL. |
| **Public/free data** | Yes. Copernicus open access. |

### 4.2 Sentinel-2C

| Field | Detail |
|---|---|
| **Operator** | ESA (Copernicus) |
| **Orbit** | Same orbit as Sentinel-2B, replacing Sentinel-2A. LTDN 10:30. |
| **Fire-relevant instruments** | Identical MSI to Sentinel-2B. 13 bands, 20m SWIR. |
| **Coverage of NSW** | Full coverage. |
| **Revisit frequency** | Combined with 2B: ~5-day revisit. |
| **Data access** | Same as Sentinel-2B. Copernicus Data Space. |
| **Status April 2026** | OPERATIONAL. Launched Sep 2024. Replaced Sentinel-2A in Jan 2025. |
| **Public/free data** | Yes |

---

## 5. SMOKE / AEROSOL DETECTION

### 5.1 TROPOMI on Sentinel-5P

| Field | Detail |
|---|---|
| **Operator** | ESA / KNMI (Copernicus) |
| **Orbit** | LEO Sun-synchronous. Altitude 824 km. LTAN 13:30 (ascending). |
| **Fire-relevant instruments** | TROPOMI: UV-VIS-NIR-SWIR spectrometer. Aerosol Index (AI) product detects UV-absorbing aerosols (smoke, dust). CO product tracks combustion plumes. Spatial resolution 5.5 x 3.5 km. Swath 2,600 km. |
| **Coverage of NSW** | Full coverage, daily. |
| **Revisit frequency** | Daily global coverage. |
| **Data access** | Copernicus Data Space. GES DISC (NASA). NRT via LANCE. |
| **Data latency** | NRT: ~3 hours. |
| **Fire products** | UV Aerosol Index for smoke tracking. CO for combustion detection. PyroCb AI for intense fire plumes. Not a primary fire detection tool but valuable for smoke plume tracking and fire confirmation. |
| **Viability for 1-min scoring** | LOW for detection. Useful for smoke/plume corroboration and fire intensity assessment. |
| **Status April 2026** | OPERATIONAL. Launched Oct 2017. |
| **Public/free data** | Yes. Copernicus open access. |

### 5.2 OMPS on Suomi NPP / NOAA-20

| Field | Detail |
|---|---|
| **Operator** | NOAA / NASA |
| **Orbit** | Same as VIIRS (834 km, 13:30 LTAN) |
| **Fire-relevant instruments** | OMPS (Ozone Mapping and Profiler Suite): Aerosol Index (AI) product. PyroCb AI product (upper limit 50.0, designed for intense fire plumes). Resolution ~50 km (nadir). |
| **Coverage of NSW** | Full coverage, daily. |
| **Fire products** | AI values 0-5 indicate biomass burning smoke. PyroCb product tracks intense fire plumes. NRT via LANCE. |
| **Viability for 1-min scoring** | LOW. Coarse resolution. Useful for large smoke plume tracking only. |
| **Status April 2026** | OPERATIONAL. |
| **Public/free data** | Yes. NASA open access. |

### 5.3 VIIRS Day-Night Band (DNB)

| Field | Detail |
|---|---|
| **Operator** | NOAA / NASA |
| **Orbit** | Same as VIIRS (on S-NPP, NOAA-20, NOAA-21) |
| **Fire-relevant instruments** | DNB: Panchromatic 0.5-0.9 um, 750m resolution. Ultra-sensitive low-light detector. Can detect fire-emitted visible light at night. |
| **Coverage of NSW** | Full coverage on nighttime passes (~01:30 local). |
| **Fire products** | Complementary to I-band fire products. DNB improves detection of smaller/cooler nocturnal fires by adding visible-light signatures to IR. VIIRS Nighttime imagery product. |
| **Viability for 1-min scoring** | MODERATE for nighttime fires. Enhances standard VIIRS fire detection at night. Same data pathway as VIIRS thermal products. |
| **Status April 2026** | OPERATIONAL (same as VIIRS). |
| **Public/free data** | Yes |

---

## 6. CUBESATS AND NEW COMMERCIAL MISSIONS

### 6.1 OroraTech Wildfire Constellation

| Field | Detail |
|---|---|
| **Operator** | OroraTech (Germany) |
| **Orbit** | LEO. Multiple planes. 8U CubeSats + SAFIRE payloads on Kepler satellites. |
| **Fire-relevant instruments** | MWIR + LWIR spectral bands. High-temperature (active flames) and low-temperature (smoldering) detection. Resolution TBD (estimated 200-500m from orbit). |
| **Coverage of NSW** | Global coverage including NSW. Late-afternoon and pre-dawn fire detection coverage. |
| **Revisit frequency** | Current constellation (8 OTC-P1 + FOREST satellites + SAFIRE payloads): aiming for 30-min revisit at full constellation. Current effective revisit may be several hours. |
| **Data access** | OroraTech Wildfire Solution platform (web interface + API). Commercial service. 500+ users worldwide. |
| **Data latency** | Near-real-time alerts with <10 min latency from platform. |
| **Fire products** | Active fire detection, fire perimeter mapping, heat maps. Integrated platform with alerts. |
| **Viability for 1-min scoring** | MODERATE-HIGH potential. <10 min alert latency is good. But commercial service -- unclear if data would be available for competition use. Coverage may still have gaps with current constellation size. |
| **Status April 2026** | OPERATIONAL. 8 OTC-P1 sats operational since Apr 2025. FOREST-3 launched Jan 2025. 4 SAFIRE Gen4 payloads launched Jan 2026. Additional 8 satellites launched end of 2025. Growing toward 100 sats by 2028. |
| **Public/free data** | NO. Commercial service. Pricing not publicly disclosed. Would need to negotiate access. |

### 6.2 FireSat (Muon Space / Earth Fire Alliance)

| Field | Detail |
|---|---|
| **Operator** | Muon Space / Earth Fire Alliance |
| **Orbit** | LEO. 1,500 km observation swath. |
| **Fire-relevant instruments** | 6-band multispectral infrared instrument. MWIR + LWIR channels. GSD ~80m average. Can detect fires as small as 5x5 m. |
| **Coverage of NSW** | Will cover NSW globally. |
| **Revisit frequency** | Phase 1 (3 satellites, mid-2026): twice-daily global observation. Full constellation (50+ sats): every 20 min globally, 9 min in fire-prone areas. |
| **Data access** | Early Adopter Program announced Jun 2025. Data delivery mechanisms being developed. |
| **Data latency** | Near-real-time fire detection and perimeter maps. Untasked "always-on" mode. |
| **Fire products** | Fire detection and perimeter maps, radiative power. Designed ground-up for fire. |
| **Viability for 1-min scoring** | POTENTIALLY HIGH but uncertain. Phase 1 (3 sats) expected mid-2026 -- may not be operational by April 2026. If operational, 80m resolution and fire-optimized design would be excellent. Data access pathway unclear. |
| **Status April 2026** | PROTOFLIGHT operational (launched Jun 2025, first-light images released). First 3 operational sats planned mid-2026 -- likely NOT operational by April 2026. |
| **Public/free data** | TBD. Earth Fire Alliance is nonprofit. Data policy being developed. |

### 6.3 SatVu HotSat-2 / HotSat-3

| Field | Detail |
|---|---|
| **Operator** | SatVu (UK) |
| **Orbit** | LEO. ~160 kg microsatellites. |
| **Fire-relevant instruments** | MWIR thermal infrared. 3.5m resolution thermal imaging. |
| **Coverage of NSW** | Tasked imaging (not continuous monitoring). Would cover NSW on request. |
| **Revisit frequency** | With 2-3 sats: limited. Full constellation (9 sats): 10-20 revisits/day. |
| **Data access** | Commercial tasking. Pre-orders announced. |
| **Fire products** | High-resolution thermal imagery. Not a dedicated fire product but thermal resolution is exceptional. |
| **Viability for 1-min scoring** | LOW. Tasked imaging model (not always-on). Very high resolution but limited coverage. Commercial/military focus. |
| **Status April 2026** | HotSat-1 failed Dec 2023. HotSat-2 and HotSat-3 planned for orbit in 2025-2026. Status uncertain. |
| **Public/free data** | NO. Commercial. NATO Innovation Fund backed. |

### 6.4 Satellogic NewSat Constellation

| Field | Detail |
|---|---|
| **Operator** | Satellogic (Argentina/US) |
| **Orbit** | LEO SSO. Multiple satellites. |
| **Fire-relevant instruments** | Multispectral: 5 bands (RGB + NIR 750-900nm), 0.7m resolution. Hyperspectral: 29 bands, 30m. NO thermal infrared capability. |
| **Coverage of NSW** | Tasked imaging. |
| **Fire products** | None. Could potentially detect smoke in visible/NIR but not designed for fire detection. No thermal capability. |
| **Viability for 1-min scoring** | NEGLIGIBLE. No thermal bands. |
| **Status April 2026** | Operational but not relevant for thermal fire detection. |
| **Public/free data** | No. Commercial. |

### 6.5 Planet (Dove/SuperDove/SkySat)

| Field | Detail |
|---|---|
| **Operator** | Planet Labs |
| **Orbit** | LEO. 100+ Dove/SuperDove CubeSats in SSO. SkySats in inclined orbits. |
| **Fire-relevant instruments** | SuperDove: 8 bands (VIS + NIR), 3m resolution. SkySat: 4 bands, 0.5m resolution. NO thermal or SWIR bands. |
| **Coverage of NSW** | Daily coverage of all landmass (Dove constellation). |
| **Revisit frequency** | Daily (Dove), multiple times daily in some areas. |
| **Data access** | Planet Explorer. NASA CSDA access (research). EULA restrictions. |
| **Fire products** | No fire product. Could detect smoke plumes in visible imagery. |
| **Viability for 1-min scoring** | NEGLIGIBLE for fire detection. Potentially useful for smoke/damage assessment. Data access restricted by EULA. |
| **Status April 2026** | Operational. |
| **Public/free data** | No. Commercial (limited research access via NASA CSDA). |

---

## 7. SAR SATELLITES (Fire Effects Detection)

### 7.1 Sentinel-1A + Sentinel-1C

| Field | Detail |
|---|---|
| **Operator** | ESA (Copernicus) |
| **Orbit** | LEO Sun-synchronous. Altitude 693 km. Inclination 98.18 deg. Period 98.6 min. 12-day repeat (6-day with 2 sats). |
| **Fire-relevant instruments** | C-SAR: C-band (5.405 GHz). VV and VH polarization. 5-20m resolution depending on mode. All-weather, day/night. |
| **Coverage of NSW** | Full coverage. Revisit ~2-4 days at NSW latitudes with 2-sat constellation. |
| **Fire products** | No active fire detection. Burn area / fire scar mapping via backscatter change detection. VH polarization best for detecting burned forest (3-6 dB decrease). Can see through smoke and clouds. |
| **Viability for 1-min scoring** | NEGLIGIBLE for active fire detection. Useful for post-fire burn area mapping and monitoring fire progression through smoke. Not a detection tool. |
| **Status April 2026** | OPERATIONAL. Sentinel-1A + Sentinel-1C (launched Dec 2024, operational May 2025). |
| **Public/free data** | Yes. Copernicus open access. |

### 7.2 ALOS-2 (PALSAR-2)

| Field | Detail |
|---|---|
| **Operator** | JAXA |
| **Orbit** | LEO SSO. Altitude 628 km. Inclination 97.9 deg. 14-day repeat. |
| **Fire-relevant instruments** | PALSAR-2: L-band SAR (1.27 GHz). 1-10m resolution. Penetrates vegetation more than C-band. |
| **Coverage of NSW** | Full coverage. |
| **Fire products** | Burn area mapping. L-band provides forest structure change information. Global mosaic updated annually (2025 mosaic released Mar 2026). |
| **Viability for 1-min scoring** | NEGLIGIBLE for real-time fire detection. Useful for post-fire analysis. |
| **Status April 2026** | OPERATIONAL. Data available through JAXA. |
| **Public/free data** | Partially. Research access available. Some products free via JAXA. |

---

## 8. OTHER SENSORS

### 8.1 WorldView-3

| Field | Detail |
|---|---|
| **Operator** | Maxar Technologies |
| **Orbit** | LEO SSO. Altitude 617 km. |
| **Fire-relevant instruments** | SWIR: 8 bands at 3.7m resolution (1.195-2.365 um). CAVIS: 12 bands at 30m (for atmospheric correction). Panchromatic: 0.31m. Multispectral: 1.24m. |
| **Coverage of NSW** | Tasked imaging. |
| **Fire products** | SWIR can penetrate smoke to see active fire fronts. 3.7m SWIR is unprecedented resolution. Used operationally in California fires 2018-2021. |
| **Viability for 1-min scoring** | LOW. Tasked commercial imaging. Not continuous monitoring. Extremely expensive. But SWIR fire detection capability through smoke is exceptional. |
| **Status April 2026** | OPERATIONAL. |
| **Public/free data** | No. Commercial. |

### 8.2 CALIPSO

| Field | Detail |
|---|---|
| **Status April 2026** | DECOMMISSIONED. Mission ended Aug 2023. Final passivation Dec 2023. Not available. |

### 8.3 Digital Earth Australia Hotspots (Integrated Service)

| Field | Detail |
|---|---|
| **Operator** | Geoscience Australia |
| **Type** | National bushfire monitoring system (not a satellite, but integrates multiple satellite feeds) |
| **Data sources** | Ingests Himawari, VIIRS, MODIS, AVHRR data. Updates every 10 minutes. |
| **Coverage of NSW** | Full Australian coverage including NSW. |
| **Data access** | Web interface (hotspots.dea.ga.gov.au). WMS and WFS web services. Download and API access. |
| **Data latency** | Updates every 10 minutes with most recent satellite data. |
| **Fire products** | Hotspot locations with confidence levels and recency coloring. |
| **Viability for 1-min scoring** | MODERATE. Aggregated product from multiple satellites. 10-min update cycle aligned with Himawari cadence. Could be used as a secondary validation source. |
| **Public/free data** | Yes. Free public access. |

---

## SUMMARY TABLE

| Satellite | Orbit | Resolution (fire) | Revisit (NSW) | Latency | Status Apr 2026 | NSW Coverage |
|---|---|---|---|---|---|---|
| **Himawari-9** | GEO 140.7E | 2km (3-4km eff.) | 10 min | 5-30 min | Operational | PRIMARY |
| **Himawari-8** | GEO 140.7E | 2km (3-4km eff.) | 10 min | 5-30 min | Backup | Backup |
| **GK-2A** | GEO 128.2E | 2km (3-5km eff.) | 10 min | Minutes | Operational | Good |
| **FY-4B** | GEO 123.5E | 2-4km | 15 min | Minutes-hours | Operational | Good |
| **FY-4A** | GEO 104.7E | 4km | 15 min | Minutes-hours | Operational | Marginal |
| **S-NPP VIIRS** | LEO 834km | 375m | ~6/day (3 sats) | 5 min-3 hr | Operational | Full |
| **NOAA-20 VIIRS** | LEO 834km | 375m | ~6/day (3 sats) | 5 min-3 hr | Operational | Full |
| **NOAA-21 VIIRS** | LEO 834km | 375m | ~6/day (3 sats) | 5 min-3 hr | Operational | Full |
| **Terra MODIS** | LEO 705km | 1km | ~2/day | 5 min-3 hr | Degrading | Full |
| **Aqua MODIS** | LEO 705km | 1km | ~2/day | 5 min-3 hr | Degrading | Full |
| **Sentinel-3A SLSTR** | LEO 814km | 1km | ~1/day | ~3 hr | Operational | Full |
| **Sentinel-3B SLSTR** | LEO 814km | 1km | ~1/day | ~3 hr | Operational | Full |
| **MetOp-B AVHRR** | LEO 817km | 1.1km | ~2/day | ~47 min | Operational | Full |
| **MetOp-C AVHRR** | LEO 817km | 1.1km | ~2/day | ~47 min | Operational | Full |
| **FY-3D MERSI-II** | LEO 836km | 250m TIR | ~2/day | Hours | Operational | Full |
| **FY-3E MERSI-LL** | LEO 836km | 250m | ~2/day | Hours | Operational | Full |
| **FY-3F MERSI** | LEO 836km | TBD | ~2/day | Hours | Operational | Full |
| **Meteor-M N2-3** | LEO 830km | 1km | ~2/day | Hours | Operational | Full |
| **Meteor-M N2-4** | LEO 830km | 1km | ~2/day | Hours | Operational | Full |
| **Landsat 8** | LEO 705km | 100m TIR, 30m SWIR | ~8 days | 4-6 hr | Operational | Full |
| **Landsat 9** | LEO 705km | 100m TIR, 30m SWIR | ~8 days | 4-6 hr | Operational | Full |
| **ECOSTRESS** | ISS 420km | 69x38m TIR | 1-5 days | Hours | Operational | Limited |
| **Sentinel-2B MSI** | LEO 786km | 20m SWIR | ~5 days | 100 min-24 hr | Operational | Full |
| **Sentinel-2C MSI** | LEO 786km | 20m SWIR | ~5 days | 100 min-24 hr | Operational | Full |
| **Sentinel-5P TROPOMI** | LEO 824km | 5.5x3.5 km | Daily | ~3 hr | Operational | Full |
| **OroraTech** | LEO various | ~200-500m | Hours | <10 min | Operational | Full |
| **FireSat** | LEO | ~80m | 2x/day (Phase 1) | NRT | Protoflight only | TBD |
| **Sentinel-1A/C** | LEO 693km | 5-20m SAR | 2-4 days | Hours | Operational | Full |

**Total unique satellite platforms with fire-relevant capability covering NSW: ~30+**
**Estimated daily overpasses (LEO thermal/fire): 20-30+ passes per day**
**Continuous geostationary coverage: 3 confirmed satellites (Himawari-9, GK-2A, FY-4B)**
