<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Describe the Himawari-8/9 AHI Wildfire Detection Algorithm implementation details. Specifically: 1) How does the JMA or JAXA official fire detection product work for AHI data? 2) What are the AHI band specifications relevant to fire detection (Band 7 at 3.9μm, Bands 14-15 thermal IR)? 3) What is the spatial resolution and pixel size at different scan angles, particularly over eastern Australia (Sydney/NSW ~33.5°S, 151°E)? 4) How does the Himawari Standard Data (HSD) format work - file structure, segments, how to read it programmatically? 5) What open-source implementations exist for processing AHI fire detection (e.g., satpy, pytroll)? 6) How does AHI fire detection performance compare to GOES ABI FDC? 7) What is the actual data latency from observation to availability on AWS or JMA servers? 8) Are there any published validation studies of AHI fire detection over Australia?

Here’s a structured answer to your eight questions, with more technical detail in the attached report.

## 1. How the official JMA / JAXA AHI fire products work

### JAXA Himawari‑8 Wild Fire product (L2WLF)

JAXA/EORC’s Level‑2 Wild Fire (L2WLF) product detects hotspots and retrieves FRP from Himawari‑8 AHI IR imagery on a 0.02° grid (≈2 km at nadir).[^1_1][^1_2]

Core pieces of the algorithm (from the official JAXA README):

- **Detection band:** Uses AHI **Band 7 (3.9 µm)** brightness temperature $T_{3.9}$ as the primary fire‑sensitive channel.[^1_1]
- **Background temperature:** Computes background from the **10.4–10.8 µm window band** (Band 13/14) over an **11×11 pixel neighborhood** surrounding each grid cell.[^1_2][^1_1]
- **Hotspot test:** Flags hotspots based on the **normalized deviation of $T_{3.9}$** from the local background temperature derived from 10.8 µm pixels in that neighborhood.[^1_1]
- **FRP retrieval:** Uses a **bi‑spectral method** combining radiances in **Band 6 (2.3 µm)** and **Band 7 (3.9 µm)** to estimate fire radiative power per grid cell.[^1_1]
- **Output fields:** Per detected fire grid: ID, UTC time, center lat/lon, grid area, volcano count (within 3×3), fire “Level”, FRP, etc., written as CSV.[^1_1]


### JMA wildfire dataset (JMA‑Himawari fire product)

JMA distributes an **hourly wildfire dataset** derived from AHI using the **JAXA/EORC algorithm above**, on a 0.02° grid (≈2 km at nadir) covering 60°N–60°S, 80°E–160°W.[^1_3][^1_4][^1_2][^1_1]

- Provides hotspot **location and FRP** for the full disk, with **hourly temporal resolution**.[^1_3][^1_2]
- Detection is based on the contrast in brightness temperature between fire pixels and background; a **reliability level** is assigned using factors such as sun glint, solar angle and spatial variability in BT.[^1_2]
- Independent evaluation over China found raw JMA‑Himawari wildfire data had overall accuracies of ~54–59% (excluding omission error), with many false alarms from industrial heat sources; a regionally adapted NSMC algorithm improved this to 80–84%.[^1_4][^1_2]


## 2. AHI band specifications relevant to fire detection

AHI has 16 bands from visible to thermal IR with 0.5–2 km nadir sampling.[^1_5][^1_6][^1_7][^1_8]

The fire‑relevant bands are:


| Band | Center λ (µm) | Type | Nadir res. | Valid bits | Notes |
| :-- | :-- | :-- | :-- | :-- | :-- |
| 6 | ~2.26–2.30 | NIR / SWIR | 2 km | 11 | Used with 3.9 µm for FRP. [^1_5][^1_8][^1_1] |
| 7 | ~3.89 | MWIR (3.9 µm) | 2 km | 14 | Primary active fire band, also low cloud/fog. [^1_5][^1_9][^1_10] |
| 13 | ~10.4 | TIR window | 2 km | 12 | Background land/surface BT. [^1_5][^1_2] |
| 14 | ~11.2 | TIR window (SST/cloud) | 2 km | 12 | Used for SST \& cloud imaging. [^1_8][^1_10] |
| 15 | ~12.4 | TIR split‑window | 2 km | 12 | Used for split‑window, cloud/SST. [^1_8] |

