import re
import logging
from Lang.StringRegistry import nml_str

logger = logging.getLogger(__name__)

def format_badge_label(badge_path: str) -> str:
    """Dynamically formats a badge path segment into a human-readable title string."""
    segment = badge_path.split("/")[-1]

    # Specific hyphenated terms
    hyphenated = {
        "bi_mode": "Bi-Mode",
        "tri_mode": "Tri-Mode",
        "multi_mode": "Multi-Mode",
        "diesel_hydraulic": "Diesel-Hydraulic",
        "diesel_electric": "Diesel-Electric",
        "diesel_mechanical": "Diesel-Mechanical",
    }
    if segment.lower() in hyphenated:
        return hyphenated[segment.lower()]

    words = segment.split("_")
    parts = []
    for w in words:
        if w.isupper() and len(w) > 1:
            parts.append(w)
        else:
            parts.append(w.capitalize())

    return " ".join(parts)


class BadgeRegistry:
    """Registry of badges seen so far.

    A badge can be a top-level name or a slash-delimited path of arbitrary depth.
    When a nested badge is added, all intermediate category levels are also created.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._badges = set()
            cls._instance = instance
            logger.debug("BadgeRegistry instance created")
        return cls._instance

    def __init__(self):
        pass

    def add_badge(self, badge_path):
        """Add a badge path, creating parent categories as needed."""
        if not isinstance(badge_path, str):
            raise TypeError("badge_path must be a string")

        normalized = badge_path.strip()
        if not normalized:
            raise ValueError("badge_path must not be empty")

        parts = normalized.strip("/").split("/")
        if any(not part for part in parts):
            raise ValueError("badge_path must not contain empty segments")

        accumulated = []
        for part in parts:
            accumulated.append(part)
            badge = "/".join(accumulated)
            existing = next(
                (candidate for candidate in self._badges if candidate.casefold() == badge.casefold()),
                None,
            )
            if existing is None:
                self._badges.add(badge)
                self._register_string_for_badge(badge)
                existing = badge
                logger.debug(f"Badge added: {badge}")
            badge = existing
        return badge

    def _register_string_for_badge(self, badge_path: str):
        clean_key = re.sub(r"[^A-Za-z0-9_]", "_", badge_path.upper())
        string_name = f"STR_BADGE_{clean_key}"
        text = format_badge_label(badge_path)
        nml_str(text, string_name)

    def clear(self):
        """Clear all registered badges."""
        self._badges.clear()

    def has_badge(self, badge_path):
        return badge_path in self._badges

    def badges(self):
        return sorted(self._badges)

    def __contains__(self, badge_path):
        return self.has_badge(badge_path)

    def __iter__(self):
        return iter(self.badges())
    
    def __repr__(self):
        return f"BadgeRegistry({self.badges()})"
    
    def write_badges_to_file(self, filename="debug/badges.txt"):
        """Write the badges to a file in a plain text format """
        with open(filename, 'w') as f:
            if filename.endswith('.md'):
                for badge in self.badges():
                    f.write(f"- {badge}\n")
            else:
                for badge in self.badges():
                    f.write(f"{badge}\n")


if __name__ == "__main__":
    registry = BadgeRegistry()
    registry.add_badge("foo/bar")

    assert registry.has_badge("foo/bar")
    assert "foo" in registry
    assert "foo/bar" in registry
    assert registry.badges() == ["foo", "foo/bar"]
    assert "foo/bat" not in registry
    assert "bat" not in registry

    print(registry)
    print("BadgeRegistry self-test passed")