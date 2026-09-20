# BRBuild Project Configuration and Structure Guide

This guide describes how to structure a newGRF project built with **BRBuild**, detailing the folder layouts, configuration files, and YAML formats.

---

## 1. Project Directory Structure

A BRBuild-compatible project (e.g., `OpenTTE2`, `BRMetro`) should be located as a sibling directory to the `BRBuild` repository and structured as follows:

```
[your-project-folder]/         # Sibling folder to BRBuild, e.g. OpenTTE2
├── BRBuild.yaml               # Core project manifest defining directories & target folders
├── build.py                   # Script copied from build.py.example to run the build
├── src/
│   ├── grf/
│   │   └── GRF.yaml           # GRF metadata, parameter configurations, & global switches
│   └── vehicles/              # Target directory for candidates (referenced in BRBuild.yaml)
│       └── [VehicleName]/     # Subfolder for a specific vehicle (e.g., Thomas)
│           ├── [VehicleName].yaml # Vehicle configuration file (e.g., Thomas.yaml)
│           ├── [VehicleName].png  # The sheet the build reads (normalised, committed)
│           ├── new/           # Drop folder: replacement artwork goes here
│           ├── ingested/      # Latest ingested source sheet (tracked, artist editable)
│           ├── error/         # Drops from units that failed to build (tracked)
│           └── [custom].pnml  # Optional raw PNML files containing sprites/custom code
```

### Ingesting new sprites

Place exactly one PNG in a vehicle's `new/` folder. A build only touches a spritesheet when one is waiting there: the PNG is staged into `WorkingData/<project>/ingest/` (never inside the source tree), normalised down to the recognised template rows, and used for that build. Once the build succeeds:

- the normalised sheet is published to the vehicle's `[VehicleName].png`, which is what the build reads from then on;
- the raw ingested source is kept as `ingested/[VehicleName].png`, for artists and debugging, including any annotation or notes the artist sent;
- `new/` is emptied so it is obvious where the next drop goes, and the staging area is deleted.

If a vehicle fails to build, its staged sheet is *not* published. The drop is moved to `error/[VehicleName].png` instead — kept and committed so the failed revision is on record, but out of `new/` so it is obvious the folder is for a fresh drop. The published `[VehicleName].png` and `ingested/` copy are left alone, and the failure is logged. That keeps a partly working project from silently adopting artwork it could not build.

Only the latest ingested source is kept, since git holds the version history. Replacements are not destructive of the published sheet until a build actually succeeds: a failed build publishes nothing and leaves the drop in `new/` to retry.

Artists work from the tracked `ingested/` sheet: edit it, drop the result into `new/`, and the next build normalises and republishes it.

This applies to every replacement sheet, not just hand-drawn revisions: a directly copied legacy sheet, a PNML-derived extraction, and a generated composite are all migrated through `new/`. Nothing should be written straight to the published `[VehicleName].png` or into `ingested/`, so `ingested/` is always the current working copy.

A build with an empty `new/` folder leaves the committed spritesheet untouched and simply reads it, so rebuilds do not churn artwork.

Reset mode (`--reset-graphics`) gives `new/` priority; if no new image is available, it restores the published sheet from `ingested/`. Legacy `original/` folders and `<name>_original.png` siblings are migrated into `ingested/` automatically when encountered.

---

## 2. Project Manifest: `BRBuild.yaml`

The `BRBuild.yaml` file at the project root declares the metadata of the project and guides the discovery of candidate folders.

### Example configuration

```yaml
project:
  name: OpenTTE2           # Unique name of the project
  build: true              # Set to false to disable this project during bulk runs
  target_folders:          # List of folders relative to project root to scan for vehicles
    - src/vehicles
  grf_folder: src/grf      # Directory containing GRF.yaml (defaults to src/grf)
  sound_folder: src/sound  # Directory containing sounds (defaults to src/sound)
```

---

## 3. GRF Configuration: `src/grf/GRF.yaml`

The `GRF.yaml` file configures the overall metadata of the compiled `.grf` file. This includes properties of the GRF block, customizable UI parameters, and global action/switch rules.

### Structure & Fields

*   **`grf`**:
    *   `grfid`: The 8-character hex-encoded GRF Identifier (e.g., `"NML\01\02"`).
    *   `short_name`: Internal short identifier of the GRF.
    *   `name`: Display name of the GRF.
    *   `description`: Description text shown in the NewGRF settings UI.
*   **`versioning`**:
    *   `version`: Current version integer.
    *   `compatible_version`: Minimum version of the GRF that is save-compatible.
*   **`params`**: A list of configuration parameters shown in the game configuration. Each item contains:
    *   `identifier`: Unique name/variable for the parameter (e.g., `param_disable_steam`).
    *   `type`: Type of variable (defaults to `int`).
    *   `name_str`: Descriptive name shown to the user.
    *   `desc_str`: Description/tooltip for the parameter.
    *   `min_value`: Minimum allowed value.
    *   `max_value`: Maximum allowed value.
    *   `def_value`: Default value.
    *   `names` *(optional)*: Map of integer values to user-facing strings (e.g., `0: "Enabled", 1: "Disabled"`).
