"""Repository records for the local coordinator; these grant no authority."""
from typing import Literal

from pydantic import Field, model_validator

from .contracts import ActionReceipt, EffectIntent, Record, TaskSnapshot


class StoredStep(Record):
    seq: int = Field(ge=1)
    snapshot: TaskSnapshot


class OperationView(Record):
    workspace_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    intent: EffectIntent
    receipt: ActionReceipt | None = None
    status: Literal['pending', 'succeeded', 'failed', 'unknown_effect'] = 'pending'

    @model_validator(mode='after')
    def matching_receipt(self):
        if self.receipt is None:
            if self.status != 'pending':
                raise ValueError('terminal operation requires a receipt')
        elif (self.receipt.operation_id != self.intent.operation_id or self.receipt.status != self.status):
            raise ValueError('operation receipt mismatch')
        return self
