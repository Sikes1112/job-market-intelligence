"""Queue / worker runtime exceptions."""

from __future__ import annotations


class QueueError(Exception):
    """Base for queue/worker runtime errors."""


class JobNotFoundInQueue(QueueError):
    """Raised when a job_id is referenced but does not exist."""


class HandlerNotRegistered(QueueError):
    """Raised when no handler is registered for a job's job_type."""


class InvalidQueueName(QueueError):
    """Raised when a queue name is not one of the four MVP queues."""


class RetryNotEligible(QueueError):
    """Raised when retry() is called on a job that cannot be retried."""
