"""Readable tilt / curve-speed handling.

OpenTTD exposes tilting through two separate mechanisms:

* ``curve_speed_mod`` — a multiplier applied after the normal curve-speed
  calculation (``max_curve_speed * (1 + mod)``), so ``0.3`` means "30% faster
  through curves". Range is -128 .. 127.996.
* ``TRAIN_FLAG_TILT`` — the game's own 20% curve-speed tilt bonus, which only
  applies when every vehicle in the consist carries the flag.

Authors describe both as one strength, so BRBuild takes a single ``tilt`` value
per vehicle, profile or livery and derives both from it. Named levels keep the
YAML readable; a bare number is accepted for anything that does not fit a level.
"""

from __future__ import annotations

from typing import Any, Optional


MISC_FLAG_TILT = "TRAIN_FLAG_TILT"
"""The consist-wide tilt flag emitted as part of ``misc_flags``."""

MAX_CURVE_SPEED_MOD = 127.996
MIN_CURVE_SPEED_MOD = -128.0


class Tilt:
	"""A resolved curve-speed modifier plus whether the tilt flag is set."""

	def __init__(self, curve_speed_mod: float):
		self.curve_speed_mod = curve_speed_mod
		self.uses_tilt_flag = curve_speed_mod > 0

	def __eq__(self, other: Any) -> bool:  # pragma: no cover - convenience
		if not isinstance(other, Tilt):
			return NotImplemented
		return (self.curve_speed_mod, self.uses_tilt_flag) == (
			other.curve_speed_mod,
			other.uses_tilt_flag,
		)

	def __repr__(self) -> str:  # pragma: no cover - convenience
		return f"Tilt(curve_speed_mod={self.curve_speed_mod}, uses_tilt_flag={self.uses_tilt_flag})"


class TiltLevels:
	"""Named tilt strengths, so YAML reads as intent rather than magic numbers.

	None of the levels are authoritative OpenTTD values: ``modest``/``strong``
	mirror the multipliers BRTrains2 used for the Class 221 and the APT family,
	and the intermediate steps exist so a new unit can be placed on the same
	scale. Use a bare number when a unit needs an exact value.
	"""

	LEVELS: dict[str, float] = {
		"none": 0.0,
		"basic": 0.1,
		"modest": 0.2,
		"strong": 0.3,
		"extreme": 0.35,
	}

	@classmethod
	def names(cls) -> list[str]:
		return sorted(cls.LEVELS)

	@classmethod
	def curve_speed_mod(cls, level: str) -> float:
		key = str(level).strip().lower().replace("_", " ").replace("-", " ")
		key = key.replace(" ", "")
		for name, value in cls.LEVELS.items():
			if name == key:
				return value
		raise ValueError(
			f"Unknown tilt level '{level}'. Use one of {', '.join(cls.names())}, or a number."
		)


def resolve_tilt(value: Any) -> Optional[Tilt]:
	"""Resolve a YAML ``tilt`` value into a `Tilt`.

	Accepts a named level ("none", "basic", "modest", "strong", "extreme") or a
	number. ``None`` means the field was not set at all, which is different from
	"none" (explicitly zero) only in that it lets a profile/livery fall through to
	the vehicle default.
	"""

	if value is None:
		return None

	if isinstance(value, bool):
		raise ValueError("tilt must be a level name or a number, not a boolean")

	if isinstance(value, (int, float)):
		curve_speed_mod = float(value)
	elif isinstance(value, str):
		text = value.strip()
		if text == "":
			raise ValueError("tilt must not be empty")
		try:
			curve_speed_mod = float(text)
		except ValueError:
			curve_speed_mod = TiltLevels.curve_speed_mod(text)
	else:
		raise ValueError(f"tilt must be a level name or a number, got {type(value).__name__}")

	if not (MIN_CURVE_SPEED_MOD <= curve_speed_mod <= MAX_CURVE_SPEED_MOD):
		raise ValueError(
			f"tilt resolves to {curve_speed_mod}, outside NML's curve_speed_mod range "
			f"({MIN_CURVE_SPEED_MOD} .. {MAX_CURVE_SPEED_MOD})"
		)

	return Tilt(curve_speed_mod)