Exact central wavelengths and valid bit depths are tabulated in the Himawari Standard Data User’s Guide v1.3 and in ESSD documentation of AHI bands.[^1_6][^1_5][^1_2]

Typical roles in fire algorithms:

- Band 7: detect sub‑pixel hot sources via high $T_{3.9}$ and large $T_{3.9} - T_{10/11}$.[^1_11][^1_2]
- Bands 13–14: provide “normal” surface temperature and contextual differences $T_7 - T_{13}$, $T_7 - T_{14}$.[^1_2]
- Band 6: used with Band 7 in the JAXA bi‑spectral FRP retrieval.[^1_1]


## 3. Spatial resolution and pixel size, including over Sydney/NSW

### Nominal sampling and full‑disk grid

From the HSD User’s Guide:[^1_12][^1_13][^1_5]

- Full disk IR bands (5–16): **5,500 × 5,500 pixels** at **2 km at the sub‑satellite point (SSP)**.
- Full disk VIS/NIR: band 3 at 0.5 km (22,000 × 22,000), bands 1,2,4 at 1 km (11,000 × 11,000).
- Sub‑satellite longitude is **140.7°E**; projection is normalized geostationary with parameters CFAC, LFAC, COFF, LOFF and satellite height 42,164 km in the header.[^1_9][^1_14][^1_13]


### Off‑nadir degradation

NOAA’s AHI SST documentation (ACSPO L2P) explicitly quantifies the growth of effective ground resolution with view zenith angle:[^1_15][^1_16]

- **2 km at nadir**,
- Degrading up to about **15 km** at **view zenith ≈ 67°** at disk edge (80°E–160°W, 60°S–60°N).

Sydney (33.5°S, 151°E) is well inside the full‑disk footprint and far from the limb, so its AHI IR pixels are somewhat larger than 2 km but well below the 15 km extreme at 67°. Published documentation does not tabulate a specific GSD at Sydney, but any precise value can be computed from the geostationary projection equations using the CFAC/LFAC/COFF/LOFF parameters in Block \#3.[^1_13][^1_9][^1_15]

### Segments and latitude bands

For distribution via HimawariCloud/HimawariCast, JMA divides full‑disk imagery into **10 north–south segments**, with approximate latitude bounds.[^1_10]

- Segment 8: ≈21°S–32°S; Segment 9: ≈32°S–47°S.[^1_10]
- Sydney (~33.5°S) falls near the boundary of segments 8–9, i.e., southern mid‑latitudes, where viewing angles and thus pixel inflation are moderate.[^1_10]


## 4. Himawari Standard Data (HSD): structure, segments, programmatic reading

### File naming and segmentation

Each HSD file name encodes satellite, time, band, area and segment:[^1_17][^1_18]

`HS_aaa_yyyymmdd_hhnn_Bbb_cccc_Rjj_Skkll.DAT`

- `aaa`: `H08` or `H09` (Himawari‑8/9).
- `yyyymmdd_hhnn`: start of 10‑minute “timeline” in UTC.
- `Bbb`: band number (`01`–`16`).
- `cccc`: `FLDK` (full disk), `JPee` (Japan Area obs no.), `R3ff` (target), `R4gg`/`R5ii` (landmarks).
- `Rjj`: nominal resolution at SSP: `05` 0.5 km, `10` 1 km, `20` 2 km, `40` 4 km.[^1_13]
- `Skkll`: segment `kk` of `ll` total segments (e.g., `S0110` = seg 1/10; `S0101` = no division).[^1_18][^1_17]

A full 10‑minute full‑disk scan is thus **16 bands × 10 segments = 160 HSD files**.[^1_19]

### Internal block layout

The Himawari Standard Format (v1.3) defines **12 blocks** per file: 11 header blocks plus one data block.[^1_20][^1_6]

Most important for implementation:

