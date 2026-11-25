# SPEC-04 — Tool gateway, environments and security

Master RFC §9, §10. Depends SPEC-00/02. MCP compatibility at M2; P0 local tools only. Reuse protocol schemas, not permission assertions from remote servers.

## Contracts

```python
class Environment(Protocol):
    async def observe(self, resource, grant) -> Observation: ...
    async def execute(self, operation_id, action, grant) -> Receipt: ...
    async def reconcile(self, operation_id, intent) -> Reconciliation: ...
class EvalEnvironmentFactory(Protocol):
    async def clone(self, fixture_ref, seed, permissions) -> Environment: ...
```

Tool manifest declares name/version, input/output JSON schemas, effect class (read/local_write/external_write), required grant, resource selector, supported version check, idempotency and reconciliation capabilities. Registry installation is trusted operator action. Model sees subset permitted by effective grants; tool gateway independently enforces at dispatch. Unknown tool, malformed input, unauthorized destination or stale resource rejected before execution. Persist stable intent and budget reservation before effect. Receipt includes operation ID, actual effect status, resource version, external reference, artifact digests, sanitized result. Adapter maps unknown transport outcome to uncertain effect, never to known failure if write might have succeeded.

## Authorization and isolation

Effective capability = intersection of agent definition, user grant, environment, task, live revocation and sandbox. Grant binds workspace, action, resource, principal, expiry. Neither skill text nor user-provided external data may grant capability. All external inputs including tool descriptions treated as untrusted data. Verify actor identity and signed event ingress; authorization checked even when model proposes familiar action. Approval request binds canonical action hash, destination, resource version, task, expiry, actor and security epoch; use once, reject changes. Credentials provided by broker to adapter only, never model or evaluator. Tool worker cannot read model credential, arbitrary host filesystem or access unrestricted network. P0 avoid arbitrary execution; local tools use explicit read mounts and separate private artifacts directory. Use OS-enforced filesystem boundaries or trusted descriptor-relative traversal with no symlink following; lexical prefix checking alone insufficient. Treat races between check and use as threats. Artifact size limits and MIME validation. No secrets from workspace sent to model absent authorized egress. If isolation cannot be verified, disable that feature; never market Python module separation as sandbox.

## GitHub recipe M2/M3

Webhook signature check on raw body, dedup source/delivery ID, fetch trusted PR head/base, queue read-only review pinned to SHA. Findings structured (file, line, evidence, severity, verification). Human feedback linked to finding/revision; optional comment publication needs distinct grant and current head verification. Initial recipe read-only, no merge. CI fixture clone per evaluation with network disabled. For real writes later: provider atomic version precondition where supported; otherwise acknowledge weaker consistency and require operator-controlled external protections. Outbound action should be narrow, not raw arbitrary shell command.

## Acceptance

Negative tests: fake grant, stale/replayed approval, secret in tool response, injection asking for credentials, malicious symlink/path race, oversize file, unknown tool, cross-scope artifact, stale resource, ambiguous write, compromised evaluator/learner attempting live dispatch. Confirm deny happens before side effect. Test successful local artifact idempotency and reconciliation. Require explicit operator install and license/supply-chain review for plugins. Security test pass is necessary, not proof of absence of vulnerabilities.
