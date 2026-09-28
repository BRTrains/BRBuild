# Build manifest

A successful BRBuild writes `docs/generated/manifest.json` in the project after the
compiled NewGRF has been copied. The file is generated documentation, not build input;
it is intentionally not added to BRBuild's ignore rules, so a project may commit it for
BRDocs or regenerate it in CI according to its release workflow. `src/` configuration,
materialised variants, and the emitted NML remain authoritative.
Consumers should use the manifest to discover the exact successful vehicle/profile/livery
set, sprite allocation and source files without reimplementing BRBuild's resolution logic.

## Schema

`schema_version` is currently `1`. The top-level document contains the project name,
UTC ISO-8601 `generated_at`, best-effort `builder_commit`, `build_success: true`, and a
`variants` array. Each variant records its vehicle/profile/livery identity, generated NML,
materialised spritesets (file, template, length, order, origin, and actual sprite rows),
purchase sprites, lighting outputs, sprite ID/generation, sprite-group reuse, and source
restrictions. Paths are objects with a project-relative `path` and descriptive `kind`; an
absolute filesystem path is never emitted.

Spriteset and row fields are copied from the already-materialised `Spriteset`, `Template`,
and `Sprite` objects. The manifest is therefore an account of what this build emitted, not
a second graphics or variant resolver.

## Atomicity and failures

The writer serialises to a temporary file and publishes with `os.replace`. A failed write
leaves an existing successful manifest untouched. Build failures do not publish a success
manifest. If manifest generation itself fails after an otherwise successful build,
`docs/generated/manifest.failure.json` is written on a best-effort basis and the build
result is not masked.

Consumers should reject unknown major schema versions and tolerate added fields. A future
incompatible format will increment `schema_version`; additive fields remain compatible
within version 1.
