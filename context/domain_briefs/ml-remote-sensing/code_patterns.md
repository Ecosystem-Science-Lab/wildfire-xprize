# Code Patterns: PyTorch/ONNX Data Loading, Training, and Inference

## 1. Dataset and Data Loading

### 1.1 Custom Fire Patch Dataset

```python
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
import rasterio
from pathlib import Path


class FirePatchDataset(Dataset):
    """Dataset of pre-extracted satellite patches for fire classification.

    Expects a directory structure:
        patches/
            fire/
                patch_001.npy    # shape: (C, H, W)
                patch_002.npy
            nofire/
                patch_001.npy
                patch_002.npy

    Each .npy file contains a multi-channel patch where channels are
    pre-computed features (T4, T11, delta-T, delta-T-background, etc.)
    """

    def __init__(self, root_dir: str, patch_size: int = 64,
                 transform=None, channel_stats=None):
        self.root_dir = Path(root_dir)
        self.patch_size = patch_size
        self.transform = transform
        self.channel_stats = channel_stats  # dict with 'mean' and 'std' arrays

        self.samples = []
        for label, class_dir in enumerate(["nofire", "fire"]):
            class_path = self.root_dir / class_dir
            if class_path.exists():
                for f in sorted(class_path.glob("*.npy")):
                    self.samples.append((f, label))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        patch = np.load(path).astype(np.float32)  # (C, H, W)

        # Normalize using precomputed channel statistics
        if self.channel_stats is not None:
            mean = self.channel_stats["mean"][:, None, None]  # (C, 1, 1)
            std = self.channel_stats["std"][:, None, None]
            patch = (patch - mean) / (std + 1e-8)

        patch = torch.from_numpy(patch)
        label = torch.tensor(label, dtype=torch.long)

        if self.transform is not None:
            patch = self.transform(patch)

        return patch, label


class FirePatchAugmentation:
    """Safe augmentations for satellite fire patches.

    Only geometric transforms that preserve radiometric values.
    Do NOT use color jitter, brightness/contrast, or elastic deformation.
    """

    def __init__(self, p_flip=0.5, noise_std=0.02):
        self.p_flip = p_flip
        self.noise_std = noise_std

    def __call__(self, patch: torch.Tensor) -> torch.Tensor:
        # Random horizontal flip
        if torch.rand(1).item() < self.p_flip:
            patch = torch.flip(patch, dims=[-1])

        # Random vertical flip
        if torch.rand(1).item() < self.p_flip:
            patch = torch.flip(patch, dims=[-2])

        # Random 90-degree rotation
        k = torch.randint(0, 4, (1,)).item()
        if k > 0:
            patch = torch.rot90(patch, k, dims=[-2, -1])

        # Small Gaussian noise
        if self.noise_std > 0:
            noise = torch.randn_like(patch) * self.noise_std
            patch = patch + noise

        return patch
```

### 1.2 Patch Extraction from Full-Disk Satellite Data

