# backend/llm/ollama_client.py
import json
import httpx
from config import settings


async def chat(messages: list[dict], response_format: str = "text") -> str:
    """
    Send a chat request to Ollama.

    Args:
        messages: list of {"role": "user"|"assistant"|"system", "content": "..."}
        response_format: "text" or "json" (for structured output)

    Returns:
        The model's response as a string.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
    }
    if response_format == "json":
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


async def chat_json(messages: list[dict]) -> dict:
    """
    Like chat() but always requests JSON output and parses it.
    """
    content = await chat(messages, response_format="json")
    return json.loads(content)
