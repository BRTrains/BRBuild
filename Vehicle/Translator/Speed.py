"""Speeds as the GRF's own speed field takes them.

Authors write speeds in mph, and NML converts an ``mph`` unit literal itself when it is
a *property* value: ``speed: 140 mph`` compiles to the field value 224. A graphics
callback is an expression instead, where a unit literal is a syntax error, and nmlc does
not convert a callback result at all — the number is written verbatim. OpenTTD reads
both through the same field (``GetVehicleProperty`` returns the callback result, or the
property when the callback fails), so a callback returning the authored mph figure makes
the vehicle read 1.6x slower than the same figure written as a property.

The field's unit is OpenTTD's "km/h-ish" speed unit, and nmlc's mph conversion for a
train is exactly 1.6 per mph: its ``unit_conversion`` (5000, 1397) over the mph unit's
(3125, 1397) cancels to 8/5. A speed that has to go into an expression is therefore
converted here, and the YAML keeps quoting mph.

The conversion is not quite ``round(mph * 1.6)``. nmlc adjusts the property value so
that OpenTTD reads the authored figure back, and where rounding leaves a choice the two
neighbouring values differ: 62 mph is 100, not the 99 that ``62 * 1.6`` rounds to,
because the game reads 99 back as 61 mph. This module mirrors that adjustment, so a
callback value is identical to the property value for the same mph figure.
"""

from __future__ import annotations

MPH_TO_SPEED_FIELD = (8, 5)
"""Numerator and denominator of nmlc's mph-to-speed-field conversion for a train."""

SPEED_FIELD_MPH = (10, 16)
"""OpenTTD's own speed field to mph conversion (``field * 10 / 16``), truncated."""


def displayed_mph(speed_field_value: int) -> int:
    """The mph OpenTTD shows for a speed field value."""
    numerator, denominator = SPEED_FIELD_MPH
    return (numerator * speed_field_value) // denominator


def speed_field(mph: float) -> int:
    """The number a GRF speed field takes for an mph value.

    Use this for any speed that is written into an NML expression — in practice the
    design/service selector callback. A property value keeps its ``mph`` literal and is
    converted by nmlc: this function is written to produce the same number nmlc does, so
    the two agree whichever setting the parameter selects.
    """
    numerator, denominator = MPH_TO_SPEED_FIELD
    field = int(float(mph) * numerator / denominator + 0.5)

    # nmlc adjusts the rounded value to whichever neighbour the game reads back as the
    # authored figure, then keeps the closer of the pair (nml/actions/action0.py).
    while displayed_mph(field) > mph:
        field -= 1
    lower = field
    while displayed_mph(field) < mph:
        field += 1
    higher = field

    if abs(displayed_mph(lower) - mph) < abs(displayed_mph(higher) - mph):
        return lower
    return higher
