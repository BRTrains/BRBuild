# NML Vehicles Reference

Source: GRFSpecs — NML:Vehicles
Source page: https://newgrf-specs.tt-wiki.net/wiki/NML:Vehicles
Page last modified: 30 July 2026

This is an LLM-oriented Markdown reference derived from the NML Vehicles specification. It preserves the documented names, ranges, flags, callback names, variables and behavioural rules while removing wiki navigation and presentation markup.

---

## 1. Common vehicle properties

These properties apply to all vehicle types unless otherwise stated.

| Property | Range / type | Articulated | Notes |
|---|---|---|---|
| `name` | string | Yes | Vehicle name, e.g. `string(STR_NAME_HEREFORD_TRAM)`. |
| `climates_available` | climate bitmask | Yes | `CLIMATE_TEMPERATE`, `CLIMATE_ARCTIC`, `CLIMATE_TROPICAL`, `CLIMATE_TOYLAND`, `NO_CLIMATE`, `ALL_CLIMATES`. `NO_CLIMATE` is useful for articulated parts. `ALL_CLIMATES & ~bitmask(CLIMATE_TOYLAND)` means all climates except Toyland. |
| `introduction_date` | `date(yyyy, mm, dd)` | No | Year range 0..5,000,000. TTDPatch limits dates after 2044 to 2044. Unless introduced within two years of game start, a random 0..511 days is added. |
| `model_life` | 0..254 years or `VEHICLE_NEVER_EXPIRES` | No | Number of years the manufacturer supports the model. |
| `retire_early` | -128..127 years | No | Retires the vehicle from the purchase menu this many years before reliability starts dropping. May be negative. |
| `vehicle_life` | 0..255 years | No | Lifetime of an individual vehicle before it is considered too old. |
| `reliability_decay` | 0..255 | No | Higher values cause reliability to decay faster. Default is 20. `0` prevents reliability decreasing due to age, provided the vehicle is not too old. |
| `refittable_cargo_classes` | cargo-class bitset | Yes | Example: `bitmask(CC_BULK, CC_COVERED)`. |
| `non_refittable_cargo_classes` | cargo-class bitset | Yes | Example: `bitmask(CC_OVERSIZED, CC_SPECIAL)`. |
| `refittable_cargo_types` | cargo translation-table bitmask | Yes | Deprecated since NML 0.3; use `cargo_allow_refit` / `cargo_disallow_refit`. |
| `cargo_allow_refit` | cargo-label array | Yes | NML 1.2. Explicitly allows listed cargo types regardless of cargo class. Example: `[COAL, IORE]`. |
| `cargo_disallow_refit` | cargo-label array | Yes | NML 1.2. Explicitly disallows listed cargo types regardless of cargo class. Example: `[MAIL]`. |
| `loading_speed` | 0..255 cargo units | Yes | Cargo loaded/unloaded per loading interval. Defaults: trains/road vehicles 5, ships 10, aircraft 20. Intervals are 40 ticks for trains, 20 for road vehicles/aircraft and 10 for ships. |
| `cost_factor` | 0..255 | Set to 0 | Multiplier for base purchase cost. |
| `running_cost_factor` | 0..255 | Set to 0 | Multiplier for base running cost. |
| `cargo_age_period` | 0..65535 ticks | Yes | NML 1.2. Cargo ages after this many ticks. Default 185; 74 ticks = 1 day. `0` disables ageing. The documented warning is to avoid this property unless the OpenTTD cargo-ageing algorithm is understood. |
| `variant_group` | vehicle ID / numeric ID 0..65535 | No | NML 13. Groups vehicles in purchase and autoreplace menus. Value identifies the parent vehicle in the same GRF. Groups may be nested; this was experimental as of the documentation date. |
| `extra_flags` | vehicle flag bitmask | No | NML 13. Common vehicle flags. |
| `badges` | badge-label array | Yes | NML 15.0. Example: `["power/electric", "flag/GB"]`. |

### Common `extra_flags`

- `VEHICLE_FLAG_DISABLE_NEW_VEHICLE_MESSAGE` — suppress the "New Vehicle" news message.
- `VEHICLE_FLAG_DISABLE_EXCLUSIVE_PREVIEW` — suppress the exclusive preview.
- `VEHICLE_FLAG_SYNC_VARIANT_EXCLUSIVE_PREVIEW` — include this variant when the primary engine has exclusive preview.
- `VEHICLE_FLAG_SYNC_VARIANT_RELIABILITY` — attempt to synchronise variant reliability with the primary engine.

### Refittability

A cargo is refittable when:

```text
((cargo classes intersect refittable_cargo_classes
  AND cargo classes do not intersect non_refittable_cargo_classes)
 OR cargo is in cargo_allow_refit)
AND cargo is not in cargo_disallow_refit
```

Equivalent decision table:

| Refittable classes match | Non-refittable classes match | Explicit allow | Explicit deny | Result |
|---|---|---|---|---|
| Yes | No | Any | No | Refittable |
| No | Any | No | Any | Not refittable |
| Any | Any | Yes | No | Refittable |
| Any | Any | Any | Yes | Not refittable |

Recommended use:

1. Use `refittable_cargo_classes` and `non_refittable_cargo_classes` for the general cargo policy.
2. Use `cargo_allow_refit` and `cargo_disallow_refit` for specific exceptions.

### Vehicle model life cycle

Each new game randomises the duration and reliability boundaries.

| Phase | Duration | Reliability |
|---|---|---|
| 1 | 7–38 months | Increases from 48–73% to 75–100% |
| 2 | `model_life - 8 years + 0–15 months` | Constant at 75–100% peak |
| 3 | 10–20.6 years | Decreases from peak to 25–50% |

`model_life` therefore does not represent the complete length of the peak-reliability phase: phase 2 is approximately 8 years shorter.

With `VEHICLE_NEVER_EXPIRES`, phase 2 continues indefinitely.

