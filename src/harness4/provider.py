"""Bounded text-only Chat Completions adapter; no tools, retries or fallback."""
from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx

from .contracts import DomainError, ErrorCode, UsageSummary


class ProviderFailure(Exception):
    def __init__(self, code: ErrorCode, message: str, correlation_id: str, retryable: bool = False):
        self.error = DomainError(code=code, message=message, correlation_id=correlation_id, retryable=retryable)
        super().__init__(message)


async def complete(*, base_url: str, model: str, key_env: str, system: str, prompt: str,
                   request_id: str, max_output_tokens: int = 4096, timeout: float = 60,
                   transport: httpx.AsyncBaseTransport | None = None) -> tuple[str, UsageSummary]:
    url = urlsplit(base_url)
    if (url.scheme not in {'https', 'http'} or not url.hostname or url.username or url.password
            or url.query or url.fragment or (url.scheme == 'http' and url.hostname not in {'localhost', '127.0.0.1', '::1'})):
        raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Use an HTTPS endpoint or loopback HTTP URL without credentials, query or fragment.', request_id)
    if not model.strip() or not 1 <= max_output_tokens <= 32768 or not 0 < timeout <= 300:
        raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Invalid model, output limit or timeout.', request_id)
    key = os.environ.get(key_env)
    headers = {'Authorization': 'Bearer ' + key} if key else {}
    body = {'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
            'max_tokens': max_output_tokens, 'stream': False}
    try:
        # Absolute wall-clock bound, bounded response body, no redirects or env proxy discovery.
        async with asyncio.timeout(timeout):
            async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False) as client:
                async with client.stream('POST', base_url.rstrip('/') + '/chat/completions', json=body,
                                         headers=headers, timeout=timeout) as response:
                    if response.status_code != 200:
                        status = response.status_code
                        if status in {401, 403}:
                            code, message = ErrorCode.NOT_AUTHORIZED, 'Provider rejected authentication or access.'
                        elif status == 429 or status >= 500:
                            code, message = ErrorCode.TRANSIENT_PROVIDER, 'Provider is temporarily unavailable; usage may be unknown.'
                        else:
                            code, message = ErrorCode.INVALID_INPUT, 'Provider rejected the request or endpoint configuration.'
                        raise ProviderFailure(code, message, request_id, code == ErrorCode.TRANSIENT_PROVIDER)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > 1_000_000:
                            raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Provider response exceeded the size limit.', request_id)
        data = json.loads(chunks)
        choices = data['choices']
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError('expected one choice')
        choice = choices[0]
        message = choice['message']
        if choice['finish_reason'] != 'stop' or message.get('refusal') or message.get('tool_calls') or message.get('function_call'):
            raise ValueError('incomplete, refused or unsupported output')
        text = message['content']
        if not isinstance(text, str) or not text.strip():
            raise ValueError('missing text')
        usage = data.get('usage') or {}
        return text, UsageSummary(input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'))
    except ProviderFailure:
        raise
    except (TimeoutError, httpx.TimeoutException):
        raise ProviderFailure(ErrorCode.TIMEOUT, 'Provider timed out; usage may be unknown.', request_id) from None
    except httpx.HTTPError:
        raise ProviderFailure(ErrorCode.TRANSIENT_PROVIDER, 'Provider connection failed; usage may be unknown.', request_id, True) from None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Provider returned invalid or incomplete output.', request_id) from None
