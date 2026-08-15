import uuid

from app.core.pipeline_config import PipelineConfig
from app.pipeline.marker_links import MarkerMoment, SegmentSpan, link_markers

MARKER = uuid.UUID("11111111-1111-4111-8111-111111111111")
FIRST = uuid.UUID("22222222-2222-4222-8222-222222222222")
SECOND = uuid.UUID("33333333-3333-4333-8333-333333333333")
MAX_FORWARD_GAP_MS = PipelineConfig().voice_tag_max_forward_gap_ms


def _segments() -> list[SegmentSpan]:
    return [
        SegmentSpan(FIRST, 0, 5_000),
        SegmentSpan(SECOND, 8_000, 12_000),
    ]


def _boundary_segments() -> list[SegmentSpan]:
    return [
        SegmentSpan(FIRST, 0, 999),
        SegmentSpan(SECOND, 6_000, 7_000),
    ]


def test_a_tap_while_speaking_marks_what_is_being_said() -> None:
    links = link_markers(
        [MarkerMoment(MARKER, 3_000)],
        _segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {MARKER: FIRST}


def test_a_tap_in_a_silence_marks_what_is_said_next() -> None:
    # Agents tap when something catches their attention and then describe it,
    # so the following segment is usually the one they meant.
    links = link_markers(
        [MarkerMoment(MARKER, 6_500)],
        _segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {MARKER: SECOND}


def test_a_tap_after_the_last_word_resolves_to_nothing() -> None:
    # Better an unresolved bookmark than one pointing at the wrong evidence.
    links = link_markers(
        [MarkerMoment(MARKER, 30_000)],
        _segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {}


def test_a_tap_on_a_segment_boundary_belongs_to_that_segment() -> None:
    assert link_markers(
        [MarkerMoment(MARKER, 5_000)],
        _segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    ) == {MARKER: FIRST}
    assert link_markers(
        [MarkerMoment(MARKER, 8_000)],
        _segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    ) == {MARKER: SECOND}


def test_segments_arriving_out_of_order_still_resolve_correctly() -> None:
    shuffled = list(reversed(_segments()))

    assert link_markers(
        [MarkerMoment(MARKER, 3_000)],
        shuffled,
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    ) == {MARKER: FIRST}


def test_several_taps_resolve_independently() -> None:
    second_marker = uuid.uuid4()

    links = link_markers(
        [MarkerMoment(MARKER, 1_000), MarkerMoment(second_marker, 9_000)],
        _segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {MARKER: FIRST, second_marker: SECOND}


def test_a_visit_with_no_transcript_yet_links_nothing() -> None:
    assert (
        link_markers(
            [MarkerMoment(MARKER, 1_000)],
            [],
            max_forward_gap_ms=MAX_FORWARD_GAP_MS,
        )
        == {}
    )
    assert link_markers([], _segments(), max_forward_gap_ms=MAX_FORWARD_GAP_MS) == {}


def test_a_tap_exactly_at_the_maximum_forward_gap_resolves() -> None:
    links = link_markers(
        [MarkerMoment(MARKER, 6_000 - MAX_FORWARD_GAP_MS)],
        _boundary_segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {MARKER: SECOND}


def test_a_tap_immediately_below_the_maximum_forward_gap_resolves() -> None:
    links = link_markers(
        [MarkerMoment(MARKER, 6_000 - MAX_FORWARD_GAP_MS + 0.001)],
        _boundary_segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {MARKER: SECOND}


def test_a_tap_immediately_above_the_maximum_forward_gap_stays_unresolved() -> None:
    links = link_markers(
        [MarkerMoment(MARKER, 6_000 - MAX_FORWARD_GAP_MS - 0.001)],
        _boundary_segments(),
        max_forward_gap_ms=MAX_FORWARD_GAP_MS,
    )

    assert links == {}
