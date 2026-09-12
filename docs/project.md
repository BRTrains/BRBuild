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
│           └── [custom].pnml  # Optional raw PNML files containing sprites/custom code
```

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
    *   `weight`: Weight in metric tons (float).
    *   `length`: Length of the vehicle.
    *   `power`: Power output in hp (integer).
    *   `speed`: Max speed in mph (integer).
    *   `tractive_effort`: Tractive effort in kN (integer).
    *   `power_type`: List of traction types (e.g., `[steam, coal]`).
*   **`cargo`**:
    *   `cargo_classes`: List of cargo classes the vehicle is capable of carrying.
*   **`dates`**:
    *   `introduction_date`: Year when the vehicle is introduced (integer).
*   **`profiles`**: A list of performance/size variations available for this vehicle.
    *   `identifier`: Short profile identifier.
    *   `name`: Name of the profile.
    *   `size`: Relative length/size modifier.
    *   `capacity`: Cargo capacity.
    *   `types`: Target vehicle type variants (e.g. `[train, tram]`).
*   **`liveries`**: Visual variations (liveries) available for the vehicle.
    *   `name`: Name of the livery.
    *   `sprite_override`: Custom sprite template file to map.
    *   `profiles`: List of profile identifiers this livery applies to.
*   **Other root fields**:
    *   `classification`: Categorization string.
    *   `model_life`: How long the vehicle remains in the purchase list.
    *   `retire_early`: Number of years to retire before normal model life ends.
    *   `vehicle_life`: Expected lifespan of individual vehicles.
    *   `cargo_age_period`: Duration for cargo aging penalties.
    *   `loading_speed`: Base speed for loading cargo.
    *   `sound effect`: Custom sound effect string.
    *   `special_tags`: List of custom tags triggering special badges (e.g., `["express", "high-speed"]`).

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