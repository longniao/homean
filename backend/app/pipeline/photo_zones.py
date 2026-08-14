"""Place captured photos in the room the agent named just before shooting.

Deriving a photo's room from zone boundaries alone is unreliable: zone
detection segments *speech*, and agents narrate out of order, shoot before
entering or after leaving, and revisit rooms. A misfiled photo is worse than
no photo, because it discredits the whole report.

So placement uses an explicit signal instead of an inference. The agent says
the room name, then takes the picture, and a photo is placed only when a
configured phrase for that room appears in the transcript near the shutter.
Photos without a spoken cue stay unplaced rather than being guessed at.
"""

import re
import uuid
from dataclasses import dataclass

# Say-then-shoot is the taught habit, so most of the window sits before the
# photo; the tail catches agents who shoot first and name the room after.
LOOKBEHIND_MS = 10_000
LOOKAHEAD_MS = 5_000

ZONE_SOURCE_VOICE = "voice_anchor"


@dataclass(frozen=True)
class SpokenSegment:
    text: str
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class ZoneWindow:
    zone_id: uuid.UUID
    zone_type: str
    start_ms: float
    end_ms: float


@dataclass(frozen=True)
class PhotoMoment:
    media_id: uuid.UUID
    offset_ms: float


def build_alias_index(
    zone_taxonomy: list[str],
    zone_labels: dict[str, str],
    zone_speech_aliases: dict[str, list[str]],
) -> list[tuple[str, str]]:
    """Return (phrase, zone_type) pairs, longest phrase first.

    Longest-first is what stops "primary bedroom" from matching the shorter
    "bedroom" alias and filing the photo in the wrong room.
    """

    phrases: dict[str, str] = {}
    for zone_type in zone_taxonomy:
        candidates = [
            zone_type.replace("_", " "),
            zone_labels.get(zone_type, ""),
            *zone_speech_aliases.get(zone_type, []),
        ]
        for candidate in candidates:
            normalized = _normalize(candidate)
            if not normalized:
                continue
            # A phrase shared by two rooms cannot identify either of them.
            if normalized in phrases and phrases[normalized] != zone_type:
                phrases[normalized] = ""
                continue
            phrases.setdefault(normalized, zone_type)
    return sorted(
        ((phrase, zone) for phrase, zone in phrases.items() if zone),
        key=lambda pair: (-len(pair[0]), pair[0]),
    )


def place_photos(
    photos: list[PhotoMoment],
    segments: list[SpokenSegment],
    zones: list[ZoneWindow],
    alias_index: list[tuple[str, str]],
) -> dict[uuid.UUID, uuid.UUID]:
    """Map media ids to zone ids for photos with an unambiguous spoken cue."""

    if not photos or not segments or not zones:
        return {}
    placements: dict[uuid.UUID, uuid.UUID] = {}
    for photo in photos:
        zone_type = _spoken_zone_type(photo.offset_ms, segments, alias_index)
        if zone_type is None:
            continue
        zone = _nearest_zone(photo.offset_ms, zone_type, zones)
        if zone is not None:
            placements[photo.media_id] = zone.zone_id
    return placements


def _spoken_zone_type(
    offset_ms: float,
    segments: list[SpokenSegment],
    alias_index: list[tuple[str, str]],
) -> str | None:
    window_start = offset_ms - LOOKBEHIND_MS
    window_end = offset_ms + LOOKAHEAD_MS
    best: tuple[float, str] | None = None
    for segment in segments:
        if segment.end_ms < window_start or segment.start_ms > window_end:
            continue
        text = _normalize(segment.text)
        if not text:
            continue
        for phrase, zone_type in alias_index:
            if not _contains_phrase(text, phrase):
                continue
            # Prefer the cue spoken closest to the shutter.
            distance = abs(segment.start_ms - offset_ms)
            if best is None or distance < best[0]:
                best = (distance, zone_type)
            break
    return best[1] if best else None


def _nearest_zone(
    offset_ms: float, zone_type: str, zones: list[ZoneWindow]
) -> ZoneWindow | None:
    candidates = [zone for zone in zones if zone.zone_type == zone_type]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Several rooms share a type (three bedrooms), so the spoken name alone
    # cannot say which. Fall back to the one the photo's moment sits in or
    # closest to.
    return min(candidates, key=lambda zone: _distance_to(offset_ms, zone))


def _distance_to(offset_ms: float, zone: ZoneWindow) -> float:
    if zone.start_ms <= offset_ms <= zone.end_ms:
        return 0.0
    if offset_ms < zone.start_ms:
        return zone.start_ms - offset_ms
    return offset_ms - zone.end_ms


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _contains_phrase(haystack: str, phrase: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None
