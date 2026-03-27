"""
Sentinel-RAG Decision Trace Builder
Assembles the full audit trail of the retrieval pipeline.
"""

from typing import List, Dict
import json

from langchain_core.messages import SystemMessage, HumanMessage

from core.llm import get_chat_llm
from core.models import DecisionTrace, IntentResult, RetrievedChunk


TRACE_SYSTEM = """You are Sentinel-RAG's transparency engine. 
Given a query, intent, and the pipeline stats, write a concise reasoning summary (3-5 sentences) explaining:
- Why this intent was assigned
- What types of chunks were prioritized  
- Why the final selection was made
- Any notable filtering decisions

Be factual and transparent. Write in third person ("Sentinel-RAG selected...").
"""


def build_decision_trace(
    query: str,
    planning_steps: List[str],
    intent: IntentResult,
    total_retrieved: int,
    rbac_rejected: List[dict],
    temporal_rejected: List[dict],
    rerank_rejected: List[dict],
    selected_chunks: List[RetrievedChunk],
) -> DecisionTrace:
    """Build the full decision trace object."""

    all_rejected = rbac_rejected + temporal_rejected + rerank_rejected

    # Generate reasoning summary via LLM
    stats = {
        "query": query,
        "planning_steps": planning_steps,
        "intent": intent.intent,
        "intent_confidence": intent.confidence,
        "intent_reasoning": intent.reasoning,
        "total_retrieved": total_retrieved,
        "rbac_filtered_count": len(rbac_rejected),
        "temporal_filtered_count": len(temporal_rejected),
        "rerank_rejected_count": len(rerank_rejected),
        "final_selected_count": len(selected_chunks),
        "selected_sources": list({c.metadata.source for c in selected_chunks}),
        "avg_rerank_score": (
            sum(c.rerank_score for c in selected_chunks) / len(selected_chunks)
            if selected_chunks else 0.0
        ),
    }

    llm = get_chat_llm(temperature=0.0)

    try:
        response = llm.invoke([
            SystemMessage(content=TRACE_SYSTEM),
            HumanMessage(content=f"Pipeline stats:\n{json.dumps(stats, indent=2)}"),
        ])
        reasoning_summary = response.content.strip()
    except Exception:
        reasoning_summary = (
            f"Sentinel-RAG classified this as a '{intent.intent}' query with "
            f"{intent.confidence:.0%} confidence. Retrieved {total_retrieved} chunks, "
            f"filtered {len(rbac_rejected)} via RBAC and {len(temporal_rejected)} via temporal rules, "
            f"then reranked to select the top {len(selected_chunks)} most relevant chunks."
        )

    return DecisionTrace(
        query=query,
        planning_steps=planning_steps,
        intent=intent,
        total_retrieved=total_retrieved,
        rbac_filtered=len(rbac_rejected),
        temporal_filtered=len(temporal_rejected),
        reranked_selected=len(selected_chunks),
        selected_chunk_ids=[c.chunk_id for c in selected_chunks],
        rejected_chunks=all_rejected,
        reasoning_summary=reasoning_summary,
    )
