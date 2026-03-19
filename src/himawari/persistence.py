"""Temporal persistence filter for Himawari fire detections.

The single highest-impact improvement for reducing false positives: a fire
that appears in 2 of 3 consecutive frames is far more likely real than one
appearing only once.

Design:
- Maintains a rolling buffer of fire pixel locations from the last N observations.
- A pixel location is "the same" if within a configurable distance threshold
  (~4km, i.e. 1-2 AHI pixels at 2km resolution).
- Fire pixels seen in >=2 of the last N frames pass through immediately.
- Fire pixels seen only once are held — they get one more frame to reappear.
  If they don't reappear, they're discarded.
- HIGH confidence fires (absolute threshold detections) bypass the persistence
  check and are reported immediately — these have extremely low false positive
  rates already.
- The buffer is lightweight: just coordinates + obs_time + confidence level,
  no full arrays.

Integration point: between detection (Step 6 in pipeline.py, which produces
Detection objects) and ingest (Step 7).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Optional

from ..models import Detection

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FirePixelRecord:
    """Lightweight record of a single fire pixel detection."""

    latitude: float
    longitude: float
    confidence: str  # "low", "nominal", "high"
    obs_time: datetime


@dataclass
class ObservationFrame:
    """All fire pixel records from a single observation."""

    obs_time: datetime
    pixels: list[FirePixelRecord] = field(default_factory=list)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km.

    Inlined here to avoid import dependency on dedup for a hot-path function.
    """
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    a = min(max(a, 0.0), 1.0)
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


class TemporalFilter:
    """Rolling temporal persistence filter for fire detections.

    Maintains a buffer of fire pixel locations from recent observations and
    uses persistence across frames to filter out transient false positives.

    Args:
        window_size: Number of recent frames to keep in the buffer.
        min_persistence: Minimum number of frames a pixel must appear in
            (within the window) to pass the filter without being held.
        distance_threshold_km: Maximum distance to consider two pixels
            as "the same location" across frames.
        bypass_high_confidence: If True, HIGH confidence detections pass
            through without persistence checking.
    """

    def __init__(
        self,
        window_size: int = 3,
        min_persistence: int = 2,
        distance_threshold_km: float = 4.0,
        bypass_high_confidence: bool = True,
    ):
        if min_persistence > window_size:
            raise ValueError(
                f"min_persistence ({min_persistence}) cannot exceed "
                f"window_size ({window_size})"
            )

        self.window_size = window_size
        self.min_persistence = min_persistence
        self.distance_threshold_km = distance_threshold_km
        self.bypass_high_confidence = bypass_high_confidence

        # Rolling buffer of recent observation frames (oldest first)
        self._buffer: deque[ObservationFrame] = deque(maxlen=window_size)

        # Held detections: pixels seen once that need one more frame to confirm.
        # Maps (approximate) location key to the Detection object and its record.
        # These are from the *previous* frame only — we hold for exactly one
        # additional frame opportunity.
        self._held: list[tuple[FirePixelRecord, Detection]] = []

    def _count_matches_in_buffer(self, lat: float, lon: float) -> int:
        """Count how many frames in the buffer have a pixel near (lat, lon)."""
        count = 0
        for frame in self._buffer:
            for pixel in frame.pixels:
                if _haversine_km(lat, lon, pixel.latitude, pixel.longitude) <= self.distance_threshold_km:
                    count += 1
                    break  # One match per frame is enough
        return count

    def _has_match_in_frame(
        self, lat: float, lon: float, frame: ObservationFrame
    ) -> bool:
        """Check if any pixel in the given frame is near (lat, lon)."""
        for pixel in frame.pixels:
            if _haversine_km(lat, lon, pixel.latitude, pixel.longitude) <= self.distance_threshold_km:
                return True
        return False

    def filter_detections(
        self,
        detections: list[Detection],
        obs_time: datetime,
    ) -> tuple[list[Detection], dict]:
        """Apply temporal persistence filter to a batch of detections.

        This is the main entry point. Call once per observation frame.

        Args:
            detections: Detection objects from the current frame (output of
                fire_pixels_to_detections).
            obs_time: Observation timestamp for this frame.

        Returns:
            Tuple of:
              - List of Detection objects that passed the filter (to be ingested).
              - Stats dict with filter metrics.
        """
        t_start = time.monotonic()

        # Build the current frame's pixel records
        current_frame = ObservationFrame(obs_time=obs_time)
        for det in detections:
            current_frame.pixels.append(
                FirePixelRecord(
                    latitude=det.latitude,
                    longitude=det.longitude,
                    confidence=det.confidence,
                    obs_time=obs_time,
                )
            )

        passed: list[Detection] = []
        new_held: list[tuple[FirePixelRecord, Detection]] = []
        n_bypassed = 0
        n_persistent = 0
        n_held = 0
        n_promoted_from_held = 0
        n_discarded_from_held = 0

        # --- Phase 1: Check held detections from previous frame ---
        # If a held pixel reappears in the current frame, promote it.
        # Otherwise, discard it.
        for held_record, held_det in self._held:
            if self._has_match_in_frame(
                held_record.latitude, held_record.longitude, current_frame
            ):
                # Reappeared — promote the held detection
                passed.append(held_det)
                n_promoted_from_held += 1
            else:
                # Did not reappear — discard
                n_discarded_from_held += 1

        # Clear held list; we'll rebuild it from current frame
        self._held = []

        # --- Phase 2: Process current frame detections ---
        for det in detections:
            # HIGH confidence bypass
            if self.bypass_high_confidence and det.confidence == "high":
                passed.append(det)
                n_bypassed += 1
                continue

            # Count appearances in the historical buffer (not including current frame)
            prior_count = self._count_matches_in_buffer(det.latitude, det.longitude)

            if prior_count >= (self.min_persistence - 1):
                # This pixel has appeared enough times before. Including this
                # frame, it meets the persistence threshold.
                passed.append(det)
                n_persistent += 1
            else:
                # First-time pixel (or insufficient history). Hold it.
                record = FirePixelRecord(
                    latitude=det.latitude,
                    longitude=det.longitude,
                    confidence=det.confidence,
                    obs_time=obs_time,
                )
                new_held.append((record, det))
                n_held += 1

        self._held = new_held

        # --- Phase 3: Update the rolling buffer ---
        self._buffer.append(current_frame)

        elapsed_ms = round((time.monotonic() - t_start) * 1000, 1)

        stats = {
            "input": len(detections),
            "passed": len(passed),
            "bypassed_high": n_bypassed,
            "persistent": n_persistent,
            "held": n_held,
            "promoted_from_held": n_promoted_from_held,
            "discarded_from_held": n_discarded_from_held,
            "buffer_depth": len(self._buffer),
            "total_held": len(self._held),
            "elapsed_ms": elapsed_ms,
        }

        logger.info(
            "Temporal filter: %d in → %d passed (%d bypass, %d persistent, "
            "%d promoted) | %d held, %d discarded | buffer=%d frames (%.1fms)",
            stats["input"],
            stats["passed"],
            n_bypassed,
            n_persistent,
            n_promoted_from_held,
            n_held,
            n_discarded_from_held,
            len(self._buffer),
            elapsed_ms,
        )

        return passed, stats

    @property
    def buffer_depth(self) -> int:
        """Number of observation frames currently in the buffer."""
        return len(self._buffer)

    @property
    def held_count(self) -> int:
        """Number of detections currently held pending confirmation."""
        return len(self._held)

    def reset(self) -> None:
        """Clear the buffer and held detections. Useful for testing."""
        self._buffer.clear()
        self._held = []