- **Block \#1 (Basic information):** satellite name, processing center, observation area, timeline time, obs start/end times (MJD), file creation time, quality flags, file name, total header/data length.[^1_21][^1_20]
- **Block \#2 (Data information):** number of bits per pixel (fixed 16), number of columns, number of lines, compression flag (0 none, 1 gzip, 2 bzip2).[^1_21][^1_9]
- **Block \#3 (Projection information):** sub‑satellite longitude 140.7°, CFAC/LFAC/COFF/LOFF, satellite distance 42,164 km, Earth radii and precomputed WGS‑84 constants.[^1_9]
- **Block \#5 (Calibration):** band number, central wavelength, valid bits, special count codes (65,535 error; 65,534 off‑Earth), linear count→radiance slope and intercept, Planck coefficients for radiance↔brightness‑temperature conversion (infrared bands), albedo conversion coefficient for VIS/NIR.[^1_14][^1_22]
- **Block \#7 (Segment info):** total segments, segment sequence number, first image line index for this segment.[^1_7][^1_23]
- **Block \#12 (Data block):** packed 16‑bit unsigned count values for all pixels (columns × lines).[^1_3]

Implementationally, you:

1. Read the header (Blocks 1–11) to get dimensions, projection, calibration.
2. Read Block 12, reshape to [lines, columns], mask special codes, then convert counts to radiance using the slope/intercept and then to BT via the Planck coefficients.[^1_22][^1_14]

### Reading with Satpy / Pytroll

Satpy’s `ahi_hsd` reader wraps all this:[^1_24][^1_14]

- Accepts a list of HSD filenames (`HS_H08_YYYYMMDD_...`) and groups them by time, band, segment.[^1_17][^1_24]
- Exposes calibrated BT or reflectance fields as xarray DataArrays on a geostationary projection grid, with metadata for nominal vs observation time in a `time_parameters` dictionary and `.attrs['start_time']`, `.attrs['end_time']`.[^1_14][^1_24]
- Optionally rounds “actual” satellite position to a consistent nominal position (`round_actual_position=True`), which helps registration between bands.[^1_14]

JMA also provides sample C/Fortran code on the MSC site demonstrating how to read HSD and convert to other formats.[^1_10]

## 5. Open‑source fire‑detection implementations for AHI

There is no widely used open‑source re‑implementation of the **official JAXA/JMA wildfire algorithm**, but there are several research‑grade implementations that operate on AHI data:

- **Satpy + custom algorithms:** Common pattern is to read Bands 7, 13–15 via Satpy and then implement contextual thresholding, MOD14‑style logic, or ML on top.[^1_25][^1_5][^1_24][^1_14]
- **AHI‑FSA (Fire Surveillance Algorithm):** A multi‑spatial‑resolution algorithm using MIR/TIR detections (Band 7) plus NIR/red reflectance to map firelines at 500 m; evaluated over Western Australia and the Northern Territory and intercompared with MODIS/VIIRS.[^1_26][^1_27][^1_28][^1_29]
- **Maeda \& Tonooka random‑forest early‑fire algorithm:** Modified MOD14 contextual tests + random forest using nine AHI bands, solar zenith angle and meteorology; trained and validated on Australian early‑stage fires from AHI + MOD14 data, achieving ~86% precision and ~93% recall.[^1_5][^1_25]
- **MSSTF deep learning model (Himawari‑8/9):** A 2025 model that integrates multi‑scale spatial–temporal features using attention CNNs and a Transformer; shows higher accuracy than JAXA wildfire products and releases code/data on GitHub.[^1_30]
- **H8‑FSR wildfire spread rate:** Uses sequences of AHI detections to compute near‑real‑time spread rates for events like the Esperance bushfires.[^1_31][^1_32]

So: Satpy/Pytroll gives robust I/O, reprojection and metadata; algorithmic pieces for fire detection are predominantly in the literature, with a few open‑sourced ML models and research codes rather than a single “official” community package.[^1_24][^1_30][^1_14]

## 6. AHI fire detection vs. GOES ABI FDC

### ABI Fire/Hot Spot Characterization (FDC)

The GOES‑R ABI Level‑2 **Fire/Hot Spot Characterization (FDC)** product:[^1_33][^1_34][^1_35]

- Uses **3.9 µm MIR** plus long‑wave window bands to create:
    - a **fire mask** (good, saturated, cloud‑contaminated, high/medium/low probability, non‑fire),
    - **fire temperature**, **fire area**, and **FRP** for each detected fire pixel.[^1_34][^1_33]
- Runs on a 2‑km fixed grid for full disk and regional domains with contextual, cloud and glint tests and temporal filtering.[^1_33][^1_34]


### Comparative validation (FDC vs FRP‑PIXEL on Himawari AHI)