Normally a vehicle is removed from the purchase menu at the end of phase 3. `retire_early` changes this by retiring it the specified number of years before (or after, if negative) the end of phase 2.

---

# 2. Train properties

| Property | Range / type | Articulated | Notes |
|---|---|---|---|
| `sprite_id` | `SPRITE_ID_NEW_TRAIN` | Yes | Enables new graphics. |
| `speed` | 0..65000 speed units | No | Maximum speed for engines; speed limit for wagons. |
| `misc_flags` | `TRAIN_FLAG_*` bitmask | Partly | `FLIP` should not be set. `TILT` and `MU` should match the first part. |
| `extra_flags` | `VEHICLE_FLAG_*` | Yes | Includes common vehicle flags. |
| `refit_cost` | 0..255 | Yes | Units of 50% of the purchase-price cost base. |
| `callback_flags` | `VEH_CBF_*` bitmask | Yes | Do not set unless using old-style callbacks. |
| `track_type` | railtype-table item | First part determines consist | NML 15 uses an array of railtype labels. Older syntax uses the railtype table. Default table: `RAIL`, `MONO`, `MGLV`. If no custom railtype table exists and an electric train is required, use `RAIL` plus `ENGINE_CLASS_ELECTRIC`. |
| `ai_special_flag` | `AI_FLAG_PASSENGER` / `AI_FLAG_CARGO` | No | Advises the AI whether the engine is intended for passenger or cargo service. |
| `power` | 0..65000 hp | Set to 0 | Engine power. |
| `running_cost_base` | `RUNNING_COST_*` | Set to `RUNNING_COST_NONE` | Base running-cost category. |
| `dual_headed` | 0/1 | Set to 0 for articulated parts | `1` creates a dual-headed engine. |
| `default_cargo_type` | cargo label or `DEFAULT_CARGO_FIRST_REFITTABLE` | Yes | Determines the default cargo. If refittable and the selected cargo is unavailable or the special constant is used, the first refittable cargo in cargo-table order is selected. |
| `cargo_capacity` | 0..255 | Yes | Base capacity. By default, passenger capacity is multiplied by 4 and mail/goods capacity by 2 relative to other cargoes. Use the `cargo_capacity` callback to override this behaviour. |
| `weight` | 0..1279 t | Set to 0 | Vehicle mass. |
| `ai_engine_rank` | 0..255 | No | TTDPatch AI preference ranking; higher means more attractive. |
| `engine_class` | `ENGINE_CLASS_*` | No | Controls livery colour settings, default sound and, unless overridden, visual effect. |
| `extra_power_per_wagon` | 0..65000 hp | Set to 0 | Adds power from powered wagons with a livery override for this engine. |
| `tractive_effort_coefficient` | 0..1 | Set to 0 | Fraction of vehicle weight available as tractive effort. Train TE in kN is approximately `coefficient * 9.8 * weight_tonnes`. |
| `air_drag_coefficient` | 0..1 | Set to 0 | Relative aerodynamic drag. Default approximately `8 / max_speed_kmh`, clamped to 0.004..0.75. |
| `length` | 1..8 | Yes | Vehicle length in arbitrary units. `8` equals `VEHICLE_LENGTH` and represents a full-length vehicle. |
| `visual_effect_and_powered` | `visual_effect_and_powered(...)` | Yes | Simple visual-effect method, with optional wagon power. Mutually exclusive with the `effect_spawn_model_and_powered` method for the same item. |
| `effect_spawn_model_and_powered` | `EFFECT_SPAWN_MODEL_*` with optional `ENABLE_WAGON_POWER` | Yes | Advanced visual-effect method used with `create_effect`. Mutually exclusive with `visual_effect_and_powered`. |
| `extra_weight_per_wagon` | 0..255 t | Set to 0 | Adds weight for powered wagons; related to `extra_power_per_wagon`. |
| `bitmask_vehicle_info` | 8-bit bitmask | Yes | Used by `bitmask_consist_info`. |
| `curve_speed_mod` | -128..127.996 | Yes | NML 0.7 / OpenTTD 12.0. Applied after normal curve-speed calculation: `max_curve_speed * (1 + curve_speed_mod)`. Negative values are allowed but the result is clamped to roughly 2 mph. If train parts differ, the lowest modifier wins. |

### Train flags

- `TRAIN_FLAG_TILT` — enables the 20% curve-speed tilt bonus when all vehicles in the consist have it.
- `TRAIN_FLAG_2CC` — enables the second company colour.
- `TRAIN_FLAG_MU` — identifies a multiple-unit vehicle for livery selection.
- `TRAIN_FLAG_FLIP` — historically enabled reversing in depots. Since NML/OpenTTD 13 this is no longer required; flipping is generally always allowed except where prohibited by multi-header/articulated constraints.
- `TRAIN_FLAG_AUTOREFIT` — allows autorefit if the `refit_cost` callback permits it or, when that callback is absent/fails, `refit_cost` is zero.
- `TRAIN_FLAG_NO_BREAKDOWN_SMOKE` — disables breakdown smoke.
- `TRAIN_FLAG_SPRITE_STACK` — NML 1.7; enables multiple-sprite vehicle composition.

`VEHICLE_FLAG_TRAIN_HAS_CAB` allows a train wagon with a cab to lead a train when driving backwards without the normal speed reduction.

### Train engine classes

- `ENGINE_CLASS_STEAM`
- `ENGINE_CLASS_DIESEL`
- `ENGINE_CLASS_ELECTRIC`
- `ENGINE_CLASS_MONORAIL`
- `ENGINE_CLASS_MAGLEV`

### Train visual effects

`VISUAL_EFFECT_DEFAULT`, `VISUAL_EFFECT_STEAM`, `VISUAL_EFFECT_DIESEL`, `VISUAL_EFFECT_ELECTRIC`, `VISUAL_EFFECT_DISABLE`.

Effect offset range is `-8..7`; zero is the default. Negative is towards the front and positive towards the rear.

Effect spawning models:

