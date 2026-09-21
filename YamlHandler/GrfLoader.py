import logging
from pathlib import Path

import yaml

from Grf import Grf


class GrfLoader:
    def __init__(self, yaml_path):
        self.yaml_path = Path(yaml_path)

    def load(self) -> Grf:
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        grf_data = data.get("grf", {}) or {}
        versioning_data = data.get("versioning", {}) or {}

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
        )