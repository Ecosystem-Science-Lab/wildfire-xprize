"""Confidence ladder logic for fire events."""

from datetime import timedelta

from .models import DetectionRow, EventStatus


def evaluate_confidence(detections: list[DetectionRow], source_set: str) -> EventStatus:
    """Evaluate the confidence level of an event based on its detections.

    Rules (simplified for fallback system):
    - PROVISIONAL: Single source only
    - LIKELY: Both DEA + FIRMS detect it, OR 2+ passes >30 min apart
    - CONFIRMED: 3+ passes >30 min apart from different times
    """
    if not detections:
        return EventStatus.PROVISIONAL

    # Check for multiple sources
    sources = set(s.strip() for s in source_set.split(",") if s.strip())
    multi_source = len(sources) >= 2

    # Count temporally distinct passes (>30 min apart)
    sorted_dets = sorted(detections, key=lambda d: d.acq_datetime)
    passes = [sorted_dets[0].acq_datetime]
    for det in sorted_dets[1:]:
        last_pass = passes[-1]
        # Handle both datetime objects and strings
        det_time = det.acq_datetime
        if isinstance(last_pass, str):
            from datetime import datetime
            last_pass = datetime.fromisoformat(last_pass)
        if isinstance(det_time, str):
            from datetime import datetime
            det_time = datetime.fromisoformat(det_time)
        if det_time - last_pass > timedelta(minutes=30):
            passes.append(det_time)

    num_passes = len(passes)

    if num_passes >= 3:
        return EventStatus.CONFIRMED
    if multi_source or num_passes >= 2:
        return EventStatus.LIKELY
    return EventStatus.PROVISIONAL