- `EFFECT_SPAWN_MODEL_NONE`
- `EFFECT_SPAWN_MODEL_STEAM` — progressively fewer effects near maximum speed.
- `EFFECT_SPAWN_MODEL_DIESEL` — proportional to acceleration; no effect while idling at top speed.
- `EFFECT_SPAWN_MODEL_ELECTRIC` — random effect, with lower probability near maximum speed.

---

# 3. Road vehicle properties

| Property | Range / type | Articulated | Notes |
|---|---|---|---|
| `sprite_id` | `SPRITE_ID_NEW_ROADVEH` | Yes | Enables new graphics. |
| `speed` | 0..511 km/h | No | Speed value is a float/speed-unit property. |
| `road_type` / `tram_type` | roadtype/tramtype-table item | Same as front | Only one may be set. `tram_type` requires `ROADVEH_FLAG_TRAM`. If unset, road vehicles default to `ROAD`; trams default to `RAIL` (which is distinct from railtype `RAIL`). |
| `misc_flags` | `ROADVEH_FLAG_*` bitmask | Partly | The tram flag must be consistent across articulated parts. |
| `refit_cost` | 0..255 | Yes | Units of 25% of purchase-price cost base. |
| `callback_flags` | `VEH_CBF_*` bitmask | Yes | Only for old-style callbacks. |
| `running_cost_base` | `RUNNING_COST_*` | Set to `RUNNING_COST_NONE` | Base running-cost category. |
| `power` | 0..2550 hp | Set to 0 | Engine power. |
| `weight` | 0..63.75 t | Set to 0 | Vehicle mass. |
| `tractive_effort_coefficient` | 0..1 | Set to 0 | TE approximately `coefficient * 10 * weight_tonnes` kN. Default is 0.3. |
| `air_drag_coefficient` | 0..1 | Set to 0 | Default approximately `8 / max_speed_kmh`, clamped to 0.004..0.75. |
| `default_cargo_type` | cargo label or `DEFAULT_CARGO_FIRST_REFITTABLE` | Yes | Same default-cargo selection rules as trains. |
| `cargo_capacity` | 0..255 | Yes | Same default passenger/mail/goods multipliers as trains; callback can override. |
| `sound_effect` | `SOUND_*`, `sound(...)`, or `import_sound(...)` | No | Since OpenTTD r27507, external/imported sound forms are also valid. |
| `visual_effect` | `visual_effect(VISUAL_EFFECT_*, offset)` | Yes | Simple visual-effect method. |
| `effect_spawn_model` | `EFFECT_SPAWN_MODEL_*` | Yes | Advanced effect spawning, used with `create_effect`. |
| `length` | 1..8 | Yes | `8` is full vehicle length. |

### Road vehicle flags

- `ROADVEH_FLAG_TRAM` — requires tram tracks.
- `ROADVEH_FLAG_2CC` — enables second company colour.
- `ROADVEH_FLAG_AUTOREFIT` — allows autorefit subject to the `refit_cost` callback/property.
- `ROADVEH_FLAG_NO_BREAKDOWN_SMOKE` — disables breakdown smoke.
- `ROADVEH_FLAG_SPRITE_STACK` — enables multiple-sprite composition.

---

# 4. Ship properties

| Property | Range / type | Notes |
|---|---|---|
| `sprite_id` | `SPRITE_ID_NEW_SHIP` | Enables new graphics. |
| `speed` | 0..127 km/h; NML 7.5 permits 0..32767 km/h | Speed value. |
| `misc_flags` | `SHIP_FLAG_*` bitmask | Set to 0 for no flags. |
| `refit_cost` | 0..255 | Units of 1/32 of the default refit-cost base. |
| `callback_flags` | `VEH_CBF_*` bitmask | Only for old-style callbacks. |
| `is_refittable` | 0/1 | Must be 1 for the cargo-class refit properties to have an effect. |
| `default_cargo_type` | cargo label or `DEFAULT_CARGO_FIRST_REFITTABLE` | Same default-cargo rules as other vehicles. |
| `cargo_capacity` | 0..255 | Unlike other vehicle types, ship capacity is not modified by cargo type. |
| `sound_effect` | `SOUND_*`, `sound(...)`, `import_sound(...)` | Vehicle sound. |
| `ocean_speed_fraction` | 0..1 | NML 1.2. Fraction of base speed on ocean tiles; default 1. |
| `canal_speed_fraction` | 0..1 | NML 1.2. Fraction of base speed on canal tiles; default 1. |
| `visual_effect` | `visual_effect(VISUAL_EFFECT_*, offset)` | Simple effect method. |
| `effect_spawn_model` | `EFFECT_SPAWN_MODEL_*` | Advanced effect method with `create_effect`. |
| `acceleration` | 1..255 | NML 7.5. Approximately 0.5 km/h per tick. Default ships use 1. |

### Ship flags

- `SHIP_FLAG_2CC`
- `SHIP_FLAG_AUTOREFIT`
- `SHIP_FLAG_NO_BREAKDOWN_SMOKE`
- `SHIP_FLAG_SPRITE_STACK`

---

# 5. Aircraft properties

| Property | Range / type | Notes |
|---|---|---|
| `sprite_id` | `SPRITE_ID_NEW_AIRCRAFT` | Enables new graphics. |
| `speed` | 0..3280 km/h | Speed value. |
| `range` | 0..2894 | Maximum Euclidean distance between airports. `0` means unlimited range. |
| `misc_flags` | aircraft flag bitmask | `AIRCRAFT_FLAG_2CC`, `AIRCRAFT_FLAG_AUTOREFIT`, `AIRCRAFT_FLAG_NO_BREAKDOWN_SMOKE`, `AIRCRAFT_FLAG_SPRITE_STACK`. |
| `refit_cost` | 0..255 | Units of 1/32 of default refit-cost base. |
| `callback_flags` | `VEH_CBF_*` bitmask | Only for old-style callbacks. |
| `aircraft_type` | `AIRCRAFT_TYPE_*` | Determines compatible airport classes. |
| `acceleration` | NML 1.3.1: 0..255; older: 0..19 | Default aircraft use approximately 18..50 in newer versions. Older OpenTTD accelerated NewGRF aircraft 166% faster than intended. |
| `passenger_capacity` | 0..65536 | Passenger compartment capacity. |
| `mail_capacity` | 0..255 | Mail compartment capacity and part of the base capacity calculation when refitted. |
| `sound_effect` | `SOUND_*`, `sound(...)`, `import_sound(...)` | Aircraft sound. |