```python
import numpy as np
import h5py  # or netCDF4 for Himawari data


def extract_candidate_patches(
    satellite_data: dict,     # band_name -> 2D array
    candidate_pixels: list,   # list of (row, col) tuples from Pass 1
    patch_size: int = 64,
    bands: list = None,
) -> np.ndarray:
    """Extract multi-band patches around candidate fire pixels.

    Args:
        satellite_data: dict mapping band names to 2D arrays.
            Example: {"T4": arr, "T11": arr, "delta_T": arr, ...}
        candidate_pixels: list of (row, col) from Pass 1 detector
        patch_size: spatial size of extracted patch
        bands: ordered list of band names to use as channels

    Returns:
        patches: array of shape (N, C, patch_size, patch_size)
    """
    if bands is None:
        bands = list(satellite_data.keys())

    half = patch_size // 2
    h, w = satellite_data[bands[0]].shape
    patches = []
    valid_indices = []

    for i, (r, c) in enumerate(candidate_pixels):
        # Skip candidates too close to image edge
        if r < half or r >= h - half or c < half or c >= w - half:
            continue

        patch_channels = []
        for band_name in bands:
            band_data = satellite_data[band_name]
            patch = band_data[r - half:r + half, c - half:c + half]
            patch_channels.append(patch)

        patches.append(np.stack(patch_channels, axis=0))  # (C, H, W)
        valid_indices.append(i)

    if not patches:
        return np.empty((0, len(bands), patch_size, patch_size), dtype=np.float32), []

    return np.stack(patches).astype(np.float32), valid_indices


def compute_derived_features(t4: np.ndarray, t11: np.ndarray,
                              window_size: int = 11) -> dict:
    """Compute derived features from brightness temperature bands.

    Args:
        t4: 2D array of 3.9um brightness temperature (K)
        t11: 2D array of 11.2um brightness temperature (K)
        window_size: size of contextual window for background stats

    Returns:
        dict of derived feature arrays, same shape as input
    """
    from scipy.ndimage import uniform_filter

    delta_t = t4 - t11

    # Background statistics (mean/std of surrounding window)
    t4_bg_mean = uniform_filter(t4, size=window_size)
    t4_bg_std = np.sqrt(uniform_filter((t4 - t4_bg_mean)**2, size=window_size))

    t11_bg_mean = uniform_filter(t11, size=window_size)

    dt_bg_mean = uniform_filter(delta_t, size=window_size)
    dt_bg_std = np.sqrt(uniform_filter((delta_t - dt_bg_mean)**2, size=window_size))

    return {
        "T4": t4,
        "T11": t11,
        "delta_T": delta_t,
        "T4_anomaly": t4 - t4_bg_mean,
        "T11_anomaly": t11 - t11_bg_mean,
        "delta_T_anomaly": delta_t - dt_bg_mean,
        "T4_zscore": (t4 - t4_bg_mean) / (t4_bg_std + 1e-8),
        "delta_T_zscore": (delta_t - dt_bg_mean) / (dt_bg_std + 1e-8),
    }
```

### 1.3 DataLoader Setup

```python
def create_dataloaders(train_dir, val_dir, batch_size=128, num_workers=4):
    """Create train/val dataloaders with proper sampling."""

    # Compute channel statistics from training data
    channel_stats = compute_channel_stats(train_dir)

    train_dataset = FirePatchDataset(
        train_dir,
        transform=FirePatchAugmentation(p_flip=0.5, noise_std=0.02),
        channel_stats=channel_stats,
    )

    val_dataset = FirePatchDataset(
        val_dir,
        transform=None,
        channel_stats=channel_stats,  # same stats as training
    )

    # Weighted sampler to handle class imbalance
    labels = [s[1] for s in train_dataset.samples]
    class_counts = np.bincount(labels)
    weights = 1.0 / class_counts[labels]
    sampler = torch.utils.data.WeightedRandomSampler(
        weights, len(weights), replacement=True
    )

    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, sampler=sampler,
        num_workers=num_workers, pin_memory=True, drop_last=True
    )

    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )

    return train_loader, val_loader, channel_stats


def compute_channel_stats(data_dir: str) -> dict:
    """Compute per-channel mean and std from all patches in a directory."""
    all_patches = []
    root = Path(data_dir)
    for npy_file in root.rglob("*.npy"):
        all_patches.append(np.load(npy_file))

    all_patches = np.stack(all_patches)  # (N, C, H, W)
    mean = all_patches.mean(axis=(0, 2, 3))  # (C,)
    std = all_patches.std(axis=(0, 2, 3))    # (C,)

    return {"mean": mean.astype(np.float32), "std": std.astype(np.float32)}
```

## 2. Model Definition

### 2.1 Small Fire CNN

