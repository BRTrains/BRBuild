import re
from pathlib import Path
from Badge import BadgeRegistry
from .BaseNmlWriter import BaseNmlWriter


class NmlBadgeWriter(BaseNmlWriter):
    """Writes NML badgetable and FEAT_BADGES item definitions with associated PNG spritesets."""

    def __init__(self, badge_dir: str = "Badge/images"):
        super().__init__()
        self.badge_dir = Path(badge_dir)

    def write_badgetable(self, f, badges: list[str]):
        if not badges:
            return

        self.writeline(f, "// Badges definition block", indent=0)
        self.writeline(f, "badgetable {", indent=0)
        for i, b in enumerate(badges):
            comma = "," if i < len(badges) - 1 else ""
            self.writeline(f, f'"{b}"{comma}', indent=1)
        self.writeline(f, "}\n", indent=0)

    def write_badge_items(self, f, badges: list[str]):
        if not badges:
            return

        self.writeline(f, "// Badges item definitions (FEAT_BADGES)", indent=0)
        for b in badges:
            clean_key = re.sub(r"[^A-Za-z0-9_]", "_", b.upper())
            nml_name = re.sub(r"[^a-z0-9_]", "_", b.lower())
            item_id = f"badge_{nml_name}"
            string_ref = f"string(STR_BADGE_{clean_key})"

            img_path = self._find_image(b, nml_name)

            if img_path:
                spriteset_id = f"spriteset_{item_id}"
                self.writeline(f, f'spriteset ({spriteset_id}, "{img_path}") {{', indent=0)
                self.writeline(f, "[0, 0, 16, 16, 0, 0]", indent=1)
                self.writeline(f, "}\n", indent=0)

                self.writeline(f, f"item (FEAT_BADGES, {item_id}) {{", indent=0)
                self.writeline(f, "property {", indent=1)
                self.writeline(f, f'label: "{b}";', indent=2)
                self.writeline(f, f"name: {string_ref};", indent=2)
                self.writeline(f, "}", indent=1)
                self.writeline(f, "graphics {", indent=1)
                self.writeline(f, f"default: {spriteset_id};", indent=2)
                self.writeline(f, "}", indent=1)
                self.writeline(f, "}\n", indent=0)
            else:
                self.writeline(f, f"item (FEAT_BADGES, {item_id}) {{", indent=0)
                self.writeline(f, "property {", indent=1)
                self.writeline(f, f'label: "{b}";', indent=2)
                self.writeline(f, f"name: {string_ref};", indent=2)
                self.writeline(f, "}", indent=1)
                self.writeline(f, "}\n", indent=0)

    def write_all(self, f):
        badges = BadgeRegistry().badges()
        if badges:
            self.write_badgetable(f, badges)
            self.write_badge_items(f, badges)

    def _find_image(self, b: str, nml_name: str) -> str | None:
        candidates = [
            self.badge_dir / f"{nml_name}.png",
            self.badge_dir / f"{b.replace('/', '_').lower()}.png",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None
