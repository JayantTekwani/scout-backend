"""
Sentinel-RAG Intent Classification Agent
Classifies user query into "support" or "technical" with routing logic.
"""

from langchain_core.messages import SystemMessage, HumanMessage
import json
import re

from core.llm import get_chat_llm
from core.models import IntentResult


SYSTEM_PROMPT = """You are an expert query intent classifier for a document retrieval system called Sentinel-RAG.

Classify user queries into EXACTLY one of these categories:

1. "support" — Questions about how to use a product, troubleshooting, FAQs, getting help, account issues, billing, policies, how-to guides.
   Examples: "How do I reset my password?", "Why is my subscription not working?", "What are the refund terms?"

2. "technical" — Questions about architecture, implementation, APIs, code, system specs, debugging code, technical configuration, performance metrics, data formats, numerical analysis.
   Examples: "What is the API rate limit?", "How does the authentication flow work?", "Calculate the average latency from the logs?"

Respond ONLY with a JSON object, no markdown:
{
  "intent": "support" or "technical",
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence explanation"
}"""


def classify_intent(query: str) -> IntentResult:
    """Classify the query intent using an LLM call."""
    try:
        llm = get_chat_llm(temperature=0.0)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Classify this query: {query}"),
        ]
        response = llm.invoke(messages)
        raw = response.content.strip()
    except Exception:
        raw = ""

    # Strip markdown code fences if present
    raw = re.sub(r"```json\s*|```", "", raw).strip()

    try:
        data = json.loads(raw)
        return IntentResult(
            intent=data.get("intent", "technical"),
            confidence=float(data.get("confidence", 0.7)),
            reasoning=data.get("reasoning", ""),
        )
    except Exception:
        # Fallback: keyword heuristic
        lower = query.lower()
        if any(w in lower for w in ["how do i", "help", "error", "not working", "refund", "support", "issue", "problem"]):
            return IntentResult(intent="support", confidence=0.6, reasoning="Keyword-based fallback classification.")
        return IntentResult(intent="technical", confidence=0.6, reasoning="Keyword-based fallback classification.")
