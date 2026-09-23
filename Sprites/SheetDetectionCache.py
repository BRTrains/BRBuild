"""Cache of the sprite rows detected in a spritesheet, beside the sheet itself.

Detecting rows is the most expensive thing a rebuild does (`SpritesheetExtractor`
scans every pixel of every published sheet), and it produces the same answer for the
same sheet, palette and template set. The result is therefore cached in a sidecar file
next to the sheet — `<sheet>.sheetcache.json`, mirroring the `.png.cache` /
`.png.cacheindex` sprite cache nmlc keeps beside each image — and reused while all
three inputs are unchanged. Delete the file to force detection again; it is derived
data, not a build input, and belongs in the project's `.gitignore`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template
from Templates.TemplateDefinition import TemplateDefinition

logger = logging.getLogger(__name__)


class SheetDetectionCache:
	"""Reads and writes the detected rows for one sheet as `<sheet>.sheetcache.json`.

	The cache is only valid for the exact sheet bytes, palette, template definitions and
	vehicle type it was written for; anything else is a miss and the caller re-detects.
	"""

	#: Bump when the stored geometry or the detection it describes changes meaning.
	FORMAT_VERSION = 1
	FORMAT_NAME = "brbuild-sheet-detection"
	SUFFIX = ".sheetcache.json"

	#: Rows are `(Spriteset, TemplateDefinition)` pairs, in sheet order.
	Rows = list[tuple[Spriteset, TemplateDefinition]]

	def __init__(
		self,
		sheet_path: str | Path,
		palette: list[int],
		definitions: list[TemplateDefinition],
		vehicle_type: str,
	):
		self.sheet_path = Path(sheet_path)
		self.palette = palette
		self.definitions = definitions
		self.vehicle_type = vehicle_type
		self._definition_names = {definition.name for definition in definitions}

	@property
	def path(self) -> Path:
		"""Where the cache for this sheet lives (beside it, never inside a build folder)."""
		return self.sheet_path.with_name(self.sheet_path.name + self.SUFFIX)

	def load(self) -> Rows | None:
		"""Return the cached rows, or None if there is no usable cache for this sheet."""
		if not self.path.is_file():
			return None

		try:
			payload = json.loads(self.path.read_text(encoding="utf-8"))
		except (OSError, json.JSONDecodeError) as exc:
			logger.warning(f"Ignoring unreadable sheet cache '{self.path}': {exc}")
			return None

		if not self._payload_matches(payload):
			return None

		rows = []
		for entry in payload["rows"]:
			definition = self._definition(entry["definition"])
			if definition is None:
				self._discard(f"template '{entry['definition']}' is no longer known")
				return None
			rows.append((self._spriteset(entry), definition))

		if not rows:
			return None

		logger.debug(f"Reused detected rows from '{self.path}' ({len(rows)} row(s)).")
		return rows

	def store(self, rows: Rows) -> None:
		"""Write the detected rows, replacing any existing cache for this sheet."""
		if not rows:
			return

		payload = {
			"format": self.FORMAT_NAME,
			"version": self.FORMAT_VERSION,
			"sheet": {
				"name": self.sheet_path.name,
				"sha256": self._file_digest(self.sheet_path),
			},
			"palette_sha256": _digest_of_bytes(bytes(bytearray(self.palette))),
			"templates_sha256": _templates_digest(self.definitions),
			"vehicle_type": self.vehicle_type,
			"rows": [self._entry(spriteset, definition) for spriteset, definition in rows],
		}

		try:
			self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
		except OSError as exc:
			logger.warning(f"Could not write sheet cache '{self.path}': {exc}")
			return

		logger.debug(f"Cached {len(rows)} detected row(s) to '{self.path}'.")

	# ------------------------------------------------------------------
	# Validation
	# ------------------------------------------------------------------

	def _payload_matches(self, payload: dict) -> bool:
		"""Return True when the cache describes the sheet, palette and templates in use."""
		if not isinstance(payload, dict):
			return False
		if payload.get("format") != self.FORMAT_NAME or payload.get("version") != self.FORMAT_VERSION:
			return False
		if payload.get("vehicle_type") != self.vehicle_type:
			return False
		if payload.get("palette_sha256") != _digest_of_bytes(bytes(bytearray(self.palette))):
			return False
		if payload.get("templates_sha256") != _templates_digest(self.definitions):
			return False

		sheet = payload.get("sheet") or {}
		if sheet.get("name") != self.sheet_path.name:
			return False
		if sheet.get("sha256") != self._file_digest(self.sheet_path):
			return False

		return isinstance(payload.get("rows"), list)

	def _discard(self, reason: str) -> None:
		logger.debug(f"Discarding sheet cache '{self.path}': {reason}.")

	def _definition(self, name: str) -> TemplateDefinition | None:
		if name not in self._definition_names:
			return None
		return next(definition for definition in self.definitions if definition.name == name)

	@staticmethod
	def _file_digest(path: Path) -> str | None:
		try:
			return _digest_of_bytes(path.read_bytes())
		except OSError:
			return None

	# ------------------------------------------------------------------
	# Serialisation
	# ------------------------------------------------------------------

	@staticmethod
	def _entry(spriteset: Spriteset, definition: TemplateDefinition) -> dict:
		return {
			"spriteset": spriteset.name,
			"file": spriteset.file,
			"x": spriteset.x,
			"y": spriteset.y,
			"template": spriteset.template.name,
			"definition": definition.name,
			"views": [
				[sprite.left_x, sprite.upper_y, sprite.width, sprite.height]
				for sprite in spriteset.template.sprites
			],
		}

	@staticmethod
	def _spriteset(entry: dict) -> Spriteset:
		views = [
			Sprite(left_x=view[0], upper_y=view[1], width=view[2], height=view[3], offset_x=0, offset_y=0)
			for view in entry["views"]
		]
		return Spriteset(
			name=entry["spriteset"],
			file=entry["file"],
			template=Template(name=entry["template"], sprites=views),
			x=entry["x"],
			y=entry["y"],
		)


def _digest_of_bytes(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def _templates_digest(definitions: list[TemplateDefinition]) -> str:
	"""Digest everything about the loaded definitions that detection depends on.

	Bounding boxes decide both the template a row matches and the purchase-icon crop, so
	they are part of the identity: editing a template must invalidate every sheet cache.
	"""
	described = [
		{
			"name": definition.name,
			"type": definition.template_type.value,
			"vehicle_type": definition.vehicle_type,
			"length": definition.length,
			"legacy": definition.legacy,
			"tall": definition.tall,
			"reversed": definition.is_reversed,
			"purchase_subtype": definition.purchase_subtype,
			"boxes": [
				[box.left_x, box.upper_y, box.width, box.height, box.offset_x, box.offset_y]
				for box in definition.bounding_boxes
			],
		}
		for definition in definitions
	]
	return _digest_of_bytes(json.dumps(described, sort_keys=True).encode("utf-8"))
