from __future__ import \
    annotations  # Python is stupid and won't allow self-referential Badge parameters without either this or stupid "Badge" nonsense

import os


class Badge:
    def __init__(self, name, parent: Badge | None = None):
        self.parent = parent

        if not name:
            raise Exception("Badge doesn't have a name")

        # Short name (without parent prefixes), eg Third_Rail
        self.short_name = name  
        # Full hierarchical name eg power/delivery/Third_Rail
        self.name = self.set_name()
        # NML friendly name eg power_delivery_third_rail
        self.nml_name = self.name.replace("/","_").lower()
        # Readable name eg Third Rail
        self.friendly_name = name.replace("_", " ")
        # Sprite name eg sprite_badge_power_delivery_third_rail
        self.sprite_name = f"sprite_badge_{self.nml_name}"
        self.has_sprite = os.path.exists(f"grf/badges/{self.nml_name}.png")
        self.has_string = not self.name[0].islower()

    def set_name(self):
        if self.parent is not None:
            return self.parent.name + "/" + self.short_name
        return self.short_name
    
    def chain_contains(self, name):
        if self.name == name:
            return True
        if self.parent is not None:
            return self.parent.chain_contains(name)
        return False
        

    def __str__(self):
        return self.name
    