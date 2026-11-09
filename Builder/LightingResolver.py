"""Resolve and generate per-variant lighting overlays."""

import logging

from Sprites.LightingOverlay import LIGHTING_AUTO, LIGHTING_EXACT, LIGHTING_NONE, Part, boxes_of, pattern_of

logger = logging.getLogger(__name__)


class LightingResolver:
    """Coordinate lighting detection and sibling-pattern assumptions."""

    @staticmethod
    def _variant_parts(variant) -> list[Part]:
        """One `Part` per drawing of a variant, in consist order."""
        return [
            Part(row_y=sprite.y, template_name=template_name, boxes=boxes_of(sprite))
            for sprite, template_name in zip(variant.spritesets, variant.sprite_template_names)
        ]


    @staticmethod
    def _lighting_setting(variant) -> str:
        """A variant's `lighting` setting, resolved livery -> profile -> vehicle."""
        return str(variant.get_attr("lighting") or LIGHTING_AUTO).strip().lower()


    @staticmethod
    def _variant_label(variant) -> str:
        """A readable, greppable name for a variant, before its identifier is generated.

        The assumption pass runs before `Variant.process()`, so `variant.identifier` is still unset;
        the label is what the log and the cache record as the source of an assumption.
        """
        return f"{variant.vehicle.identifier} {variant.profile.identifier}/{variant.livery.name}"


    @staticmethod
    def _assume_lighting_patterns(variants, allocator, lightings) -> None:
        """Fill an unreadable livery's lamps from a sibling livery that draws the same pattern.

        Jon's rule (2026-09-25): where a unit's own artwork identifies lamps on at least one livery
        and says nothing about another, the silent one is assumed to match — one livery of a class
        shows the class's lamp geometry. A guess is worth making because a player who does not like
        it has to hand-author that vehicle's lamps anyway, so it costs nobody anything when it is
        right and is one override away when it is wrong.

        Deliberately narrow, on Jon's conditions:

        - only where **exactly one** trustworthy pattern was identified; two or more is ambiguity about which to
          use, so nothing is assumed and the rows keep their flags;
        - only within one spritesheet **and** one template, because a pattern is box-relative;
        - only from a pattern the detector did not flag, and only for a drawing it said *nothing*
          about: a row it actively rejected (over
          the cap, asymmetric, both end-on faces lit) keeps its flag for a human;
        - never for a variant set to `lighting: exact`, which is the manual override.

        Every assumption is labelled three ways so it is easy to find and confirm: the detection
        records the identifier it came from (`assumed_from`, which lands in the sheet's
        `.lightcache.json` with `"view_mapping": "assumed"`), the build logs a warning naming source
        and target, and the variant is marked in game by the lamps themselves being the guess.
        """
        identified: dict[tuple, dict[frozenset, str]] = {}
        waiting: dict[tuple, list] = {}

        for variant in variants:
            if getattr(variant, "is_livery_refit", False):
                continue
            if not variant.spritesets or LightingResolver._lighting_setting(variant) == LIGHTING_NONE:
                continue
            if LightingResolver._lighting_setting(variant) == LIGHTING_EXACT:
                continue  # the manual override: trust only what this vehicle's art shows

            sheet = str(allocator.sheet_for(variant.profile, variant.livery))
            parts = LightingResolver._variant_parts(variant)
            if len({part.row_y for part in parts}) != len(parts):
                continue  # drawings sharing a row cannot be told apart per part

            detection = variant.lighting_detection
            for index, part in enumerate(parts):
                key = (sheet, part.template_name, index)
                if detection is not None and detection.pixels:
                    pattern = pattern_of(detection, part)
                    if detection.assumed_from or detection.flags or not pattern:
                        # An assumption is not evidence for the next one; a row the detector flagged
                        # (over the cap, asymmetric) is too unreliable to set the pattern; and a part
                        # this drawing said nothing about must not register an empty pattern.
                        continue
                    identified.setdefault(key, {}).setdefault(pattern, LightingResolver._variant_label(variant))
                elif detection is None or not detection.flags:
                    waiting.setdefault(key, []).append((variant, index, parts))

        for key, targets in waiting.items():
            patterns = identified.get(key) or {}
            if len(patterns) != 1:
                continue
            pattern, source = next(iter(patterns.items()))
            sheet = key[0]
            lighting = lightings.get(sheet)
            if lighting is None:
                continue

            for variant, part_index, parts in targets:
                detection = lighting.assume_for(parts, part_index, pattern, source)
                if not detection.pixels:
                    continue
                flag = f"lamps assumed from '{source}' (same sheet and template): verify in game"
                if flag not in detection.flags:
                    detection.flags.append(flag)
                variant.lighting_detection = detection
                logger.warning(
                    f"Assumed the lighting pattern of '{source}' for "
                    f"'{LightingResolver._variant_label(variant)}': its own drawing showed no lamps. The sidecar "
                    f"beside the sheet records it as \"view_mapping\": \"assumed\"; set "
                    f"`lighting: exact` on that livery (or its profile or vehicle) to keep the "
                    f"artwork as drawn instead."
                )

