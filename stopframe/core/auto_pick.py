"""Select sharp frames with acceptable detected faces and distinct composition.

Time buckets preserve coverage; spatial fingerprints reject near duplicates.
The requested count is an upper limit, never a reason to include bad faces or
repeat a static scene. Nearby frames are checked to recover a blink/mouth change.
"""

from __future__ import annotations

from collections.abc import Callable
import math

from stopframe.config import Settings
from stopframe.core.compositor import pick_slot_key
from stopframe.core.face_check import check_face_quality
from stopframe.core.frame_reader import FrameSource
from stopframe.core.frame_similarity import fingerprint, are_similar
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement, VideoItem
from stopframe.core.sharpness import laplacian_variance
from stopframe.core.performance import ANALYSIS_MAX_EDGE, bounded_frame
from stopframe.logging_setup import get_logger

logger = get_logger("core.auto_pick")

SAMPLE_STEP_SECONDS = 1.0
MIN_PICKS = 1
SHARPNESS_RELATIVE_FLOOR = 0.35

FACE_RETRY_OFFSETS = (-0.3, -0.15, 0.15, 0.3)


class _Candidate:
    __slots__ = ("timestamp", "sharpness", "score", "side", "fingerprint")

    def __init__(self, timestamp: float, sharpness: float) -> None:
        self.timestamp = timestamp
        self.sharpness = sharpness
        self.score = sharpness
        self.side = "left"
        self.fingerprint = None


def _bucket_index(timestamp: float, duration: float, bucket_count: int) -> int:
    if duration <= 0:
        return 0
    fraction = timestamp / duration
    return min(bucket_count - 1, int(fraction * bucket_count))


def pick_frames_for_video(
    video: VideoItem,
    settings: Settings,
    target_count: int = 4,
    is_cancelled: Callable[[], bool] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> list[FrameCandidate]:
    """`is_cancelled`, if given, is polled before every per-frame read and
    every per-frame face check — the two points that can each individually
    take a long time on a very large source file — so a Stop request takes
    effect within roughly one frame's worth of I/O instead of only between
    whole videos."""
    target_count = max(MIN_PICKS, target_count)

    source = FrameSource(video.path, native_decode=True)
    if not source.is_open():
        source.close()
        logger.error(f"Could not open video for auto pick: {video.file_name}")
        return []

    # Keep scores and small fingerprints, never full video pixels. Face checks
    # are deferred until a candidate can contribute to the final selection.
    candidates: list[_Candidate] = []
    try:
        sample_count = max(1, math.ceil(video.duration_seconds / SAMPLE_STEP_SECONDS))
        timestamp = 0.0
        while timestamp < video.duration_seconds:
            if is_cancelled is not None and is_cancelled():
                return []
            frame = source.read_at(timestamp)
            if frame is not None:
                frame = bounded_frame(frame, ANALYSIS_MAX_EDGE)
                candidate = _Candidate(timestamp, laplacian_variance(frame))
                candidate.fingerprint = fingerprint(frame)
                candidates.append(candidate)
            del frame
            timestamp += SAMPLE_STEP_SECONDS
            if on_progress is not None:
                on_progress("sharpness", min(sample_count, round(timestamp / SAMPLE_STEP_SECONDS)), sample_count)

        if not candidates:
            return []
        floor = max(c.sharpness for c in candidates) * SHARPNESS_RELATIVE_FLOOR
        ranked = sorted((c for c in candidates if c.sharpness >= floor),
                        key=lambda c: c.score, reverse=True)
        last_timestamp = max(0.0, video.duration_seconds - (1 / video.fps if video.fps > 0 else 0.001))
        checked: dict[float, _Candidate | None] = {}

        def validate(candidate: _Candidate) -> _Candidate | None:
            if candidate.timestamp in checked:
                return checked[candidate.timestamp]
            if is_cancelled is not None and is_cancelled():
                return None
            checked[candidate.timestamp] = None
            if on_progress is not None:
                on_progress("faces", len(checked), len(ranked))
            frame = source.read_at(candidate.timestamp)
            if frame is None:
                return None
            frame = bounded_frame(frame, ANALYSIS_MAX_EDGE)
            face = check_face_quality(frame)
            if not face.face_found or (face.eyes_open and face.mouth_closed):
                candidate.fingerprint = fingerprint(frame)
                del frame
                checked[candidate.timestamp] = candidate
                return candidate
            del frame

            # A one-second grid can land exactly on a blink. Search nearby,
            # but never replace a detected bad face with an undetected one.
            alternatives: list[_Candidate] = []
            for offset in FACE_RETRY_OFFSETS:
                if is_cancelled is not None and is_cancelled():
                    return None
                timestamp = candidate.timestamp + offset
                if not 0 <= timestamp <= last_timestamp:
                    continue
                frame = source.read_at(timestamp)
                if frame is None:
                    continue
                frame = bounded_frame(frame, ANALYSIS_MAX_EDGE)
                sharpness = laplacian_variance(frame)
                if sharpness >= floor:
                    face = check_face_quality(frame)
                    if face.face_found and face.eyes_open and face.mouth_closed:
                        replacement = _Candidate(timestamp, sharpness)
                        replacement.fingerprint = fingerprint(frame)
                        alternatives.append(replacement)
                del frame
            if alternatives:
                checked[candidate.timestamp] = max(alternatives, key=lambda c: c.score)
            return checked[candidate.timestamp]

        # Find the sharpest acceptable moment in each time bucket first. Do not
        # run landmark detection on every second of a long recording just to
        # discard nearly all those results later.
        # A large requested count must not allocate more buckets than there
        # are usable samples (e.g. a million picks from a ten-second clip).
        bucket_count = min(target_count, len(ranked))
        buckets: list[_Candidate | None] = [None] * bucket_count
        for candidate in ranked:
            if is_cancelled is not None and is_cancelled():
                return []
            bucket = _bucket_index(candidate.timestamp, video.duration_seconds, bucket_count)
            if buckets[bucket] is None:
                buckets[bucket] = validate(candidate)
            if all(c is not None for c in buckets):
                break

        selected: list[_Candidate] = []
        winners = sorted((c for c in buckets if c is not None), key=lambda c: c.score, reverse=True)
        for candidate in winners:
            if not any(are_similar(candidate.fingerprint, chosen.fingerprint) for chosen in selected):
                selected.append(candidate)

        # If bucket winners repeat a scene, examine remaining moments lazily.
        # A retry near a blink must still contain a detected acceptable face.
        for candidate in ranked:
            if len(selected) == target_count:
                break
            if is_cancelled is not None and is_cancelled():
                return []
            if any(are_similar(candidate.fingerprint, chosen.fingerprint) for chosen in selected):
                continue
            valid = validate(candidate)
            if valid is not None and not any(
                are_similar(valid.fingerprint, chosen.fingerprint) for chosen in selected
            ):
                selected.append(valid)
        selected.sort(key=lambda c: c.timestamp)
    finally:
        source.close()

    if is_cancelled is not None and is_cancelled():
        return []

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
