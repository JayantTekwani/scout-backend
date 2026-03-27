"""
Sentinel-RAG Answer Generator
Synthesizes final answer ONLY from retrieved chunks. Handles conflicts.
Updated for FREE Groq Inference.
"""

from typing import List
from langchain_core.messages import SystemMessage, HumanMessage

from core.llm import get_chat_llm
from core.models import RetrievedChunk, ConflictResult, IntentResult

# Branding change to SCOUT
BASE_SYSTEM = """You are SCOUT, an enterprise document intelligence assistant for Dell.

CRITICAL RULES:
1. Answer ONLY based on the provided document chunks. Never hallucinate.
2. If chunks don't contain enough information, say exactly: "Insufficient information in the knowledge base."
3. Cite the source name for every claim (e.g., [Source: manual_v2.pdf]).
4. Tone must be professional, helpful, concise, and human-to-human.
5. Do NOT reveal internal reasoning or chain-of-thought.
6. Do NOT include labels like "Steps", "Analysis", "Intent", "Thinking", or "Planning".

RESPONSE FORMAT (always):
- Start immediately with the answer.
- Use bold headers and bullet points.
- Keep paragraphs short and action-oriented.
- If a link/path/location is available, explicitly tell the user where to go first.
"""

CONFLICT_SYSTEM = """You are SCOUT operating in CONFLICT MODE.
Contradictions detected. You MUST:
1. Present BOTH views labeled as [View A] and [View B].
2. Cite sources for both.
3. Recommend the authoritative one (Newer Date + Higher Authority Score = Better).
4. Do NOT reveal internal reasoning or chain-of-thought.
5. Do NOT include labels like "Steps", "Analysis", "Intent", "Thinking", or "Planning".
6. Keep output concise with bold headers and bullet points.
"""


def _fallback_grounded_answer(query: str, chunks: List[RetrievedChunk], rate_limited: bool) -> str:
    """
    Deterministic fallback answer when LLM generation is unavailable.
    Keeps response grounded in retrieved chunks.
    """
    lines = ["**Answer**"]
    if rate_limited:
        lines.append("- Provider is rate-limited, so this is a grounded fallback from retrieved documents.")
    lines.append("- Based on retrieved context only.")
    lines.append("")
    lines.append("**Key Evidence**")
    for i, c in enumerate(chunks[:3], 1):
        snippet = " ".join(c.content.strip().split())
        snippet = snippet[:280] + ("..." if len(snippet) > 280 else "")
        lines.append(f"- {i}. {snippet} [Source: {c.metadata.source}]")
    lines.append("")
    lines.append("**Next Action**")
    lines.append("- Retry after rate-limit reset or switch to a higher quota key for a richer synthesis.")
    return "\n".join(lines)

def generate_answer(
    query: str,
    chunks: List[RetrievedChunk],
    conflict: ConflictResult,
    intent: IntentResult,
    planning_steps: List[str] | None = None,
) -> str:
    if not chunks:
        return "⚠️ No relevant documents found. Please ingest data to Scout."

    # Build context
    context_parts = []
    for i, c in enumerate(chunks, 1):
        context_parts.append(
            f"[Chunk {i} | Source: {c.metadata.source} | "
            f"Date: {c.metadata.timestamp.strftime('%Y-%m-%d')} | "
            f"Authority: {c.metadata.authority_score:.1f}]\n{c.content}"
        )
    context = "\n\n---\n\n".join(context_parts)

    system = CONFLICT_SYSTEM if conflict.has_conflict else BASE_SYSTEM

    llm = get_chat_llm(temperature=0.1)

    user_msg = (
        f"Query: {query}\nStyle Mode: {intent.intent}\n"
        f"Conflict Note: {conflict.explanation if conflict.has_conflict else 'None'}\n\n"
        f"Context:\n{context}"
    )

    messages = [SystemMessage(content=system), HumanMessage(content=user_msg)]

    try:
        response = llm.invoke(messages)
        return response.content.strip()
    except Exception as e:
        err = str(e)
        rate_limited = "rate limit" in err.lower() or "429" in err
        return _fallback_grounded_answer(query=query, chunks=chunks, rate_limited=rate_limited)
