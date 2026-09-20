from enum import Enum

''' Enumeration for different fuel types, each with associated purchase and running cost multipliers.

The multipliers are BRBuild conventions, not OpenTTD values: they only set the shape of
the cost model relative to each other, and can be refined freely.

Some of these fuels are not OpenTTD concepts (hydrogen, battery, gas turbine). They are
approximated with the mechanics described in `FuelDefaults` and `PowerTypeClassifier`:
a self-powered type behaves as a diesel for track purposes and needs no catenary.
'''
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
        0.56,
        "hydrogen",
    )

    BATTERY = (
        0.60,
        0.38,
        "battery",
    )

    # Gas turbine (the APT-E): a one-off specialist machine, so dearer to buy than a
    # diesel of the same output and appreciably thirstier to run, but cheaper than steam.
    GAS_TURBINE = (
        0.62,
        0.62,
        "gas_turbine",
    )

    UNPOWERED = (
        0.3,
        0.2,
        "unpowered",
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