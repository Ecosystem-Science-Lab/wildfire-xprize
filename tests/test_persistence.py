"""Tests for the Himawari temporal persistence filter."""

from datetime import datetime, timedelta, timezone

import pytest

from src.himawari.persistence import TemporalFilter
from src.models import Detection, Source


def _make_detection(
    lat: float = -33.0,
    lon: float = 150.0,
    confidence: str = "nominal",
    obs_time: datetime | None = None,
) -> Detection:
    """Helper to create a Detection object for testing."""
    if obs_time is None:
        obs_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    return Detection(
        source_id=f"TEST|{lat}|{lon}|{obs_time.isoformat()}",
        source=Source.HIMAWARI,
        satellite="Himawari-9",
        instrument="AHI",
        latitude=lat,
        longitude=lon,
        acq_datetime=obs_time,
        confidence=confidence,
        brightness=350.0,
        daynight="D",
    )


T0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=10)
T2 = T0 + timedelta(minutes=20)
T3 = T0 + timedelta(minutes=30)
T4 = T0 + timedelta(minutes=40)


class TestTemporalFilterBasic:
    """Basic filter behavior."""

    def test_high_confidence_bypasses_filter(self):
        """HIGH confidence detections should pass through immediately."""
        tf = TemporalFilter(window_size=3, min_persistence=2)
        det = _make_detection(confidence="high", obs_time=T0)
        passed, stats = tf.filter_detections([det], T0)

        assert len(passed) == 1
        assert passed[0].confidence == "high"
        assert stats["bypassed_high"] == 1
        assert stats["held"] == 0

    def test_single_low_detection_is_held(self):
        """A LOW/NOMINAL detection seen once should be held, not passed."""
        tf = TemporalFilter(window_size=3, min_persistence=2)
        det = _make_detection(confidence="nominal", obs_time=T0)
        passed, stats = tf.filter_detections([det], T0)

        assert len(passed) == 0
        assert stats["held"] == 1
        assert tf.held_count == 1

    def test_empty_frame_advances_buffer(self):
        """Empty frames should still advance the buffer."""
        tf = TemporalFilter(window_size=3, min_persistence=2)
        tf.filter_detections([], T0)
        tf.filter_detections([], T1)
        tf.filter_detections([], T2)

        assert tf.buffer_depth == 3

    def test_buffer_maxlen(self):
        """Buffer should not exceed window_size."""
        tf = TemporalFilter(window_size=3, min_persistence=2)
        for i in range(5):
            tf.filter_detections([], T0 + timedelta(minutes=10 * i))

        assert tf.buffer_depth == 3


class TestTemporalFilterPersistence:
    """Tests for the persistence logic across multiple frames."""

    def test_detection_in_two_consecutive_frames_passes(self):
        """A pixel appearing in frame 1 and frame 2 should pass in frame 2."""
        tf = TemporalFilter(window_size=3, min_persistence=2)

        # Frame 1: detection appears, gets held
        det1 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T0)
        passed1, stats1 = tf.filter_detections([det1], T0)
        assert len(passed1) == 0
        assert stats1["held"] == 1

        # Frame 2: same location appears again
        det2 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T1)
        passed2, stats2 = tf.filter_detections([det2], T1)

        # The held detection from frame 1 should be promoted,
        # AND the new detection from frame 2 should pass (it now has prior history)
        assert stats2["promoted_from_held"] == 1
        # The new det2 also has 1 prior appearance (frame 1 is in buffer), so
        # with min_persistence=2, it needs 1 prior. It passes.
        assert stats2["persistent"] == 1
        assert len(passed2) == 2  # promoted + persistent

    def test_detection_disappears_after_one_frame_is_discarded(self):
        """A pixel seen once that doesn't reappear should be discarded."""
        tf = TemporalFilter(window_size=3, min_persistence=2)

        # Frame 1: detection appears, gets held
        det1 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T0)
        passed1, _ = tf.filter_detections([det1], T0)
        assert len(passed1) == 0

        # Frame 2: different location (far away), the held one should be discarded
        det2 = _make_detection(lat=-35.0, lon=152.0, confidence="nominal", obs_time=T1)
        passed2, stats2 = tf.filter_detections([det2], T1)

        assert stats2["discarded_from_held"] == 1
        assert stats2["promoted_from_held"] == 0
        # det2 is new, gets held
        assert stats2["held"] == 1
        assert len(passed2) == 0

    def test_nearby_pixel_counts_as_same_location(self):
        """Pixels within distance_threshold_km should be treated as the same."""
        tf = TemporalFilter(
            window_size=3, min_persistence=2, distance_threshold_km=4.0
        )

        # Frame 1: fire at exact location
        det1 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T0)
        tf.filter_detections([det1], T0)

        # Frame 2: fire at slightly offset location (~2km away, well within 4km)
        # 0.02 degrees lat ~ 2.2km
        det2 = _make_detection(lat=-33.02, lon=150.0, confidence="nominal", obs_time=T1)
        passed2, stats2 = tf.filter_detections([det2], T1)

        # Should match: held det1 promoted, det2 passes as persistent
        assert stats2["promoted_from_held"] == 1
        assert stats2["persistent"] == 1

    def test_distant_pixel_not_same_location(self):
        """Pixels beyond distance_threshold_km should be treated as separate."""
        tf = TemporalFilter(
            window_size=3, min_persistence=2, distance_threshold_km=4.0
        )

        # Frame 1
        det1 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T0)
        tf.filter_detections([det1], T0)

        # Frame 2: fire 50km away
        det2 = _make_detection(lat=-33.5, lon=150.0, confidence="nominal", obs_time=T1)
        passed2, stats2 = tf.filter_detections([det2], T1)

        # det1 held but det2 is far away, so det1 gets discarded
        assert stats2["discarded_from_held"] == 1
        assert stats2["promoted_from_held"] == 0
        # det2 is new, gets held
        assert stats2["held"] == 1


