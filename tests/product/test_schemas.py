"""Shape-level schema rejections that don't need the catalog."""

import pytest
from pydantic import ValidationError

from artifact_forge_ng.product.archetype import ArchetypeSpec, FormSpec, ParamSpec
from artifact_forge_ng.product.instance import ProductInstance


class TestParamSpec:
    def test_min_above_max_fails(self):
        with pytest.raises(ValidationError, match="min .* max|min 5.0 > max"):
            ParamSpec(type="length", min="5mm", max="2mm")

    def test_bad_role_fails(self):
        with pytest.raises(ValidationError):
            ParamSpec.model_validate({"type": "length", "role": "vibes"})

    def test_choice_needs_choices(self):
        with pytest.raises(ValidationError, match="choices"):
            ParamSpec.model_validate({"type": "choice"})

    def test_choice_default_must_be_member(self):
        with pytest.raises(ValidationError, match="not in choices"):
            ParamSpec.model_validate(
                {"type": "choice", "choices": ["M3", "M4"], "default": "M8"}
            )

    def test_choice_min_max_forbidden(self):
        with pytest.raises(ValidationError, match="cannot have min/max"):
            ParamSpec.model_validate(
                {"type": "choice", "choices": ["a"], "min": "1mm"}
            )


class TestFormSpec:
    def test_width_axis_must_be_normal_to_plane(self):
        with pytest.raises(ValidationError, match="normal to plane"):
            FormSpec(type="section_extrude", section="s", plane="YZ", width_axis="Y")


class TestSchemaMarker:
    BASE = {
        "id": "x",
        "archetype": "some_archetype",
    }

    def test_wrong_kind_rejected(self):
        with pytest.raises(ValidationError, match="wrong document kind"):
            ProductInstance.model_validate({"schema": "archetype/v1", **self.BASE})

    def test_malformed_marker_rejected(self):
        with pytest.raises(ValidationError, match="malformed schema marker"):
            ProductInstance.model_validate({"schema": "v1", **self.BASE})

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ProductInstance.model_validate(
                {"schema": "product/v1", **self.BASE, "surprise": 1}
            )

    def test_malformed_archetype_ref_rejected(self):
        with pytest.raises(ValidationError, match="malformed archetype ref"):
            ProductInstance.model_validate(
                {"schema": "product/v1", "id": "x", "archetype": "Bad Ref!"}
            )


def test_archetype_requires_form():
    with pytest.raises(ValidationError):
        ArchetypeSpec.model_validate(
            {"schema": "archetype/v1", "id": "a", "object_class": "c"}
        )
