"""
Workflow API — CRUD + execution management.

Endpoints:
  POST   /workflows              — Create workflow
  GET    /workflows              — List workflows
  GET    /workflows/{id}         — Get workflow detail
  PUT    /workflows/{id}         — Update workflow (graph, config)
  DELETE /workflows/{id}         — Delete workflow
  POST   /workflows/{id}/execute — Execute workflow
  GET    /workflows/{id}/executions — List executions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.workflow import Workflow, WorkflowExecution, WorkflowStatus, ExecutionStatus

router = APIRouter(prefix="/workflows")


# ── Schemas ───────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import Optional, Any


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    agent_id: Optional[str] = None
    graph_data: dict = Field(default_factory=lambda: {"nodes": [], "edges": []})
    trigger_config: Optional[dict] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    graph_data: Optional[dict] = None
    trigger_config: Optional[dict] = None


class WorkflowExecuteRequest(BaseModel):
    trigger_data: Optional[dict] = None
    session_id: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("")
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db_session)):
    """Create a new workflow."""
    workflow = Workflow(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        agent_id=uuid.UUID(data.agent_id) if data.agent_id else None,
        status=WorkflowStatus.DRAFT,
        graph_data=data.graph_data,
        trigger_config=data.trigger_config or {},
        version=1,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return {"id": str(workflow.id), "name": workflow.name, "status": workflow.status.value}


@router.get("")
async def list_workflows(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all workflows with optional filters."""
    query = select(Workflow)
    if agent_id:
        query = query.where(Workflow.agent_id == uuid.UUID(agent_id))
    if status:
        query = query.where(Workflow.status == WorkflowStatus(status))
    query = query.order_by(Workflow.updated_at.desc())
    result = await db.execute(query)
    workflows = result.scalars().all()
    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "status": w.status.value,
            "version": w.version,
            "total_executions": w.total_executions,
            "success_rate": w.success_rate,
            "node_count": len(w.graph_data.get("nodes", [])) if w.graph_data else 0,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in workflows
    ]


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get workflow detail including full graph."""
    result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "status": workflow.status.value,
        "graph_data": workflow.graph_data,
        "trigger_config": workflow.trigger_config,
        "version": workflow.version,
        "total_executions": workflow.total_executions,
        "success_rate": workflow.success_rate,
        "agent_id": str(workflow.agent_id) if workflow.agent_id else None,
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
    }


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, data: WorkflowUpdate, db: AsyncSession = Depends(get_db_session)):
    """Update workflow."""
    result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if data.name is not None:
        workflow.name = data.name
    if data.description is not None:
        workflow.description = data.description
    if data.status is not None:
        workflow.status = WorkflowStatus(data.status)
    if data.graph_data is not None:
        workflow.graph_data = data.graph_data
        workflow.version += 1
    if data.trigger_config is not None:
        workflow.trigger_config = data.trigger_config
    await db.commit()
    return {"id": str(workflow.id), "status": "updated", "version": workflow.version}


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete workflow."""
    result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)
    await db.commit()
    return {"deleted": True}


@router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, data: WorkflowExecuteRequest, db: AsyncSession = Depends(get_db_session)):
    """Start a workflow execution."""
    result = await db.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    execution = WorkflowExecution(
        id=uuid.uuid4(),
        workflow_id=workflow.id,
        session_id=data.session_id,
        status=ExecutionStatus.RUNNING,
        trigger_data=data.trigger_data or {},
        steps=[],
    )
    db.add(execution)
    workflow.total_executions += 1
    await db.commit()
    return {"execution_id": str(execution.id), "status": "running"}


@router.get("/{workflow_id}/executions")
async def list_executions(workflow_id: str, limit: int = 20, db: AsyncSession = Depends(get_db_session)):
    """List workflow executions."""
    query = (
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == uuid.UUID(workflow_id))
        .order_by(WorkflowExecution.started_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    execs = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "status": e.status.value,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "duration_ms": e.duration_ms,
            "steps_count": len(e.steps or []),
            "error": e.error,
        }
        for e in execs
    ]
