import logging
from pathlib import Path

from PropertyCalculation import VehicleType
from .BaseNmlWriter import BaseNmlWriter
from .NmlSpritesetWriter import NmlSpritesetWriter
from .NmlSwitchWriter import NmlSwitchWriter

logger = logging.getLogger(__name__)


class NmlVariantWriter(BaseNmlWriter):
    def __init__(self, variant_model, output_path):
        super().__init__()
        self.variant = variant_model
        self.switch_writer = NmlSwitchWriter()
        self.spriteset_writer = NmlSpritesetWriter()

        self.filepath = str(Path(output_path) / variant_model.nml_filename)

        # Ensure the output directory exists
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)

    def write(self):
        variant = self.variant

        with open(self.filepath, "w", encoding="utf-8") as f:
            self.write_item(f, variant)

        return self.filepath

    def write_item(self, f, variant):
        v_type = variant.vehicle_type
        feature = "FEAT_TRAINS"

        if isinstance(v_type, VehicleType):
            feature = v_type.nml_feature
        elif hasattr(v_type, "name"):
            v_name = v_type.name.upper()
            if v_name in ("TRAM", "ROADVEH"):
                feature = "FEAT_ROADVEHS"

        self.writeline(f, f"item ({feature}, {variant.identifier}) {{", indent=0)

        # NML Properties Block
        properties = getattr(variant, "properties", None)
        if properties and len(properties) > 0:
            self.writeline(f, "property {", indent=1)
            for prop_name, prop_val in properties.items():
                val_str = str(prop_val).strip()
                if not val_str.endswith(";"):
                    val_str += ";"
                self.writeline(f, f"{prop_name}: {val_str}", indent=2)
            self.writeline(f, "}", indent=1)

        # NML Graphics & Callbacks Block
        callbacks = getattr(variant, "callbacks", None)
        if callbacks and len(callbacks) > 0:
            self.writeline(f, "graphics {", indent=1)
            for cb_name, cb_target in callbacks.items():
                target_str = str(cb_target).strip()
                if not target_str.endswith(";"):
                    target_str += ";"
                self.writeline(f, f"{cb_name}: {target_str}", indent=2)
            self.writeline(f, "}", indent=1)

        self.writeline(f, "}\n", indent=0)