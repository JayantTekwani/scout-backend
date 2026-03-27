"""
SCOUT Pipeline Orchestrator
Integrated with Groq LPU & Dell Security Protocol.
Fixed: 'tuple' object has no attribute 'metadata' error.
"""

import os
import sys
from typing import Optional
from datetime import datetime

# Path setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import CONFIG
from core.models import SentinelResponse, ConflictResult
from core.ingestion import VectorStoreManager, build_retrieved_chunks

# Agents
from agents.planning_agent import plan_query
from agents.intent_agent import classify_intent
from agents.filter_agent import apply_rbac_filter, apply_temporal_filter
from agents.reranker_agent import rerank_chunks
from agents.conflict_agent import detect_conflicts
from agents.excel_agent import run_excel_sandbox
from agents.answer_agent import generate_answer
from agents.trace_builder import build_decision_trace


class SentinelPipeline:
    """
    SCOUT Agentic RAG Pipeline.
    Wired for Groq Inference & Enterprise Veracity.
    """

    def __init__(self, index_path: Optional[str] = None):
        # Initialize the vector store manager (FAISS)
        self.vector_store = VectorStoreManager(index_path=index_path or CONFIG.INDEX_PATH)
        
        # Ensure Groq API Key is available in environment
        if not os.environ.get("GROQ_API_KEY") and CONFIG.GROQ_API_KEY:
            os.environ["GROQ_API_KEY"] = CONFIG.GROQ_API_KEY

    def run(
        self,
        query: str,
        user_access_level: int = 1,
        after_date: Optional[datetime] = None,
        before_date: Optional[datetime] = None,
        milestone_tag: Optional[str] = None,
    ) -> SentinelResponse:
        """
        Execute the SCOUT Discovery Pipeline.
        """

        # --- Step 0: Planning Agent ---
        planning_steps = plan_query(query)

        # --- Step 1: Intent Classification ---
        intent = classify_intent(query)

        # --- Step 2: Vector Retrieval (Dell Knowledge Base) ---
        search_results = self.vector_store.similarity_search(
            query, k=CONFIG.TOP_K_RETRIEVE
        )
        total_retrieved = len(search_results)

        # 🚨 SAFE UNPACK LOGIC 🚨
        # Agar FAISS (Doc, Score) de raha hai toh sirf Doc nikalo.
        # Agar sirf Doc de raha hai toh as-is rakho.
        raw_results = []
        for res in search_results:
            if isinstance(res, tuple):
                raw_results.append(res[0]) # Tuple hai toh pehla element lo
            else:
                raw_results.append(res)    # Seedha Document hai toh wahi lo

        # --- Step 3: RBAC Filtering (Security Layer) ---
        # Ab raw_results 100% Documents ki list hai, unpacking error nahi aayega
        rbac_allowed, rbac_rejected = apply_rbac_filter(raw_results, user_access_level)

        # --- Step 4: Temporal Filtering ---
        temp_allowed, temp_rejected = apply_temporal_filter(
            rbac_allowed,
            after_date=after_date,
            before_date=before_date,
            milestone_tag=milestone_tag,
        )

        # --- Convert to SCOUT Internal Objects ---
        all_chunks = build_retrieved_chunks(temp_allowed)

        # --- Step 5: LLM Reranking ---
        selected_chunks, rerank_rejected = rerank_chunks(query, all_chunks)

        # --- Step 6: Conflict Detection ---
        conflict = detect_conflicts(selected_chunks)

        # --- Step 7: Excel Sandbox ---
        computation = run_excel_sandbox(query, selected_chunks)

        # --- Step 8: Answer Generation ---
        answer = generate_answer(
            query=query,
            chunks=selected_chunks,
            conflict=conflict,
            intent=intent,
            planning_steps=planning_steps,
        )

        # Add concise computed result without exposing internal logic details
        if computation.triggered and computation.result:
            answer = (
                f"**Computed Result**\n"
                f"- {computation.result}\n\n"
                f"{answer}"
            )

        # --- Step 9: Decision Trace (Audit Trail for the HUD) ---
        trace = build_decision_trace(
            query=query,
            planning_steps=planning_steps,
            intent=intent,
            total_retrieved=total_retrieved,
            rbac_rejected=rbac_rejected,
            temporal_rejected=temp_rejected,
            rerank_rejected=rerank_rejected,
            selected_chunks=selected_chunks,
        )

        return SentinelResponse(
            answer=answer,
            sources=selected_chunks,
            conflict=conflict,
            decision_trace=trace,
            computation=computation,
        )
