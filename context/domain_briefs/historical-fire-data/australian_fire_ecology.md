# Australian Fire Ecology: NSW Context

## 1. Fire Seasons

### Typical Seasonal Pattern (NSW)

```
Jul  Aug  Sep  Oct  Nov  Dec  Jan  Feb  Mar  Apr  May  Jun
|-------|-------|-------|-------|-------|-------|
 Prescribed   Fire Season        Fire    Prescribed
 Burns       (Spring/Summer)     Season  Burns
 (Winter)                        Peak    (Autumn)
                                ^^^^
                            Dec-Feb Peak
```

- **Primary fire season**: October - March
- **Peak fire activity**: December - February
- **Prescribed burn windows**: March - May (autumn), June - August (winter) when conditions allow low-intensity burning
- **Competition timing**: April 2026 -- shoulder season between fire season end and autumn prescribed burns

### Black Summer 2019-2020 (Anomalous)

- Fire season started abnormally early (August 2019) due to record drought
- Peak burning: November 2019 - January 2020
- Key statistics for NSW:
  - 5.5 million hectares burned
  - 2,448 homes destroyed
  - 26 lives lost
  - >800 million animals estimated killed
- Unprecedented pyroconvective events (fire-generated thunderstorms)
- Fire spread rates exceeded all historical models
- Multiple fires merged into mega-fire complexes >500,000 ha

### Fire Weather Drivers

**Hot, dry, windy conditions:**
- Northwest winds ahead of cold fronts bring hot, dry air from interior
- Cold front passage causes rapid wind direction change (wind change fires)
- Foehn-effect winds on leeward slopes intensify fire behavior

**Drought:**
- Preceding drought is the strongest predictor of severe fire seasons
- KBDI (Keetch-Byram Drought Index) accumulates over weeks/months
- 2019 had the lowest rainfall on record for much of eastern NSW

**Climate modes:**
- El Nino/positive IOD = drier conditions = worse fire seasons
- La Nina = wetter conditions = reduced fire risk but more fuel growth
- Positive SAM (Southern Annular Mode) = drier in southeast Australia

## 2. Vegetation Types and Fire Behavior

### Wet Sclerophyll Forest (Tall Eucalypt Forest)

**Location**: Blue Mountains, Illawarra escarpment, North Coast ranges
**Canopy**: Eucalyptus regnans, E. fastigata, E. viminalis (20-60m tall)
**Understory**: Rainforest elements (tree ferns, Acacia, mesophyll shrubs)
**Fire behavior**:
- Crown fires with extreme intensity (40,000-100,000+ kW/m)
- Bark strips from stringybark eucalypts become firebrands, causing spotting up to 30-40 km
- Fires in these forests drove the worst Black Summer destruction
- Typically burn only in extreme conditions (FFDI >50)
- Long fire return interval: 50-200+ years
- Post-fire: mass germination from seed (obligate seeders) or resprouting from epicormic buds

**Detection implications**:
- Very high FRP values when burning
- Dense canopy means understory fires may be invisible to satellites until crown involvement
- Post-fire spectral change is dramatic and long-lasting

### Dry Sclerophyll Forest

**Location**: Western slopes, coastal lowlands, Sydney sandstone basin
**Canopy**: E. pilularis, E. punctata, E. crebra, Corymbia maculata (10-25m)
**Understory**: Shrubby (Banksia, Hakea, Lambertia) or grassy (Themeda, Poa)
**Fire behavior**:
- Surface fires to crown fires depending on fuel load and weather
- Moderate to high intensity (5,000-50,000 kW/m)
- Spotting distance: typically 1-5 km from stringybark species
- Fire return interval: 5-50 years
- Most common fire type in NSW

**Detection implications**:
- Moderate FRP
- More frequent fires = more training data available
- Open canopy allows better satellite detection of surface fires

### Grassland

