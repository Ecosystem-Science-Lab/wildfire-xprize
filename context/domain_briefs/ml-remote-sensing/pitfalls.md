# Pitfalls: Overfitting, Class Imbalance, Geographic Bias, Latency Traps, Model Drift

## 1. Class Imbalance

### The Problem
Fire pixels are extremely rare. In a typical Himawari-8 full-disk scan of ~5500x5500 pixels, fewer than 100 may contain active fire. Even after Pass 1 filtering, the candidate set is dominated by false positives (sun glint, hot desert, cloud edges).

Typical ratios:
- Full disk: ~1:300,000 (fire:non-fire)
- After Pass 1: ~1:5 to ~1:20 (fire:false-positive)
- Training set should be: ~1:3 to ~1:5

### Mitigation Strategies

**Do:**
- Use weighted sampling (`WeightedRandomSampler`) so each batch contains ~30-40% fire patches
- Use focal loss (gamma=2.0, alpha=[0.25, 0.75]) to down-weight easy negatives
- Construct hard negative training sets from Pass 1 false positives specifically
- Monitor recall as primary metric, not accuracy (99% accuracy with 80% recall is a failure)

**Do not:**
- Use standard cross-entropy without class weights (model learns to predict "no fire" always)
- Over-augment fire patches to artificially balance classes (creates distribution artifacts)
- Use SMOTE on image patches (generates unrealistic interpolated patches that don't represent physical fire signatures)
- Rely on accuracy as the optimization target

### Focal Loss Caveat
Focal loss can struggle with large fire clusters, producing higher false negative rates. It overemphasizes rare ambiguous fire pixels and underweights confident predictions, reducing ability to fully classify well-defined fire regions. If recall drops below 95%, switch to weighted cross-entropy with hard negative mining.

## 2. Overfitting to Specific Sensors

### The Problem
A model trained on Himawari-8 data will not transfer directly to GOES-16 or VIIRS due to:
- Different spectral response functions (even for "same wavelength" bands)
- Systematic brightness temperature biases between sensors (1-3K offsets)
- Different spatial resolutions (Himawari 2km vs VIIRS 375m)
- Different noise characteristics and saturation levels
- Different scan geometries and viewing angles

### Concrete Example
VIIRS detects sub-pixel fires at 375m that are smoothed out in Himawari-8's 2km pixel. A fire with FRP < 5 MW may be clearly visible to VIIRS but invisible to Himawari-8. Using VIIRS fire labels directly for Himawari-8 training creates mislabeled positives.

### Mitigation
- Train separate model instances per sensor (same architecture, different weights)
- When using VIIRS labels for Himawari-8 training, filter to FRP > 10 MW (fires large enough to be detectable at 2km)
- Add buffer radius of 1km when matching VIIRS fire locations to Himawari-8 pixels
- If transfer learning across sensors: freeze convolutional layers, retrain classifier head with target-sensor data
- Normalize inputs to physical units (brightness temperature in K, reflectance 0-1) rather than raw digital numbers

### Multi-Sensor Architecture Approach

```
DO:   Same architecture, separate weights per sensor
DON'T: One model with sensor-ID as input feature (conflates different physics)

Architecture: FireCNN(in_channels=4)  # same for all sensors
Weights:      fire_cnn_himawari.pt, fire_cnn_goes.pt, fire_cnn_viirs.pt
```

## 3. Geographic and Temporal Bias

### The Problem
Models trained on fire data from one region (e.g., Australian bushfires) may fail in others (e.g., Siberian boreal fires, African savanna burns) because:
- Different land cover types produce different false-positive patterns
- Seasonal patterns differ (Northern vs Southern hemisphere fire seasons)
- Different land surface emissivities affect brightness temperature baselines
- Desert regions in Australia vs tropical forests produce fundamentally different background signatures

### For XPRIZE Specifically
The competition is in NSW, Australia (April 2026). Training only on NSW data risks:
- Overfitting to eucalyptus-dominated vegetation signatures
- Missing generalization to the specific fire types expected in April (early autumn)
- The 2019-2020 Black Summer fires were extreme events; training heavily on them may bias toward large fires, missing small ignitions

### Mitigation
- Include diverse geographic regions in training data (at least 5 continents)
- Stratify validation sets by region and season
- Include "out-of-distribution" test set from a geographic region not in training
- For XPRIZE: fine-tune on NSW-specific data, but validate on non-NSW Australian fires
- Track per-region performance metrics separately

### Temporal Bias
- Do NOT train and validate on different time slices of the same fire event (spatial autocorrelation creates information leakage)
- Split by fire event, not by patch. All patches from one fire go to train OR val, never both
- Include diverse times of day (day vs. night detection characteristics differ significantly)

## 4. Latency Traps

### Trap 1: The CNN Is Not Your Bottleneck

```
Typical latency breakdown:
  Data download:       30-60s  (this is the real bottleneck)
  Data decode/ingest:  5-15s
  Pass 1 thresholds:   5-10s
  Pass 2 CNN:          0.1-0.5s  (< 1% of total time)
  Alert generation:    < 1s
```

Optimizing the CNN from 200ms to 50ms saves almost nothing. Focus optimization efforts on data download and Pass 1.

### Trap 2: Python Overhead in Single-Patch Inference

Processing candidates one at a time in a Python loop destroys GPU utilization:

```python
# BAD: 100 candidates x 10ms each = 1000ms
for pixel in candidates:
    patch = extract_patch(pixel)
    result = model(patch)

# GOOD: 100 candidates batched = 20ms total
patches = np.stack([extract_patch(p) for p in candidates])
results = model(patches)  # single forward pass
```

Always batch candidates from one scan together.

### Trap 3: ONNX Runtime Provider Fallback

If `CUDAExecutionProvider` fails silently, ONNX Runtime falls back to CPU without warning:

```python
# DANGEROUS: may silently use CPU
session = ort.InferenceSession("model.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])

# SAFE: verify which provider is active
session = ort.InferenceSession("model.onnx", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
active = session.get_providers()
if "CUDAExecutionProvider" not in active:
    raise RuntimeError("GPU not available, inference will be too slow")
```

### Trap 4: INT8 Quantization on Old Hardware

INT8 quantization only speeds things up on hardware with native INT8 instruction support:
- Intel CPUs with VNNI (Ice Lake+): 2-4x speedup
- NVIDIA GPUs with INT8 Tensor Cores (Turing+): 2-3x speedup
- Older hardware: INT8 can be SLOWER than FP32 due to quantize/dequantize overhead

Always benchmark on your actual deployment hardware.

### Trap 5: Memory Allocation in Inference Loops

```python
# BAD: creates new numpy arrays every iteration
while True:
    scan_data = get_next_scan()
    patches = extract_patches(scan_data)  # allocates new array
    results = model(patches)              # allocates new array

# BETTER: pre-allocate and reuse buffers
patch_buffer = np.zeros((MAX_CANDIDATES, C, H, W), dtype=np.float32)
while True:
    scan_data = get_next_scan()
    n = fill_patch_buffer(scan_data, patch_buffer)
    results = model(patch_buffer[:n])
```

## 5. Model Drift

### Sources of Drift in Satellite Fire Detection

**Sensor drift:**
- Gradual degradation of detector sensitivity (aging)
- Orbit drift (sun-synchronous satellites gradually shift local crossing time)
- Calibration coefficient updates by sensor operators (sudden jumps)
- Stray light contamination (documented in Himawari-8 3.9um channel)

**Environmental drift:**
- Seasonal vegetation changes (NDVI baseline shifts)
- Multi-year land use changes (deforestation, urbanization)
- Climate trends (baseline temperature changes)
- Volcanic aerosols affecting atmospheric transmission

**Label drift:**
- VIIRS fire product algorithm updates (new versions may change detection characteristics)
- Changes in FIRMS processing pipeline

### Monitoring Strategy

```python
class ModelMonitor:
    """Track model performance metrics over time to detect drift."""

    def __init__(self, baseline_metrics: dict, alert_thresholds: dict = None):
        self.baseline = baseline_metrics
        self.thresholds = alert_thresholds or {
            "recall_drop": 0.05,          # alert if recall drops by 5%
            "fp_rate_increase": 0.10,      # alert if FP rate increases by 10%
            "input_distribution_shift": 2.0,  # z-score threshold
        }
        self.history = []

    def check_input_drift(self, batch_stats: dict):
        """Compare current input statistics to training distribution."""
        alerts = []
        for channel, stats in batch_stats.items():
            baseline_mean = self.baseline["channel_means"][channel]
            baseline_std = self.baseline["channel_stds"][channel]

            z_score = abs(stats["mean"] - baseline_mean) / (baseline_std + 1e-8)

            if z_score > self.thresholds["input_distribution_shift"]:
                alerts.append(
                    f"Channel {channel}: mean shifted by {z_score:.1f} sigma "
                    f"(baseline={baseline_mean:.1f}, current={stats['mean']:.1f})"
                )
        return alerts

    def check_prediction_drift(self, fire_rate: float, fp_rate: float):
        """Compare current prediction rates to baseline."""
        alerts = []
        baseline_fire_rate = self.baseline["fire_rate"]
        baseline_fp_rate = self.baseline["fp_rate"]

        if fire_rate < baseline_fire_rate * 0.5:
            alerts.append(f"Fire detection rate dropped 50%+ "
                         f"({fire_rate:.4f} vs baseline {baseline_fire_rate:.4f})")

        if fp_rate > baseline_fp_rate + self.thresholds["fp_rate_increase"]:
            alerts.append(f"False positive rate increased "
                         f"({fp_rate:.4f} vs baseline {baseline_fp_rate:.4f})")

        return alerts
```

### When to Retrain

| Trigger | Action |
|---|---|
| Sensor calibration update announced | Collect 1 week of new data, fine-tune for 5 epochs |
| Input distribution shift > 3 sigma sustained > 24h | Investigate root cause, then retrain with recent data |
| Recall drops below 90% against validation fires | Full retrain with updated training set |
| New VIIRS product version released | Regenerate labels, full retrain |
| Quarterly | Evaluate on recent fires, fine-tune if performance degraded |

### Retraining Best Practices

- Always keep a held-out test set that is never used for training or threshold tuning
- Use expanding window: include all historical data + recent data (do not discard old data)
- Version models and link to exact training dataset version
- A/B test new model against current production model before deployment
- Keep the old model running as fallback for 48 hours after deploying new model

## 6. Training Data Construction Pitfalls

### Pitfall: Spatial Autocorrelation Leakage

```
WRONG: Random 80/20 split of all patches
  -> Adjacent patches from same fire end up in both train and val
  -> Val accuracy is artificially inflated (99%+)
  -> Real-world performance is 10-20% lower

RIGHT: Split by fire EVENT
  -> All patches from fire event #123 go to train OR val
  -> Fire event #124 may go to the other split
  -> Val accuracy reflects real generalization
```

### Pitfall: Using MODIS/VIIRS Labels for Geostationary Training Without Temporal Alignment

VIIRS overpasses happen twice per day. Himawari-8 scans every 10 minutes. A VIIRS fire detection at 02:30 UTC does not guarantee the fire was burning at 02:00 UTC or 03:00 UTC.

Solution: Use VIIRS detections as seed locations, but verify fire presence in the contemporaneous Himawari-8 scan by checking T4 elevation above background.

### Pitfall: Ignoring Day/Night Differences

Fire detection physics differ fundamentally between day and night:
- Day: solar reflection in SWIR bands causes false positives; T4-T11 difference is modulated by solar heating
- Night: no solar contamination; T4-T11 is a cleaner fire signal; background is colder, so contrast is higher

Train separate day/night models OR include solar zenith angle as an input feature. Do NOT mix day and night patches without accounting for this.

### Pitfall: Cloud Contamination in Training Data

Cloud edges are a major source of false positives (sharp temperature gradients mimic fire). If training data is not properly cloud-masked:
- Model learns to classify cloud edges as fire
- False positive rate explodes in cloudy conditions

Solution: Include cloud mask as a quality flag during label construction. Discard fire labels that overlap with cloud pixels. Include cloud-edge patches as explicit hard negatives.

## 7. Deployment Pitfalls

### Threshold Selection

Do not set the fire/no-fire threshold to maximize accuracy. Set it to achieve target recall (>= 95%) and accept the resulting precision.

```python
# WRONG: threshold = 0.5 (default, maximizes accuracy)
# RIGHT: find threshold that gives recall >= 0.95
from sklearn.metrics import precision_recall_curve

precisions, recalls, thresholds = precision_recall_curve(labels, probs)
# Find highest precision where recall >= 0.95
valid = recalls >= 0.95
optimal_threshold = thresholds[valid][np.argmax(precisions[valid])]
# This threshold is usually 0.2-0.4, much lower than 0.5
```

### Model Serving Without Health Checks

```python
# BAD: model silently returns garbage if GPU runs out of memory
result = model(patches)

# GOOD: validate outputs
result = model(patches)
fire_probs = softmax(result)

# Sanity checks
assert fire_probs.min() >= 0 and fire_probs.max() <= 1, "Invalid probabilities"
assert len(fire_probs) == len(patches), "Output size mismatch"

# Check for degenerate model (all same prediction)
if fire_probs.std() < 1e-6:
    log.warning("Model producing constant outputs -- possible failure")
```

### Coordinate System Mismatches

Satellite data uses various coordinate systems. A common bug:
- VIIRS fire locations are in (lat, lon)
- Himawari-8 data is in a fixed grid projection
- Converting between them introduces rounding that shifts patches by 1-2 pixels
- This matters when the fire is only 1-2 pixels and the shift moves it out of the patch

Always verify patch extraction visually for a sample of known fires before training.
