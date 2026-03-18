# ML for Remote Sensing: Pass 2 Candidate Classifier

## Scope

This domain brief covers the ML component of a two-pass wildfire detection pipeline:

- **Pass 1** (not covered here): Fast threshold-based detector flags candidate fire pixels using brightness temperature thresholds (e.g., T4 > 310K, delta-T > 10K).
- **Pass 2** (this brief): A lightweight CNN classifies each candidate as fire vs. non-fire to reduce false positives.

The classifier receives small image patches (32x32 or 64x64 pixels) centered on each candidate pixel, with multi-band satellite data as input channels.

## Key Constraints

| Constraint | Target |
|---|---|
| Inference latency (GPU) | <200ms per candidate |
| Inference latency (CPU) | <1s per candidate |
| Model size | <50MB (ideally <10MB) |
| False positive reduction | >80% FP reduction vs Pass 1 alone |
| Recall preservation | >95% (cannot miss real fires) |
| Candidate batch size | 10-1000 candidates per scan |
| Deployment target | Cloud GPU (primary), CPU fallback |

## Target Sensors

| Sensor | Platform | Spatial Resolution | Temporal Resolution | Key Fire Bands |
|---|---|---|---|---|
| AHI | Himawari-8/9 | 2km (IR), 0.5km (VIS) | 10 min full disk | B7 (3.9um), B14 (11.2um), B15 (12.4um) |
| ABI | GOES-16/17/18 | 2km (IR), 0.5km (VIS) | 10 min full disk | B7 (3.9um), B14 (11.2um), B15 (12.3um) |
| VIIRS | Suomi-NPP, NOAA-20/21 | 375m (I-bands) | ~12hr revisit | I4 (3.74um), I5 (11.45um) |

Himawari-8 AHI is the primary sensor for the XPRIZE competition (fires in NSW, Australia). GOES and VIIRS serve as training data sources and validation references.

## Architecture Decision: Per-Sensor vs. Unified Model

**Recommended: Per-sensor models with shared architecture.**

Rationale:
- Different sensors have different band counts, spatial resolutions, and radiometric characteristics
- Systematic bias exists between AHI and VIIRS brightness temperatures (documented in cross-calibration studies)
- A single architecture (e.g., small MobileNetV2) can be instantiated per sensor with different input channel counts
- Transfer learning from one sensor to another is viable for fine-tuning, but direct cross-sensor inference degrades accuracy

## Input Feature Design

The CNN does not receive raw radiance values. Input channels are engineered features derived from satellite bands:

### Core channels (minimum viable input)
1. **T4**: Brightness temperature at ~3.9um (fire-sensitive MWIR band)
2. **T11**: Brightness temperature at ~11.2um (background reference)
3. **delta-T**: T4 - T11 (fire signal amplification)
4. **delta-T-background**: delta-T minus mean delta-T of surrounding 11x11 window (contextual anomaly)

### Extended channels (improved accuracy)
5. **T4-background**: T4 minus mean T4 of surrounding window
6. **T11-background**: T11 minus mean T11 of surrounding window
7. **NIR reflectance**: ~0.86um band (smoke/vegetation context)
8. **SWIR reflectance**: ~1.6um or ~2.3um band (sub-pixel fire detection)
9. **Temporal delta**: T4 minus T4 from previous scan (10min ago)

### Normalization
- Brightness temperatures: standardize to zero mean, unit variance using per-band statistics from training data
- Reflectances: clip to [0, 1], then standardize
- Band differences: standardize independently

## Pipeline Position

```
Satellite Data Ingest
       |
   [Pass 1: Threshold Detector]  -- fast, high recall, many false positives
       |
   Candidate list (pixel locations + small patches)
       |
   [Pass 2: CNN Classifier]  -- this component
       |
   Confirmed fire pixels
       |
   Alert Generation
```

## Files in This Brief

- **algorithms.md**: CNN architectures, training strategies, anomaly detection methods, inference optimization
- **apis_and_data_access.md**: Training data sources, pre-trained models, compute resources
- **code_patterns.md**: PyTorch/ONNX patterns, data loading, training loops, inference pipelines
- **pitfalls.md**: Overfitting, class imbalance, geographic bias, latency traps, model drift

## Key References

- Xu et al. (2022). "Active Fire Detection Using a Novel Convolutional Neural Network Based on Himawari-8 Satellite Images." Frontiers in Environmental Science.
- Zhang et al. (2025). "Near-real-time wildfire detection approach with Himawari-8/9 geostationary satellite data integrating multi-scale spatial-temporal feature." JAG.
- Kim et al. (2023). "Early Stage Forest Fire Detection from Himawari-8 AHI Images Using a Modified MOD14 Algorithm Combined with Machine Learning." Sensors.
- Pereira et al. (2021). "Active Fire Detection in Landsat-8 Imagery: A Large-Scale Dataset and a Deep-Learning Study." ISPRS J. Photogrammetry.
- Jaafari et al. (2024). "Deep Autoencoders for Unsupervised Anomaly Detection in Wildfire Prediction." Earth and Space Science.
- Zhang et al. (2025). "TS-SatFire: A Multi-Task Satellite Image Time-Series Dataset for Wildfire Detection and Prediction." Scientific Data.
- Shahid (2023). "FireNet-v2: Improved Lightweight Fire Detection Model for Real-Time IoT Applications." Procedia Computer Science.
- Valero et al. (2025). "PyroFocus: A Deep Learning Approach to Real-Time Wildfire Detection in Multispectral Remote Sensing Imagery." arXiv.
