# backend/agents/ranker_agent.py
from llm.ollama_client import chat_json


# To change ranking criteria (value, quality, reliability), edit this prompt.
RANKING_PROMPT = """You are a product ranking expert.

Score each of the following Amazon products on a scale of 0 to 100 based on:
- Value for money (price vs features)
- Quality (build quality, durability based on reviews)
- Reliability (consistency of positive reviews)

Products:
{products_text}

Return a JSON object with a "rankings" array. Each item must have:
- "asin": the product ASIN
- "score": integer 0-100
- "rank": integer starting from 1 (1 = best)

Sort by score descending. Return only valid JSON, no extra text."""


class RankerAgent:
    """
    Scores and ranks analyzed products using the local LLM (Ollama).
    Model is configured via OLLAMA_MODEL in .env (default: qwen3:14b).
    To change scoring criteria, edit RANKING_PROMPT above.
    """

    async def rank(
        self, products: list[dict], analyses: dict[str, dict], requirements: list[str] | None = None
    ) -> list[dict]:
        """
        products: list of product dicts with asin, title, price, rating, review_count
        analyses: dict mapping product asin to analysis dict (summary, pros, cons)
        Returns products sorted by score with score and rank added.
        """
        if not products:
            return []

        products_text = ""
        for i, p in enumerate(products, 1):
            analysis = analyses.get(p["asin"], {})
            products_text += (
                f"{i}. ASIN: {p['asin']}\n"
                f"   Title: {p.get('title', 'Unknown')}\n"
                f"   Price: ${p.get('price', 'N/A')}\n"
                f"   Rating: {p.get('rating', 'N/A')}/5 ({p.get('review_count', 0)} reviews)\n"
                f"   Summary: {analysis.get('summary', 'N/A')}\n"
                f"   Pros: {', '.join(analysis.get('pros', []))}\n"
                f"   Cons: {', '.join(analysis.get('cons', []))}\n\n"
            )

        if requirements:
            req_block = "\n".join(f"- {r}" for r in requirements)
            content = (
                RANKING_PROMPT.format(products_text=products_text)
                + f"\n\nAdditional user requirements — products meeting more of these should score higher:\n{req_block}"
            )
        else:
            content = RANKING_PROMPT.format(products_text=products_text)

        result = await chat_json([{"role": "user", "content": content}])

        rank_map = {
            r["asin"]: {"score": r["score"], "rank": r["rank"]}
            for r in result.get("rankings", [])
        }

        ranked = []
        for p in products:
            rank_data = rank_map.get(p["asin"], {"score": 50, "rank": 99})
            ranked.append({**p, **rank_data})

        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
        return ranked
