"""
Sentinel-RAG Data Models
Pydantic schemas for all data structures flowing through the pipeline.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class DocumentMetadata(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    authority_score: float = Field(ge=0.0, le=1.0, default=0.8)
    access_level: int = Field(ge=1, le=5, default=1)
    chunk_index: int = 0
    milestone_tag: Optional[str] = None   # e.g. "Q1-2024", "v2.0"


class RetrievedChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: DocumentMetadata
    similarity_score: float = 0.0
    rerank_score: float = 0.0
    selected: bool = False
    rejection_reason: Optional[str] = None


class IntentResult(BaseModel):
    intent: str   # "support" | "technical"
    confidence: float
    reasoning: str


class ConflictResult(BaseModel):
    has_conflict: bool
    conflicting_chunks: List[str] = []
    explanation: str = ""


class ComputationResult(BaseModel):
    triggered: bool = False
    extracted_data: Optional[str] = None
    computation: Optional[str] = None
    result: Optional[str] = None


class DecisionTrace(BaseModel):
    query: str
    planning_steps: List[str] = []
    intent: IntentResult
    total_retrieved: int
    rbac_filtered: int
    temporal_filtered: int
    reranked_selected: int
    selected_chunk_ids: List[str]
    rejected_chunks: List[Dict[str, str]]   # {id, reason}
    reasoning_summary: str


class SentinelResponse(BaseModel):
    answer: str
    sources: List[RetrievedChunk]
    conflict: ConflictResult
    decision_trace: DecisionTrace
    computation: ComputationResult
    timestamp: datetime = Field(default_factory=datetime.utcnow)
