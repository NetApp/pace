"""REST API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from orchestrio.engine import run_workflow
from orchestrio.models import WorkflowDefinition, WorkflowResult
from orchestrio.plugins.base import list_plugins

router = APIRouter()


# ── Health ─────────────────────────────────────────────────────────


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Plugins ────────────────────────────────────────────────────────


@router.get("/plugins")
async def get_plugins() -> dict[str, list[str]]:
    """List all registered step plugins."""
    import orchestrio.plugins  # noqa: F401

    return {"plugins": list_plugins()}


# ── Validate ───────────────────────────────────────────────────────


@router.post("/workflows/validate")
async def validate_workflow(body: WorkflowDefinition) -> dict[str, Any]:
    """Validate a workflow definition (parsed via Pydantic)."""
    return {"valid": True, "workflow": body.name, "steps": len(body.steps)}


# ── Execute ────────────────────────────────────────────────────────


@router.post("/workflows/execute", response_model=WorkflowResult)
async def execute_workflow(body: WorkflowDefinition) -> WorkflowResult:
    """Execute a workflow and return the full run result."""
    try:
        return await run_workflow(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
