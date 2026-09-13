from .BaseNmlWriter import BaseNmlWriter


class NmlSpritesetWriter(BaseNmlWriter):
    def __init__(self):
        super().__init__()

    def write(self, f, sprite, variant):
        if getattr(sprite, "type", None) == "purchase" or getattr(sprite, "size", 0) == 0:
            template_name = "tmpl_purchase"
        elif isinstance(sprite.size, int):
            v_type = variant.vehicle_type
            v_type_str = v_type.name.lower() if hasattr(v_type, "name") else str(v_type).lower()
            template_name = f"tmpl_{v_type_str}_{sprite.size}"
        else:
            template_name = "tmpl_purchase"

        self.writeline(f, f'spriteset({sprite.name}, "{sprite.file}") {{', indent=0)
        self.writeline(f, f"{template_name}({sprite.x}, {sprite.y})", indent=1)
        self.writeline(f, "}\n", indent=0)