### Aircraft types

- `AIRCRAFT_TYPE_HELICOPTER` — can land on helipads.
- `AIRCRAFT_TYPE_SMALL` — can land on all airports with a runway.
- `AIRCRAFT_TYPE_LARGE` — can use all runway airports but has a high crash chance on small airports.

### Aircraft mail/cargo capacity calculation

For a refit to a cargo in `CC_PASSENGERS`, the mail capacity participates in the base capacity.

For other cargoes:

```text
base_capacity = passenger_capacity + mail_capacity
actual_capacity =
    base_capacity / 1  for mail
    base_capacity / 2  for goods
    base_capacity / 4  for other cargoes
```

Use the `passenger_capacity` and `mail_capacity` callbacks to override this behaviour.

---

# 6. Vehicle variables

Vehicle variables can be used in vehicle switches/callbacks. In the purchase list, the vehicle has not yet been built, so many variables are unavailable.

Accessing an unavailable variable has undefined behaviour.

All variables technically exist for all vehicle types, but some only have meaningful results for particular vehicle types. For example, rail variables should not be used as generic road/tram state checks.

## Variables without arguments

| Variable | Range / type | Purchase list | Meaning |
|---|---|---:|---|
| `position_in_consist` | 0..255 | No | Position from front/start of consist. Engine = 0. |
| `position_in_consist_from_end` | 0..255 | No | Position counted from rear. Last part = 0. |
| `num_vehs_in_consist` | 1..256 | No | Number of vehicle parts. Aircraft count shadow and rotor too. |
| `position_in_vehid_chain` | 0..255 | No | Position within consecutive parts having the same vehicle ID. |
| `position_in_vehid_chain_from_end` | 0..255 | No | Same, counted backwards. |
| `num_vehs_in_vehid_chain` | 1..256 | No | Number of consecutive parts with the same vehicle ID. |
| `position_in_articulated_veh` | 0..255 | No | NML 0.3 / OpenTTD 1.4. Articulated-part position from front. |
| `position_in_articulated_veh_from_end` | 0..255 | No | Articulated-part position from rear. |
| `cargo_classes_in_consist` | cargo-class bitmask | No | Cargo classes present in the consist. |
| `most_common_cargo_type` | cargo label | No | Most common cargo type in the consist. |
| `most_common_cargo_subtype` | 0..255 | No | Most common subtype for `most_common_cargo_type`. |
| `bitmask_consist_info` | 8-bit bitmask | No | OR of `bitmask_vehicle_info` across all vehicles. Rail vehicles only. |
| `company_num` | 0..14 | Yes | Owner company number. TTDPatch supports 0..7. |
| `company_type` | `PLAYERTYPE_*` | Yes | Human/AI company type. |
| `company_colour1` | `COLOUR_*` | Yes | Primary company colour. |
| `company_colour2` | `COLOUR_*` | Yes | Secondary company colour; equals colour 1 if no second colour is selected. |
| `aircraft_height` | 0..255 | No | Height difference between aircraft and shadow. 8 units = one map height level. |
| `airport_type` | `AIRPORTTYPE_*` | No | Small, large, heliport or oil rig. |
| `flight_state` | 0..28 | No | NML 0.8.1; aircraft only. |
| `curv_info_prev_cur` | -2..2 | No | Direction difference between previous vehicle and current vehicle; right is positive; 1 = 45°. |
| `curv_info_cur_next` | -2..2 | No | Direction difference between current and next vehicle; right is positive; 1 = 45°. |
| `curv_info_prev_next` | -4..4 | No | Direction difference between previous and next vehicle; equals previous/current + current/next. |
| `curv_info` | magic value | No | Encodes the previous/current/next curvature state. Use `vehicle_curv_info()` for comparisons rather than interpreting the number. |
| `motion_counter` | 0..0xFFFFFF | Yes, but always 0 | Increments each time the vehicle moves one map step. Useful for animation. Use a power-of-two frame count and low bits of this value. |
| `cargo_type_in_veh` | cargo translation-table entry | Yes, default cargo | `0xFF` if absent from the table. |
| `cargo_unit_weight` | weight per unit in 1/16 t | Yes, default cargo | Weight of one cargo unit. |
| `cargo_classes` | cargo-class bitmask | Yes, default cargo | Classes of current cargo. |
| `vehicle_is_available` | 0/1 | Yes | Vehicle is available on the open market. |
| `vehicle_is_testing` | 0/1 | Yes | Vehicle is being tested. |
| `vehicle_is_offered` | 0/1 | Yes | Vehicle is in exclusive preview. |
| `build_year` | 0..5,000,000 | Yes | Build year; current year if not yet built. |
| `direction` | `DIRECTION_*` | No | Vehicle direction. |
| `cargo_capacity` | 0..65535 | No | Vehicle cargo capacity. |
| `cargo_count` | 0..65535 | No | Current cargo quantity. |
| `cargo_subtype` | 0..255 | Yes, always 0 | Current cargo subtype. |
| `vehicle_is_powered` | 0/1 | No | Vehicle provides power and is on a compatible track type. |
| `vehicle_is_not_powered` | 0/1 | No | Vehicle is unpowered or on an incompatible track type. |
| `vehicle_is_potentially_powered` | 0/1 | No | Vehicle provides power if placed on a compatible track type. |
| `vehicle_is_flipped` | 0/1 | No | Train is flipped in depot or is rear part of a dual-head engine. |
| `vehicle_is_reversed` | 0/1 | No | Vehicle has been reversed an odd number of times. |
| `train_is_driving_backwards` | 0/1 | No | NML 16; train is travelling backwards. |
| `built_during_preview` | 0/1 | No | Built during exclusive preview. |
| `current_railtype` | railtype-table entry / 0xFF | No | Deprecated/useless with equivalent railtypes; use `tile_xxx_railtype`. Requires a railtype translation table to be meaningful. |
| `current_roadtype` | roadtype-table entry / 0xFF | No | Deprecated/useless with equivalent roadtypes; use `tile_xxx_roadtype`. |
| `current_tramtype` | tramtype-table entry / 0xFF | No | Deprecated/useless with equivalent tramtypes; use `tile_xxx_tramtype`. |
| `tile_has_catenary` | 0/1 | No | Current tile's track type has some catenary. For exact rail/road/tram type, use tile-type variables. |
| `waiting_triggers` | trigger state | No | Random triggers waiting to be matched. |
| `random_bits` | 0..255 | No | Random data for randomised decisions. |
| `grfid` | 0..0xFFFFFFFF | No | GRFID of the graphics block defining the vehicle. Use `str2number()` when comparing against another GRFID. |
| `vehicle_type_id` | 0..65535 or item-block name | No | GRF-local vehicle/item ID. IDs can collide between GRFs, so check `grfid` as well. |
| `vehicle_is_hidden` | 0/1 | No | Vehicle is hidden in a depot or tunnel. |
| `vehicle_is_stopped` | 0/1 | No | Vehicle is stopped; for trains also true while braking for a stop. |
| `vehicle_is_crashed` | 0/1 | No | Vehicle has crashed. |
| `vehicle_is_broken` | 0/1 | No | Vehicle is broken down. |
| `date_of_last_service` | date | No | Last service date. |
| `breakdowns_since_last_service` | 0..255 | No | Breakdown count since service. |
| `reliability` | 0..100 | No | Reliability percentage. |
| `age_in_days` | 0..65535 | No | Vehicle age. |
| `max_age_in_days` | 0..65535 | No | Maximum vehicle age. |
| `current_speed` | speed units | No | Current speed in m/s. |
| `max_speed` | speed units | No | Maximum vehicle speed in m/s. |
| `current_max_speed` | speed units | No | Current maximum speed including track/timetable restrictions; only valid for the front vehicle. |
| `vehicle_is_in_depot` | 0/1 | No | Vehicle is in a depot. |
| `vehicle_is_unloading` | 0/1 | No | NML 1.5 / OpenTTD 2.5. Vehicle is unloading at a station and has not started loading new cargo. |

