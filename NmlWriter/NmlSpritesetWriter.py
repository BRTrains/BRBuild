from .BaseNmlWriter import BaseNmlWriter


class NmlSpritesetWriter(BaseNmlWriter):
    """Writes `spriteset(...)` blocks for a variant's Spriteset objects.

    Each spriteset calls the exact NML template macro (e.g. `tmpl_train_6`, `tmpl_purchase`)
    it was matched against by `Templates.TemplateMatcher`, so the caller must supply that
    real template name rather than one guessed from vehicle type/articulation role.
    """

    def __init__(self):
        super().__init__()

    def write(self, f, spriteset, template_name, name=None):
        spriteset_name = name or spriteset.name

        self.writeline(f, f'spriteset({spriteset_name}, "{spriteset.file}") {{', indent=0)
        self.writeline(f, f"{template_name}({spriteset.x}, {spriteset.y})", indent=1)
        self.writeline(f, "}\n", indent=0)

