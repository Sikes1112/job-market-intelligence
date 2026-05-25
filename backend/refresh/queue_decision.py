"""External queue posture selected for production refresh jobs.

No broker client is imported here. This module records the decision so later
batches can add an adapter without making this batch start workers, schedulers,
or live external network calls.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class QueueBackend(StrEnum):
    RQ_REDIS = "rq_redis"
    KAFKA = "kafka"
    DATABASE_QUEUE = "database_queue"


class RejectedQueueOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: QueueBackend
    reason: str = Field(min_length=1)


class QueueDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    selected_backend: QueueBackend
    broker: str = Field(min_length=1)
    worker_process_model: str = Field(min_length=1)
    contract_stage: str = Field(min_length=1)
    imports_runtime_client: bool
    production_queue_is_in_process: bool
    existing_internal_queue_role: str = Field(min_length=1)
    selection_reason: str = Field(min_length=1)
    rejected_options: tuple[RejectedQueueOption, ...]

    @property
    def external_process_compatible(self) -> bool:
        return (
            self.broker == "redis"
            and "external" in self.worker_process_model
            and not self.production_queue_is_in_process
            and not self.imports_runtime_client
        )

    @property
    def rejects_kafka(self) -> bool:
        return any(option.backend is QueueBackend.KAFKA for option in self.rejected_options)


SELECTED_QUEUE_DECISION = QueueDecision(
    selected_backend=QueueBackend.RQ_REDIS,
    broker="redis",
    worker_process_model="external worker processes",
    contract_stage="runtime_boundary_dependency_deferred",
    imports_runtime_client=False,
    production_queue_is_in_process=False,
    existing_internal_queue_role=(
        "The current database-backed QueueService remains a local admission, "
        "dedupe, and test harness. It is not the production external broker."
    ),
    selection_reason=(
        "No existing Python broker dependency is present. RQ plus Redis is the "
        "simplest fit for a FastAPI-style app with separate worker processes, "
        "basic retries, named queues, and low integration overhead."
    ),
    rejected_options=(
        RejectedQueueOption(
            backend=QueueBackend.KAFKA,
            reason=(
                "Kafka is rejected for this layer because refresh jobs need a "
                "simple task queue, not a streaming platform with topic, "
                "consumer-group, offset, and operations overhead."
            ),
        ),
        RejectedQueueOption(
            backend=QueueBackend.DATABASE_QUEUE,
            reason=(
                "A database queue is useful for existing admission semantics, "
                "but it is not the selected production worker broker."
            ),
        ),
    ),
)


__all__ = [
    "QueueBackend",
    "QueueDecision",
    "RejectedQueueOption",
    "SELECTED_QUEUE_DECISION",
]
