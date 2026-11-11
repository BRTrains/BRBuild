"""Process discovered candidates and their generated variants."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

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
        self._pending_variants = []

    def process_candidates(self, ctx: BuildContext):
        if not ctx.candidates:
            raise RuntimeError("No candidates found")

        self._pending_variants = []
        for candidate in ctx.candidates:
            self.process_candidate(candidate, ctx)

        self._prune_failed_dependencies(ctx)
        self._write_variants(ctx)

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
            vehicle = (
                ctx.item_catalog.vehicle_for_file(file)
                if ctx.item_catalog is not None
                else VehicleLoader.load(file)
            )
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
            variants = (
                ctx.item_catalog.all_variants_for(vehicle)
                if ctx.item_catalog is not None
                else list(VariantIterator(vehicle))
            )
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
                            spritesets, template_names, lengths = allocator.get(
                                variant.profile, variant.livery, variant.vehicle_type
                            )
                            pattern = allocator.pattern_for(variant.profile, variant.livery)
                            if getattr(variant, "hidden_articulated_part", False):
                                variant.pin_articulated_position(
                                    spritesets, template_names, lengths, pattern
                                )
                            else:
                                variant.spritesets = spritesets
                                variant.sprite_template_names = template_names
                                variant.sprite_lengths = lengths
                                variant.sprite_pattern = pattern
                        if getattr(variant, "hidden_articulated_part", False):
                            purchase = None
                        else:
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
                    variant.registry_profile_identifier or variant.profile.identifier,
                    variant.livery.name,
                    self.builder._vehicle_type_name(variant.vehicle_type),
                    self.builder._compatibility_snapshot(variant),
                )
                variant.sprite_id = assignment["id"]
                variant.sprite_id_generation = assignment["generation"]
                self._set_disable_conditions(variant, vehicle, ctx.grf)

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
                self._pending_variants.append((vehicle, variant, assignment))

            if failed_variant_ids:
                ctx.failed_units.add(vehicle.identifier)
                self._pending_variants = [
                    pending for pending in self._pending_variants if pending[0] is not vehicle
                ]
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

    @staticmethod
    def _set_disable_conditions(variant, vehicle, grf):
        """Apply purchase visibility controls only to independently purchasable items."""
        variant.disable_item_condition = None
        variant.disable_item_conditions = []
        if getattr(variant, "hidden_articulated_part", False):
            return

        variant.disable_item_condition = disable_condition(
            vehicle.vehicle_type,
            variant.vehicle_type,
            vehicle.usage,
            getattr(grf, "usage_filters", None),
        )
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

    def _prune_failed_dependencies(self, ctx: BuildContext):
        """Drop parents with unavailable hidden parts, then remove unused hidden items."""
        available = {id(variant) for _, variant, _ in self._pending_variants}
        failed = []
        for record in self._pending_variants:
            vehicle, variant, _ = record
            dependencies = getattr(variant, "articulated_part_variants", None) or []
            missing = [part for part in dependencies if id(part) not in available]
            if not missing:
                continue
            failed.append(record)
            error = (
                f"Required hidden articulated part '{missing[0].identifier or missing[0].vehicle.identifier}' "
                "did not build successfully"
            )
            ctx.failed_variants.append(repr(variant))
            ctx.failed_units.add(vehicle.identifier)
            self.builder._record_failure(
                ctx, vehicle, variant, "articulated dependency", error
            )

        failed_ids = {id(variant) for _, variant, _ in failed}
        remaining = [
            record for record in self._pending_variants
            if id(record[1]) not in failed_ids
        ]
        referenced_hidden = {
            id(part)
            for _, variant, _ in remaining
            for part in (getattr(variant, "articulated_part_variants", None) or [])
        }
        self._pending_variants = [
            record for record in remaining
            if not getattr(record[1], "hidden_articulated_part", False)
            or id(record[1]) in referenced_hidden
        ]

    def _write_variants(self, ctx: BuildContext):
        """Write the complete pending batch before publishing any registry success."""
        staged = []
        failed_vehicle = None
        failed_variant = None
        with TemporaryDirectory(
            dir=ctx.nml_output_folder, prefix=".variant-batch-"
        ) as staging_folder:
            try:
                for vehicle, variant, assignment in self._pending_variants:
                    failed_vehicle = vehicle
                    failed_variant = variant
                    writer = NmlVariantWriter(
                        variant,
                        staging_folder,
                        ctx.template_alignment_param_index
                        if ctx.template_alignment_param_index is not None else 4,
                    )
                    staged.append((vehicle, variant, assignment, writer.write()))
            except Exception as exc:
                assert failed_vehicle is not None and failed_variant is not None
                logger.exception(f"Unable to write NML for variant {failed_variant}: {exc}")
                ctx.failed_variants.append(repr(failed_variant))
                ctx.failed_units.add(failed_vehicle.identifier)
                self.builder._record_failure(
                    ctx, failed_vehicle, failed_variant, "NML writing", exc
                )
                raise

            written = []
            for vehicle, variant, assignment, staged_file in staged:
                final_path = Path(ctx.nml_output_folder) / variant.nml_filename
                Path(staged_file).replace(final_path)
                written.append((vehicle, variant, assignment, str(final_path)))

        for vehicle, variant, assignment, nml_file in written:
            ctx.nml_files.append(nml_file)
            ctx.variant_owners[str(nml_file)] = vehicle.identifier
            ctx.sprite_id_registry.mark_written(assignment)
            ctx.sprite_id_registry.archive_variant(
                assignment,
                nml_file,
                dict(_registry.items()),
                variant.identifier,
            )
            ctx.successful_variants.append(variant)

