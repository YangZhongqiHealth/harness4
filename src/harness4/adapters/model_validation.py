"""Pure validation shared by scripted and network model adapters."""
import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from ..model_contracts import ModelRequest, ModelResponse, strict_object


def schema_validator(text: str) -> Draft202012Validator:
    schema = strict_object(text)
    # Deliberately inline-only P0 schemas. Never retrieve remote schema references.
    def inspect(value):
        if isinstance(value, dict):
            if any(key in value for key in ('$ref', '$dynamicRef', '$recursiveRef')):
                raise ValueError('schema references are not supported; use inline schemas')
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(schema)
    if schema.get('type') != 'object':
        raise ValueError('top-level schema must have type object')
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ValueError('invalid JSON Schema') from None
    return Draft202012Validator(schema)


def validate_request_schemas(request: ModelRequest) -> None:
    for tool in request.tools:
        schema_validator(tool.parameters_json)
    if request.output_schema_json:
        schema_validator(request.output_schema_json)


def validate_response(request: ModelRequest, response: ModelResponse) -> ModelResponse:
    if (response.request_id, response.attempt_id) != (request.request_id, request.attempt_id):
        raise ValueError('response identity mismatch')
    catalog = {tool.name: tool for tool in request.tools}
    seen = {call.call_id for message in request.messages for call in message.tool_calls}
    try:
        for call in response.tool_calls:
            if call.name not in catalog or call.call_id in seen:
                raise ValueError('unknown tool or reused call ID')
            schema_validator(catalog[call.name].parameters_json).validate(strict_object(call.arguments_json))
        if response.finish == 'stop':
            if request.tool_choice == 'required':
                raise ValueError('required tool call absent')
            if request.output_schema_json:
                schema_validator(request.output_schema_json).validate(strict_object(response.text))
    except ValidationError:
        raise ValueError('model output violates schema') from None
    return response
