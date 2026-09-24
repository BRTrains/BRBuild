import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from Sprites.LightingOverlay import (
    Detection,
    LightingOverlayCache,
    Part,
    RULES_VERSION,
    TRAILING_LAMP_LIT,
    VehicleLighting,
    boxes_of,
    detect_for_parts,
    detect_in_row,
    mirror_symmetric,
    signature,
)
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.BoundingBox import BoundingBox
from Templates.Template import Template
from Templates.TemplateDefinition import TemplateDefinition
from Templates.TemplateType import TemplateType

#: The view boxes of tmpl_train_8_old, so coordinates in the tests are the real ones.
BOXES = (
    (0, 0, 8, 24),
    (9, 0, 21, 18),
    (31, 0, 32, 12),
    (64, 0, 21, 18),
    (86, 0, 8, 24),
    (95, 0, 21, 18),
    (117, 0, 32, 12),
    (150, 0, 21, 18),
)
ROW_PITCH = 25
SHEET_SIZE = (171, 4 * ROW_PITCH)

WHITE = 0x0F
PALE_YELLOW = 0x45
PALE_GREY = 0x0D
RED = 0xB7
GREY = 0x03
TRANSPARENT = 0x00


def _palette():
    palette = []
    for index in range(256):
        palette.extend([index, index, index])
    palette[WHITE * 3:WHITE * 3 + 3] = [252, 252, 252]
    palette[RED * 3:RED * 3 + 3] = [224, 0, 0]
    palette[PALE_GREY * 3:PALE_GREY * 3 + 3] = [216, 216, 216]
    palette[PALE_YELLOW * 3:PALE_YELLOW * 3 + 3] = [252, 252, 192]
    return palette


def _sheet(path: Path, rows: dict[int, dict[tuple[int, int], int]]):
    """Draw a sheet: for each row y, a mapping of absolute (x, y) -> palette index."""
    image = Image.new("P", SHEET_SIZE, GREY)
    image.putpalette(_palette())
    for row_y, pixels in rows.items():
        for y in range(row_y, row_y + ROW_PITCH):
            for x in range(SHEET_SIZE[0]):
                image.putpixel((x, y), TRANSPARENT)
        for (x, y), value in pixels.items():
            image.putpixel((x, y), value)
    image.save(path)
    return path


def _parts(*rows: int, template: str = "tmpl_train_8_old"):
    return [Part(row_y=row, template_name=template, boxes=tuple(BOXES)) for row in rows]


def _definition(name="tmpl_train_8_old", length=8, boxes=BOXES):
    return TemplateDefinition(
        name=name,
        template_type=TemplateType.VEHICLE,
        vehicle_type="train",
        length=length,
        bounding_boxes=[
            BoundingBox(left, top, width, height, 0, 0, []) for left, top, width, height in boxes
        ],
    )


class LampDetectionTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.sheet = self.root / "sheet.png"

    def tearDown(self):
        self._folder.cleanup()

    def _detect_two_rows(self, front: dict, rear: dict) -> Detection:
        _sheet(self.sheet, {0: front, ROW_PITCH: rear})
        image = Image.open(self.sheet).convert("P")
        return detect_for_parts(image, _parts(0, ROW_PITCH))

    def test_end_on_pair_between_two_drawings(self):
        # the leading drawing carries the white lamps, the trailing drawing the red ones
        detection = self._detect_two_rows(
            {(86 + 1, 20): WHITE, (86 + 6, 20): WHITE},
            {(0 + 1, ROW_PITCH + 20): RED, (0 + 6, ROW_PITCH + 20): RED},
        )
        self.assertEqual(detection.pairs, 2)
        self.assertEqual(detection.flags, [])
        # the leading drawing's pixels take the trailing drawing's value, and the other way round
        self.assertEqual(detection.pixels[(87, 20)], RED)
        self.assertEqual(detection.pixels[(92, 20)], RED)
        self.assertEqual(detection.pixels[(1, ROW_PITCH + 20)], WHITE)
        self.assertEqual(detection.pixels[(6, ROW_PITCH + 20)], WHITE)

    def test_white_that_stays_white_is_not_a_lamp(self):
        detection = self._detect_two_rows(
            {(86 + 1, 20): WHITE, (86 + 6, 20): WHITE},
            {(0 + 1, ROW_PITCH + 20): WHITE, (0 + 6, ROW_PITCH + 20): WHITE},
        )
        self.assertEqual(detection.pairs, 0)
        self.assertEqual(detection.pixels, {})
        self.assertGreaterEqual(detection.rejected, 2)

    def test_lamp_going_to_a_dimmer_white_is_not_a_lamp(self):
        # 0F -> 0D is still white, so it has not changed state
        detection = self._detect_two_rows(
            {(86 + 1, 20): WHITE},
            {(0 + 1, ROW_PITCH + 20): PALE_GREY},
        )
        self.assertEqual(detection.pairs, 0)

    def test_nothing_drawn_on_the_counterpart_is_flagged(self):
        detection = self._detect_two_rows({(86 + 1, 20): WHITE}, {})
        self.assertEqual(detection.pairs, 0)
        self.assertTrue(any("transparent counterpart" in flag for flag in detection.flags))

    def test_asymmetric_end_on_lamps_are_flagged(self):
        detection = self._detect_two_rows(
            {(86 + 1, 20): WHITE},  # a single lamp, no mirror partner, away from the centreline
            {(0 + 1, ROW_PITCH + 20): RED},
        )
        self.assertEqual(detection.pairs, 0)
        self.assertTrue(any("mirror-symmetric" in flag for flag in detection.flags))

    def test_centre_repeater_pixel_is_allowed(self):
        detection = self._detect_two_rows(
            {(86 + 3, 16): WHITE},  # a lone centre pixel, either side of dead centre
            {(0 + 3, ROW_PITCH + 16): RED},
        )
        self.assertEqual(detection.pairs, 1)
        self.assertEqual(detection.flags, [])

    def test_view_over_the_cap_is_flagged(self):
        front = {(86 + x, 20): WHITE for x in range(7)}
        rear = {(0 + x, ROW_PITCH + 20): RED for x in range(7)}
        detection = self._detect_two_rows(front, rear)
        self.assertEqual(detection.pairs, 0)
        self.assertTrue(any("cap" in flag for flag in detection.flags))

    def test_single_unit_pairs_its_own_views(self):
        # a locomotive drawing holds both its nose view and its rear view
        _sheet(
            self.sheet,
            {0: {(86 + 1, 20): WHITE, (86 + 6, 20): WHITE, (0 + 1, 20): RED, (0 + 6, 20): RED}},
        )
        image = Image.open(self.sheet).convert("P")
        detection = detect_for_parts(image, _parts(0))
        self.assertEqual(detection.pairs, 2)
        self.assertEqual(detection.pixels[(87, 20)], RED)
        self.assertEqual(detection.pixels[(1, 20)], WHITE)
        self.assertEqual(detection.view_mapping, "same x")

    def test_only_the_brightest_shade_of_a_cluster_is_the_lamp(self):
        _sheet(
            self.sheet,
            {0: {(86 + 1, 20): WHITE, (86 + 1, 21): PALE_YELLOW, (0 + 1, 20): RED, (0 + 1, 21): GREY}},
        )
        image = Image.open(self.sheet).convert("P")
        detection = detect_in_row(image, 0, BOXES)
        # the pale yellow next to the lamp is not treated as a lamp of its own
        self.assertNotIn((87, 21), detection.pixels)

    def test_mirror_symmetric_accepts_a_mirrored_pair_and_a_centre_pixel(self):
        self.assertTrue(mirror_symmetric([(1, 20, 0, 0), (6, 20, 0, 0)], 8))
        self.assertTrue(mirror_symmetric([(3, 16, 0, 0)], 8))
        self.assertFalse(mirror_symmetric([(1, 20, 0, 0)], 8))

    def test_loco_and_tender_rows_are_handled_separately(self):
        # row 0 is the locomotive (it has lamps in its own views), row 25 the tender (it has none)
        _sheet(
            self.sheet,
            {0: {(86 + 1, 20): WHITE, (86 + 6, 20): WHITE, (0 + 1, 20): RED, (0 + 6, 20): RED},
             ROW_PITCH: {}},
        )
        image = Image.open(self.sheet).convert("P")
        detection = detect_for_parts(
            image,
            [
                Part(row_y=0, template_name="tmpl_train_8_old", boxes=tuple(BOXES)),
                Part(row_y=ROW_PITCH, template_name="tmpl_train_4", boxes=tuple(BOXES)),
            ],
        )
        self.assertEqual(detection.pairs, 2)

    def test_spriteset_boxes_come_from_its_template(self):
        sprites = [
            Sprite(left_x=left, upper_y=top, width=width, height=height, offset_x=0, offset_y=0)
            for left, top, width, height in BOXES
        ]
        spriteset = Spriteset(
            name="spriteset_y0", file="sheet.png", template=Template(name="row_0", sprites=sprites), x=0, y=0
        )
        self.assertEqual(boxes_of(spriteset), tuple(BOXES))

    def test_signature_changes_with_the_pairings(self):
        self.assertNotEqual(signature(_parts(0, ROW_PITCH)), signature(_parts(0, 2 * ROW_PITCH)))


class LightingCacheTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.sheet = _sheet(self.root / "sheet.png", {0: {(86 + 1, 20): WHITE, (0 + 1, 20): RED}})
        self.palette = list(_palette())

    def tearDown(self):
        self._folder.cleanup()

    def _cache(self):
        return LightingOverlayCache(self.sheet, self.palette, [_definition()])

    def _detections(self):
        detection = Detection(pixels={(87, 20): RED}, pairs=1)
        return {signature(_parts(0)): detection}

    def test_round_trip(self):
        self._cache().store(self._detections())
        loaded = self._cache().load()
        self.assertEqual(len(loaded), 1)
        detection = next(iter(loaded.values()))
        self.assertEqual(detection.pixels, {(87, 20): RED})
        self.assertEqual(detection.pairs, 1)

    def test_missing_cache_is_a_miss(self):
        self.assertEqual(self._cache().load(), {})

    def test_invalidated_by_a_changed_sheet(self):
        self._cache().store(self._detections())
        _sheet(self.sheet, {0: {(86 + 2, 20): WHITE, (0 + 1, 20): RED}})
        self.assertEqual(self._cache().load(), {})

    def test_invalidated_by_a_changed_palette(self):
        self._cache().store(self._detections())
        palette = list(_palette())
        palette[WHITE * 3:WHITE * 3 + 3] = [250, 250, 250]
        self.assertEqual(LightingOverlayCache(self.sheet, palette, [_definition()]).load(), {})

    def test_invalidated_by_changed_template_geometry(self):
        self._cache().store(self._detections())
        changed = [(0, 0, 8, 23), *BOXES[1:]]
        self.assertEqual(LightingOverlayCache(self.sheet, self.palette, [_definition(boxes=changed)]).load(), {})

    def test_invalidated_by_a_rules_version_bump(self):
        self._cache().store(self._detections())
        with patch("Sprites.LightingOverlay.RULES_VERSION", RULES_VERSION + 1):
            self.assertEqual(self._cache().load(), {})


