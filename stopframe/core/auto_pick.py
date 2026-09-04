"""Automatic frame selection for one video: sample -> sharpness filter ->
(optional) face-quality scoring -> one best frame per time bucket.

Diversity is driven by splitting the video's duration into `target_count`
equal time buckets and taking the single best-scoring frame from each,
rather than comparing color histograms — drone footage keeps a fairly
constant sky/ground color palette even as the framing/zoom changes a lot,
so a histogram-distance check kept picking near-duplicate shots. Spreading
picks across the whole timeline directly captures the framing changes
that actually happen as a clip progresses.

The logo always defaults to the left slot — no auto side-detection.
Reassign individual picks to the right via the Screenshots tab if needed.
"""

from __future__ import annotations

import numpy as np

from stopframe.config import Settings
from stopframe.core.compositor import pick_slot_key
from stopframe.core.face_check import check_face_quality
from stopframe.core.frame_reader import FrameSource
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement, VideoItem
from stopframe.core.sharpness import laplacian_variance
from stopframe.logging_setup import get_logger

logger = get_logger("core.auto_pick")

SAMPLE_STEP_SECONDS = 1.0
MIN_PICKS = 3
MAX_PICKS = 5
SHARPNESS_RELATIVE_FLOOR = 0.35

EYES_CLOSED_PENALTY = 0.3
MOUTH_OPEN_PENALTY = 0.7


class _Candidate:
    __slots__ = ("timestamp", "sharpness", "score", "side")

    def __init__(self, timestamp: float, sharpness: float) -> None:
        self.timestamp = timestamp
        self.sharpness = sharpness
        self.score = sharpness
        self.side = "left"


def _bucket_index(timestamp: float, duration: float, bucket_count: int) -> int:
    if duration <= 0:
        return 0
    fraction = timestamp / duration
    return min(bucket_count - 1, int(fraction * bucket_count))


def pick_frames_for_video(video: VideoItem, settings: Settings, target_count: int = 4) -> list[FrameCandidate]:
    target_count = max(MIN_PICKS, min(MAX_PICKS, target_count))

    source = FrameSource(video.path)
    if not source.is_open():
        source.close()
        logger.error(f"Could not open video for auto pick: {video.file_name}")
        return []

    sampled: list[tuple[float, np.ndarray]] = []
    timestamp = 0.0
    while timestamp < video.duration_seconds:
        frame = source.read_at(timestamp)
        if frame is not None:
            sampled.append((timestamp, frame))
        timestamp += SAMPLE_STEP_SECONDS
    source.close()

    if not sampled:
        return []

    candidates = [_Candidate(ts, laplacian_variance(frame)) for ts, frame in sampled]
    max_sharpness = max(c.sharpness for c in candidates)
    floor = max_sharpness * SHARPNESS_RELATIVE_FLOOR
    keep_indices = [i for i, c in enumerate(candidates) if c.sharpness >= floor] or list(range(len(candidates)))

    for i in keep_indices:
        timestamp, frame = sampled[i]
        candidate = candidates[i]
        face = check_face_quality(frame)
        multiplier = 1.0
        if face.face_found:
            if not face.eyes_open:
                multiplier *= EYES_CLOSED_PENALTY
            if not face.mouth_closed:
                multiplier *= MOUTH_OPEN_PENALTY
        candidate.score = candidate.sharpness * multiplier

    buckets: list[_Candidate | None] = [None] * target_count
    for i in keep_indices:
        candidate = candidates[i]
        bucket = _bucket_index(candidate.timestamp, video.duration_seconds, target_count)
        current = buckets[bucket]
        if current is None or candidate.score > current.score:
            buckets[bucket] = candidate

    selected = [c for c in buckets if c is not None]
    selected.sort(key=lambda c: c.timestamp)

    results = []
    for candidate in selected:
        slot_key = pick_slot_key(video.aspect_ratio, video.orientation, candidate.side)
        slot = settings.logo_slots[slot_key]
        placement = LogoPlacement(slot_key=slot_key, offset_x=slot.offset_x, offset_y=slot.offset_y, scale=slot.scale)
        frame_index = round(candidate.timestamp * video.fps) if video.fps else 0
        results.append(
            FrameCandidate(
                video_path=video.path,
                frame_index=frame_index,
                timestamp_seconds=candidate.timestamp,
                origin=FrameOrigin.AUTO,
                logo_placement=placement,
                sharpness_score=candidate.sharpness,
            )
        )

    logger.info(f"Auto-picked {len(results)} frame(s) for {video.file_name}")
    return results
