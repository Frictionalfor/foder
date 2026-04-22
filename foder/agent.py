"""
Agent loop - streaming-first with smart history management.

Design:
- Tool call iterations: collect full response synchronously (reliable JSON parsing)
- Final answer: stream tokens live to the caller (fast, responsive)
- History: only last 6 messages sent per request (keeps requests lean)
- Tool results: truncated to 500 chars in history (prevents bloat)
"""

import json
import re
from collections.abc import Iterator, Generator
from foder.llm import chat_stream, LLMError
from foder.prompt import build_messages
from foder.tools.registry import dispatch
from foder.config import MAX_ITERATIONS

# ── Constants ─────────────────────────────────────────────────────────────────

_TOOL_RESULT_MAX_CHARS = 500   # truncate tool results stored in history
_RECENT_TURNS          = 10    # messages to include per LLM request
_MAX_HISTORY_MESSAGES  = 40    # hard cap on in-memory history

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


# ── Tool call detection ───────────────────────────────────────────────────────

def _extract_tool_call(text: str) -> dict | None:
    """Parse a tool call JSON from model output. Handles fenced, bare, and indented JSON."""
    decoder = json.JSONDecoder()
    text    = text.strip()

    # Fenced code block
    match = _JSON_FENCE_RE.search(text)
    if match:
        try:
            data = json.loads(match.group(1))
            if "tool" in data and "parameters" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Bare or preamble JSON - find first { and decode forward
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


def _is_tool_call(text: str) -> bool:
    """Quick check - does this text contain a tool call?"""
    return '"tool"' in text and '"parameters"' in text


# ── History management ────────────────────────────────────────────────────────

def _truncate_tool_result(content: str) -> str:
    """Trim large tool results so they don't bloat future requests."""
    if len(content) <= _TOOL_RESULT_MAX_CHARS:
        return content
    return "...[truncated]\n" + content[-_TOOL_RESULT_MAX_CHARS:]


def _trim_history(history: list[dict]) -> list[dict]:
    if len(history) <= _MAX_HISTORY_MESSAGES:
        return history
    return history[-_MAX_HISTORY_MESSAGES:]


def _build_messages(history: list[dict]) -> list[dict]:
    """
    Send the system prompt + recent history to the LLM.
    Always includes the first user message of the current turn so the model
    never loses context of what it was asked to do.
    """
    if len(history) <= _RECENT_TURNS:
        return build_messages(history)

    recent = history[-_RECENT_TURNS:]

    # Always anchor with the original user request (first non-tool message)
    # so the model remembers the full task across multiple tool calls
    first_user = next(
        (m for m in history if m["role"] == "user" and not m["content"].startswith("[tool:")),
        None,
    )
    if first_user and first_user not in recent:
        recent = [first_user] + recent

    return build_messages(recent)


# ── Agent loop ────────────────────────────────────────────────────────────────

def run(
    user_input: str,
    history: list[dict],
    on_tool_call: callable = None,
) -> tuple[Generator[str, None, None], list[dict]]:
    """
    Run the agent loop for a single user turn.

    Returns (token_generator, updated_history).

    Tool call iterations collect the full response synchronously so JSON
    parsing is reliable. The final answer streams live token by token.
    """
    history.append({"role": "user", "content": user_input})
    history = _trim_history(history)

    for _ in range(MAX_ITERATIONS):
        messages = _build_messages(history)

        try:
            # Collect full response - needed to reliably detect tool calls
            tokens = []
            for token in chat_stream(messages):
                tokens.append(token)
            raw = "".join(tokens)
        except LLMError as e:
            msg = str(e)
            if "[interrupted]" in msg:
                history.append({"role": "assistant", "content": "[interrupted]"})
                return _single("cancelled"), history
            err = f"[llm error] {msg}"
            history.append({"role": "assistant", "content": err})
            return _single(err), history
        except KeyboardInterrupt:
            history.append({"role": "assistant", "content": "[interrupted]"})
            return _single("cancelled"), history

        # Check if this is a tool call
        tool_call = _extract_tool_call(raw) if _is_tool_call(raw) else None

        if tool_call is None:
            # Final answer - stream the collected tokens
            history.append({"role": "assistant", "content": raw})
            return _stream_tokens(tokens), history

        # Execute tool call
        tool_name  = tool_call["tool"]
        parameters = tool_call.get("parameters", {})

        if on_tool_call:
            on_tool_call(tool_name, parameters)

        result        = dispatch(tool_name, parameters)
        stored_result = _truncate_tool_result(result)

        tool_turn = (
            f"[tool: {tool_name}]\n"
            f"parameters: {json.dumps(parameters)}\n"
            f"result:\n{stored_result}"
        )

        history.append({"role": "assistant", "content": raw})
        history.append({"role": "user",      "content": tool_turn})

    timeout = f"[agent] Reached max iterations ({MAX_ITERATIONS})."
    history.append({"role": "assistant", "content": timeout})
    return _single(timeout), history


def _stream_tokens(tokens: list[str]) -> Generator[str, None, None]:
    """Yield pre-collected tokens one by one - simulates streaming for the UI."""
    for t in tokens:
        yield t


def _single(text: str) -> Generator[str, None, None]:
    yield text
