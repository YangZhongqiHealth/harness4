"""Model port; importing this module performs no I/O."""
from collections.abc import AsyncIterator
from typing import Protocol

from .contracts import ModelRef
from .model_contracts import CapabilityProfile, ModelDelta, ModelRequest, ModelResponse


class ModelProvider(Protocol):
    async def capabilities(self, model: ModelRef) -> CapabilityProfile: ...
    async def generate(self, request: ModelRequest) -> ModelResponse: ...
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelDelta]: ...
