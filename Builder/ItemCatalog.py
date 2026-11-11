"""Resolve cross-vehicle articulated items before candidate NML is written."""

from __future__ import annotations

from collections import defaultdict

from PropertyCalculation import VehicleType
from Vehicle import Variant, VariantIterator
from YamlHandler import VehicleLoader


class ItemCatalog:
    """Materialised variants and demand-generated feature-specific articulated parts."""

    def __init__(self, vehicles, vehicles_by_file=None):
        self.vehicles = list(vehicles)
        self._vehicles_by_file = vehicles_by_file or {}
        self._variants = {id(vehicle): list(VariantIterator(vehicle)) for vehicle in self.vehicles}
        self._hidden = defaultdict(list)
        self._hidden_by_key = {}
        self._vehicle_by_identifier = {}
        for vehicle in self.vehicles:
            key = self._normalise(vehicle.identifier)
            if key in self._vehicle_by_identifier:
                raise ValueError(f"Ambiguous vehicle identifier '{vehicle.identifier}'")
            self._vehicle_by_identifier[key] = vehicle
        self._resolve_all()

    @classmethod
    def from_candidates(cls, candidates, rail_type_table=None):
        vehicles = []
        by_file = {}
        for candidate in candidates:
            for filename in candidate.get("files", []):
                vehicle = VehicleLoader.load(filename)
                vehicle.rail_type_table = rail_type_table
                vehicles.append(vehicle)
                by_file[str(filename)] = vehicle
        return cls(vehicles, by_file)

    @classmethod
    def from_vehicles(cls, vehicles):
        return cls(vehicles)

    @staticmethod
    def _normalise(value):
        return str(value).replace("_", "").replace(" ", "").strip().casefold()

    def vehicle_for_file(self, filename):
        return self._vehicles_by_file[str(filename)]

    def variants_for(self, vehicle):
        return self._variants[id(vehicle)]

    def hidden_variants_for(self, vehicle):
        return self._hidden[id(vehicle)]

    def all_variants_for(self, vehicle):
        return self.variants_for(vehicle) + self.hidden_variants_for(vehicle)

    def _selection(self, reference):
        identifier = self._normalise(reference["vehicle"])
        target = self._vehicle_by_identifier.get(identifier)
        if target is None:
            raise ValueError(f"Articulated-part vehicle '{reference['vehicle']}' is missing")
        profile = self._select(
            target.profiles, "identifier", reference.get("profile"), "profile", target.identifier
        )
        livery = self._select(
            target.liveries, "name", reference.get("livery"), "livery", target.identifier
        )
        applicable_profiles = getattr(livery, "profiles", None) or []
        if applicable_profiles and not any(
            self._normalise(candidate) == self._normalise(profile.identifier)
            for candidate in applicable_profiles
        ):
            raise ValueError(
                f"Articulated-part vehicle '{target.identifier}' livery '{livery.name}' "
                f"does not apply to profile '{profile.identifier}'"
            )
        return target, profile, livery

    def _select(self, values, attribute, requested, kind, vehicle_identifier):
        if requested is None:
            if len(values) != 1:
                raise ValueError(
                    f"Articulated-part vehicle '{vehicle_identifier}' has ambiguous {kind}; specify {kind}"
                )
            return values[0]
        matches = [
            value for value in values
            if self._normalise(getattr(value, attribute)) == self._normalise(requested)
        ]
        if not matches:
            raise ValueError(
                f"Articulated-part vehicle '{vehicle_identifier}' has no {kind} '{requested}'"
            )
        if len(matches) != 1:
            raise ValueError(
                f"Articulated-part vehicle '{vehicle_identifier}' has ambiguous {kind} '{requested}'"
            )
        return matches[0]

    def _resolve_all(self):
        graph = {}
        selections = {}
        resolving_variants = [
            variant for vehicle in self.vehicles for variant in self.variants_for(vehicle)
        ]
        for variant in resolving_variants:
            references = self._articulated_references(variant)
            selected = [self._selection(ref) for ref in references]
            selections[id(variant)] = selected
            graph[id(variant)] = []
            for target, profile, livery in selected:
                matches = [
                    candidate for candidate in self.variants_for(target)
                    if not getattr(candidate, "is_livery_refit", False)
                    and candidate.profile is profile and candidate.livery is livery
                ]
                graph[id(variant)].extend(id(candidate) for candidate in matches)
        self._check_cycles(graph)

        for variant in resolving_variants:
            parts = []
            for target, profile, livery in selections[id(variant)]:
                projected = Variant(
                    target, livery, profile, vehicleType=variant.vehicle_type,
                    rail_type_table=getattr(target, "rail_type_table", None),
                )
                count = projected.resolved_vehicle_count() or 1
                for position in range(int(count)):
                    parts.append(
                        self._hidden_variant(
                            target, profile, livery, variant.vehicle_type, position
                        )
                    )
            if parts:
                variant.articulated_part_variants = parts

    def _articulated_references(self, variant):
        """Resolve authoring references, including aggregate livery-refit items."""
        if not getattr(variant, "is_livery_refit", False):
            return variant.get_attr("articulated_parts") or []

        applicable = [
            livery for livery in variant.vehicle.liveries
            if not livery.profiles
            or any(
                self._normalise(profile) == self._normalise(variant.profile.identifier)
                for profile in livery.profiles
            )
        ]
        resolved = [
            (
                livery.articulated_parts
                if livery.articulated_parts is not None
                else variant.profile.articulated_parts
                if variant.profile.articulated_parts is not None
                else variant.vehicle.articulated_parts
            ) or []
            for livery in applicable
        ]
        if not resolved:
            return []

        def canonical(references):
            return tuple(
                (
                    self._normalise(target.identifier),
                    self._normalise(profile.identifier),
                    self._normalise(livery.name),
                )
                for target, profile, livery in (
                    self._selection(reference) for reference in references
                )
            )

        expected = canonical(resolved[0])
        if any(canonical(references) != expected for references in resolved[1:]):
            raise ValueError(
                f"Livery Refits variant for profile '{variant.profile.identifier}' has "
                "different articulated_parts across applicable liveries"
            )
        return resolved[0]

    @staticmethod
    def _check_cycles(graph):
        visiting = set()
        visited = set()

        def visit(node):
            if node in visiting:
                raise ValueError("Cycle in articulated_parts references")
            if node in visited:
                return
            visiting.add(node)
            for target in graph.get(node, []):
                visit(target)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def _hidden_variant(self, vehicle, profile, livery, parent_type, position):
        parent_feature = getattr(parent_type, "nml_feature", str(parent_type))
        # Preserve tram semantics within FEAT_ROADVEHS; other projections only need their feature.
        projected_type = VehicleType.TRAM if parent_type == VehicleType.TRAM else parent_type
        key = (id(vehicle), id(profile), id(livery), parent_feature, projected_type, position)
        hidden = self._hidden_by_key.get(key)
        if hidden is not None:
            return hidden
        hidden = Variant(
            vehicle, livery, profile, vehicleType=projected_type,
            rail_type_table=getattr(vehicle, "rail_type_table", None),
        )
        raw = (
            f"hidden_part_{vehicle.identifier}_{profile.identifier}_{livery.name}_"
            f"{projected_type.name}_pos{position + 1}"
        ).lower()
        import re
        hidden.hidden_identifier_base = re.sub(r"[^a-z0-9_]", "_", raw)
        hidden.identifier = hidden.hidden_identifier_base
        hidden.nml_filename = f"{hidden.identifier}.gnml"
        hidden.hidden_articulated_part = True
        hidden.suppress_articulated = True
        hidden.target_part_position = position
        hidden.registry_profile_identifier = (
            f"__part_{profile.identifier}_{projected_type.name}_pos{position + 1}"
        )
        self._hidden_by_key[key] = hidden
        self._hidden[id(vehicle)].append(hidden)
        return hidden
