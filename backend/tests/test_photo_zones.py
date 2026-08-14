import uuid

from app.pipeline.photo_zones import (
    PhotoMoment,
    SpokenSegment,
    ZoneWindow,
    build_alias_index,
    place_photos,
)
from app.verticals import VerticalConfigService

KITCHEN = uuid.UUID("11111111-1111-4111-8111-111111111111")
BEDROOM_ONE = uuid.UUID("22222222-2222-4222-8222-222222222222")
BEDROOM_TWO = uuid.UUID("33333333-3333-4333-8333-333333333333")
PHOTO = uuid.UUID("44444444-4444-4444-8444-444444444444")


def _index() -> list[tuple[str, str]]:
    pack = VerticalConfigService().get()
    return build_alias_index(
        pack.zone_taxonomy, pack.display_labels.zones, pack.zone_speech_aliases
    )


def _zones() -> list[ZoneWindow]:
    return [
        ZoneWindow(KITCHEN, "kitchen", 0, 60_000),
        ZoneWindow(BEDROOM_ONE, "bedroom", 60_000, 120_000),
        ZoneWindow(BEDROOM_TWO, "bedroom", 120_000, 180_000),
    ]


def test_places_a_photo_in_the_room_named_just_before_the_shutter() -> None:
    segments = [SpokenSegment("Okay, this is the kitchen.", 8_000, 10_000)]
    photos = [PhotoMoment(PHOTO, 12_000)]

    assert place_photos(photos, segments, _zones(), _index()) == {PHOTO: KITCHEN}


def test_places_a_photo_when_the_room_is_named_just_after() -> None:
    segments = [SpokenSegment("That was the kitchen.", 14_000, 16_000)]
    photos = [PhotoMoment(PHOTO, 12_000)]

    assert place_photos(photos, segments, _zones(), _index()) == {PHOTO: KITCHEN}


def test_leaves_a_photo_unplaced_when_no_room_was_named_nearby() -> None:
    # Spoken far outside the window: a guess here would be worse than nothing.
    segments = [SpokenSegment("This is the kitchen.", 100, 2_000)]
    photos = [PhotoMoment(PHOTO, 90_000)]

    assert place_photos(photos, segments, _zones(), _index()) == {}


def test_leaves_a_photo_unplaced_when_nothing_was_said() -> None:
    segments = [SpokenSegment("Plenty of storage in here.", 8_000, 10_000)]
    photos = [PhotoMoment(PHOTO, 12_000)]

    assert place_photos(photos, segments, _zones(), _index()) == {}


def test_longer_room_names_win_over_the_shorter_ones_they_contain() -> None:
    zones = [
        ZoneWindow(KITCHEN, "primary_bedroom", 0, 60_000),
        ZoneWindow(BEDROOM_ONE, "bedroom", 60_000, 120_000),
    ]
    segments = [SpokenSegment("Here is the primary bedroom.", 8_000, 10_000)]

    placements = place_photos([PhotoMoment(PHOTO, 12_000)], segments, zones, _index())

    assert placements == {PHOTO: KITCHEN}


def test_repeated_room_types_resolve_to_the_one_the_photo_sits_in() -> None:
    segments = [
        SpokenSegment("This is the bedroom.", 62_000, 64_000),
        SpokenSegment("And the other bedroom.", 122_000, 124_000),
    ]

    placements = place_photos(
        [PhotoMoment(PHOTO, 126_000)], segments, _zones(), _index()
    )

    assert placements == {PHOTO: BEDROOM_TWO}


def test_configured_synonyms_are_accepted() -> None:
    zones = [ZoneWindow(KITCHEN, "living_room", 0, 60_000)]
    segments = [SpokenSegment("Coming into the lounge now.", 8_000, 10_000)]

    placements = place_photos([PhotoMoment(PHOTO, 12_000)], segments, zones, _index())

    assert placements == {PHOTO: KITCHEN}


def test_room_words_inside_longer_words_do_not_match() -> None:
    segments = [SpokenSegment("The kitchenette is tiny.", 8_000, 10_000)]

    placements = place_photos(
        [PhotoMoment(PHOTO, 12_000)], segments, _zones(), _index()
    )

    assert placements == {}


def test_a_named_room_with_no_detected_zone_leaves_the_photo_unplaced() -> None:
    zones = [ZoneWindow(KITCHEN, "kitchen", 0, 60_000)]
    segments = [SpokenSegment("Out on the balcony.", 8_000, 10_000)]

    assert place_photos([PhotoMoment(PHOTO, 12_000)], segments, zones, _index()) == {}


def test_alias_index_drops_phrases_shared_by_two_rooms() -> None:
    index = build_alias_index(
        ["kitchen", "bedroom"],
        {"kitchen": "Kitchen", "bedroom": "Bedroom"},
        {"kitchen": ["back room"], "bedroom": ["back room"]},
    )

    assert ("back room", "kitchen") not in index
    assert ("back room", "bedroom") not in index
    assert ("kitchen", "kitchen") in index
