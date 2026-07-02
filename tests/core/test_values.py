import pytest

from artifact_forge_ng.core.values import (
    normalize_formula,
    parse_delta,
    parse_quantity,
    parse_value,
)


class TestParseQuantity:
    def test_plain_mm(self):
        assert parse_quantity("20mm", "length") == 20.0

    def test_spaced_and_cm(self):
        assert parse_quantity("2 cm", "length") == 20.0

    def test_bare_number_is_canonical(self):
        assert parse_quantity("12", "length") == 12.0

    def test_angle(self):
        assert parse_quantity("90deg", "angle") == 90.0

    def test_unknown_unit_fails(self):
        with pytest.raises(ValueError, match="unknown unit"):
            parse_quantity("20parsec", "length")

    def test_dimension_mismatch_fails(self):
        with pytest.raises(ValueError, match="needs length"):
            parse_quantity("30deg", "length")

    def test_malformed_fails(self):
        with pytest.raises(ValueError, match="malformed"):
            parse_quantity("mm20", "length")

    def test_unknown_type_fails(self):
        with pytest.raises(ValueError, match="unknown parameter type"):
            parse_quantity("20mm", "distance")


class TestParseValue:
    def test_number_literal(self):
        v = parse_value(0.35, "number")
        assert v.kind == "literal" and v.literal == 0.35

    def test_quantity_string(self):
        v = parse_value("3.2mm", "length")
        assert v.kind == "literal" and v.literal == 3.2

    def test_expr(self):
        v = parse_value("expr(bundle_d * 0.55)", "length")
        assert v.kind == "expr"
        assert v.resolve({"bundle_d": 20.0}) == pytest.approx(11.0)

    def test_expr_dot_normalization(self):
        v = parse_value("expr(printer.min_wall * 2)", "length")
        assert v.formula == "printer_min_wall * 2"
        assert v.resolve({"printer_min_wall": 0.8}) == pytest.approx(1.6)

    def test_float_literal_dot_untouched(self):
        assert normalize_formula("bundle_d * 0.55") == "bundle_d * 0.55"

    def test_expr_wrapper_stripped_in_formula_position(self):
        assert normalize_formula("expr(a + b)") == "a + b"

    def test_empty_expr_fails(self):
        with pytest.raises(ValueError, match="empty expr"):
            parse_value("expr()", "length")

    def test_bool_for_length_fails(self):
        with pytest.raises(ValueError, match="boolean"):
            parse_value(True, "length")

    def test_source_round_trip(self):
        v = parse_value("2 cm", "length")
        assert v.to_yaml() == "2 cm"


class TestParseDelta:
    def test_positive_delta(self):
        d = parse_delta("+3mm", "length")
        assert d.kind == "add"
        assert d.apply(10.0, {}) == 13.0

    def test_negative_delta(self):
        d = parse_delta("-1.5mm", "length")
        assert d.apply(10.0, {}) == 8.5

    def test_absolute_set(self):
        d = parse_delta("12mm", "length")
        assert d.kind == "set" and d.apply(99.0, {}) == 12.0

    def test_expr_delta(self):
        d = parse_delta("expr(bundle_d * 0.5)", "length")
        assert d.apply(0.0, {"bundle_d": 20.0}) == 10.0

    def test_yaml_number_is_absolute(self):
        assert parse_delta(-3, "length").kind == "set"
