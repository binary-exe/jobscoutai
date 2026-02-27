"""
KB (Second Brain) storage: document and chunk persistence with strict user_id filtering.

All operations require an explicit user_id; RLS policies use app.current_user_id
when set per transaction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID
import asyncpg

from backend.app.services.embeddings import to_pgvector_literal


async def insert_document_and_chunks(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    source_type: str,
    source_table: Optional[str] = None,
    source_id: Optional[str] = None,
    title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    chunks: List[Dict[str, Any]],
) -> UUID:
    """
    Insert one kb_document and its kb_chunks. Each chunk must have:
    - text: str
    - chunk_index: int
    - embedding: List[float]
    - page: Optional[int] = None
    - token_count: Optional[int] = None

    Returns the new document id.
    """
    import json
    meta = json.dumps(metadata or {})

    row = await conn.fetchrow(
        """
        INSERT INTO kb_documents (user_id, source_type, source_table, source_id, title, metadata)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        RETURNING id
        """,
        user_id,
        source_type,
        source_table,
        source_id,
        title,
        meta,
    )
    doc_id = row["id"]

    for c in chunks:
        emb = c.get("embedding")
        if not emb:
            continue
        lit = to_pgvector_literal(emb)
        await conn.execute(
            """
            INSERT INTO kb_chunks (user_id, document_id, chunk_index, page, token_count, text, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
            """,
            user_id,
            doc_id,
            c["chunk_index"],
            c.get("page"),
            c.get("token_count"),
            (c.get("text") or "").strip(),
            lit,
        )

    return doc_id


async def fetch_similar_chunks(
    conn: asyncpg.Connection,
    *,
    user_id: UUID,
    embedding: List[float],
    limit: int = 10,
    source_type: Optional[str] = None,
    source_table: Optional[str] = None,
    source_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Run cosine similarity search on kb_chunks for the given user.
    Returns list of dicts with: chunk_id, document_id, source_type, source_id, page, score, snippet (text).
    """
    lit = to_pgvector_literal(embedding)
    # Cosine distance: 1 - (a <=> b); we want highest similarity first
    where_parts = ["c.user_id = $1"]
    params: List[Any] = [user_id, lit]
    idx = 3
    if source_type is not None:
        where_parts.append(f"d.source_type = ${idx}")
        params.append(source_type)
        idx += 1
    if source_table is not None:
        where_parts.append(f"d.source_table = ${idx}")
        params.append(source_table)
        idx += 1
    if source_id is not None:
        where_parts.append(f"d.source_id = ${idx}")
        params.append(source_id)
        idx += 1
    params.append(limit)

    where_sql = " AND ".join(where_parts)
    limit_param = f"${idx}"

    rows = await conn.fetch(
        f"""
        SELECT
            c.id AS chunk_id,
            c.document_id,
            d.source_type,
            d.source_id,
            c.page,
            1 - (c.embedding <=> $2::vector) AS score,
            LEFT(c.text, 500) AS snippet
        FROM kb_chunks c
        JOIN kb_documents d ON d.id = c.document_id AND d.user_id = c.user_id
        WHERE {where_sql}
        ORDER BY c.embedding <=> $2::vector
        LIMIT {limit_param}
        """,
        *params,
    )

    return [
        {
            "chunk_id": str(r["chunk_id"]),
            "document_id": str(r["document_id"]),
            "source_type": r["source_type"] or "",
            "source_id": r["source_id"] or "",
            "page": r["page"],
            "score": round(float(r["score"]), 4),
            "snippet": (r["snippet"] or "").strip(),
        }
        for r in rows
    ]


async def count_documents_for_user(
    conn: asyncpg.Connection,
    user_id: UUID,
    *,
    source_table: Optional[str] = None,
) -> int:
    """Count kb_documents for the user, optionally filtered by source_table."""
    if source_table is not None:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS cnt
            FROM kb_documents
            WHERE user_id = $1 AND source_table = $2
            """,
            user_id,
            source_table,
        )
    else:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS cnt
            FROM kb_documents
            WHERE user_id = $1
            """,
            user_id,
        )
    return row["cnt"] if row else 0


async def list_documents(
    conn: asyncpg.Connection,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    source_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List kb_documents for the user with optional source_type filter."""
    if source_type is not None:
        rows = await conn.fetch(
            """
            SELECT id, source_type, source_table, source_id, title, created_at
            FROM kb_documents
            WHERE user_id = $1 AND source_type = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
            """,
            user_id,
            source_type,
            limit,
            offset,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, source_type, source_table, source_id, title, created_at
            FROM kb_documents
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id,
            limit,
            offset,
        )
    return [
        {
            "id": str(r["id"]),
            "source_type": r["source_type"] or "",
            "source_table": r["source_table"],
            "source_id": r["source_id"],
            "title": r["title"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
