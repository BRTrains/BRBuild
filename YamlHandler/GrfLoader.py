import yaml
from pathlib import Path
from GRF.Grf import Grf


class GrfLoader:
    def __init__(self, yaml_path):
        self.yaml_path = Path(yaml_path)

    def load(self) -> Grf:
        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return Grf(
            grfid=data.get("grfid"),
            short_name=data.get("short_name"),
            name=data.get("name"),
            description=data.get("description"),
            version=data.get("version"),
            compatible_version=data.get("compatible_version"),
            params=data.get("params", []),
            global_vehicle_switches=data.get("global_vehicle_switches", [])
        )