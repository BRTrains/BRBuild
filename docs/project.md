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

#### Derived metadata beside a spritesheet

A build writes two kinds of derived file next to each spritesheet, both of which belong in the project's `.gitignore` and neither of which is a build input:

- `<sheet>.png.cache` / `<sheet>.png.cacheindex` — nmlc's own cache of the sprites encoded from that image. Rewriting an image gives it a newer mtime than the cache and throws its entries away, so BRBuild only rewrites a generated sprite (a purchase icon) when its bytes actually changed.
- `<sheet>.png.sheetcache.json` — the sprite rows detected in that sheet, with the hash of the sheet, the palette, the template definitions and the vehicle type they were detected against. Row detection scans every pixel and is the most expensive part of a rebuild, so it is skipped whenever all four still match. Editing a sheet, the palette or a template invalidates the cache automatically; deleting the file just forces one rebuild to detect again.

Neither file is read from anywhere else, and both are safe to delete at any time.

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

Two optional files sit beside it in the same folder:

*   **`RailTypes.yaml`** — the project's logical track types and the railtype labels they fall back to (see Track types above). Declaring it replaces NML's default railtype table.
*   **`<name>.pnml`** — hand-written NML the project needs beyond what the vehicle YAML can express, collated with the generated files.

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
*   **`global_actions`**: List of parameter-controlled NML actions that run at GRF scope. Each action requires `condition` and `action`; for example, `condition: param_disable_default_vehicles == 1` and `action: disable_item(FEAT_TRAINS)`.
*   **`purchase_list`**: How the purchase list is ordered. Optional; without it vehicles appear in vehicle-ID order, which is an accident of the ID registry.
    *   `order`: `none` (the default), `date`, or `grouped`.
    *   `file` *(optional)*: A manual NML file, relative to the project's `grf_folder`. When set, its contents are used instead of generated sort blocks; this is useful when the list needs explicit headers or an order the built-in grouping does not express. The file is collated after all generated items, so it may name their symbols.
    *   `date` puts every vehicle in introduction-date order.
    *   `grouped` is four groups, in this order: (1) everything else by introduction date — this is where BR Standard classes land, because their names start `Standard Class` rather than `Class <number>`; (2) the BR/privatisation class grouping, a name starting `Class <number>[/<subclass>]`, ordered by class then subclass; (3) coaches (`train_type: coach`); (4) wagons (`train_type: wagon`).
    *   Road vehicles (trams) are always ordered by introduction date, whatever the setting.
    *   Vehicles of one candidate stay contiguous and keep the order the variant iterator produced (profile-outer, livery-inner), so a unit's liveries never interleave with another unit's.
    *   The builder emits one `sort(<feature>, [...])` block per feature, after every generated item and before any `custom_nml/append` file, so the block can name the item symbols the build produced. A feature with fewer than two vehicles gets no block.

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

purchase_list:
  order: "grouped"
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
    *   `speed`: Service speed in mph (integer) — the limit the vehicle normally runs to.
    *   `design_speed`: Design speed in mph (integer), optional. Set it only where the real design/technical maximum differs from the service limit; with both set, the `param_speed_mode` GRF parameter picks between them (see Design vs service speed below). Accepted on a profile or a livery as well as `stats`.
    *   `tractive_effort`: Tractive effort in kN (integer).
    *   `power_type`: List of traction types (e.g., `[steam, coal]`).
    *   `track_type`: List of the project's logical track types the train can use (see Track types below). Defaults to `RAIL`; trains only.
    *   `has_cab`: `true` marks an unpowered driving vehicle (a DVT, DBSO or driving trailer) so the train may back up with it leading (see Driving vehicles below). Also accepted on a profile or a livery.
    *   `lighting`: `auto` (the default), `exact` or `none` — see Lighting overlays below. Also accepted on a profile or a livery.
    *   `sound_effect`, `visual_effect`: Override the presentation implied by the traction type (see Traction types below). Also accepted on a profile or a livery.
