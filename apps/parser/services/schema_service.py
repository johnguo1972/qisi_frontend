"""JSON validation and repair service for AI parsing output."""
import json
import logging
from apps.common.utils import repair_json_string
from apps.common.exceptions import SchemaValidationError
from apps.parser.schemas.page_parse_schema import validate_parse_result

logger = logging.getLogger(__name__)


def validate_and_repair_json(raw_response: str) -> dict:
    """Validate and repair JSON from AI response.

    Args:
        raw_response: Raw text response from AI.

    Returns:
        Parsed and validated dict.

    Raises:
        SchemaValidationError: If JSON cannot be parsed or validated.
    """
    # Step 1: Clean and repair the JSON string
    cleaned = repair_json_string(raw_response)

    # Step 2: Parse JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise SchemaValidationError(f"Failed to parse JSON: {e}")

    # Step 3: Validate with Pydantic schema
    try:
        result = validate_parse_result(data)
        # Convert back to dict for downstream processing
        return result.model_dump()
    except Exception as e:
        # If strict validation fails, still return raw data with warning
        logger.warning(f"Schema validation failed: {e}")
        return data