*   **`global_vehicle_switches`**: List of NML switch definitions that apply globally. Each switch requires:
    *   `vehicle_type`: The feature/type (e.g., `TRAIN`, `ROADVEH`).
    *   `target_type`: Target for variables evaluation, e.g., `SELF` (default) or `PARENT`.
    *   `name`: Name of the switch.
    *   `expression`: The variable or expression evaluated (e.g., `param_disable_steam`).
    *   `values`: Key-value map (or list) representing the cases and return values.

### Example configuration

```yaml
grf:
  grfid: "NML\01\01"
  short_name: "OTTE"
  name: "OpenTTD Extended Trains"
  description: "A comprehensive trainset containing custom liveries and dynamic performance calculations."

versioning:
  version: 1
  compatible_version: 1

params:
  - identifier: "param_cost_multiplier"
    type: "int"
    name_str: "Cost Multiplier"
    desc_str: "Adjust the purchase and running costs of all trains."
    min_value: 0
    max_value: 2
    def_value: 1
    names:
      0: "Cheap"
      1: "Normal"
      2: "Expensive"

global_vehicle_switches:
  - vehicle_type: "TRAIN"
    target_type: "SELF"
    name: "sw_global_cost_modifier"
    expression: "param_cost_multiplier"
    values:
      0: 50
      1: 100
      2: 150
      default: 100
```

---

## 4. Vehicle Configuration: `[VehicleName].yaml`

Each vehicle is located in its own directory (e.g. `src/vehicles/Thomas/`) and must contain a YAML file named exactly after that directory (e.g. `Thomas.yaml`).

### Data Fields

*   **`info`**:
    *   `identifier`: Short, unique string identifier (e.g., `thomas`).
    *   `name`: Display name of the vehicle.
    *   `sub_name`: Subtitle/alternative name.
    *   `based_on`: Reference/source vehicle.
    *   `operator`: Original railway operator.
*   **`stats`**:
    *   `vehicle_type`: Core type. Supported values: `train`, `tram`, `road_vehicle`, `ship`, `plane`.
    *   `train_type` *(only for `vehicle_type: train`)*: Enum defining sub-type. Supported: `locomotive`, `multiple_unit`, `wagon`, `coach`.
    *   `weight`: Weight in metric tons (float). Tram weights are converted to NewGRF's quarter-ton units when written.
    *   `length`: Length of the vehicle.
    *   `power`: Power output in hp (integer).
    *   `speed`: Max speed in mph (integer).
    *   `tractive_effort`: Tractive effort in kN (integer).
    *   `power_type`: List of traction types (e.g., `[steam, coal]`).
    *   `sound_effect`, `visual_effect`: Override the presentation implied by the traction type (see Traction types below). Also accepted on a profile or a livery.
*   **`cargo`**:
    *   `cargo_classes`: List of cargo classes the vehicle is capable of carrying.
*   **`dates`**:
    *   `introduction_date`: Year when the vehicle is introduced (integer).
*   **`profiles`**: A list of performance/size variations available for this vehicle.
    *   `identifier`: Short profile identifier.
    *   `name`: Name of the profile.
    *   `size`: Relative length/size modifier.
    *   `capacity`: Cargo capacity.
    *   `power`: Power in hp for this profile; overrides the vehicle-level `stats.power`.
    *   `weight`: Weight in metric tons for this profile; overrides the vehicle-level `stats.weight`.
    *   `tilt`: Tilt strength for this profile, as a named level or a number.
    *   `special_tags`: List of custom tags triggering special badges for this profile's variants.
    *   `types`: Target vehicle type variants (e.g. `[train, tram]`).
*   **`liveries`**: Visual variations (liveries) available for the vehicle.
    *   `name`: Name of the livery.
    *   `sprite_override`: Custom sprite template file to map.
    *   `profiles`: List of profile identifiers this livery applies to.
    *   `power`: Power in hp for this livery; overrides the vehicle default, but not the profile.
    *   `weight`: Weight in metric tons for this livery; overrides the vehicle default, but not the profile.
    *   `tilt`: Tilt strength for this livery; overrides the vehicle default, but not the profile.
    *   `special_tags`: List of custom tags triggering special badges for this livery's variants.
*   **Other root fields**:
    *   `classification`: Categorization string.
    *   `model_life`: How long the vehicle remains in the purchase list.
    *   `retire_early`: Number of years to retire before normal model life ends.
    *   `vehicle_life`: Expected lifespan of individual vehicles.
    *   `cargo_age_period`: Duration for cargo aging penalties.
    *   `loading_speed`: Base speed for loading cargo.
    *   `sound effect`: Custom sound effect string.
    *   `special_tags`: List of custom tags triggering special badges for all variants (e.g., `["express", "high-speed"]`).

Statistical fields that appear on both a profile and a livery are resolved per variant: the profile wins, then the livery, then the vehicle. Use them when one formation or operator really differs — for example a longer multiple unit whose extra vehicles add power and weight.