### `company_type` values

- `PLAYERTYPE_HUMAN`
- `PLAYERTYPE_AI`
- `PLAYERTYPE_HUMAN_IN_AI`
- `PLAYERTYPE_AI_IN_HUMAN`

OpenTTD normally uses only `PLAYERTYPE_HUMAN` and `PLAYERTYPE_AI`.

---

## Variables requiring an argument

### Consist-relative variables

The argument is generally an offset from the current vehicle in the vehicle chain.

For these offset-based variables:

- Argument range is `-128..127`.
- Positive means towards the rear/end of the chain.
- Negative means towards the front.
- If the requested offset is outside the chain, the result is 0.

| Variable | Argument | Result | Meaning |
|---|---|---|---|
| `count_veh_id(id)` | Vehicle ID | 0..255 | Number of vehicles in the current consist having the specified ID. |
| `other_veh_curv_info(offset)` | Chain offset | -4..4 | Direction difference between the other vehicle and current vehicle; right positive; 1 = 45°. |
| `other_veh_is_hidden(offset)` | Chain offset | 0/1 | Whether the other vehicle is hidden in depot/tunnel. |
| `other_veh_x_offset(offset)` | Chain offset | -128..127 | Signed X-position difference; X axis runs top-right to bottom-left. |
| `other_veh_y_offset(offset)` | Chain offset | -128..127 | Signed Y-position difference; Y axis runs top-left to bottom-right. |
| `other_veh_z_offset(offset)` | Chain offset | -128..127 | Signed vertical position difference. |

### Tile track-type functions

The argument is a railtype, roadtype or tramtype translation-table entry.

| Function | Result | Meaning |
|---|---|---|
| `tile_supports_railtype(type)` | 0/1 | Whether the specified railtype is compatible with the railtype on the current tile. |
| `tile_supports_roadtype(type)` | 0/1 | Whether the specified roadtype is compatible with the roadtype on the current tile. |
| `tile_supports_tramtype(type)` | 0/1 | Whether the specified tramtype is compatible with the tramtype on the current tile. |
| `tile_powers_railtype(type)` | 0/1 | Whether the specified railtype would be powered on the current tile. |
| `tile_powers_roadtype(type)` | 0/1 | Whether the specified roadtype would be powered on the current tile. |
| `tile_powers_tramtype(type)` | 0/1 | Whether the specified tramtype would be powered on the current tile. |
| `tile_is_railtype(type)` | 0/1 | Whether the specified railtype is identical/equivalent to the tile railtype. |
| `tile_is_roadtype(type)` | 0/1 | Whether the specified roadtype is identical/equivalent to the tile roadtype. |
| `tile_is_tramtype(type)` | 0/1 | Whether the specified tramtype is identical/equivalent to the tile tramtype. |

Example:

```nml
tile_supports_railtype(ELRL)
```

### Badge functions

| Function | Argument | Result | Meaning |
|---|---|---|---|
| `has_badge(label)` | badge label | 0/1 | Whether the vehicle has the badge. |
| `count_has_badge(label)` | badge label | 0..255 | Number of vehicles in the consist having the badge. |
| `tile_has_railtype_badge(label)` | badge label | 0/1 | Whether the railtype on the current tile has the badge. |
| `tile_has_roadtype_badge(label)` | badge label | 0/1 | Whether the roadtype on the current tile has the badge. |
| `tile_has_tramtype_badge(label)` | badge label | 0/1 | Whether the tramtype on the current tile has the badge. |

