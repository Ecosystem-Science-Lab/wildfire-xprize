# Algorithms: CNN Architectures, Training Strategies, Anomaly Detection, Inference Optimization

## 1. CNN Architectures for Small-Patch Fire Classification

### 1.1 Recommended: Custom Lightweight CNN (FireNet-style)

For 32x32 or 64x64 patches with 4-9 input channels, a custom small CNN outperforms repurposed ImageNet architectures because:
- Input is multi-spectral (not RGB), so pretrained weights from ImageNet have limited value
- Patches are small, so deep networks waste parameters
- Inference speed is critical

**Architecture spec (recommended starting point):**

```
Input: (batch, C, 64, 64) where C = 4-9 channels

Conv2d(C, 32, 3, padding=1) + BatchNorm + ReLU
Conv2d(32, 32, 3, padding=1) + BatchNorm + ReLU
MaxPool2d(2)                                        # -> 32x32
Dropout(0.25)

Conv2d(32, 64, 3, padding=1) + BatchNorm + ReLU
Conv2d(64, 64, 3, padding=1) + BatchNorm + ReLU
MaxPool2d(2)                                        # -> 16x16
Dropout(0.25)

Conv2d(64, 128, 3, padding=1) + BatchNorm + ReLU
MaxPool2d(2)                                        # -> 8x8
Dropout(0.25)

AdaptiveAvgPool2d(1)                                # -> 1x1
Flatten
Linear(128, 64) + ReLU + Dropout(0.5)
Linear(64, 2)                                       # fire / no-fire logits
```

**Specs:**
- Parameters: ~150K-200K (depending on input channels)
- Model size: ~0.8MB (FP32), ~0.2MB (INT8)
- Inference: <5ms per patch on GPU, <50ms on CPU
- Suitable for batch processing 100s of candidates simultaneously

### 1.2 FireNet (Jasmeet 2019)

Published lightweight architecture designed for fire detection on embedded devices:

| Layer | Type | Config |
|---|---|---|
| 1 | Conv2d | 16 filters, 3x3, ReLU |
| 2 | MaxPool2d | 2x2 |
| 3 | Dropout | 0.5 |
| 4 | Conv2d | 32 filters, 3x3, ReLU |
| 5 | MaxPool2d | 2x2 |
| 6 | Dropout | 0.5 |
| 7 | Conv2d | 64 filters, 3x3, ReLU |
| 8 | MaxPool2d | 2x2 |
| 9 | Dropout | 0.5 |
| 10 | Dense | 256 units, ReLU |
| 11 | Dropout | 0.2 |
| 12 | Dense | 128 units, ReLU |
| 13 | Dense | 2 units, Softmax |

- Input: 64x64x3
- Parameters: 646,818 (~7.5MB)
- Speed: 24 FPS on Raspberry Pi 3B
- Open source: https://github.com/OlafenwaMoses/FireNET

**FireNet-v2** reduces to 318,460 parameters with 98.43% accuracy.

### 1.3 MobileNetV2 (adapted)

For cases where more capacity is needed (e.g., 9-channel input, larger patches):

- Replace first conv layer to accept C channels instead of 3
- Use width_multiplier=0.35 to reduce parameters
- Depthwise separable convolutions give 8-9x reduction vs standard conv
- ~0.5M parameters at width=0.35
- Known issue: MobileNets are less robust to INT8 quantization than ResNets (fewer parameters means each one matters more)

### 1.4 SSRN (Spectral-Spatial Residual Network)

Designed for hyperspectral/multispectral classification:
- 0.25M parameters
- 1.01ms inference latency
- 98.4% accuracy on multispectral fire patches (PyroFocus benchmark)
- Better suited than general-purpose architectures when spectral channels carry the signal

### 1.5 EfficientNet-Lite0 (ceiling model)

Upper bound on model complexity. Use for benchmarking, not production:
- Removes squeeze-and-excite layers (poor mobile support)
- Replaces swish with ReLU6 (easier quantization)
- ~4.7M parameters
- Pre-quantized INT8 models available
- 80.4% ImageNet top-1 at 30ms/image on Pixel 4 CPU

### Architecture Selection Guide

| Scenario | Architecture | Params | Reason |
|---|---|---|---|
| Baseline / MVP | Custom small CNN | ~150K | Fast to train, easy to debug |
| Better accuracy needed | SSRN or MobileNetV2-0.35 | 250K-500K | Spectral-spatial features |
| Ablation / ceiling test | EfficientNet-Lite0 | 4.7M | Upper bound on what's possible |
| Edge deployment | FireNet-v2 | 318K | Proven on resource-constrained devices |

