# Training Data Construction Strategies

## Overview

Building effective fire/no-fire training datasets requires careful matching of fire event records to satellite imagery, strategic sampling to handle extreme class imbalance, and domain-aware stratification for Australian conditions.

## 1. Positive Sample Construction

### FIRMS-to-Imagery Matching

The core approach: use FIRMS active fire detections as labels, then retrieve the corresponding satellite scene.

**Temporal matching rules:**
- FIRMS provides `Acq_Date` and `Acq_Time` (UTC) for each detection
- Match to satellite imagery acquired within the same overpass window (typically +/- 5 minutes for same-sensor, +/- 30 minutes for cross-sensor)
- For VIIRS-to-VIIRS matching, the acquisition time aligns directly since FIRMS VIIRS detections come from the same sensor
- For FIRMS-to-Sentinel-2 or FIRMS-to-Landsat matching, allow a wider temporal window (same day) but verify the fire was active during both acquisitions

**Spatial matching rules:**
- VIIRS 375m detections: center pixel +/- 375m (at nadir); pixels grow toward scan edges
- MODIS 1km detections: center pixel +/- 1km; significant geolocation uncertainty
- Buffer FIRMS points by 1-2x the pixel size for label generation
- For training patches (e.g., 256x256 at 10m = 2.56km), center on fire cluster centroids

**Confidence filtering:**
- Use only `nominal` and `high` confidence FIRMS detections for positive samples
- Low-confidence pixels frequently contain sun glint, industrial heat, or cloud-edge artifacts
- VIIRS has an undocumented issue: no low-confidence nighttime detections exist, meaning nighttime data is already filtered
- For MODIS, `confidence` is 0-100%; filter at >= 30% for nominal, >= 80% for high

### Multi-Source Label Fusion

Combine FIRMS active fire points with burned area products for richer labels:

```
Positive label hierarchy:
1. FIRMS active fire point (high confidence) = confirmed fire pixel at specific time
2. MCD64A1 BurnDate within +/- 1 day of imagery = recently burned pixel
3. FESM (NSW) burn severity > 0 within fire date range = ground-truth burned
4. dNBR > 0.27 (moderate-high severity) from pre/post Sentinel-2 = spectrally confirmed burn
```

### Patch Extraction Strategy

```
For each high-confidence FIRMS detection:
  1. Retrieve all FIRMS points within 5km radius on same date
  2. Compute cluster centroid
  3. Download satellite tile containing centroid
  4. Extract NxN patch centered on centroid
  5. Generate binary fire mask from all FIRMS points in patch
  6. Record: patch_id, center_lat, center_lon, acq_date, acq_time, sensor, fire_pixel_fraction
```

## 2. Negative Sample Construction

### Temporal Negatives (Same Location, No Fire)

- For each positive sample location, retrieve imagery from the same location 30-90 days before or after the fire
- Verify no FIRMS detections within 10km during the negative sample period
- Cross-check against MCD64A1 to ensure no burn date assigned
- Advantage: same terrain, vegetation, and atmospheric conditions; only fire presence changes

### Spatial Negatives (Different Location, Fire-Free)

- Sample from locations with no fire history in the NPWS/FIRMS record
- Prioritize locations with similar vegetation type and terrain to positive samples
- Include urban/industrial areas (common false positive sources) as hard negatives
- Include water bodies, bare soil, and agricultural stubble as easy negatives

### Hard Negative Mining

Critical for reducing false positives:
- **Sun glint patches**: Extract daytime imagery over bright/reflective surfaces where FIRMS low-confidence detections occurred but were not real fires
- **Industrial heat**: Steel mills, power plants, refineries -- persistent hot spots that FIRMS Type=2 (static land source) flags
- **Volcanic/geothermal**: Particularly relevant for NZ/Pacific, less so for NSW
- **Prescribed burns**: Can be either positive or negative depending on detection goals; NSW RFS records distinguish wildfire from prescribed burns
- **Post-fire smoldering**: Hot but no longer actively flaming; FIRMS may or may not detect

## 3. Class Balance Strategies

### The Imbalance Problem

In any satellite scene, fire pixels represent <1% of all pixels. At continental scale, <0.01% of pixels on any given day contain fire.

### Recommended Approaches

**Patch-level balancing:**
- Select patches such that ~50% contain at least one fire pixel
- Within fire-containing patches, fire pixels will still be a minority (2-20%)
- This is the most common approach in the literature

**Pixel-level weighting:**
- Apply inverse-frequency weighting to fire pixels in the loss function
- Typical weight ratio: 10:1 to 100:1 (fire:non-fire)
- Use focal loss (Lin et al., 2017) to down-weight easy negatives

