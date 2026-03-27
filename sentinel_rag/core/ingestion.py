"""
Sentinel-RAG Document Ingestion
Loads PDFs/text, chunks them, enriches with metadata, stores in FAISS.
"""

import os
import json
import uuid
import pickle
import shutil
import hashlib
import re
from html import unescape
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import random

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

from core.config import CONFIG
from core.models import DocumentMetadata, RetrievedChunk

# Metadata constants
MILESTONE_TAGS = ["Q1-2024", "Q2-2024", "Q3-2024", "Q4-2024", "Q1-2025", "v1.0", "v2.0", "v3.0"]


class LocalHashEmbeddings:
    """
    Offline-safe fallback embeddings.
    Uses deterministic token hashing into a fixed-size vector so SCOUT can run
    even when HuggingFace model download is unavailable.
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        tokens = text.lower().split()
        if not tokens:
            return vec
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

def _assign_milestone(chunk_index: int, total_chunks: int) -> str:
    ratio = chunk_index / max(total_chunks, 1)
    idx = int(ratio * len(MILESTONE_TAGS))
    return MILESTONE_TAGS[min(idx, len(MILESTONE_TAGS) - 1)]

def _simulate_timestamp(chunk_index: int, total_chunks: int) -> datetime:
    days_back = int((1 - chunk_index / max(total_chunks, 1)) * 365)
    return datetime.utcnow() - timedelta(days=days_back)


def _chunk_raw_text(raw_text: str, source_name: str, authority_score: float, access_level: int) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CONFIG.CHUNK_SIZE,
        chunk_overlap=CONFIG.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_text(raw_text or "")
    total = len(chunks)

    documents = []
    for i, chunk_text in enumerate(chunks):
        doc = Document(
            page_content=chunk_text,
            metadata={
                "doc_id": str(uuid.uuid4())[:8],
                "source": source_name,
                "timestamp": _simulate_timestamp(i, total),
                "authority_score": authority_score,
                "access_level": access_level,
                "chunk_index": i,
                "milestone_tag": _assign_milestone(i, total),
            },
        )
        documents.append(doc)
    return documents


def _html_to_text(html: str) -> str:
    txt = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = unescape(txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def load_and_chunk_file(file_path: str, authority_score: float = 0.8, access_level: int = 1) -> List[Document]:
    ext = os.path.splitext(file_path)[-1].lower()
    source_name = os.path.basename(file_path)

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return _chunk_raw_text(raw_text, source_name, authority_score, access_level)


def load_and_chunk_url(url: str, authority_score: float = 0.8, access_level: int = 1) -> List[Document]:
    """Load and chunk public URL content (e.g., Confluence public page/export)."""
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (SCOUT-RAG URL Ingestion)"},
    )
    with urlopen(req, timeout=20) as resp:
        raw = resp.read()
        content_type = (resp.headers.get("Content-Type") or "").lower()

    text = raw.decode("utf-8", errors="ignore")
    parsed = urlparse(url)
    source_name = parsed.netloc + parsed.path

    if "text/html" in content_type or source_name.lower().endswith((".html", ".htm")):
        text = _html_to_text(text)

    return _chunk_raw_text(text, source_name, authority_score, access_level)

class VectorStoreManager:
    """SCOUT Vector Engine using Local HuggingFace Embeddings."""

    def __init__(self, index_path: str = CONFIG.INDEX_PATH):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"local_files_only": True},
            )
        except Exception:
            # Fallback keeps API online in restricted/offline environments.
            self.embeddings = LocalHashEmbeddings(dim=384)
        self.index_path = index_path
        self.vectorstore: Optional[FAISS] = None
        self._load_if_exists()

    def _load_if_exists(self):
        if os.path.exists(self.index_path):
            try:
                self.vectorstore = FAISS.load_local(
                    self.index_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
            except Exception:
                self.vectorstore = None

    def add_documents(self, documents: List[Document]) -> int:
        if self.vectorstore is None:
            self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        else:
            self.vectorstore.add_documents(documents)
        self.vectorstore.save_local(self.index_path)
        return len(documents)

    def similarity_search(self, query: str, k: int = CONFIG.TOP_K_RETRIEVE) -> List[Tuple[Document, float]]:
        if self.vectorstore is None:
            return []
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def is_ready(self) -> bool:
        return self.vectorstore is not None

    def doc_count(self) -> int:
        return self.vectorstore.index.ntotal if self.vectorstore else 0

    def reset(self):
        if os.path.exists(self.index_path):
            shutil.rmtree(self.index_path)
        self.vectorstore = None

def build_retrieved_chunks(langchain_docs) -> List[RetrievedChunk]:
    chunks = []
    for doc in langchain_docs:
        chunks.append(RetrievedChunk(
            chunk_id=doc.metadata.get("doc_id", str(uuid.uuid4())[:8]), 
            content=doc.page_content,
            metadata=doc.metadata,
            similarity_score=0.0,
            rerank_score=0.0,
            selected=True
        ))
    return chunks
