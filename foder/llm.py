"""
LLM client — communicates with Ollama via HTTP.
Designed so the backend can be swapped by changing this module.
Supports both streaming and non-streaming modes.

Token tracking:
- Ollama returns prompt_eval_count and eval_count in the final streaming chunk.
- chat_stream() captures these and stores them in module-level counters.
- main.py reads _last_prompt_tokens and _last_response_tokens for /cost display.
"""

import httpx
import foder.config as config
from collections.abc import Iterator


class LLMError(Exception):
    pass


# ── Token counters — updated after every LLM call ────────────────────────────
# Ollama reports actual token counts in the done=true streaming chunk.
# These are real BPE token counts, not character estimates.

_last_prompt_tokens:   int = 0   # tokens sent in the prompt (context)
_last_response_tokens: int = 0   # tokens generated in the response

_session_prompt_tokens:   int = 0   # cumulative for the session
_session_response_tokens: int = 0   # cumulative for the session


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

    Timeout strategy (fixes hang-forever bug):
    - connect_timeout: 10s  — fail fast if Ollama isn't running
    - read_timeout:    per-token idle limit (LLM_TIMEOUT / 4, min 30s)
                       if Ollama stops sending tokens mid-response, we bail
    - pool_timeout:    10s  — connection pool wait
    The read timeout resets with each received token, so slow-but-alive
    models are fine. Only truly stalled streams are killed.
    """
    import json as _json
    import time

    # Per-token idle timeout: generous but bounded
    per_token_timeout = max(30.0, config.LLM_TIMEOUT / 4)

    timeout = httpx.Timeout(
        connect=10.0,
        read=per_token_timeout,
        write=10.0,
        pool=10.0,
    )

    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "keep_alive": "10m",
    }

    # Hard wall-clock deadline for the entire stream
    deadline = time.monotonic() + config.LLM_TIMEOUT

    try:
        with httpx.stream(
            "POST",
            f"{config.OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                # Hard deadline check — catches model that trickles tokens forever
                if time.monotonic() > deadline:
                    raise LLMError(
                        f"Request to Ollama timed out after {config.LLM_TIMEOUT:.0f}s "
                        "(wall-clock limit reached)."
                    )
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
                    # Capture real token counts from Ollama's final chunk
                    global _last_prompt_tokens, _last_response_tokens
                    global _session_prompt_tokens, _session_response_tokens
                    pt = data.get("prompt_eval_count", 0) or 0
                    rt = data.get("eval_count", 0) or 0
                    _last_prompt_tokens   = pt
                    _last_response_tokens = rt
                    _session_prompt_tokens   += pt
                    _session_response_tokens += rt
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
        raise LLMError(
            f"Ollama stopped responding (idle > {per_token_timeout:.0f}s). "
            "The model may be overloaded or the request too large."
        )


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


def get_token_stats() -> dict:
    """
    Return current token usage stats.
    Uses real counts from Ollama when available, falls back to 0.
    """
    return {
        "last_prompt":    _last_prompt_tokens,
        "last_response":  _last_response_tokens,
        "session_prompt":   _session_prompt_tokens,
        "session_response": _session_response_tokens,
        "session_total":    _session_prompt_tokens + _session_response_tokens,
    }


def reset_session_tokens() -> None:
    """Reset session-level token counters (call at session start)."""
    global _session_prompt_tokens, _session_response_tokens
    _session_prompt_tokens   = 0
    _session_response_tokens = 0
