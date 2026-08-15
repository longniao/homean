"""Attach each voice tag to the transcript it marks.

An agent taps a voice tag to say "this bit matters". The tap lands at an
instant, but evidence lives in transcript segments, so the tag has to resolve
to one: the segment being spoken at that moment, or — when the tap falls in a
silence — the next thing said, because the agent is usually marking something
they are about to describe.

A tag that resolves to nothing stays unresolved rather than guessing at the
nearest speech in either direction. It is a bookmark into evidence, and a
bookmark pointing at the wrong page is worse than one that admits it is loose.
"""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class MarkerMoment:
    marker_id: uuid.UUID
    offset_ms: float


@dataclass(frozen=True)
class SegmentSpan:
    segment_id: uuid.UUID
    start_ms: float
    end_ms: float


def link_markers(
    markers: list[MarkerMoment], segments: list[SegmentSpan]
) -> dict[uuid.UUID, uuid.UUID]:
    """Map marker ids to the segment each one bookmarks."""

    if not markers or not segments:
        return {}
    ordered = sorted(segments, key=lambda span: (span.start_ms, span.end_ms))
    links: dict[uuid.UUID, uuid.UUID] = {}
    for marker in markers:
        span = _containing(marker.offset_ms, ordered) or _following(
            marker.offset_ms, ordered
        )
        if span is not None:
            links[marker.marker_id] = span.segment_id
    return links


def _containing(offset_ms: float, ordered: list[SegmentSpan]) -> SegmentSpan | None:
    for span in ordered:
        if span.start_ms <= offset_ms <= span.end_ms:
            return span
        if span.start_ms > offset_ms:
            break
    return None


def _following(offset_ms: float, ordered: list[SegmentSpan]) -> SegmentSpan | None:
    for span in ordered:
        if span.start_ms > offset_ms:
            return span
    # Tapped after the last word, so there is nothing it can point at.
    return None
