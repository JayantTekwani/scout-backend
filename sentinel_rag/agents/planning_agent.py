"""
Sentinel-RAG Planning Agent
Breaks a user question into a short execution plan for downstream agents.
"""

import json
import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm import get_chat_llm


PLANNER_SYSTEM = """You are SCOUT's planning agent.
Create a concise execution plan (3-5 steps) for answering a user question with RAG.

Return ONLY JSON:
{
  "steps": ["step 1", "step 2", "step 3"]
}
"""


def plan_query(query: str) -> List[str]:
    """Return short plan steps for the query, with robust fallback."""
    try:
        llm = get_chat_llm(temperature=0.0)
        resp = llm.invoke(
            [
                SystemMessage(content=PLANNER_SYSTEM),
                HumanMessage(content=f"User query: {query}"),
            ]
        )
        raw = re.sub(r"```json\s*|```", "", resp.content.strip()).strip()
        data = json.loads(raw)
        steps = [str(s).strip() for s in data.get("steps", []) if str(s).strip()]
        if steps:
            return steps[:6]
    except Exception:
        pass

    return [
        "Identify user intent and target entities in the question.",
        "Retrieve candidate chunks from indexed documents.",
        "Filter by access/temporal constraints and rank relevance.",
        "Synthesize a grounded answer with citations.",
    ]
