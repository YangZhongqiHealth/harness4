"""Run with python examples/provider_tools.py after installing the package. No network."""
import asyncio
import time

from harness4.adapters.fake import FakeProvider
from harness4.contracts import ModelRef
from harness4.model_contracts import CapabilityProfile, Message, ModelRequest, ModelResponse, ToolCall, ToolSchema


async def main():
    model = ModelRef(provider='fake', name='scripted')
    schema = ToolSchema(name='echo', description='Echo text in this offline demonstration.',
                        parameters_json='{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":false}')
    provider = FakeProvider((
        ModelResponse(request_id='template', attempt_id='template', finish='tools',
                      tool_calls=(ToolCall(call_id='echo-1', name='echo', arguments_json='{"text":"hello"}'),)),
        ModelResponse(request_id='template', attempt_id='template', finish='stop', text='The echo result was hello.'),
    ), profile=CapabilityProfile(model=model, native_tools=True))
    req = ModelRequest(request_id='step-1', attempt_id='attempt-1', model=model,
                       messages=(Message(role='user', content='Echo hello.'),), tools=(schema,),
                       deadline_unix_ms=time.time_ns() // 1_000_000 + 10000)
    first = await provider.generate(req)
    print(first.model_dump_json(indent=2))
    # This demo supplies a known fixture result. A real broker must authorize calls
    # before execution; provider validation never grants permission to use tools.
    second = ModelRequest(request_id='step-2', attempt_id='attempt-2', model=model,
                          messages=req.messages + (Message(role='assistant', tool_calls=first.tool_calls),
                          Message(role='tool', tool_call_id='echo-1', content='hello')),
                          tools=(schema,), deadline_unix_ms=req.deadline_unix_ms)
    print((await provider.generate(second)).model_dump_json(indent=2))


if __name__ == '__main__':
    asyncio.run(main())