A recent global validation compared GOES‑16/17 ABI FDC with **FRP‑PIXEL** products from GOES, Himawari AHI and MSG, using near‑simultaneous Landsat‑8 OLI detections as reference.[^1_36][^1_37][^1_38]

Main takeaways relevant to AHI vs ABI:

- For **high‑confidence fire pixels**, FRP‑PIXEL products (including Himawari‑8 AHI) show **low false alarm rates (~4–7%) and good detection** relative to Landsat.[^1_38]
- GOES ABI **FDC** detects **more fire pixels overall**, but its low‑confidence categories have **much higher false alarm rates**, up to ~30% in some classes, compared to FRP‑PIXEL.[^1_38]
- For matched confidence levels, **detection rates of high‑confidence FDC pixels are comparable to FRP‑PIXEL**, but FRP‑PIXEL offers a more conservative, lower‑false‑alarm approach.[^1_38]

In short: **AHI FRP‑PIXEL/JAXA‑style products trade some sensitivity for lower false alarms**, while **ABI FDC is more aggressive**, yielding higher detection at the cost of more screening for false positives.[^1_37][^1_38]

## 7. Observation‑to‑availability latency (JMA vs AWS)

### JMA HimawariCloud / HimawariCast

JMA timing diagrams show approximate latencies for full‑disk imagery:[^1_10]

- **HimawariCloud (HSD/HSF imagery):**
    - Level‑0 reception and Level‑1 processing: ~2–4 minutes after observation start.
    - Transfer to HimawariCloud vendor and staging: a few more minutes.
    - **First segment file typically ready to pull within ~7 minutes after observation start.**
    - **Last segment available within ~4–5 minutes after observation end**, i.e. ~12–15 minutes after start for a 10‑minute full‑disk scan.[^1_10]
- **HimawariCast (HRIT broadcast):**
    - First HRIT segment disseminated within ~8 minutes after observation start; last segment within ~7 minutes after observation end.[^1_10]

These are “peak time” values (around local noon near the equinox); actual latency will vary somewhat but gives the right order of magnitude.[^1_10]

### AWS / noaa‑himawari8 S3

NOAA’s NESDIS Common Cloud Framework ingests Himawari‑8 from JMA, performs security inspection, and pushes L1b and Level‑2+ products to the **noaa‑himawari8** S3 bucket and Registry of Open Data on AWS.[^1_39][^1_40][^1_41]

- Public messaging describes the service as **low latency and highly available**, handling ≈41,000 H8 files per day via this pipeline.[^1_41]
- Neither the AWS blog nor the noaa‑himawari8 registry entry provides a **numerical latency (in minutes)** from JMA ingestion to object appearance in S3.[^1_39][^1_41]
- NOAA STAR has built tooling explicitly to analyze latency of near‑real‑time satellite data (using Himawari‑8 HSD as an example), but published abstracts focus on methodology rather than a single latency metric.[^1_42]

So: JMA HimawariCloud/‑Cast typical latencies are ~7–15 minutes; AWS availability lags that by an additional, undocumented but generally small interval.[^1_41][^1_39][^1_10]

## 8. Published validation over Australia

There is a reasonably rich Australian validation and algorithm‑development literature around Himawari‑8 AHI:

- **Wickramasinghe et al. (2016):** Developed a multi‑spatial‑resolution algorithm using AHI MIR/TIR plus NIR/red to map firelines at 500 m in Western Australia; shows AHI can track firelines continuously at 10‑minute cadence.[^1_27][^1_26]
- **BNHCRC “Active fire detection using the Himawari‑8 satellite” final report (Jones et al., 2022):**
    - Assesses AHI noise characteristics in the fire‑sensitive bands.
    - Develops the **AHI‑FSA** and **BAT** methods and compares them against VIIRS hotspots and other products across Australia.[^1_43][^1_11]
- **AHI‑FSA intercomparison with MODIS/VIIRS:** Over ~1.4 million km² in the Northern Territory, AHI‑FSA achieved **~7% daily omission error** relative to MODIS while sometimes detecting fires **up to three hours before** the MODIS overpass.[^1_28][^1_29]
- **H8‑FSR (Near real‑time wildfire spread rate from Himawari‑8):** Demonstrates that spread rates can be retrieved for Australian bushfires (e.g., Esperance) by tracking fire centroids in time using AHI detections.[^1_32][^1_31]
- **Global geostationary validation including AHI:** The GOES‑16/17/MSG/Himawari FRP‑PIXEL/FDC validation includes AHI over its entire disk, including Australian regions, and finds good detection performance with low false alarms when using appropriate confidence classes.[^1_36][^1_37][^1_38]

