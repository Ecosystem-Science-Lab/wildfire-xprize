# ECOSTRESS & High-Resolution Thermal Sensors for Wildfire Detection

Research compiled March 2026. Competition window: mid-April 2026, 2-week window, NSW Australia (~-28 to -37S, 148-154E).

---

## 1. ECOSTRESS Instrument Specifications

### Current Status (March 2026)
- **ECOSTRESS** (the original instrument, sometimes called "ECOSTRESS-1") is **still operational** on the ISS as of March 2026
- Approved for operations through FY2026, with potential continuation to FY2029 pending a 2026 Senior Review
- Current end-of-life estimate: January 2031 (tied to ISS lifetime)
- There is **no ECOSTRESS-2** — no upgraded replacement has been announced or launched
- Over 610,000 scenes acquired since launch (June 2018)
- Data quality note: May 15 – July 1, 2025 had noisier-than-expected data (resolved by cycling the payload)
- Version 1 data products were decommissioned May 2025; all current products are **Collection 2 (V002)**

### Radiometer: PHyTIR (Prototype HyspIRI Thermal Infrared Radiometer)

| Parameter | Specification |
|---|---|
| **Spectral bands** | 6 total (5 TIR + 1 SWIR) |
| Band 1 (SWIR) | 1.660 um — cloud detection and geolocation |
| Band 2 (TIR) | 8.285 um |
| Band 3 (TIR) | 8.785 um |
| Band 4 (TIR) | 9.060 um |
| Band 5 (TIR) | 10.522 um |
| Band 6 (TIR) | 12.001 um |
| **Native spatial resolution** | 38 m in-track x 69 m cross-track |
| **Product resolution** | Resampled to ~70 m x 70 m |
| **Swath width** | ~400 km (53 deg cross-track scan, meets >=360 km requirement even with ISS yaw up to +-18.5 deg) |
| **Scan mechanism** | Push-whisk mapper; double-sided scan mirror at 25.4 rpm |
| **Scan cycle** | 1.29 seconds per cross-track sweep (includes 2 blackbody calibration views at 300K and 340K) |
| **Cross-track pixels** | 256 per spectral channel |
| **Radiometric accuracy** | <=0.5 K at 300K (exceeds the <=1K requirement) |
| **Radiometric precision** | <=0.15 K at 300K (exceeds the <=0.3K requirement) |
| **Dynamic range** | 200–500 K |
| **Data rate** | 4.5 Mbit/s (X-band downlink) |
| **Mass / Power / Volume** | 490 kg / ~527 W / 1.3 m3 |

### Key Band Notes
- Three TIR bands align with ASTER thermal bands
- Two bands match ASTER/MODIS split-window applications
- All bands are in the LWIR (8–12.5 um) — **no MWIR (3–5 um) channel**
- This is a significant limitation for fire detection (see Section 6)

---

## 2. ISS Orbit Parameters

| Parameter | Value |
|---|---|
| Inclination | 51.6 deg |
| Altitude | ~400 km (range 385–415 km; varies with drag and reboosts) |
| Orbital period | ~92–93 minutes |
| Orbits per day | ~15.5–15.9 |
| Ground track shift per orbit | ~22.9 deg westward (at equator) |
| Approximate ground track repeat | Every ~3 days |
| Illumination cycle | ~63-day cycle through descending/ascending, day/night passes |
| Orbit type | Non-sun-synchronous (observation times vary) |
| Latitude coverage | 52 deg N to 52 deg S |

### Implications for NSW Coverage (-28 to -37S)
- NSW is well within the ISS coverage band (51.6 deg inclination)
- At latitudes 28–37S, the ISS passes are relatively frequent because the orbit tracks converge at higher latitudes
- The ISS crosses these latitudes on both ascending (SW to NE) and descending (NW to SE) passes
- Due to the non-sun-synchronous orbit, overpass times change from day to day, cycling through all local times over ~63 days
- This means some overpasses will be at night (advantageous for thermal fire detection — lower background temperature, higher contrast)

---

## 3. ECOSTRESS Revisit and Coverage

