from enum import Enum


class WagonType(Enum):
    FREIGHT_WAGON = (0.25, 0.10, "freight_wagon")
    TANK_WAGON = (0.35, 0.15, "tank_wagon")
    REFRIGERATED_WAGON = (0.45, 0.20, "refrigerated_wagon")

    COACH = (0.55, 0.30, "coach")
    SLEEPER_COACH = (0.70, 0.35, "sleeper_coach")

    DRIVING_VAN_TRAILER = (0.75, 0.40, "dvt")

    def __init__(
        self,
        purchase_multiplier: float,
        running_multiplier: float,
        label: str,
    ):
        self.purchase_multiplier = purchase_multiplier
        self.running_multiplier = running_multiplier
        self.label = label

def print_sorted_by_purchase_cost():
    print("Sorted by purchase cost:")
    print()

    for fuel in sorted(
        WagonType,
        key=lambda f: f.purchase_multiplier,
    ):
        print(
            f"{fuel.name:<20} "
            f"purchase={fuel.purchase_multiplier:<4.2f} "
        )


def print_sorted_by_running_cost():
    print("Sorted by running cost:")
    print()

    for fuel in sorted(
        WagonType,
        key=lambda f: f.running_multiplier,
    ):
        print(
            f"{fuel.name:<20} "
            f"running={fuel.running_multiplier:<4.2f}"
        )


if __name__ == "__main__":
    print_sorted_by_purchase_cost()
    print()
    print_sorted_by_running_cost()