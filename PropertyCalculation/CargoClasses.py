"""Cargo classes: the presets this project authors, and the NML constants they mean.

A vehicle's YAML names its cargo with `cargo:`. That is normally one of the named presets
below (`cargo: passenger`, `cargo: containerised`), because the useful unit of meaning is
"what sort of thing does this vehicle carry", not a raw bitmask. An explicit OpenTTD class
is also accepted (`cargo: [mail, CC_ARMOURED]`) so a combination with no preset is still
expressible without inventing one.

Unknown names raise at load rather than being dropped: a dropped class means a vehicle
that cannot be refitted, which is invisible in the build output.
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

#: Named bundles, chosen from what BRTrains2 uses for each kind of unit.
PRESETS: dict[str, tuple[str, ...]] = {
    # Multiple units, trams, London Underground stock, coaches, sleepers.
    "PASSENGER": ("PASSENGERS",),
    # Parcels and express mail units: 128, 325, 321 Freight, 769/5, TPO.
    "PARCELS": ("MAIL", "EXPRESS", "ARMOURED"),
    # Mail-only vehicles, such as the LNER Gresley 616BG.
    "MAIL": ("MAIL",),
    # Container flats and flatbed wagons.
    "CONTAINERISED": (
        "PIECE_GOODS",
        "EXPRESS",
        "HAZARDOUS",
        "REFRIGERATED",
        "NON_POURABLE",
        "NEO_BULK",
        "OVERSIZED",
    ),
    # Hoppers and mineral wagons.
    "BULK": ("BULK", "COVERED", "POWDERIZED", "NON_POURABLE", "NEO_BULK"),
    # Tank wagons.
    "TANK": ("LIQUID",),
    # Open wagons that take general goods only.
    "OPEN_WAGON": ("PIECE_GOODS",),
}

#: Words that mean "this vehicle carries nothing", so an empty class list is emitted.
EMPTY_VALUES: frozenset[str] = frozenset({"NONE", "NO", "EMPTY", "FALSE", "UNREFITTABLE"})


def normalise_token(token: str) -> str:
    """Return the bare name for one authored value.

    Accepts `piece_goods`, `PIECE GOODS`, `cc_piece_goods` and `CC_PIECE_GOODS`.
    """
    text = str(token).strip().upper().replace(" ", "_").replace("-", "_")
    if text.startswith("CC_"):
        text = text[3:]
    return text


def parse_cargo(value, where: str = "'cargo'", presets: bool = True) -> list[str] | None:
    """Resolve an authored cargo value to NML constants.

    Returns None when nothing was authored, and an empty list for an explicit `none`
    (which is emitted as a deliberate empty class list rather than being omitted).
    Accepts a scalar or a list; presets and explicit classes may be mixed.

    `presets=False` resolves class names only, for the exclusion list: `bulk` is both a
    preset (the hopper recipe) and a class, and "not refittable to bulk" must mean the
    class. Pass an explicit `CC_BULK` there if you want to be unambiguous.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        raise ValueError(
            f"{where} takes its value directly, not a nested block: write "
            f"'cargo: passenger' or 'cargo: [mail, express]'. The nested "
            f"'cargo: {{cargo_classes: [...]}}' form is gone."
        )
    if isinstance(value, str):
        values: Iterable = [value]
    elif isinstance(value, Iterable):
        values = value
    else:
        raise ValueError(f"{where} must be a preset name, an NML class, or a list of them")

    resolved: list[str] = []
    for item in values:
        token = str(item).strip()
        if not token:
            continue
        # An explicit `CC_` prefix means "this is a class", so it always resolves to that
        # one class. A bare name is read as a preset first, which is what lets `cargo: bulk`
        # mean the hopper recipe while `cargo: CC_BULK` means the single bulk class.
        explicit_class = token.upper().startswith("CC_")
        name = normalise_token(token)
        if name in EMPTY_VALUES:
            continue
        if explicit_class and name in CARGO_CLASSES:
            members = (name,)
        elif presets and not explicit_class and name in PRESETS:
            members = PRESETS[name]
        elif name in CARGO_CLASSES:
            members = (name,)
        elif presets and name in PRESETS:
            members = PRESETS[name]
        else:
            presets_list = ", ".join(sorted(preset.lower() for preset in PRESETS))
            classes = ", ".join(CARGO_CLASSES)
            hint = (
                f"Presets: {presets_list}. Or name classes directly: {classes}"
                if presets
                else f"Name classes directly: {classes}"
            )
            raise ValueError(f"unknown cargo '{item}' in {where}. {hint}")
        for member in members:
            constant = f"CC_{member}"
            if constant not in resolved:
                resolved.append(constant)

    return resolved


def as_bitmask(constants: list[str]) -> str | None:
    """Render resolved classes as an NML bitmask, or None when there are none."""
    if not constants:
        return None
    return f"bitmask({', '.join(constants)})"
