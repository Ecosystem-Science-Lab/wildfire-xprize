# Validation Results v1 — March 20, 2026

## Raw Numbers

| Metric | Value | Assessment |
|--------|-------|-----------|
| FIRMS events evaluated | 86 | |
| Detected | 85 (98.8%) | Misleadingly good — see false alarms |
| Missed | 1 | |
| Early detections (before FIRMS) | 23 (26.7%) | |
| **Total detections** | **10,234,461** | |
| **False alarms** | **10,218,307 (99.8%)** | **Catastrophic** |
| Median latency | +1886 min (~31 hours) | Detections are days late |
| First detection by CUSUM | 82 of 85 | CUSUM is producing all the "detections" |
| First detection by contextual | 3 of 85 | Contextual barely fires |

## Interpretation

### CUSUM is a false alarm machine
With only ~23% of pixels initialized (the Kalman model hasn't converged), CUSUM produces ~5000 candidates per frame × ~2700 frames = millions of false positives. The 98.8% "detection rate" is meaningless — we're just spraying so many alerts that some land near real fires by coincidence.

**Action:** Disable CUSUM for now. It needs 4+ weeks of pre-initialization before it can contribute. Run preinit daily until competition.

### Contextual detector is too conservative
Only 3 fires first-detected by the contextual algorithm. This means our thresholds are too strict for real NSW March conditions. The fires ARE there in the data (FIRMS detected them from VIIRS), but our contextual algorithm isn't catching them from AHI.

**Possible causes:**
- Candidate selection thresholds too high (day BTD > 22K might miss moderate fires)
- Sigma thresholds too strict (3.5σ day / 3.0σ night)
- Background window too small to get reliable statistics at AHI resolution
- Cloud masking too aggressive (removing fire pixels)
- Some fires may just be too small for 2km AHI resolution

**Action:** Analyze the 83 fires that contextual missed. For each one, extract the AHI pixel values and determine which threshold test failed. Then tune.

### Latency distribution is bimodal
- P10 = -1713 min (28 hours BEFORE FIRMS) — some genuine early detections
- Median = +1886 min (31 hours AFTER FIRMS) — most are very late
- This bimodal pattern suggests the "early" detections are CUSUM noise that happened to be near a fire before FIRMS caught it, and the "late" detections are CUSUM noise days later near the same fire location.

### Detection by fire size
All FRP bins show ~100% detection, which confirms this is noise matching, not real detection. A real detector should show lower rates for smaller fires.

## Priority Actions

1. **Disable CUSUM** in the validation run. Re-run with contextual only to get clean contextual-only numbers.
2. **Analyze contextual misses** — why are only 3 of 86 fires detected by contextual?
3. **Loosen contextual thresholds** based on miss analysis.
4. **Build RF classifier** to replace hard thresholds with learned decision boundaries.
5. **Fix validation matching** — the 10km/24h matching window may be too generous. Tighten to 5km/60min.
