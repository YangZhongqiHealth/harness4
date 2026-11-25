# Security

This alpha performs read-only diff inspection and optional remote model review. It
is not a sandbox or approval authority. Prompts are not a security boundary; a model
can be influenced by malicious source content, so reports remain advisory.

Only send code to providers you are authorized to use. Credentials are read from an
environment variable inside the adapter; they are not report fields. Provider error
bodies are not surfaced. Successful model output is untrusted and may quote source
content; treat reports as having the same confidentiality as the reviewed code.

Use a trusted installed package and trusted policy when reviewing an untrusted PR.
The bundled Actions example installs the base branch and uses no secrets. Never
execute PR-controlled code in a job with write permissions or model credentials.

For vulnerabilities, use GitHub's private vulnerability reporting if enabled on the
published repository. If unavailable, open a minimal issue asking for a private
contact without exploit details, private code or secrets. Only the current alpha is
maintained; there is no production support commitment.
