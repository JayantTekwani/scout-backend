"""
Sentinel-RAG RBAC + Temporal Filtering
- RBAC: filter chunks where user_access >= doc_access_level
- Temporal: filter by date range or milestone tag
"""

from typing import List, Optional, Tuple
from datetime import datetime
from langchain_core.documents import Document

from core.models import RetrievedChunk, DocumentMetadata


def apply_rbac_filter(results, user_access_level: int):
    """
    Filters document chunks based on RBAC access levels.
    """
    allowed = []
    rejected = []

    for item in results:
        # 🚨 FIX: Handle both (Doc, Score) and plain Doc 🚨
        if isinstance(item, tuple):
            doc = item[0]
        else:
            doc = item

        # Access logic
        doc_level = doc.metadata.get("access_level", 1)
        
        if user_access_level >= doc_level:
            allowed.append(doc)
        else:
            rejected.append({
                "id": doc.metadata.get("doc_id", "unknown"),
                "reason": f"Level {doc_level} required (User: {user_access_level})"
            })
            
    return allowed, rejected


def apply_temporal_filter(
    results: List[Tuple[Document, float]],
    after_date: Optional[datetime] = None,
    before_date: Optional[datetime] = None,
    milestone_tag: Optional[str] = None,
) -> Tuple[List[Tuple[Document, float]], List[dict]]:
    """
    Filter chunks by timestamp range or milestone tag.
    If no filters provided, returns all results unchanged.
    """
    if after_date is None and before_date is None and milestone_tag is None:
        return results, []

    allowed = []
    rejected = []
    for doc, score in results:
        ts_raw = doc.metadata.get("timestamp")
        doc_milestone = doc.metadata.get("milestone_tag", "")
        doc_id = doc.metadata.get("doc_id", "?")

        # Milestone filter (overrides date filters if set)
        if milestone_tag and doc_milestone != milestone_tag:
            rejected.append({
                "id": doc_id,
                "reason": f"Temporal: milestone '{doc_milestone}' ≠ filter '{milestone_tag}'",
            })
            continue

        # Date range filter
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw)
                if after_date and ts < after_date:
                    rejected.append({"id": doc_id, "reason": f"Temporal: chunk date {ts.date()} before {after_date.date()}"})
                    continue
                if before_date and ts > before_date:
                    rejected.append({"id": doc_id, "reason": f"Temporal: chunk date {ts.date()} after {before_date.date()}"})
                    continue
            except Exception:
                pass  # Keep if timestamp unparseable

        allowed.append((doc, score))

    return allowed, rejected


def build_retrieved_chunks(
    results: List[Tuple[Document, float]],
) -> List[RetrievedChunk]:
    """Convert raw (doc, score) list into RetrievedChunk objects."""
    chunks = []
    for doc, score in results:
        m = doc.metadata
        try:
            ts = datetime.fromisoformat(m.get("timestamp", datetime.utcnow().isoformat()))
        except Exception:
            ts = datetime.utcnow()

        meta = DocumentMetadata(
            doc_id=m.get("doc_id", "?"),
            source=m.get("source", "unknown"),
            timestamp=ts,
            authority_score=float(m.get("authority_score", 0.8)),
            access_level=int(m.get("access_level", 1)),
            chunk_index=int(m.get("chunk_index", 0)),
            milestone_tag=m.get("milestone_tag"),
        )
        chunk = RetrievedChunk(
            chunk_id=meta.doc_id,
            content=doc.page_content,
            metadata=meta,
            similarity_score=float(1 / (1 + score)),  # Convert L2 to similarity
        )
        chunks.append(chunk)
    return chunks
