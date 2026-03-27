"""
Sentinel-RAG Excel Sandbox Agent
Detects numerical queries, extracts table-like data, executes Python computation.
"""

import re
import json
import ast
from typing import List
import pandas as pd

from langchain_core.messages import SystemMessage, HumanMessage

from core.llm import get_chat_llm
from core.models import RetrievedChunk, ComputationResult


EXTRACT_SYSTEM = """You are a data extraction agent for Sentinel-RAG.

Given a user query and document chunks, extract any numerical/tabular data relevant to the query.
If numerical data exists, provide Python code using pandas/basic arithmetic to compute the answer.

Respond ONLY with JSON (no markdown):
{
  "has_numerical_data": true or false,
  "extracted_data": "description of what data was found, e.g. 'prices: [100, 200, 300]'",
  "python_code": "valid Python code using only builtins and basic math. Store result in variable named 'result'.",
  "explanation": "what the code computes"
}

RULES:
- Only use Python builtins (sum, min, max, len, sorted, etc.) and basic arithmetic
- No imports needed
- Store final answer in variable: result
- If no numerical data, set has_numerical_data=false
"""

NUMERICAL_TRIGGERS = [
    r'\b(sum|total|average|avg|mean|count|maximum|minimum|max|min|calculate|compute|how many|how much)\b',
    r'\d+\.?\d*\s*(dollars?|\$|percent|%|units?|items?|requests?)',
    r'(price|cost|rate|limit|latency|throughput|quota|budget)',
]


def is_numerical_query(query: str) -> bool:
    """Quick heuristic check before calling LLM."""
    lower = query.lower()
    for pattern in NUMERICAL_TRIGGERS:
        if re.search(pattern, lower):
            return True
    return False


def run_safe_computation(code: str) -> str:
    """Execute simple Python code in a restricted namespace."""
    # Whitelist of safe builtins
    safe_builtins = {
        "__builtins__": {
            "sum": sum, "min": min, "max": max, "len": len, "abs": abs,
            "round": round, "sorted": sorted, "list": list, "dict": dict,
            "int": int, "float": float, "str": str, "range": range,
            "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
            "print": print, "True": True, "False": False, "None": None,
        }
    }
    try:
        local_ns = {}
        exec(code, safe_builtins, local_ns)
        result = local_ns.get("result", "No result variable found.")
        return str(result)
    except Exception as e:
        return f"Computation error: {e}"


def run_excel_sandbox(query: str, chunks: List[RetrievedChunk]) -> ComputationResult:
    """
    Detect if query is numerical, extract data from chunks, compute answer.
    """
    if not is_numerical_query(query):
        return ComputationResult(triggered=False)

    # Build context
    context = "\n\n".join([
        f"[Source: {c.metadata.source}]\n{c.content[:400]}"
        for c in chunks[:5]
    ])

    llm = get_chat_llm(temperature=0.0)

    prompt = f"User Query: {query}\n\nDocument Context:\n{context}"
    messages = [
        SystemMessage(content=EXTRACT_SYSTEM),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        raw = re.sub(r"```json\s*|```", "", raw).strip()
        data = json.loads(raw)
    except Exception as e:
        return ComputationResult(triggered=True, result=f"Extraction failed: {e}")

    if not data.get("has_numerical_data", False):
        return ComputationResult(triggered=False)

    code = data.get("python_code", "")
    computed = run_safe_computation(code) if code else "No computation code provided."

    return ComputationResult(
        triggered=True,
        extracted_data=data.get("extracted_data", ""),
        computation=data.get("explanation", ""),
        result=computed,
    )
