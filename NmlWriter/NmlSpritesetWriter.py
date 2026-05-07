class NmlSpritesetWriter:
    def __init__(self):
        pass

    def write(self, f, sprite, variant):        
        if sprite.type == "purchase" or sprite.size == 0:
            template_name = "tmpl_purchase"
        elif isinstance(sprite.size, int):
            template_name = f"tmpl_{variant.vehicle_type_name.lower()}_{sprite.size}"
        
        self.writeline(f"spriteset({sprite.name}, \"{sprite.file}\") {{", f)
        self.writeline(f"{template_name}({sprite.x},{sprite.y})", f, 1)
        self.writeline("}\n", f)