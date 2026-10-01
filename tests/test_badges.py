from Badge import BadgeRegistry


def test_badge_paths_are_case_insensitive_for_nml_identity():
    registry = BadgeRegistry()
    registry.clear()
    registry.add_badge("Operator/LU")
    assert registry.add_badge("operator/LU") == "Operator/LU"
    assert registry.badges() == ["Operator", "Operator/LU"]
