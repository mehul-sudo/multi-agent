"""
Structured Output and JSON Schema Validation Helper.

Safely parses and validates LLM response text against JSON Schemas or Pydantic models
without using unsafe eval() or dynamic code execution.
"""

import json
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, ValidationError

from app.llm.errors import LLMResponseFormatError


def parse_and_validate_json(
    raw_text: str,
    json_schema: Optional[Dict[str, Any]] = None,
    pydantic_model: Optional[Type[BaseModel]] = None,
) -> Dict[str, Any]:
    """Parse raw text into JSON and validate against schema or Pydantic model.

    Args:
        raw_text: Text string returned by LLM.
        json_schema: Optional dict containing JSON Schema specification.
        pydantic_model: Optional Pydantic BaseModel class for validation.

    Returns:
        Validated dict data.

    Raises:
        LLMResponseFormatError: If raw_text is not valid JSON or fails schema validation.
    """
    cleaned_text = raw_text.strip()

    # Extract JSON string if wrapped in markdown codeblocks (e.g. ```json ... ```)
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    cleaned_text = cleaned_text.strip()

    if not cleaned_text:
        raise LLMResponseFormatError("LLM response text is empty; expected valid JSON.")

    try:
        parsed_data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise LLMResponseFormatError(
            f"Failed to parse LLM text output as JSON: {exc.msg} at line {exc.lineno} col {exc.colno}."
        ) from exc

    if not isinstance(parsed_data, dict):
        raise LLMResponseFormatError(f"LLM JSON response must be a JSON object (dict), got {type(parsed_data).__name__}.")

    # Validate against Pydantic model if provided
    if pydantic_model:
        try:
            model_inst = pydantic_model.model_validate(parsed_data)
            return model_inst.model_dump(mode="json")
        except ValidationError as exc:
            first_err = exc.errors()[0]
            field_loc = ".".join(str(p) for p in first_err.get("loc", ())) or "data"
            raise LLMResponseFormatError(
                f"Structured JSON validation failed for field '{field_loc}': {first_err.get('msg', 'invalid value')}."
            ) from exc

    # Validate against JSON Schema if provided
    if json_schema and "required" in json_schema:
        required_fields = json_schema.get("required", [])
        missing = [field for field in required_fields if field not in parsed_data]
        if missing:
            raise LLMResponseFormatError(
                f"Structured JSON output missing required fields: {', '.join(missing)}."
            )

    return parsed_data
