# APIs and Data Access: Training Data, Pre-Trained Models, Compute Resources

## 1. Training Data Sources

### 1.1 NASA FIRMS (Fire Information for Resource Management System)

The primary source for fire detection labels.

**API endpoint:** `https://firms.modaps.eosdis.nasa.gov/api/`

**Products available:**
| Product | Sensor | Resolution | Temporal Coverage |
|---|---|---|---|
| MODIS C6.1 | Terra/Aqua MODIS | 1km | Nov 2000 - present |
| VIIRS 375m | Suomi-NPP | 375m | Jan 2012 - present |
| VIIRS 375m | NOAA-20 | 375m | Apr 2018 - present |
| VIIRS 375m | NOAA-21 | 375m | Jan 2024 - present |

**Data format:** CSV, SHP, KML, JSON

**Key fields per fire detection:**
- `latitude`, `longitude`: fire pixel center
- `brightness`: brightness temperature (K) in MWIR band
- `bright_t31`: brightness temperature in 11um band
- `confidence`: detection confidence (low/nominal/high for VIIRS, 0-100 for MODIS)
- `frp`: fire radiative power (MW)
- `acq_date`, `acq_time`: acquisition timestamp
- `daynight`: D or N

**API access:**
```python
import requests

MAP_KEY = "your_key_here"  # free registration at earthdata.nasa.gov
url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/world/1"
# Returns last 1 day of global VIIRS fire detections

# For archive data (specific region, date range):
url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_SP/[-180,-90,180,90]/1/2024-01-01"
```

Rate limit: 5000 requests per 10 minutes.

**Archive download:** https://firms.modaps.eosdis.nasa.gov/download/ for bulk historical data.

### 1.2 Geostationary Active Fire Products

Available through FIRMS for direct comparison and label construction:
- **GOES-16/18 ABI Fire/Hotspot Characterization (FHC)**
- **Himawari-8 AHI Wildfire Product (WLF)**
- **Meteosat SEVIRI Active Fire Monitoring**

Himawari-8 wildfire product documentation: https://www.eorc.jaxa.jp/ptree/documents/README_H08_L2WLF.txt

### 1.3 Published Datasets

#### Landsat-8 Active Fire Dataset (Pereira et al. 2021)
- **Size:** 146,214 image patches, >200GB
- **Bands:** 10 Landsat-8 spectral bands
- **Labels:** Outputs from 3 handcrafted fire algorithms + manual annotations
- **Coverage:** Global, Aug-Sep 2020
- **Access:** https://github.com/pereira-gha/activefire (Google Drive links)
- **Best result:** 87.2% precision, 92.4% recall with CNN ensemble
- **Use case:** Pre-training and architecture validation