*   **`cargo`**: what the vehicle can be refitted to, as a preset name, an explicit NML class, or a list of either:
    *   Presets — `passenger`, `parcels`, `mail`, `containerised`, `bulk`, `tank`, `open_wagon`. These are the project's own names for the bundles each kind of unit actually uses, so `cargo: containerised` beats repeating a seven-class bitmask in every wagon.
    *   Explicit classes — any OpenTTD class, written `CC_PIECE_GOODS` or `piece_goods` (prefix and case optional). A `CC_` prefix always means that single class, which matters where a preset shares its name: `cargo: bulk` is the hopper recipe, `cargo: CC_BULK` is the bulk class alone.
    *   `none` — carries nothing. Emitted as an explicit empty class list (`refittable_cargo_classes: 0`) rather than omitted, so "carries nothing" is stated rather than looking like an unconverted vehicle.
    *   Leaving `cargo` out emits no class property at all.
    *   An unknown name fails the build and lists the valid names, because a silently dropped class means a vehicle that cannot be refitted.
    *   Accepted on the vehicle or a profile, resolved profile first, so one candidate can offer both a passenger and a parcels formation.
*   **`non_cargo_classes`**: classes the vehicle can never be refitted to. Resolves classes only, never presets.
*   **`default_cargo_type`**: which cargo a newly bought vehicle carries. Currently only NML's label-free `DEFAULT_CARGO_FIRST_REFITTABLE` is accepted — naming a cargo label such as `GOOD` needs a `cargotable`, which BRBuild does not generate yet, and would abort the compile.
*   **`autorefit`**: `true` sets `TRAIN_FLAG_AUTOREFIT`, so the vehicle adopts the consist's cargo instead of needing its own refit.
*   **`loading_speed`**: cargo units loaded/unloaded per loading interval.
*   **`cargo_age_period`**: custom cargo ageing period in ticks.
*   **`dates`**:
    *   `introduction_date`: when the vehicle becomes available. Write a year (`1952`), `YYYY-MM` (`1952-04`) or `YYYY-MM-DD` (`1952-04-21`); it is emitted as an NML `date(...)`, so a bare date is never read as the arithmetic expression it looks like. A profile may set its own `introduction_date` to become available later than the vehicle.
*   **`profiles`**: A list of performance/size variations available for this vehicle.
    *   `identifier`: Short profile identifier.
    *   `name`: Name of the profile.
    *   `size`: Relative length/size modifier.
    *   `capacity`: Cargo capacity.
    *   `power`: Power in hp for this profile; overrides the vehicle-level `stats.power`.
    *   `speed`, `design_speed`: Speeds in mph for this profile; override the vehicle-level `stats.speed` and `stats.design_speed`.
    *   `weight`: Weight in metric tons for this profile; overrides the vehicle-level `stats.weight`.
    *   `introduction_date`: Date when this profile becomes available; overrides the vehicle-level `dates.introduction_date`.
    *   `tilt`: Tilt strength for this profile, as a named level or a number.
    *   `track_type`: Track types for this profile (see Track types below), e.g. a dual-voltage formation alongside a single-system one.
    *   `has_cab`: `true` when this profile is a driving vehicle (see Driving vehicles below).
    *   `lighting`: `auto`, `exact` or `none` for this profile (see Lighting overlays below).
    *   `spritesheet`: A spritesheet of this profile's own, instead of the candidate's `<Vehicle>.png` (see Standalone spritesheets below).
    *   `cargo`: Cargo preset or classes for this profile, overriding the vehicle's `cargo`.
    *   `special_tags`: List of custom tags triggering special badges for this profile's variants.
    *   `types`: Target vehicle type variants (e.g. `[train, tram]`). Rows are matched once per vehicle, against the vehicle's own `stats.vehicle_type`, so a variant emitted as a road vehicle is drawn with the `tmpl_tram_*` twin of whichever template its row matched: the twins are deliberately the same shape as the train templates and differ only in the offsets that place a tram on the road. Both variants of a profile therefore share one set of sprites, with different placement.
*   **`liveries`**: Visual variations (liveries) available for the vehicle.
    *   `name`: Name of the livery.
    *   `sprite_override`: Custom sprite template file to map.
    *   `profiles`: List of profile identifiers this livery applies to.
    *   `power`: Power in hp for this livery; overrides the vehicle default, but not the profile.
    *   `weight`: Weight in metric tons for this livery; overrides the vehicle default, but not the profile.
    *   `tilt`: Tilt strength for this livery; overrides the vehicle default, but not the profile.
    *   `track_type`: Track types for this livery; overrides both profile and vehicle (see Track types below).
    *   `has_cab`: `true` when this livery is a driving vehicle; overrides both profile and vehicle.
    *   `lighting`: `auto`, `exact` or `none` for this livery; overrides both profile and vehicle.
    *   `spritesheet`: A spritesheet of this livery's own; overrides both profile and vehicle (see Standalone spritesheets below).
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
    *   `nml_override`: Point one of the vehicle's graphics callbacks at a hand-written switch instead of the generated one (see "Integrating custom NML" below).