```python
import torch
import torch.nn as nn


class FireCNN(nn.Module):
    """Lightweight CNN for fire/no-fire patch classification.

    Designed for 64x64 multi-channel satellite patches.
    ~150K-200K parameters depending on input channels.
    """

    def __init__(self, in_channels: int = 4, num_classes: int = 2,
                 dropout: float = 0.25):
        super().__init__()

        self.features = nn.Sequential(
            # Block 1: 64x64 -> 32x32
            nn.Conv2d(in_channels, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout2d(dropout),

            # Block 2: 32x32 -> 16x16
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout2d(dropout),

            # Block 3: 16x16 -> 8x8
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout2d(dropout),
        )

        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(64, num_classes),
        )

    def forward(self, x):
        x = self.features(x)
        x = self.classifier(x)
        return x

    def count_parameters(self):
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class FireCNNWithConfidence(nn.Module):
    """FireCNN variant that outputs calibrated probabilities.

    Adds temperature scaling for better-calibrated confidence scores.
    """

    def __init__(self, in_channels: int = 4):
        super().__init__()
        self.backbone = FireCNN(in_channels=in_channels, num_classes=2)
        self.temperature = nn.Parameter(torch.ones(1) * 1.5)

    def forward(self, x):
        logits = self.backbone(x)
        # Temperature scaling for calibration
        scaled_logits = logits / self.temperature
        return scaled_logits

    def predict_proba(self, x):
        """Return calibrated fire probability."""
        with torch.no_grad():
            logits = self.forward(x)
            probs = torch.softmax(logits, dim=1)
            return probs[:, 1]  # fire probability
```

### 2.2 SSRN (Spectral-Spatial Residual Network)

```python
class SpectralResidualBlock(nn.Module):
    """1D convolution along spectral dimension."""

    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv3d(1, channels, kernel_size=(7, 1, 1), padding=(3, 0, 0))
        self.bn1 = nn.BatchNorm3d(channels)
        self.conv2 = nn.Conv3d(channels, 1, kernel_size=(7, 1, 1), padding=(3, 0, 0))
        self.bn2 = nn.BatchNorm3d(1)

    def forward(self, x):
        residual = x
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return torch.relu(out + residual)


class SpatialResidualBlock(nn.Module):
    """2D convolution along spatial dimensions."""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv1 = nn.Conv2d(in_channels, out_channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels)
        self.skip = nn.Conv2d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()

    def forward(self, x):
        residual = self.skip(x)
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return torch.relu(out + residual)


class SSRN(nn.Module):
    """Spectral-Spatial Residual Network for multispectral classification.

    Better than standard CNNs when spectral channels carry strong signal.
    ~250K parameters.
    """

    def __init__(self, in_channels: int, num_classes: int = 2, patch_size: int = 64):
        super().__init__()

        # Spectral feature extraction (treats input as 3D: 1 x C x H x W)
        self.spectral = nn.Sequential(
            SpectralResidualBlock(24),
            SpectralResidualBlock(24),
        )

        # Spatial feature extraction
        self.spatial = nn.Sequential(
            SpatialResidualBlock(in_channels, 64),
            nn.MaxPool2d(2),
            SpatialResidualBlock(64, 128),
            nn.MaxPool2d(2),
        )

        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )

    def forward(self, x):
        # Spectral processing: (B, C, H, W) -> (B, 1, C, H, W)
        x_3d = x.unsqueeze(1)
        x_3d = self.spectral(x_3d)
        x = x_3d.squeeze(1)  # back to (B, C, H, W)

        # Spatial processing
        x = self.spatial(x)
        x = self.classifier(x)
        return x
```

## 3. Training Loop

### 3.1 Focal Loss Implementation

```python
class FocalLoss(nn.Module):
    """Focal loss for handling class imbalance in fire detection.

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
    """

    def __init__(self, alpha=None, gamma=2.0):
        super().__init__()
        if alpha is None:
            alpha = torch.tensor([0.25, 0.75])  # [nofire_weight, fire_weight]
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, inputs, targets):
        ce_loss = nn.functional.cross_entropy(inputs, targets, reduction='none')
        pt = torch.exp(-ce_loss)

        alpha_t = self.alpha.to(inputs.device)[targets]
        focal_loss = alpha_t * (1 - pt) ** self.gamma * ce_loss

        return focal_loss.mean()
```

### 3.2 Training Script

