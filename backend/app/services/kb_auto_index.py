"""
KB auto-index helpers for job_targets (opt-in, capped).
Used by Apply API when jobs are imported/parsed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from backend.app.core.config import get_settings
from backend.app.core.database import db
from backend.app.storage import apply_storage, kb_storage
from backend.app.services.embeddings import embed_text

logger = logging.getLogger(__name__)

KB_CHUNK_SIZE = 1500
KB_CHUNK_OVERLAP = 100


def _chunk_text(text: str) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks. Returns list of {text, chunk_index}."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: List[Dict[str, Any]] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + KB_CHUNK_SIZE, len(text))
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                last = text.rfind(sep, start, end + 1)
                if last > start:
                    end = last + len(sep)
                    break
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({"text": chunk_text, "chunk_index": idx})
            idx += 1
        start = end - KB_CHUNK_OVERLAP if end < len(text) else len(text)
        if start < 0:
            start = end
    return chunks


async def maybe_auto_index_job_target(
    user_id: UUID,
    job_target_id: UUID,
) -> None:
    """
    Best-effort auto-index of job_target into KB when JOBSCOUT_KB_AUTO_INDEX_JOBS=true.
    Cap: 50 job_targets per user. Non-blocking; logs errors, never raises.
    """
    settings = get_settings()
    if not settings.kb_enabled or not settings.kb_auto_index_jobs:
        return
    if not settings.openai_api_key:
        return
    try:
        async with db.connection() as conn:
            count = await kb_storage.count_documents_for_user(
                conn, user_id, source_table="job_targets"
            )
            if count >= 50:
                return
            row = await apply_storage.get_job_target(
                conn, user_id=user_id, job_target_id=job_target_id
            )
            if not row:
                return
            parts = []
            if row.get("title"):
                parts.append(f"Title: {row['title']}")
            if row.get("company"):
                parts.append(f"Company: {row['company']}")
            if row.get("location"):
                parts.append(f"Location: {row['location']}")
            if row.get("description_text"):
                parts.append(f"Description:\n{row['description_text']}")
            if row.get("job_text"):
                parts.append(f"Raw:\n{row['job_text']}")
            text = "\n\n".join(parts).strip()
            if not text:
                return
            chunks_raw = _chunk_text(text)
            if not chunks_raw:
                return
        chunks_with_emb = []
        for c in chunks_raw:
            result = await embed_text(c["text"])
            if not result.ok or not result.embedding:
                continue
            chunks_with_emb.append({
                "text": c["text"],
                "chunk_index": c["chunk_index"],
                "embedding": result.embedding,
            })
        if not chunks_with_emb:
            return
        async with db.connection() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SET LOCAL app.current_user_id = $1",
                    str(user_id),
                )
                await kb_storage.insert_document_and_chunks(
                    conn,
                    user_id=user_id,
                    source_type="job_description",
                    source_table="job_targets",
                    source_id=str(job_target_id),
                    title=row.get("title") or row.get("company") or "Job",
                    chunks=chunks_with_emb,
                )
        logger.info("Auto-indexed job_target %s to KB", job_target_id)
    except Exception as e:
        logger.warning("KB auto-index of job_target failed: %s", e)