The tile badge functions are intended for trains, road vehicles and trams. `tile_has_roadtype_badge` also works for trams.

---

# 7. Vehicle callbacks

Cargo-specific callback names can be used as graphics callbacks by using the cargo label as the callback name. These callbacks apply when the vehicle is refitted to the corresponding cargo.

If no cargo-specific graphics callback matches, `default` is used.

Cargo-specific graphics callbacks are not called from the purchase menu; use `purchase` for purchase-menu graphics.

| Callback | Available for | Purchase menu | Result | Purpose |
|---|---|---|---|---|
| `default` | All | Yes unless `purchase` exists | Sprite group | Normal vehicle graphics. |
| `purchase` | All | Yes only | Sprite group | Purchase-menu graphics. |
| `rotor` | Helicopters | No | Sprite group | Rotor graphics: 4 sprites, one stopped + three moving. |
| `random_trigger` | All | No | N/A | Random-trigger handling. |
| `cargo_subtype_text` | All | No | String / `CB_RESULT_NO_TEXT` | Provides extra refit options/text based on cargo subtype. Deprecated for most uses since OpenTTD 13; variants are preferred. |
| `additional_text` | All | Yes only | String | Additional purchase-list text. |
| `colour_mapping` | All | Yes unless separate purchase mapping | Recolour sprite number | Custom colour mapping instead of normal 1CC/2CC remapping. |
| `start_stop` | All | No | String / `CB_RESULT_NO_TEXT` | Allows/disallows starting/stopping; useful for depot departure restrictions. |
| `every_32_days` | All | No | 32-day callback flag bitmask | Periodic callback. |
| `sound_effect` | All | No | Sound / `CB_RESULT_NO_SOUND` | Selects vehicle sound. |
| `articulated_part` | Trains, road vehicles | Yes, no separate callback | Vehicle ID / `CB_RESULT_NO_MORE_ARTICULATED_PARTS` | Dynamically adds articulated parts. |
| `can_attach_wagon` | Trains | No | String / attach result | Allows/disallows attaching a wagon. |
| `refit_cost` | All | Yes | -8192..8191 + flags | Controls refit cost and autorefit. |
| `create_effect` | Trains, road vehicles, ships | No | 0..3 + flags | Defines visual effects spawned by effect-spawn models. |
| `reverse_build_probability` | Trains | No | 0 | NML 0.7.5 / OpenTTD 14. Probability of initial forward/reverse orientation. |
| `refit` | All | Purchase scope only | 0, 1, 2 | OpenTTD 15. Overrides standard refittability per cargo. |
| `loading_speed` | All | No | Same as property | Callback form of the property. |
| `speed` | All | Yes unless `purchase_speed` | Same as property | Dynamic speed. Units unavailable in callback. |
| `cost_factor` | All | Yes only | Same as property | Dynamic purchase cost. |
| `running_cost_factor` | All | Yes unless `purchase_running_cost_factor` | Same as property | Dynamic running cost. |
| `cargo_age_period` | All | No | Same as property | Dynamic cargo ageing period. |
| `cargo_capacity` | All except aircraft | Yes unless purchase version | Same as property | Dynamic cargo capacity. |
| `passenger_capacity` | Aircraft | Yes unless purchase version | Same as property | Dynamic passenger capacity. |
| `mail_capacity` | Aircraft | Yes unless purchase version | Same as property | Dynamic mail capacity. |
| `range` | Aircraft | Yes unless purchase version | Same as property | Dynamic aircraft range. |
| `visual_effect_and_powered` | Trains | No | Same as property | Train visual-effect method. |
| `visual_effect` | Road vehicles, ships | No | Same as property | Road/ship visual-effect method. |
| `effect_spawn_model_and_powered` | Trains | No | Same as property | Train effect-spawn method. |
| `effect_spawn_model` | Road vehicles, ships | No | Same as property | Road/ship effect-spawn method. |
| `power` | Trains, road vehicles | Yes unless purchase version | Same as property | Dynamic power. Units unavailable. |
| `weight` | Trains, road vehicles | Yes unless purchase version | Same as property | Dynamic weight. Units unavailable. |
| `length` | Trains, road vehicles | No | Same as property | Dynamic length. |
| `tractive_effort_coefficient` | Trains, road vehicles | Yes unless purchase version | 0..255 | Callback range is 0..255 rather than 0..1. |
| `bitmask_vehicle_info` | Trains | No | Same as property | Dynamic consist information bitmask. |
| `curve_speed_mod` | Trains | No | Same as property | Dynamic curve-speed modifier. |
| `name` | All | Yes | String | NML 0.7.2 / OpenTTD 14. Allows context-dependent vehicle names. |

## `purchase` callback

The purchase callback supplies buy-menu graphics.

For normal vehicles only the horizontal view is needed.

Dual-headed trains have special handling: the purchase sprite is rendered for both front and rear parts. A single purchase sprite is reused for both. A set of 8 sprites can be used to control which sprite is displayed; blanking all but the required position permits a single controlled sprite.

---

# 8. Specific callback details

## `cargo_subtype_text`

The callback is called repeatedly during refitting with increasing `cargo_subtype` values until `CB_RESULT_NO_TEXT` is returned.

Returned strings are presented as refit options.

The selected option is stored in `cargo_subtype`, which can then be used to select graphics.

This facility is considered deprecated for most uses since OpenTTD 13; use variants instead.

## `colour_mapping`

Allows a custom recolour sprite instead of the standard 1CC/2CC mapping.

Use `reserve_sprites()` when allocating a custom sprite.

The result is cached and only updated when `every_32_days` requests a colour-mapping update.

Add `CB_RESULT_COLOUR_MAPPING_ADD_CC` to the result to additionally apply company colours. This requires 16 sprites for 1CC or 256 sprites for 2CC.

## `start_stop`

Return:

- `CB_RESULT_NO_TEXT` — allow start/stop.
- String — disallow and use the returned string as the error message.

