# Copyright 2026 NetApp, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Workflow data models — mirrors the workflow-spec JSON Schema."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Workflow Definition ────────────────────────────────────────────


class OnFailure(str, Enum):
    STOP = "stop"
    CONTINUE = "continue"


class RetryConfig(BaseModel):
    attempts: int = Field(default=1, ge=1)
    delay_seconds: float = Field(default=1.0, ge=0)


class StepDefinition(BaseModel):
    name: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    on_failure: OnFailure = OnFailure.STOP


class WorkflowDefinition(BaseModel):
    name: str
    version: str = "1"
    description: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    defaults: dict[str, dict[str, Any]] = Field(default_factory=dict)
    steps: list[StepDefinition]


# ── Execution Results ──────────────────────────────────────────────


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    name: str
    status: StepStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 0


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class WorkflowResult(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    workflow_name: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: list[StepResult] = Field(default_factory=list)
