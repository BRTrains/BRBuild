import re
import logging
from Badge import BadgeRegistry
from Grf.RailTypeTable import RailTypeTable
from Lang.StringRegistry import nml_clean_str, nml_str
from PropertyCalculation import (
    CostCalculator,
    FuelDefaults,
    FuelType,
    loading_speed_for,
    Physics,
    PowerTypeClassifier,
    TrainType,
    VehicleType,
)
from PropertyCalculation.CargoClasses import as_bitmask
from PropertyCalculation.Formation import formation_display_name, formation_tag
from Sprites.LightingOverlay import LIGHTING_NONE

from Vehicle.Translator.PhysicsRules import PhysicsRules
from Vehicle.Translator.Speed import speed_field
from Vehicle.Translator.Tilt import MISC_FLAG_TILT, Tilt, resolve_tilt

logger = logging.getLogger(__name__)

#: Largest weight a road vehicle's weight property can hold: one byte in 1/4-ton units.
ROADVEH_WEIGHT_PROPERTY_MAX_T = 63.75
#: Road vehicle power is stored in a byte in 10 hp units.
ROADVEH_POWER_PROPERTY_MAX_HP = 2550

#: Name colours for the purchase list: the profile in grey, the livery in gold. The vehicle
#: keeps OpenTTD's own default text colour, so it needs no code and `BLACK` exists only to
#: close a grey profile again. Readable names rather than raw palette indices, because what
#: each segment should look like is a presentation decision.
GRAY = "GRAY"
BLACK = "BLACK"
GOLD = "GOLD"
RED = "RED"
SILVER = "SILVER"
LTBROWN = "LTBROWN"


def colour(name: str) -> str:
    """Render an OpenTTD text colour code, e.g. `{GOLD}`."""
    return "{" + name + "}"


