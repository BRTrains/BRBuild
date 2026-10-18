from PropertyCalculation.VehicleType import VehicleType
from PropertyCalculation.VehicleUsage import VehicleUsage


def disable_condition(base_type, output_type, usage, filters):
    """Return (feature, condition) for a configured cross-feature variant."""
    if not isinstance(base_type, VehicleType) or not isinstance(output_type, VehicleType):
        return None
    if base_type.nml_feature == output_type.nml_feature:
        return None

    feature = output_type.nml_feature
    rule = next((item for item in filters or [] if item.get("feature") == feature), None)
    if rule is None:
        return None

    parameter = str(rule["parameter"])
    minimums = rule.get("minimum", {}) or {}
    usages = usage if isinstance(usage, (list, tuple)) else [usage]
    thresholds = []
    for item in usages:
        threshold = minimums.get(item.name) if isinstance(item, VehicleUsage) else None
        if threshold is None:
            threshold = rule.get("default_minimum")
        if threshold is not None:
            thresholds.append(threshold)
    if not thresholds:
        return feature, f"{parameter} >= 0"
    return feature, f"{parameter} < {int(min(thresholds))}"
