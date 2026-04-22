"""
LLM client — communicates with Ollama via HTTP.
Designed so the backend can be swapped by changing this module.
Supports both streaming and non-streaming modes.
"""

import httpx
import foder.config as config
from collections.abc import Iterator


class LLMError(Exception):
    pass


def list_models() -> list[str]:
    """Query Ollama for all locally available models."""
    try:
        response = httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=10.0)
        response.raise_for_status()
    except httpx.ConnectError:
        raise LLMError(
            f"Cannot connect to Ollama at {config.OLLAMA_BASE_URL}. "
            "Is Ollama running? Try: ollama serve"
        )
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")

    models = response.json().get("models", [])
    return [m["name"] for m in models]


def chat(messages: list[dict]) -> str:
    """Send messages and return the full response string (non-streaming)."""
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }
    try:
        response = httpx.post(
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=config.LLM_TIMEOUT,
        )
        response.raise_for_status()
    except KeyboardInterrupt:
        raise LLMError("[interrupted]")
    except httpx.ConnectError:
        raise LLMError(
            f"Cannot connect to Ollama at {config.OLLAMA_BASE_URL}. "
            "Is Ollama running? Try: ollama serve"
        )
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")
    except httpx.TimeoutException:
        raise LLMError("Request to Ollama timed out.")

    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not content:
        raise LLMError(f"Empty response from model. Raw: {data}")
    return content


def chat_stream(messages: list[dict]) -> Iterator[str]:
    """
    Stream tokens from Ollama as they arrive.
    Yields string chunks. Raises LLMError on connection/HTTP failure.
    """
    import json as _json

    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "keep_alive": "10m",   # keep model in RAM for 10 min between requests
    }
    try:
        with httpx.stream(
            "POST",
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=config.LLM_TIMEOUT,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break
    except KeyboardInterrupt:
        return  # stop iteration cleanly
    except httpx.ConnectError:
        raise LLMError(
            f"Cannot connect to Ollama at {config.OLLAMA_BASE_URL}. "
            "Is Ollama running? Try: ollama serve"
        )
    except httpx.HTTPStatusError as e:
        raise LLMError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")
    except httpx.TimeoutException:
        raise LLMError("Request to Ollama timed out.")


def unload_model() -> None:
    """
    Tell Ollama to evict the current model from memory.
    Called on clean exit so RAM is freed immediately.
    Silently ignores errors — best effort only.
    """
    try:
        httpx.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={"model": config.OLLAMA_MODEL, "keep_alive": 0},
            timeout=5.0,
        )
    except Exception:
        pass
