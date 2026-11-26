"""No-tool model backend. Expected labels and release authority stay in the caller."""
import json
import time
from uuid import uuid4

from ..adapters.openai_compatible import OpenAICompatibleProvider
from ..contracts import ModelRef, digest
from ..model_contracts import CapabilityProfile, Message, ModelRequest
from .store import LearningError


class LiveBackend:
    evidence_class = 'live'

    def __init__(self, profile, *, key_env='H4_MODEL_KEY', transport=None):
        self.profile, self.profile_hash = profile, digest(profile)
        self.model = ModelRef(provider='openai_compatible', name=profile.model)
        self.provider = OpenAICompatibleProvider(base_url=profile.base_url, key_env=key_env, transport=transport,
            profile=CapabilityProfile(model=self.model, max_output_tokens=profile.max_output_tokens))

    async def __call__(self, system, payload):
        request_id = str(uuid4())
        response = await self.provider.generate(ModelRequest(request_id=request_id, attempt_id=request_id,
            model=self.model, messages=(Message(role='system', content=system),
                                      Message(role='user', content=json.dumps(payload))),
            max_output_tokens=self.profile.max_output_tokens,
            deadline_unix_ms=time.time_ns() // 1_000_000 + int(self.profile.timeout * 1000)))
        if response.finish != 'stop' or response.model_revision != self.profile.revision:
            raise LearningError('Incomplete response or model revision mismatch.')
        return {'text': response.text, 'revision': response.model_revision, 'usage': response.usage}
