from dataclasses import dataclass, field


DEFAULT_GLOBAL_PROPERTIES = {
    "traininfo_y_offset": 2,
    "train_width_32_px": 1,
}


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
    global_properties: dict = field(default_factory=lambda: dict(DEFAULT_GLOBAL_PROPERTIES))
    usage_filters: list = field(default_factory=list)
    #: How the purchase list is ordered: `none` (vehicle-ID order, the default),
    #: `date`, or `grouped` (see `Vehicle/PurchaseList.py`).
    purchase_list_order: str = "none"
    #: Optional manual NML file, relative to the project's GRF folder. When set it
    #: replaces the generated purchase-list blocks.
    purchase_list_file: str | None = None
    #: Optional project script, relative to the project root, that the build runs before
    #: the list is read. It is handed the items the build produced, so a list that names
    #: their symbols cannot go stale.
    purchase_list_script: str | None = None