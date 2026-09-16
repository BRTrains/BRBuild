from enum import Enum


class TemplateType(Enum):
	"""Whether an NML template describes a vehicle's directional views or a purchase icon."""

	VEHICLE = "vehicle"
	PURCHASE = "purchase"
