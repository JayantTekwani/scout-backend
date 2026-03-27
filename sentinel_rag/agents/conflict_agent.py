"""
Sentinel-RAG Conflict Detection Agent
Detects factual contradictions in retrieved chunks using LLM reasoning.
"""

from typing import List
import json
import re

from langchain_core.messages import SystemMessage, HumanMessage

from core.llm import get_chat_llm
from core.models import RetrievedChunk, ConflictResult


CONFLICT_SYSTEM = """You are a fact-consistency auditor for Sentinel-RAG.

Examine the provided document chunks and detect any FACTUAL CONTRADICTIONS.
Look for:
- Conflicting numerical values (prices, versions, dates, limits)
- Opposing procedural steps for the same task
- Contradictory policy statements
- Inconsistent technical specifications

Only flag genuine contradictions, not mere differences in depth or perspective.

Respond with ONLY a JSON object (no markdown):
{
  "has_conflict": true or false,
  "conflicting_chunks": ["chunk_id_1", "chunk_id_2"],
  "explanation": "Chunk X says the limit is 100 requests/min, but Chunk Y states 500 requests/min for the same API endpoint."
}

If no conflict, set has_conflict=false and leave conflicting_chunks as [].
"""


def detect_conflicts(chunks: List[RetrievedChunk]) -> ConflictResult:
    """
    Run conflict detection on the selected chunks.
    Returns ConflictResult.
    """
    if len(chunks) < 2:
        return ConflictResult(has_conflict=False, explanation="Insufficient chunks to compare.")

    # Build chunk summaries
    chunk_summaries = []
    for c in chunks:
        chunk_summaries.append({
            "chunk_id": c.chunk_id,
            "source": c.metadata.source,
            "timestamp": c.metadata.timestamp.isoformat(),
            "content": c.content[:500],
        })

    llm = get_chat_llm(temperature=0.0)

    prompt = f"Analyze these chunks for contradictions:\n\n{json.dumps(chunk_summaries, indent=2)}"
    messages = [
        SystemMessage(content=CONFLICT_SYSTEM),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        raw = re.sub(r"```json\s*|```", "", raw).strip()
        data = json.loads(raw)
        return ConflictResult(
            has_conflict=bool(data.get("has_conflict", False)),
            conflicting_chunks=data.get("conflicting_chunks", []),
            explanation=data.get("explanation", ""),
        )
    except Exception as e:
        return ConflictResult(
            has_conflict=False,
            explanation=f"Conflict detection unavailable: {str(e)}",
        )
