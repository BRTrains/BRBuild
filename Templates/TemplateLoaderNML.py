from __future__ import annotations

from pathlib import Path

from .BoundingBox import BoundingBox
from .TemplateDefinition import TemplateDefinition
from .TemplateType import TemplateType


class TemplateLoaderNML:
	"""Parses NML `template tmpl_...(x, y) { [...] }` blocks into TemplateDefinition objects."""

	def read(self, path: str) -> list[TemplateDefinition]:
		with open(path, "r", encoding="utf-8") as f:
			lines = f.readlines()

		definitions: list[TemplateDefinition] = []

		inside = False
		name: str | None = None
		bboxes: list[BoundingBox] = []

		for raw in lines:
			line = raw.strip()

			if line.startswith("template "):
				name = self._extract_name(line)
				inside = True
				bboxes = []
				continue

			if inside:
				if line.startswith("}"):
					definitions.append(self._build_definition(name, bboxes))
					inside = False
					name = None
					bboxes = []
					continue

				bbox = self._parse_bbox_line(raw)
				if bbox:
					bboxes.append(bbox)

		return definitions

	def read_folder(self, folder: str) -> list[TemplateDefinition]:
		"""Read every .pnml file in a folder and return their combined template definitions."""
		definitions: list[TemplateDefinition] = []
		for path in sorted(Path(folder).glob("*.pnml")):
			definitions.extend(self.read(str(path)))
		return definitions

	# ------------------------------------------------------------------
	# Template construction helpers
	# ------------------------------------------------------------------

	def _extract_name(self, header_line: str) -> str:
		# template tmpl_tram_3_tall(x, y)
		before_paren = header_line.split("(")[0]
		return before_paren.split()[1]

	def _build_definition(self, name: str, bboxes: list[BoundingBox]) -> TemplateDefinition:
		if name.startswith("tmpl_mu_purchase"):
			return TemplateDefinition(
				name=name,
				template_type=TemplateType.PURCHASE,
				purchase_subtype="mu",
				bounding_boxes=bboxes,
			)

		if name.startswith("tmpl_purchase"):
			return TemplateDefinition(
				name=name,
				template_type=TemplateType.PURCHASE,
				bounding_boxes=bboxes,
			)

		# Vehicle templates: tmpl_train_2, tmpl_tram_5_tall, tmpl_train_8_old_reversed, ...
		parts = name.split("_")

		if len(parts) < 3:
			raise ValueError(f"Cannot parse template name: {name!r}")

		_, vehicle_type, length_str = parts[:3]
		tags = parts[3:]

		return TemplateDefinition(
			name=name,
			template_type=TemplateType.VEHICLE,
			vehicle_type=vehicle_type,
			length=int(length_str),
			legacy="old" in tags,
			tall="tall" in tags,
			is_reversed="reversed" in tags,
			variant_tags=tags,
			bounding_boxes=bboxes,
		)

	# ------------------------------------------------------------------
	# Bounding box parser
	# ------------------------------------------------------------------

	def _parse_bbox_line(self, raw_line: str) -> BoundingBox | None:
		"""Parse lines like `[ x+0, y+0, 8, 13, -3, -12, WHITE | NOANIM, "file.png" ]`."""
		if "//" in raw_line:
			raw_line = raw_line.split("//", 1)[0].rstrip()

		if "[" not in raw_line or "]" not in raw_line:
			return None

		inner = raw_line[raw_line.find("[") + 1: raw_line.rfind("]")]
		parts = [p.strip() for p in inner.split(",")]
		parts = [p for p in parts if p != ""]

		if len(parts) < 6:
			return None

		left = int(parts[0].replace("x+", "").strip())
		top = int(parts[1].replace("y+", "").strip())
		width = int(parts[2])
		height = int(parts[3])
		offset_x = int(parts[4])
		offset_y = int(parts[5])

		remaining = parts[6:]
		flags = self._parse_flags_field(remaining[0]) if remaining else []
		filename = self._parse_optional_string(remaining[1]) if len(remaining) >= 2 else None
		mask = self._parse_optional_string(remaining[2]) if len(remaining) >= 3 else None

		return BoundingBox(
			left_x=left,
			upper_y=top,
			width=width,
			height=height,
			offset_x=offset_x,
			offset_y=offset_y,
			flags=flags,
			filename=filename,
			mask=mask,
		)

	def _parse_flags_field(self, field: str) -> list[str]:
		if not field or field == "0":
			return []

		f = field.strip().strip('"').strip("'")
		return [p.strip() for p in f.split("|") if p.strip()]

	def _parse_optional_string(self, field: str) -> str | None:
		if not field or field in ("0", "None", "null"):
			return None

		field = field.strip().strip('"').strip("'")
		return field or None
