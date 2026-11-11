"""Public-facing views of compiled vehicle variants."""


def is_public_variant(variant) -> bool:
    """Return whether a compiled variant belongs in purchase lists and public metadata."""
    return not bool(getattr(variant, "hidden_articulated_part", False))


def public_variants(variants):
    """Keep registry-tracked implementation items out of public variant collections."""
    return [variant for variant in variants if is_public_variant(variant)]