## 2. Training Strategies

### 2.1 Loss Functions

**Primary: Focal Loss**

Standard cross-entropy under-weights hard examples. Focal loss down-weights easy negatives:

```
FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
```

Recommended hyperparameters for fire detection:
- gamma = 2.0 (focus on hard examples)
- alpha = 0.75 for fire class, 0.25 for non-fire (compensate for class imbalance)

**Caveat:** Focal loss can struggle with large fire clusters, producing higher false negatives by overemphasizing rare ambiguous pixels. Monitor recall closely.

**Alternative: Dice Loss**

Better for segmentation-style tasks. Measures overlap between predicted and ground truth:
```
Dice = 2 * |A intersect B| / (|A| + |B|)
```
Handles class imbalance inherently without alpha tuning.

**Recommendation:** Start with focal loss for classification. If recall drops below 95%, switch to weighted cross-entropy with hard negative mining.

### 2.2 Hard Negative Mining

The most impactful technique for Pass 2 performance:

1. Run Pass 1 threshold detector on training data
2. Collect all false positives from Pass 1 (these are the hard negatives)
3. Ensure training set includes 2-3x as many hard negatives as fire positives
4. Categories of hard negatives: sun glint, hot desert, volcanic activity, industrial heat sources, cloud edges

### 2.3 Data Augmentation

Limited options for satellite fire patches (no color jitter, no large rotations):
- Horizontal/vertical flips (safe)
- 90-degree rotations (safe)
- Small Gaussian noise (sigma=0.01-0.05 of channel std)
- Random crop from 72x72 to 64x64 (spatial jitter)
- **Do NOT** use: color jitter, brightness/contrast shifts, elastic deformation (all destroy the radiometric signal)

### 2.4 Training Schedule

```
Optimizer: AdamW (lr=1e-3, weight_decay=1e-4)
Scheduler: CosineAnnealingLR over 50 epochs
Batch size: 128-256
Early stopping: patience=10, monitor val_recall
```

Key: monitor recall, not accuracy. A model with 99% accuracy but 90% recall is worse than one with 96% accuracy and 98% recall for fire detection.

### 2.5 Constructing Training Sets

**Positive samples (fire):**
1. Use VIIRS 375m active fire product (high-confidence pixels, confidence >= 80%)
2. Cross-reference with FIRMS archive data
3. Map VIIRS fire locations to corresponding Himawari-8/GOES imagery (within 10-minute window)
4. Extract patches centered on fire pixels
5. Typical dataset: 2,000-10,000 fire patches per region

**Negative samples (non-fire):**
1. Random background patches from fire-free scenes (easy negatives, 1x fire count)
2. Hard negatives from Pass 1 false positives (2-3x fire count)
3. Known confusers: sun glint, desert, volcanic, urban heat islands, cloud edges
4. Sample across seasons, times of day, and geographic regions

**Ratio:** 1:3 to 1:5 (fire:non-fire), with at least half of non-fire being hard negatives.

## 3. Anomaly Detection Approaches

### 3.1 Autoencoder-Based Anomaly Detection

Train an autoencoder exclusively on non-fire data. Fire pixels produce high reconstruction error.

**Architecture (FC Autoencoder for per-pixel features):**
```
Encoder: Input(N) -> 512 -> 256 -> 128 -> 64 -> 32 (latent)
Decoder: 32 -> 64 -> 128 -> 256 -> 512 -> Output(N)
Activation: ReLU
```

Where N = number of input features per pixel (band values + derived features).

**Anomaly scoring:**
```
threshold = mean_MSLE(train) + 2 * std_MSLE(train)
anomaly = MSLE(test) > threshold
```

**Performance (from Ustek et al. 2024 on Australian wildfire data):**
- FC Autoencoder: 71.1% accuracy, 74.2% F1, AUC ~78%
- LSTM Autoencoder: AUC ~51% (poor)
- Isolation Forest on latent features: F1 42-72%

**Verdict:** Autoencoders alone are insufficient for primary fire detection (~74% F1 vs >95% needed). However, reconstruction error serves as a useful auxiliary feature fed into the CNN classifier.

### 3.2 Isolation Forest

