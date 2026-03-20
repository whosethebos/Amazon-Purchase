# backend/llm/analyze.py
"""LLM analysis helper — isolated from FastAPI for testability."""
from llm.ollama_client import chat_json

_LLM_FALLBACK: dict = {
    "summary": "",
    "pros": [],
    "cons": [],
    "featured_review_indices": [],
    "score": None,
}


async def run_llm_analysis(
    title: str,
    reviews: list[dict],
    histogram: dict,
    review_count: int | None,
) -> dict:
    """
    Call Ollama to summarize product reviews, pick representative ones, and score the product.
    Returns a shallow copy of _LLM_FALLBACK on any error.
    """
    formatted = "\n\n".join(
        f"[{i}] {r['stars']}★ — {r['title']}\n{r['body']}"
        for i, r in enumerate(reviews)
    )

    histogram_lines = "\n".join(
        f"  {star}★: {histogram.get(str(star), 0):.1f}%"
        for star in [5, 4, 3, 2, 1]
    )
    review_count_str = str(review_count) if review_count is not None else "unknown"

    prompt = f"""You are analyzing customer reviews for an Amazon product.

Product: {title}
Total reviews: {review_count_str}
Star distribution:
{histogram_lines}

Reviews (indexed 0 to {len(reviews) - 1}):
{formatted or "(no reviews available)"}

Respond ONLY with valid JSON in this exact shape:
{{
  "summary": "<2-3 sentence overview>",
  "pros": ["<specific pro>", ...],
  "cons": ["<specific con>", ...],
  "featured_review_indices": [<3-5 indices from 0 to {len(reviews) - 1} — pick substantive reviews covering both praise and criticism; return [] if no reviews>],
  "score": <plain integer between 1 and 10 inclusive — not a float, not a string>
}}

Rules:
- pros and cons: 3-5 items each, grounded in the review text
- featured_review_indices: valid 0-based indices only
- score: rate 1–10 based on (a) value for the price per review sentiment, (b) volume/trustworthiness of reviews, (c) star distribution quality, (d) balance of pros vs cons. Return an integer, not a float or string.
- Return only the JSON object, no other text"""

    try:
        return await chat_json([{"role": "user", "content": prompt}])
    except Exception:
        return dict(_LLM_FALLBACK)
