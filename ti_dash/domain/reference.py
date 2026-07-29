COLORS: tuple[str, ...] = (
    "Red",
    "Blue",
    "Green",
    "Yellow",
    "Purple",
    "Orange",
    "Pink",
    "Black",
)

STRATEGY_CARDS: dict[int, str] = {
    1: "Leadership",
    2: "Diplomacy",
    3: "Politics",
    4: "Construction",
    5: "Trade",
    6: "Warfare",
    7: "Technology",
    8: "Imperial",
}

PHASES: tuple[str, ...] = ("Strategy", "Action", "Status", "Agenda")

CONTEXTS: tuple[str, ...] = (
    "strategy_pick",
    "action",
    "secondary",
    "status",
    "agenda_window",
    "agenda_vote",
)

FACTIONS: tuple[str, ...] = (
    # --- Base game ---
    "The Arborec",
    "The Barony of Letnev",
    "The Clan of Saar",
    "The Embers of Muaat",
    "The Emirates of Hacan",
    "The Federation of Sol",
    "The Ghosts of Creuss",
    "The L1Z1X Mindnet",
    "The Mentak Coalition",
    "The Naalu Collective",
    "The Nekro Virus",
    "Sardakk N'orr",
    "The Universities of Jol-Nar",
    "The Winnu",
    "The Xxcha Kingdom",
    "The Yin Brotherhood",
    "The Yssaril Tribes",
    # --- Prophecy of Kings ---
    "The Argent Flight",
    "The Empyrean",
    "The Mahact Gene-Sorcerers",
    "The Naaz-Rokha Alliance",
    "The Nomad",
    "The Titans of Ul",
    "The Vuil'raith Cabal",
    "The Council Keleres",
    # --- Thunder's Edge (populate faction names here) ---
    # TODO(user): add Thunder's Edge faction names as string entries.
)