**Location**: Western plains, tablelands, pastoral country
**Species**: Themeda triandra, Austrostipa, Chloris, introduced pasture grasses
**Fire behavior**:
- Fast-moving surface fires: rate of spread up to 17 km/h in extreme conditions
- Rate of spread approximately 20% of 10m open wind speed
- Lower intensity per pixel but rapid spread creates large burned areas quickly
- Spotting is minimal (no bark firebrands)
- Fire can pass in 5-10 seconds with brief smoldering
- Fire return interval: 1-5 years

**Detection implications**:
- Low FRP per pixel (may fall below VIIRS detection threshold)
- Very fast spread means fire may move through VIIRS pixel before next overpass
- Rapid post-fire green-up (weeks) means burn scars disappear quickly in optical imagery
- MCD64A1 may miss rapidly-recovering grassland burns

### Coastal Heath

**Location**: Coastal strip, especially sandstone areas (Royal NP, Jervis Bay)
**Species**: Banksia, Allocasuarina, Leptospermum, sedges
**Fire behavior**:
- Surface to crown fire (low canopy height 1-3m)
- Moderate intensity (5,000-20,000 kW/m)
- Requires 7-15 years of fuel accumulation
- Very flammable due to oil-rich Myrtaceae species

**Detection implications**:
- Moderate FRP
- Fires in narrow coastal strips may be partially over water, confusing detection algorithms
- Sea breeze interactions create complex fire weather patterns

### Alpine/Subalpine

**Location**: Snowy Mountains, Australian Alps
**Species**: Snow Gum (E. pauciflora), alpine heath, sphagnum bogs
**Fire behavior**:
- Rare but ecologically devastating
- Peat fires can burn for months underground
- 2003 and 2019-2020 alpine fires were unprecedented
- Lightning ignition common in summer

**Detection implications**:
- Smoldering peat fires produce low thermal signal, hard to detect
- Complex terrain creates satellite viewing angle issues
- High elevation = more cloud cover

## 3. Fire Behavior Physics (Australian Context)

### FFDI Rating Scale and Typical Conditions

| FFDI | Category | Fire Behavior |
|------|----------|--------------|
| 0-5 | Low-Moderate | Fires easily controlled |
| 5-12 | High | Head fire difficult to control |
| 12-24 | Very High | Crown fires in forest; spotting active |
| 24-50 | Severe | Erratic fire behavior; ember attack on structures |
| 50-100 | Extreme | Major fire runs; long-distance spotting |
| 100+ | Catastrophic | Loss of life likely; fire behavior unprecedented |

Black Summer peak FFDI values exceeded 200 in some locations (off-scale catastrophic).

### AFDRS (New System, since September 2022)

