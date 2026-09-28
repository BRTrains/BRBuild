"""Build-generated, portable documentation manifest."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ManifestWriter:
    """Project manifest writer that only consumes already-materialised build state."""

    def __init__(self, project, successful_variants):
        self.project = project
        self.successful_variants = list(successful_variants)
        self.output = Path(project.path) / "docs" / "generated" / "manifest.json"

    def write(self, builder_commit: str | None = None) -> Path:
        document = self.build_document(builder_commit=builder_commit or self._builder_commit())
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.output.with_name(f".{self.output.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary, self.output)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return self.output

    def write_failure_report(self, error: Exception) -> Path:
        """Best-effort diagnostic; never replace a successful manifest."""
        output = self.output.with_name("manifest.failure.json")
        document = {
            "schema_version": 1,
            "project": str(self.project.name),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "build_success": False,
            "error": {"type": type(error).__name__, "message": str(error)},
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary, output)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return output

    def build_document(self, builder_commit: str | None = None) -> dict[str, Any]:
        variants = [self._variant(variant) for variant in self.successful_variants]
        return {
            "schema_version": 1,
            "project": str(self.project.name),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "builder_commit": builder_commit,
            "build_success": True,
            "vehicles": self._vehicles(),
            "profiles": self._profiles(),
            "liveries": self._liveries(),
            "variants": variants,
        }

    def _vehicles(self):
        result = {}
        for variant in self.successful_variants:
            vehicle = variant.vehicle
            identifier = str(vehicle.identifier)
            if identifier in result:
                continue
            result[identifier] = {
                "identifier": identifier,
                "name": vehicle.name,
                "subtitle": getattr(vehicle, "sub_name", None),
                "based_on": getattr(vehicle, "based_on", None),
                "vehicle_type": self._value(getattr(getattr(vehicle, "vehicle_type", None), "name", getattr(vehicle, "vehicle_type", None))),
                "train_type": self._value(getattr(getattr(vehicle, "train_type", None), "name", getattr(vehicle, "train_type", None))),
                "introduction_date": self._value(getattr(vehicle, "introduction_date", None)),
                "stats": {key: self._value(getattr(vehicle, key, None)) for key in (
                    "speed", "design_speed", "power", "weight", "capacity", "tractive_effort",
                    "power_type", "track_type", "cargo_classes", "default_cargo_type", "loading_speed",
                )},
                "special_tags": list(getattr(vehicle, "special_tags", None) or []),
                "source_yaml": self._path(getattr(vehicle, "yaml_path", None), "source_yaml"),
                "spritesheet": self._path(getattr(vehicle, "spritesheet_path", None), "source_artwork"),
            }
        return list(result.values())

    def _profiles(self):
        result = {}
        for variant in self.successful_variants:
            key = (str(variant.vehicle.identifier), str(variant.profile.identifier))
            if key in result:
                result[key]["variants"].append(variant.identifier)
                continue
            result[key] = {
                "vehicle_identifier": str(variant.vehicle.identifier),
                "identifier": str(variant.profile.identifier),
                "name": variant.profile.name,
                "resolved": {field: self._value(self._resolved(variant, field)) for field in (
                    "num_vehicles", "capacity", "power", "weight", "speed", "introduction_date",
                    "track_type", "cargo_classes", "default_cargo_type", "sprite_pattern",
                )},
                "sprite_group": getattr(variant.profile, "sprite_group", None),
                "spritesheet": self._path(getattr(variant.profile, "spritesheet", None), "source_artwork"),
                "source_restrictions": {
                    "sprite_group": getattr(variant.profile, "sprite_group", None),
                    "special_tags": list(getattr(variant.profile, "special_tags", None) or []),
                },
                "variants": [variant.identifier],
            }
        return list(result.values())

    @staticmethod
    def _resolved(variant, field):
        if field == "sprite_pattern":
            return getattr(variant, field, None)
        resolver = getattr(variant, "get_attr", None)
        if callable(resolver):
            return resolver(field)
        for obj in (getattr(variant, "livery", None), getattr(variant, "profile", None), getattr(variant, "vehicle", None)):
            value = getattr(obj, field, None)
            if value is not None:
                return value
        return None

    def _liveries(self):
        result = {}
        for variant in self.successful_variants:
            key = (str(variant.vehicle.identifier), str(variant.livery.name))
            if key in result:
                result[key]["variants"].append(variant.identifier)
                continue
            result[key] = {
                "vehicle_identifier": str(variant.vehicle.identifier),
                "name": variant.livery.name,
                "special_tags": list(getattr(variant.livery, "special_tags", None) or []),
                "profile_restrictions": list(getattr(variant.livery, "profiles", None) or []),
                "spritesheet": self._path(getattr(variant.livery, "spritesheet", None), "source_artwork"),
                "variants": [variant.identifier],
            }
        return list(result.values())

    def _variant(self, variant) -> dict[str, Any]:
        vehicle = getattr(variant, "vehicle", None)
        profile = getattr(variant, "profile", None)
        livery = getattr(variant, "livery", None)
        spritesets = list(getattr(variant, "spritesets", None) or [])
        templates = list(getattr(variant, "sprite_template_names", None) or [])
        lengths = list(getattr(variant, "sprite_lengths", None) or [])
        names = list(getattr(variant, "spriteset_names", None) or [])
        pattern = list(getattr(variant, "sprite_pattern", None) or [])

        item = {
            "vehicle": self._identity(vehicle, ("identifier", "name")),
            "profile": self._identity(profile, ("identifier", "name")),
            "livery": self._identity(livery, ("name",)),
            "variant": {
                "identifier": getattr(variant, "identifier", None),
                "nml_filename": self._path(getattr(variant, "nml_filename", None), "nml"),
                "vehicle_type": self._value(getattr(getattr(variant, "vehicle_type", None), "name", getattr(variant, "vehicle_type", None))),
                "display_name": getattr(variant, "name", None),
                "graphics_emitted": bool(spritesets),
            },
            "formation": {
                "part_count": len(pattern) or getattr(variant, "articulated_count", None) or 1,
                "sprite_pattern": pattern,
            },
            "spritesets": [
                self._spriteset(s, i, templates, lengths, names) for i, s in enumerate(spritesets)
            ],
            "purchase": self._purchase(variant),
            "lighting": {
                "overlay": self._path(getattr(variant, "lighting_overlay_path", None), "lighting_overlay"),
                "transparent": self._path(getattr(variant, "lighting_transparent_path", None), "lighting_transparent"),
            },
            "sprite_id": {
                "id": getattr(variant, "sprite_id", None),
                "generation": getattr(variant, "sprite_id_generation", None),
            },
            "sprite_group": {
                "source": getattr(profile, "sprite_group", None),
                "reused": bool(getattr(profile, "sprite_group", None)),
            },
            "source_restrictions": {
                "livery_profiles": list(getattr(livery, "profiles", None) or []),
                "profile_spritesheet": self._path(getattr(profile, "spritesheet", None), "profile_spritesheet"),
                "livery_spritesheet": self._path(getattr(livery, "spritesheet", None), "livery_spritesheet"),
            },
        }
        return item

    def _spriteset(self, spriteset, index, templates, lengths, names):
        template = getattr(spriteset, "template", None)
        template_name = templates[index] if index < len(templates) else getattr(template, "name", None)
        return {
            "spriteset": names[index] if index < len(names) else getattr(spriteset, "name", None),
            "source_name": getattr(spriteset, "name", None),
            "file": self._path(getattr(spriteset, "file", None), "spritesheet"),
            "template": template_name,
            "length": lengths[index] if index < len(lengths) else None,
            "order": index,
            "x": getattr(spriteset, "x", None),
            "y": getattr(spriteset, "y", None),
            "rows": [self._row(row) for row in list(getattr(template, "sprites", None) or [])],
        }

    def _purchase(self, variant):
        spriteset = getattr(variant, "purchase_spriteset", None)
        if spriteset is None:
            return None
        template = getattr(variant, "purchase_template_name", None)
        return {
            "name": getattr(variant, "purchase_spriteset_name", None),
            "template": template,
            "file": self._path(getattr(spriteset, "file", None), "purchase_spritesheet"),
            "x": getattr(spriteset, "x", None),
            "y": getattr(spriteset, "y", None),
            "rows": [self._row(row) for row in list(getattr(getattr(spriteset, "template", None), "sprites", None) or [])],
        }

    @staticmethod
    def _row(row):
        return {
            "left_x": getattr(row, "left_x", None), "upper_y": getattr(row, "upper_y", None),
            "width": getattr(row, "width", None), "height": getattr(row, "height", None),
            "offset_x": getattr(row, "offset_x", None), "offset_y": getattr(row, "offset_y", None),
            "flags": list(getattr(row, "flags", None) or []),
        }

    def _path(self, value, kind):
        if value is None:
            return None
        raw = Path(str(value))
        if not raw.is_absolute():
            return {"path": raw.as_posix(), "kind": kind}
        try:
            relative = raw.resolve().relative_to(Path(self.project.path).resolve())
        except ValueError:
            relative = Path("external") / raw.name
        return {"path": relative.as_posix(), "kind": kind}

    @staticmethod
    def _identity(value, fields):
        return {field: ManifestWriter._value(getattr(value, field, None)) for field in fields} if value else {}

    @staticmethod
    def _value(value):
        if hasattr(value, "name") and not isinstance(value, str):
            return value.name
        if isinstance(value, Path):
            return value.as_posix()
        return value

    def _builder_commit(self):
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
                text=True, stderr=subprocess.DEVNULL,
            ).strip() or None
        except (OSError, subprocess.SubprocessError):
            return None
