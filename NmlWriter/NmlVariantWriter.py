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
            self.write_sprites(f, variant)
            self.write_item(f, variant)

        return self.filepath

    def write_sprites(self, f, variant):
        """Write the generated switches and sprites for this variant."""
        self._write_articulated_switch(f, variant)
        self._write_name_switches(f, variant)
        self._write_spritesets(f, variant)

    def _write_articulated_switch(self, f, variant):
        articulated_switch_name = getattr(variant, "articulated_switch_name", None)
        articulated_count = getattr(variant, "articulated_count", None)
        if articulated_switch_name and articulated_count is not None:
            articulated_range = (
                "1" if articulated_count == 2 else f"1..{articulated_count - 1}"
            )
            values = {
                articulated_range: variant.identifier,
                "default": "CB_RESULT_NO_MORE_ARTICULATED_PARTS",
            }
            self.switch_writer.write_switch(
                f, self._feature(variant), "SELF", articulated_switch_name, "extra_callback_info1", values
            )

    def _write_name_switches(self, f, variant):
        name_switch_name = getattr(variant, "name_callback_name", None)
        name_switch_string = getattr(variant, "name_callback_string", None)
        if name_switch_name and name_switch_string:
            # Callback 0x161 is called with extra_callback_info1 bit 0..7 as
            # the GUI context and bits 8..15 as purchase-list indentation.
            # A single 0x20 branch would therefore return the root/group name
            # for every item in the purchase list, including its children.
            purchase_name_switch = f"{name_switch_name}_purchase"
            base_name_string = (getattr(variant, "properties", None) or {}).get("name", "CB_FAILED")
            profile_id = str(getattr(getattr(variant, "profile", None), "identifier", "")).replace("_", "").strip().lower()
            eligible_liveries = [
                livery
                for livery in getattr(getattr(variant, "vehicle", None), "liveries", [])
                if not getattr(livery, "profiles", None)
                or any(str(livery_profile).replace("_", "").strip().lower() == profile_id for livery_profile in livery.profiles)
            ]
            grouped_name_string = getattr(variant, "name_callback_string", name_switch_string)
            single_livery_name_string = getattr(variant, "name_callback_single_livery_string", base_name_string)
            root_name_string = single_livery_name_string if len(eligible_liveries) <= 1 else grouped_name_string
            self.switch_writer.write_switch(
                f,
                self._feature(variant),
                "SELF",
                purchase_name_switch,
                "getbits(extra_callback_info1, 0, 16)",
                {
                    "0x20": root_name_string,
                    "0x120": base_name_string,
                    "default": base_name_string,
                },
            )
            self.switch_writer.write_switch(
                f,
                self._feature(variant),
                "SELF",
                name_switch_name,
                "extra_callback_info1 & 0xFF",
                {"0x20": purchase_name_switch, "default": "CB_FAILED"},
            )

    def _write_spritesets(self, f, variant):
        spritesets = getattr(variant, "spritesets", None)
        names = getattr(variant, "spriteset_names", None)
        template_names = getattr(variant, "sprite_template_names", None)
        if not spritesets or not names or not template_names:
            return

        if variant.purchase_spriteset is not None and variant.purchase_template_name is not None:
            self.spriteset_writer.write(
                f, variant.purchase_spriteset, variant.purchase_template_name, name=variant.purchase_spriteset_name
            )

        written_names = set()
        for spriteset, template_name, name in zip(spritesets, template_names, names):
            if name in written_names:
                continue
            self.spriteset_writer.write(f, spriteset, template_name, name=name)
            written_names.add(name)

        switch_name = getattr(variant, "sprite_switch_name", None)
        if switch_name:
            values = {i: name for i, name in enumerate(names)}
            expression = f"position_in_articulated_veh % {len(spritesets)}"
            self.switch_writer.write_switch(f, self._feature(variant), "SELF", switch_name, expression, values)

        length_switch_name = getattr(variant, "length_switch_name", None)
        lengths = getattr(variant, "sprite_lengths", None)
        if length_switch_name and lengths:
            values = {i: length for i, length in enumerate(lengths)}
            expression = f"position_in_articulated_veh % {len(lengths)}"
            self.switch_writer.write_switch(f, self._feature(variant), "SELF", length_switch_name, expression, values)

    @staticmethod
    def _feature(variant):
        v_type = variant.vehicle_type
        feature = "FEAT_TRAINS"

        if isinstance(v_type, VehicleType):
            feature = v_type.nml_feature
        elif hasattr(v_type, "name"):
            v_name = v_type.name.upper()
            if v_name in ("TRAM", "ROADVEH"):
                feature = "FEAT_ROADVEHS"

        return feature

    def write_item(self, f, variant):
        feature = self._feature(variant)
        sprite_id = getattr(variant, "sprite_id", None)
        item_header = f"item ({feature}, {variant.identifier}"
        if sprite_id is not None:
            item_header += f", {sprite_id}"
        item_header += ") {"

        self.writeline(f, item_header, indent=0)

        # NML Properties Block
        properties = dict(getattr(variant, "properties", None) or {})
        if sprite_id is not None:
            properties["sprite_id"] = self._sprite_id_property(feature)
        if properties and len(properties) > 0:
            properties = sorted(properties.items())

            self.writeline(f, "property {", indent=1)
            for prop_name, prop_val in properties:
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

    @staticmethod
    def _sprite_id_property(feature):
        return {
            "FEAT_TRAINS": "SPRITE_ID_NEW_TRAIN",
            "FEAT_ROADVEHS": "SPRITE_ID_NEW_ROADVEH",
            "FEAT_SHIPS": "SPRITE_ID_NEW_SHIP",
            "FEAT_AIRCRAFT": "SPRITE_ID_NEW_AIRCRAFT",
        }[feature]