#### TS-SatFire (Zhang et al. 2025)
- **Size:** 3,552 VIIRS surface reflectance images, 71GB
- **Bands:** 6 VIIRS bands (I1-I5, M11)
- **Labels:** Active fire masks, burned area masks (manually QA'd)
- **Coverage:** Contiguous US, Jan 2017 - Oct 2021
- **Tasks:** Active fire detection, burned area mapping, fire progression prediction
- **Access:** https://github.com/zhaoyutim/ts-satfire and https://www.kaggle.com/datasets/z789456sx/ts-satfire
- **Use case:** Time-series fire detection, multi-task training

#### PyroNear2025
- **Coverage:** Camera-based wildfire detection (not satellite, but useful for data augmentation ideas)
- **Access:** https://arxiv.org/html/2402.05349v3

### 1.4 Constructing Himawari-8 Training Data

Since no large public Himawari-8 fire classification dataset exists, construct one:

**Step 1: Get fire labels from VIIRS**
```python
# Download VIIRS high-confidence fire detections for Australia
# Filter: confidence == "high", country == "AUS"
# Time range: 2019-2024 (includes 2019-2020 Black Summer fires)
```

**Step 2: Match to Himawari-8 imagery**
```python
# For each VIIRS fire detection:
#   Find Himawari-8 full-disk scan within +/- 5 minutes of VIIRS overpass
#   Extract 64x64 patch centered on VIIRS fire location
#   Label as "fire"
```

**Step 3: Construct negatives**
```python
# Easy negatives: random patches from fire-free scans (same region, different dates)
# Hard negatives: patches flagged by Pass 1 threshold detector but NOT confirmed by VIIRS
# Confuser patches: known hot spots (volcanoes, refineries, sun glint locations)
```

**Step 4: Handle cross-sensor bias**
VIIRS and Himawari-8 have systematic brightness temperature differences. The VIIRS 375m pixel may detect sub-pixel fires that Himawari-8's 2km pixel smooths out. Account for this by:
- Only using VIIRS fires with FRP > 10 MW (detectable at 2km)
- Buffering fire locations by 1km when matching

### 1.5 Himawari-8 Data Access

**JAXA P-Tree System:** https://www.eorc.jaxa.jp/ptree/
- Free registration required
- Full-disk data every 10 minutes
- Formats: NetCDF4, HSD (Himawari Standard Data)

**AWS Open Data:** Himawari-8 data available on S3
```
s3://noaa-himawari8/AHI-L1b-FLDK/
```

**Australian Bureau of Meteorology:** Direct access for registered users.

### 1.6 GOES Data Access

**AWS Open Data (free, no auth):**
```
s3://noaa-goes16/ABI-L1b-RadF/  (GOES-16 full disk)
s3://noaa-goes17/ABI-L1b-RadF/  (GOES-17 full disk)
s3://noaa-goes18/ABI-L1b-RadF/  (GOES-18 full disk)
```

**Google Cloud:** `gs://gcp-public-data-goes-16/`

## 2. Pre-Trained Models and Frameworks

### 2.1 TorchGeo

PyTorch domain library for geospatial data. Provides:
- GeoDataset class with spatiotemporal indexing
- Pre-trained models on multispectral imagery (Sentinel-2, Landsat)
- Samplers that handle CRS and resolution mismatches
- Kornia-based transforms that support >3 channels

```bash
pip install torchgeo
```

Key classes:
- `torchgeo.datasets.RasterDataset`: base for custom satellite datasets
- `torchgeo.samplers.RandomGeoSampler`: spatiotemporal sampling
- `torchgeo.transforms`: multispectral augmentations

### 2.2 TorchSat

Open-source deep learning framework for satellite imagery:
- https://github.com/sshuair/torchsat
- Simpler than TorchGeo, good for quick experiments
- Built-in classification models

### 2.3 torchrs

PyTorch implementations of remote sensing models and datasets:
- https://github.com/isaaccorley/torchrs
- Covers Sentinel-2, Landsat, SAR
- Good reference implementations

### 2.4 Satellighte

PyTorch Lightning implementations for satellite image classification:
- https://github.com/canturan10/satellighte
- Lightning-based training loops (easier experiment tracking)

### 2.5 Pretrained Weights

For transfer learning (limited value for multispectral, but useful for RGB components):
- `torchvision.models.mobilenet_v2(pretrained=True)`: first conv must be replaced for >3 channels
- `timm` library: EfficientNet-Lite, ResNet variants
- TorchGeo pretrained models: trained on Sentinel-2 multispectral data (more relevant than ImageNet)

## 3. Compute Resources

### 3.1 Training Compute

| Resource | Cost | GPU | RAM | Suitability |
|---|---|---|---|---|
| Google Colab Pro | $10/mo | T4 16GB | 25GB | Prototyping, small experiments |
| AWS g4dn.xlarge | ~$0.53/hr | T4 16GB | 16GB | Training runs |
| AWS g5.xlarge | ~$1.01/hr | A10G 24GB | 16GB | Larger experiments |
| Lambda Cloud A100 | ~$1.10/hr | A100 40GB | 200GB | Full dataset training |

Our small CNN (~150K params) trains in <1 hour on a T4 with 10K training samples. Cost: <$1.

### 3.2 Inference Compute

| Deployment | Hardware | Latency (batch=100) | Cost |
|---|---|---|---|
| Cloud GPU | T4 | 50-100ms total | ~$0.50/hr |
| Cloud GPU | A10G | 20-50ms total | ~$1.00/hr |
| Cloud CPU | c5.xlarge (4 vCPU) | 1-3s total | ~$0.17/hr |
| Cloud CPU + ONNX INT8 | c5.xlarge (VNNI) | 0.5-1s total | ~$0.17/hr |

For the XPRIZE competition, a single T4 instance is sufficient. Total monthly cost for 24/7 inference: ~$360.

### 3.3 Model Versioning and Experiment Tracking

**Recommended tools:**
- **MLflow**: Track experiments, compare runs, log models
- **Weights & Biases (wandb)**: Free for personal use, better visualization
- **DVC**: Version control for datasets alongside model code

```bash
pip install wandb mlflow
```

## 4. Label Quality and Validation

### 4.1 VIIRS Confidence Levels

| Confidence | Description | Use |
|---|---|---|
| low | Possible fire, many false positives | Exclude from training |
| nominal | Likely fire | Include with care, weight lower |
| high | Very likely fire | Primary positive labels |

### 4.2 Cross-Validation with Multiple Sources

For high-quality labels, require agreement between 2+ sources:
1. VIIRS high-confidence detection
2. GOES/Himawari fire product detection
3. Ground-based reports (available for Australia via NSW Rural Fire Service)

### 4.3 Commission and Omission Error Rates

VIIRS 375m active fire product:
- Commission error: ~2% (false fires) for high-confidence
- Omission error: ~5-10% (missed fires, mainly small/cool fires)

MODIS 1km active fire product:
- Commission error: ~5% for high-confidence
- Omission error: ~15-20% (misses smaller fires)

Use VIIRS as primary label source. MODIS is supplementary for pre-2012 historical data.
