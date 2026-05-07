"""Downstream trigger recommendation schema.

Source: ``JOB_CONTRACT_SPEC.md`` §19.

A :class:`DownstreamTriggerRecommendation` is a *suggestion* attached to a
job response — "consider running this follow-up job." Slice 4 only defines the
shape. **Nothing in this module enqueues anything**: the orchestrator (Slice
14) and the event router (Slice 15) decide whether to honor the recommendation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.orchestration.jobs.types import JobType, Priority


class DownstreamTriggerRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_type: JobType
    reason: str = Field(min_length=1)
    scope: dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.NORMAL
