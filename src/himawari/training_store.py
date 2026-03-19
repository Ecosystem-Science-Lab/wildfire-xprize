"""Lightweight training data store for CUSUM calibration.

Records per-pixel observation data so that the Bayesian probability scaling
factor (cusum_to_logodds_scale) and other parameters can be calibrated against
known fire / non-fire labels.

Output format: one Parquet file per UTC day in the configured directory.

Only stores "interesting" pixels to keep file sizes manageable:
- Any pixel with P(fire) > 0.01
- Plus a random 1% sample of background pixels for negative examples

Gated by CUSUMConfig.training_store_enabled — no I/O overhead when disabled.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Lazy import: pyarrow/pandas only loaded if training store is actually used
_pa = None
_pq = None


def _ensure_pyarrow():
    """Lazy-load pyarrow to avoid import cost when training store is disabled."""
    global _pa, _pq
    if _pa is None:
        import pyarrow as pa
        import pyarrow.parquet as pq
        _pa = pa
        _pq = pq


# Column names and types for the output schema
_SCHEMA_FIELDS = [
    ("obs_time", "timestamp[us, tz=UTC]"),
    ("lat", "float32"),
    ("lon", "float32"),
    ("bt7", "float32"),
    ("bt14", "float32"),
    ("btd", "float32"),
    ("btd_predicted", "float32"),
    ("z_score", "float32"),
    ("fire_probability", "float32"),
    ("cusum_slow", "float32"),
    ("cusum_fast", "float32"),
    ("bt14_anomaly", "float32"),
    ("kalman_weight", "float32"),
    ("cloud_flag", "bool"),
    ("is_day", "bool"),
    ("pixel_type", "string"),
]


class TrainingStore:
    """Stores per-pixel observation data for CUSUM calibration.

    Writes to data/training/ as parquet files (one per day).
    Only stores pixels that meet certain criteria:
    - P(fire) > 0.01 (interesting pixels)
    - OR randomly sampled background pixels (configurable sample rate)
    """

    def __init__(
        self,
        output_dir: str = "data/training",
        background_sample_rate: float = 0.01,
        fire_prob_threshold: float = 0.01,
    ):
        """
        Args:
            output_dir: Directory to write parquet files into.
            background_sample_rate: Fraction of background (non-interesting)
                pixels to randomly sample per frame.
            fire_prob_threshold: P(fire) above which a pixel is considered
                "interesting" and always stored.
        """
        self.output_dir = Path(output_dir)
        self.background_sample_rate = background_sample_rate
        self.fire_prob_threshold = fire_prob_threshold
        # Buffer rows in memory, flush once per day boundary or on explicit flush
        self._buffer: list[dict] = []
        self._current_day: Optional[str] = None
        self._rng = np.random.default_rng(seed=42)

    def record_frame(
        self,
        obs_time: datetime,
        lats: np.ndarray,
        lons: np.ndarray,
        bt7: np.ndarray,
        bt14: np.ndarray,
        btd: np.ndarray,
        btd_predicted: np.ndarray,
        z_scores: np.ndarray,
        fire_prob: np.ndarray,
        cusum_slow: np.ndarray,
        cusum_fast: np.ndarray,
        bt14_anomaly: np.ndarray,
        kalman_weight: np.ndarray,
        cloud_mask: np.ndarray,
        is_day: np.ndarray,
    ) -> int:
        """Record one observation frame's data for training.

        All arrays should be 1-D (flattened grid), same length.

        Args:
            obs_time: Observation time (UTC).
            lats, lons: Pixel coordinates.
            bt7, bt14, btd: Raw brightness temperatures.
            btd_predicted: Kalman-predicted BTD (for residual context).
            z_scores: Normalized residuals from Kalman filter.
            fire_prob: Bayesian posterior fire probability.
            cusum_slow, cusum_fast: CUSUM statistics.
            bt14_anomaly: BT14 deviation from EMA.
            kalman_weight: Bayesian Kalman weight applied.
            cloud_mask: True = cloudy (excluded from CUSUM).
            is_day: True = daytime pixel.

        Returns:
            Number of pixels stored in this call.
        """
        if obs_time.tzinfo is None:
            obs_time = obs_time.replace(tzinfo=timezone.utc)

        day_str = obs_time.strftime("%Y-%m-%d")

        # Flush buffer if we've crossed a day boundary
        if self._current_day is not None and self._current_day != day_str:
            self.flush()
        self._current_day = day_str

        n = lats.shape[0]
        fire_prob_safe = np.where(np.isfinite(fire_prob), fire_prob, 0.0)

        # Select interesting pixels: P(fire) above threshold
        interesting = fire_prob_safe > self.fire_prob_threshold
        # Select random background sample from non-interesting, non-cloudy pixels
        background_pool = (~interesting) & (~cloud_mask) & np.isfinite(z_scores)
        n_background_pool = int(np.sum(background_pool))
        n_background_sample = max(1, int(n_background_pool * self.background_sample_rate))

        if n_background_pool > 0:
            bg_indices = np.where(background_pool)[0]
            if n_background_sample < len(bg_indices):
                bg_indices = self._rng.choice(
                    bg_indices, size=n_background_sample, replace=False
                )
            background_selected = np.zeros(n, dtype=bool)
            background_selected[bg_indices] = True
        else:
            background_selected = np.zeros(n, dtype=bool)

        # Combined selection mask
        selected = interesting | background_selected
        indices = np.where(selected)[0]

        if len(indices) == 0:
            return 0

        # Determine pixel type labels
        pixel_types = np.where(interesting[indices], "fire_candidate", "background_sample")

        # Build rows
        ts = obs_time
        for i, idx in enumerate(indices):
            self._buffer.append({
                "obs_time": ts,
                "lat": float(lats[idx]),
                "lon": float(lons[idx]),
                "bt7": float(bt7[idx]),
                "bt14": float(bt14[idx]),
                "btd": float(btd[idx]),
                "btd_predicted": float(btd_predicted[idx]),
                "z_score": float(z_scores[idx]) if np.isfinite(z_scores[idx]) else None,
                "fire_probability": float(fire_prob[idx]) if np.isfinite(fire_prob[idx]) else None,
                "cusum_slow": float(cusum_slow[idx]),
                "cusum_fast": float(cusum_fast[idx]),
                "bt14_anomaly": float(bt14_anomaly[idx]),
                "kalman_weight": float(kalman_weight[idx]),
                "cloud_flag": bool(cloud_mask[idx]),
                "is_day": bool(is_day[idx]),
                "pixel_type": pixel_types[i],
            })

        n_stored = len(indices)
        n_fire = int(np.sum(interesting[indices]))
        n_bg = n_stored - n_fire
        logger.debug(
            "TrainingStore: recorded %d pixels (%d fire_candidate, %d background) "
            "for %s",
            n_stored, n_fire, n_bg, obs_time.isoformat(),
        )
        return n_stored

    def flush(self) -> Optional[Path]:
        """Write buffered rows to a parquet file and clear the buffer.

        Returns:
            Path to the written file, or None if buffer was empty.
        """
        if not self._buffer:
            return None

        _ensure_pyarrow()

        day_str = self._current_day or "unknown"
        out_path = self.output_dir / f"{day_str}.parquet"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Convert buffer to columnar format
        columns = {field[0]: [] for field in _SCHEMA_FIELDS}
        for row in self._buffer:
            for col_name, _ in _SCHEMA_FIELDS:
                columns[col_name].append(row[col_name])

        # Build pyarrow table
        pa_arrays = []
        pa_fields = []
        for col_name, col_type in _SCHEMA_FIELDS:
            values = columns[col_name]
            if col_type == "timestamp[us, tz=UTC]":
                arr = _pa.array(values, type=_pa.timestamp("us", tz="UTC"))
            elif col_type == "float32":
                arr = _pa.array(values, type=_pa.float32())
            elif col_type == "bool":
                arr = _pa.array(values, type=_pa.bool_())
            elif col_type == "string":
                arr = _pa.array(values, type=_pa.string())
            else:
                arr = _pa.array(values)
            pa_arrays.append(arr)
            pa_fields.append(_pa.field(col_name, arr.type))

        schema = _pa.schema(pa_fields)
        table = _pa.table(pa_arrays, schema=schema)

        # Append to existing file if it exists (read + concat), else write new
        if out_path.exists():
            try:
                existing = _pq.read_table(str(out_path))
                table = _pa.concat_tables([existing, table])
            except Exception:
                logger.warning(
                    "Failed to read existing training file %s — overwriting",
                    out_path, exc_info=True,
                )

        _pq.write_table(table, str(out_path), compression="snappy")

        n_rows = len(self._buffer)
        self._buffer.clear()

        logger.info(
            "TrainingStore: flushed %d rows to %s (total %d rows in file)",
            n_rows, out_path, table.num_rows,
        )
        return out_path

    def __del__(self):
        """Flush remaining buffer on cleanup."""
        try:
            if self._buffer:
                self.flush()
        except Exception:
            pass
