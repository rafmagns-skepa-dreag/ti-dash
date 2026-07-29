from ti_dash.domain import reference as ref


def test_colors_are_the_standard_eight():
    assert ref.COLORS == (
        "Red",
        "Blue",
        "Green",
        "Yellow",
        "Purple",
        "Orange",
        "Pink",
        "Black",
    )


def test_strategy_cards_one_through_eight():
    assert ref.STRATEGY_CARDS == {
        1: "Leadership",
        2: "Diplomacy",
        3: "Politics",
        4: "Construction",
        5: "Trade",
        6: "Warfare",
        7: "Technology",
        8: "Imperial",
    }


def test_phases_and_contexts():
    assert ref.PHASES == ("Strategy", "Action", "Status", "Agenda")
    assert ref.CONTEXTS == (
        "strategy_pick",
        "action",
        "secondary",
        "status",
        "agenda_window",
        "agenda_vote",
    )


def test_factions_include_base_and_pok_and_are_unique():
    assert "The Emirates of Hacan" in ref.FACTIONS  # base
    assert "The Council Keleres" in ref.FACTIONS  # PoK
    assert len(ref.FACTIONS) == len(set(ref.FACTIONS))