Statistical fields that appear on both a profile and a livery are resolved per variant: the livery wins, then the profile, then the vehicle. The narrowest statement wins, so one livery of a unit can override its profile — use them when one formation or operator really differs, for example a longer multiple unit whose extra vehicles add power and weight.

#### Variant names

A variant's name is built from the vehicle's `info.name`, then its profile and its livery.
A profile or livery called **Default** is treated as "this unit has no separate name" and is
left out rather than shown as a label, so the purchase list reads as the vehicle itself
instead of a placeholder:

| Vehicle | Profile | Livery | Name shown |
|---|---|---|---|
| Conflat A Container Wagon | Default | Default | Conflat A Container Wagon |
| Thomas the Tank Engine | Default | Blue | Thomas the Tank Engine - Blue |
| Class 221 Voyager | 5-Car | Virgin Trains | Class 221 Voyager - 5-Car - Virgin Trains |

That gives three levels of detail without repeating "Default" anywhere: a single-formation
unit lists under its own name, a named livery disambiguates it, and a multi-formation unit
also names the formation. The profile name is what a unit uses for a formation or length
difference, and the livery name for a paint/operator difference.

OpenTTD's purchase list groups a candidate's liveries: the group row shows the vehicle and
profile ("Class 221 Voyager - 5-Car") and the child rows return the full variant name, so
the livery only appears on the rows that need it.

#### Design vs service speed

`speed` is the service speed: the limit the vehicle normally runs to. `design_speed` is
the maximum it is designed for, and is optional — most units have only one published
figure and need no `design_speed` at all. When a unit has both, BRBuild emits the
`speed` graphics callback as a selector driven by the project's `param_speed_mode`
parameter, so the player picks between the two:

* `param_speed_mode: 1` (the usual default) returns the design speed;
* `param_speed_mode: 0` returns the service speed.

When only one figure is set, both settings resolve to it and the property is written
plainly with no callback, so a unit without a documented pair is unaffected by the
parameter. A design speed lower than the service speed is accepted but logged, because
it normally means the two were swapped.

Both figures stay in mph in the YAML: the property is written as an `mph` literal, which
nmlc converts, and the callback carries the converted number because a callback result is
an expression — NML takes no unit literal there and converts nothing. The conversion lives
in `Vehicle/Translator/Speed.py` and reproduces nmlc's own mph handling exactly, so that
the two settings of the parameter read back as the figures that were authored.

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

#### Track types

`track_type` says which infrastructure a train can use. It is a list of the project's
*logical* track types, not railtype labels, and is resolved livery → profile → vehicle.
Trains only: a road vehicle's running gear is `road_type`/`tram_type`, so a tram ignores it.

```yaml
stats:
  power_type: [electric, third_rail]
  track_type: [THIRD]          # third rail only: `THIRD` may fall back to ELRL

# Dual-voltage in one file: the profile carries the extra system.
profiles:
  - identifier: third_rail
    track_type: [THIRD]
  - identifier: dual_voltage
    track_type: [THIRD, ELRL]  # can use overhead electric regardless of fallbacks
```

Left unset, the vehicle's `power_type` decides, so most candidates need to say nothing:

| `power_type` | Track types |
|---|---|
| `steam`, `diesel`, `hydrogen`, `battery`, `gas_turbine`, unpowered stock | `[RAIL]` |
| `electric`, `ohle`, `overhead`, `catenary` | `[ELRL]` |
| `electric` + `third_rail` | `[THIRD]` |
| `electric` + `fourth_rail` | `[FOURTH]` |
| self-powered + `electric` (bi-mode) | `[RAIL, ELRL]` |
| self-powered + `third_rail` | `[RAIL, THIRD]` |
| `fourth_rail` + `third_rail` (two systems, not two rails) | `[FOURTH, THIRD]` |

`RAIL` is compatible with electrified track too, which is why a self-powered unit asks for
it: a diesel can use overhead-wired or third-rail track without needing any electric
supply of its own. The explicit field always wins, so a vehicle is never stuck with what
the classifier inferred.

