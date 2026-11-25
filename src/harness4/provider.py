"""Backward-compatible text-only facade over the canonical model provider port."""
import time

import httpx

from .adapters.openai_compatible import OpenAICompatibleProvider
from .contracts import ErrorCode, ModelRef, UsageSummary
from .model_contracts import CapabilityProfile, Message, ModelRequest
from .provider_errors import ProviderFailure


async def complete(*, base_url: str, model: str, key_env: str, system: str, prompt: str,
                   request_id: str, max_output_tokens: int = 4096, timeout: float = 60,
                   transport: httpx.AsyncBaseTransport | None = None) -> tuple[str, UsageSummary]:
    if not model.strip() or not 1 <= max_output_tokens <= 32768 or not 0 < timeout <= 300:
        raise ProviderFailure(ErrorCode.INVALID_INPUT, 'Invalid model, output limit or timeout.', request_id)
    model_ref = ModelRef(provider='openai_compatible', name=model)
    provider = OpenAICompatibleProvider(base_url=base_url, key_env=key_env, transport=transport,
                                       profile=CapabilityProfile(model=model_ref, max_output_tokens=32768))
    request = ModelRequest(request_id=request_id, attempt_id=request_id, model=model_ref,
                           messages=(Message(role='system', content=system), Message(role='user', content=prompt)),
                           max_output_tokens=max_output_tokens, deadline_unix_ms=time.time_ns() // 1_000_000 + int(timeout * 1000))
    result = await provider.generate(request)
    if result.finish != 'stop':
        raise ProviderFailure(ErrorCode.INVALID_MODEL_OUTPUT, 'Provider returned invalid or incomplete output.', request_id)
    return result.text, result.usage