Unsupervised anomaly detection using random feature splits:
- Anomalies require fewer splits to isolate (shorter path length)
- Trains on per-pixel feature vectors
- No labeled data needed
- Scikit-learn implementation: `IsolationForest(n_estimators=100, contamination=0.01)`

**Best use:** Complement CNN classification. If both CNN and Isolation Forest agree on fire, confidence is higher.

### 3.3 One-Class SVM

Learns a decision boundary around normal (non-fire) data:
- Kernel: RBF with gamma='scale'
- nu: 0.01-0.05 (expected anomaly fraction)
- Slower training than Isolation Forest for large datasets
- Better than Isolation Forest when feature space is low-dimensional (<20 features)

### 3.4 Recommended Hybrid Approach

```
Candidate pixel from Pass 1
     |
     +---> CNN classifier (primary) --> fire probability
     |
     +---> Autoencoder reconstruction error --> anomaly score
     |
     +---> Isolation Forest --> anomaly flag
     |
  Ensemble: fire if CNN_prob > 0.5 AND (autoencoder_score > threshold OR iso_forest_flag)
  Or: weighted average of all three scores
```

This reduces false positives by 10-20% over CNN alone while maintaining recall.

## 4. Inference Optimization

### 4.1 ONNX Runtime

Convert PyTorch model to ONNX for 2-3x inference speedup:

```python
# Export
torch.onnx.export(model, dummy_input, "fire_classifier.onnx",
                  input_names=["input"], output_names=["output"],
                  dynamic_axes={"input": {0: "batch_size"}})

# Inference
import onnxruntime as ort
session = ort.InferenceSession("fire_classifier.onnx",
                                providers=["CUDAExecutionProvider"])
output = session.run(None, {"input": batch_numpy})
```

### 4.2 INT8 Quantization

**Post-training quantization (easiest):**
```python
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic("fire_classifier.onnx", "fire_classifier_int8.onnx",
                 weight_type=QuantType.QInt8)
```

**Static quantization (better accuracy, requires calibration data):**
```python
from onnxruntime.quantization import quantize_static, CalibrationDataReader

class FireCalibrationReader(CalibrationDataReader):
    def __init__(self, calibration_dataset):
        self.data = iter(calibration_dataset)
    def get_next(self):
        try:
            return {"input": next(self.data)}
        except StopIteration:
            return None

quantize_static("fire_classifier.onnx", "fire_classifier_int8.onnx",
                FireCalibrationReader(cal_data))
```

**Expected speedups:**
| Configuration | Latency (per patch) | Model Size |
|---|---|---|
| PyTorch FP32, GPU | ~10ms | ~0.8MB |
| ONNX FP32, GPU | ~3ms | ~0.8MB |
| ONNX FP32, CPU | ~30ms | ~0.8MB |
| ONNX INT8, CPU (VNNI) | ~10ms | ~0.2MB |
| TensorRT FP16, GPU | ~1ms | ~0.4MB |

Note: INT8 speedups require hardware with VNNI (Intel) or INT8 Tensor Cores (NVIDIA). On older hardware, INT8 may be slower than FP32 due to quantize/dequantize overhead.

### 4.3 TensorRT (NVIDIA GPUs only)

For maximum GPU throughput:
```python
import onnxruntime as ort
session = ort.InferenceSession("fire_classifier.onnx",
    providers=[("TensorRTExecutionProvider", {
        "trt_max_workspace_size": 2 << 30,
        "trt_fp16_enable": True,
    })])
```

TensorRT FP16 gives ~3.7x speedup over FP32 for ResNet-50 class models. For our small CNN, expect 2-3x speedup.

### 4.4 Batch Processing

Process all candidates from one scan simultaneously:

```python
# Collect all candidate patches into a single batch
batch = np.stack(candidate_patches)  # (N, C, H, W)

# Single forward pass for all candidates
outputs = session.run(None, {"input": batch})
fire_probs = softmax(outputs[0], axis=1)[:, 1]  # fire probability

# Filter
confirmed = fire_probs > threshold
```

Batch inference is 10-50x faster than processing candidates one at a time due to GPU parallelism.

### 4.5 Latency Budget

For a 10-minute Himawari-8 scan cycle:
```
Data download + decode:  30-60s
Pass 1 threshold scan:   5-10s
Pass 2 CNN (100 candidates, batched): 0.1-0.5s on GPU
Alert generation:        <1s
---
Total:                   36-72s (well within 10min budget)
```

The CNN is not the bottleneck. Data download and Pass 1 dominate latency.
