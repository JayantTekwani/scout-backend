# 🛡️ Sentinel-RAG

**Agentic Retrieval-Augmented Generation System**

A full-featured, production-grade RAG system with multi-agent orchestration, RBAC, conflict detection, and complete decision transparency.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key
```bash
cp .env.example .env
# Edit .env and add your key
```

### 3. Run Sentinel-RAG
```bash
streamlit run app.py
```

### 4. Run HTTP API (for `scout_website.html` chatbot)
```bash
python3 api_server.py
```

The API starts at `http://127.0.0.1:8008`:
- `GET /health` → backend status + indexed document count
- `GET /projects` → list available projects + active project
- `POST /projects/select` → create/select project workspace
- `POST /session` → create/resume browser session id
- `POST /chat` → chatbot endpoint used by the website
- `POST /ingest` → upload and index documents (`.pdf`, `.txt`, `.md`)
- `POST /ingest_urls` → ingest public URLs / Confluence-like pages
- `POST /reset` → clear index

### Production Environment Variables

Set these on your backend host:

```bash
GROQ_API_KEY=...
SCOUT_LLM_PROVIDER=groq
SCOUT_LLM_MODEL=llama-3.1-8b-instant
SCOUT_TOP_K_RETRIEVE=24
SCOUT_TOP_K_RERANK=8
SCOUT_CHUNK_SIZE=1100
SCOUT_CHUNK_OVERLAP=180
SCOUT_ALLOWED_ORIGINS=https://your-frontend-domain.com
SCOUT_AUTH_TOKEN=your-shared-secret-token
```

- `SCOUT_ALLOWED_ORIGINS` can be comma-separated for multiple frontends.
- If `SCOUT_AUTH_TOKEN` is set, API requests must include `X-Scout-Token`.
- For open-source local inference, set:
  - `SCOUT_LLM_PROVIDER=ollama`
  - `SCOUT_OLLAMA_MODEL=llama3.1:8b`
  - `SCOUT_OLLAMA_BASE_URL=http://127.0.0.1:11434`

### Frontend Deployment Config

Before loading `scout_website.html`, inject:

```html
<script>
  window.SCOUT_API_BASE = "https://api.yourdomain.com";
  window.SCOUT_AUTH_TOKEN = "your-shared-secret-token";
</script>
```

This avoids hardcoding localhost in production.

### Stress Testing

Run a quick load test against `/chat`:

```bash
python3 stress_test.py --total 100 --concurrency 10 --ingest-seed-doc
```

Higher load example:

```bash
python3 stress_test.py --total 500 --concurrency 25 --ingest-seed-doc
```

If backend auth token is enabled:

```bash
python3 stress_test.py --token your-shared-secret-token --total 200 --concurrency 20 --ingest-seed-doc
```

---

## 🏗️ Architecture

```
sentinel_rag/
├── app.py                    ← Streamlit UI (main entry point)
├── requirements.txt
├── .env.example
│
├── core/
│   ├── config.py             ← Central configuration
│   ├── models.py             ← Pydantic data models
│   ├── ingestion.py          ← Document loading, chunking, FAISS store
│   └── pipeline.py           ← Master pipeline orchestrator
│
├── agents/
│   ├── intent_agent.py       ← LLM intent classifier (support/technical)
│   ├── filter_agent.py       ← RBAC + temporal filtering
│   ├── reranker_agent.py     ← LLM-based reranking
│   ├── conflict_agent.py     ← Contradiction detection
│   ├── excel_agent.py        ← Numerical computation sandbox
│   ├── answer_agent.py       ← Final answer generation
│   └── trace_builder.py      ← Decision trace assembly
│
└── data/
    └── demo_documents.txt    ← Pre-built demo dataset
```

---

## ✨ Features

| Feature | Implementation |
|---|---|
| **Document Ingestion** | PyPDF + LangChain TextSplitter → chunks with metadata |
| **Metadata** | timestamp, source, authority_score, access_level, milestone_tag |
| **Vector DB** | FAISS (persisted to disk, reloads automatically) |
| **Retrieval** | Top-20 semantic search via OpenAI embeddings |
| **Intent Classification** | LLM classifies queries as "support" or "technical" |
| **LLM Reranking** | Scores by relevance (50%) + recency (30%) + authority (20%) |
| **RBAC** | user_access_level >= doc_access_level to retrieve |
| **Temporal Filtering** | Filter by date range or milestone tag (Q1-2024, v2.0, etc.) |
| **Conflict Detection** | LLM identifies factual contradictions between chunks |
| **Excel Sandbox** | Extracts numerical data, executes Python in safe namespace |
| **Answer Generation** | Grounded-only responses; conflict-aware dual-answer mode |
| **Decision Trace** | Full audit: why selected, why rejected, reasoning summary |

---

## 🎮 Demo Dataset

Click **"🎯 Load Demo Dataset"** in the sidebar to ingest pre-built documents:

- `api_documentation_v2.txt` (access level 1) — Current API docs with rate limits, auth, pricing
- `support_guide.txt` (access level 1) — Password reset, refunds, support hours
- `security_policy_internal.txt` (access level 4) — Internal security procedures
- `api_documentation_v1_legacy.txt` (access level 1) — **Deprecated** v1 docs (creates conflicts!)
- `performance_benchmarks.txt` (access level 2) — Q1-2025 metrics with financial data
- `onboarding_guide.txt` (access level 1) — Customer onboarding steps

### 🧪 Try These Queries

**Intent + Retrieval:**
- "What is the API rate limit for Enterprise accounts?"
- "How do I reset my password?"

**Conflict Detection (set access level 1+):**
- "What are the API rate limits?" ← v1 says 500/min, v2 says 1000/min

**RBAC Demo:**
- "What are the encryption standards?" ← Set user access to 3 (won't see it), then 4 (will see it)

**Numerical Computation:**
- "Calculate the total infrastructure cost and revenue for Q1-2025"
- "What is the gross margin percentage?"

**Temporal Filtering:**
- Enable temporal filter → milestone "v1.0" → queries return only older chunks

---

## ⚙️ Configuration

Edit `core/config.py`:

```python
top_k_retrieve: int = 20    # Chunks retrieved from FAISS
top_k_rerank: int = 5       # Chunks after LLM reranking
chunk_size: int = 512       # Tokens per chunk
chunk_overlap: int = 64     # Overlap between chunks
llm_model: str = "gpt-4o-mini"
embedding_model: str = "text-embedding-3-small"
```

---

## 🔒 RBAC Access Levels

| Level | Label | Can Access |
|---|---|---|
| 1 | Public | All public docs |
| 2 | Standard | + Standard docs |
| 3 | Professional | + Pro-tier docs |
| 4 | Internal | + Internal/confidential |
| 5 | Admin | Everything |

---

## 📝 License

MIT — Built as a prototype for demonstration purposes.
