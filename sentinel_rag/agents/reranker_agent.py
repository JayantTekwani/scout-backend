"""
Sentinel-RAG Reranker Agent
LLM-based reranking of top-K chunks by relevance + recency + authority.
"""

from typing import List
from datetime import datetime
import json
import re

from langchain_core.messages import SystemMessage, HumanMessage

from core.config import CONFIG
from core.llm import get_chat_llm
from core.models import RetrievedChunk


RERANK_SYSTEM = """You are a retrieval quality judge for Sentinel-RAG, an enterprise document intelligence system.

Given a user query and a list of retrieved document chunks, score each chunk from 0.0 to 1.0 based on:
- Relevance (50%): Does this chunk directly answer or support the query?
- Recency (30%): More recent timestamps score higher (provided as days_old).
- Authority (20%): Higher authority_score = more trustworthy source.

Return ONLY a JSON array (no markdown), same order as input, with objects:
[{"chunk_id": "...", "score": 0.85, "reason": "directly answers question about X"}]"""


def rerank_chunks(
    query: str,
    chunks: List[RetrievedChunk],
    top_k: int = CONFIG.TOP_K_RERANK,
) -> tuple[List[RetrievedChunk], List[dict]]:
    """
    Rerank chunks using LLM. Returns (selected_chunks, rejected_info).
    """
    if not chunks:
        return [], []

    # Build context for LLM
    now = datetime.utcnow()
    chunk_data = []
    for c in chunks:
        days_old = max(0, (now - c.metadata.timestamp).days)
        chunk_data.append({
            "chunk_id": c.chunk_id,
            "content_preview": c.content[:1200],
            "days_old": days_old,
            "authority_score": c.metadata.authority_score,
            "source": c.metadata.source,
        })

    llm = get_chat_llm(temperature=0.0)
    prompt = f"Query: {query}\n\nChunks to score:\n{json.dumps(chunk_data, indent=2)}"
    messages = [
        SystemMessage(content=RERANK_SYSTEM),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        raw = re.sub(r"```json\s*|```", "", raw).strip()
        scores = json.loads(raw)
    except Exception as e:
        # Fallback: use similarity scores
        scores = [{"chunk_id": c.chunk_id, "score": c.similarity_score, "reason": "Fallback: similarity score"} for c in chunks]

    # Map scores back
    score_map = {s["chunk_id"]: s for s in scores}
    for c in chunks:
        entry = score_map.get(c.chunk_id, {})
        c.rerank_score = float(entry.get("score", 0.5))

    # Sort by rerank score descending
    ranked = sorted(chunks, key=lambda x: x.rerank_score, reverse=True)
    selected = ranked[:top_k]
    rejected_raw = ranked[top_k:]

    for c in selected:
        c.selected = True
    for c in rejected_raw:
        c.selected = False
        entry = score_map.get(c.chunk_id, {})
        c.rejection_reason = f"Rerank score {c.rerank_score:.2f} below top-{top_k} threshold. {entry.get('reason','')}"

    rejected_info = [
        {"id": c.chunk_id, "reason": c.rejection_reason or "Low rerank score"}
        for c in rejected_raw
    ]
    return selected, rejected_info