```python
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import recall_score, precision_score, f1_score
import numpy as np
from pathlib import Path


def train_fire_classifier(
    train_dir: str,
    val_dir: str,
    in_channels: int = 4,
    patch_size: int = 64,
    epochs: int = 50,
    batch_size: int = 128,
    lr: float = 1e-3,
    save_dir: str = "checkpoints",
):
    """Train fire/no-fire classifier."""

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Data
    train_loader, val_loader, channel_stats = create_dataloaders(
        train_dir, val_dir, batch_size=batch_size
    )

    # Model
    model = FireCNN(in_channels=in_channels, num_classes=2).to(device)
    print(f"Model parameters: {model.count_parameters():,}")

    # Loss, optimizer, scheduler
    criterion = FocalLoss(alpha=torch.tensor([0.25, 0.75]), gamma=2.0)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

    # Training loop
    best_recall = 0.0
    patience_counter = 0
    save_path = Path(save_dir)
    save_path.mkdir(exist_ok=True)

    for epoch in range(epochs):
        # Train
        model.train()
        train_loss = 0.0
        for batch_patches, batch_labels in train_loader:
            batch_patches = batch_patches.to(device)
            batch_labels = batch_labels.to(device)

            optimizer.zero_grad()
            outputs = model(batch_patches)
            loss = criterion(outputs, batch_labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        scheduler.step()

        # Validate
        model.eval()
        all_preds = []
        all_labels = []
        val_loss = 0.0

        with torch.no_grad():
            for batch_patches, batch_labels in val_loader:
                batch_patches = batch_patches.to(device)
                batch_labels = batch_labels.to(device)

                outputs = model(batch_patches)
                loss = criterion(outputs, batch_labels)
                val_loss += loss.item()

                preds = outputs.argmax(dim=1)
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(batch_labels.cpu().numpy())

        all_preds = np.array(all_preds)
        all_labels = np.array(all_labels)

        recall = recall_score(all_labels, all_preds, pos_label=1)
        precision = precision_score(all_labels, all_preds, pos_label=1)
        f1 = f1_score(all_labels, all_preds, pos_label=1)

        avg_train_loss = train_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)

        print(f"Epoch {epoch+1}/{epochs} | "
              f"Train Loss: {avg_train_loss:.4f} | "
              f"Val Loss: {avg_val_loss:.4f} | "
              f"Recall: {recall:.4f} | "
              f"Precision: {precision:.4f} | "
              f"F1: {f1:.4f}")

        # Save best model (by recall, not accuracy)
        if recall > best_recall:
            best_recall = recall
            patience_counter = 0
            torch.save({
                "model_state_dict": model.state_dict(),
                "channel_stats": channel_stats,
                "in_channels": in_channels,
                "epoch": epoch,
                "recall": recall,
                "precision": precision,
                "f1": f1,
            }, save_path / "best_model.pt")
            print(f"  -> Saved best model (recall={recall:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= 10:
                print(f"Early stopping at epoch {epoch+1}")
                break

    return model, channel_stats
```

## 4. ONNX Export and Inference

### 4.1 Export to ONNX

```python
def export_to_onnx(model: nn.Module, in_channels: int, patch_size: int = 64,
                   output_path: str = "fire_classifier.onnx"):
    """Export PyTorch model to ONNX with dynamic batch size."""

    model.eval()
    model.cpu()

    dummy_input = torch.randn(1, in_channels, patch_size, patch_size)

    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        input_names=["input"],
        output_names=["logits"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "logits": {0: "batch_size"},
        },
        opset_version=17,
    )
    print(f"Exported ONNX model to {output_path}")

    # Verify
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("ONNX model verification passed")
```

### 4.2 ONNX Runtime Inference Pipeline

