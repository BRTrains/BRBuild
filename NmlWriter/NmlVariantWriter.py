import logging
from pathlib import Path

from PropertyCalculation import VehicleType
from Sprites.Spriteset import Spriteset
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
        """Return coloured purchase-list names without using the D0xx callback pool.

        OpenTTD 15's callback result 0x40F takes the GRF string ID from register 0x100.
        Putting string(...) inside STORE_TEMP makes nml allocate the text in its larger
        DCxx range; the callback text stack, when used, starts at register 0x101.
        """
        name_switch_name = getattr(variant, "name_callback_name", None)
        group_string = getattr(variant, "name_callback_string", None)
        nested_string = getattr(variant, "name_callback_nested_string", None)
        if not name_switch_name or not group_string or not nested_string:
            return

        feature = self._feature(variant)
        group_result = f"{name_switch_name}_group"
        nested_result = f"{name_switch_name}_nested"

        self.switch_writer.write_switch(
            f,
            feature,
            "SELF",
            group_result,
            f"[STORE_TEMP({group_string}, 0x100)]",
            {"default": "0x40F"},
        )
        self.switch_writer.write_switch(
            f,
            feature,
            "SELF",
            nested_result,
            f"[STORE_TEMP({nested_string}, 0x100)]",
            {"default": "0x40F"},
        )
        self.switch_writer.write_switch(
            f,
            feature,
            "SELF",
            f"{name_switch_name}_purchase",
            "getbits(extra_callback_info1, 0, 16)",
            {
                "0x20": group_result,
                "0x120": nested_result,
                "default": "CB_FAILED",
            },
        )
        self.switch_writer.write_switch(
            f,
            feature,
            "SELF",
            name_switch_name,
            "extra_callback_info1 & 0xFF",
            {"0x20": f"{name_switch_name}_purchase", "default": "CB_FAILED"},
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

        self._write_lighting(f, variant)

        length_switch_name = getattr(variant, "length_switch_name", None)
        lengths = getattr(variant, "sprite_lengths", None)
        if length_switch_name and lengths:
            values = {i: length for i, length in enumerate(lengths)}
            expression = f"position_in_articulated_veh % {len(lengths)}"
            self.switch_writer.write_switch(f, self._feature(variant), "SELF", length_switch_name, expression, values)

    def _transparent_spriteset(self, f, variant, base, template_name, transparent_path) -> str:
        """One transparent spriteset per vehicle and template, shared by every part that needs one.

        The sheet is uniform, so a single copy at (0, 0) serves all of a vehicle's parts and variants —
        it is the same eight empty views either way, and emitting one per part would add a spriteset to
        the GRF for every articulated part of every livery.
        """
        vehicle = variant.vehicle
        emitted = getattr(vehicle, "_lighting_transparent_spritesets", None)
        if emitted is None:
            emitted = {}
            setattr(vehicle, "_lighting_transparent_spritesets", emitted)

        name = f"spriteset_{vehicle.identifier}_transparent_{template_name}"
        if template_name not in emitted:
            blank = Spriteset(
                name=name,
                file=str(transparent_path),
                template=base.template,
                x=0,
                y=0,
            )
            self.spriteset_writer.write(f, blank, template_name, name=name)
            emitted[template_name] = name
        return emitted[template_name]

    def _write_lighting(self, f, variant):
        """Write the second sprite layer: the published drawing with the lamps of the other state.

        Layer 0 draws the vehicle as published; layer 1 draws the overlay, which holds the reciprocal
        lamp pixels and is transparent everywhere else. Layer 1 hands over the overlay while the
        vehicle is drawn turned around or the train is backing up — the XOR of the two, which is
        exactly when the published lamps sit at the wrong end — and nothing otherwise. Both stores
        also set the sprite-stack flag that makes OpenTTD resolve a second layer at all.
        """
        switch_name = getattr(variant, "lighting_switch_name", None)
        overlay_path = getattr(variant, "lighting_overlay_path", None)
        transparent_path = getattr(variant, "lighting_transparent_path", None)
        if not switch_name or not overlay_path or not transparent_path:
            return

        spritesets = variant.spritesets
        names = variant.spriteset_names
        template_names = variant.sprite_template_names
        detection = getattr(variant, "lighting_detection", None)
        lamp_rows = set(getattr(detection, "rows", set()) or set())
        feature = self._feature(variant)
        count = len(spritesets)

        def as_spriteset(path, base, name):
            return Spriteset(name=name, file=str(path), template=base.template, x=base.x, y=base.y)

        layers = []
        written = set()
        for i, (base, template_name, name) in enumerate(zip(spritesets, template_names, names)):
            # two parts of a formation can share a drawing (a repeated middle car), and a spriteset
            # name may only be defined once
            overlay_name = f"{name}_light"
            plain_name = f"{name}_no_light"
            has_lamps = base.y in lamp_rows
            if overlay_name not in written:
                self.spriteset_writer.write(
                    f, as_spriteset(overlay_path if has_lamps else transparent_path, base, overlay_name),
                    template_name, name=overlay_name,
                )
                written.add(overlay_name)
            if has_lamps:
                plain_name = self._transparent_spriteset(f, variant, base, template_name, transparent_path)
            layers.append((i, name, overlay_name, plain_name, has_lamps))

        for i, base_name, overlay_name, plain_name, has_lamps in layers:
            self.switch_writer.write_switch(
                f, feature, "SELF", f"{switch_name}_l0_{i}",
                "STORE_TEMP(CB_FLAG_MORE_SPRITES | PALETTE_USE_DEFAULT, 0x100)",
                {"default": base_name},
            )
            if has_lamps:
                self.switch_writer.write_switch(
                    f, feature, "SELF", f"{switch_name}_l1_{i}",
                    "STORE_TEMP(PALETTE_IDENTITY, 0x100)", {"default": overlay_name},
                )
                self.switch_writer.write_switch(
                    f, feature, "SELF", f"{switch_name}_n1_{i}",
                    "STORE_TEMP(PALETTE_IDENTITY, 0x100)", {"default": plain_name},
                )
                self.switch_writer.write_switch(
                    f, feature, "SELF", f"{switch_name}_pick_{i}",
                    "vehicle_is_flipped != train_is_driving_backwards",
                    {0: f"{switch_name}_n1_{i}", "default": f"{switch_name}_l1_{i}"},
                )
            else:
                # no lamps on this part: layer 1 is transparent in both states, so one spriteset does
                # for both branches (the overlay name already points at the transparent sheet)
                self.switch_writer.write_switch(
                    f, feature, "SELF", f"{switch_name}_l1_{i}",
                    "STORE_TEMP(PALETTE_IDENTITY, 0x100)", {"default": overlay_name},
                )

        picks = {
            i: (f"{switch_name}_pick_{i}" if has_lamps else f"{switch_name}_l1_{i}")
            for i, _name, _overlay, _plain, has_lamps in layers
        }
        self.switch_writer.write_switch(
            f, feature, "SELF", f"{switch_name}_base",
            f"position_in_articulated_veh % {count}",
            {i: f"{switch_name}_l0_{i}" for i in range(count)},
        )
        self.switch_writer.write_switch(
            f, feature, "SELF", f"{switch_name}_overlay",
            f"position_in_articulated_veh % {count}", picks,
        )
        self.switch_writer.write_switch(
            f, feature, "SELF", switch_name, "getbits(extra_callback_info1, 8, 8)",
            {0: f"{switch_name}_base", "default": f"{switch_name}_overlay"},
        )

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