**Oversampling fire events:**
- Replicate fire patches with augmentation (rotation, flip, brightness jitter)
- Each fire event can generate 4-8x samples via geometric augmentation
- Apply atmospheric augmentation (simulated haze, cloud shadows)

**Undersampling non-fire:**
- Randomly subsample non-fire patches to match fire patch count
- Risk: losing representative non-fire diversity
- Mitigate by stratified undersampling across land cover types

## 4. Geographic Stratification

### For NSW/Australia Focus

```
Stratification dimensions:
  1. Vegetation type: wet sclerophyll, dry sclerophyll, grassland, woodland, heath
  2. Terrain: coastal lowland, tablelands, western slopes, alpine
  3. Fire weather regime: subtropical (northern NSW), temperate (southern NSW)
  4. Season: spring (Sep-Nov), summer (Dec-Feb), autumn (Mar-May)
  5. Time of day: daytime vs nighttime (fire thermal signature differs)
```

### Cross-Geography Generalization

If training on global data to apply in NSW:
- Include substantial Australian fire samples (Black Summer provides ~thousands of FIRMS detections)
- Eucalypt fires behave differently from Northern Hemisphere conifer forests: higher fire intensity, more spotting, bark-strip firebrands
- Grassland fires in NSW western slopes move fast (up to 17 km/h) with lower FRP per pixel
- Weight Australian samples more heavily in training, or fine-tune a global model on Australian data

## 5. Temporal Stratification

### Fire Season Bias

- Most fire data is from October-March (Australian fire season)
- Training only on peak-season data will underperform on shoulder-season fires
- The competition is in April -- explicitly include autumn fire samples
- Prescribed burns (primarily autumn/winter in NSW) provide shoulder-season positive samples

### Diurnal Bias

- MODIS/VIIRS polar-orbiting satellites have fixed overpass times (~1:30am/pm local for VIIRS S-NPP)
- Fires peak in intensity in the afternoon (14:00-18:00 local)
- Morning overpasses may catch overnight burns that are less intense
- If using Himawari-8/9 (geostationary, 10-min cadence), sample across all hours

### Year-to-Year Variability

- Black Summer (2019-2020) was an extreme outlier; don't let it dominate the training set
- Include "normal" fire seasons for balanced representation
- Reserve specific years for validation (e.g., train on 2012-2018, validate on 2019-2020)

## 6. Validation Dataset Design

### Recommended Holdout: Black Summer 2019-2020 NSW

**Why:**
- Extensively mapped at high resolution (FESM 10m rasters)
- Thousands of FIRMS detections spanning months
- Diverse fire types: crown fires in wet sclerophyll, grassland fires, peat fires
- Well-documented timeline allowing temporal validation of detection latency

**Construction:**
1. Download FESM 2019/20 GeoTIFFs from SEED portal
2. Download all FIRMS VIIRS detections for NSW, Jul 2019 - Jun 2020
3. For each FIRMS detection, retrieve corresponding Sentinel-2 or Landsat scene
4. Label pixels using FESM severity classes as ground truth
5. Compute detection metrics: precision, recall, F1 at pixel level
6. Compute temporal metrics: how early before FIRMS did the model detect?

### Additional Validation Sets

- **Gospers Mountain fire (Oct-Jan 2019-2020)**: Single mega-fire, 512,000 ha, well-documented progression
- **Currowan fire (Nov 2019 - Feb 2020)**: Coastal NSW, complex terrain
- **2013 Blue Mountains fires**: Smaller event, good for testing on moderate-severity fires

## 7. Multi-Task Label Generation

For more sophisticated models, generate multiple label types per sample:

```
Per patch:
  - binary_fire: 0/1 (any fire in patch)
  - fire_mask: HxW binary mask of fire pixels
  - fire_fraction: float, proportion of fire pixels
  - burn_severity: categorical (unburnt, low, moderate, high) from FESM/dNBR
  - frp_map: HxW continuous FRP values from FIRMS
  - burn_date_map: HxW Julian day of burn from MCD64A1
  - fire_type: wildfire vs prescribed burn (from NPWS records)
```

## 8. Data Augmentation for Fire Detection

### Geometric Augmentations (Safe)
- Horizontal/vertical flip
- 90/180/270 degree rotation
- Random crop and resize

### Radiometric Augmentations (Use Carefully)
- Brightness/contrast jitter (simulates different atmospheric conditions)
- Additive Gaussian noise (simulates sensor noise)
- Simulated cloud/shadow overlay (critical for robustness)
- Band dropout (simulates missing spectral channels)

### Augmentations to AVOID
- Color space transforms designed for RGB (fire detection uses thermal/SWIR bands)
- Heavy spatial distortion (warps fire shape unrealistically)
- Mixing fire and non-fire patches (CutMix/MixUp can create unrealistic composites)