The Australian Fire Danger Rating System replaced FFDI with:
- 4 danger levels: Moderate, High, Extreme, Catastrophic
- 22 fuel types (vs FFDI's 2: forest and grass)
- 8 fire behavior models
- Better reflects actual fire potential across different vegetation types
- For historical analysis, FFDI remains the primary available index (AFDRS data only from 2022)

### Spotting: The Defining Feature of Australian Fires

Eucalypt bark types determine spotting potential:

| Bark Type | Species Examples | Spotting Distance |
|-----------|-----------------|-------------------|
| Stringybark | E. obliqua, E. macrorhyncha | 5-40 km (long-range) |
| Ribbon bark | E. viminalis, E. rubida | 1-10 km |
| Rough bark | E. pilularis, E. sideroxylon | 0.5-5 km |
| Smooth bark | E. pauciflora, Corymbia maculata | Minimal |

- Stringybark strips ignite, are lofted by the convection column, and travel with upper-level winds
- Spot fires can establish well ahead of the main fire front
- This makes fire perimeter detection very challenging: the actual fire extent may include disconnected spot fires spread over tens of kilometers
- FIRMS detections during severe spotting events will show scattered points rather than contiguous fire fronts

### Fire Rate of Spread Models

**Vesta Mk 2 (CSIRO)** -- current best model for Australian eucalypt forests:
- Inputs: wind speed, fuel moisture, fuel hazard scores, slope
- Predicts rate of spread and flame height
- Documentation: https://research.csiro.au/vestamk2/

**Grassland fire model:**
- Rate of spread ≈ 0.2 × 10m wind speed (km/h)
- In critical conditions (wind >50 km/h, RH <10%), grassfires can outrun vehicles

## 4. Key Fire Events for Training/Validation

### Black Summer Mega-Fires (NSW)

| Fire Name | Period | Area (ha) | Key Features |
|-----------|--------|-----------|-------------- |
| Gospers Mountain | Oct 2019 - Jan 2020 | 512,626 | Largest single fire complex; Blue Mountains |
| Currowan | Nov 2019 - Feb 2020 | 499,621 | Coastal NSW; complex terrain |
| Green Wattle Creek | Dec 2019 - Feb 2020 | 278,950 | Southwest of Sydney |
| Ruined Castle | Dec 2019 - Jan 2020 | 50,000+ | World Heritage Blue Mountains |

### Other Notable NSW Fire Events

| Event | Year | Area | Notes |
|-------|------|------|-------|
| Blue Mountains fires | 2013 | 108,000 ha | Well-documented; good for moderate-event training |
| Wambelong fire | 2013 | 55,000 ha | Warrumbungles NP |
| Sir Ivan fire | 2017 | 55,000 ha | Fast-moving grassland/woodland fire |
| Tathra fire | 2018 | 1,400 ha | Coastal fire; destroyed 69 homes |

### Prescribed Burn Records

- NPWS conducts 100-300 prescribed burns per year in NSW
- Total area: typically 50,000-150,000 ha per year
- Available in NPWS Fire History dataset (FireType=2)
- Useful for training models to detect low-intensity fires or to distinguish wildfire from prescribed burn

## 5. Vegetation Mapping Resources

### NSW Vegetation Map

- **State Vegetation Type Map (SVTM)**: https://datasets.seed.nsw.gov.au/
- Maps Plant Community Types (PCTs) across NSW
- Can be simplified to structural classes relevant for fire behavior
- Essential for stratifying training data by vegetation type

### National Vegetation Information System (NVIS)

- **URL**: https://www.dcceew.gov.au/science-research/nvis
- National-level vegetation mapping
- Major Vegetation Groups (MVGs) align roughly with fire behavior categories

### Dynamic Land Cover (DLCD)

- Available in GEE: `ee.ImageCollection("AU/GA/DLCDv1")`
- 250m resolution, derived from MODIS
- Classes include forest, woodland, grassland, cropland
- Useful for stratifying fire data by land cover type

## 6. Climate and Weather Context

### NSW Climate Zones

```
Northern NSW (north of ~31S):
  - Subtropical influence
  - Higher rainfall, shorter dry season
  - Fire season: Aug-Dec (earlier start)

Central/Southern NSW (south of ~31S):
  - Temperate
  - Winter rainfall dominant in some areas
  - Fire season: Oct-Mar (later start, longer peak)

Western NSW (west of ~148E):
  - Semi-arid
  - Grassland/woodland fires
  - Highly variable; fire only after good rainfall grows fuel
  - Fire season: whenever fuel load is sufficient and conditions hot/dry
```

### Key Weather Stations for Fire Context

| Station | ID | Location | Relevance |
|---------|-----|----------|-----------|
| Sydney Airport | 066037 | Coastal metropolitan | Urban-rural interface fire risk |
| Katoomba | 063039 | Blue Mountains | Wet sclerophyll fire weather |
| Penrith Lakes | 067113 | Western Sydney | Extreme heat records |
| Canberra Airport | 070351 | Southern tablelands | ACT/NSW border fire weather |
| Moree | 053115 | Northern plains | Grassland fire conditions |
| Wagga Wagga | 072150 | Riverina | Inland fire weather |

### Fire Weather Observation Parameters

The Bureau of Meteorology records:
- Temperature (dry bulb and wet bulb) at screen height
- Relative humidity (derived)
- Wind speed and direction at 10m
- Rainfall (daily totals and since 9am)
- Drought factor (computed)
- FFDI (computed from above)

These observations are available through BOM Climate Data Online for historical analysis and through real-time feeds during fire events.
