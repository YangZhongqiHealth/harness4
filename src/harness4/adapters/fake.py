"""Credential-free, deterministic provider for lifecycle and fault-injection tests."""
from collections import deque
import time

from ..contracts import ErrorCode, ModelRef
from ..model_contracts import CapabilityProfile, ModelDelta, ModelRequest, ModelResponse
from ..provider_errors import ProviderFailure
from .model_validation import validate_request_schemas, validate_response


class FakeProvider:
    def __init__(self, script: tuple[ModelResponse | ProviderFailure, ...], *, profile: CapabilityProfile):
        self._script = deque(script)
        self.profile = profile.model_copy(update={'verified': (), 'checked_at_unix_ms': None})
        self.requests: list[ModelRequest] = []

    async def capabilities(self, model: ModelRef) -> CapabilityProfile:
        if model != self.profile.model:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Model does not match fake profile.', 'configuration')
        return self.profile

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.model != self.profile.model:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Model does not match fake profile.', request.request_id)
        if request.deadline_unix_ms <= time.time_ns() // 1_000_000:
            raise ProviderFailure(ErrorCode.TIMEOUT, 'Model deadline expired before dispatch.', request.request_id)
        needs_tools = bool(request.tools) or any(m.tool_calls or m.role == 'tool' for m in request.messages)
        if ((needs_tools and not self.profile.native_tools) or (request.output_schema_json and not self.profile.structured_output)):
            raise ProviderFailure(ErrorCode.UNSUPPORTED_CAPABILITY, 'Fake profile does not support request.', request.request_id)
        if request.max_output_tokens > self.profile.max_output_tokens:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Output limit exceeds fake profile.', request.request_id)
        try:
            validate_request_schemas(request)
        except (ValueError, RecursionError):
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Invalid or unsupported inline JSON Schema.', request.request_id) from None
        if not self._script:
            raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Fake script exhausted.', request.request_id)
        self.requests.append(request)
        result = self._script.popleft()
        if isinstance(result, ProviderFailure):
            raise ProviderFailure(result.error.code, result.error.message, request.request_id, result.error.retryable)
        # Templates receive the caller's IDs; all content still undergoes real validation.
        result = result.model_copy(update={'request_id': request.request_id, 'attempt_id': request.attempt_id})
        try:
            return validate_response(request, result)
        except (ValueError, RecursionError):
            raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Fake output violates request schema.', request.request_id) from None

    async def stream(self, request: ModelRequest):
        if not self.profile.streaming:
            raise ProviderFailure(ErrorCode.UNSUPPORTED_CAPABILITY, 'Fake profile does not support streaming.', request.request_id)
        response = await self.generate(request)
        seq = 1
        if response.text:
            yield ModelDelta(request_id=request.request_id, attempt_id=request.attempt_id, seq=seq, kind='text', text=response.text)
            seq += 1
        yield ModelDelta(request_id=request.request_id, attempt_id=request.attempt_id, seq=seq, kind='final', response=response)
