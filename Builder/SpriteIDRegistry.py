from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)


class SpriteIDRegistry:
    """Persist vehicle IDs and the GNML needed to retain released variants."""

    FIRST_ID = 1001
    STRING_REFERENCE_PATTERN = re.compile(r"\bstring\(([^)]+)\)")
    #: Identifiers a project renamed after an archived variant was generated. A tombstone
    #: is copied verbatim from its archive, so a stale symbol would fail the release
    #: compile with an unknown identifier; rewriting the reference keeps the archived
    #: definition buildable. Keyed by the project-visible name, so the values are the
    #: project's own symbols rather than anything BRBuild owns.
    RENAMED_SYMBOLS: dict[str, str] = {
        "param_passenger_multiplier": "param_capacity_scaling",
    }

    def __init__(self, yaml_path: str | Path, archive_folder: str | Path, release: bool = False):
        self.yaml_path = Path(yaml_path)
        self.archive_folder = Path(archive_folder)
        self.release = release
        self.entries: list[dict[str, Any]] = []
        self._seen: set[int] = set()
        self._deprecated_this_build: list[dict[str, Any]] = []
        self._load()

    def resolve(
        self,
        vehicle: str,
        profile: str,
        livery: str,
        vehicle_type: str,
        compatibility: dict[str, Any],
    ) -> dict[str, Any]:
        key = self._key(vehicle, profile, livery, vehicle_type)
        entry = self._current_entry(key)

        if entry is not None and self.release and entry.get("locked", False):
            if self._compatibility_changed(entry, compatibility):
                entry["active"] = False
                entry["deprecated"] = True
                self._deprecated_this_build.append(entry)
                entry = None

        if entry is None:
            entry = self._new_entry(key, compatibility)
            if self.release:
                entry["locked"] = True
        elif not entry.get("locked", False):
            entry["compatibility"] = self._normalise_compatibility(compatibility)

        entry["active"] = True
        self._save()

        return {
            "id": entry["id"],
            "generation": entry["generation"],
            "entry": entry,
        }

    def prepare(self, keys: set[tuple[str, str, str, str]]) -> None:
        """Free unlocked IDs whose variants are absent before allocating new ones."""
        for entry in self.entries:
            if entry.get("locked", False) or self._entry_key(entry) in keys:
                continue
            entry["id"] = None
            entry["active"] = False
            entry["deprecated"] = False
        self._save()

    def mark_written(self, assignment: dict[str, Any]) -> None:
        """Mark an assignment as present in the successfully generated build."""
        self._seen.add(id(assignment["entry"]))

    def archive_variant(
        self,
        assignment: dict[str, Any],
        nml_path: str | Path,
        strings: dict[str, str],
        identifier: str,
    ) -> None:
        """Keep the latest emitted GNML and language strings for this ID."""
        entry = assignment["entry"]
        source = Path(nml_path)
        self.archive_folder.mkdir(parents=True, exist_ok=True)
        existing_archive = entry.get("archive")
        if existing_archive and entry.get("locked", False):
            existing_path = self.yaml_path.parent / existing_archive
            if existing_path.is_file():
                return

        destination = self.archive_folder / f"{entry['id']}_{source.name}"
        shutil.copy2(source, destination)

        entry["archive"] = str(destination.relative_to(self.yaml_path.parent))
        entry["identifier"] = identifier
        entry["name_string"] = f"str_{identifier}_name"
        entry["strings"] = self.referenced_strings(source, strings)
        self._save()

    @classmethod
    def referenced_strings(cls, nml_path: str | Path, strings: dict[str, str]) -> dict[str, str]:
        """Return only language entries referenced by one variant's GNML."""
        references = set(cls.STRING_REFERENCE_PATTERN.findall(Path(nml_path).read_text(encoding="utf-8")))
        return {name: text for name, text in strings.items() if name in references}

    def finalize(self, output_folder: str | Path) -> list[str]:
        """Mark entries absent from this build and materialise released tombstones."""
        deprecated_entries = list(self._deprecated_this_build)
        if self.release:
            deprecated_entries.extend(
                entry
                for entry in self.entries
                if entry.get("locked", False) and entry.get("deprecated", False)
            )

        for entry in self.entries:
            if id(entry) in self._seen:
                entry["active"] = True
                if self.release:
                    entry["locked"] = True
                continue

            entry["active"] = False
            if entry.get("locked", False):
                if self.release and not entry.get("deprecated", False):
                    entry["deprecated"] = True
                    deprecated_entries.append(entry)
            else:
                entry["id"] = None
                entry["deprecated"] = False

        deprecated_files = []
        if self.release:
            for entry in self._unique_entries(deprecated_entries):
                deprecated_file = self._write_deprecated(entry, output_folder)
                if deprecated_file is not None:
                    deprecated_files.append(str(deprecated_file))

        self._save()
        return deprecated_files

    def register_deprecated_strings(self, write_string: Callable[[str, str], str]) -> None:
        """Add archived strings to the current language registry for release builds."""
        if not self.release:
            return

        for entry in self.entries:
            if not entry.get("deprecated", False):
                continue

            name_string = entry.get("name_string")
            for name, text in (entry.get("strings") or {}).items():
                if name == name_string and not text.startswith("(DEPRECATED)"):
                    text = f"(DEPRECATED) {text}"
                write_string(text, name)

    def _write_deprecated(self, entry: dict[str, Any], output_folder: str | Path) -> Path | None:
        archive = entry.get("archive")
        if not archive:
            logger.warning("Cannot emit deprecated sprite ID %s: no GNML archive exists.", entry.get("id"))
            return None

        source = self.yaml_path.parent / archive
        if not source.is_file():
            logger.warning("Cannot emit deprecated sprite ID %s: archive '%s' is missing.", entry.get("id"), source)
            return None

        target = Path(output_folder) / f"deprecated_{entry['id']}_{source.name}"
        content = source.read_text(encoding="utf-8")
        for old, new in self.RENAMED_SYMBOLS.items():
            content = re.sub(rf"\b{re.escape(old)}\b", new, content)
        content = re.sub(
            r"(climates_available\s*:\s*)ALL_CLIMATES(\s*;)",
            r"\1NO_CLIMATE\2",
            content,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def _current_entry(self, key: tuple[str, str, str, str]) -> dict[str, Any] | None:
        matches = [
            entry
            for entry in self.entries
            if self._entry_key(entry) == key
            and entry.get("id") is not None
            and not entry.get("deprecated", False)
        ]
        return matches[-1] if matches else None

    def _new_entry(self, key: tuple[str, str, str, str], compatibility: dict[str, Any]) -> dict[str, Any]:
        generation = max(
            (entry.get("generation", 0) for entry in self.entries if self._entry_key(entry) == key),
            default=0,
        ) + 1
        entry = {
            "id": self._next_id(),
            "vehicle": key[0],
            "profile": key[1],
            "livery": key[2],
            "vehicle_type": key[3],
            "generation": generation,
            "locked": False,
            "active": False,
            "deprecated": False,
            "compatibility": self._normalise_compatibility(compatibility),
        }
        self.entries.append(entry)
        return entry

    def _next_id(self) -> int:
        used_ids = {entry["id"] for entry in self.entries if isinstance(entry.get("id"), int)}
        candidate = self.FIRST_ID
        while candidate in used_ids:
            candidate += 1
        return candidate

    @staticmethod
    def _key(vehicle: str, profile: str, livery: str, vehicle_type: str) -> tuple[str, str, str, str]:
        return tuple(str(value).strip().lower() for value in (vehicle, profile, livery, vehicle_type))

    def _entry_key(self, entry: dict[str, Any]) -> tuple[str, str, str, str]:
        return self._key(
            entry.get("vehicle", ""),
            entry.get("profile", ""),
            entry.get("livery", ""),
            entry.get("vehicle_type", ""),
        )

    @staticmethod
    def _normalise_compatibility(compatibility: dict[str, Any]) -> dict[str, Any]:
        return {
            "capacity": int(compatibility.get("capacity", 0)),
            "articulated_count": int(compatibility.get("articulated_count", 1)),
            "lengths": [int(length) for length in compatibility.get("lengths", [])],
        }

    def _compatibility_changed(self, entry: dict[str, Any], compatibility: dict[str, Any]) -> bool:
        return entry.get("compatibility", {}) != self._normalise_compatibility(compatibility)

    def _unique_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for entry in entries:
            if id(entry) not in seen:
                result.append(entry)
                seen.add(id(entry))
        return result

    def _load(self) -> None:
        if not self.yaml_path.is_file():
            return

        data = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}
        legacy = "variants" not in data and "vehicles" in data
        raw_entries = data.get("variants", data.get("vehicles", [])) or []
        for raw_entry in raw_entries:
            entry = dict(raw_entry)
            entry["id"] = int(entry["id"]) if entry.get("id") is not None else None
            entry["generation"] = int(entry.get("generation", 1))
            entry["locked"] = bool(entry.get("locked", legacy))
            entry["active"] = bool(entry.get("active", True))
            entry["deprecated"] = bool(entry.get("deprecated", False))
            if entry.get("compatibility"):
                entry["compatibility"] = self._normalise_compatibility(entry["compatibility"])
            archive = entry.get("archive")
            if archive and entry.get("strings"):
                archive_path = self.yaml_path.parent / archive
                if archive_path.is_file():
                    entry["strings"] = self.referenced_strings(archive_path, entry["strings"])
            self.entries.append(entry)

    def _save(self) -> None:
        self.yaml_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "variants": self.entries}
        self.yaml_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )