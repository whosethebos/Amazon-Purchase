# backend/llm/analyze.py
"""LLM analysis helper — isolated from FastAPI for testability."""
from llm.ollama_client import chat_json

_LLM_FALLBACK: dict = {
    "summary": "",
    "pros": [],
    "cons": [],
    "featured_review_indices": [],
}


async def run_llm_analysis(title: str, reviews: list[dict]) -> dict:
    """
    Call Ollama to summarize product reviews and pick representative ones.
    Returns _LLM_FALLBACK on any error.
    """
    formatted = "\n\n".join(
        f"[{i}] {r['stars']}★ — {r['title']}\n{r['body']}"
        for i, r in enumerate(reviews)
    )
    prompt = f"""You are analyzing customer reviews for an Amazon product.

Product: {title}

Reviews (indexed 0 to {len(reviews) - 1}):
{formatted or "(no reviews available)"}

Respond ONLY with valid JSON in this exact shape:
{{
  "summary": "<2-3 sentence overview>",
  "pros": ["<specific pro>", ...],
  "cons": ["<specific con>", ...],
  "featured_review_indices": [<3-5 indices from 0 to {len(reviews) - 1} — pick substantive reviews covering both praise and criticism; return [] if no reviews>]
}}

Rules:
- pros and cons: 3-5 items each, grounded in the review text
- featured_review_indices: valid 0-based indices only
- Return only the JSON object, no other text"""

    try:
        return await chat_json([{"role": "user", "content": prompt}])
    except Exception:
        return _LLM_FALLBACK
