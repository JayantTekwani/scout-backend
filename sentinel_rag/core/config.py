"""
SCOUT Configuration
Central config file for all system parameters.
Updated for CAPS consistency and Local Embeddings.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SentinelConfig:
    # --- INFRASTRUCTURE (CAPS FOR CONSISTENCY) ---
    # Sabse pehle API Key ko CAPS mein define karo
    GROQ_API_KEY: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    
    # Blazing fast Groq Inference (env-overridable; cheaper default to reduce TPD burn)
    LLM_MODEL: str = field(default_factory=lambda: os.getenv("SCOUT_LLM_MODEL", "llama-3.1-8b-instant"))
    GROQ_BASE_URL: str = "https://api.groq.com/groq/v1"
    LLM_PROVIDER: str = field(default_factory=lambda: os.getenv("SCOUT_LLM_PROVIDER", "groq").lower())
    OLLAMA_MODEL: str = field(default_factory=lambda: os.getenv("SCOUT_OLLAMA_MODEL", "llama3.1:8b"))
    OLLAMA_BASE_URL: str = field(default_factory=lambda: os.getenv("SCOUT_OLLAMA_BASE_URL", "http://127.0.0.1:11434"))

    # --- EMBEDDINGS (LOCAL & FREE) ---
    # Note: We are using HuggingFace locally to keep Dell's data private
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- RETRIEVAL PARAMETERS ---
    TOP_K_RETRIEVE: int = int(os.getenv("SCOUT_TOP_K_RETRIEVE", "24"))
    TOP_K_RERANK: int = int(os.getenv("SCOUT_TOP_K_RERANK", "8"))
    CHUNK_SIZE: int = int(os.getenv("SCOUT_CHUNK_SIZE", "1100"))
    CHUNK_OVERLAP: int = int(os.getenv("SCOUT_CHUNK_OVERLAP", "180"))

    # FAISS index path
    INDEX_PATH: str = "./sentinel_index"

    # Access levels & Intent
    ACCESS_LEVELS: list = field(default_factory=lambda: [1, 2, 3, 4, 5])
    INTENT_LABELS: list = field(default_factory=lambda: ["support", "technical"])

# Create the Global Config Object
CONFIG = SentinelConfig()
