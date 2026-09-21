"""The project's logical track types and the real railtype labels they fall back to.

A vehicle names a *logical* track type (``RAIL``, ``ELRL``, ``THIRD``, ``FOURTH``) in
its ``track_type`` field. What that means in a given game depends on which railtype
NewGRFs are loaded, so the mapping is a project-level table rather than a value baked
into each vehicle:

* the vehicle says *what kind of infrastructure* it can use;
* the table says *which real railtype label* that resolves to, in preference order.

The table is therefore about compatibility with railtype NewGRFs. A third-rail unit
asks for ``THIRD``; the table decides whether that becomes the standardised ``SAA3``,
an older ``3RDR`` label, or the last-resort ``ELRL`` fallback that keeps the unit
available when no track set defines third rail at all.

NML resolution notes (verified against nmlc 0.9.0):
* an entry with one label assigns directly, and an *empty* list is an nmlc crash, so a
  type with no fallbacks of its own is written as the single label it stands for;
* a label that is not a bare identifier (``3RDR``, ``4RDR``) must be quoted;
* declaring the block replaces the default table, so the standard labels a project
  still uses have to be declared explicitly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator

import yaml

#: Prefix of the generated NML constant a vehicle names for each logical track type.
CONST_PREFIX = "railtype_"

#: A bare NML identifier; anything else has to be quoted in the table.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class RailTypeTable:
    """Ordered railtype fallbacks for each logical track type the project defines."""

    #: logical name -> the railtype labels it may resolve to, best first.
    entries: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def load(cls, path) -> "RailTypeTable":
        """Read a ``RailTypes.yaml`` mapping of logical name to ordered fallbacks."""
        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if not isinstance(data, dict):
            raise ValueError(
                f"Railtype table in {path} must be a mapping of track type to fallbacks"
            )

        entries: dict[str, list[str]] = {}
        for key, fallbacks in data.items():
            name = str(key).strip()
            if not name:
                raise ValueError(f"Railtype table in {path} has an empty track type name")
            if fallbacks is None:
                entries[name] = []
                continue
            if not isinstance(fallbacks, list):
                raise ValueError(
                    f"Railtype table entry '{name}' in {path} must be a list of labels, "
                    f"got {type(fallbacks).__name__}"
                )
            entries[name] = [str(label).strip() for label in fallbacks if str(label).strip()]

        return cls(entries=entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    def __iter__(self) -> Iterator[str]:
        return iter(self.entries)

    def keys(self) -> list[str]:
        return list(self.entries)

    def has(self, name: str) -> bool:
        return str(name).strip() in self.entries

    def lookup(self, name: str) -> str:
        """Return the NML constant a vehicle names to declare this track type."""
        key = str(name).strip()
        if key not in self.entries:
            raise ValueError(
                f"Unknown track type '{name}'. The project defines: "
                f"{', '.join(self.entries) or 'none'}"
            )
        return f"{CONST_PREFIX}{key}"

    def lookup_many(self, names) -> str:
        """Join several logical track types into one NML ``track_type`` expression."""
        return " + ".join(self.lookup(name) for name in names)

    def lookup_order(self, name: str) -> list[str]:
        """The railtype labels this logical type resolves to, best first.

        A type with no fallbacks of its own still resolves to itself, so `RAIL` means
        the ordinary rail label rather than nothing at all.
        """
        key = str(name).strip()
        self.lookup(key)
        return list(self.entries[key]) or [key]

    def lookup_translation(self, name: str) -> str:
        """The label a logical type translates to: its own name alone, or the first
        *different* label in its fallback list.

        NML's property 0x12 stores one label per entry; the rest of the list has to be
        spelled out through translation tables, which is what `write_nml` does.
        """
        return self.lookup_order(name)[0]

    @staticmethod
    def quote_label(label: str) -> str:
        """Quote a railtype label only when NML cannot read it as a bare identifier."""
        return label if _IDENTIFIER.fullmatch(label) else f'"{label}"'

    def write_nml(self, handle, indent: int = 0) -> None:
        """Write the ``railtypetable`` block and the constants vehicles name.

        Always the list form, even for one label: nmlc accepts `RAIL: [RAIL]` and a
        single-element list assigns that label, but a *bare* label (`RAIL: RAIL`) is a
        syntax error and an empty list is an internal crash.
        """
        pad = "\t" * indent
        handle.write(f"{pad}railtypetable {{\n")
        for name, fallbacks in self.entries.items():
            labels = fallbacks or [name]
            rendered = ", ".join(self.quote_label(label) for label in labels)
            handle.write(f"{pad}\t{name}: [{rendered}],\n")
        handle.write(f"{pad}}}\n")

        handle.write(f"\n{pad}// Indices for each logical track type a vehicle can name.\n")
        for name in self.entries:
            handle.write(f"{pad}const {CONST_PREFIX}{name} = {name};\n")
