"""F4 — faction/color selection with presets."""

from game import COLORS, FACTION_PRESETS, FACTIONS


def test_faction_presets_reference_only_known_factions_and_colors() -> None:
    assert all(faction in FACTIONS for faction in FACTION_PRESETS)
    assert all(color in COLORS for color in FACTION_PRESETS.values())
