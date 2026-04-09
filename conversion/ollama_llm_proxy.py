"""
Ollama LLM Proxy — drop-in replacement for llama_cpp.Llama.

Mimics the llama_cpp.Llama interface so deepmost's OpenSourceEmbeddings
can call Ollama instead of loading a local GGUF model.  This lets Ollama
manage GPU VRAM and swap between roleplay (Llama 3.1 8B) and conversion
analysis (Qwen3-4B) automatically.

Two call signatures are supported:
  1. __call__(prompt, ...)          → text completion  (used by analyze_metrics)
  2. create_chat_completion(...)    → chat completion   (used by generate_response)

Both are routed through Ollama's /api/chat endpoint, because Qwen3's
/no_think token (which disables expensive chain-of-thought reasoning)
only works via the chat template, not the raw generate endpoint.
"""

import logging
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OllamaLLMProxy:
    """
    Proxy that implements the llama_cpp.Llama interface but routes
    all inference calls to a running Ollama server via /api/chat.
    """

    def __init__(
        self,
        model: str = "qwen3:4b",
        base_url: str = "http://localhost:11434",
        keep_alive: str = "30s",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.keep_alive = keep_alive
        self._is_qwen3 = "qwen3" in model.lower()

    def _append_no_think(self, text: str) -> str:
        """Append /no_think for Qwen3 models to disable thinking mode."""
        if self._is_qwen3 and not text.rstrip().endswith("/no_think"):
            return text.rstrip() + " /no_think"
        return text

    def _call_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        stop: Optional[List[str]] = None,
    ) -> str:
        """Shared helper: call Ollama /api/chat and return the content string."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_gpu": 99,
            },
            "keep_alive": self.keep_alive,
        }
        if stop:
            payload["options"]["stop"] = stop

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    # ── Text completion (llama_cpp.__call__) ─────────────────────────

    def __call__(
        self,
        prompt: str,
        max_tokens: int = 450,
        temperature: float = 0.1,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Mimics llama_cpp.Llama.__call__() → text completion.

        Routed through /api/chat (not /api/generate) so Qwen3's
        /no_think token works correctly.

        deepmost calls:  self.llm(prompt, max_tokens=450, ...)
        expects:         {'choices': [{'text': '...'}]}
        """
        messages = [
            {"role": "user", "content": self._append_no_think(prompt)},
        ]

        try:
            text = self._call_chat(messages, max_tokens, temperature, stop)
            return {"choices": [{"text": text}]}
        except Exception as e:
            logger.error(f"OllamaLLMProxy text completion failed: {e}")
            return {"choices": [{"text": "{}"}]}

    # ── Chat completion (llama_cpp.create_chat_completion) ───────────

    def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 150,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Mimics llama_cpp.Llama.create_chat_completion().

        deepmost calls:  self.llm.create_chat_completion(messages=[...], ...)
        expects:         {'choices': [{'message': {'content': '...'}}]}
        """
        # Append /no_think to the last user message for Qwen3
        if self._is_qwen3 and messages:
            messages = list(messages)
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i] = {
                        **messages[i],
                        "content": self._append_no_think(messages[i]["content"]),
                    }
                    break

        try:
            content = self._call_chat(messages, max_tokens, temperature, stop)
            return {"choices": [{"message": {"content": content}}]}
        except Exception as e:
            logger.error(f"OllamaLLMProxy chat completion failed: {e}")
            return {"choices": [{"message": {"content": ""}}]}