### Revisit Frequency
- **1–5 day revisit** for a given location, depending on latitude
- Typical: **90% of CONUS covered every 4 days** (similar latitudes to NSW)
- Some areas can be observed multiple times in a single day at higher latitudes where tracks converge
- The 400 km swath width helps — adjacent orbits have overlapping or near-overlapping swaths
- Approximate 3-day repeat cycle for ground tracks, but exact repeat depends on altitude

### Coverage Constraints
- **Bandwidth-limited**: ECOSTRESS acquires data faster than it can downlink (4.5 Mbit/s X-band)
- The **CLASP algorithm** (Compressed Large-scale Activity Scheduler and Planner) manages acquisition priorities
- Highest-priority targets get ~3+ acquisitions per week
- Lowest-priority targets: captured at least once per month
- Australia is NOT a primary ECOSTRESS target (CONUS is the primary focus)
- **Critical question**: Whether NSW falls within ECOSTRESS's acquisition schedule during April 2026 is uncertain. It may be acquired opportunistically rather than systematically

### Diurnal Sampling Advantage
- Unlike sun-synchronous satellites (fixed overpass time), ECOSTRESS samples at varying times of day
- This means some passes will be during afternoon peak fire activity, some at night
- Night passes are particularly valuable for fire detection: lower background temperature = higher thermal contrast

---

## 4. Predicting ECOSTRESS Overpasses for April 2026

### What Can Be Predicted

**Orbital mechanics (predictable):**
- ISS inclination (51.6 deg) — fixed
- Orbital period (~92–93 min) — varies slightly with altitude
- General coverage pattern over NSW latitudes — ISS will definitely pass over NSW multiple times per day

**What CANNOT be predicted 13 months in advance:**
- Exact overpass times and ground tracks — TLE-based predictions degrade within days
- ISS reboosts occur ~monthly and unpredictably shift the orbit; after a reboost, TLE parameters need ~2 days to settle, and predictions can be off by 5–10% in longitude/time
- Atmospheric drag (tied to solar activity) affects altitude and orbital period unpredictably
- ECOSTRESS acquisition scheduling (CLASP) decisions are made operationally, not months ahead

### TLE Propagation Accuracy
- **1–2 days**: ~1 km position accuracy (useful for planning)
- **2–3 days**: 20–70 km 1-sigma error (still usable for swath prediction given 400 km swath)
- **1 week+**: Rapidly degrading, hundreds of km error
- **Months ahead**: Completely unreliable for specific overpass timing

### Prediction Approach for April 2026
1. **Now (13 months out)**: Can only estimate statistical coverage patterns. Expect 1–5 day revisit, multiple overpasses per day over NSW, with ~3-day ground track quasi-repeat
2. **1–2 weeks before competition**: Obtain fresh TLEs from Celestrak/Space-Track.org. Use pyorbital, orbit-predictor, or passpredict (Python libraries) to propagate forward ~5–7 days with reasonable accuracy
3. **During competition**: Update TLEs daily. Predictions accurate to minutes for 1–2 days ahead; after any reboost, wait ~2 days for TLEs to stabilize
4. **N2YO.com**: Real-time ISS tracking and near-term pass predictions
5. **ESA EVDC Orbit Prediction Tool**: https://evdc.esa.int/orbit/ — can generate overpass predictions for any location/time period
6. **NASA Spot The Station**: https://spotthestation.nasa.gov/ — simple ISS pass predictions

