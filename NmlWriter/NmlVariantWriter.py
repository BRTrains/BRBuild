import logging
logger = logging.getLogger(__name__)
from pathlib import Path

from .NmlSwitchWriter import NmlSwitchWriter
from .NmlSpritesetWriter import NmlSpritesetWriter


class NmlVariantWriter:
    def __init__(self, variant_model, output_path):

        self.variant = variant_model
        self.switch_writer = NmlSwitchWriter()
        self.spriteset_writer = NmlSpritesetWriter()

        self.filepath = output_path + variant_model.nml_filename

        # Ensure the output directory exists
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)

    def write(self):        
        variant = self.variant

        with open(self.filepath, 'w') as f:
            # if getattr(variant.sprite_handler, "purchase_sprite", None) is not None:
            #     self.spriteset_writer.write_spriteset(f, variant.sprite_handler.purchase_sprite, variant)

            # for sprite in variant.sprite_handler.spritesets:
            #     # Only write each spriteset once
            #     if not any(s.name == sprite.name for s in self.written_spritesets):
            #         self.spriteset_writer.write_spriteset(f, sprite, variant)
            #         self.written_spritesets.append(sprite)

            # for switch in variant.switches + variant.sprite_handler.switches:
            #     self.switch_writer.write_switch(
            #         f,
            #         switch["vehicle_type"],
            #         switch["target_type"],
            #         switch["name"] if switch["name"].lower().startswith("sw_") else f"sw_{switch['name']}",
            #         switch["expression"],
            #         switch["values"]
            #     )

            self.write_item(f, variant)

            return self.filepath

    def write_item(self, f, variant):
        # TODO Implement writing the main item block for the variant
        pass