Useful for conditions preventing a vehicle leaving a depot.

## `every_32_days`

Called every 32 days.

Return flags such as:

- `CB_RESULT_32_DAYS_TRIGGER` — trigger `TRIGGER_VEHICLE_32_CALLBACK`.
- `CB_RESULT_32_DAYS_COLOUR_MAPPING` — rerun `colour_mapping`.

## `sound_effect`

The sound event is available through:

```nml
getbits(extra_callback_info1, 0, 8)
```

Return:

- `SOUND_*` — built-in/default sound.
- `sound("soundfile")` — imported WAV sound.
- `import_sound(grfid, number)` — sound from another GRF.
- `CB_RESULT_NO_SOUND` — suppress the sound.

If the callback fails or is not implemented, the default sound is used.

## `articulated_part`

Called repeatedly until:

```text
CB_RESULT_NO_MORE_ARTICULATED_PARTS
```

is returned.

Each returned vehicle ID is appended as an articulated part.

`getbits(extra_callback_info1, 0, 8)` gives the call number: 1 on the first call, 2 on the second, etc.

The callback can also be called from the purchase list, where vehicle variables cannot be used.

`CB_RESULT_REVERSED_VEHICLE` can be combined with the returned vehicle ID to display the articulated part backwards.

Vehicle IDs for articulated parts must be 0..16383; NML 0.2 and earlier used 0..127.

## `can_attach_wagon`

Called when a wagon is attached.

If a wagon is inserted in the middle, the existing wagons are detached and reattached one at a time in the new order.

The callback is defined on the engine, but its scopes are unusual:

- `SELF` = wagon being attached.
- `PARENT` = existing consist from engine up to the wagon immediately before `SELF`.

Return:

- String — disallow with custom error.
- `CB_RESULT_ATTACH_DISALLOW` — disallow with standard "incompatible railtypes" message.
- `CB_RESULT_ATTACH_ALLOW` — allow.
- `CB_RESULT_ATTACH_ALLOW_IF_RAILTYPES` — allow only if railtypes match; default behaviour.

## `refit_cost`

Return range is -8192..8191.

Add `CB_RESULT_AUTOREFIT` to permit autorefit.

When returning a negative value, encode the cost using:

```text
cost & CB_RESULT_REFIT_COST_MASK
```

before adding `CB_RESULT_AUTOREFIT`.

The relevant vehicle `misc_flags` must also contain the appropriate autorefit flag.

Callback parameters are packed into `extra_callback_info1`:

```nml
getbits(extra_callback_info1, 0, 8)   // new cargo type
getbits(extra_callback_info1, 8, 8)   // new cargo subtype
getbits(extra_callback_info1, 16, 16) // target cargo-class bitmask
```

The callback can be called before the vehicle exists, so only a limited set of variables is available.

## `create_effect`

Used when an `effect_spawn_model` or `effect_spawn_model_and_powered` property is active.

Return 0..3 for the number of effects.

Optional result flags:

- `CB_RESULT_CREATE_EFFECT_CENTER`
- `CB_RESULT_CREATE_EFFECT_NO_ROTATION`

Each effect's data is placed in registers `0x100`..`0x103`.

Example pattern:

```nml
switch (FEAT_XXX, SELF, switch_name, [
    STORE_TEMP(create_effect(EFFECT_SPRITE_XXX, 8, -3, 10), 0x100),
    STORE_TEMP(create_effect(EFFECT_SPRITE_YYY, 8,  3, 10), 0x101)
]) {
    return 2;
}
```

The helper has the form:

```text
create_effect(effect_sprite, l_x_offset, t_y_offset, z_offset)
```

where:

- `effect_sprite` = one of `EFFECT_SPRITE_NONE`, `EFFECT_SPRITE_STEAM`, `EFFECT_SPRITE_DIESEL`, `EFFECT_SPRITE_ELECTRIC`, `EFFECT_SPRITE_AIRCRAFT_BREAKDOWN_SMOKE`.
- `l_x_offset` = longitudinal/X offset depending on `CB_RESULT_CREATE_EFFECT_NO_ROTATION`.
- `t_y_offset` = transversal/Y offset depending on `CB_RESULT_CREATE_EFFECT_NO_ROTATION`.
- `z_offset` = vertical offset.

`CB_RESULT_CREATE_EFFECT_CENTER` applies to trains and road vehicles and makes positions relative to the vehicle centre rather than the sprite.

Without `CB_RESULT_CREATE_EFFECT_NO_ROTATION`, longitudinal/transversal coordinates rotate with vehicle orientation.

With it, X/Y coordinates are not automatically rotated.

## `reverse_build_probability`

NML 0.7.5 / OpenTTD 14.

Controls the probability that a purchased rail vehicle starts facing forward versus backward.

---

# 9. Custom `refit` callback

Available from OpenTTD 15.

The callback is called once for each defined cargo type after all NewGRFs have loaded.

It runs in purchase scope, not on an actual vehicle.

Return:

- `0` — leave refittability unchanged.
- `1` — allow the cargo as a refit.
- `2` — disallow the cargo as a refit.

The cargo being evaluated is available through variables 10 and 18.

The callback is not reevaluated after game initialisation. Do not use dynamic variables such as the current game date; doing so produces undefined/faulty behaviour.

---

# 10. GUI sprite context

`getbits(extra_callback_info1, 0, 8)` identifies the GUI/map context in which a vehicle sprite is being requested.

| Value | Context |
|---|---|
| `0x00` | Vehicle on the map/in a viewport. |
| `0x01..0x0F` | Reserved. |
| `0x10` | Depot GUI. |
| `0x11` | Vehicle details GUI, including refit GUI. |
| `0x12` | Vehicle list. |
| `0x13..0x1F` | Reserved for future GUIs. |
| `0x20` | Purchase list, including autoreplace GUI. |
| `0x21` | Exclusive preview GUI or advertisement news. |
| `0x22..0x2F` | Reserved for future GUIs involving non-purchased vehicles. |
| `0x30..0xFF` | Reserved. |

