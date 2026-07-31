from enum import Enum, StrEnum, auto


class Color(StrEnum):
    RED = auto()
    BLUE = auto()
    GREEN = auto()
    YELLOW = auto()
    PURPLE = auto()
    ORANGE = auto()
    PINK = auto()
    BLACK = auto()


class StrategyCard(Enum):
    Leadership = 1
    Diplomacy = 2
    Politics = 3
    Construction = 4
    Trade = 5
    Warfare = 6
    Technology = 7
    Imperial = 8


class Phase(StrEnum):
    Strategy = auto()
    Action = auto()
    Status = auto()
    Agenda = auto()


class Context(Enum):
    STRATEGY_PICK = auto()
    ACTION = auto()
    SECONDARY = auto()
    STATUS = auto()
    AGENDA_WINDOW = auto()
    AGENDA_VOTE = auto()


class Faction(StrEnum):
    F = "F"
    # --- Base game ---
    ARBOREC = "The Arborec"
    BARONY = "The Barony of Letnev"
    SAAR = "The Clan of Saar"
    MUAAT = "The Embers of Muaat"
    HACAN = "The Emirates of Hacan"
    SOL = "The Federation of Sol"
    GHOSTS = "The Ghosts of Creuss"
    L1Z1X = "The L1Z1X Mindnet"
    MENTAK = "The Mentak Coalition"
    NAALU = "The Naalu Collective"
    NEKRO = "The Nekro Virus"
    SARDAKK = "Sardakk N'orr"
    JOL_NAR = "The Universities of Jol-Nar"
    WINNU = "The Winnu"
    XXCHA = "The Xxcha Kingdom"
    YIN = "The Yin Brotherhood"
    YSSARIL = "The Yssaril Tribes"
    # --- Prophecy of Kings ---
    ARGENT = "The Argent Flight"
    EMPYREAN = "The Empyrean"
    MAHACT = "The Mahact Gene-Sorcerers"
    NAZZ_ROKHA = "The Naaz-Rokha Alliance"
    NOMAD = "The Nomad"
    TITANS = "The Titans of Ul"
    VUILRAITH = "The Vuil'raith Cabal"
    KELERES = "The Council Keleres"
    # --- Thunder's Edge ---
    BASTION = "Last Bastion"
    RAL_NEL = "The Ral Nel Consortium"
    DEEPWROUGHT = "The Deepwrought Scholarate"
    CRIMSON = "The Crimson Rebellion"
    FIRMAMENT = "The Firmament/The Obsidian"


class BudgetField: ...


BUDGET_FIELDS: dict[Context, str] = {
    Context.STRATEGY_PICK: "strategy_pick_seconds",
    Context.ACTION: "action_seconds",
    Context.SECONDARY: "secondary_seconds",
    Context.STATUS: "status_seconds",
    Context.AGENDA_WINDOW: "agenda_window_seconds",
    Context.AGENDA_VOTE: "agenda_vote_seconds",
}