class TrailingOnlyLampTests(unittest.TestCase):
    """The rule for a driving vehicle that draws its lamps only in the trailing state.

    A DVT's cab faces away from the train, so its art carries a red pair on the end-on face and no
    white counterpart anywhere: nothing for the pair-based rule to find. The trailing rule accepts
    that pair for a vehicle the caller says is a driving car (`has_cab`) and paints it white.
    """

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.sheet = self.root / "sheet.png"

    def tearDown(self):
        self._folder.cleanup()

    def _detect(self, pixels: dict, trailing_only: bool) -> Detection:
        _sheet(self.sheet, {0: pixels})
        image = Image.open(self.sheet).convert("P")
        return detect_for_parts(image, _parts(0), trailing_only_fallback=trailing_only)

    def test_a_red_pair_is_found_and_painted_white_for_a_driving_car(self):
        detection = self._detect(
            {(0 + 1, 20): RED, (0 + 6, 20): RED}, trailing_only=True
        )

        self.assertEqual(detection.pixels, {(1, 20): TRAILING_LAMP_LIT, (6, 20): TRAILING_LAMP_LIT})
        self.assertEqual(detection.rows, {0})
        self.assertEqual(detection.view_mapping, "trailing only")
        self.assertEqual(detection.flags, [])

    def test_the_rule_stays_off_without_the_driving_car_flag(self):
        detection = self._detect({(0 + 1, 20): RED, (0 + 6, 20): RED}, trailing_only=False)

        self.assertEqual(detection.pixels, {})
        self.assertEqual(detection.pairs, 0)

    def test_the_same_lamps_are_flipped_in_the_diagonal_and_side_views(self):
        # A DVT draws its tail lamps in three views (N and both rear diagonals) and sometimes
        # side-on too: the diagonal pair mirrors across the box width, the side pair likewise.
        # Without this the lamps stayed red on diagonal track, which is most of what a player sees.
        detection = self._detect(
            {
                (0 + 2, 21): RED,
                (0 + 5, 21): RED,  # end-on pair, mirrored within the 8-wide N box
                (9 + 1, 10): RED,
                (150 + 19, 10): RED,  # a lamp in NE and its mirror in NW (21-wide boxes)
                (31 + 3, 8): RED,
                (117 + 28, 8): RED,  # side-on, mirrored between the 32-wide E and W boxes
            },
            trailing_only=True,
        )

        self.assertEqual(
            detection.pixels,
            {
                (2, 21): TRAILING_LAMP_LIT,
                (5, 21): TRAILING_LAMP_LIT,
                (10, 10): TRAILING_LAMP_LIT,
                (169, 10): TRAILING_LAMP_LIT,
                (34, 8): TRAILING_LAMP_LIT,
                (145, 8): TRAILING_LAMP_LIT,
            },
        )

    def test_a_livery_dash_without_a_mirror_partner_is_left_alone(self):
        detection = self._detect(
            {
                (0 + 2, 21): RED,
                (0 + 5, 21): RED,
                (9 + 5, 5): RED,  # a dash in NE whose mirror (15,5) is not drawn in NW
            },
            trailing_only=True,
        )

        self.assertEqual(
            detection.pixels, {(2, 21): TRAILING_LAMP_LIT, (5, 21): TRAILING_LAMP_LIT}
        )

    def test_diagonal_lamps_alone_are_enough_when_the_end_on_pair_is_unreadable(self):
        # The Mk4 DVT's Virgin East Coast row: its livery band runs through the end-on pair, so only
        # the mirror pair in the diagonals identifies the lamps - and those are the views a train on
        # diagonal track is drawn in, so they must be flipped.
        detection = self._detect({(9 + 1, 10): RED, (150 + 19, 10): RED}, trailing_only=True)

        self.assertEqual(
            detection.pixels, {(10, 10): TRAILING_LAMP_LIT, (169, 10): TRAILING_LAMP_LIT}
        )

    def test_a_livery_stroke_is_not_a_lamp(self):
        # eleven reds in a diagonal run: a livery stripe, which no lamp cluster ever is
        stroke = {(0 + 1 + step, 4 + step): RED for step in range(7)}
        detection = self._detect(stroke, trailing_only=True)

        self.assertEqual(detection.pixels, {})

    def test_an_asymmetric_red_pixel_is_not_a_lamp(self):
        detection = self._detect({(0 + 1, 20): RED}, trailing_only=True)

        self.assertEqual(detection.pixels, {})
        self.assertTrue(any("mirror-symmetric" in flag for flag in detection.flags))

    def test_lamps_on_both_end_on_faces_are_left_to_a_human(self):
        # a red pair on N *and* on S: not a single-cab vehicle, so which end trails is ambiguous
        detection = self._detect(
            {(0 + 1, 20): RED, (0 + 6, 20): RED, (86 + 1, 20): RED, (86 + 6, 20): RED},
            trailing_only=True,
        )

        self.assertEqual(detection.pixels, {})
        self.assertTrue(any("both ends" in flag for flag in detection.flags))

    def test_over_the_cap_is_flagged_rather_than_automated(self):
        # four mirror-symmetric pairs = eight lamps, over MAX_LAMPS_PER_VIEW
        detection = self._detect(
            {(0 + x, 20): RED for x in (1, 2, 5, 6)} | {(0 + x, 12): RED for x in (1, 2, 5, 6)},
            trailing_only=True,
        )

        self.assertEqual(detection.pixels, {})
        self.assertTrue(any("cap" in flag for flag in detection.flags))

    def test_the_cache_key_separates_the_two_modes(self):
        _sheet(self.sheet, {0: {(0 + 1, 20): RED, (0 + 6, 20): RED}})
        vehicle = SimpleNamespace(spritesheet_path=str(self.sheet))
        lighting = VehicleLighting(
            vehicle, _palette(), [_definition()], str(self.root / "out")
        )

        plain = lighting.detection_for(_parts(0), trailing_only=False)
        driving = lighting.detection_for(_parts(0), trailing_only=True)

        self.assertEqual(plain.pixels, {})
        self.assertEqual(len(driving.pixels), 2)


