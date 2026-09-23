from dataclasses import dataclass, field


@dataclass
class Grf:
    grfid: str
    short_name: str
    name: str
    description: str
    version: str
    compatible_version: str
    params: list = field(default_factory=list)
    global_vehicle_switches: list = field(default_factory=list)
    global_actions: list = field(default_factory=list)
    #: How the purchase list is ordered: `none` (vehicle-ID order, the default),
    #: `date`, or `grouped` (see `Vehicle/PurchaseList.py`).
    purchase_list_order: str = "none"
    #: Optional manual NML file, relative to the project's GRF folder. When set it
    #: replaces the generated purchase-list blocks.
    purchase_list_file: str | None = None