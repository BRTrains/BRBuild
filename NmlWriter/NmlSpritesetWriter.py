from .BaseNmlWriter import BaseNmlWriter


class NmlSpritesetWriter(BaseNmlWriter):
    """Writes `spriteset(...)` blocks for a variant's Spriteset objects.

    Each spriteset calls the exact NML template macro (e.g. `tmpl_train_6`, `tmpl_purchase`)
    it was matched against by `Templates.TemplateMatcher`, so the caller must supply that
    real template name rather than one guessed from vehicle type/articulation role.
    """

    def __init__(self, alignment_param_index=4):
        super().__init__()
        self.alignment_param_index = alignment_param_index

    def write_aligned(self, f, spriteset, template_name, name, switch_writer, feature="FEAT_TRAINS"):
        """Write Iron Horse and Generic variants, then select by the injected GRF parameter."""
        iron_name = f"{name}_iron_horse"
        generic_name = f"{name}_generic"
        self.write(f, spriteset, template_name, name=iron_name)
        self.write(f, spriteset, f"{template_name}_generic", name=generic_name)
        switch_writer.write_switch(
            f, feature, "SELF", name, f"param[{self.alignment_param_index}]", {0: generic_name, 1: iron_name}
        )

    def write(self, f, spriteset, template_name, name=None):
        spriteset_name = name or spriteset.name
        self.writeline(f, f'spriteset({spriteset_name}, "{spriteset.file}") {{', indent=0)
        self.writeline(f, f"{template_name}({spriteset.x}, {spriteset.y})", indent=1)
        self.writeline(f, "}\n", indent=0)