class FakeVariant:
    """Just enough of a `Variant` for the assumption pass: sprites, settings, a detection.

    The identifier is written as `<unit> <profile>/<livery>` so the labels the pass records are the
    ones a build would produce, without needing `Variant.process()` to have run.
    """

    def __init__(self, identifier, rows, template_name="tmpl_train_8_old", settings=None):
        unit, rest = identifier.split(" ", 1)
        profile_id, livery_name = rest.split("/", 1)
        self.profile = SimpleNamespace(identifier=profile_id)
        self.livery = SimpleNamespace(name=livery_name)
        self.vehicle = SimpleNamespace(identifier=unit)
        self.spritesets = [_spriteset(row, template_name) for row in rows]
        self.sprite_template_names = [template_name] * len(rows)
        self.lighting_detection = None
        self._settings = settings or {}

    def get_attr(self, name):
        return self._settings.get(name)


class FakeAllocator:
    def __init__(self, sheet):
        self.sheet = str(sheet)

    def sheet_for(self, profile, livery):
        return self.sheet


def _spriteset(row_y: int, template_name: str):
    template = Template(
        name=template_name,
        sprites=[Sprite(left, top, width, height, 0, 0) for left, top, width, height in BOXES],
    )
    return Spriteset(name=f"spriteset_{row_y}", file="sheet.png", template=template, x=0, y=row_y)


def _detection(lamps: dict) -> Detection:
    detection = Detection()
    detection.pixels.update(lamps)
    detection.pairs = len(lamps)
    return detection


class AssumedPatternTests(unittest.TestCase):
    """Jon's rule: a livery the detector cannot read takes its unit's own lamp pattern.

    Only where exactly one trustworthy pattern exists, only on the same sheet and template, and
    never when the unit says `lighting: exact`.
    """

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.sheet = self.root / "sheet.png"
        _sheet(self.sheet, {})

    def tearDown(self):
        self._folder.cleanup()

    def _lighting(self):
        vehicle = SimpleNamespace(spritesheet_path=str(self.sheet))
        return VehicleLighting(vehicle, _palette(), [_definition()], str(self.root / "out"))

    def _run_real(self, variants):
        """Call the pass on a real Builder instance (it needs no other state)."""
        from Builder.Builder import Builder

        builder = Builder.__new__(Builder)
        lighting = self._lighting()
        Builder._assume_lighting_patterns(
            builder, variants, FakeAllocator(self.sheet), {str(self.sheet): lighting}
        )
        return lighting

    def test_an_unreadable_livery_takes_the_units_single_pattern(self):
        source = FakeVariant("br_mk4 dvt/National Express", [25])
        source.lighting_detection = _detection({(1, 25 + 21): WHITE, (6, 25 + 21): WHITE})
        target = FakeVariant("br_mk4 dvt/Virgin East Coast", [50])

        self._run_real([source, target])

        self.assertEqual(target.lighting_detection.pixels, {(1, 50 + 21): WHITE, (6, 50 + 21): WHITE})
        self.assertEqual(target.lighting_detection.assumed_from, "br_mk4 dvt/National Express")
        self.assertEqual(target.lighting_detection.view_mapping, "assumed")
        self.assertTrue(any("verify in game" in flag for flag in target.lighting_detection.flags))

    def test_two_patterns_are_ambiguous_and_nothing_is_assumed(self):
        first = FakeVariant("br_mk1 a/first", [25])
        first.lighting_detection = _detection({(1, 25 + 21): WHITE, (6, 25 + 21): WHITE})
        second = FakeVariant("br_mk1 b/second", [50])
        second.lighting_detection = _detection({(0, 50 + 20): WHITE})
        target = FakeVariant("br_mk1 c/third", [75])

        self._run_real([first, second, target])

        self.assertIsNone(target.lighting_detection)

    def test_a_different_template_is_not_a_pattern_match(self):
        source = FakeVariant("br_mk1 a/first", [25], template_name="tmpl_train_8")
        source.lighting_detection = _detection({(1, 25 + 21): WHITE})
        target = FakeVariant("br_mk1 b/second", [50], template_name="tmpl_train_8_old")

        self._run_real([source, target])

        self.assertIsNone(target.lighting_detection)

    def test_a_flagged_pattern_is_not_evidence(self):
        source = FakeVariant("br_mk1 a/first", [25])
        source.lighting_detection = _detection({(1, 25 + 21): WHITE})
        source.lighting_detection.flags.append("view 0 of row y=25 found 8 lamp pixels (cap 6): not automated")
        target = FakeVariant("br_mk1 b/second", [50])

        self._run_real([source, target])

        self.assertIsNone(target.lighting_detection)

    def test_lighting_exact_on_the_target_keeps_the_artwork_as_drawn(self):
        source = FakeVariant("br_mk1 a/first", [25])
        source.lighting_detection = _detection({(1, 25 + 21): WHITE})
        target = FakeVariant("br_mk1 b/second", [50], settings={"lighting": "exact"})

        self._run_real([source, target])

        self.assertIsNone(target.lighting_detection)

    def test_lighting_exact_on_the_only_reader_leaves_nothing_to_assume(self):
        source = FakeVariant("br_mk1 a/first", [25], settings={"lighting": "exact"})
        source.lighting_detection = _detection({(1, 25 + 21): WHITE})
        target = FakeVariant("br_mk1 b/second", [50])

        self._run_real([source, target])

        self.assertIsNone(target.lighting_detection)

    def test_the_assumption_is_cached_against_the_sibling_it_came_from(self):
        source = FakeVariant("br_mk1 a/first", [25])
        source.lighting_detection = _detection({(1, 25 + 21): WHITE})
        target = FakeVariant("br_mk1 b/second", [50])

        lighting = self._run_real([source, target])

        keys = [key for key in lighting._detections if "assumed" in key]
        self.assertEqual(len(keys), 1)
        self.assertIn("br_mk1 a/first", keys[0])


class VehicleLightingTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.sheet = _sheet(
            self.root / "BR000.png",
            {
                # the leading drawing carries the white lamps in its nose view...
                0: {(86 + 1, 20): WHITE, (86 + 6, 20): WHITE},
                # ...and the trailing drawing the red ones in the view four along
                ROW_PITCH: {(1, ROW_PITCH + 20): RED, (6, ROW_PITCH + 20): RED},
            },
        )
        self.vehicle = type("Vehicle", (), {"spritesheet_path": str(self.sheet), "identifier": "br_000"})()
        self.output = self.root / "WorkingData"

    def tearDown(self):
        self._folder.cleanup()

    def _lighting(self):
        return VehicleLighting(self.vehicle, list(_palette()), [_definition()], str(self.output))

    def test_writes_overlay_and_transparency_sheets_with_pixels(self):
        lighting = self._lighting()
        lighting.detection_for(_parts(0, ROW_PITCH))
        lighting.write_images()
        self.assertIsNotNone(lighting.overlay_path)
        self.assertTrue(lighting.overlay_path.is_file())
        self.assertTrue(lighting.transparent_path.is_file())
        overlay = Image.open(lighting.overlay_path).convert("P")
        self.assertEqual(overlay.getpixel((87, 20)), RED)
        self.assertEqual(overlay.getpixel((1, ROW_PITCH + 20)), WHITE)

    def test_an_unchanged_overlay_is_not_rewritten(self):
        lighting = self._lighting()
        lighting.detection_for(_parts(0, ROW_PITCH))
        lighting.write_images()
        before = lighting.overlay_path.stat().st_mtime_ns
        again = self._lighting()
        again.detection_for(_parts(0, ROW_PITCH))
        again.write_images()
        self.assertEqual(again.overlay_path.stat().st_mtime_ns, before)

    def test_no_pixels_writes_nothing(self):
        _sheet(self.sheet, {
            0: {(86 + 1, 20): WHITE, (86 + 6, 20): WHITE},
            ROW_PITCH: {(1, ROW_PITCH + 20): WHITE, (6, ROW_PITCH + 20): WHITE},
        })  # white on both drawings: no state change, so nothing to automate
        lighting = self._lighting()
        lighting.detection_for(_parts(0, ROW_PITCH))
        lighting.write_images()
        self.assertIsNone(lighting.overlay_path)

    def test_second_run_reuses_the_cache(self):
        lighting = self._lighting()
        lighting.detection_for(_parts(0, ROW_PITCH))
        lighting.write_images()
        self.assertTrue(lighting.unwritten)

        cached = self._lighting()
        detection = cached.detection_for(_parts(0, ROW_PITCH))
        self.assertFalse(cached.unwritten, "the second run should not have done detection work")
        self.assertEqual(detection.pairs, 2)


if __name__ == "__main__":
    unittest.main()
