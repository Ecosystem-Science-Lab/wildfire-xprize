# Fire Detection Algorithms — Algorithm Details

## VIIRS VNP14IMG Algorithm (375 m)

The gold standard for polar-orbiting fire detection. Full ATBD: https://viirsland.gsfc.nasa.gov/PDF/VIIRS_activefire_375m_ATBD.pdf

### Pipeline overview
1. Input preparation (I4, I5, I1-I3 reflectances, M13 radiance, quality flags)
2. Cloud masking
3. Water masking
4. Fixed threshold tests → immediate high-confidence fires
5. Large-area background (501×501) → scene-dependent candidate threshold BT4S
6. Candidate fire selection
7. Contextual background characterization (11×11 to 31×31)
8. Contextual fire tests → nominal-confidence fires
9. Secondary tests → low-confidence fires or downgrades
10. FRP retrieval via M13

### Step 2: Cloud masking
Liberal cloud mask (avoids masking fires under thin cloud):

**Daytime** (any true → cloud):
- BT5 < 265 K
- (ρ1 + ρ2 > 0.9) AND (BT5 < 295 K)
- (ρ1 + ρ2 > 0.7) AND (BT5 < 285 K)

**Nighttime** (both must hold):
- BT5 < 265 K AND BT4 < 295 K

### Step 3: Water masking
Spectral ordering test (daytime): ρ1 > ρ2 > ρ3
Combined with MODIS-derived 250 m land-water mask. Water pixels processed separately (not excluded — allows gas flare detection).

### Step 4: Fixed threshold tests (immediate high-confidence)
These bypass contextual analysis entirely:

**Nighttime unsaturated**: BT4 > 320 K AND QF4=0 → class 9 (high confidence)

**Saturated I4**: BT4=367 K AND QF4=9 AND QF5=0, plus (daytime) BT5>290 K AND (ρ1+ρ2)<0.7 → class 9

**I4 folding** (DN wrap-around from extreme saturation):
- Day: ΔBT45 < 0 AND BT5 > 325 K AND QF5=0
- Night: ΔBT45 < 0 AND BT5 > 310 K AND QF5=0, OR BT4=208 K AND BT5>335 K
→ class 9

### Step 4b: Potential background fire masking
Pixels excluded from background stats (but not classified as fires yet):
- Day: BT4 > 335 K AND ΔBT45 > 30 K
- Night: BT4 > 300 K AND ΔBT45 > 10 K

### Step 4c: Bright surface rejection (daytime only)
- ρ3 > 0.3 AND ρ3 > ρ2 AND ρ2 > 0.25 AND BT4 ≤ 335 K → reject

### Step 4d: Sun glint rejection
Glint angle: cos(θg) = cos(θv)cos(θs) - sin(θv)sin(θs)cos(φ)
- θg < 15° AND (ρ1+ρ2) > 0.35 → glint (class 2)
- θg < 25° AND (ρ1+ρ2) > 0.4 → glint (class 2)

### Step 5: Large-area background threshold (BT4S)
501×501 window, excluding clouds/water/background-fires/bad-quality pixels.
If <10 valid pixels: BT4S = 330 K
Otherwise: M = median(BT4), BT4M = MAX(325, M+25), BT4S = MIN(330, BT4M)
Result: BT4S ranges adaptively between 325-330 K daytime.

### Step 6: Candidate fire selection
**Daytime**: BT4 > BT4S AND ΔBT45 > 25 K
**Nighttime**: BT4 > 295 K AND ΔBT45 > 10 K

### Step 7: Contextual background characterization
Dynamic window starting at 11×11, growing to max 31×31 until:
- ≥25% of window elements are valid background, OR
- ≥10 valid background pixels found

Valid background = not cloud, not background-fire, nominal QF, same land/water type as candidate.

Statistics computed over valid background:
- BT4B (mean BT4), BT5B (mean BT5), ΔBT45B (mean ΔBT45)
- δ4B, δ5B, δ45B (mean absolute deviations)

If insufficient background: class 6 (unclassified).

