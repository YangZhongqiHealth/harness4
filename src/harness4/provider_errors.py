"""Safe domain exceptions shared across provider adapters."""
from .contracts import DomainError, ErrorCode


class ProviderFailure(Exception):
    def __init__(self, code: ErrorCode, message: str, correlation_id: str, retryable: bool = False):
        self.error = DomainError(code=code, message=message, correlation_id=correlation_id, retryable=retryable)
        super().__init__(message)
