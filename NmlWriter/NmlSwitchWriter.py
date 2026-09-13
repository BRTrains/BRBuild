from .BaseNmlWriter import BaseNmlWriter
from .NmlTargetType import NmlTargetType


class NmlSwitchWriter(BaseNmlWriter):
    def __init__(self):
        super().__init__()

    def write_switch(self, f, vehicle_type, target_type, name, expression, values):
        target_enum = NmlTargetType.from_str(target_type)
        self.writeline(f, f"switch ({vehicle_type}, {target_enum.value}, {name}, {expression})", indent=0)
        self.writeline(f, "{", indent=0)

        if isinstance(values, dict):
            for key, val in values.items():
                val_str = str(val).strip()
                if not val_str.endswith(";"):
                    val_str += ";"
                if key == "default":
                    self.writeline(f, val_str, indent=1)
                else:
                    self.writeline(f, f"{key} : {val_str}", indent=1)
        elif isinstance(values, list):
            for i, val in enumerate(values):
                val_str = str(val).strip()
                if not val_str.endswith(";"):
                    val_str += ";"
                self.writeline(f, f"{i} : {val_str}", indent=1)

        self.writeline(f, "}", indent=0)
        self.writeline(f, "", indent=0)