```python
import onnxruntime as ort
import numpy as np
from typing import List, Tuple


class FireClassifierONNX:
    """Production inference pipeline using ONNX Runtime.

    Handles batch processing of candidates from Pass 1.
    """

    def __init__(self, model_path: str, channel_stats: dict,
                 threshold: float = 0.5, use_gpu: bool = True):
        providers = []
        if use_gpu:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        self.session = ort.InferenceSession(model_path, providers=providers)
        self.channel_stats = channel_stats
        self.threshold = threshold

        # Verify model loaded on expected device
        active_provider = self.session.get_providers()[0]
        print(f"ONNX Runtime using: {active_provider}")

    def preprocess(self, patches: np.ndarray) -> np.ndarray:
        """Normalize patches using training statistics.

        Args:
            patches: (N, C, H, W) float32 array of raw feature patches

        Returns:
            Normalized patches ready for inference
        """
        mean = self.channel_stats["mean"][None, :, None, None]  # (1, C, 1, 1)
        std = self.channel_stats["std"][None, :, None, None]
        return ((patches - mean) / (std + 1e-8)).astype(np.float32)

    def classify_candidates(
        self,
        satellite_data: dict,
        candidate_pixels: List[Tuple[int, int]],
        bands: List[str],
        patch_size: int = 64,
    ) -> dict:
        """Classify candidate fire pixels from Pass 1.

        Args:
            satellite_data: dict of band_name -> 2D array
            candidate_pixels: list of (row, col) from Pass 1
            bands: ordered list of band names matching model input channels
            patch_size: spatial patch size

        Returns:
            dict with 'fire_pixels', 'fire_probabilities', 'all_probabilities'
        """
        if not candidate_pixels:
            return {"fire_pixels": [], "fire_probabilities": [],
                    "all_probabilities": []}

        # Extract patches
        patches, valid_indices = extract_candidate_patches(
            satellite_data, candidate_pixels, patch_size, bands
        )

        if len(patches) == 0:
            return {"fire_pixels": [], "fire_probabilities": [],
                    "all_probabilities": []}

        # Normalize
        patches_norm = self.preprocess(patches)

        # Batch inference
        logits = self.session.run(None, {"input": patches_norm})[0]

        # Softmax for probabilities
        exp_logits = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp_logits / exp_logits.sum(axis=1, keepdims=True)
        fire_probs = probs[:, 1]

        # Filter by threshold
        fire_mask = fire_probs >= self.threshold

        fire_pixels = [candidate_pixels[valid_indices[i]]
                       for i in range(len(valid_indices)) if fire_mask[i]]
        fire_probabilities = fire_probs[fire_mask].tolist()

        return {
            "fire_pixels": fire_pixels,
            "fire_probabilities": fire_probabilities,
            "all_probabilities": fire_probs.tolist(),
            "n_candidates": len(candidate_pixels),
            "n_confirmed": int(fire_mask.sum()),
            "fp_reduction": 1.0 - fire_mask.mean(),
        }
```

### 4.3 Quantization

```python
def quantize_model(onnx_path: str, output_path: str,
                   calibration_data: np.ndarray = None):
    """Quantize ONNX model to INT8 for faster CPU inference.

    Args:
        onnx_path: path to FP32 ONNX model
        output_path: path for quantized model
        calibration_data: optional array of representative inputs for static quantization
    """
    if calibration_data is not None:
        # Static quantization (better accuracy, needs calibration data)
        from onnxruntime.quantization import quantize_static, CalibrationDataReader

        class FireCalibReader(CalibrationDataReader):
            def __init__(self, data):
                self.data = iter([{"input": d[None]} for d in data[:200]])

            def get_next(self):
                try:
                    return next(self.data)
                except StopIteration:
                    return None

        quantize_static(
            onnx_path, output_path,
            FireCalibReader(calibration_data),
            quant_format=ort.quantization.QuantFormat.QDQ,
        )
    else:
        # Dynamic quantization (no calibration data needed)
        from onnxruntime.quantization import quantize_dynamic, QuantType
        quantize_dynamic(
            onnx_path, output_path,
            weight_type=QuantType.QInt8,
        )

    import os
    orig_size = os.path.getsize(onnx_path)
    quant_size = os.path.getsize(output_path)
    print(f"Original:  {orig_size / 1024:.1f} KB")
    print(f"Quantized: {quant_size / 1024:.1f} KB")
    print(f"Reduction: {(1 - quant_size / orig_size) * 100:.1f}%")
```

## 5. Complete Inference Pipeline Integration

