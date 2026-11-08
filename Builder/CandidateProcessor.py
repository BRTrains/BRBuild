"""Process discovered candidates and their generated variants."""

import logging
from pathlib import Path

from Lang.StringRegistry import _registry
from NmlWriter import NmlVariantWriter
from Sprites.LightingOverlay import VehicleLighting
from Vehicle import VariantIterator
from Vehicle.UsageVisibility import disable_condition
from YamlHandler import VehicleLoader
from .BuildContext import BuildContext

logger = logging.getLogger(__name__)


class CandidateProcessor:
    """Own candidate-to-variant processing while delegating shared services to Builder."""

    def __init__(self, builder):
        self.builder = builder

    def process_candidates(self, ctx: BuildContext):
        if not ctx.candidates:
            raise RuntimeError("No candidates found")

        for candidate in ctx.candidates:
            self.process_candidate(candidate, ctx)

        if len(ctx.successful_variants) == 0:
            raise RuntimeError(f"No successful variants were generated for project '{ctx.project.name}'. Halting build process.")
        if ctx.failed_variants:
            logger.warning(
                f"{len(ctx.failed_variants)} variant(s) failed for project "
                f"'{ctx.project.name}'; continuing with successful variants."
            )


    def process_candidate(self, candidate, ctx: BuildContext):
        logger.info(f"Processing candidate: {candidate.get('name')}")

        for file in candidate.get("files", []):
            logger.debug(f"\tParsing YAML file: {file}")
            vehicle = VehicleLoader.load(file)
            vehicle.rail_type_table = ctx.rail_type_table
            logger.debug(
                f"\tLoaded vehicle: {vehicle.name} with identifier {vehicle.identifier}, "
                f"{len(vehicle.profiles)} profiles, and {len(vehicle.liveries)} liveries."
            )

            # A candidate folder's own NML is keyed by its loaded vehicle identifier (not the
            # folder name, which need not match it) so the collator can place it immediately
            # before the blocks of the vehicle that uses it.
            for pnml in candidate.get("pnml_files", []):
                logger.debug(f"\tFound manual PNML file: {pnml}")
                staged = self.builder._stage_candidate_nml(pnml, ctx)
                files_for_vehicle = ctx.vehicle_nml_files.setdefault(vehicle.identifier, [])
                if staged not in files_for_vehicle:
                    files_for_vehicle.append(staged)

            ingested_new_spritesheet = self.builder._ingest_new_spritesheet(vehicle, ctx)
            has_spritesheet = self.builder._has_any_sheet(vehicle)
            # A unit without any usable PNG is necessarily unfinished (or a utility/debug
            # definition whose artwork has not landed yet). Keep it in the GRF for development
            # mode, but hide it by default just like an explicitly flagged unit.
            vehicle.development = bool(vehicle.development) or not has_spritesheet
            if not has_spritesheet:
                self.builder._record_failure(
                    ctx,
                    vehicle,
                    None,
                    "development mode",
                    f"No {vehicle.identifier}.png spritesheet found",
                )
            allocator = None
            variant_groups = {}

            if has_spritesheet:
                allocator = self.builder._load_sprite_allocator(vehicle, ctx, normalize=ingested_new_spritesheet)
                if allocator is None:
                    logger.error(
                        f"Skipping vehicle '{vehicle.identifier}': unable to confidently identify spritesets "
                        f"in '{vehicle.spritesheet_path}'."
                    )
                    ctx.failed_variants.append(f"{vehicle.identifier} (spritesheet)")
                    ctx.failed_units.add(vehicle.identifier)
                    self.builder._record_failure(
                        ctx,
                        vehicle,
                        None,
                        "sprite allocation",
                        "Unable to resolve required spritesets from spritesheet",
                    )
                    continue

            # Materialised so the lighting overlays for every variant can be resolved before any of
            # them is written: one overlay sheet per published sheet holds the union of their lamps.
            # A candidate whose profiles name spritesheets of their own gets one detector per sheet.
            # Cost scale is a GRF-level setting, but variants are the calculation boundary.
            # Keep it on the candidate so direct Variant/CostCalculator callers retain the
            # same default when no project context is present.
            vehicle.cost_scale = ctx.grf.cost_scale
            variants = list(VariantIterator(vehicle))
            failed_variant_ids = set()
            lightings: dict[str, VehicleLighting] = {}
            if allocator is not None and variants:
                for sheet in self.builder._declared_sheets(vehicle, resolved=True):
                    if not Path(sheet).is_file():
                        # A candidate can declare a sheet nothing draws from yet.
                        continue
                    lightings[str(sheet)] = VehicleLighting(
                        vehicle,
                        ctx.palette,
                        self.builder._get_template_definitions(ctx),
                        ctx.nml_output_folder,
                        sheet_path=sheet,
                    )

            for variant in variants:
                logger.debug(
                    f"\tGenerated variant: {variant.vehicle.name}, using livery {variant.livery.name} "
                    f"and profile {variant.profile.identifier}"
                )

                refit_liveries = []
                if allocator is not None:
                    try:
                        if getattr(variant, "is_livery_refit", False):
                            variant.refit_groups = []
                            refit_liveries = [
                                livery for livery in vehicle.liveries
                                if not livery.profiles
                                or str(variant.profile.identifier).lower() in {
                                    str(item).lower() for item in livery.profiles
                                }
                            ]
                            for livery in refit_liveries:
                                group = allocator.get(variant.profile, livery, variant.vehicle_type)
                                variant.refit_groups.append((livery.name, *group))
                            if not variant.refit_groups:
                                raise ValueError(f"No livery refits apply to profile {variant.profile.identifier}")
                            first = variant.refit_groups[0]
                            variant.spritesets, variant.sprite_template_names, variant.sprite_lengths = first[1:]
                            variant.sprite_pattern = allocator.pattern_for(variant.profile, refit_liveries[0])
                        else:
                            variant.spritesets, variant.sprite_template_names, variant.sprite_lengths = allocator.get(
                                variant.profile, variant.livery, variant.vehicle_type
                            )
                            variant.sprite_pattern = allocator.pattern_for(variant.profile, variant.livery)
                        purchase_livery = (
                            refit_liveries[0] if getattr(variant, "is_livery_refit", False) else variant.livery
                        )
                        purchase = allocator.get_purchase(
                            variant.profile, purchase_livery, ctx.nml_output_folder
                        )
                        variant.purchase_spriteset, variant.purchase_template_name = purchase if purchase else (None, None)
                    except Exception as exc:
                        logger.exception(f"Unable to assign sprites for variant {variant}: {exc}")
                        ctx.failed_variants.append(repr(variant))
                        failed_variant_ids.add(id(variant))
                        self.builder._record_failure(ctx, vehicle, variant, "sprite allocation", exc)
                        continue

                if (
                    allocator is not None
                    and not getattr(variant, "is_livery_refit", False)
                    and variant.spritesets
                ):
                    lighting = lightings.get(str(allocator.sheet_for(variant.profile, variant.livery)))
                    if lighting is not None:
                        variant.lighting_detection = lighting.detection_for(
                            self.builder._variant_parts(variant),
                            trailing_only=bool(variant.get_attr("has_cab")),
                        )

            if allocator is not None:
                self.builder._assume_lighting_patterns(variants, allocator, lightings)

            for lighting in lightings.values():
                lighting.write_images()

            for variant in variants:
                if id(variant) in failed_variant_ids:
                    continue
                lighting = (
                    lightings.get(str(allocator.sheet_for(variant.profile, variant.livery)))
                    if allocator is not None
                    else None
                )
                if (
                    lighting is not None
                    and variant.lighting_detection is not None
                    and variant.lighting_detection.pixels
                ):
                    variant.lighting_overlay_path = lighting.overlay_path
                    variant.lighting_transparent_path = lighting.transparent_path
                assignment = ctx.sprite_id_registry.resolve(
                    vehicle.identifier,
                    variant.profile.identifier,
                    variant.livery.name,
                    self.builder._vehicle_type_name(variant.vehicle_type),
                    self.builder._compatibility_snapshot(variant),
                )
                variant.sprite_id = assignment["id"]
                variant.sprite_id_generation = assignment["generation"]
                variant.disable_item_condition = disable_condition(
                    vehicle.vehicle_type,
                    variant.vehicle_type,
                    vehicle.usage,
                    getattr(ctx.grf, "usage_filters", None),
                )
                variant.disable_item_conditions = []
                if variant.disable_item_condition:
                    variant.disable_item_conditions.append(variant.disable_item_condition)
                if vehicle.development:
                    variant.disable_item_conditions.append(
                        (variant.vehicle_type.nml_feature, "param_development_mode == 0")
                    )
                if getattr(variant, "is_livery_refit", False):
                    variant.disable_item_conditions.append(
                        (variant.vehicle_type.nml_feature, "param_livery_mode == 0")
                    )
                else:
                    variant.disable_item_conditions.append(
                        (variant.vehicle_type.nml_feature, "param_livery_mode == 1")
                    )

                try:
                    variant.process()
                except Exception as exc:
                    logger.exception(f"Error processing variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    failed_variant_ids.add(id(variant))
                    self.builder._record_failure(ctx, vehicle, variant, "variant processing", exc)
                    continue

                if getattr(variant, "is_livery_refit", False):
                    variant.refit_switches = []
                    applicable_liveries = [
                        livery for livery in vehicle.liveries
                        if not livery.profiles
                        or str(variant.profile.identifier).lower() in {
                            str(item).lower() for item in livery.profiles
                        }
                    ]
                    for livery in applicable_liveries:
                        source = next(
                            (
                                candidate for candidate in variants
                                if not getattr(candidate, "is_livery_refit", False)
                                and candidate.profile is variant.profile
                                and candidate.livery is livery
                                and candidate.vehicle_type == variant.vehicle_type
                                and candidate.callbacks.get("default")
                            ),
                            None,
                        )
                        if source is not None:
                            variant.refit_switches.append(
                                (livery.name, source.callbacks["default"])
                            )

                self.builder._assign_variant_group(variant, variant_groups)

                try:
                    variant_writer = NmlVariantWriter(
                        variant, ctx.nml_output_folder,
                        ctx.template_alignment_param_index if ctx.template_alignment_param_index is not None else 4,
                    )
                    nml_file = variant_writer.write()
                    ctx.nml_files.append(nml_file)
                    ctx.variant_owners[str(nml_file)] = vehicle.identifier
                    ctx.sprite_id_registry.mark_written(assignment)
                    ctx.sprite_id_registry.archive_variant(
                        assignment,
                        nml_file,
                        dict(_registry.items()),
                        variant.identifier,
                    )
                except Exception as exc:
                    logger.exception(f"Unable to write NML for variant {variant}: {exc}")
                    ctx.failed_variants.append(repr(variant))
                    failed_variant_ids.add(id(variant))
                    self.builder._record_failure(ctx, vehicle, variant, "NML writing", exc)
                    continue

                ctx.successful_variants.append(variant)

            if failed_variant_ids:
                ctx.failed_units.add(vehicle.identifier)
                failed_nml = {
                    path for path, owner in ctx.variant_owners.items() if owner == vehicle.identifier
                }
                ctx.nml_files = [path for path in ctx.nml_files if str(path) not in failed_nml]
                for path in failed_nml:
                    ctx.variant_owners.pop(path, None)
                ctx.successful_variants = [
                    variant for variant in ctx.successful_variants
                    if getattr(getattr(variant, "vehicle", None), "identifier", None) != vehicle.identifier
                ]

