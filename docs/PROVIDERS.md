# Provider interface and conformance

The versioned model port is `harness4.model_ports.ModelProvider`. It exposes async
`capabilities(model)` and `generate(request)` plus an async iterator `stream(request)`.
`h4 ship` uses this port through its backward-compatible text facade. The separate
`h4 doctor` command inspects or explicitly probes the selected endpoint.

## Offline configuration check

```sh
h4 doctor --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --offline --native-tools --streaming --usage-reporting
```

Flags are operator declarations. The output's `verified` list stays empty. Offline
inspection does not read the credential or create an HTTP client. Unknown context
window and usage remain unknown rather than guessed.

## Explicit paid probe

```sh
h4 doctor --model YOUR_MODEL --base-url https://YOUR_PROVIDER/v1 \
  --probe --native-tools --streaming --structured-output --usage-reporting
```

`--probe` authorizes up to five small requests (text, tool call, tool-result response,
structured output and streaming) with one shared deadline and at most 128 output
tokens per request. It uses the named credential environment variable (default
`H4_MODEL_KEY`). Only declared optional capabilities are probed. Probes return
individual checks, the tested model, time and known usage; failed checks are never
marked verified. Unknown usage is reported separately and is not treated as a text
failure. A passed probe demonstrates a canned exchange, not model accuracy or a
security guarantee. Probe results are not automatically persisted or activated.

For endpoints requiring `max_completion_tokens`, pass
`--token-parameter max_completion_tokens` to doctor or configure the adapter's
`token_parameter` explicitly. The ship CLI retains its original `max_tokens` mode.
No API name or endpoint fallback is inferred after an error.

## SDK behavior

See [the credential-free tool conversation example](../examples/provider_tools.py):

```sh
python examples/provider_tools.py
```

`FakeProvider` consumes a fixed script and validates the same schemas as the real
adapter. Exhaustion is an explicit error, never fabricated success. It supports
scripted domain failures and records requests for deterministic lifecycle tests.
It has no credentials, transport or live effects.

`OpenAICompatibleProvider` accepts a trusted `CapabilityProfile`, explicit API base
URL, credential variable name and optional HTTP transport. Records live in
`model_contracts.py`; no vendor SDK classes enter the core. Requests carry stable
logical IDs, attempt IDs, an absolute UTC deadline, role-tagged messages, output
ceilings and optional generation/schema settings. IDs are for local correlation;
the adapter does not promise provider-side request deduplication or exactly-once billing.

Tool schemas and arguments are immutable canonical JSON strings. Schemas use the
JSON Schema 2020-12 validator, require an object root, and must be inline: `$ref`,
`$dynamicRef` and `$recursiveRef` are rejected, so validation cannot fetch remote
resources. Messages match tool results to unique call IDs. Tool batches must use
known names and validate against the requested schemas before being returned.
Absent call IDs are derived deterministically from the logical request ID and index.
Schema validation establishes shape, not authorization to execute the proposed action.

Streaming text deltas are provisional. Tool arguments are buffered internally until
a valid finish and `[DONE]`; only the final delta carries validated calls. On a
malformed fragment, inconsistent ID, duplicate/missing choice, disconnect or missing
terminator, no final response is emitted. Cancellation closes the response stream.
Truncated/refused responses expose no executable tool calls. The text-only facade
rejects all finishes other than a complete text response.

Requests and response streams each have a one-megabyte transport ceiling. Deadlines
bound network waits; token ceilings are sent explicitly. Request context packing,
spending reservations and durable retries belong to the future compiler/kernel,
not this adapter. Usage omitted by a provider remains `None`; failures may still
have incurred cost. Error messages do not include provider bodies or credentials.
No adapter retries, redirects, implicit environment proxy, or alternate endpoints.

## Conformance status

| Capability | Fake | Compatible adapter | Validation |
|---|---|---|---|
| Text and known/unknown usage | Implemented | Implemented | Offline transport fixtures |
| Native tools and tool-result IDs | Implemented | Implemented | Valid, malformed, duplicate and missing-ID cases |
| Structured object output | Implemented | Implemented | Declared capability plus schema validation |
| Streaming text and buffered calls | Deterministic deltas | SSE | Split UTF-8/JSON, truncation, cancellation, disconnect |
| Capability probe | Scripted | Explicit network calls | Full five-request lifecycle tested with fake |
| Live endpoint families | Not applicable | Not yet qualified | No real provider calls performed |
| Images, audio, embeddings, signed continuation | Unsupported | Unsupported | No silent modality fallback |

Full provider reliability and review quality need separate real-endpoint conformance
and benchmark runs. Passing offline fixtures does not establish cross-provider parity.
