"""
Agent loop — single-pass streaming.

Each LLM call streams tokens. If the full response is a tool call JSON,
execute the tool and loop. Otherwise yield the tokens directly to the UI —
no second request, no wasted memory.
"""

import json
import re
from collections.abc import Iterator
from foder.llm import chat_stream, LLMError
from foder.prompt import build_messages
from foder.tools.registry import dispatch
from foder.config import MAX_ITERATIONS

_MAX_HISTORY_MESSAGES = 30  # tighter cap = less RAM

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_BARE_RE  = re.compile(r"\{[^{}]*\"tool\"\s*:\s*\"[^\"]+\"[^{}]*\"parameters\"\s*:\s*\{.*?\}\s*\}", re.DOTALL)

# No length cap — tool calls with large file content can be very long
_TOOL_CALL_MAX_LEN = None


def _extract_tool_call(text: str) -> dict | None:
    """
    Extract a tool call JSON from model output.
    Uses json.JSONDecoder.raw_decode to correctly handle nested structures
    and large file content payloads.
    """
    decoder = json.JSONDecoder()
    text = text.strip()

    # Try fenced block first
    match = _JSON_FENCE_RE.search(text)
    if match:
        try:
            data = json.loads(match.group(1))
            if "tool" in data and "parameters" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Scan for the first { and try to decode from there
    start = text.find("{")
    if start == -1:
        return None

    try:
        data, _ = decoder.raw_decode(text, start)
        if isinstance(data, dict) and "tool" in data and "parameters" in data:
            return data
    except json.JSONDecodeError:
        pass

    return None


def _trim_history(history: list[dict]) -> list[dict]:
    if len(history) <= _MAX_HISTORY_MESSAGES:
        return history
    return history[-_MAX_HISTORY_MESSAGES:]


def run(
    user_input: str,
    history: list[dict],
    on_tool_call: callable = None,
) -> tuple[Iterator[str], list[dict]]:
    """
    Run the agent loop for a single user turn.
    Returns (token_iterator, updated_history).
    The token_iterator streams the final answer — no double requests.
    """
    history.append({"role": "user", "content": user_input})
    history = _trim_history(history)

    for _ in range(MAX_ITERATIONS):
        messages = build_messages(history)

        try:
            tokens = list(_collect_stream(chat_stream(messages)))
        except LLMError as e:
            msg = str(e)
            if "[interrupted]" in msg:
                history.append({"role": "assistant", "content": "[interrupted]"})
                return _single("cancelled"), history
            error_msg = f"[llm error] {msg}"
            history.append({"role": "assistant", "content": error_msg})
            return _single(error_msg), history
        except KeyboardInterrupt:
            history.append({"role": "assistant", "content": "[interrupted]"})
            return _single("cancelled"), history

        raw_response = "".join(tokens)

        # Try tool call detection on every response — no length cap
        tool_call = _extract_tool_call(raw_response)

        if tool_call is None:
            # Final answer — stream the already-collected tokens
            history.append({"role": "assistant", "content": raw_response})
            return iter(tokens), history

        # Tool call
        tool_name  = tool_call["tool"]
        parameters = tool_call.get("parameters", {})

        if on_tool_call:
            on_tool_call(tool_name, parameters)

        tool_result = dispatch(tool_name, parameters)

        tool_turn = (
            f"[tool: {tool_name}]\n"
            f"parameters: {json.dumps(parameters)}\n"
            f"result:\n{tool_result}"
        )

        history.append({"role": "assistant", "content": raw_response})
        history.append({"role": "user",      "content": tool_turn})

        # Free the token list — no longer needed
        del tokens

    timeout_msg = f"[agent] Reached max iterations ({MAX_ITERATIONS})."
    history.append({"role": "assistant", "content": timeout_msg})
    return _single(timeout_msg), history


def _collect_stream(stream: Iterator[str]) -> Iterator[str]:
    """Pass-through iterator — yields tokens and lets KeyboardInterrupt propagate."""
    for token in stream:
        yield token


def _single(text: str) -> Iterator[str]:
    yield text
