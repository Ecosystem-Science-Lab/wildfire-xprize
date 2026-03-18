# Fire Detection Algorithms — Pitfalls

## False Positive Sources

### Sun glint
- Specular reflection off water, metal roofs, solar panels, glasshouses
- Worst at specific solar geometries (low sun angle + favorable view angle)
- In Australia: inland water bodies, farm dams, salt lakes are major sources
- Mitigation: glint angle calculation, reflectance thresholds, persistence tests

### Hot bare ground
- Australian outback surfaces can exceed 330 K in summer daytime
- Pushes BT4 above typical candidate thresholds
- Dark soils (low reflectance but high thermal emission) are particularly problematic
- Mitigation: scene-dependent BT4S, stronger ΔBT45 requirements, NDVI-based surface type masking

### Industrial heat sources
- Smelters, power stations, gas flares, mine sites
- Persistent hot spots that re-trigger every frame
- Australia has significant mining and industrial activity in fire-prone regions
- Mitigation: static industrial heat source database, persistence filtering (always hot ≠ new fire)

### Cloud edges and thin cirrus
- Cloud edges create mixed pixels with warm ground + cold cloud = anomalous BT patterns
- Thin cirrus can depress BT5 more than BT4, inflating ΔBT45
- Afternoon convective clouds in Australian summer are a major source
- Mitigation: conservative cloud buffer zones, split-window tests (BT11 - BT12)

### Volcanic activity
- Not a major concern for NSW, but relevant globally
- Active volcanic hotspots trigger fire algorithms
- Mitigation: volcanic activity database, persistence patterns differ from fires

## Algorithm-Specific Pitfalls

### VIIRS I4 saturation
- I4 saturates at only ~358-367 K — reached by moderate fires
- Saturation causes DN folding: extremely hot fires appear cold in I4
- Critical: must check quality flags (QF4) and implement folding detection
- Miss this and you'll miss the most intense fires

### Background window edge effects
- Near coastlines: water/land mixing in background window
- Near large fires: fire pixels contaminating background statistics
- Near cloud edges: insufficient valid background pixels
- Result: class 6 (unclassified) — information loss
- Mitigation: enforce same medium type, mask background fires, grow window

### Bow-tie effect (VIIRS)
- VIIRS pixel overlap at swath edges due to aggregation scheme
- Deleted pixels create gaps in coverage
- Background windows near swath edges may have insufficient valid pixels
- Impact: reduced detection at swath edges where pixels are also largest

### Geolocation accuracy
- VIIRS: typically <375 m (sub-pixel) but can be worse at swath edges
- Himawari AHI: 1-2 km at nadir, worse at high view angles (>2 km over Australia)
- Geolocation errors mean fire coordinates don't exactly match ground truth
- Impact on scoring: reported fire location may be offset from actual ignition point

## Australia-Specific Pitfalls

### Himawari view geometry over NSW
- Himawari-9 is at 140.7°E — NSW (Sydney 151°E, ~33.5°S) is off to the southeast
- View zenith angle over Sydney: ~40-45° — significant pixel enlargement
- 2 km nadir pixel becomes ~3-4 km effective at this angle
- Minimum detectable fire size increases proportionally
- Detection capability degrades compared to sub-satellite point (near equator, 140.7°E)

### Australian diurnal temperature cycle
- Summer ground temps in inland NSW can swing 30+ K diurnally
- Background statistics computed at one time may not represent conditions an hour later
- Fast-moving grass fires can start and spread significantly between 10-min Himawari scans
- Mitigation: time-of-day dependent thresholds, shorter temporal baselines

### Eucalypt fire behavior
- Crown fires in eucalypt forests are extremely intense (high FRP) but narrow fronts
- Fire spotting: embers carried km ahead of fire front create new ignitions
- Spot fires may be too small/brief for detection before merging with main fire
- Dense smoke can obscure thermal signal in IR bands, even at 3.9 μm
- Implications: very high-confidence on main front, but satellite may miss initial spotting

### Prescribed burning
- Extensive prescribed burning in NSW (mainly autumn/spring)
- These are real fires that should be detected but are not "wildfires"
- Competition scoring may or may not include prescribed burns
- Need to understand what the XPRIZE evaluators consider a "fire"

### Black Summer 2019-2020 as reference
- Extreme fire season across eastern Australia
- Massive smoke plumes affected detection algorithms globally
- Some fires were so large they created their own weather (pyrocumulonimbus)
- Provides excellent validation dataset but represents extreme conditions, not typical

## Performance Pitfalls

### Per-pixel loops are too slow
- A single Himawari full disk is ~5500×5500 pixels per band
- VIIRS granule is ~6400×3200 pixels
- Nested per-pixel contextual detection with growing windows: O(n² × w²)
- Must use vectorized operations (scipy uniform_filter, GPU) for production
- Target: full detection pass in <500 ms

### Memory with multiple bands
- Loading all bands at full resolution for a full disk scan: several GB
- If processing in-memory, need careful band management
- Tip: process in tiles/chunks, load only needed bands, release memory aggressively
- For Himawari: can process 10 segments independently then merge

### Threshold sensitivity
- Small changes in thresholds (e.g., 25 K → 27 K for ΔBT45) can dramatically change detection counts
- Always validate threshold changes against independent reference data
- Recommendation: maintain threshold configs as external parameters, not hardcoded
- Build A/B testing capability to compare threshold sets on archived data

### Temporal baseline drift
- Background statistics computed from historical data assume stable land surface
- After a fire: burned area has different thermal properties for months
- Seasonal vegetation changes affect background reflectance
- Mitigation: rolling baselines (30-90 day window), exclude known burned areas
