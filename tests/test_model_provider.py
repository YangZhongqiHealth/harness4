"""Credential-free provider conformance and adversarial transport fixtures."""
import asyncio
import json
import time

import httpx
import pytest
from pydantic import ValidationError

from harness4.adapters.fake import FakeProvider
from harness4.adapters.openai_compatible import OpenAICompatibleProvider
from harness4.cli import main
from harness4.contracts import ModelRef, UsageSummary
from harness4.model_contracts import CapabilityProfile, Message, ModelRequest, ModelResponse, ToolCall, ToolSchema
from harness4.model_probe import probe
from harness4.provider_errors import ProviderFailure

MODEL = ModelRef(provider='openai_compatible', name='fixture-model')
TOOL = ToolSchema(name='lookup', description='Look up an item.', parameters_json='{"type":"object","properties":{"key":{"type":"string"}},"required":["key"],"additionalProperties":false}')


def request(**overrides):
    args = dict(request_id='logical-1', attempt_id='attempt-1', model=MODEL,
                messages=(Message(role='user', content='Look up item A.'),),
                deadline_unix_ms=time.time_ns() // 1_000_000 + 10000)
    args.update(overrides)
    return ModelRequest(**args)


def provider(handler, **profile_overrides):
    profile = CapabilityProfile(model=MODEL, **profile_overrides)
    return OpenAICompatibleProvider(base_url='https://provider.invalid/v1', profile=profile, transport=httpx.MockTransport(handler))


def wire_response(*, content='ok', calls=None, finish='stop', usage=None):
    message = {'role':'assistant','content':content}
    if calls is not None:
        message['tool_calls'] = calls
    return {'id':'response-1','model':'fixture-revision','choices':[{'index':0,'message':message,'finish_reason':finish}], 'usage':usage}


def wire_call(arguments='{"key":"A"}', name='lookup', call_id='call-1'):
    result = {'type':'function','function':{'name':name,'arguments':arguments}}
    if call_id is not None:
        result['id'] = call_id
    return result


def test_native_tool_call_result_roundtrip():
    bodies = []
    def handler(req):
        body = json.loads(req.content)
        bodies.append(body)
        if len(bodies) == 1:
            assert body['tools'][0]['function']['name'] == 'lookup'
            return httpx.Response(200, json=wire_response(content=None, calls=[wire_call()], finish='tool_calls', usage={'prompt_tokens':9,'completion_tokens':3}))
        assert body['messages'][-1] == {'role':'tool','content':'value A','tool_call_id':'call-1'}
        assert body['messages'][-2]['tool_calls'][0]['id'] == 'call-1'
        return httpx.Response(200, json=wire_response(content='Found A'))
    p = provider(handler, native_tools=True)
    first = request(tools=(TOOL,))
    result = asyncio.run(p.generate(first))
    assert result.finish == 'tools' and result.usage.input_tokens == 9
    second = request(request_id='logical-2', tools=(TOOL,), messages=first.messages + (
        Message(role='assistant', tool_calls=result.tool_calls), Message(role='tool', tool_call_id='call-1', content='value A')))
    assert asyncio.run(p.generate(second)).text == 'Found A'
    assert len(bodies) == 2


@pytest.mark.parametrize('arguments,name', [('not JSON','lookup'), ('[]','lookup'), ('{"key":2}','lookup'), ('{}','lookup'), ('{"key":"A","grant":"shell"}','lookup'), ('{"key":"A"}','unknown'), ('{"key":"A","key":"B"}','lookup'), ('{"key":NaN}','lookup'), ('{"key":1e999}','lookup')])
def test_bad_tool_args_never_escape(arguments, name):
    p = provider(lambda _: httpx.Response(200, json=wire_response(content=None, calls=[wire_call(arguments,name)], finish='tool_calls')), native_tools=True)
    with pytest.raises(ProviderFailure) as exc:
        asyncio.run(p.generate(request(tools=(TOOL,))))
    assert exc.value.error.code == 'INVALID_MODEL_OUTPUT'
    assert arguments not in str(exc.value)


def test_missing_call_id_is_stable_across_attempts():
    p = provider(lambda _: httpx.Response(200, json=wire_response(content=None, calls=[wire_call(call_id=None)], finish='tool_calls')), native_tools=True)
    one = asyncio.run(p.generate(request(tools=(TOOL,))))
    two = asyncio.run(p.generate(request(tools=(TOOL,), attempt_id='attempt-2')))
    assert one.tool_calls[0].call_id == two.tool_calls[0].call_id
    assert one.attempt_id != two.attempt_id


@pytest.mark.parametrize('finish,normalized', [('length','length'),('content_filter','refusal')])
def test_refused_or_truncated_calls_are_not_dispatchable(finish, normalized):
    p = provider(lambda _: httpx.Response(200, json=wire_response(content=None, calls=[wire_call('{')], finish=finish)), native_tools=True)
    result = asyncio.run(p.generate(request(tools=(TOOL,))))
    assert result.finish == normalized and not result.tool_calls


def test_duplicate_call_ids_rejected():
    p = provider(lambda _: httpx.Response(200, json=wire_response(content=None, calls=[wire_call(),wire_call()], finish='tool_calls')), native_tools=True)
    with pytest.raises(ProviderFailure):
        asyncio.run(p.generate(request(tools=(TOOL,))))


@pytest.mark.parametrize('messages', [
    (Message(role='tool',tool_call_id='orphan',content='x'),),
    (Message(role='assistant',tool_calls=(ToolCall(call_id='c',name='lookup',arguments_json='{}'),)),),
    (Message(role='assistant',tool_calls=(ToolCall(call_id='c',name='lookup',arguments_json='{}'),)), Message(role='user',content='skip')),
])
def test_bad_tool_history_rejected(messages):
    with pytest.raises(ValidationError):
        request(messages=messages)


def test_text_only_capability_rejected_without_network():
    def forbidden(req):
        pytest.fail('must reject before dispatch')
    p = provider(forbidden)
    with pytest.raises(ProviderFailure) as exc:
        asyncio.run(p.generate(request(tools=(TOOL,))))
    assert exc.value.error.code == 'UNSUPPORTED_CAPABILITY'
    async def consume():
        return [d async for d in p.stream(request())]
    with pytest.raises(ProviderFailure):
        asyncio.run(consume())


@pytest.mark.parametrize('schema', [
    '{"type":"object","properties":{"x":{"$ref":"https://attacker.invalid/schema"}}}',
    '{"type":"object","properties":{"x":{"$ref":"#/definitions/x"}}}',
    '{"type":"object","required":"wrong-type"}',
    '{"type":"array"}',
])
def test_invalid_schema_rejected_without_network(schema):
    def forbidden(req):
        pytest.fail('must reject before dispatch')
    p = provider(forbidden, native_tools=True)
    with pytest.raises(ProviderFailure) as exc:
        asyncio.run(p.generate(request(tools=(ToolSchema(name='x',description='',parameters_json=schema),))))
    assert exc.value.error.code == 'INVALID_INPUT'


def test_json_output_schema_enforced():
    schema = '{"type":"object","properties":{"ok":{"const":true}},"required":["ok"],"additionalProperties":false}'
    def valid(req):
        assert json.loads(req.content)['response_format']['json_schema']['strict'] is True
        return httpx.Response(200,json=wire_response(content='{"ok":true}'))
    assert asyncio.run(provider(valid, structured_output=True).generate(request(output_schema_json=schema))).finish == 'stop'
    invalid = provider(lambda _: httpx.Response(200,json=wire_response(content='{"ok":false}')), structured_output=True)
    with pytest.raises(ProviderFailure):
        asyncio.run(invalid.generate(request(output_schema_json=schema)))


class ByteStream(httpx.AsyncByteStream):
    def __init__(self, chunks, fail=False):
        self.chunks = chunks
        self.fail = fail
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.fail:
            raise httpx.ReadError('private-transport-canary')

    async def aclose(self):
        self.closed = True


def event(delta=None, finish=None, usage=None, **overrides):
    data = {'id':'r1','model':'revision1','choices':[{'index':0,'delta':delta or {},'finish_reason':finish}]}
    if usage is not None:
        data['usage'] = usage
    data.update(overrides)
    return ('data: ' + json.dumps(data,ensure_ascii=False) + '\n\n').encode()


async def stream_all(p, req):
    return [delta async for delta in p.stream(req)]


def streaming_provider(chunks, *, fail=False, **flags):
    stream = ByteStream(chunks, fail=fail)
    p = provider(lambda _: httpx.Response(200, stream=stream), streaming=True, **flags)
    return p, stream


def test_stream_split_utf8_and_usage_final():
    raw = b': heartbeat\n\n' + event({'role':'assistant','content':'你好'}) + event({'content':'!'}, finish='stop')
    raw += event(usage={'prompt_tokens':4,'completion_tokens':3},choices=[]) + b'data: [DONE]\n\n'
    p, stream = streaming_provider([raw[i:i+1] for i in range(len(raw))], usage_reporting=True)
    deltas = asyncio.run(stream_all(p, request()))
    assert ''.join(d.text for d in deltas) == '你好!'
    assert [d.seq for d in deltas] == [1,2,3]
    assert all(d.response is None for d in deltas[:-1])
    assert deltas[-1].response.usage.output_tokens == 3
    assert stream.closed


def test_stream_buffers_tool_calls_until_done():
    chunks = [event({'tool_calls':[{'index':0,'id':'c1','type':'function','function':{'name':'look','arguments':'{"key":'}}]}),
              event({'tool_calls':[{'index':0,'function':{'name':'up','arguments':'"A"}'}}]},finish='tool_calls'), b'data: [DONE]\n\n']
    p, stream = streaming_provider(chunks,native_tools=True)
    deltas = asyncio.run(stream_all(p,request(tools=(TOOL,))))
    assert len(deltas) == 1 and deltas[0].kind == 'final'
    assert deltas[0].response.tool_calls[0].arguments_json == '{"key":"A"}'
    assert stream.closed


@pytest.mark.parametrize('chunks', [
    [event({'content':'hi'})],
    [event({'content':'hi'},finish='stop')],
    [b'data: [DONE]\n\n'],
    [b'data: {invalid}\n\n'],
    [event({'content':'hi'},finish='stop'),event({'content':'extra'}),b'data: [DONE]\n\n'],
    [event({'content':'hi'}),event({},finish='stop',id='changed'),b'data: [DONE]\n\n'],
    [event({'tool_calls':[{'index':1,'function':{'name':'lookup','arguments':'{}'}}]},finish='tool_calls'),b'data: [DONE]\n\n'],
    [event({'tool_calls':[{'index':0,'function':{'name':'lookup','arguments':'{'}}]},finish='tool_calls'),b'data: [DONE]\n\n'],
    [event({'tool_calls':[{'index':0,'id':'first','function':{'name':'lookup','arguments':'{}'}}]}),event({'tool_calls':[{'index':0,'id':'changed'}]},finish='tool_calls'),b'data: [DONE]\n\n'],
    [event({'content':'hi'},finish='stop') + b'data: [DONE]'],
])
def test_malformed_stream_has_no_final_event(chunks):
    p, stream = streaming_provider(chunks,native_tools=True)
    observed = []
    async def consume():
        async for delta in p.stream(request(tools=(TOOL,))):
            observed.append(delta)
    with pytest.raises(ProviderFailure):
        asyncio.run(consume())
    assert not any(d.kind == 'final' for d in observed)
    assert stream.closed


def test_disconnect_is_safe_and_not_retried():
    p, stream = streaming_provider([event({'content':'partial'})],fail=True)
    with pytest.raises(ProviderFailure) as exc:
        asyncio.run(stream_all(p,request()))
    assert exc.value.error.code == 'TRANSIENT_PROVIDER'
    assert 'canary' not in str(exc.value)
    assert stream.closed


def test_stream_cancel_closes_transport():
    p, stream = streaming_provider([event({'content':'partial'}),event({},finish='stop'),b'data: [DONE]\n\n'])
    async def consume():
        iterator = p.stream(request())
        assert (await anext(iterator)).kind == 'text'
        await iterator.aclose()
    asyncio.run(consume())
    assert stream.closed


def test_deadline_expires_before_dispatch():
    def forbidden(req):
        pytest.fail('expired request must not dispatch')
    with pytest.raises(ProviderFailure) as exc:
        asyncio.run(provider(forbidden).generate(request(deadline_unix_ms=1)))
    assert exc.value.error.code == 'TIMEOUT'


def template(text='probe-ok', **overrides):
    args = dict(request_id='template',attempt_id='template',text=text,finish='stop',usage=UsageSummary(input_tokens=5,output_tokens=2))
    args.update(overrides)
    return ModelResponse(**args)


def test_fake_replays_and_exhaustion_is_explicit():
    p = FakeProvider((template('one'),template('two')),profile=CapabilityProfile(model=MODEL,streaming=True))
    assert asyncio.run(p.generate(request())).text == 'one'
    streamed = asyncio.run(stream_all(p,request(attempt_id='second')))
    assert streamed[-1].response.text == 'two' and streamed[-1].attempt_id == 'second'
    with pytest.raises(ProviderFailure,match='exhausted'):
        asyncio.run(p.generate(request()))
    assert len(p.requests) == 2


def test_full_probe_records_only_verified_capabilities():
    tool_call = ToolCall(call_id='c',name='echo_probe',arguments_json='{"value":"probe-ok"}')
    p = FakeProvider((template(),template('',finish='tools',tool_calls=(tool_call,)),template(),template('{"ok":true}'),template()),
                     profile=CapabilityProfile(model=MODEL,native_tools=True,streaming=True,structured_output=True,usage_reporting=True))
    report = asyncio.run(probe(p,MODEL))
    assert all(check.passed for check in report.checks)
    assert report.requests_made == 5 and report.usage.input_tokens == 25
    assert report.profile.checked_at_unix_ms
    assert set(report.profile.verified) == {'text','native_tools','structured_output','streaming','usage_reporting'}
    assert not asyncio.run(p.capabilities(MODEL)).verified


def test_unknown_usage_probe_is_explicit():
    p = FakeProvider((template(usage=UsageSummary()),),profile=CapabilityProfile(model=MODEL))
    result = asyncio.run(probe(p,MODEL))
    assert result.profile.verified == ('text',)
    assert result.usage.input_tokens is None and result.requests_made == 1


def test_offline_doctor_no_network(monkeypatch,capsys):
    def forbidden(*args,**kwargs):
        pytest.fail('offline doctor must not create a client')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    assert main(['doctor','--model','test','--base-url','https://example.invalid/v1','--native-tools']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['native_tools'] is True and result['verified'] == []


def test_declarations_cannot_fake_probe_evidence():
    profile = CapabilityProfile(model=MODEL,verified=('text',),checked_at_unix_ms=123)
    p = OpenAICompatibleProvider(base_url='https://example.invalid',profile=profile)
    assert not asyncio.run(p.capabilities(MODEL)).verified


def test_request_size_limit_before_transport():
    def forbidden(req):
        pytest.fail('oversized request must not dispatch')
    p = provider(forbidden)
    req = request(messages=(Message(role='user',content='x' * 600_000),Message(role='user',content='y' * 600_000)))
    with pytest.raises(ProviderFailure,match='transport limit'):
        asyncio.run(p.generate(req))


def test_tools_required_cannot_fall_back_to_text():
    p = provider(lambda _: httpx.Response(200,json=wire_response()),native_tools=True)
    with pytest.raises(ProviderFailure):
        asyncio.run(p.generate(request(tools=(TOOL,),tool_choice='required')))


def test_transient_errors_are_not_retried_in_new_port():
    calls=[]
    def busy(req):
        calls.append(req)
        return httpx.Response(429, text='private-provider-body')
    p=provider(busy)
    with pytest.raises(ProviderFailure) as exc:
        asyncio.run(p.generate(request()))
    assert exc.value.error.retryable and len(calls) == 1
    assert 'private-provider-body' not in str(exc.value)


def test_token_parameter_is_explicit():
    def handler(req):
        body=json.loads(req.content)
        assert 'max_tokens' not in body and body['max_completion_tokens']==4096
        return httpx.Response(200,json=wire_response())
    p=OpenAICompatibleProvider(base_url='https://provider.invalid',profile=CapabilityProfile(model=MODEL),token_parameter='max_completion_tokens',transport=httpx.MockTransport(handler))
    assert asyncio.run(p.generate(request())).text=='ok'


def test_fake_invalid_call_rejected():
    p=FakeProvider((template('',finish='tools',tool_calls=(ToolCall(call_id='c',name='lookup',arguments_json='{"key":false}'),)),),profile=CapabilityProfile(model=MODEL,native_tools=True))
    with pytest.raises(ProviderFailure):
        asyncio.run(p.generate(request(tools=(TOOL,))))


def test_failing_probe_does_not_claim_verified(monkeypatch,capsys):
    p=FakeProvider((template('not-probe-ok'),),profile=CapabilityProfile(model=MODEL))
    result=asyncio.run(probe(p,MODEL))
    assert 'text' not in result.profile.verified
    async def failed_probe(*args,**kwargs):
        return result
    monkeypatch.setattr('harness4.model_probe.probe',failed_probe)
    assert main(['doctor','--model',MODEL.name,'--base-url','https://provider.invalid','--probe'])==2
    assert json.loads(capsys.readouterr().out)['requests_made']==1


def test_stream_response_limit_and_multi_choice():
    for chunks in ([b':' + b'x' * 1_000_001], [event(choices=[{'index':0,'delta':{},'finish_reason':None},{'index':1,'delta':{},'finish_reason':None}])]):
        p, stream = streaming_provider(chunks)
        with pytest.raises(ProviderFailure):
            asyncio.run(stream_all(p,request()))
        assert stream.closed
