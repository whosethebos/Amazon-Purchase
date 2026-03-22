# backend/agents/analyst_agent.py
from llm.ollama_client import chat_json


# To change what the LLM extracts from reviews, edit this prompt.
REVIEW_ANALYSIS_PROMPT = """You are a product review analyst.

Analyze the following Amazon product reviews and return a JSON object with:
- "summary": a 2-3 sentence overview of what customers think
- "pros": a list of 3-5 key positive points (strings)
- "cons": a list of 2-4 key negative points (strings)
- "sentiment": overall sentiment, one of "positive", "mixed", or "negative"

Product: {title}

Reviews:
{reviews_text}

Return only valid JSON, no extra text."""


class ReviewAnalystAgent:
    """
    Analyzes scraped product reviews using the local LLM (Ollama).
    Model is configured via OLLAMA_MODEL in .env (default: qwen3:14b).
    To change analysis criteria, edit REVIEW_ANALYSIS_PROMPT above.
    """

    async def analyze(
        self, product_title: str, reviews: list[dict], requirements: list[str] | None = None
    ) -> dict:
        """
        Returns analysis dict: summary, pros, cons, sentiment.
        When requirements are provided, the LLM is asked to note whether the product meets them.
        """
        if not reviews:
            return {
                "summary": "No reviews available.",
                "pros": [],
                "cons": [],
                "sentiment": "mixed",
            }

        reviews_text = "\n\n".join([
            f"Rating: {r.get('rating', '?')}/5\n{r.get('title', '')}\n{r.get('body', '')}"
            for r in reviews[:20]
        ])

        if requirements:
            req_block = "\n".join(f"- {r}" for r in requirements)
            prompt = (
                f"You are a product review analyst.\n\n"
                f"Analyze the following Amazon product reviews and return a JSON object with:\n"
                f'- "summary": a 2-3 sentence overview of what customers think\n'
                f'- "pros": a list of 3-5 key positive points (strings)\n'
                f'- "cons": a list of 2-4 key negative points (strings)\n'
                f'- "sentiment": overall sentiment, one of "positive", "mixed", or "negative"\n\n'
                f"Note whether the product meets these user requirements in your summary:\n"
                f"{req_block}\n\n"
                f"Product: {product_title}\n\n"
                f"Reviews:\n{reviews_text}\n\n"
                f"Return only valid JSON, no extra text."
            )
        else:
            prompt = REVIEW_ANALYSIS_PROMPT.format(
                title=product_title,
                reviews_text=reviews_text,
            )

        result = await chat_json([{"role": "user", "content": prompt}])
        return {
            "summary": result.get("summary", ""),
            "pros": result.get("pros", []),
            "cons": result.get("cons", []),
            "sentiment": result.get("sentiment", "mixed"),
        }
