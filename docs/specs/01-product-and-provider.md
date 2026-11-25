# SPEC-01 — Application, CLI, provider gateway and output

Master RFC §§1–3, 6. P0 owner: application/provider. Depends SPEC-00. Reuse LiteLLM as optional adapter; direct OpenAI-compatible first, fake provider for tests. Never require two models or embeddings.

## User journey

`h4 init` writes nonsecret config, prompts for provider/model/base URL and credential reference; credential comes from environment or OS keyring. `doctor --offline` validates config; `doctor --probe` asks consent before charged test and returns verified capabilities, declared capabilities and unavailable features. `chat` creates/resumes session; `run` submits one task; `inspect` returns persisted result; `feedback` captures correction or rating linked to task/output digest. `serve`, webhook and reconnectable HTTP are M2. P0 CLI may run one coordinator in foreground; it must not pretend a task continues after process exit. Default agent created once. No API key printed or stored in YAML; endpoint is an operator-selected egress destination. `chat` accepts explicit mounted workspace, read-only input, private output directory. No browser or shell by default.

## Interface

```python
class ModelProvider(Protocol):
    async def capabilities(self, model: ModelRef) -> CapabilityProfile: ...
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelDelta]: ...
```

Request: stable logical ID, attempt ID supplied by coordinator, role-tagged content, tools with JSON schemas, output ceiling, deadline, generation settings, optional schema. Response: text blocks, validated calls with stable IDs, normalized finish reason (stop/tools/length/refusal/error), usage and provider request ID. Map each tool result to its call ID. Buffer streaming argument fragments; never dispatch before complete and validated. Missing usage must be unknown, not zero; estimate conservatively or retain reservation pending reconciliation. Retry 429/temporary transport failures with jitter and bounded deadline; request ambiguity records possible billing. No silent provider fallback. Credentials retrieved only inside adapter; safe errors stripped of raw request bodies. Test capability differences (native tools, schema, context window, streaming, usage, text-only); P0 text-only model supports chat without tools. Additional endpoints via documented adapter, not claim universal support.

## Application protocol

Submit external TaskSpec plus idempotency key; server derives effective grants, model and policy, never trusts user-supplied internal pointers. Return task ID, status, stream cursor. Reuse key with different canonical input returns conflict. Session turns serialized; background tasks independent. `TaskResult` contains final answer, artifact refs with digest/MIME/size, receipt summaries, verification state (`not_evaluated`, `verified`, `failed`, `inconclusive`), unresolved requests, cost estimate/known usage and pinned policy. Status is execution state, independent of quality. UI default shows answer/artifacts and actionable blocker; `--json` emits structured result. No fabricated citation or claim of external action.

Durable events carry workspace, task, event ID, sequence, type, timestamp, payload; display streaming tokens as provisional; reconnect replays committed events by cursor, not the agent. Expose `task.started`, `tool.completed`, `approval.required`, `task.waiting`, `task.completed`, `task.failed`, `learning.completed`; never expose hidden reasoning or secrets. Learning report shows scope, incumbent/candidate hash, diff, split counts, evidence quality, uncertainty, cost, gate result, activation state and rollback target. Reports distinguish fake demo from live evaluation.

## Acceptance

Fake provider tests credential-free; recorded compatible protocol tests tool roundtrip and malformed args; live probe opt-in. One configured endpoint for actor/learner; no embedding key. User can chat without tool support. CLI and SDK produce same TaskResult; request retry does not duplicate task; output path is accessible and authorized. No network traffic from offline doctor; no key in stdout/log/trace/config. Provider refusal and truncated outputs never dispatch a tool. User-visible failure explains remediation. Add provider conformance matrix before public release.
