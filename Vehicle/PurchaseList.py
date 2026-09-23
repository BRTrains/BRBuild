"""Purchase-list ordering for the vehicles a build produced.

OpenTTD lists a GRF's vehicles in vehicle-ID order unless the GRF supplies a `sort`
block, so what a player sees is otherwise an accident of the ID registry. These blocks
are derived from the project's own vehicle data rather than a hand-maintained list of
item symbols, which goes stale whenever a unit is added, renamed or re-identified.

A project opts in from `GRF.yaml`:

    purchase_list:
      order: grouped      # grouped | date | none (the default)

`grouped` is four groups, in this order:

1. Everything else, by introduction date. A BR Standard class lands here, because its
   name starts `Standard Class` and not `Class <number>` — the digits requirement in
   the class pattern is the whole exclusion, so no unit needs special-casing.
2. The BR/privatisation class grouping: a name starting `Class <number>[/<subclass>]`,
   ordered by class, then subclass.
3. Coaches (`train_type: coach`).
4. Wagons (`train_type: wagon`).

Road vehicles (trams) are always ordered by introduction date, whatever the setting;
a classification that only speaks about rail stock should not decide the tram order.
Vehicles of one candidate stay contiguous and keep the order the variant iterator
produced (profile-outer, livery-inner), so a livery's variants never interleave with
another unit's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from PropertyCalculation.TrainType import TrainType

#: The accepted `purchase_list.order` values.
NONE = "none"
DATE = "date"
GROUPED = "grouped"
VALID_ORDERS = (NONE, DATE, GROUPED)

#: A BR/privatisation class designation: `Class 375`, `Class 375/4`. Stock built
#: before the class numbering (and BR Standard classes) does not match this.
CLASS_NAME = re.compile(r"^Class\s+(\d+)(?:\s*/\s*(\d+))?", re.IGNORECASE)

#: An NML date expression, as the vehicle loader renders `introduction_date`.
DATE_EXPRESSION = re.compile(r"date\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")

DATE_UNKNOWN = (9999, 12, 31)

OTHER_GROUP = 1
CLASS_GROUP = 2
COACH_GROUP = 3
WAGON_GROUP = 4


def parse_order(raw) -> str:
    """Validate a `purchase_list.order` value."""
    if raw is None:
        return NONE
    if not isinstance(raw, str):
        raise ValueError(
            f"'purchase_list.order' must be one of {', '.join(VALID_ORDERS)}, got {raw!r}"
        )
    order = raw.strip().lower()
    if order not in VALID_ORDERS:
        raise ValueError(
            f"'purchase_list.order: {raw}' is not understood. Use one of: "
            f"{', '.join(VALID_ORDERS)}."
        )
    return order


@dataclass(frozen=True)
class VehicleFacts:
    """The vehicle facts the purchase-list order depends on."""

    identifier: str
    name: str
    feature: str
    #: The candidate the variant belongs to, so a unit's variants are one run in the list.
    unit: str = ""
    introduction_date: Optional[str] = None
    train_type: Optional[TrainType] = None
    #: Stable position within the build, so entries with equal keys keep build order.
    position: int = 0


@dataclass(frozen=True)
class PurchaseListEntry:
    facts: VehicleFacts
    group: int
    class_number: int
    subclass: int
    released: tuple

    @property
    def identifier(self) -> str:
        return self.facts.identifier

    @property
    def sort_key(self) -> tuple:
        return (
            self.group,
            self.class_number,
            self.subclass,
            self.released,
            self.facts.name.casefold(),
            self.facts.position,
        )

    @property
    def released_text(self) -> str:
        if self.released == DATE_UNKNOWN:
            return "no date"
        return "%04d-%02d-%02d" % self.released


def parse_date(raw) -> tuple:
    """Read an NML `date(y, m, d)` expression into a sortable tuple."""
    if isinstance(raw, tuple):
        return raw
    if raw is None:
        return DATE_UNKNOWN
    match = DATE_EXPRESSION.search(str(raw))
    if not match:
        return DATE_UNKNOWN
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def group_of(facts: VehicleFacts) -> int:
    """Return the group a vehicle belongs to, or 0 for a feature without groups."""
    if facts.feature != "FEAT_TRAINS":
        return 0
    if facts.train_type is TrainType.COACH:
        return COACH_GROUP
    if facts.train_type is TrainType.WAGON:
        return WAGON_GROUP
    if CLASS_NAME.match(facts.name or ""):
        return CLASS_GROUP
    return OTHER_GROUP


def entry_for(facts: VehicleFacts) -> PurchaseListEntry:
    match = CLASS_NAME.match(facts.name or "") if facts.feature == "FEAT_TRAINS" else None
    return PurchaseListEntry(
        facts=facts,
        group=group_of(facts),
        class_number=int(match.group(1)) if match else 0,
        subclass=int(match.group(2) or 0) if match else 0,
        released=parse_date(facts.introduction_date),
    )


def facts_from_variant(variant, position: int) -> VehicleFacts:
    """Read the ordering facts off a processed `Variant`."""
    vehicle = variant.vehicle
    vehicle_type = getattr(variant, "vehicle_type", None) or getattr(vehicle, "vehicle_type", None)
    feature = getattr(vehicle_type, "nml_feature", None) or ""

    introduction_date = getattr(vehicle, "introduction_date", None)
    if introduction_date is None:
        introduction_date = variant.get_attr("introduction_date")

    return VehicleFacts(
        identifier=variant.identifier,
        name=vehicle.name or vehicle.identifier,
        feature=feature,
        unit=vehicle.identifier,
        introduction_date=introduction_date,
        train_type=getattr(vehicle, "train_type", None),
        position=position,
    )


def build_blocks(variants: Sequence, order: str) -> list[str]:
    """Render one `sort(...)` block per feature, or nothing when order is `none`."""
    if order == NONE:
        return []

    facts = [facts_from_variant(variant, position) for position, variant in enumerate(variants)]

    by_feature: dict[str, list[VehicleFacts]] = {}
    for item in facts:
        by_feature.setdefault(item.feature, []).append(item)

    blocks = []
    for feature in sorted(by_feature):
        entries = [entry_for(item) for item in by_feature[feature] if item.identifier]
        if len(entries) < 2:
            continue
        if order == DATE or feature != "FEAT_TRAINS":
            entries.sort(key=lambda entry: (entry.released, entry.facts.name.casefold(), entry.facts.position))
        else:
            entries.sort(key=lambda entry: entry.sort_key)
        blocks.append(render_block(feature, entries, order))
    return blocks


def render_block(feature: str, entries: Iterable[PurchaseListEntry], order: str) -> str:
    feature_label = "trams" if feature == "FEAT_ROADVEHS" else "trains"
    lines = [f"// Purchase-list order for {feature_label}."]
    if order == GROUPED and feature == "FEAT_TRAINS":
        lines += [
            "// 1. Everything else, by introduction date (Standard Class stock included).",
            "// 2. The BR/privatisation class grouping.",
            "// 3. Coaches.",
            "// 4. Wagons.",
        ]
    else:
        lines.append("// Introduction-date order.")
    lines.append("// Keep each candidate contiguous; variants retain generated order within the candidate.")
    lines.append(f"sort({feature}, [")

    entries = list(entries)
    previous_unit = None
    for index, entry in enumerate(entries):
        if entry.facts.unit != previous_unit:
            lines.append(f"  // {entry.facts.name} ({entry.released_text})")
            previous_unit = entry.facts.unit
        separator = "" if index == len(entries) - 1 else ","
        lines.append(f"  {entry.identifier}{separator}")
    lines.append("]);")
    return "\n".join(lines)