### Step 8: Contextual fire tests → nominal confidence (class 8)
**Daytime** (ALL must hold):
- ΔBT45 > ΔBT45B + 2×δ45B
- ΔBT45 > ΔBT45B + 10 K
- BT4 > BT4B + 3.5×δ4B
- BT5 > BT5B + δ5B − 4 K (OR δ'4B > 5 K when background-fire variability high)

**Nighttime** (ALL must hold):
- ΔBT45 > ΔBT45B + 3×δ45B
- ΔBT45 > ΔBT45B + 9 K
- BT4 > BT4B + 3×δ4B

### Step 8b: Background-fire pre-filter (daytime)
If ≥4 background fire pixels or >10% of valid background:
Compute BT'4B, δ'4B over background-fire subset.
Reject if: ρ2 > 0.15 AND BT'4B < 345 K AND δ'4B < 3 K AND BT4 < BT'4B + 6×δ'4B

### Step 9: Secondary tests
**Residual saturation fires** → low confidence (class 7):
If (BT5 ≥ 325 K OR BT4 = 355 K OR ΔBT45 < 0) AND has adjacent nominal/high fire

**Sun glint downgrades** (nominal → low confidence):
If (ΔBT45 ≤ 30 K OR θg < 15°) AND (≥2 adjacent glint pixels OR (no adjacent high-confidence fires AND BT4 < 15 K above any adjacent pixel))

### Step 10: FRP retrieval
Uses M13 (750 m, dual-gain, higher saturation) not I4:
FRP = A × σ × ((L13 - L13B) / a)^(1/4)
Where: A = pixel area, σ = Stefan-Boltzmann, a = 2.88×10⁻⁹, L13/L13B = fire/background M13 radiance.
FRP apportioned equally among coincident 375 m fire pixels.

### Fire mask classes
0=not processed, 1=bow-tie, 2=sun glint, 3=water, 4=cloud, 5=land, 6=unclassified, 7=low confidence, 8=nominal, 9=high confidence

---

## GOES ABI FDCA Algorithm (2 km geostationary)

Full ATBD: https://www.star.nesdis.noaa.gov/atmospheric-composition-training/documents/ABI_FDC_ATBD.pdf

### Key differences from VIIRS
- 2 km pixels (vs 375 m)
- Continuous temporal coverage (5-15 min refresh)
- Two-part processing: Part I (all pixels) + Part II (candidates with temporal filtering)
- Full Dozier sub-pixel characterization (area + temperature + FRP)
- Background window up to ~111×111 pixels (vs 31×31 for VIIRS contextual)
- Channel 7 (3.9 μm) saturates at ~400 K (vs I4 ~358-367 K)

### Part I: Per-pixel processing
- Screen by view zenith (≤80°, best ≤65°)
- Cloud tests: T11.2 < 270 K, T3.9-T11.2 < −4 K, visible albedo ≥0.38
- Background window (up to 111×111, ≥20% valid required)
- Contextual tests on T3.9, T11.2, T3.9-T11.2 anomalies vs σ-multiples
- Dozier inversion: solve L3.9 = p·L3.9(Tf) + (1-p)·L3.9(Tb), same for L11.2
- FRP from fire fraction and temperature

### Part II: Temporal filtering
- Compare against previous 12h of detections
- Persistent fires get upgraded confidence
- One-off detections downgraded
- Key advantage for false positive reduction

---

## Himawari AHI Fire Detection

Uses same physical principles as GOES FDCA but for AHI instrument:
- Band 7 (3.9 μm, 2 km) + Band 14 (11.2 μm, 2 km)
- 10-min full disk scan (vs GOES 10-15 min)
- Primary geostationary sensor for Australia
- See `perplexity_himawari_ahi.md` for detailed implementation (when available)

Adaptation needed: GOES FDCA ATBD provides the algorithmic framework, but thresholds need tuning for AHI spectral response and Australian conditions.

---

## Tunable Parameters for Australia

### VIIRS thresholds to consider adjusting
1. **ΔBT45 daytime threshold**: 25 K → consider 27-30 K for hot Australian backgrounds (reduces false alarms from hot soils, but risks missing low-intensity grass fires)
2. **BT4S range**: 325-330 K may be too low for hot Australian summers. Consider M+30 or cap at 335 K.
3. **Contextual multipliers**: 3.5×δ4B daytime → try 3.0 for narrow eucalypt fire fronts
4. **Bright surface rejection**: ρ3>0.3 threshold may need adjustment for Australian salt lakes and bright soils
5. **Glint handling**: θg thresholds may need tuning for solar geometry at -33.5°S latitude

### Geostationary (AHI) parameters
1. **Background window size**: 111×111 may be too large for heterogeneous Australian landscapes
2. **T3.9min**: Night 285 K may be too aggressive for cool Australian winter nights
3. **Temporal filtering window**: 12h for GOES; consider shorter for fast-moving Australian grass fires
4. **Cloud thresholds**: Tune to Australian cloud climatology (convective afternoon clouds in summer)
