"""NML cargo classes, and the names this project accepts for them.

`cargo_classes` in a vehicle's YAML names the cargo classes it can be refitted to. The
NML side needs `CC_*` constants, so the YAML may name them either way: `piece_goods`,
`PIECE_GOODS` or `CC_PIECE_GOODS` all resolve to `CC_PIECE_GOODS`. Unknown names raise
rather than being dropped, because a silently ignored class means a wagon that cannot be
refitted and a cargo-driven graphics chain that never fires.
"""

from typing import Iterable

#: Every cargo class NML defines. Kept explicit so an unknown name is a load error.
CARGO_CLASSES: tuple[str, ...] = (
    "ARMOURED",
    "BULK",
    "COVERED",
    "EXPRESS",
    "HAZARDOUS",
    "LIQUID",
    "MAIL",
    "NEO_BULK",
    "NON_POTABLE",
    "NON_POURABLE",
    "OVERSIZED",
    "PASSENGERS",
    "PIECE_GOODS",
    "POTABLE",
    "POWDERIZED",
    "REFRIGERATED",
    "SPECIAL",
)

#: Words that mean "this vehicle carries nothing", so no refittable property is emitted.
EMPTY_VALUES: frozenset[str] = frozenset({"NONE", "NO", "EMPTY", "FALSE", "UNREFITTABLE"})

#: Convenience spellings for the classes this project uses most.
ALIASES: dict[str, str] = {
    "PASSENGER": "PASSENGERS",
    "GOODS": "PIECE_GOODS",
    "GENERAL_GOODS": "PIECE_GOODS",
    "CONTAINER": "PIECE_GOODS",
    "CONTAINERS": "PIECE_GOODS",
    "REFRIGERATED_GOODS": "REFRIGERATED",
    "FRIDGE": "REFRIGERATED",
    "NONPOURABLE": "NON_POURABLE",
    "NONPOTABLE": "NON_POTABLE",
    "NEOBULK": "NEO_BULK",
    "PIECEGOODS": "PIECE_GOODS",
    "ARMORED": "ARMOURED",
    "POWDER": "POWDERIZED",
}


def normalise_token(token: str) -> str:
    """Return the bare class name for one authored value.

    Accepts `piece_goods`, `PIECE GOODS`, `cc_piece_goods` and `CC_PIECE_GOODS`.
    """
    text = str(token).strip().upper().replace(" ", "_").replace("-", "_")
    if text.startswith("CC_"):
        text = text[3:]
    return ALIASES.get(text, text)


def parse_cargo_classes(values) -> list[str]:
    """Validate authored cargo classes and return them as NML constants.

    Accepts a single scalar (`cargo_classes: NONE`, as the family's other projects
    author it) or a list. Empty markers resolve to an empty list.
    """
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Iterable):
        raise ValueError(f"cargo classes must be a name or list of names, got {values!r}")

    resolved: list[str] = []
    for value in values:
        token = str(value).strip()
        if not token:
            continue
        name = normalise_token(token)
        if name in EMPTY_VALUES:
            continue
        if name not in CARGO_CLASSES:
            known = ", ".join(CARGO_CLASSES)
            raise ValueError(
                f"unknown cargo class '{value}'. Known classes: {known}"
            )
        constant = f"CC_{name}"
        if constant not in resolved:
            resolved.append(constant)

    return resolved


def as_bitmask(constants: list[str]) -> str | None:
    """Render resolved classes as an NML bitmask, or None when there are none."""
    if not constants:
        return None
    return f"bitmask({', '.join(constants)})"
