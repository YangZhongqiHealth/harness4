"""Versioned, immutable model boundary. No provider SDK objects or credentials."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .contracts import ModelRef, Record, UsageSummary


def strict_object(text: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('non-finite JSON constant')

    result = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if not isinstance(result, dict):
        raise ValueError('expected JSON object')
    # Also rejects overflowing numeric literals (e.g. 1e999).
    json.dumps(result, allow_nan=False)
    return result


def canonical_object(text: str) -> str:
    return json.dumps(strict_object(text), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class ToolSchema(Record):
    name: str = Field(pattern=r'^[A-Za-z_][A-Za-z0-9_-]{0,63}$')
    description: str = Field(max_length=4000)
    # Immutable JSON strings avoid shallow-frozen mutable dicts at this boundary.
    parameters_json: str = Field(max_length=100_000)

    @field_validator('parameters_json')
    @classmethod
    def valid_json(cls, value: str) -> str:
        return canonical_object(value)


class ToolCall(Record):
    call_id: str = Field(min_length=1, max_length=256)
    name: str = Field(pattern=r'^[A-Za-z_][A-Za-z0-9_-]{0,63}$')
    arguments_json: str = Field(max_length=100_000)

    @field_validator('arguments_json')
    @classmethod
    def valid_json(cls, value: str) -> str:
        return canonical_object(value)


class Message(Record):
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str = Field(default='', max_length=1_000_000)
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    source_refs: tuple[str, ...] = ()

    @model_validator(mode='after')
    def valid_role_fields(self):
        if self.tool_calls and self.role != 'assistant':
            raise ValueError('only assistant messages can propose tools')
        if (self.role == 'tool') != (self.tool_call_id is not None):
            raise ValueError('tool result requires a call ID; other roles cannot supply one')
        if self.tool_call_id == '':
            raise ValueError('empty tool call ID')
        return self


class GenerationSettings(Record):
    temperature: float | None = Field(default=None, ge=0, le=2, allow_inf_nan=False)


class ModelRequest(Record):
    request_id: str = Field(min_length=1, max_length=256)
    attempt_id: str = Field(min_length=1, max_length=256)
    model: ModelRef
    messages: tuple[Message, ...] = Field(min_length=1)
    tools: tuple[ToolSchema, ...] = ()
    max_output_tokens: int = Field(default=4096, ge=1, le=32768)
    # Absolute UTC epoch milliseconds; deterministic serialization across timezones.
    deadline_unix_ms: int = Field(ge=1)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    output_schema_json: str | None = Field(default=None, max_length=100_000)
    tool_choice: Literal['auto', 'required'] = 'auto'

    @field_validator('output_schema_json')
    @classmethod
    def valid_schema_json(cls, value: str | None) -> str | None:
        return canonical_object(value) if value is not None else None

    @model_validator(mode='after')
    def valid_conversation(self):
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError('duplicate tool name')
        if self.tool_choice == 'required' and not self.tools:
            raise ValueError('required tool choice needs tools')
        seen = set()
        pending = set()
        for message in self.messages:
            if message.role == 'tool':
                if message.tool_call_id not in pending:
                    raise ValueError('orphan or duplicate tool result')
                pending.remove(message.tool_call_id)
            else:
                if pending:
                    raise ValueError('all tool calls need results before the next message')
                for call in message.tool_calls:
                    if call.call_id in seen:
                        raise ValueError('duplicate tool call ID')
                    seen.add(call.call_id)
                    pending.add(call.call_id)
        if pending:
            raise ValueError('tool results missing at model dispatch')
        return self


class ModelResponse(Record):
    request_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    text: str = ''
    tool_calls: tuple[ToolCall, ...] = ()
    finish: Literal['stop', 'tools', 'length', 'refusal', 'error']
    usage: UsageSummary = Field(default_factory=UsageSummary)
    provider_request_id: str | None = None
    model_revision: str | None = None

    @model_validator(mode='after')
    def valid_finish(self):
        if bool(self.tool_calls) != (self.finish == 'tools'):
            raise ValueError('only a complete tool response may expose tool calls')
        ids = [call.call_id for call in self.tool_calls]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate tool call ID')
        return self


class ModelDelta(Record):
    request_id: str
    attempt_id: str
    seq: int = Field(ge=1)
    kind: Literal['text', 'final']
    text: str = ''
    response: ModelResponse | None = None

    @model_validator(mode='after')
    def valid_delta(self):
        if (self.kind == 'final') != (self.response is not None):
            raise ValueError('only final delta carries a response')
        if self.response and (self.response.request_id, self.response.attempt_id) != (self.request_id, self.attempt_id):
            raise ValueError('response identity mismatch')
        if self.kind == 'final' and self.text:
            raise ValueError('final text belongs in the response')
        return self


class CapabilityProfile(Record):
    model: ModelRef
    native_tools: bool = False
    streaming: bool = False
    structured_output: bool = False
    usage_reporting: bool = False
    context_window: int | None = Field(default=None, ge=1)
    max_output_tokens: int = Field(default=4096, ge=1, le=32768)
    verified: tuple[Literal['text', 'native_tools', 'streaming', 'structured_output', 'usage_reporting'], ...] = ()
    checked_at_unix_ms: int | None = Field(default=None, ge=1)


class ProbeResult(Record):
    capability: Literal['text', 'native_tools', 'streaming', 'structured_output', 'usage_reporting']
    passed: bool
    error_code: str | None = None


class ProbeReport(Record):
    profile: CapabilityProfile
    checks: tuple[ProbeResult, ...]
    usage: UsageSummary
    requests_made: int = Field(ge=0)
