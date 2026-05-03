from enum import Enum

''' Enumeration for different fuel types, each with associated purchase and running cost multipliers. '''
class FuelType(Enum):
    STEAM = (
        1.00,   # purchase_multiplier
        1.00,   # running_multiplier
        "steam",
    )

    DIESEL = (
        0.57,
        0.50,
        "diesel",
    )

    ELECTRIC = (
        0.49,
        0.45,
        "electric",
    )

    BI_MODE = (
        0.69,
        0.40,
        "bi-mode",
    )

    TRI_MODE = (
        0.80,
        0.35,
        "tri-mode",
    )

    HYDROGEN = (
        0.66,
        0.48,
        "hydrogen",
    )

    BATTERY = (
        0.60,
        0.38,
        "battery",
    )


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
        FuelType,
        key=lambda f: f.purchase_multiplier,
    ):
        print(
            f"{fuel.name:<10} "
            f"purchase={fuel.purchase_multiplier:<4.2f} "
        )


def print_sorted_by_running_cost():
    print("Sorted by running cost:")
    print()

    for fuel in sorted(
        FuelType,
        key=lambda f: f.running_multiplier,
    ):
        print(
            f"{fuel.name:<10} "
            f"running={fuel.running_multiplier:<4.2f}"
        )


if __name__ == "__main__":
    print_sorted_by_purchase_cost()
    print()
    print_sorted_by_running_cost()