def standard_pattern(size: int, is_ohle: bool) -> list[int]:
	"""Build the standard spriteset-usage pattern for a variant of the given size.

	Each entry is the 1-based position (within the variant's group of spritesets) used
	by that articulated part, e.g. [1, 3, 3, 2] means 4 parts sharing 3 spritesets.

	Non-OHLE stock (DMU/battery/hydrogen, or EMUs on 3rd/4th rail only) pads with a
	repeated "middle" spriteset (3). OHLE stock instead reserves one "pantograph"
	spriteset (4) among plain middle cars once there are more than 3 parts.
	"""
	if size <= 0:
		return []
	if size == 1:
		return [1]
	if size == 2:
		return [1, 2]

	if is_ohle:
		return [1, 3] + [4] * (size - 3) + [2]

	return [1] + [3] * (size - 2) + [2]
