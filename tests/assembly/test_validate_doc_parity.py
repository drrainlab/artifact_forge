"""validate_assembly_doc is the object-entry twin of run_assembly_validate:
same catalog, same document, byte-identical report. The intent repair loop
re-validates parsed assemblies without a tempfile round-trip — this parity
test pins the wrapper split as a pure refactor."""

from pathlib import Path

from artifact_forge_ng.assembly.pipeline import (
    load_assembly,
    run_assembly_validate,
    validate_assembly_doc,
)
from artifact_forge_ng.catalog.loader import load_catalog

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
ESP32 = EXAMPLES / "esp32_box_with_lid.yaml"


def test_doc_and_path_entry_points_agree():
    catalog = load_catalog()
    asm = load_assembly(ESP32)
    assert validate_assembly_doc(asm, catalog, None) == run_assembly_validate(
        ESP32, None
    )


def test_doc_entry_point_accepts_strict_override():
    catalog = load_catalog()
    asm = load_assembly(ESP32)
    out = validate_assembly_doc(asm, catalog, False)
    assert out["status"] == "pass"
    assert out["assembly"] == asm.id