Collectively, these studies support the conclusion that **Himawari‑8/9 AHI can provide operationally useful, validated active‑fire information over Australia**, particularly when using algorithms tuned to Australian fuels and backgrounds (e.g., AHI‑FSA, BAT, or ML‑based approaches).[^1_29][^1_26][^1_27][^1_28][^1_11]

***

All of this is pulled together with more detail, band tables, and citations in the attached markdown report “Himawari‑8/9 AHI Wildfire Detection: Algorithms, Bands, Geometry, Data Formats, Implementations, and Validation.”
<span style="display:none">[^1_100][^1_44][^1_45][^1_46][^1_47][^1_48][^1_49][^1_50][^1_51][^1_52][^1_53][^1_54][^1_55][^1_56][^1_57][^1_58][^1_59][^1_60][^1_61][^1_62][^1_63][^1_64][^1_65][^1_66][^1_67][^1_68][^1_69][^1_70][^1_71][^1_72][^1_73][^1_74][^1_75][^1_76][^1_77][^1_78][^1_79][^1_80][^1_81][^1_82][^1_83][^1_84][^1_85][^1_86][^1_87][^1_88][^1_89][^1_90][^1_91][^1_92][^1_93][^1_94][^1_95][^1_96][^1_97][^1_98][^1_99]</span>

<div align="center">⁂</div>

[^1_1]: https://www.eorc.jaxa.jp/ptree/documents/README_H08_L2WLF.txt

[^1_2]: https://essd.copernicus.org/preprints/essd-2022-435/essd-2022-435.pdf

[^1_3]: https://essd.copernicus.org/preprints/essd-2022-435/essd-2022-435-manuscript-version3.pdf

[^1_4]: https://essd.copernicus.org/articles/15/1911/2023/

[^1_5]: https://www.eoportal.org/satellite-missions/himawari-8-9

[^1_6]: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/spsg_ahi.html

[^1_7]: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/hsd_sample/HS_D_users_guide_en_v13.pdf

[^1_8]: http://www.bom.gov.au/australia/satellite/himawari.shtml

[^1_9]: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/hsd_sample/HS_D_users_guide_en

[^1_10]: https://www.data.jma.go.jp/mscweb/en/aomsuc6_data/oral/st1-02.pdf

[^1_11]: https://www.preventionweb.net/publication/active-fire-detection-using-himawari-8-satellite-final-project-report

[^1_12]: https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc%3AGHRSST-AHI_H08-STAR-L2P

[^1_13]: https://data.nasa.gov/w/aszi-izfx/default?cur=JMTWIRLz2fB\&from=1RwKF5vbwEG

[^1_14]: https://stackoverflow.com/questions/70515790/why-do-i-using-satpy-on-himawari-8-standard-data-failed

[^1_15]: https://www.wis-jma.go.jp/cms/gisc_tokyo/workshop/file/2014/lesson15_ws2014.pdf

[^1_16]: https://satpy.readthedocs.io/en/stable/api/satpy.readers.ahi_hsd.html

[^1_17]: https://satpy.readthedocs.io/en/latest/api/satpy.readers.ahi_hsd.html

[^1_18]: https://pmc.ncbi.nlm.nih.gov/articles/PMC9823964/

[^1_19]: https://ouci.dntb.gov.ua/en/works/9GrQVP3l/

[^1_20]: https://ui.adsabs.harvard.edu/abs/2016RemS....8..932W/abstract

[^1_21]: https://doaj.org/article/08a838b704fa49468703b210f7ee32cb

[^1_22]: https://www.tandfonline.com/doi/abs/10.1080/17538947.2018.1527402

[^1_23]: https://modis.gsfc.nasa.gov/sci_team/pubs/abstract_new.php?id=70582

[^1_24]: https://www.academia.edu/78317514/Near_Real_Time_Extracting_Wildfire_Spread_Rate_from_Himawari_8_Satellite_Data

[^1_25]: https://pdfs.semanticscholar.org/c8e3/5db134a5c87ad28c7797bd9313fcd33e9db8.pdf

[^1_26]: https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC01520

