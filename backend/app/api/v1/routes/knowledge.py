"""
Knowledge Base API — CRUD for knowledge bases, documents, RAG search.

Endpoints:
  POST   /knowledge              — Create knowledge base
  GET    /knowledge              — List knowledge bases
  GET    /knowledge/{id}         — Get KB detail
  PUT    /knowledge/{id}         — Update KB settings
  DELETE /knowledge/{id}         — Delete KB
  POST   /knowledge/{id}/documents — Upload document
  GET    /knowledge/{id}/documents — List documents
  DELETE /knowledge/{id}/documents/{doc_id} — Delete document
  POST   /knowledge/{id}/search   — RAG search
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.knowledge import KnowledgeBase, KnowledgeDocument, KnowledgeChunk

router = APIRouter(prefix="/knowledge")


# ── Schemas ───────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import Optional, List


class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    agent_id: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 512
    chunk_overlap: int = 50


class KBUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.7


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("")
async def create_knowledge_base(data: KBCreate, db: AsyncSession = Depends(get_db_session)):
    """Create a new knowledge base."""
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        agent_id=uuid.UUID(data.agent_id) if data.agent_id else None,
        embedding_model=data.embedding_model,
        chunk_size=data.chunk_size,
        chunk_overlap=data.chunk_overlap,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return {"id": str(kb.id), "name": kb.name, "embedding_model": kb.embedding_model}


@router.get("")
async def list_knowledge_bases(
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all knowledge bases."""
    query = select(KnowledgeBase)
    if agent_id:
        query = query.where(KnowledgeBase.agent_id == uuid.UUID(agent_id))
    query = query.order_by(KnowledgeBase.created_at.desc())
    result = await db.execute(query)
    kbs = result.scalars().all()
    return [
        {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description,
            "total_documents": kb.total_documents,
            "total_chunks": kb.total_chunks,
            "embedding_model": kb.embedding_model,
            "chunk_size": kb.chunk_size,
            "agent_id": str(kb.agent_id) if kb.agent_id else None,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
        }
        for kb in kbs
    ]


@router.get("/{kb_id}")
async def get_knowledge_base(kb_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get knowledge base detail."""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id)))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return {
        "id": str(kb.id),
        "name": kb.name,
        "description": kb.description,
        "total_documents": kb.total_documents,
        "total_chunks": kb.total_chunks,
        "embedding_model": kb.embedding_model,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "agent_id": str(kb.agent_id) if kb.agent_id else None,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }


@router.put("/{kb_id}")
async def update_knowledge_base(kb_id: str, data: KBUpdate, db: AsyncSession = Depends(get_db_session)):
    """Update KB settings."""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id)))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    if data.name is not None:
        kb.name = data.name
    if data.description is not None:
        kb.description = data.description
    if data.embedding_model is not None:
        kb.embedding_model = data.embedding_model
    if data.chunk_size is not None:
        kb.chunk_size = data.chunk_size
    if data.chunk_overlap is not None:
        kb.chunk_overlap = data.chunk_overlap
    await db.commit()
    return {"id": str(kb.id), "status": "updated"}


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete KB and all documents/chunks."""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id)))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    await db.delete(kb)
    await db.commit()
    return {"deleted": True}


@router.post("/{kb_id}/documents")
async def upload_document(kb_id: str, db: AsyncSession = Depends(get_db_session)):
    """Upload a document to the knowledge base (stub — file processing is async)."""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id)))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    doc = KnowledgeDocument(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        filename="uploaded_document.pdf",
        file_type="pdf",
        file_size_bytes=0,
        status="processing",
    )
    db.add(doc)
    kb.total_documents += 1
    await db.commit()
    return {"document_id": str(doc.id), "status": "processing"}


@router.get("/{kb_id}/documents")
async def list_documents(kb_id: str, db: AsyncSession = Depends(get_db_session)):
    """List documents in a knowledge base."""
    query = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.knowledge_base_id == uuid.UUID(kb_id))
        .order_by(KnowledgeDocument.created_at.desc())
    )
    result = await db.execute(query)
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size_bytes": d.file_size_bytes,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete a document and its chunks."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == uuid.UUID(doc_id),
            KnowledgeDocument.knowledge_base_id == uuid.UUID(kb_id),
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    # Update KB counts
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id)))
    kb = kb_result.scalar_one_or_none()
    if kb:
        kb.total_documents = max(0, kb.total_documents - 1)
        kb.total_chunks = max(0, kb.total_chunks - (doc.chunk_count or 0))
    await db.commit()
    return {"deleted": True}


@router.post("/{kb_id}/search")
async def search_knowledge_base(kb_id: str, data: SearchRequest, db: AsyncSession = Depends(get_db_session)):
    """Semantic search against knowledge base chunks (stub — returns mock results)."""
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == uuid.UUID(kb_id)))
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # In production, this would embed the query and do vector similarity search
    # For now, return text-match approximation
    query = (
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id.in_(
            select(KnowledgeDocument.id).where(KnowledgeDocument.knowledge_base_id == kb.id)
        ))
        .limit(data.top_k)
    )
    result = await db.execute(query)
    chunks = result.scalars().all()

    return {
        "query": data.query,
        "results": [
            {
                "chunk_id": str(c.id),
                "content": c.content,
                "score": 0.95 - (i * 0.05),  # Mock scores
                "chunk_index": c.chunk_index,
            }
            for i, c in enumerate(chunks)
        ],
        "total_results": len(chunks),
    }
