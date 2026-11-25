"""Explicit, bounded capability probes. Calling probe() authorizes model requests."""
import time
from uuid import uuid4

from .contracts import ModelRef, UsageSummary
from .model_contracts import Message, ModelRequest, ProbeReport, ProbeResult, ToolSchema
from .model_ports import ModelProvider
from .provider_errors import ProviderFailure


async def probe(provider: ModelProvider, model: ModelRef, *, timeout: float = 60) -> ProbeReport:
    if not 0 < timeout <= 300:
        raise ValueError('probe timeout must be between 0 and 300 seconds')
    profile = await provider.capabilities(model)
    deadline = time.time_ns() // 1_000_000 + int(timeout * 1000)
    results = []
    usages = []
    count = 0

    def request(messages, **kwargs):
        return ModelRequest(request_id=str(uuid4()), attempt_id=str(uuid4()), model=model,
                            messages=messages, deadline_unix_ms=deadline,
                            max_output_tokens=min(128, profile.max_output_tokens), **kwargs)

    async def generate(req):
        nonlocal count
        count += 1
        try:
            response = await provider.generate(req)
        except ProviderFailure:
            usages.append(UsageSummary())
            raise
        usages.append(response.usage)
        return response

    text_messages = (Message(role='system', content='This is a capability probe. Reply exactly probe-ok.'),
                     Message(role='user', content='Reply exactly probe-ok.'))
    try:
        response = await generate(request(text_messages))
        results.append(ProbeResult(capability='text', passed=response.finish == 'stop' and response.text.strip() == 'probe-ok'))
    except ProviderFailure as exc:
        results.append(ProbeResult(capability='text', passed=False, error_code=exc.error.code.value))
    if profile.native_tools:
        tool = ToolSchema(name='echo_probe', description='Return the supplied value.', parameters_json='{"type":"object","properties":{"value":{"type":"string","const":"probe-ok"}},"required":["value"],"additionalProperties":false}')
        try:
            req = request((Message(role='user', content='Call echo_probe with value probe-ok.'),), tools=(tool,), tool_choice='required')
            response = await generate(req)
            passed = response.finish == 'tools' and len(response.tool_calls) == 1
            if passed:
                messages = req.messages + (Message(role='assistant', tool_calls=response.tool_calls),
                                           Message(role='tool', tool_call_id=response.tool_calls[0].call_id, content='probe-ok'),
                                           Message(role='user', content='Reply exactly with the tool result.'))
                final = await generate(request(messages, tools=(tool,)))
                passed = final.finish == 'stop' and final.text.strip() == 'probe-ok'
            results.append(ProbeResult(capability='native_tools', passed=passed))
        except ProviderFailure as exc:
            results.append(ProbeResult(capability='native_tools', passed=False, error_code=exc.error.code.value))
    if profile.structured_output:
        try:
            response = await generate(request((Message(role='user', content='Return {"ok":true}.'),), output_schema_json='{"type":"object","properties":{"ok":{"type":"boolean","const":true}},"required":["ok"],"additionalProperties":false}'))
            results.append(ProbeResult(capability='structured_output', passed=response.finish == 'stop'))
        except ProviderFailure as exc:
            results.append(ProbeResult(capability='structured_output', passed=False, error_code=exc.error.code.value))
    if profile.streaming:
        count += 1
        try:
            final = None
            seq = 0
            async for delta in provider.stream(request(text_messages)):
                if delta.seq != seq + 1 or final is not None:
                    raise ValueError('invalid delta sequence')
                seq = delta.seq
                if delta.kind == 'final':
                    final = delta.response
            usages.append(final.usage if final else UsageSummary())
            results.append(ProbeResult(capability='streaming', passed=final is not None and final.finish == 'stop' and final.text.strip() == 'probe-ok'))
        except ProviderFailure as exc:
            usages.append(UsageSummary())
            results.append(ProbeResult(capability='streaming', passed=False, error_code=exc.error.code.value))
    known = bool(usages) and all(u.input_tokens is not None and u.output_tokens is not None for u in usages)
    results.append(ProbeResult(capability='usage_reporting', passed=known))
    usage = UsageSummary(input_tokens=sum(u.input_tokens for u in usages) if known else None,
                         output_tokens=sum(u.output_tokens for u in usages) if known else None)
    verified = tuple(result.capability for result in results if result.passed)
    return ProbeReport(profile=profile.model_copy(update={'verified': verified, 'checked_at_unix_ms': time.time_ns() // 1_000_000}),
                       checks=tuple(results), usage=usage, requests_made=count)