[^1_27]: https://www.ncei.noaa.gov/sites/default/files/2022-11/GOES-18_ABI_L2_FDC_Provisional_ReadMe.pdf

[^1_28]: https://developers.google.com/earth-engine/datasets/catalog/NOAA_GOES_19_FDCC

[^1_29]: https://developers.google.com/earth-engine/datasets/catalog/NOAA_GOES_19_FDCF

[^1_30]: https://catalog.data.gov/dataset/noaa-goes-r-series-advanced-baseline-imager-abi-level-2-fire-hot-spot-characterization-fdc3

[^1_31]: https://geog.umd.edu/sites/geog.umd.edu/files/pubs/Geostationary active fire products validation GOES 17 ABI GOES 16 ABI and Himawari AHI.pdf

[^1_32]: https://www.tandfonline.com/doi/full/10.1080/01431161.2023.2217983

[^1_33]: https://repository.library.noaa.gov/view/noaa/53332/noaa_53332_DS1.pdf

[^1_34]: https://registry.opendata.aws/noaa-himawari/

[^1_35]: https://noaa-himawari8.s3.amazonaws.com/README.txt

[^1_36]: https://aws.amazon.com/blogs/publicsector/himawari-8-enabling-access-key-weather-data/

[^1_37]: https://ui.adsabs.harvard.edu/abs/2016AGUFMIN41C1674H/abstract

[^1_38]: https://isprs-archives.copernicus.org/articles/XLI-B8/65/2016/isprs-archives-XLI-B8-65-2016.pdf

[^1_39]: https://www.naturalhazards.com.au/crc-collection/downloads/active_fire_detection_using_the_himawari-8_satellite_final_project_report.pdf

[^1_40]: https://essd.copernicus.org/articles/15/1911/2023/essd-15-1911-2023.pdf

[^1_41]: https://pdfs.semanticscholar.org/96e1/ae17bc27fe4515a33ef03dbf0e82989dd558.pdf

[^1_42]: https://groups.google.com/g/pytroll/c/Ht9-9-XPIKk

[^1_43]: https://essd.copernicus.org/articles/15/1911/2023/essd-15-1911-2023.html

[^1_44]: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/hsd_sample/HS_D_users_guide_en_v12.pdf

[^1_45]: https://www.typhooncommittee.org/docs/roving_seminar/2018/2018_A_Yamashita.pdf

[^1_46]: https://repository.library.noaa.gov/view/noaa/62006/noaa_62006_DS1.pdf

[^1_47]: https://www.sciencedirect.com/science/article/pii/S1569843225000639

[^1_48]: https://en.wikipedia.org/wiki/Himawari_8

[^1_49]: https://www.weather.gov/media/hfo/hpaws/Japan Meteorological Agency's Himawari Satellite Products for Aviation Users - Tomohiro Nozawa.pdf

[^1_50]: https://www.ospo.noaa.gov/data/messages/2021/03/MSG_20210330_1314.html

[^1_51]: https://www.naturalhazards.com.au/crc-collection/downloads/near_real-time_extracting_wildfire_spread_rate_from_himawari-8_satellite_da.pdf

[^1_52]: https://podaac.jpl.nasa.gov/dataset/AHI_H08-STAR-L3C-v2.70

[^1_53]: https://www.science.org/doi/10.1126/sciadv.adh0032

[^1_54]: https://repository.library.noaa.gov/view/noaa/43920

[^1_55]: https://www.data.jma.go.jp/mscweb/en/oper/eventlog/20161117_Quality_improvement_of_Himawari-8_observation_data.pdf

[^1_56]: https://aws.amazon.com/marketplace/pp/prodview-eu33kalocbhiw

[^1_57]: https://research.utwente.nl/en/publications/large-area-validation-of-himawari-8-fire-active-fire-products

[^1_58]: https://www.jstage.jst.go.jp/article/jmsj/103/1/103_2025-005/_html/-char/ja

[^1_59]: https://ui.adsabs.harvard.edu/abs/2025RSEnv.31614491Z/abstract

[^1_60]: https://smythdesign.com/blog/georeferencing-himawari/

[^1_61]: https://essd.copernicus.org/preprints/essd-2023-414/essd-2023-414-manuscript-version3.pdf

[^1_62]: https://www.sciencedirect.com/science/article/pii/S0303243420301434

