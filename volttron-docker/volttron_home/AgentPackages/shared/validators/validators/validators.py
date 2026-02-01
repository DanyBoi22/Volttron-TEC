from pydantic import BaseModel, Field, model_validator
from enum import Enum
from typing import Optional, Any, Dict, List, Union, Callable

class ValidationType(str, Enum):
    type = "type"
    range = "range"
    enum = "enum"

class ValidationRule(BaseModel):
    validation_type: ValidationType
    min_value: Optional[float] = None   # for range
    max_value: Optional[float] = None   # for range
    allowed_values: Optional[List[str]] = None  # for enum
    expected_type: Optional[str] = None # for type
    comment: Optional[str] = None

    @model_validator(mode="after")
    def check_params(self) -> "ValidationRule":
        if self.validation_type == ValidationType.range:
            if self.min_value is None or self.max_value is None:
                raise ValueError("Range validator requires 'min_value' and 'max_value'.")
        if self.validation_type == ValidationType.enum:
            if not self.allowed_values:
                raise ValueError("Enum validator requires 'allowed_values'.")
        if self.validation_type == ValidationType.type:
            if not self.expected_type:
                raise ValueError("Type validator requires 'expected_type'.")
        return self

def validate_command(value: Any, rules_list: List[Dict]) -> Any:
    """
    Generic and only validation entry point.
    
    Params:
        value: The command value to validate.
        rules_list: a List of Dict with keys:
            - 'validation_type': one of validation types
            - type-specific params.
    Returns:
        The validated value.
    Raises:
        ValueError if validation fails.
    """
    if not rules_list:
        raise ValueError(f"No rules to validate command with.")

    for rule in rules_list:
        # validate rule with pydantic
        validated_rule = ValidationRule(**rule)

        # make sure the validor exists fot the specified validation type
        if validated_rule.validation_type not in VALIDATORS:
            raise ValueError(f"Unknown validation type '{validated_rule.validation_type}'")
        
        # validate the value with according validator
        try:
            validated_value = VALIDATORS[validated_rule.validation_type](value, validated_rule)
        except Exception as e:
            raise ValueError(f"Validation failed: {e}")
        
        # varify that the validated value is same. Not actually needed.
        if not validated_value == value:
            raise ValueError(f"You should not see this error. validated value is not same as value to validate.")
        
    return value
        

# A mapping from string names to actual Python types
TYPE_MAP = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
}

def _validate_type(value: Any, rule: ValidationRule) -> Any:
    """
    Validate that a value matches the expected type.

    Params:
        value: Any value to validate.
        rule: ValidationRule Object with the requiered params like expected_type
    Returns:
        The validated value if type matches.
    Raises:
        ValueError if validation fails or unknown type is requested.
    """

    # TODO: multiple types in a list
    expected_type_str = rule.expected_type
    expected_type = TYPE_MAP.get(expected_type_str)
    if expected_type is None:
        raise ValueError(f"Unsupported type: {expected_type_str}")

    if not isinstance(value, expected_type):
        raise ValueError(
            f"Expected {expected_type_str}, got {type(value).__name__}"
        )
    return value

def _validate_range(value: Union[int, float], rule: ValidationRule) -> Union[int, float]:
    """
    Validate that the value lies within the allowed numeric range.

    Params:
        value: int or float to validate.
        rule: ValidationRule Object with the requiered params like min_value and max_value
    Returns:
        The validated numeric value.
    Raises:
        ValueError if validation fails.
    """

    if not isinstance(value, (int, float)):
        raise ValueError(f"Cannot validate reange that is not of type int or float. Received type: {type(value).__name__}")
    
    min_val = rule.min_value
    max_val = rule.max_value
    if min_val is not None and value < min_val:
        raise ValueError(f"Value {value} is below minimum {min_val}")
    if max_val is not None and value > max_val:
        raise ValueError(f"Value {value} is above maximum {max_val}")
    return value

def _validate_enum(value: Any, rule: ValidationRule) -> Any:
    """
    Validate that the value is among allowed values.
    Params:
        value: value to validate.
        rule: ValidationRule Object with the requiered params like allowed_values 
    Returns:
        The validated value.
    Raises:
        ValueError if validation fails.
    """

    allowed = rule.allowed_values
    #if not isinstance(allowed, list):
    #    raise ValueError("Validation rule missing 'allowed' list")

    if value not in allowed:
        raise ValueError(f"Value {value} not in allowed set {allowed}")
    return value

# TODO: Validate string optionaly with regex?

VALIDATORS: Dict[ValidationType, Callable[[Any, ValidationRule], Any]] = {
    ValidationType.type: _validate_type,
    ValidationType.range: _validate_range,
    ValidationType.enum: _validate_enum,
}