#### Tilt

`tilt` may be set on `stats`, a profile or a livery, and is resolved the same way. It accepts a named level or a number, and drives both of OpenTTD's tilting mechanisms:

| Level | `curve_speed_mod` | `TRAIN_FLAG_TILT` |
|---|---|---|
| `none` | 0 | no |
| `basic` | 0.1 | yes |
| `modest` | 0.2 | yes |
| `strong` | 0.3 | yes |
| `extreme` | 0.35 | yes |

Any non-zero value also sets `TRAIN_FLAG_TILT` for that variant. Numbers are accepted directly for units that do not sit on the scale, e.g. `tilt: 0.25`. The flag only takes effect when every vehicle in the consist has it, which is how articulated units are built here anyway. The levels are conventions, not OpenTTD constants: OpenTTD's flag already carries a 20% curve-speed bonus, and whether it stacks with `curve_speed_mod` is not documented, so treat the level names as a project-wide scale rather than a claim that `strong` equals a specific total bonus.

#### Traction types

`power_type` takes one token per traction mode. Two or more tokens make the vehicle bi- or
tri-mode, which is also what selects the bi-mode and tri-mode cost multipliers.

| Token | Engine class | Notes |
|---|---|---|
| `steam` | steam | |
| `diesel`, `diesel_hydraulic`, `diesel_electric`, `diesel_mechanical` | diesel | |
| `electric`, `ohle`, `overhead`, `third_rail`, `fourth_rail`, `catenary` | electric | supply forms add delivery/voltage badges; they are not separate modes |
| `hydrogen` | electric | not an OpenTTD concept: electric traction motors, no catenary needed |
| `battery` | electric | not an OpenTTD concept: as hydrogen |
| `gas_turbine` | diesel | not an OpenTTD concept: self-powered, so no catenary, but no diesel-like exhaust |

Several of these have no OpenTTD equivalent, so BRBuild approximates them with the
mechanics OpenTTD does have (see `PropertyCalculation/FuelDefaults.py` and
`PropertyCalculation/PowerTypeClassifier.py`):

- **Track**: every train currently uses the project's electric railtype. A self-powered
  type needs no catenary in reality, but BRBuild has no `track_type` field yet, so that
  distinction is not expressible.
- **Costs**: the per-fuel multipliers in `PropertyCalculation/FuelType.py` shape purchase
  and running cost relative to each other. They are BRBuild conventions rather than
  OpenTTD values, and are expected to be refined.
- **Sound**: OpenTTD's built-in sound set has no diesel, electric or turbine entry, so no
  sound is set by default. Set `sound_effect` on the vehicle, profile or livery to a
  `SOUND_*` constant, a `sound("file")` from this GRF, or a switch name. It is emitted as
  the `sound_effect` graphics callback.
- **Visual effect**: emitted only when the fuel's effect differs from what the engine class
  already gives. Hydrogen, battery and gas turbine get `VISUAL_EFFECT_DISABLE` because
  OpenTTD has no water-vapour effect and a self-powered unit should not clag like a diesel.
  Trains emit `visual_effect_and_powered(...)`, other vehicle types `visual_effect(...)`.

### Example configuration

### Example configuration

```yaml
classification: "steam"
introduction_date: 1915
model_life: 40
vehicle_life: 30

info:
  identifier: "thomas"
  name: "Thomas the Tank Engine"
  sub_name: "LBSC E2 Class"
  operator: "NWR"

stats:
  vehicle_type: "train"
  train_type: "locomotive"
  weight: 52.0
  length: 4
  power: 500
  speed: 40
  tractive_effort: 75
  power_type:
    - steam

cargo:
  cargo_classes:
    - passengers

profiles:
  - identifier: "standard"
    name: "Standard Tank"
    capacity: 0
    types:
      - train

liveries:
  - name: "NWR Blue"
    sprite_override: "blue_livery.png"
    profiles:
      - "standard"
```

---

## 5. Integrating Custom PNML Files

If a vehicle candidate folder contains `.pnml` files (e.g., `Thomas.pnml` alongside `Thomas.yaml`), BRBuild will automatically discover them and prepend them to the generated NML sources (just before the YAML-generated code).

This is useful for writing custom graphics overrides, callbacks, or advanced logic blocks that cannot be fully described in YAML.

## 6. Sprite IDs and releases

BRBuild stores the numeric vehicle IDs used in `item()` definitions in `src/grf/VehicleIDData.yaml`. The registry identifies a variant by vehicle, profile, livery, and vehicle type. Generated GNML is archived beside that file so released variants can remain in the GRF after they are removed or changed.

Normal development builds reuse IDs from variants that were not seen in the build. Run with `--release` when the set of variants is ready to be savegame-compatible: active IDs are locked, and changes to capacity, articulated-part count, or individual part lengths create a new ID. The previous definition is retained with `NO_CLIMATE` and `(DEPRECATED)` so it remains loadable but cannot be purchased.