### Tools for Overpass Prediction
- **pyorbital** (Python): `pip install pyorbital` — TLE propagation, `get_lonlatalt()` for position, can calculate overpass geometry
- **orbit-predictor** (Python, by Satellogic): TLE-based orbit propagation
- **passpredict** (Python): Built on orbit-predictor with optimized Cython functions
- **Celestrak** (https://celestrak.org/): TLE source, updated frequently
- **Space-Track.org**: Official US DoD TLE repository (requires free registration)

### Statistical Expectation for April 2026
- ISS will pass over NSW roughly **3–6 times per day** (considering the full latitude range -28 to -37S)
- Of these, perhaps **1–3 will be with ECOSTRESS actively imaging** (bandwidth constraints)
- Over a 2-week window, expect roughly **7–20 usable ECOSTRESS scenes** of the competition area, IF NSW is in the acquisition schedule
- Overpass times will be distributed across all hours of day/night

---

## 5. ECOSTRESS Data Access and Latency

### Data Distribution
- **Primary archive**: NASA LP DAAC (Land Processes DAAC)
- **Search**: NASA Earthdata Search (https://search.earthdata.nasa.gov/)
- **API access**: NASA CMR (Common Metadata Repository)
- **Analysis-ready**: AppEEARS (https://appeears.earthdatacloud.nasa.gov/) — subsetting, reprojection, visualization
- **Code resources**: https://github.com/nasa/ECOSTRESS-Data-Resources
- **Collection 2 code**: https://github.com/ECOSTRESS-Collection-2

### Data Products (Collection 2 / V002)
| Level | Product | Description |
|---|---|---|
| L1B | ECO1BRAD | Calibrated at-sensor radiance (5 TIR bands) |
| L1B | ECO1BMAPRAD | Resampled radiance (70m grid) |
| L2 | ECO_L2_LSTE | Land Surface Temperature & Emissivity |
| L2 | ECO_L2_CLOUD | Cloud mask |
| L3 | ECO_L3T_JET | Evapotranspiration (tiled) |
| L4 | ECO_L4T_ESI | Evaporative Stress Index |
| L4 | ECO_L4T_WUE | Water Use Efficiency |

### Data Latency — CRITICAL LIMITATION
- **No near-real-time product exists for ECOSTRESS**
- Original design specification: **12 weeks** from observation to Level 1 availability, then 12 weeks per subsequent level
- In practice, latency has varied from days to weeks, with historical episodes of multi-week delays (e.g., summer 2020 network issues caused several-week delays)
- The ISS downlinks via TDRS relay (near-continuous contact) or direct X-band, but ECOSTRESS's 4.5 Mbit/s rate means data queuing
- **Bottom line for competition**: ECOSTRESS data will almost certainly NOT be available in time for real-time fire detection during the competition. Historical data could inform pre-fire fuel condition mapping (via ESI/WUE products), but active fire detection from ECOSTRESS is not operationally feasible

---

## 6. ECOSTRESS for Fire Detection

### The TIR vs. MWIR Problem
ECOSTRESS operates at 8–12.5 um (LWIR/TIR). Most operational fire detection systems use the MWIR band at ~3.9 um (MODIS Band 21/22, VIIRS I4/M13). The physics:

- **MWIR (3–5 um)**: Fire signal is ~1 order of magnitude stronger than background. A sub-pixel fire covering even 0.01% of a 1 km pixel produces a detectable signal at 3.9 um
- **TIR (8–12 um)**: Fire signal is only marginally above background. The radiance contrast between a 600K fire pixel fraction and a 300K background is much smaller at 10 um than at 4 um (Wien's law: peak emission shifts to shorter wavelengths at higher temperatures)

### What ECOSTRESS CAN Detect
- The 70m pixel size partially compensates for the spectral disadvantage
- A fire filling a significant fraction of a 70m x 70m pixel (~0.5 ha) would elevate the pixel temperature noticeably above background
- ECOSTRESS has been successfully used to track large active wildfires (e.g., the 2021 Bootleg Fire)
- The **RADR-Fire tool** (Pacific Northwest National Lab) incorporates ECOSTRESS data for tracking fire fronts
- ECOSTRESS's 200–500K dynamic range means it won't saturate on fire pixels (unlike some sensors that saturate at 350K)
- TIR has an advantage: **smoke is relatively transparent at 8–12 um**, so fires obscured by their own smoke are still visible

### What ECOSTRESS CANNOT Do Well
- Detect small fires (sub-hectare) — the TIR spectral response makes sub-pixel fire detection much harder than with MWIR
- Provide real-time fire alerts — data latency is days to weeks
- Compete with MWIR-based systems (VIIRS, MODIS, OroraTech, FireSat) for fire detection sensitivity

### Minimum Detectable Fire Size (Estimate)
- No published threshold specific to ECOSTRESS
- For a 70m pixel in the TIR: a fire needs to occupy enough of the pixel to raise the integrated temperature by at least ~2–3K above background (given 0.5K accuracy)
- A 1000K fire occupying ~1% of a 70m pixel (~50 m2) would raise pixel temperature by ~7K at 10.5 um — detectable
- A fire covering ~0.5% (~25 m2) might produce ~3K anomaly — marginally detectable
- At MWIR, the same 25 m2 fire would produce a much stronger signal
- **Conservative estimate**: ECOSTRESS can detect fires of ~500–2500 m2 (0.05–0.25 ha) depending on fire temperature and background conditions

### ECOSTRESS Value Proposition for Wildfire Competition
- **Pre-fire fuel condition mapping**: ESI (Evaporative Stress Index) and WUE (Water Use Efficiency) data can identify drought-stressed vegetation. Research showed WUE > 2 g C/kg H2O correlated with 95% probability of vegetation burning in Australia's Black Summer
- **Post-event analysis**: High-resolution thermal maps of burn severity
- **NOT suitable for real-time fire detection** due to data latency and TIR spectral limitations

---

## 7. ECOSTRESS Pointing and Footprint

### Scan Geometry
- ECOSTRESS uses a **rotating scan mirror** (not ISS platform pointing)
- The mirror sweeps 53 deg across nadir in the cross-track direction
- This produces a continuous swath of ~400 km width
- There is NO independent pointing capability — ECOSTRESS observes whatever is beneath its swath
- The ISS can perform attitude maneuvers, but these are not done for ECOSTRESS targeting

### Footprint Characteristics
- At nadir: 38m x 69m pixels
- At swath edges: pixels become larger and more distorted due to increased path length and oblique viewing angle
- Products are resampled to uniform 70m x 70m grid
- No significant resolution degradation across most of the swath (the scan mirror maintains near-constant angular rate)

### Effective Coverage Width
- The 400 km swath width means NSW (roughly 6 deg longitude = ~530 km at -33S) can be partially or fully covered in a single pass depending on the ground track
- Adjacent orbits (shifted by ~22.9 deg longitude at equator, less at -33S latitude) will have overlapping or gap-filling coverage

---

## 8. Other High-Resolution Thermal Sensors

### Currently Operational (April 2026)

#### Landsat 8 & 9 (TIRS)
| Parameter | Specification |
|---|---|
| Thermal bands | Band 10: 10.6–11.2 um; Band 11: 11.5–12.5 um |
| Native resolution | 100 m (resampled to 30 m in products) |
| Revisit | 8 days (combined L8+L9) |
| Fire detection | **YES** — Landsat Fire and Thermal Anomaly (LFTA) product in FIRMS |
| **Latency** | **~30 minutes from overpass to FIRMS availability** |
| Swath | 185 km |
| Orbit | Sun-synchronous, ~10:00 AM descending node |
| Limitation | Fixed overpass time (morning only), 8-day revisit, TIR bands only (no MWIR) |
| **Relevance** | LFTA in FIRMS is operationally useful for the competition — 30m active fire data within 30 min. But 8-day revisit and morning-only passes limit utility |

#### OroraTech Wildfire Constellation (launched March 2025)
| Parameter | Specification |
|---|---|
| Satellites | 8 x 8U CubeSats (another 8 planned late 2025) |
| Bands | MWIR + LWIR (dual-band — optimal for fire detection) |
| Detection threshold | Fires as small as ~4m x 4m |
| Orbit | 550 km |
| Alert latency | ~3 minutes from detection to alert (onboard AI + Spire ground network) |
| Revisit target | 30-minute revisit (full constellation) |
| **Relevance** | **Highly relevant** — MWIR+LWIR dual band, onboard AI processing, minute-scale alerts. However, this is a commercial service; data access/pricing unclear for competition use |

#### Satellite Vu (HotSat)
| Parameter | Specification |
|---|---|
| Resolution | 3.5 m MWIR (highest resolution commercial thermal) |
| Status | HotSat-1 failed Dec 2023. HotSat-2 and HotSat-3 planned for 2025 launches |
| Capability | Video-rate thermal imaging |
| **Relevance** | If operational by April 2026, extremely high resolution thermal. Commercial service, access uncertain |

### Launching in 2026 (Likely NOT Available for April 2026)

#### FireSat (Muon Space / Earth Fire Alliance)
| Parameter | Specification |
|---|---|
| Instrument | 6-band multispectral IR (visible through LWIR) |
| Resolution | ~80 m average GSD |
| Swath | 1,500 km |
| Detection | Fires as small as 5m x 5m |
| Timeline | First 3 operational satellites in **mid-2026** |
| Full constellation | 50+ satellites by 2030, every point on Earth every 20 minutes |
| **Relevance** | Almost certainly NOT operational by April 2026. The protoflight satellite launched March 2025 and delivered first light images in June 2025, but operational constellation is mid-2026 at earliest |

### Future Missions (NOT Available for April 2026)

#### TRISHNA (CNES/ISRO)
- 57 m resolution, 4 TIR bands, 3-day revisit
- Launch: late 2026 or possibly 2027 — **not available for competition**

#### LSTM (ESA Copernicus)
- 50 m resolution thermal
- Launch: 2028 — **not available**

#### SBG-TIR (NASA/ASI)
- ECOSTRESS successor concept
- Launch: 2029 — **not available**

### Decommissioned

#### ASTER TIR (on Terra)
- **ASTER TIR was turned off January 16, 2026** to manage Terra power margins
- 90 m thermal resolution was excellent, but no longer collecting thermal data
- ASTER VNIR resumed Feb 9, 2026, but TIR is permanently off
- **Not available for competition**

---

## 9. Summary: Thermal Sensor Availability for NSW April 2026

| Sensor | Resolution | Bands | Revisit over NSW | Latency | Fire Detection | Available? |
|---|---|---|---|---|---|---|
| **ECOSTRESS** | 70 m | TIR only (8–12.5 um) | 1–5 days | Days–weeks | Marginal (TIR only) | Yes, but uncertain coverage |
| **Landsat 8/9 LFTA** | 30 m | TIR (10.6–12.5 um) | 8 days combined | **30 min** | Yes (via FIRMS) | Yes |
| **OroraTech** | ~200 m (est.) | MWIR + LWIR | ~30 min (target) | **3 min** | Yes (optimized) | Yes (commercial) |
| **Satellite Vu** | 3.5 m | MWIR | TBD | TBD | Yes | Uncertain |
| **FireSat** | 80 m | 6-band IR | Twice daily (3 sats) | Minutes (target) | Yes (optimized) | Unlikely (mid-2026) |
| **VIIRS** (reference) | 375 m | MWIR + TIR | ~6 hrs (2 sats) | **3 hrs (NRT)** | Yes (FIRMS standard) | Yes |
| **MODIS** (reference) | 1 km | MWIR + TIR | ~6 hrs (2 sats) | **3 hrs (NRT)** | Yes (FIRMS standard) | Yes |

---

## 10. Recommendations for Competition

### ECOSTRESS Assessment
- **Do not rely on ECOSTRESS for real-time fire detection**. The data latency (days to weeks) and TIR-only bands make it unsuitable for the competition's detection requirements
- **Pre-competition value**: ECOSTRESS ESI/WUE products from preceding weeks could map drought-stressed vegetation to identify high-risk areas, informing where to focus monitoring efforts
- **Overpass prediction**: Use pyorbital + fresh TLEs starting ~1 week before competition to predict ECOSTRESS overpasses, but do not expect data to be available in time for scoring

### Better Thermal Options for the Competition
1. **Landsat LFTA via FIRMS**: 30m fire detection, 30-minute latency. The 8-day revisit is a limitation, but if a Landsat pass coincides with a fire, this is high-resolution near-real-time thermal data
2. **OroraTech**: If accessible (commercial), this is the most capable thermal fire detection system currently in orbit — MWIR+LWIR, minute-scale alerts, sub-hectare detection
3. **VIIRS/MODIS via FIRMS**: Lower resolution but operationally proven, 3-hour NRT latency, global coverage every ~6 hours

### Orbit Prediction: What We Can Know When
| Timeframe | What's knowable |
|---|---|
| Now (13 months out) | Statistical coverage patterns only. ISS will pass over NSW. We cannot predict specific times |
| 1 month before | General orbital phase (whether overpasses are day/night). Still cannot predict exact times |
| 1 week before | Reasonably accurate overpass predictions (within ~10 min, ~50 km) using current TLEs |
| 2 days before | Accurate to within a few minutes and a few km |
| Day-of | Precise predictions available from N2YO.com, Celestrak, pyorbital |
| After reboost | Wait 2 days for TLEs to settle before trusting predictions |

---

## Sources

- [ECOSTRESS Instrument — JPL](https://ecostress.jpl.nasa.gov/instrument)
- [ECOSTRESS on eoportal.org](https://www.eoportal.org/satellite-missions/iss-ecostress)
- [ECOSTRESS Spectral Bands — NASA Earthdata](https://www.earthdata.nasa.gov/data/instruments/ecostress/spectral-bands)
- [ECOSTRESS Data Products — NASA Earthdata](https://www.earthdata.nasa.gov/data/instruments/ecostress)
- [ECOSTRESS Wildfire Response Tool — NASA](https://www.nasa.gov/earth/climate-change/ecostress-data-incorporated-into-new-wildfire-response-tool/)
- [ECOSTRESS Wildfire Prediction — NASA Earthdata](https://www.earthdata.nasa.gov/learn/data-in-action/ecostress-data-offer-significant-potential-wildfire-prediction-analysis)
- [ECOSTRESS FAQ (PDF)](https://ecostress.jpl.nasa.gov/downloads/faq/ECOSTRESS_FAQ_20240401.pdf)
- [ECOSTRESS Data Resources — GitHub](https://github.com/nasa/ECOSTRESS-Data-Resources)
- [ISS Orbit Tutorial — NASA JSC](https://eol.jsc.nasa.gov/Tools/orbitTutorial.htm)
- [Pyorbital Documentation](https://pyorbital.readthedocs.io/en/latest/)
- [orbit-predictor — PyPI](https://pypi.org/project/orbit-predictor/)
- [ESA EVDC Orbit Prediction Tool](https://evdc.esa.int/orbit/)
- [N2YO Real-Time Satellite Tracking](https://www.n2yo.com/)
- [Celestrak](https://celestrak.org/)
- [Terra Mission Adjustments — NASA](https://science.nasa.gov/blogs/science-news/2026/02/12/terra-adjusts-instrument-operations-to-extend-mission-life/)
- [TRISHNA Mission — eoportal](https://www.eoportal.org/satellite-missions/trishna)
- [OroraTech Wildfire Constellation — eoportal](https://www.eoportal.org/satellite-missions/ororatech-wildfire-constellation)
- [FireSat First Light — Muon Space](https://www.muonspace.com/press/muon-space-releases-first-light-images-from-firesat-protoflight)
- [Satellite Vu — SpaceNews](https://spacenews.com/satvu-aims-to-revive-thermal-imaging-business-in-2025-with-two-satellites/)
- [Landsat LFTA in FIRMS — NASA Earthdata](https://www.earthdata.nasa.gov/news/feature-articles/landsat-fire-thermal-anomaly-data-added-firms)
- [FIRMS Landsat Fire Description](https://firms.modaps.eosdis.nasa.gov/descriptions/FIRMS_Landsat_Firehotspots.html)
- [Wildfires Temperature Estimation with PRISMA/ECOSTRESS — Amici et al. 2022](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JG007055)
- [ECOSTRESS Black Summer Analysis — Zhu et al. 2025](https://zslpublications.onlinelibrary.wiley.com/doi/full/10.1002/rse2.422)
