import pytest
from validators.validators import _validate_range, _validate_type, _validate_enum, validate_command, ValidationRule, ValidationType

# ------------ Validation Rule Class Success cases ------------
class TestClassSuccess:
    def test_type_rule_valid(self):
        val = {"validation_type": "type", "expected_type": "str"}
        rule = ValidationRule(**val)
        assert rule.validation_type == ValidationType.type
        assert rule.expected_type is not None
        assert rule.min_value is None
        assert rule.max_value is None
        assert rule.allowed_values is None

    def test_range_rule_valid(self):
        val = {
            "validation_type": "range",
            "min_value": 0,
            "max_value": 100
        }
        rule = ValidationRule(**val)
        assert rule.validation_type == ValidationType.range
        assert rule.min_value == 0
        assert rule.max_value == 100

    def test_enum_rule_valid(self):
        val = {
            "validation_type": "enum",
            "allowed_values": ["eco", "boost", "off"]
        }
        rule = ValidationRule(**val)
        assert rule.validation_type == ValidationType.enum
        assert rule.allowed_values == ["eco", "boost", "off"]


# ------------ Validation Rule Class Failure cases ------------
class TestClassFailure:
    def test_range_rule_missing_min_value(self):
        val = {
            "validation_type": "range",
            "max_value": 100
        }
        with pytest.raises(Exception) as excinfo:
            ValidationRule(**val)
        assert "min_value" in str(excinfo.value)

    def test_range_rule_missing_max_value(self):
        val = {
            "validation_type": "range",
            "min_value": 0
        }
        with pytest.raises(Exception) as excinfo:
            ValidationRule(**val)
        assert "max_value" in str(excinfo.value)

    def test_enum_rule_missing_allowed_values(self):
        val = {
            "validation_type": "enum",
        }
        with pytest.raises(Exception) as excinfo:
            ValidationRule(**val)
        assert "allowed_values" in str(excinfo.value)

    def test_invalid_enum_type_string(self):
        val = {
            "validation_type": "not_a_type",
        }
        # if someone tries to pass a string not in ValidationType
        with pytest.raises(Exception):
            ValidationRule(**val)


# ------------ Validation Rule Class Edge cases ------------
class TestClassEdge:
    def test_range_rule_accepts_float_bounds(self):
        val = {
            "validation_type": "range",
            "min_value": 0.1,
            "max_value": 99.9
        }
        rule = ValidationRule(**val)
        assert isinstance(rule.min_value, float)
        assert isinstance(rule.max_value, float)

    def test_enum_rule_empty_list_rejected(self):
        val = {
            "validation_type": "enum",
            "allowed_values": []
        }
        with pytest.raises(Exception):
            ValidationRule(**val)

            
# ------------ Range Validator ------------
class TestRange:
    def test__validate_range_success_int(self):
        rule = ValidationRule(**{"validation_type": "range","min_value": 0, "max_value": 10})
        assert _validate_range(0, rule) == 0
        assert _validate_range(5, rule) == 5
        assert _validate_range(10, rule) == 10

    def test__validate_range_success_float(self):
        rule = ValidationRule(**{"validation_type": "range","min_value": 0, "max_value": 10})
        assert _validate_range(0.0, rule) == 0
        assert _validate_range(10.0, rule) == 10

    def test__validate_range_below_min(self):
        rule = ValidationRule(**{"validation_type": "range","min_value": 0, "max_value": 10})
        with pytest.raises(ValueError):
            _validate_range(-1, rule)

    def test__validate_range_above_max(self):
        rule = ValidationRule(**{"validation_type": "range","min_value": 0, "max_value": 10})
        with pytest.raises(ValueError):
            _validate_range(11, rule)
        with pytest.raises(ValueError):
            _validate_range(10.001, rule)

    def test__validate_range_type_error(self):
        rule = ValidationRule(**{"validation_type": "range","min_value": 0, "max_value": 10})
        with pytest.raises(ValueError):
            _validate_range("not_a_number", rule)


# ------------ Type Validator ------------
class TestType:
    def test_validate_type_success(self):
        rule = ValidationRule(**{"validation_type": "type", "expected_type": "str"})
        assert _validate_type("hello", rule) is "hello"
        rule = ValidationRule(**{"validation_type": "type", "expected_type": "bool"})
        assert _validate_type(False, rule) is False

    def test_validate_type_fail(self):
        rule = ValidationRule(**{"validation_type": "type", "expected_type": "bool"})
        with pytest.raises(ValueError):
            _validate_type("True", rule)
        with pytest.raises(ValueError):
            _validate_type(1, rule)


# ------------ Enum Validator ------------
class TestEnum:
    def test_validate_enum_success(self):
        rule = ValidationRule(**{"validation_type": "enum", "allowed_values": ["START", "STOP"]})
        assert _validate_enum("START", rule) == "START"

    def test_validate_enum_fail(self):
        rule = ValidationRule(**{"validation_type": "enum", "allowed_values": ["START", "STOP"]})
        with pytest.raises(ValueError):
            _validate_enum("PAUSE", rule)

    def test_validate_enum_missing_allowed(self):
        with pytest.raises(ValueError):
            rule = ValidationRule(**{"validation_type": "enum"})
            _validate_enum("START", rule)


# ------------ Generic Entry Point ------------
class TestGeneric:
    def test_validate_command_range(self):
        rule = {"validation_type": "range", "min_value": 0, "max_value": 100}
        assert validate_command(50, [rule]) == 50

    def test_validate_command_bool(self):
        rule = {"validation_type": "type", "expected_type": "bool"}
        assert validate_command(True, [rule]) is True

    def test_validate_command_enum(self):
        rule = {"validation_type": "enum", "allowed_values": ["ON", "OFF"]}
        assert validate_command("ON", [rule]) == "ON"

    def test_validate_command_invalid_type(self):
        with pytest.raises(ValueError):
            validate_command(123, [{"validation_type": "unknown"}])

    # TODO: test multiple rules validation at the same time