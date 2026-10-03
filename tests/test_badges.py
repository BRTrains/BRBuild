from Badge import BadgeRegistry
from Badge.BadgeRegistry import format_badge_label


def test_badge_paths_are_case_insensitive_for_nml_identity():
    registry = BadgeRegistry()
    registry.clear()
    registry.add_badge("Operator/LU")
    assert registry.add_badge("operator/LU") == "Operator/LU"
    assert registry.badges() == ["Operator", "Operator/LU"]


def test_badge_labels_preserve_title_case_and_acronyms():
    assert format_badge_label("operator/London Underground") == "London Underground"
    assert format_badge_label("operator/Docklands Light Railway") == "Docklands Light Railway"
    assert format_badge_label("operator/LU") == "LU"
