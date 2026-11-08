"""Inject BRBuild-owned GRF parameters and global actions."""


class GrfParameterInjector:
    """Keep builder-owned parameters ahead of project-owned parameters."""

    @staticmethod
    def ensure_cost_parameters(grf):
        """Inject separate runtime purchase/running-cost parameters first."""
        choices = {
            0: "1/4",
            1: "1/3",
            2: "1/2",
            3: "1x",
            4: "2x",
            5: "3x",
            6: "4x",
        }
        definitions = [
            ("param_running_cost_multiplier", "Running Cost Multiplier"),
            ("param_purchase_cost_multiplier", "Purchase Cost Multiplier"),
        ]

        # Remove the previous combined parameter if a caller is reusing a loaded
        # config object from the earlier builder version.
        grf.params[:] = [param for param in grf.params if param.get("identifier") != "param_cost_multiplier"]
        for identifier, name in reversed(definitions):
            existing = next((param for param in grf.params if param.get("identifier") == identifier), None)
            if existing is None:
                existing = {
                    "identifier": identifier,
                    "name_str": name,
                    "desc_str": f"Adjust {name.lower()}",
                    "min_value": 0,
                    "max_value": 6,
                    "def_value": 3,
                    "names": choices,
                }
            else:
                grf.params.remove(existing)
            grf.params.insert(0, existing)

    @staticmethod
    def ensure_general_parameters(grf):
        """Inject shared speed, capacity, and default-vehicle controls first."""
        definitions = [
            (
                "param_wagon_speed_limits",
                "Wagon Speed Limits",
                "Enable or disable speed limits on unpowered coaches and wagons",
                0,
                1,
                1,
                {0: "Disabled", 1: "Enabled"},
            ),
            (
                "param_speed_mode",
                "Speed Mode",
                "Use each unit's design speed, or its permitted service speed",
                0,
                1,
                1,
                {0: "Service Speed", 1: "Design Speed"},
            ),
            (
                "param_passenger_multiplier",
                "Passenger Capacity Multiplier",
                "Increase capacities of passenger vehicles",
                1,
                4,
                1,
                {1: "1x", 2: "2x", 3: "3x", 4: "4x"},
            ),
            (
                "param_mail_multiplier",
                "Mail Capacity Multiplier",
                "Increase capacities of mail vehicles",
                1,
                4,
                1,
                {1: "1x", 2: "2x", 3: "3x", 4: "4x"},
            ),
            (
                "param_freight_multiplier",
                "Freight Capacity Multiplier",
                "Increase capacities of freight vehicles",
                1,
                4,
                1,
                {1: "1x", 2: "2x", 3: "3x", 4: "4x"},
            ),
            (
                "param_disable_default_trains",
                "Hide Default OpenTTD trains?",
                "Hide the default OpenTTD trains from the vehicle list",
                0,
                1,
                1,
                {0: "Show Default OpenTTD trains", 1: "Hide Default OpenTTD trains"},
            ),
            (
                "param_disable_default_roadvehicles",
                "Hide Default OpenTTD road vehicles?",
                "Hide the default OpenTTD road vehicles from the vehicle list",
                0,
                1,
                1,
                {0: "Show Default OpenTTD road vehicles", 1: "Hide Default OpenTTD road vehicles"},
            ),
            (
                "param_development_mode",
                "Development Mode",
                "Show units marked as work in progress or development units",
                0,
                1,
                0,
                {0: "Off", 1: "On"},
            ),
            (
                "param_livery_mode",
                "Livery Mode",
                "Choose separate variants, livery refits, or both",
                0,
                2,
                0,
                {0: "Variants", 1: "Livery Refits", 2: "Both"},
            ),
        ]

        builder_ids = {
            "param_wagon_speed_limits",
            "param_running_cost_multiplier",
            "param_purchase_cost_multiplier",
            "param_passenger_multiplier",
            "param_mail_multiplier",
            "param_freight_multiplier",
            "param_disable_default_trains",
            "param_disable_default_roadvehicles",
            "param_development_mode",
            "param_livery_mode",
            "param_align_with",
        }
        # Remove legacy combined/default-vehicle identifiers before re-inserting the
        # canonical builder-owned definitions.
        legacy_ids = {"param_disable_default_vehicles"}
        grf.params[:] = [param for param in grf.params if param.get("identifier") not in legacy_ids]
        insertion_index = next(
            (index for index, param in enumerate(grf.params) if param.get("identifier") not in builder_ids),
            len(grf.params),
        )
        for identifier, name, description, minimum, maximum, default, names in definitions:
            existing = next((param for param in grf.params if param.get("identifier") == identifier), None)
            if existing is not None:
                grf.params.remove(existing)
            else:
                existing = {
                    "identifier": identifier,
                    "name_str": name,
                    "desc_str": description,
                    "min_value": minimum,
                    "max_value": maximum,
                    "def_value": default,
                    "names": names,
                }
            grf.params.insert(insertion_index, existing)
            insertion_index += 1

        grf.global_actions[:] = [
            action
            for action in grf.global_actions
            if action.get("condition")
            not in {
                "param_disable_default_trains == 1",
                "param_disable_default_roadvehicles == 1",
                "param_disable_default_vehicles == 1",
            }
        ]
        actions = [
            {"condition": "param_disable_default_trains == 1", "action": "disable_item(FEAT_TRAINS)"},
            {
                "condition": "param_disable_default_roadvehicles == 1",
                "action": "disable_item(FEAT_ROADVEHS)",
            },
        ]
        grf.global_actions[0:0] = actions

    @staticmethod
    def ensure_template_alignment_param(grf):
        existing = [param for param in grf.params if param.get("identifier") == "param_align_with"]
        managed_ids = {
            "param_running_cost_multiplier",
            "param_purchase_cost_multiplier",
            "param_align_with",
        }
        if existing:
            parameter = existing[0]
            grf.params.remove(parameter)
            insertion_index = next(
                (index for index, param in enumerate(grf.params) if param.get("identifier") not in managed_ids),
                len(grf.params),
            )
            grf.params.insert(insertion_index, parameter)
            return insertion_index
        insertion_index = next(
            (index for index, param in enumerate(grf.params) if param.get("identifier") not in managed_ids),
            len(grf.params),
        )
        grf.params.insert(
            insertion_index,
            {
                "identifier": "param_align_with",
                "name_str": "Align with",
                "desc_str": "Choose the sprite offset alignment convention",
                "min_value": 0,
                "max_value": 1,
                "def_value": 1,
                "names": {0: "Generic", 1: "Iron Horse"},
            },
        )
        return insertion_index