Contexts `0x20..0x2F` use the `purchase` callback.

Other contexts use `default` or cargo-specific callbacks.

An exception is the special depot-grid-size request for ships and aircraft, which uses the `purchase` callback.

OpenTTD also uses the purchase-list chain with cargo type `FF` to determine depot grid size.

---

# 11. Multiple-sprite vehicle composition

Since OpenTTD r27668 / version 1.7, vehicles can be composed from multiple sprites.

Requirements:

1. Set the relevant `*_FLAG_SPRITE_STACK` in `misc_flags`.
2. Resolve the sprite repeatedly.
3. Read the iteration number using:

```nml
getbits(extra_callback_info1, 8, 8)
```

Sprites may have independent recolouring.

32bpp sprites can use alpha blending, including alpha blending company colours over other sprites.

Sprite limits:

- OpenTTD 1.7–12.0: maximum 4 sprites per articulated part.
- OpenTTD 13+: maximum 8 sprites per articulated part.

Set register 100 with the additional result:

```nml
STORE_TEMP(CB_FLAG_MORE_SPRITES | recolouring, 0x100)
```

when more sprites remain.

For the final sprite:

```nml
STORE_TEMP(recolouring, 0x100)
```

Possible `recolouring` values include:

- `PALETTE_USE_DEFAULT` — normal vehicle recolouring.
- `PALETTE_IDENTITY` — no recolouring.
- Any other default or custom recolouring sprite.

---

# 12. Vehicle sound events

The `sound_effect` callback receives the event through:

```nml
getbits(extra_callback_info1, 0, 8)
```

| Event | Meaning |
|---|---|
| `SOUND_EVENT_START` | Vehicle leaves station/depot; aircraft takes off. |
| `SOUND_EVENT_TUNNEL` | Vehicle enters a tunnel. |
| `SOUND_EVENT_BREAKDOWN` | Vehicle breaks down; not used for aircraft. |
| `SOUND_EVENT_RUNNING` | Once per engine tick, but at most once per vehicle motion. |
| `SOUND_EVENT_TOUCHDOWN` | Aircraft touches down. |
| `SOUND_EVENT_VISUAL_EFFECT` | A visual effect is generated: steam, diesel smoke or electric spark. |
| `SOUND_EVENT_RUNNING_16` | Every 16 engine ticks while moving. |
| `SOUND_EVENT_STOPPED` | Every 16 engine ticks while stopped. |
| `SOUND_EVENT_LOAD_UNLOAD` | Consist loads or unloads cargo. |

---

# 13. Vehicle IDs

Vehicle IDs behave differently depending on whether OpenTTD's engine pool is enabled.

The state can be checked using the global variable:

```text
dynamic_engines
```

Vehicle IDs normally affect purchase-menu ordering, but this can be overridden by a `sort` block.

## Engine pool enabled

Each NewGRF has its own vehicle-ID namespace.

IDs may be chosen freely from 0..65535.

If the selected ID belongs to an existing vehicle:

- the existing vehicle is overridden;
- if another NewGRF already overrides it, a new vehicle is allocated and the old vehicle's properties are copied;
- if no original vehicle exists, a new blank vehicle is allocated.

`engine_override` can change this behaviour and allow properties of vehicles defined in another NewGRF to be modified rather than allocating a new vehicle.

## Engine pool disabled / TTDPatch

Every new vehicle must replace an existing vehicle.

If multiple NewGRFs replace the same vehicle, the last loaded NewGRF wins.

IDs are associated with a feature, not a specific subtype. For example, IDs belong to the train feature rather than separately to electric/monorail/maglev wagons.

Recommended compatibility strategy:

1. If the NewGRF is a complete replacement for the default vehicles, disable the relevant default vehicles with `disable_item`.
2. Reuse existing vehicle IDs where practical.
3. If using IDs outside the normal range, check `dynamic_engines`.
4. If dynamic engines are disabled, skip vehicles outside the normal range and retain a usable set of remaining vehicles.
5. Consider issuing a warning when vehicles are skipped, or disable the entire NewGRF.

If IDs outside the supported range are used while dynamic engines are disabled, OpenTTD may disable the NewGRF with:

```text
Attempt to use invalid ID
```

---

# 14. Important compatibility distinctions

When writing NML vehicle code, distinguish between:

- **Properties** — static vehicle definitions.
- **Callbacks** — dynamic results that may depend on variables/context.
- **Vehicle variables** — values describing the current vehicle/consist/tile.
- **Purchase-list scope** — many vehicle variables are unavailable because the vehicle has not yet been built.
- **Articulated parts** — individual vehicle parts can inherit or override properties subject to the documented restrictions.
- **Engine-pool behaviour** — vehicle ID semantics depend on `dynamic_engines`.
- **GUI graphics** — `purchase`, `default` and cargo-specific callbacks can be invoked in different contexts.
- **Visual effects** — simple `visual_effect*` and advanced `effect_spawn_model*` mechanisms are alternatives for a given item.
- **Sprite stacking** — requires the corresponding `*_FLAG_SPRITE_STACK` and uses `extra_callback_info1` bits 8..15 to identify the sprite iteration.

## Prefer current tile-type variables over current translation-table variables

The documented `current_railtype`, `current_roadtype` and `current_tramtype` variables are described as effectively obsolete/useless when equivalent types are involved.

Prefer:

```text
tile_xxx_railtype
tile_xxx_roadtype
tile_xxx_tramtype
```

and their `tile_supports_*`, `tile_powers_*` and `tile_is_*` forms.

## Articulated-chain offsets

For `other_veh_*` variables:

```text
negative offset = towards front/engine
positive offset = towards rear/end
```

The valid argument range is `-128..127`. Requests outside the chain return 0.

---

## Source

GRFSpecs, **NML:Vehicles**  
https://newgrf-specs.tt-wiki.net/wiki/NML:Vehicles

The source page was last modified 30 July 2026.
