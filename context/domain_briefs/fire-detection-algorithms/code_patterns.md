# Fire Detection Algorithms — Code Patterns

## Language and Framework Choices

### Python (primary)
- **NumPy/SciPy**: Core array operations, fast threshold tests
- **xarray**: NetCDF/HDF5 satellite data with labeled dimensions
- **satpy**: High-level satellite data reading and processing (supports VIIRS, AHI, ABI)
- **numba**: JIT compilation for hot-path detection loops
- **cupy**: GPU-accelerated array operations (drop-in NumPy replacement)

### For production latency-critical path
- Consider **Rust** or **C++** for the innermost detection loop
- **ONNX Runtime** for ML inference
- Python orchestration with compiled kernels for compute

## Core Detection Implementation Patterns

### Brightness temperature from radiance
```python
import numpy as np

def radiance_to_bt(radiance, wavelength_um, c1=1.191042e8, c2=1.4387752e4):
    """Convert spectral radiance to brightness temperature.

    Args:
        radiance: W/m²/sr/μm
        wavelength_um: central wavelength in micrometers
        c1, c2: Planck constants (default CGS-compatible)
    Returns:
        brightness temperature in Kelvin
    """
    return c2 / (wavelength_um * np.log(c1 / (wavelength_um**5 * radiance) + 1))
```

### VIIRS-style contextual detection (simplified)
```python
import numpy as np
from scipy.ndimage import uniform_filter

def viirs_contextual_detect(bt4, bt5, cloud_mask, water_mask, is_daytime):
    """Simplified VIIRS-style contextual fire detection.

    Args:
        bt4: 2D array of I4 brightness temperatures (K)
        bt5: 2D array of I5 brightness temperatures (K)
        cloud_mask: boolean 2D array (True = cloud)
        water_mask: boolean 2D array (True = water)
        is_daytime: boolean
    Returns:
        fire_mask: integer array (0=no fire, 7=low, 8=nominal, 9=high)
    """
    h, w = bt4.shape
    fire_mask = np.zeros((h, w), dtype=np.int8)
    dbt = bt4 - bt5  # ΔBT45

    # Valid mask (not cloud, not water, valid data)
    valid = ~cloud_mask & ~water_mask & (bt4 > 0) & (bt5 > 0)

    # --- Fixed threshold tests (high confidence) ---
    if not is_daytime:
        high_conf = valid & (bt4 > 320)
        fire_mask[high_conf] = 9

    # --- Candidate selection ---
    if is_daytime:
        # Compute scene-dependent BT4S from large-area median
        # (simplified: use percentile of valid background)
        bg_bt4 = bt4[valid & (fire_mask == 0)]
        if len(bg_bt4) > 10:
            median_bt4 = np.median(bg_bt4)
            bt4s = min(330, max(325, median_bt4 + 25))
        else:
            bt4s = 330
        candidates = valid & (bt4 > bt4s) & (dbt > 25) & (fire_mask == 0)
    else:
        candidates = valid & (bt4 > 295) & (dbt > 10) & (fire_mask == 0)

    # --- Contextual tests for each candidate ---
    candidate_indices = np.argwhere(candidates)

    for y, x in candidate_indices:
        # Grow window from 11x11 to 31x31
        for win_size in [11, 15, 21, 31]:
            half = win_size // 2
            y0, y1 = max(0, y-half), min(h, y+half+1)
            x0, x1 = max(0, x-half), min(w, x+half+1)

            bg_mask = valid[y0:y1, x0:x1] & ~candidates[y0:y1, x0:x1]
            bg_mask[y-y0, x-x0] = False  # exclude candidate itself

            n_valid = bg_mask.sum()
            n_total = (y1-y0) * (x1-x0)

            if n_valid >= max(10, 0.25 * n_total):
                break

        if n_valid < 10:
            fire_mask[y, x] = 6  # unclassified
            continue

        # Background statistics
        bg_bt4_vals = bt4[y0:y1, x0:x1][bg_mask]
        bg_bt5_vals = bt5[y0:y1, x0:x1][bg_mask]
        bg_dbt_vals = dbt[y0:y1, x0:x1][bg_mask]

        bt4b = bg_bt4_vals.mean()
        bt5b = bg_bt5_vals.mean()
        dbt45b = bg_dbt_vals.mean()
        d4b = np.mean(np.abs(bg_bt4_vals - bt4b))
        d5b = np.mean(np.abs(bg_bt5_vals - bt5b))
        d45b = np.mean(np.abs(bg_dbt_vals - dbt45b))

        # Contextual tests
        if is_daytime:
            pass_test = (
                dbt[y, x] > dbt45b + 2 * d45b and
                dbt[y, x] > dbt45b + 10 and
                bt4[y, x] > bt4b + 3.5 * d4b and
                bt5[y, x] > bt5b + d5b - 4
            )
        else:
            pass_test = (
                dbt[y, x] > dbt45b + 3 * d45b and
                dbt[y, x] > dbt45b + 9 and
                bt4[y, x] > bt4b + 3 * d4b
            )

        if pass_test:
            fire_mask[y, x] = 8  # nominal confidence

    return fire_mask
```

