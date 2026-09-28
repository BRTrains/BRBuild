import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from Builder.ManifestWriter import ManifestWriter
from Sprites.Sprite import Sprite
from Sprites.Spriteset import Spriteset
from Templates.Template import Template


def _variant(root):
    sheet = root / "src" / "vehicles" / "A.png"
    nml = root / "WorkingData" / "Demo" / "a.nml"
    spriteset = Spriteset(
        "spriteset_a_0", str(sheet), Template("tmpl_train_8", [Sprite(1, 2, 8, 9, 3, 4, ["foo"])]), 10, 20
    )
    vehicle = SimpleNamespace(identifier="a", name="Alpha", spritesheet_path=str(sheet), special_tags=["express"])
    profile = SimpleNamespace(identifier="standard", name="Standard", sprite_group="base", profiles=None)
    livery = SimpleNamespace(name="Blue", profiles=["standard"], spritesheet=None)
    return SimpleNamespace(
        vehicle=vehicle, profile=profile, livery=livery, identifier="a_standard_blue",
        nml_filename=str(nml), vehicle_type=SimpleNamespace(name="TRAIN"), articulated_count=2,
        spritesets=[spriteset], sprite_template_names=["tmpl_train_8"], sprite_lengths=[8],
        spriteset_names=["spriteset_a_0"], purchase_spriteset=spriteset,
        sprite_pattern=[1, 2, 3, 4, 2, 3, 4],
        purchase_spriteset_name="spriteset_a_purchase", purchase_template_name="tmpl_train_8",
        lighting_overlay_path=root / "src" / "generated" / "a_lighting.png",
        lighting_transparent_path=None, sprite_id=42, sprite_id_generation=3,
        properties={"variant_group": 41},
    )


def test_manifest_contains_every_materialised_variant_and_real_rows(tmp_path):
    project = SimpleNamespace(name="Demo", path=tmp_path)
    manifest = ManifestWriter(project, [_variant(tmp_path)]).build_document(builder_commit="abc")

    assert manifest["schema_version"] == 1
    assert manifest["project"] == "Demo"
    assert manifest["build_success"] is True
    assert len(manifest["variants"]) == 1
    item = manifest["variants"][0]
    assert item["vehicle"]["identifier"] == "a"
    assert item["profile"]["identifier"] == "standard"
    assert item["livery"]["name"] == "Blue"
    assert item["spritesets"][0]["template"] == "tmpl_train_8"
    assert item["spritesets"][0]["length"] == 8
    assert item["spritesets"][0]["order"] == 0
    assert item["spritesets"][0]["rows"][0]["width"] == 8
    assert item["purchase"]["template"] == "tmpl_train_8"
    assert item["sprite_id"] == {"id": 42, "generation": 3}
    assert item["sprite_group"]["source"] == "base"
    assert item["formation"] == {"part_count": 7, "sprite_pattern": [1, 2, 3, 4, 2, 3, 4]}
    assert manifest["profiles"][0]["resolved"]["sprite_pattern"] == [1, 2, 3, 4, 2, 3, 4]

    def assert_no_absolute(value):
        if isinstance(value, dict):
            for v in value.values(): assert_no_absolute(v)
        elif isinstance(value, list):
            for v in value: assert_no_absolute(v)
        elif isinstance(value, str):
            assert not Path(value).is_absolute()
    assert_no_absolute(manifest)


def test_write_is_atomic_and_preserves_previous_manifest_on_failure(tmp_path, monkeypatch):
    project = SimpleNamespace(name="Demo", path=tmp_path)
    writer = ManifestWriter(project, [_variant(tmp_path)])
    target = tmp_path / "docs" / "generated" / "manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"old": true}\n', encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr("Builder.ManifestWriter.os.replace", fail_replace)

    with pytest.raises(OSError):
        writer.write()
    assert target.read_text(encoding="utf-8") == '{"old": true}\n'
    assert not list(target.parent.glob(".manifest.json.*.tmp"))
