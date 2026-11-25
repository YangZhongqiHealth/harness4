"""Bounded Chat Completions adapter. No automatic retries, tools or fallback execution."""
from __future__ import annotations

import asyncio
import codecs
from hashlib import sha256
import json
import os
import time
from urllib.parse import urlsplit

import httpx

from ..contracts import ErrorCode, ModelRef, UsageSummary
from ..model_contracts import CapabilityProfile, ModelDelta, ModelRequest, ModelResponse, ToolCall, strict_object
from ..provider_errors import ProviderFailure
from .model_validation import validate_request_schemas, validate_response

MAX_RESPONSE_BYTES = 1_000_000


def now_ms() -> int:
    return time.time_ns() // 1_000_000


class OpenAICompatibleProvider:
    def __init__(self, *, base_url: str, profile: CapabilityProfile, key_env: str = 'H4_MODEL_KEY',
                 token_parameter: str = 'max_tokens', transport: httpx.AsyncBaseTransport | None = None):
        try:
            url = urlsplit(base_url)
            invalid = (url.scheme not in {'https', 'http'} or not url.hostname or url.username or url.password
                       or url.query or url.fragment or (url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'}))
            _ = url.port
        except ValueError:
            invalid = True
        if invalid:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Use an HTTPS endpoint or loopback HTTP URL without credentials, query or fragment.', 'configuration')
        if token_parameter not in {'max_tokens', 'max_completion_tokens'}:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Unsupported output token parameter.', 'configuration')
        self.base_url = base_url.rstrip('/')
        # A caller cannot turn a configured declaration into probe evidence.
        self.profile = profile.model_copy(update={'verified': (), 'checked_at_unix_ms': None})
        self.key_env = key_env
        self.token_parameter = token_parameter
        self.transport = transport

    async def capabilities(self, model: ModelRef) -> CapabilityProfile:
        if model != self.profile.model:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Model does not match configured profile.', 'configuration')
        return self.profile

    def _prepare(self, request: ModelRequest, streaming: bool) -> dict:
        if request.model != self.profile.model:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Model does not match configured profile.', request.request_id)
        if request.deadline_unix_ms <= now_ms():
            raise ProviderFailure(ErrorCode.TIMEOUT, 'Model deadline expired before dispatch.', request.request_id)
        needs_tools = bool(request.tools) or any(m.tool_calls or m.role == 'tool' for m in request.messages)
        if ((needs_tools and not self.profile.native_tools) or (streaming and not self.profile.streaming)
                or (request.output_schema_json and not self.profile.structured_output)):
            raise ProviderFailure(ErrorCode.UNSUPPORTED_CAPABILITY, 'Configured model profile does not support this request.', request.request_id)
        if request.max_output_tokens > self.profile.max_output_tokens:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Output limit exceeds configured model ceiling.', request.request_id)
        try:
            validate_request_schemas(request)
        except (ValueError, RecursionError):
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Invalid or unsupported inline JSON Schema.', request.request_id) from None
        messages = []
        for message in request.messages:
            wire = {'role': message.role, 'content': message.content}
            if message.tool_calls:
                wire['tool_calls'] = [self._wire_call(call) for call in message.tool_calls]
            if message.tool_call_id:
                wire['tool_call_id'] = message.tool_call_id
            messages.append(wire)
        body = {'model': request.model.name, 'messages': messages, 'stream': streaming,
                self.token_parameter: request.max_output_tokens}
        if request.generation.temperature is not None:
            body['temperature'] = request.generation.temperature
        if request.tools:
            body['tools'] = [{'type': 'function', 'function': {'name': tool.name, 'description': tool.description,
                             'parameters': strict_object(tool.parameters_json)}} for tool in request.tools]
            body['tool_choice'] = request.tool_choice
        if request.output_schema_json:
            body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'response', 'strict': True, 'schema': strict_object(request.output_schema_json)}}
        if streaming and self.profile.usage_reporting:
            body['stream_options'] = {'include_usage': True}
        if len(json.dumps(body, ensure_ascii=False).encode('utf-8')) > MAX_RESPONSE_BYTES:
            raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Model request exceeds the one-megabyte transport limit.', request.request_id)
        return body

    @staticmethod
    def _wire_call(call: ToolCall) -> dict:
        return {'id': call.call_id, 'type': 'function', 'function': {'name': call.name, 'arguments': call.arguments_json}}

    def _headers(self) -> dict:
        key = os.environ.get(self.key_env)
        return {'Authorization': 'Bearer ' + key} if key else {}

    @staticmethod
    def _remaining(request: ModelRequest) -> float:
        seconds = (request.deadline_unix_ms - now_ms()) / 1000
        if seconds <= 0:
            raise ProviderFailure(ErrorCode.TIMEOUT, 'Model deadline expired; usage may be unknown.', request.request_id)
        return seconds

    @staticmethod
    def _check_status(response: httpx.Response, request: ModelRequest) -> None:
        status = response.status_code
        if status == 200:
            return
        if status in {401, 403}:
            code, message = ErrorCode.NOT_AUTHORIZED, 'Provider rejected authentication or access.'
        elif status == 429 or status >= 500:
            code, message = ErrorCode.TRANSIENT_PROVIDER, 'Provider is temporarily unavailable; usage may be unknown.'
        else:
            code, message = ErrorCode.INVALID_INPUT, 'Provider rejected the request or endpoint configuration.'
        raise ProviderFailure(code, message, request.request_id, code == ErrorCode.TRANSIENT_PROVIDER)

    def _normalize(self, request: ModelRequest, data: dict) -> ModelResponse:
        choices = data['choices']
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError('expected one choice')
        choice = choices[0]
        if choice.get('index', 0) != 0:
            raise ValueError('unexpected choice index')
        message = choice['message']
        raw_finish = choice['finish_reason']
        finish = {'stop': 'stop', 'tool_calls': 'tools', 'length': 'length', 'content_filter': 'refusal'}.get(raw_finish)
        if finish is None or message.get('function_call'):
            raise ValueError('unsupported finish or legacy call')
        if message.get('refusal'):
            finish = 'refusal'
        content = message.get('content')
        if content is None:
            content = ''
        if not isinstance(content, str):
            raise ValueError('unsupported content')
        calls = []
        if finish == 'tools':
            raw_calls = message.get('tool_calls')
            if not isinstance(raw_calls, list) or not raw_calls:
                raise ValueError('missing calls')
            for index, call in enumerate(raw_calls):
                if call.get('type', 'function') != 'function':
                    raise ValueError('unsupported call type')
                function = call['function']
                call_id = call.get('id')
                if call_id is None:
                    call_id = 'h4_' + sha256(f'{request.request_id}:{index}'.encode()).hexdigest()[:32]
                calls.append(ToolCall(call_id=call_id, name=function['name'], arguments_json=function['arguments']))
        elif finish == 'stop':
            if message.get('tool_calls') or not content.strip():
                raise ValueError('inconsistent stop')
        # Truncated/refused calls are deliberately discarded, never exposed for dispatch.
        raw_usage = data.get('usage')
        if raw_usage is None:
            raw_usage = {}
        if not isinstance(raw_usage, dict):
            raise ValueError('invalid usage')
        response = ModelResponse(request_id=request.request_id, attempt_id=request.attempt_id, text=content,
                                 tool_calls=tuple(calls), finish=finish,
                                 usage=UsageSummary(input_tokens=raw_usage.get('prompt_tokens'), output_tokens=raw_usage.get('completion_tokens')),
                                 provider_request_id=data.get('id'), model_revision=data.get('model'))
        return validate_response(request, response)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        body = self._prepare(request, False)
        try:
            async with asyncio.timeout(self._remaining(request)):
                async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False) as client:
                    async with client.stream('POST', self.base_url + '/chat/completions', json=body,
                                             headers=self._headers(), timeout=self._remaining(request)) as response:
                        self._check_status(response, request)
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > MAX_RESPONSE_BYTES:
                                raise ValueError('response size exceeded')
            return self._normalize(request, strict_object(chunks.decode('utf-8')))
        except ProviderFailure:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderFailure(ErrorCode.TIMEOUT, 'Provider timed out; usage may be unknown.', request.request_id) from None
        except httpx.HTTPError:
            raise ProviderFailure(ErrorCode.TRANSIENT_PROVIDER, 'Provider connection failed; usage may be unknown.', request.request_id, True) from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Provider returned invalid or incomplete output.', request.request_id) from None

    async def _events(self, request: ModelRequest, body: dict):
        # Timeout only wraps transport awaits, never user code between yielded deltas.
        async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False) as client:
            outgoing = client.build_request('POST', self.base_url + '/chat/completions', json=body, headers=self._headers())
            async with asyncio.timeout(self._remaining(request)):
                response = await client.send(outgoing, stream=True)
            try:
                self._check_status(response, request)
                decoder = codecs.getincrementaldecoder('utf-8')('strict')
                buffer = ''
                data_lines = []
                total = 0
                iterator = response.aiter_bytes().__aiter__()
                while True:
                    async with asyncio.timeout(self._remaining(request)):
                        try:
                            chunk = await anext(iterator)
                        except StopAsyncIteration:
                            break
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise ValueError('stream size exceeded')
                    buffer += decoder.decode(chunk)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.removesuffix('\r')
                        if not line:
                            if data_lines:
                                yield '\n'.join(data_lines)
                                data_lines = []
                        elif line.startswith('data:'):
                            data_lines.append(line[5:].removeprefix(' '))
                        elif line.startswith(':') or line.startswith(('event:', 'id:', 'retry:')):
                            continue
                        else:
                            raise ValueError('invalid SSE field')
                decoder.decode(b'', final=True)
                if buffer or data_lines:
                    raise ValueError('unterminated SSE event')
            finally:
                await response.aclose()

    async def stream(self, request: ModelRequest):
        body = self._prepare(request, True)
        seq = 0
        text = ''
        calls = {}
        finish = None
        refusal = ''
        usage = None
        identity = None
        revision = None
        done = False
        events = self._events(request, body)
        try:
            async for payload in events:
                if payload == '[DONE]':
                    if finish is None:
                        raise ValueError('missing finish reason')
                    done = True
                    break
                data = strict_object(payload)
                if data.get('id') is not None:
                    if identity is not None and identity != data['id']:
                        raise ValueError('stream identity changed')
                    identity = data['id']
                if data.get('model') is not None:
                    if revision is not None and revision != data['model']:
                        raise ValueError('model changed midstream')
                    revision = data['model']
                if data.get('usage') is not None:
                    if usage is not None:
                        raise ValueError('duplicate usage')
                    usage = data['usage']
                choices = data['choices']
                if choices == []:
                    if finish is None or data.get('usage') is None:
                        raise ValueError('unexpected empty choices')
                    continue
                if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('index') != 0 or finish is not None:
                    raise ValueError('invalid stream choices or data after finish')
                choice = choices[0]
                delta = choice['delta']
                if delta.get('role') not in {None, 'assistant'} or delta.get('function_call'):
                    raise ValueError('unsupported stream role or legacy call')
                fragment = delta.get('content')
                if fragment is not None:
                    if not isinstance(fragment, str):
                        raise ValueError('invalid text fragment')
                    text += fragment
                    if fragment:
                        seq += 1
                        yield ModelDelta(request_id=request.request_id, attempt_id=request.attempt_id, seq=seq, kind='text', text=fragment)
                if delta.get('refusal') is not None:
                    if not isinstance(delta['refusal'], str):
                        raise ValueError('invalid refusal')
                    refusal += delta['refusal']
                raw_calls = delta.get('tool_calls', [])
                if not isinstance(raw_calls, list):
                    raise ValueError('invalid calls')
                for call in raw_calls:
                    index = call['index']
                    if type(index) is not int or not 0 <= index < 128:
                        raise ValueError('invalid call index')
                    target = calls.setdefault(index, {'type': 'function', 'function': {'name': '', 'arguments': ''}})
                    if call.get('type', 'function') != 'function':
                        raise ValueError('invalid call type')
                    if 'id' in call:
                        if 'id' in target and target['id'] != call['id']:
                            raise ValueError('changed call ID')
                        target['id'] = call['id']
                    function = call.get('function', {})
                    for key in ('name', 'arguments'):
                        if key in function:
                            if not isinstance(function[key], str):
                                raise ValueError('invalid function fragment')
                            target['function'][key] += function[key]
                finish = choice.get('finish_reason')
            if not done or sorted(calls) != list(range(len(calls))):
                raise ValueError('incomplete stream')
            data = {'id': identity, 'model': revision, 'usage': usage, 'choices': [{
                'finish_reason': finish, 'message': {'content': text, 'refusal': refusal,
                'tool_calls': [calls[index] for index in sorted(calls)]}}]}
            normalized = self._normalize(request, data)
        except ProviderFailure:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderFailure(ErrorCode.TIMEOUT, 'Provider stream timed out; usage may be unknown.', request.request_id) from None
        except httpx.HTTPError:
            raise ProviderFailure(ErrorCode.TRANSIENT_PROVIDER, 'Provider stream disconnected; usage may be unknown.', request.request_id, True) from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Provider returned invalid or incomplete stream output.', request.request_id) from None
        finally:
            await events.aclose()
        # Only this event can contain a validated, complete batch of calls.
        yield ModelDelta(request_id=request.request_id, attempt_id=request.attempt_id, seq=seq + 1, kind='final', response=normalized)