### Vectorized approach (much faster for production)
```python
import numpy as np
from scipy.ndimage import generic_filter

def fast_contextual_detect(bt4, bt5, valid_mask, is_day, win=15):
    """Vectorized contextual detection using scipy filters.
    Much faster than per-pixel loop for large images.
    """
    dbt = bt4 - bt5

    # Compute background stats with uniform filters (ignoring invalid via NaN)
    bt4_bg = bt4.copy().astype(float)
    bt4_bg[~valid_mask] = np.nan

    # Use nanmean via convolution trick
    count = uniform_filter(valid_mask.astype(float), win)
    bt4_sum = uniform_filter(np.where(valid_mask, bt4, 0).astype(float), win)
    bt4_mean = bt4_sum / np.maximum(count, 1)

    dbt_bg = dbt.copy().astype(float)
    dbt_bg[~valid_mask] = np.nan
    dbt_sum = uniform_filter(np.where(valid_mask, dbt, 0).astype(float), win)
    dbt_mean = dbt_sum / np.maximum(count, 1)

    # MAD approximation (using std * 0.8 as rough proxy)
    bt4_sq = uniform_filter(np.where(valid_mask, bt4**2, 0).astype(float), win)
    bt4_var = bt4_sq / np.maximum(count, 1) - bt4_mean**2
    bt4_mad = np.sqrt(np.maximum(bt4_var, 0)) * 0.8

    dbt_sq = uniform_filter(np.where(valid_mask, dbt**2, 0).astype(float), win)
    dbt_var = dbt_sq / np.maximum(count, 1) - dbt_mean**2
    dbt_mad = np.sqrt(np.maximum(dbt_var, 0)) * 0.8

    # Contextual tests (vectorized)
    if is_day:
        fire = (
            (dbt > dbt_mean + 2 * dbt_mad) &
            (dbt > dbt_mean + 10) &
            (bt4 > bt4_mean + 3.5 * bt4_mad) &
            valid_mask &
            (count * win**2 >= 10)  # sufficient background
        )
    else:
        fire = (
            (dbt > dbt_mean + 3 * dbt_mad) &
            (dbt > dbt_mean + 9) &
            (bt4 > bt4_mean + 3 * bt4_mad) &
            valid_mask &
            (count * win**2 >= 10)
        )

    return fire
```

### FRP calculation
```python
def compute_frp(radiance_fire, radiance_bg, pixel_area_m2,
                stefan_boltzmann=5.67e-8, a_coeff=2.88e-9):
    """Wooster-method FRP from MIR radiance difference.

    Args:
        radiance_fire: fire pixel MIR radiance (W/m²/sr/μm)
        radiance_bg: background MIR radiance (W/m²/sr/μm)
        pixel_area_m2: pixel area in m²
        a_coeff: band-specific constant (2.88e-9 for VIIRS M13)
    Returns:
        FRP in MW
    """
    delta_l = radiance_fire - radiance_bg
    frp = pixel_area_m2 * stefan_boltzmann * (delta_l / a_coeff)
    return frp * 1e-6  # Convert to MW
```

## Reading Satellite Data with satpy

### VIIRS I-band data
```python
from satpy import Scene

# Load VIIRS SDR files
files = [
    'SVI04_npp_d20240115_t0830_e0845.h5',  # I4 SDR
    'SVI05_npp_d20240115_t0830_e0845.h5',  # I5 SDR
    'GITCO_npp_d20240115_t0830_e0845.h5',  # Geolocation
]
scn = Scene(reader='viirs_sdr', filenames=files)
scn.load(['I04', 'I05'])

bt4 = scn['I04'].values  # Brightness temperature array
bt5 = scn['I05'].values
lons = scn['I04'].attrs['area'].lons
lats = scn['I04'].attrs['area'].lats
```

### Himawari AHI data
```python
from satpy import Scene

# Load AHI HSD files
files = glob.glob('HS_H09_*_B07_*.DAT')  # Band 7 (3.9 μm)
files += glob.glob('HS_H09_*_B14_*.DAT')  # Band 14 (11.2 μm)
scn = Scene(reader='ahi_hsd', filenames=files)
scn.load(['B07', 'B14'])

bt_mir = scn['B07'].values
bt_tir = scn['B14'].values
```

### GOES ABI data
```python
from satpy import Scene
import s3fs

# Read GOES ABI L1b from AWS
fs = s3fs.S3FileSystem(anon=True)
files = fs.glob('noaa-goes18/ABI-L1b-RadF/2024/015/08/OR_ABI-L1b-RadF-M6C07_*.nc')
# Download locally or use fsspec
scn = Scene(reader='abi_l1b', filenames=files)
scn.load(['C07', 'C14'])
```

## Performance Optimization

### Numba JIT for per-pixel loop
```python
from numba import njit, prange

@njit(parallel=True)
def contextual_detect_numba(bt4, bt5, valid, is_day):
    h, w = bt4.shape
    result = np.zeros((h, w), dtype=np.int8)
    dbt = bt4 - bt5

    for i in prange(h):
        for j in range(w):
            if not valid[i, j]:
                continue
            # ... per-pixel contextual tests (same logic as above)
    return result
```

### GPU acceleration with CuPy
```python
import cupy as cp

def gpu_contextual_detect(bt4_np, bt5_np, valid_np, is_day):
    bt4 = cp.asarray(bt4_np)
    bt5 = cp.asarray(bt5_np)
    valid = cp.asarray(valid_np)
    # Same vectorized logic but on GPU
    # ...
    return cp.asnumpy(result)
```