class TestTemporalFilterThreeFrameScenario:
    """Tests simulating the full 3-frame window scenario."""

    def test_fire_in_frames_1_and_3_passes(self):
        """Fire in frame 1 and 3 (skip frame 2) should pass in frame 3.

        Frame 1: pixel appears, held
        Frame 2: pixel absent, held is discarded (but frame 1 stays in buffer)
        Frame 3: pixel reappears. Buffer has frame 1 with matching pixel,
                 so prior_count=1, meets min_persistence-1=1, passes.
        """
        tf = TemporalFilter(window_size=3, min_persistence=2)

        # Frame 1
        det1 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T0)
        passed1, _ = tf.filter_detections([det1], T0)
        assert len(passed1) == 0

        # Frame 2: no detection at that location
        passed2, stats2 = tf.filter_detections([], T1)
        assert stats2["discarded_from_held"] == 1

        # Frame 3: pixel reappears. Frame 1 is still in buffer.
        det3 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T2)
        passed3, stats3 = tf.filter_detections([det3], T2)

        # Should pass because buffer has frame 1 with matching pixel
        assert stats3["persistent"] == 1
        assert len(passed3) == 1

    def test_mixed_confidences_in_single_frame(self):
        """Frame with both HIGH and LOW detections: HIGH bypasses, LOW filtered."""
        tf = TemporalFilter(window_size=3, min_persistence=2)

        dets = [
            _make_detection(lat=-33.0, lon=150.0, confidence="high", obs_time=T0),
            _make_detection(lat=-34.0, lon=151.0, confidence="low", obs_time=T0),
            _make_detection(lat=-35.0, lon=152.0, confidence="nominal", obs_time=T0),
        ]
        passed, stats = tf.filter_detections(dets, T0)

        assert len(passed) == 1  # Only HIGH
        assert stats["bypassed_high"] == 1
        assert stats["held"] == 2

    def test_buffer_slides_window_correctly(self):
        """After window_size+1 frames, the oldest frame should be evicted.

        With window_size=3 and deque maxlen=3, the buffer holds the last 3
        frames that have been *appended*. When processing a new frame, we
        check the buffer (which contains the previous 3 frames), then
        append the current frame (which evicts the oldest).

        So to fully evict frame 0, we need 4 frames in the buffer after it:
        frames 1, 2, 3 fill the buffer, then frame 4 triggers the eviction
        of frame 1 (frame 0 was already pushed out when frame 3 was appended).
        """
        tf = TemporalFilter(window_size=3, min_persistence=2)

        # Frame 0: fire at location A
        det_a = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=T0)
        tf.filter_detections([det_a], T0)
        # buffer = [T0]

        # Frame 1: empty — held from frame 0 is discarded
        tf.filter_detections([], T1)
        # buffer = [T0, T1]

        # Frame 2: empty
        tf.filter_detections([], T2)
        # buffer = [T0, T1, T2]

        # Frame 3: empty — this appends T3, evicting T0 from buffer
        tf.filter_detections([], T3)
        # buffer = [T1, T2, T3]

        # Frame 4: fire at location A reappears. Buffer is [T1, T2, T3] — no match.
        t4 = T0 + timedelta(minutes=40)
        det_a2 = _make_detection(lat=-33.0, lon=150.0, confidence="nominal", obs_time=t4)
        passed, stats = tf.filter_detections([det_a2], t4)

        # No prior history in buffer (T0 was evicted)
        assert stats["persistent"] == 0
        assert stats["held"] == 1
        assert len(passed) == 0


class TestTemporalFilterConfig:
    """Tests for configuration validation and edge cases."""

    def test_min_persistence_exceeds_window_raises(self):
        """min_persistence > window_size should raise ValueError."""
        with pytest.raises(ValueError, match="cannot exceed"):
            TemporalFilter(window_size=2, min_persistence=3)

    def test_bypass_disabled(self):
        """When bypass_high_confidence=False, HIGH detections are also filtered."""
        tf = TemporalFilter(
            window_size=3, min_persistence=2, bypass_high_confidence=False
        )
        det = _make_detection(confidence="high", obs_time=T0)
        passed, stats = tf.filter_detections([det], T0)

        assert len(passed) == 0
        assert stats["bypassed_high"] == 0
        assert stats["held"] == 1

    def test_min_persistence_one_passes_everything(self):
        """With min_persistence=1, everything passes on first appearance."""
        tf = TemporalFilter(window_size=3, min_persistence=1)
        det = _make_detection(confidence="nominal", obs_time=T0)
        passed, stats = tf.filter_detections([det], T0)

        # prior_count=0, min_persistence-1=0, so 0>=0 is True
        assert len(passed) == 1
        assert stats["persistent"] == 1

    def test_reset_clears_state(self):
        """reset() should clear buffer and held detections."""
        tf = TemporalFilter(window_size=3, min_persistence=2)
        det = _make_detection(confidence="nominal", obs_time=T0)
        tf.filter_detections([det], T0)
        assert tf.buffer_depth == 1
        assert tf.held_count == 1

        tf.reset()
        assert tf.buffer_depth == 0
        assert tf.held_count == 0
