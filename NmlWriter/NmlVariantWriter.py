import logging
from pathlib import Path

from Lang.StringRegistry import nml_str
from PropertyCalculation import VehicleType
from .NmlSpritesetWriter import NmlSpritesetWriter
from .NmlSwitchWriter import NmlSwitchWriter

logger = logging.getLogger(__name__)


class NmlVariantWriter:
    def __init__(self, variant_model, output_path):
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
        sprite_id = "SPRITE_ID_NEW_TRAIN"

        if isinstance(v_type, VehicleType):
            feature = v_type.nml_feature
            if v_type in (VehicleType.TRAM, VehicleType.ROADVEH):
                sprite_id = "SPRITE_ID_NEW_ROADVEH"
            elif v_type == VehicleType.SHIP:
                sprite_id = "SPRITE_ID_NEW_SHIP"
            elif v_type == VehicleType.PLANE:
                sprite_id = "SPRITE_ID_NEW_AIRCRAFT"
        elif hasattr(v_type, "name"):
            v_name = v_type.name.upper()
            if v_name in ("TRAM", "ROADVEH"):
                feature = "FEAT_ROADVEHS"
                sprite_id = "SPRITE_ID_NEW_ROADVEH"

        name_str = variant.name
        name_ref = nml_str(name_str, f"{variant.identifier}_name")

        f.write(f"item ({feature}, {variant.identifier}) {{\n")
        f.write("    property {\n")
        f.write(f"        name: {name_ref};\n")
        f.write(f"        sprite_id: {sprite_id};\n")
        f.write("        climates_available: ALL_CLIMATES;\n")

        intro_date = variant.get_attr("introduction_date")
        if intro_date is not None:
            if isinstance(intro_date, int) or (isinstance(intro_date, str) and intro_date.isdigit()):
                f.write(f"        introduction_date: date({intro_date}, 1, 1);\n")
            else:
                f.write(f"        introduction_date: {intro_date};\n")

        model_life = variant.get_attr("model_life")
        if model_life is not None:
            f.write(f"        model_life: {model_life};\n")

        vehicle_life = variant.get_attr("vehicle_life")
        if vehicle_life is not None:
            f.write(f"        vehicle_life: {vehicle_life};\n")

        speed = variant.get_attr("speed")
        if speed is not None:
            if isinstance(speed, float):
                f.write(f"        speed: {speed:.1f} mph;\n")
            else:
                f.write(f"        speed: {speed} mph;\n")

        power = variant.get_attr("power")
        if power is not None:
            f.write(f"        power: {power} hp;\n")

        weight = variant.get_attr("weight")
        if weight is not None:
            f.write(f"        weight: {weight} ton;\n")

        if hasattr(variant, "te_coefficient") and variant.te_coefficient is not None:
            f.write(f"        tractive_effort_coefficient: {variant.te_coefficient};\n")

        if hasattr(variant, "ad_coefficient") and variant.ad_coefficient is not None:
            f.write(f"        air_drag_coefficient: {variant.ad_coefficient};\n")

        length = variant.get_attr("length")
        if length is not None:
            f.write(f"        length: {length};\n")

        # NML 15.0 Badges array
        if getattr(variant, "badges", None):
            badges_formatted = ", ".join(f'"{b}"' for b in variant.badges)
            f.write(f"        badges: [{badges_formatted}];\n")

        f.write("    }\n")
        f.write("}\n\n")