What each logical type resolves to is a property of the set, not of the unit, and lives in
`src/grf/RailTypes.yaml`. When a candidate set does not provide that file it gets the
BRTrains table:

```yaml
RAIL: [RAIL]                      # unelectrified: the plain rail label
ELRL: [SAAA, SAAE, ELRL]          # overhead electric
THIRD: [SAA3, 3RDR, ELRL]         # third rail, then older labels, then overhead
FOURTH: [SAA4, SAA3, 4RDR, ELRL]  # fourth rail, then third, then overhead
```

- The list is an ordered preference: the first label some loaded track set defines is the
  one used, so a unit stays available when no track set defines its own supply.
- `SAA3`/`SAAE`/`SAA4` are [Standardized Railtype
  Scheme](https://newgrf-specs.tt-wiki.net/wiki/Standardized_Railtype_Scheme) labels:
  `S` standard gauge, `A` the train-set speed class, `A` the axle-load class, then the
  energy source (`N` none, `E` overhead, `3` third rail, `4` fourth rail).
- A type with a single label is written as that label; nmlc rejects an empty fallback
  list. A label that is not a bare identifier (`3RDR`, `4RDR`) is quoted.
- Declaring the file replaces NML's default table, so every standard label the project
  still uses has to be listed in it.

#### Driving vehicles (`has_cab`)

An unpowered vehicle with a driving cab — a DVT, a DBSO, a driving trailer — can lead a rake,
which decides how OpenTTD 16+ reverses a train: with a cab at the far end it **backs up**
(keeping every vehicle's facing and its artwork), and without one it magic-flips the consist.

```yaml
has_cab: true          # stats, a profile or a livery
```

- Emits `extra_flags: bitmask(VEHICLE_FLAG_TRAIN_HAS_CAB)` on the variant's train item.
- Resolved livery → profile → vehicle, like every other per-variant field, so one vehicle can
  carry a driving variant among ordinary coaches.
- Only meaningful for a train, and only emitted for one: a tram has no back-up state, so
  `has_cab` on a road-vehicle variant is ignored (logged at debug) rather than written into the
  road-vehicle property block, where the bit means something else.
- Unset emits nothing, so a candidate that does not use it produces byte-identical output.

#### Standalone spritesheets (`spritesheet`)

By default a candidate's rows all live in its own `<Vehicle>.png`. A profile or a livery can
name a sheet of its own instead:

```yaml
profiles:
  - identifier: mk3_dvt
    spritesheet: BRMk3DVT.png   # beside the candidate's YAML
    has_cab: true
```

- The path is relative to the candidate folder (an absolute path is accepted as-is) and is
  resolved at load.
- Rows are consumed from that sheet with its own cursor, using the same detection, template
  matching and `<sheet>.png.sheetcache.json` cache as the candidate's own sheet, so a
  standalone sheet is held to exactly the same geometry contract.
- The group's purchase icon and lighting overlays are read from the sheet the rows came from,
  and each sheet gets its own `<Sheet>_lights.png` overlay.
- `sprite_group` sharing is unaffected: a profile that reuses another profile's rows also reuses
  that profile's sheet.
- Ingest works per sheet: drop one PNG per sheet in `new/`, named after the sheet it replaces
  (a single unnamed drop still goes to the candidate's own sheet, as before). Anything
  ambiguous fails the build rather than rewriting the wrong artwork, and a failed candidate
  parks every dropped sheet in `error/`.

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

If a vehicle candidate folder contains `.pnml` files (e.g., `Thomas.pnml` alongside `Thomas.yaml`), BRBuild will automatically discover them and collate them into the generated NML **before** the vehicle's own generated blocks, so the candidate's switches and spritesets are in scope whenever its item references them.

A project can also keep NML that is not tied to a candidate in `<grf_folder>/custom_nml/`; every file below that folder is collated into the same place. Files below `<grf_folder>/custom_nml/append/` are collated after all generated vehicle blocks, for declarations such as purchase-list sort blocks that refer to generated item symbols.

Either way the file is staged into `WorkingData/<project>/` and copied rather than compiled in place, and the quoted paths inside it are rewritten to absolute paths resolved against the file's own folder first, then the project root. That is what lets a candidate `.pnml` address its images the way the artist wrote them:

```nml
spriteset(spriteset_container_0, "Container.png") { tmpl_train_8(0, 0) }
```

Collation order is: the GRF header and parameters, the `template` blocks, project-level `custom_nml`, the badge table, then each vehicle's own `.pnml` immediately before that vehicle's generated blocks. NML resolves identifiers before generating output, so a hand-written file must still declare its own symbols in dependency order (leaves first, entry switch last).

Vehicle-level NML is deliberately kept adjacent to its own vehicle rather than hoisted with the GRF-scoped files. A `switch` holds a concurrent spritegroup slot while it is in scope and OpenTTD allows only 255 of them, so keeping each chain next to the item that uses it costs nothing while it is not being built.

### Pointing a callback at your own NML: `nml_override`

For a unit whose graphics chain the YAML model cannot express — cargo-count or cargo-subtype driven sprites, weighted `random_switch` choices — hand the builder the switch and let it keep out of the way:

```yaml
nml_override:
  default: sw_my_unit_root_switch
```

* The value is emitted verbatim as the callback's target in the item's `graphics {}` block.
* The callback's own generated switch is **not** generated, so the two cannot shadow each other. Other callbacks (`name`, `length`, `articulated_part`, `purchase`, …) are still generated as usual, and `length`/`articulated_part` can be overridden individually.
* It may be set on the vehicle, a profile, or a livery; the values merge vehicle first, then profile, then livery, so a livery can point one of its own variants elsewhere.
* Recognised callback names are validated when the file loads — an unknown or misspelled one fails the build immediately rather than emitting a callback NML will not accept. The keys are the graphics callbacks listed in section 7 (`default`, `purchase`, `colour_mapping`, `cargo_subtype_text`, `create_effect`, `sound_effect`, `refit_cost`, `visual_effect`, …).

This is deliberately an escape hatch, not a second schema: keep the chain in NML, keep the vehicle's data in YAML, and only reach for it when expressing the behaviour as builder fields would not be worth it.

## 6. Sprite IDs and releases

BRBuild stores the numeric vehicle IDs used in `item()` definitions in `src/grf/VehicleIDData.yaml`. The registry identifies a variant by vehicle, profile, livery, and vehicle type. Generated GNML is archived beside that file so released variants can remain in the GRF after they are removed or changed.

Normal development builds reuse IDs from variants that were not seen in the build. Run with `--release` when the set of variants is ready to be savegame-compatible: active IDs are locked, and changes to capacity, articulated-part count, or individual part lengths create a new ID. The previous definition is retained with `NO_CLIMATE` and `(DEPRECATED)` so it remains loadable but cannot be purchased.

## Lighting overlays (directional headlights)

A train's headlights are drawn into its artwork, so before OpenTTD 16 a train that reversed looked
right because the game flipped the whole consist: whichever drawing led, its lamps led with it. A train
that now *backs up* instead keeps its arrangement, so the leading end's lamps are the trailing end's
drawing — the lamps are at the wrong end of the train.

BRBuild handles this by drawing a second sprite layer over the vehicle: layer 0 as published, layer 1 an
overlay that holds the lamps of the opposite running state and is transparent everywhere else. Layer 1
takes over while `vehicle_is_flipped != train_is_driving_backwards` — the XOR of "this vehicle is drawn
turned around" (ctrl+click) and "the train is backing up" — which is exactly when the published lamps sit
at the wrong end. The layer switch stores the stack flags in temporary register `0x100`
(`CB_FLAG_MORE_SPRITES | PALETTE_USE_DEFAULT` for layer 0, `PALETTE_IDENTITY` for layer 1), and the
misc flag `TRAIN_FLAG_SPRITE_STACK` is added to any variant that gets an overlay.

### What counts as a lamp

- Candidates are single pixels of the lamp shades, searched brightest first (`0F`, `A1`, `45`, `34`, `44`);
  within a cluster only the brightest shade counts, so a dimmer glow does not widen the lamp.
- A lamp is *not* a lamp unless it changes state: the counterpart pixel, in the view four along of the
  other drawing, must not itself be one of the lit shades (`0F`, `0E`, `0D`, `45`, `44`, `34`, `A1`).
- A multiple unit pairs the drawing at its first consist position with the one at its last: the leading
  end's lamps against the trailing end's. A single-unit vehicle (locomotive, tank engine, single-unit
  stock) has no rear unit to compare with, so it pairs a view with the view four along inside its own
  drawing — those rows carry both the nose and the rear views.
- At most six lamp pixels are automated in one view (a double headlight is two pixels a side and a centre
  repeater adds a pair). End-on views (N and S) must be mirror-symmetric about the centreline, apart from
  a lone centre repeater pixel.
- Anything not clearly identified — a view over the cap, asymmetric lamps, a lamp with nothing drawn on
  the counterpart pixel, a drawing whose lamps are in no shade we accept — is logged and left alone: the
  unit keeps its published artwork until someone deals with it manually. Units with no headlights drawn
  at all (much early steam) are in this group by design.
- **The trailing-lamp rule, for driving cars only.** A driving vehicle (`has_cab`) draws its lamps
  *red*: a DVT's cab faces away from the train in the normal state, so the art shows the tail lamps and
  has no white counterpart anywhere for the rule above to pair with — which would leave its lamps red
  while the train drives backwards. For those vehicles, and only those, an **end is recognised by an
  end-on face whose isolated bright-red pixels (`B6`, `B7`) mirror about its own centreline, or by the
  diagonal pair that mirrors across the box width** — the diagonals are where a train on diagonal track
  is drawn, and they still identify the lamps on a drawing whose end-on pair the livery's red band
  swamps. The side pair is taken too when it mirrors. Kept pixels are capped at the six-lamp limit and
  repainted white (`0F`), the state the lamps take while the train drives backwards. Lamps on **both**
  ends of a drawing is ambiguous about which end trails and is left to a human; so is a view over the
  cap. A locomotive or multiple unit never reaches this rule: it already pairs, and its `has_cab` is
  unset.

The overlay paints the counterpart's own value at the lamp pixel, so the shade is reciprocated rather
than replaced; the trailing-lamp rule paints the white the lamps take when the train drives backwards.

### Assuming a livery's lamps from its siblings (`lighting`)

A class is drawn once per livery, and a livery whose lamps the detector cannot read otherwise keeps
its artwork as authored — no layer, no flip. Where the unit's *other* liveries do identify lamps, the
unreadable one is taken to match them: one livery of a class shows the class's lamp geometry.

The assumption is deliberately narrow, and each condition is a way for it to be wrong:

- it needs **exactly one** identified pattern; two or more different patterns is ambiguity about which
  to use, so nothing is assumed;
- the pattern must come from the **same spritesheet and the same template**, because a pattern is
  recorded relative to the view boxes;
- the pattern must come from a drawing the detector **did not flag** (not over the lamp cap, not
  asymmetric, not assumed itself), since a rejected row is not evidence;
- the target must be a drawing the detector said **nothing at all** about — a rejected row keeps its
  flag and stays for a human;
- a variant set to **`lighting: exact`** neither gives nor takes a pattern.

`lighting` is accepted on the vehicle, a profile or a livery (livery wins), and takes:

| Value | Meaning |
|---|---|
| `auto` | the default: detect the lamps, and fill an unreadable livery in from its siblings |
| `exact` | trust only what this vehicle's own artwork shows (the override for a wrong guess) |
| `none` | emit no lighting layer for this variant at all |

Every assumption is labelled so it can be found and checked: the build logs a warning naming the
source and the target, the sheet's `<sheet>.lightcache.json` records `"assumed_from"` and
`"view_mapping": "assumed"` (so `grep assumed <sheet>.lightcache.json` lists every guess on that
sheet), and the detection's flags carry `lamps assumed from '<source>': verify in game`.

### Cost and caching

Detection is pure pixel work over the published sheet, so it is cached beside the sheet in
`<sheet>.lightcache.json`, keyed by the sheet bytes, the palette, the template geometry, the rules
version and the pairings it was asked about. An unchanged rebuild re-uses every entry and does no
detection at all; the generated overlay and transparency sheets are only rewritten when their contents
change, so nmlc's sprite cache stays valid. The cache is derived data: it is not a build input and
belongs in each project's `.gitignore`.

The overlay and transparency sheets are written to `WorkingData/<project>/`, beside the generated
purchase icons. One transparent spriteset per vehicle and template is shared by every part that needs
one, rather than one per articulated part.

On BRTrains3 (189 variants) the layer adds 3592 sprites and about 337 KB to the GRF (+32%); the build
itself is unchanged within noise (about 1.6 s warm). Nothing is emitted for a project whose artwork has
no detected lamps, so such a project's output stays byte-identical.
