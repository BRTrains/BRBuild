import logging
from pathlib import Path

import yaml

from Grf import Grf
from Vehicle.PurchaseList import parse_order


class GrfLoader:
    def __init__(self, yaml_path):
        self.yaml_path = Path(yaml_path)

    def load(self) -> Grf:
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        grf_data = data.get("grf", {}) or {}
        versioning_data = data.get("versioning", {}) or {}
        purchase_list = data.get("purchase_list") or {}
        if not isinstance(purchase_list, dict):
            raise ValueError(
                f"'purchase_list' in {self.yaml_path} must be a mapping with an 'order' key"
            )

        purchase_list_order = parse_order(purchase_list.get("order"))
        purchase_list_file = purchase_list.get("file")
        if purchase_list_file is not None:
            if not isinstance(purchase_list_file, str) or not purchase_list_file.strip():
                raise ValueError(
                    f"'purchase_list.file' in {self.yaml_path} must be a non-empty relative path"
                )
            purchase_list_file = purchase_list_file.strip()
            if Path(purchase_list_file).is_absolute():
                raise ValueError(
                    f"'purchase_list.file' in {self.yaml_path} must be relative to the GRF folder"
                )

        purchase_list_script = purchase_list.get("script")
        if purchase_list_script is not None:
            if not isinstance(purchase_list_script, str) or not purchase_list_script.strip():
                raise ValueError(
                    f"'purchase_list.script' in {self.yaml_path} must be a non-empty relative path"
                )
            purchase_list_script = purchase_list_script.strip()
            if Path(purchase_list_script).is_absolute():
                raise ValueError(
                    f"'purchase_list.script' in {self.yaml_path} must be relative to the project root"
                )

        if purchase_list_file is not None and purchase_list_script is not None:
            raise ValueError(
                f"'purchase_list' in {self.yaml_path} names both a 'file' and a 'script': "
                "name the static list, or the script that produces it, not both"
            )

        logging.getLogger(__name__).debug(f"Loaded GRF data from {self.yaml_path}")

        return Grf(
            grfid = grf_data.get("grfid"),
            short_name = grf_data.get("short_name"),
            name = grf_data.get("name"),
            description = grf_data.get("description"),
            version = versioning_data.get("version"),
            compatible_version = versioning_data.get("compatible_version"),
            params = data.get("params", []),
            global_vehicle_switches = data.get("global_vehicle_switches", []),
            global_actions = data.get("global_actions", []),
            usage_filters = data.get("usage_filters", []),
            purchase_list_order = purchase_list_order,
            purchase_list_file = purchase_list_file,
            purchase_list_script = purchase_list_script,
        )