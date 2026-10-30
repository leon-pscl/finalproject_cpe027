import os
import httpx
from typing import List

# Use the Settings loader to pull the Groq API key (ensures .env is read)
from .config import get_settings

class GroqAnswerGenerator:
    """Simple wrapper around Groq's chat completion API (openai/gpt-oss-20b).

    The grounding prompt is hard‑coded according to the specification:
    * "Answer using only the provided context. If the context does not contain the answer, say you don't know."
    * Keep answers concise and cite the source chunk IDs.
    """
    def __init__(self) -> None:
        # Pull the key from Settings (which loads .env via pydantic‑settings)
        self.api_key = get_settings().groq_api_key
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set – LLM calls are unavailable")
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "openai/gpt-oss-20b"
        self.system_prompt = (
            "You are a helpful assistant. Answer using only the provided context. "
            "If the context does not contain the answer, say you don't know. "
            "Keep answers concise and mention which source chunk each fact came from."
        )

    def generate(self, question: str, context_chunks: List[dict]) -> str:
        # Build a simple context string that lists each chunk with its ID.
        context_str = "\n\n".join(
            f"[Chunk {c.get('chunk_id', i)}] {c.get('text', '')}" for i, c in enumerate(context_chunks)
        )
        user_content = f"Question: {question}\n\nContext:\n{context_str}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = httpx.post(self.endpoint, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        return answer.strip()