```python
class Pass2Classifier:
    """Complete Pass 2 classifier integrating CNN + optional anomaly detection.

    Usage:
        classifier = Pass2Classifier("model.onnx", channel_stats)
        results = classifier.run(satellite_data, candidate_pixels)
    """

    def __init__(
        self,
        cnn_model_path: str,
        channel_stats: dict,
        bands: list,
        patch_size: int = 64,
        fire_threshold: float = 0.5,
        use_gpu: bool = True,
        anomaly_model=None,  # optional sklearn anomaly detector
    ):
        self.cnn = FireClassifierONNX(
            cnn_model_path, channel_stats, fire_threshold, use_gpu
        )
        self.bands = bands
        self.patch_size = patch_size
        self.fire_threshold = fire_threshold
        self.anomaly_model = anomaly_model

    def run(self, satellite_data: dict,
            candidate_pixels: List[Tuple[int, int]]) -> dict:
        """Run Pass 2 classification on candidates from Pass 1.

        Args:
            satellite_data: dict of feature_name -> 2D array
                Must contain all bands in self.bands
            candidate_pixels: list of (row, col) from Pass 1

        Returns:
            dict with confirmed fire pixels, probabilities, and metadata
        """
        import time
        t0 = time.perf_counter()

        results = self.cnn.classify_candidates(
            satellite_data, candidate_pixels, self.bands, self.patch_size
        )

        # Optional: anomaly detection ensemble
        if self.anomaly_model is not None and results["all_probabilities"]:
            patches, valid_indices = extract_candidate_patches(
                satellite_data, candidate_pixels, self.patch_size, self.bands
            )
            # Flatten patches to feature vectors for anomaly detection
            flat_features = patches.reshape(len(patches), -1)
            anomaly_scores = self.anomaly_model.decision_function(flat_features)

            # Combine: require both CNN and anomaly detector agreement
            cnn_probs = np.array(results["all_probabilities"])
            combined = cnn_probs * 0.7 + (1.0 / (1.0 + np.exp(-anomaly_scores))) * 0.3

            fire_mask = combined >= self.fire_threshold
            results["fire_pixels"] = [
                candidate_pixels[valid_indices[i]]
                for i in range(len(valid_indices)) if fire_mask[i]
            ]
            results["fire_probabilities"] = combined[fire_mask].tolist()
            results["n_confirmed"] = int(fire_mask.sum())
            results["fp_reduction"] = 1.0 - fire_mask.mean()

        results["inference_time_ms"] = (time.perf_counter() - t0) * 1000
        return results
```

## 6. Model Evaluation

```python
def evaluate_fire_classifier(model_path: str, test_dir: str,
                              channel_stats: dict, in_channels: int):
    """Evaluate classifier and produce detailed metrics report."""
    from sklearn.metrics import (
        classification_report, confusion_matrix, roc_auc_score,
        precision_recall_curve
    )

    classifier = FireClassifierONNX(model_path, channel_stats, threshold=0.5)

    dataset = FirePatchDataset(test_dir, channel_stats=channel_stats)
    loader = DataLoader(dataset, batch_size=256, shuffle=False)

    all_probs = []
    all_labels = []

    for patches, labels in loader:
        patches_np = patches.numpy()
        logits = classifier.session.run(None, {"input": patches_np})[0]
        exp_l = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs = exp_l / exp_l.sum(axis=1, keepdims=True)
        all_probs.extend(probs[:, 1])
        all_labels.extend(labels.numpy())

    all_probs = np.array(all_probs)
    all_labels = np.array(all_labels)

    # Find optimal threshold for recall >= 0.95
    precisions, recalls, thresholds = precision_recall_curve(all_labels, all_probs)
    valid_mask = recalls >= 0.95
    if valid_mask.any():
        best_idx = np.argmax(precisions[valid_mask])
        optimal_threshold = thresholds[valid_mask][best_idx] if best_idx < len(thresholds[valid_mask]) else 0.5
    else:
        optimal_threshold = 0.3  # lower threshold to ensure recall

    preds = (all_probs >= optimal_threshold).astype(int)

    print("=== Fire Classifier Evaluation ===")
    print(f"Optimal threshold (recall >= 0.95): {optimal_threshold:.3f}")
    print(f"AUC-ROC: {roc_auc_score(all_labels, all_probs):.4f}")
    print(f"\n{classification_report(all_labels, preds, target_names=['nofire', 'fire'])}")
    print(f"Confusion Matrix:\n{confusion_matrix(all_labels, preds)}")

    return {
        "threshold": optimal_threshold,
        "auc_roc": roc_auc_score(all_labels, all_probs),
        "recall": recall_score(all_labels, preds),
        "precision": precision_score(all_labels, preds),
    }
```