[^1_63]: https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/XAERDT_L2_AHI_H08

[^1_64]: https://ceos.org/document_management/Working_Groups/WGCV/Meetings/WGCV-41/Presentations/CEOS-WGCV-41-AGR-02-JMA.pdf

[^1_65]: https://www.sciencedirect.com/science/article/pii/S0034425724005170

[^1_66]: https://cmr.earthdata.nasa.gov/opensearch/collections?boundingBox=\&clientId=our_html_ui\&endTime=\&satellite=Himawari-8\&spatial_type=bbox\&startTime=

[^1_67]: https://www.data.jma.go.jp/mscweb/en/himawari89/himawari_cast/Newsletter/HimawariCast_Newsletter_No.7.pdf

[^1_68]: https://www.reddit.com/r/australia/comments/a22yfb/i_had_no_idea_how_red_our_country_was_taken_from/

[^1_69]: https://space.oscar.wmo.int/satellites/view/himawari_8

[^1_70]: https://www.facebook.com/australianspaceagency/posts/️-the-satellite-that-monitors-rain-storms-and-cloud-cover-over-australia-also-to/1373204874851780/

[^1_71]: https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2021JD034906

[^1_72]: http://www.bom.gov.au/research/aomsuc-10/presentations/S1-P5-BESSHO.pdf

[^1_73]: https://researchonline.jcu.edu.au/71374/1/JCU_71374_Patricio-Valerio_2021_thesis.pdf

[^1_74]: https://registry.opendata.aws/tag/geospatial/

[^1_75]: https://acrs-aars.org/proceeding/ACRS2023/Poster I/ACRS2023126.pdf

[^1_76]: https://www.sciencedirect.com/science/article/pii/S0034425717300834

[^1_77]: https://satpy.readthedocs.io/en/latest/examples/

[^1_78]: https://ouci.dntb.gov.ua/en/works/lx3prqQ4/

[^1_79]: http://lightfield-forum.com/2012/08/lfp-file-reader-python-scripts-to-read-view-and-export-lytro-living-pictures/

[^1_80]: https://www.youtube.com/watch?v=9I5snThHkd0

[^1_81]: https://usda-fsa.github.io/fsa-design-system/getting-started/

[^1_82]: https://www.oreateai.com/blog/building-your-own-barcode-reader-with-python/e110796b05dd5087e4a9c0c264e90fdc

[^1_83]: https://github.com/pytroll/satfire

[^1_84]: https://github.com/hideki-saito/FSA

[^1_85]: https://github.com/pravodev/uhf-rfid-reader-sdk

[^1_86]: https://groups.google.com/group/pytroll/attach/8400de15b90de/atot-JTECH-D-22-0107.1.pdf?part=0.1

[^1_87]: https://www.linkedin.com/in/chathurahasanka

[^1_88]: https://github.com/amasud08/satellite-image-deep-learning

[^1_89]: https://stackoverflow.com/questions/56261178/cant-read-card-with-nfc-rfid-reader-through-python

[^1_90]: https://www.jma.go.jp/jma/en/photogallery/RDCAmeeting_202503/summary_report.pdf

[^1_91]: https://img.nsmc.org.cn/PORTAL/NSMC/DOC/CONFERENCE/AOMSUC/AOMSUC11/SESSION2/4-Sakashita.pdf

[^1_92]: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/hsd_sample/HS_D_users_guide_en_v11.pdf

[^1_93]: https://www.eorc.jaxa.jp/ptree/userguide.html

[^1_94]: https://www.data.jma.go.jp/mscweb/en/himawari89/cloud_service/cloud_service.html

[^1_95]: https://www.cgms-info.org/Agendas/PPT/CGMS-42-JMA-WP-09 PPT

[^1_96]: https://repository.library.noaa.gov/view/noaa/70963/noaa_70963_DS1.pdf

[^1_97]: https://www.data.jma.go.jp/mscweb/en/aomsuc12/presentation/S1_06.pdf

[^1_98]: https://www.eorc.jaxa.jp/ptree/faq.html

[^1_99]: https://himawari8.nict.go.jp

[^1_100]: https://www.cgms-info.org/Agendas/GetWpFile.ashx?wid=4233907a-e77d-4643-a36e-49ee9bca89f3\&aid=efe9d01a-8cba-4962-a740-1f4a4ceb9041