class Variant:
    #: The BRTrains track types, used when a candidate set does not provide its own
    #: `RailTypes.yaml`. Candidates normally take this: the fallbacks are about
    #: interoperability with track sets, which is not a per-unit decision.
    DEFAULT_RAILTYPE_TABLE = RailTypeTable(
        entries={
            "RAIL": ["RAIL"],
            "ELRL": ["SAAA", "SAAE", "ELRL"],
            "THIRD": ["SAA3", "3RDR", "ELRL"],
            "FOURTH": ["SAA4", "SAA3", "4RDR", "ELRL"],
        }
    )

    def __init__(self, vehicle, livery, profile, vehicleType=None, rail_type_table=None):
        self.vehicle = vehicle
        self.livery = livery
        self.profile = profile
        self.vehicle_type = vehicleType if vehicleType is not None else vehicle.vehicle_type
        self.rail_type_table = rail_type_table or self.DEFAULT_RAILTYPE_TABLE

        self.badges = list()
        self.properties = dict()
        self.callbacks = dict()

        self.spritesets = list()
        self.misc_flags = set()
        #: Train `extra_flags` contributed by any stage (`handleExtraFlags` writes the bitmask).
        self.extra_flags = set()
        self.visual_effect = None
        self.track_types = list()
        #: Track types implied by the vehicle's traction, unless it names its own.
        self.default_track_types = None
        self.sprite_pattern = list()
        self.sprite_template_names = list()
        self.sprite_lengths = list()
        self.spriteset_names = list()
        self.purchase_spriteset = None
        self.purchase_spriteset_name = None
        #: Lamp pixels found for this variant (Sprites.LightingOverlay.Detection), plus the sheets the
        #: builder generated for it. Set before `process()` so the misc flag and graphics chain follow.
        self.lighting_detection = None
        self.lighting_overlay_path = None
        self.lighting_transparent_path = None
        self.lighting_switch_name = None
        self.purchase_template_name = None
        self.sprite_switch_name = None
        self.length_switch_name = None
        self.articulated_switch_name = None
        self.articulated_count = None
        self.effect_callback_name = None
        self.effect_switch_name = None
        self.nml_override: dict = {}
        self.disable_item_condition = None
        self.disable_item_conditions = []
        self.is_livery_refit = False
        self.refit_groups = []

        self.identifier = None
        self.nml_filename = None
        self.sprite_id = None
        self.sprite_id_generation = 1

    def process(self):
        """Executes the processing pipeline stages for this variant."""
        stages = [
            self.generate_identifiers,
            self.handleArticulated,
            self.handleBasicProperties, # Things that don't need any complicated transformations or calculations
            self.handleSpeed,
            self.handleTilt,
            self.handleCargo,
            self.handleCapacity,
            self.handlePhysics,
            self.handleFuelType,
            self.handleRunningCostBase,
            self.handleTrackType,
            self.handleFuelPresentation,
            self.handleCosts,
            self.handleSpecialTags,
            self.handleAdditionalText,
            self.handleColourMapping,
            self.handleSprites,
            self.handleEffectSpawnModel,
            self.handleLighting,
            self.handleMiscFlags,
            self.handleExtraFlags,
            self.handleNmlOverride,
        ]

        for stage in stages:
            try:
                stage()
            except Exception as exc:
                logger.exception(f"Error in variant {self} during stage {stage.__name__}: {exc}")
                raise

    # Clamp ranges
    @staticmethod
    def clamp(n, smallest, largest):
        return max(smallest, min(n, largest))

    def get_attr(self, attr):
        # Check livery first, then profile, then vehicle, returning the first non-None
        # value: the narrowest statement wins, so one livery of a unit can override the
        # profile's own value.
        for obj in (self.livery, self.profile, self.vehicle):
            val = getattr(obj, attr, None)
            if val is not None:
                return val
        return None

    def resolved_vehicle_count(self):
        """Share the sprite arrangement's part count across articulation and names."""
        from Vehicle.VariantSpriteGroups import _resolve_pattern

        pattern = self.sprite_pattern or _resolve_pattern(self.livery, self.profile, self.vehicle)
        if pattern:
            return len(pattern)
        count = self.get_attr("num_vehicles")
        return count if count is not None else self.get_attr("size")

    def _formation_tag(self):
        override = self.get_attr("formation")
        if override:
            value = str(override).strip()
            return value if value.lower().startswith("formation/") else f"formation/{value}"
        return formation_tag(
            getattr(self.vehicle, "train_type", None),
            self.get_attr("power"),
            self.get_attr("cargo_classes"),
            self.get_attr("power_type"),
            num_vehicles=self.resolved_vehicle_count(),
        )

    def _formation_display_name(self):
        return formation_display_name(self._formation_tag())

    def _vehicle_display_name(self):
        sub_name = self.get_attr("sub_name")
        sub_name = str(sub_name).strip() if sub_name else ""
        nickname = getattr(self.vehicle, "nickname", None)
        name = self.vehicle.name
        if sub_name:
            name += f" {sub_name}"
        if nickname:
            name += f' "{nickname}"'
        return name

    @property
    def name(self):
        """Return the full variant name using nickname, formation and livery."""
        vehicle = self._vehicle_display_name()
        formation = self._formation_display_name()
        livery = self._livery_display_name()
        name = vehicle
        if formation:
            name += f" - {colour(SILVER)}{formation}{colour(BLACK)}"
        if livery:
            name += f" - {colour(GOLD)}{livery}"
        return name

    def _name_parts(self):
        """Return the vehicle, formation and livery name segments."""
        return self._vehicle_display_name(), self._formation_display_name(), self._livery_display_name()

    def _display_name(self):
        """Return the displayed name without changing the variant's stable NML string key."""
        if getattr(self.vehicle, "development", False):
            return f"{colour(RED)}(devmode){colour(BLACK)} {nml_clean_str(self.name)}"
        return self.name

    def _display_string(self, text, key, *, deduplicate=False):
        development = bool(getattr(self.vehicle, "development", False))
        if development:
            text = f"{colour(RED)}(devmode){colour(BLACK)} {nml_clean_str(text)}"
        return nml_str(text, key, deduplicate=deduplicate, preserve_parentheses=development)

    def _profile_display_name(self):
        """Return the profile's own name, or "" when the profile is the unnamed `Default`."""
        if not self.profile:
            return ""
        profile_id = str(self.profile.identifier).strip() if self.profile.identifier else ""
        if profile_id.upper() == "DEFAULT":
            return ""
        name = str(self.profile.name).strip() if self.profile.name else ""
        if name.upper() == "DEFAULT":
            return ""
        return self.profile.name or profile_id

    def _livery_display_name(self):
        """Return the livery's own name, or "" when it is the unnamed `Default` livery.

        `Default` is a placeholder for "this unit has no livery name of its own", so the
        name falls back to the vehicle's; any other name disambiguates the variant.
        """
        if not self.livery or not self.livery.name:
            return ""
        name = str(self.livery.name).strip()
        return "" if name.upper() == "DEFAULT" else name

    def __repr__(self):
        return f"Variant(vehicle={self.vehicle.name}, livery={self.livery.name}, profile={self.profile.identifier})"

    def __str__(self):
        return self.name

    def generate_identifiers(self):
        # Generate unique identifiers for the variant based on the vehicle, livery, and profile
        raw_id = (
            f"{self.vehicle.identifier}_"
            f"{self.profile.identifier}_"
            f"{self.livery.name}_"
            f"{self.vehicle_type.name}"
        ).lower()
        self.identifier = re.sub(r"[^a-z0-9_]", "_", raw_id)
        if self.sprite_id_generation > 1:
            self.identifier = f"{self.identifier}_v{self.sprite_id_generation}"
        self.nml_filename = f"{self.identifier}.gnml"

        # Formatted NML header properties. The name is a property and nothing else: OpenTTD
        # keeps a vehicle's name in its own per-vehicle string space (Action 4 keyed by the
        # vehicle id), while a name returned from a callback is drawn from the 1024-id misc
        # pool (`0xD0`) — the pool the set's per-variant names had exhausted.
        name_ref = self._display_string(self.name, f"{self.identifier}_name")
        self.properties["name"] = name_ref

        # The root switch names the vehicle and formation; the nested switch names the
        # formation and livery. The variant property below carries the full name including
        # the livery for details/depot views.
        formation_name = self._formation_display_name()
        livery_name = self._livery_display_name()
        vehicle_name = self._vehicle_display_name()
        self.name_callback_name = f"sw_{self.identifier}_name"
        self.name_callback_string = self._display_string(
            vehicle_name
            + (f" - {{SILVER}}{formation_name}{{BLACK}}" if formation_name else "")
            + (f" - {{GOLD}}{livery_name}" if livery_name else ""),
            f"{self.identifier}_group_name",
            deduplicate=True,
        )
        self.name_callback_nested_string = nml_str(
            (f"{{SILVER}}{formation_name}{{BLACK}}" if formation_name else "")
            + (f" - " if formation_name and livery_name else "")
            + (f"{{GOLD}}{livery_name}" if livery_name else ""),
            f"{self.identifier}_nested_name",
            deduplicate=True,
        )
        self.callbacks["name"] = self.name_callback_name

        v_type = self.vehicle_type
        if getattr(v_type, "name", str(v_type)).upper() == "TRAM":
            self.add_misc_flag("ROADVEH_FLAG_TRAM")

    ''' Handle some fairly simple properties that don't need complex calculations'''
    def handleBasicProperties(self):
        """Emit the properties that need no calculation: dates, life, length.

        `introduction_date` arrives already resolved to an NML `date(...)` expression by
        the loader; a raw year is still accepted here so a variant built by hand (a
        test, or a caller constructing a Variant directly) behaves sensibly.
        """
        intro_date = self.get_attr("introduction_date")
        if intro_date is not None:
            if isinstance(intro_date, int) or (isinstance(intro_date, str) and intro_date.isdigit()):
                self.properties["introduction_date"] = f"date({intro_date}, 1, 1)"
            else:
                self.properties["introduction_date"] = str(intro_date)

        model_life = self.get_attr("years_available")
        if model_life is None:
            # Keep accepting the old internal name for callers constructing Vehicle objects
            # directly. YAML authoring should use years_available.
            model_life = self.get_attr("model_life")
        if model_life is None:
            introduction_year = self._introduction_year(intro_date)
            if introduction_year is not None and introduction_year <= 1998:
                model_life = 30
        if model_life is None or int(model_life) == 0:
            model_life = "VEHICLE_NEVER_EXPIRES"
        else:
            model_life = self.clamp(int(model_life), 1, 254) # Clamp to NML range
        self.properties["model_life"] = str(model_life)

        self.properties["climates_available"] = "ALL_CLIMATES"

        vehicle_life = self.get_attr("vehicle_life")
        if vehicle_life is not None:
            vehicle_life = self.clamp(int(vehicle_life), 1, 255) # Clamp to NML range
        else:
            vehicle_life = self._default_vehicle_life(intro_date)
        self.properties["vehicle_life"] = str(vehicle_life)

        length = self.get_attr("length")
        if length is not None:
            self.properties["length"] = str(length)

    @staticmethod
    def _introduction_year(value):
        """Extract the year from the resolved NML date expression."""
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            if value.isdigit():
                return int(value)
            match = re.match(r"\s*date\s*\(\s*(\d+)", value)
            if match:
                return int(match.group(1))
        return None

    def _default_vehicle_life(self, introduction_date):
        """Return the default lifespan for the resolved vehicle facts."""
        power_type = self.get_attr("power_type")
        if isinstance(power_type, str):
            power_types = {power_type.lower()}
        else:
            power_types = {str(value).lower() for value in (power_type or [])}
        if "steam" in power_types:
            return 30

        train_type = getattr(self.vehicle, "train_type", None)
        train_type_name = getattr(train_type, "name", str(train_type)).upper()
        introduction_year = self._introduction_year(introduction_date)
        if (
            train_type_name in {"COACH", "WAGON"}
            and introduction_year is not None
            and introduction_year < 1960
        ):
            return 30
        return 40

    def handleSpeed(self):
        """Emit the vehicle's speed, and the design/service selector when they differ.

        `speed` is the service speed (the normal limit a train runs to) and
        `design_speed` is the maximum the vehicle is designed for. When only one is
        given, both settings of the `param_speed_mode` parameter resolve to it, so the
        property is written plainly and the callback is not emitted at all. When they
        differ, the callback becomes the design/service selector, defaulting to the
        design figure unless the project's parameter says otherwise.
        """
        service = self.get_attr("speed")
        design = self.get_attr("design_speed")
        self.speed = service if service is not None else design
        if self.speed is None:
            return

        self.properties["speed"] = self._format_speed(self.speed)
        if design is None or service is None or float(design) == float(service):
            return

        if design < service:
            logger.warning(
                "%s has a design speed lower than its service speed (%s < %s mph)",
                self.identifier,
                design,
                service,
            )
        self.callbacks["speed"] = self._speed_selector(design, service)

    @staticmethod
    def _format_speed(value) -> str:
        if isinstance(value, float):
            return f"{value:.1f} mph"
        return f"{value} mph"

    def _speed_selector(self, design, service) -> str:
        """The design/service speed switch expression for one variant.

        The parameter holds 1 for design speeds (the default) and 0 for service speeds,
        so the expression is written in that order. Both figures are converted out of mph
        into the value the speed field takes (`Vehicle/Translator/Speed.py`): a callback
        is an expression, so NML accepts no unit literal here and does not convert the
        result, while the property it stands in for carries `mph` and is converted by
        nmlc.
        """
        return (
            f"param_speed_mode == 1 ? {speed_field(design)} "
            f": {speed_field(service)}"
        )

    def handleTilt(self):
        """Emit curve_speed_mod and, when the vehicle tilts, the consist tilt flag.

        `tilt` is a named level or a number (see Vehicle/Translator/Tilt.py). It is
        resolved profile first, then livery, then vehicle, like the other
        per-variant statistics, so one formation of a unit can tilt where another
        does not.
        """
        tilt = resolve_tilt(self.get_attr("tilt"))
        self.tilt = tilt
        if tilt is None:
            return

        self.curve_speed_mod = tilt.curve_speed_mod
        self.properties["curve_speed_mod"] = self._format_number(tilt.curve_speed_mod)
        if tilt.uses_tilt_flag:
            self.add_misc_flag(MISC_FLAG_TILT)

    @staticmethod
    def _format_number(value: float) -> str:
        """Render a float without a trailing '.0', which NML reads as an integer."""
        if float(value).is_integer():
            return str(int(value))
        return repr(float(value))

    def add_misc_flag(self, flag: str):
        self.misc_flags.add(flag)

    def add_extra_flag(self, flag: str):
        self.extra_flags.add(flag)

    def handleExtraFlags(self):
        """Write the accumulated train `extra_flags` bitmask.

        One flag so far: `VEHICLE_FLAG_TRAIN_HAS_CAB`, from `has_cab: true` on the vehicle, a
        profile or a livery. It tells OpenTTD this unpowered vehicle has a driving cab, so the
        train may back up with it leading instead of magic-flipping the whole consist.

        A road vehicle has no equivalent — the back-up state exists for trains only — so the flag
        is emitted for trains and a `has_cab` on a tram-only variant is ignored rather than
        written into the road-vehicle property block, where the bit would mean something else.
        """
        if self.get_attr("has_cab"):
            vehicle_type = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
            if vehicle_type == "TRAIN":
                self.add_extra_flag("VEHICLE_FLAG_TRAIN_HAS_CAB")
            else:
                logger.debug(
                    f"Ignoring 'has_cab' for {self.vehicle.name} ({vehicle_type}): the "
                    f"has-a-cab flag applies to trains only."
                )

        if self.extra_flags:
            self.properties["extra_flags"] = f"bitmask({', '.join(sorted(self.extra_flags))})"

    def handleMiscFlags(self):
        """Write the accumulated misc_flags bitmask and the visual effect last.

        Both are written here so every earlier stage can contribute to them.
        """
        if self.misc_flags:
            self.properties["misc_flags"] = f"bitmask({', '.join(sorted(self.misc_flags))})"

        if getattr(self, "visual_effect", None):
            vehicle_type = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
            if vehicle_type == "TRAIN":
                # Trains use the _and_powered form, which always takes three arguments.
                # Wagon power stays off and the effect offset is 0, so the drawn offset
                # comes from the sprite template.
                self.properties["visual_effect_and_powered"] = (
                    f"visual_effect_and_powered({self.visual_effect}, 0, DISABLE_WAGON_POWER)"
                )
            else:
                self.properties["visual_effect"] = f"visual_effect({self.visual_effect}, 0)"

    def handleCargo(self):
        """Emit the cargo configuration the loader reads.

        Three states, all meaningful: unset emits nothing; `cargo: none` emits a deliberate
        empty class list, so a vehicle that carries nothing says so instead of looking like
        a conversion that simply forgot; anything else emits the bitmask. Capacity stays 1
        in the property with the real value in the callback, as the legacy set did.
        """
        refittable = self.get_attr("cargo_classes")
        if refittable is None:
            pass
        elif not refittable:
            self.properties["refittable_cargo_classes"] = "0"
        else:
            self.properties["refittable_cargo_classes"] = as_bitmask(refittable)

        non_refittable = as_bitmask(self.get_attr("non_cargo_classes") or [])
        if non_refittable:
            self.properties["non_refittable_cargo_classes"] = non_refittable

        default_cargo = self.get_attr("default_cargo_type")
        if default_cargo:
            self.properties["default_cargo_type"] = str(default_cargo).strip().upper()

        loading_speed = self.get_attr("loading_speed")
        if loading_speed is None:
            loading_speed = loading_speed_for(
                doors=self.get_attr("doors"),
                usage=self.get_attr("usage"),
                speed=self.get_attr("speed"),
                train_type=getattr(self.vehicle, "train_type", None),
                cargo_classes=self.get_attr("cargo_classes"),
            )
        if loading_speed is not None:
            self.properties["loading_speed"] = str(int(loading_speed))

        cargo_age_period = self.get_attr("cargo_age_period")
        if cargo_age_period is not None:
            self.properties["cargo_age_period"] = str(int(cargo_age_period))

        if self.get_attr("autorefit"):
            self.add_misc_flag("TRAIN_FLAG_AUTOREFIT")

    def handleCapacity(self):
        capacity = self.get_attr("capacity")
        if capacity is None:
            capacity = 0
        cargo_classes = self.get_attr("cargo_classes") or []
        cargo_classes = {str(cargo).upper() for cargo in cargo_classes}
        if not cargo_classes or "PASSENGERS" in cargo_classes:
            parameter = "param_passenger_multiplier"
        elif "MAIL" in cargo_classes:
            parameter = "param_mail_multiplier"
        else:
            parameter = "param_freight_multiplier"
        # Each parameter defaults to one, but an unset slot in an older save reads
        # as zero, so retain the authored capacity instead of zeroing it.
        self.callbacks["cargo_capacity"] = (
            f"{parameter} < 1 "
            f"? {int(capacity)} "
            f": {int(capacity)} * {parameter}"
        )
        self.properties["cargo_capacity"] = 1 # Needed for NML to allow the callback override

    def handlePhysics(self):
        PhysicsRules().apply_rules(self)

        power = self.get_attr("power")
        if power is not None:
            self.power = power
            vehicle_type_name = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
            if vehicle_type_name in ("TRAM", "ROAD"):
                self.properties["power"] = f"{min(power, ROADVEH_POWER_PROPERTY_MAX_HP)} hp"
            else:
                self.properties["power"] = f"{power} hp"
        else:
            self.power = 0

        weight = self.get_attr("weight")
        if weight is not None:
            vehicle_type_name = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
            if vehicle_type_name in ("TRAM", "ROAD"):
                # A road vehicle's weight property is one byte of 1/4 tons, so it cannot carry
                # more than 63.75 t: the property holds the clamped figure as the fallback and the
                # callback holds the real one, in the field's unit (nmlc converts a `ton` property
                # but converts nothing written into an expression - the same split the capacity
                # already uses). Writing the property at the authored figure aborts the compile
                # with `Action 0 property too large`.
                self.properties["weight"] = f"{min(weight, ROADVEH_WEIGHT_PROPERTY_MAX_T)} ton"
                self.callbacks["weight"] = f"{round(weight * 4)}"
            else:
                self.properties["weight"] = f"{weight} ton"

        if hasattr(self, "te_coefficient") and self.te_coefficient is not None:
            self.properties["tractive_effort_coefficient"] = str(self.te_coefficient)

        if hasattr(self, "ad_coefficient") and self.ad_coefficient is not None:
            self.properties["air_drag_coefficient"] = str(self.ad_coefficient)

    def handleCosts(self):
        calculator = CostCalculator(self)

        purchase_cost = calculator.purchase_cost(False)
        running_cost = calculator.running_cost(False)

        self.callbacks["cost_factor"] = calculator.runtime_expression(
            purchase_cost, "param_purchase_cost_multiplier"
        )
        self.callbacks["running_cost_factor"] = calculator.runtime_expression(
            running_cost, "param_running_cost_multiplier"
        )
    
    #todo: this doesn't need to be per variant, can be done per vehicle instead
    def handleAdditionalText(self):
        additional_text = self.get_attr("additional_text")
        if additional_text:
            if isinstance(additional_text, list):
                additional_text = "{}".join(additional_text)
            self.callbacks["additional_text"] = nml_str(additional_text,f"{self.identifier}_additional_text")

    def handleSpecialTags(self):
        for source in (self.vehicle, self.profile, self.livery):
            for tag in getattr(source, "special_tags", None) or []:
                # Formation is derived from the resolved facts below; a hand-authored
                # formation badge must not survive alongside the derived one.
                if str(tag).lower().startswith("formation/"):
                    continue
                badge = BadgeRegistry().add_badge(tag)
                if badge not in self.badges:
                    self.badges.append(badge)

        formation = self._formation_tag()
        if formation:
            badge = BadgeRegistry().add_badge(formation)
            if badge not in self.badges:
                self.badges.append(badge)

        operator = self.get_attr("operator")
        if operator:
            # Route the operator badge through the registry so its name string exists in
            # the badge table; NML only accepts badge literals declared there.
            badge = BadgeRegistry().add_badge(f"operator/{operator}")
            if badge not in self.badges:
                self.badges.append(badge)

        if self.badges:
            badges_formatted = ", ".join(f'"{b}"' for b in self.badges)
            self.properties["badges"] = f"[{badges_formatted}]"

    def handleFuelType(self):
        PowerTypeClassifier(self).process()

    def _power_type_tokens(self):
        raw_power = self.get_attr("power_type") or self.get_attr("fuel_type")
        if isinstance(raw_power, str):
            raw_power = [raw_power]
        return {str(value).strip().upper() for value in (raw_power or [])}

    def handleRunningCostBase(self):
        """Select the NML running-cost category from the resolved vehicle type."""
        vehicle_type = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
        if vehicle_type in {"TRAM", "ROAD", "ROADVEH"}:
            self.properties["running_cost_base"] = "RUNNING_COST_ROADVEH"
            return

        tokens = self._power_type_tokens()
        if "STEAM" in tokens:
            base = "RUNNING_COST_STEAM"
        elif tokens & {"DIESEL", "DIESEL_HYDRAULIC", "DIESEL_ELECTRIC", "DIESEL_MECHANICAL", "HYDRAULIC", "GAS_TURBINE", "GAS_TURBINE_ELECTRIC", "TURBINE"}:
            base = "RUNNING_COST_DIESEL"
        elif tokens or getattr(self, "fuel_type", None) == FuelType.ELECTRIC:
            base = "RUNNING_COST_ELECTRIC"
        else:
            base = "RUNNING_COST_DIESEL"
        self.properties["running_cost_base"] = base

    def _effect_power_key(self):
        tokens = self._power_type_tokens()
        if "STEAM" in tokens:
            return "steam"
        if tokens & {"DIESEL", "DIESEL_HYDRAULIC", "DIESEL_ELECTRIC", "DIESEL_MECHANICAL", "HYDRAULIC", "GAS_TURBINE", "GAS_TURBINE_ELECTRIC", "TURBINE"}:
            return "diesel"
        if set(self.track_types) & {"THIRD", "FOURTH"}:
            return "powered_rail"
        if tokens or getattr(self, "fuel_type", None) == FuelType.ELECTRIC:
            return "ohle"
        return "none"

    def _power_override(self, attr, key):
        for source in (self.livery, self.profile, self.vehicle):
            values = getattr(source, attr, None) or {}
            if key in values:
                return values[key]
        return None

    def _effect_positions(self, power_key):
        positions = self._power_override("effect_vehicles_by_power", power_key)
        if positions is None and power_key == "ohle":
            positions = self.get_attr("pantograph_car")
        if positions is None:
            positions = self.get_attr("effect_vehicles")
        if positions is not None:
            return list(positions)

        pattern = list(self.sprite_pattern or [1])
        if power_key == "steam":
            return [1]
        if power_key in {"diesel", "powered_rail"}:
            return list(range(1, len(pattern) + 1))
        if power_key != "ohle":
            return []
        if len(pattern) <= 2:
            return [1]
        if len(pattern) == 3:
            return [2]

        end_groups = {pattern[0], pattern[-1]}
        candidates = sorted(set(pattern) - end_groups)
        if not candidates:
            return [len(pattern)]
        counts = {group: pattern.count(group) for group in candidates}
        selected = max(candidates, key=lambda group: (-counts[group], group))
        return [index + 1 for index, group in enumerate(pattern) if group == selected]

    def _effect_sprite(self, power_key):
        sprite = self._power_override("effect_sprites_by_power", power_key)
        if sprite is None:
            sprite = self.get_attr("effect_sprite")
        if sprite is not None:
            return str(sprite).strip()
        return {
            "steam": "EFFECT_SPRITE_STEAM",
            "diesel": "EFFECT_SPRITE_DIESEL",
            "ohle": "EFFECT_SPRITE_ELECTRIC",
            "powered_rail": "EFFECT_SPRITE_ELECTRIC",
        }.get(power_key, "EFFECT_SPRITE_NONE")

    def _effect_offsets(self, power_key):
        values = {
            "x": self.get_attr("effect_x_offset"),
            "y": self.get_attr("effect_y_offset"),
            "z": self.get_attr("effect_z_offset"),
        }
        if values["z"] is None:
            values["z"] = -6 if power_key == "powered_rail" else 10
        override = self._power_override("effect_offsets_by_power", power_key) or {}
        for axis in ("x", "y", "z"):
            if axis in override:
                values[axis] = override[axis]
        return {axis: int(value or 0) for axis, value in values.items()}

    def handleEffectSpawnModel(self):
        """Generate standard effect properties and the articulated effect callback."""
        vehicle_type = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
        if vehicle_type != "TRAIN":
            return
        power_key = self._effect_power_key()
        effect_models = {
            "steam": "EFFECT_SPAWN_MODEL_STEAM",
            "diesel": "EFFECT_SPAWN_MODEL_DIESEL",
            "ohle": "EFFECT_SPAWN_MODEL_ELECTRIC",
            "powered_rail": "EFFECT_SPAWN_MODEL_ELECTRIC",
            "none": "EFFECT_SPAWN_MODEL_NONE",
        }
        self.properties["effect_spawn_model_and_powered"] = effect_models[power_key]
        if self.nml_override_callbacks() and "create_effect" in self.nml_override_callbacks():
            self.callbacks["create_effect"] = self.resolve_nml_override()["create_effect"]
            return
        sprite = self._effect_sprite(power_key)
        if sprite == "EFFECT_SPRITE_NONE":
            return
        offsets = self._effect_offsets(power_key)
        self.effect_callback_name = f"sw_{self.identifier}_create_effect"
        self.effect_switch_name = f"sw_{self.identifier}_create_effect_value"
        self.callbacks["create_effect"] = self.effect_callback_name
        self.effect_sprite = sprite
        self.effect_offsets = offsets
        self.effect_positions = self._effect_positions(power_key)

    def handleTrackType(self):
        """Emit the track types the vehicle can use, as NML railtype indices.

        The value is a list of the project's logical track types, resolved livery →
        profile → vehicle, so a dual-voltage formation can live in the same candidate as
        a single-system one. When none of the three names one, the vehicle's `power_type`
        decides (see `PowerTypeClassifier.track_types`): a self-powered unit gets `RAIL`,
        an overhead electric unit `ELRL`, third rail `THIRD`, fourth rail `FOURTH`, and a
        multi-system unit the union of its systems. The explicit field always wins, so a
        vehicle never has to accept the mapping the classifier would infer.

        Only trains have `track_type` in NML: a road vehicle's running gear is
        `road_type` or `tram_type` instead, so trams and road vehicles are left alone.
        """
        vehicle_type = getattr(self.vehicle_type, "name", str(self.vehicle_type)).upper()
        if vehicle_type != "TRAIN":
            return

        track_types = None
        for source in (self.livery, self.profile, self.vehicle):
            value = getattr(source, "track_type", None)
            if value:
                track_types = value
                break
        if not track_types:
            track_types = getattr(self, "default_track_types", None) or ["RAIL"]
        if isinstance(track_types, str):
            track_types = [track_types]

        self.track_types = list(track_types)
        self.properties["track_type"] = self.rail_type_table.lookup_many(self.track_types)

    def handleFuelPresentation(self):
        """Give the vehicle the sound and visual effect its fuel warrants.

        The novel fuels (hydrogen, battery, gas turbine) have no OpenTTD equivalent, so
        their presentation is chosen per fuel in `FuelDefaults`. Only a *deviation* from
        the engine class's own default is emitted, which keeps the property block on
        ordinary vehicles unchanged and avoids clashing with an `effect_spawn_model`.

        A vehicle, profile or livery can override either field by setting
        `sound_effect` or `visual_effect`.

        The effect is staged on `self.visual_effect` and written by `handleMiscFlags`,
        because NML names the property differently per feature (`visual_effect_and_powered`
        for trains, `visual_effect` for the others).
        """
        fuel = getattr(self, "fuel_type", None)
        if fuel is not None:
            default_engine_class = FuelDefaults.engine_class(fuel)
            default_visual_effect = FuelDefaults.visual_effect(fuel)
            if (
                default_visual_effect is not None
                and default_visual_effect != self._effect_for_engine_class(default_engine_class)
            ):
                self.visual_effect = default_visual_effect

        visual_effect = self.get_attr("visual_effect")
        if visual_effect is not None:
            self.visual_effect = str(visual_effect)

        sound_effect = self.get_attr("sound_effect")
        if sound_effect is not None:
            # `sound_effect` is a graphics callback, not a property: the callback returns
            # the sound to play (a SOUND_* constant, a sound(...) call, or a switch).
            self.callbacks["sound_effect"] = self._validate_sound_effect(str(sound_effect))

    def handleColourMapping(self):
        """Keep authored sprites in their source palette unless explicitly overridden.

        BRBuild currently has no 2CC-authored vehicles.  OpenTTD's default colour mapping
        callback can nevertheless reinterpret palette entries, which is undesirable for
        imported artwork whose colours are already deliberate.  Keep the escape hatch in
        ``nml_override`` for the future, but make identity mapping the project-wide default.
        """
        if "colour_mapping" not in self.nml_override_callbacks():
            self.callbacks["colour_mapping"] = "PALETTE_IDENTITY"

    @staticmethod
    def _validate_sound_effect(value: str) -> str:
        """Reject sound values NML cannot parse, before nmlc reports them obscurely.

        A sound may be a built-in `SOUND_*` constant, a `sound(...)`/`import_sound(...)`
        call, or a callback switch name declared elsewhere in the collated NML (which is
        what BRMetro does, e.g. `sw_sound_tram_generic`). An unquoted bare word is almost
        always a legacy name that means nothing here.
        """
        text = value.strip()
        if not text:
            raise ValueError("sound_effect must not be empty")
        if re.fullmatch(r"SOUND_[A-Z0-9_]+", text):
            return text
        if re.fullmatch(r"(import_)?sound\(.*\)", text):
            return text
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text):
            return text
        raise ValueError(
            f"sound_effect '{value}' is not a SOUND_* constant, a sound(...) call or a "
            "switch name"
        )

    @staticmethod
    def _effect_for_engine_class(engine_class: str | None) -> str | None:
        """The visual effect OpenTTD applies for an engine class when none is set."""
        if engine_class is None:
            return None
        return {
            "ENGINE_CLASS_STEAM": "VISUAL_EFFECT_STEAM",
            "ENGINE_CLASS_DIESEL": "VISUAL_EFFECT_DIESEL",
            "ENGINE_CLASS_ELECTRIC": "VISUAL_EFFECT_ELECTRIC",
            "ENGINE_CLASS_MONORAIL": "VISUAL_EFFECT_DISABLE",
            "ENGINE_CLASS_MAGLEV": "VISUAL_EFFECT_DISABLE",
        }.get(engine_class)

    def handleSprites(self):
        """Wire the per-variant sprite switch into graphics{} if sprites were assigned.

        Spriteset/switch names must be unique across the whole collated .nml, but the
        same underlying Spriteset can be reused by multiple variants (e.g. the same
        livery across train/tram types), so names are generated here from this
        variant's own identifier rather than reused from the shared Spriteset objects.

        A callback listed in `nml_override` keeps the candidate's own target instead:
        the generated switch for it is not emitted, so a unit that supplies its own NML
        gets its chain referenced rather than shadowed.
        """
        if not self.spritesets:
            return
        if self.is_livery_refit:
            if self.purchase_spriteset is not None:
                self.purchase_spriteset_name = f"spriteset_{self.identifier}_purchase"
                if "purchase" not in self.nml_override_callbacks():
                    self.callbacks["purchase"] = self.purchase_spriteset_name
            return

        overridden = self.nml_override_callbacks()

        if "default" not in overridden:
            self.sprite_switch_name = f"sw_{self.identifier}"

        name_by_spriteset: dict[int, str] = {}
        self.spriteset_names = []
        for spriteset in self.spritesets:
            key = id(spriteset)
            if key not in name_by_spriteset:
                name_by_spriteset[key] = f"spriteset_{self.identifier}_{len(name_by_spriteset)}"
            self.spriteset_names.append(name_by_spriteset[key])

        if "default" not in overridden:
            self.callbacks["default"] = self.sprite_switch_name

        if self.sprite_lengths and "length" not in overridden:
            self.length_switch_name = f"sw_{self.identifier}_length"
            self.callbacks["length"] = self.length_switch_name

        if self.purchase_spriteset is not None:
            self.purchase_spriteset_name = f"spriteset_{self.identifier}_purchase"
            if "purchase" not in overridden:
                self.callbacks["purchase"] = self.purchase_spriteset_name

    def handleLighting(self):
        """Give the variant a second sprite layer when its drawing carries lamps.

        The lighting overlay only makes sense with the sprite stack enabled, so the flag is added
        here; the switch that routes the stack sits in front of the generated part switch, which
        stays as layer 0's selector. A supplied `default` override wins, as everywhere else, and
        `lighting: none` (vehicle, profile or livery) suppresses the layer entirely.
        """
        if self.is_livery_refit:
            return
        if self.lighting_overlay_path is None or not self.spritesets:
            return
        if self.get_attr("lighting") == LIGHTING_NONE:
            # The project wants this variant's artwork left exactly as drawn.
            self.lighting_overlay_path = None
            self.lighting_transparent_path = None
            return
        if self.nml_override_callbacks() and "default" in self.nml_override_callbacks():
            return

        feature = getattr(getattr(self.vehicle_type, "nml_feature", None), "value", None)
        if str(feature).upper().endswith("ROADVEHS"):
            # road vehicles reverse without the train variables, so their side waits for a decision
            logger.debug(f"Lighting overlay found for road vehicle {self.identifier}; not emitted yet.")
            self.lighting_overlay_path = None
            self.lighting_transparent_path = None
            return

        self.add_misc_flag("TRAIN_FLAG_SPRITE_STACK")
        self.lighting_switch_name = f"{self.sprite_switch_name}_layers"
        self.callbacks["default"] = self.lighting_switch_name

    def nml_override_callbacks(self) -> set[str]:
        """Callback names this variant's YAML supplies itself, via `nml_override`."""
        return set(self.resolve_nml_override())

    def resolve_nml_override(self) -> dict:
        """Merge `nml_override` blocks vehicle first, then profile, then livery.

        Later sources win, matching how per-variant statistics resolve, so a livery can
        point one of its own variants at a different switch than the profile does.
        """
        merged: dict[str, str] = {}
        for source in (self.vehicle, self.profile, self.livery):
            merged.update(getattr(source, "nml_override", None) or {})
        return merged

    def handleNmlOverride(self):
        """Apply `nml_override` last so a supplied target beats a generated callback.

        The target is emitted verbatim, so this is the "just use this switch and don't
        generate one" escape hatch for a unit whose graphics chain BRBuild cannot model.
        """
        self.nml_override = self.resolve_nml_override()
        for callback, target in self.nml_override.items():
            self.callbacks[callback] = target

    def handleArticulated(self):
        count = self.resolved_vehicle_count()

        if count is not None and int(count) > 1:
            self.articulated_count = int(count)
            self.articulated_switch_name = f"switch_articulated_{self.identifier}"
            self.callbacks["articulated_part"] = self.articulated_switch_name
