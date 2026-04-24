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
    """Quick check - does this look like a tool call JSON (not a tool result)?"""
    # Tool results start with "[tool:" — exclude them
    stripped = text.strip()
    if stripped.startswith("[tool:"):
        return False
    return '"tool"' in stripped and '"parameters"' in stripped


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


def _is_tool_result(msg: dict) -> bool:
    """True if this message is a tool result injected by the agent loop."""
    return msg["role"] == "user" and msg["content"].startswith("[tool:")


def _build_messages(history: list[dict]) -> list[dict]:
    """
    Build the message list for the LLM.
    - Takes the last _RECENT_TURNS messages
    - Strips standalone tool result messages that are older than 2 turns
      (they bloat context and confuse the model)
    - Always anchors the original user request of the CURRENT turn
    """
    if not history:
        return build_messages([])

    # Find the start of the current user turn (last non-tool user message)
    current_turn_start = None
    for i in range(len(history) - 1, -1, -1):
        m = history[i]
        if m["role"] == "user" and not _is_tool_result(m):
            current_turn_start = i
            break

    # Take recent messages
    recent = history[-_RECENT_TURNS:]

    # Ensure the current turn's user message is always included
    if current_turn_start is not None:
        anchor = history[current_turn_start]
        if anchor not in recent:
            recent = [anchor] + recent

    # Filter out old tool results that are not part of the current tool chain
    # Keep tool results only from the last 4 messages (current tool call chain)
    cutoff = max(0, len(recent) - 4)
    filtered = []
    for i, m in enumerate(recent):
        if _is_tool_result(m) and i < cutoff:
            continue  # drop old tool results
        filtered.append(m)

    return build_messages(filtered)


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
            # Check if model output a fenced code block instead of a tool call
            # This happens when the model explains instead of acting
            auto_tc = _extract_code_block_as_tool_call(raw, user_input)
            if auto_tc:
                tool_call = auto_tc

        if tool_call is None:
            # Final answer - clean up any leaked tool call JSON before displaying
            clean = _strip_tool_json(raw)
            history.append({"role": "assistant", "content": clean})
            return _stream_tokens([clean]), history

        # Execute ALL tool calls found in this response (model sometimes batches them)
        remaining = raw
        executed  = 0
        while True:
            tc = _extract_tool_call(remaining) if _is_tool_call(remaining) else None
            if tc is None:
                break

            tool_name  = tc["tool"]
            parameters = tc.get("parameters", {})

            if on_tool_call:
                on_tool_call(tool_name, parameters)

            result        = dispatch(tool_name, parameters)
            stored_result = _truncate_tool_result(result)

            tool_turn = (
                f"[tool: {tool_name}]\n"
                f"parameters: {json.dumps(parameters)}\n"
                f"result:\n{stored_result}"
            )

            history.append({"role": "assistant", "content": remaining})
            history.append({"role": "user",      "content": tool_turn})
            executed += 1

            # Strip the executed tool call from remaining text and check for more
            remaining = _strip_one_tool_call(remaining)
            if not remaining.strip() or not _is_tool_call(remaining):
                break

        # If there's leftover plain text after all tool calls, that's the final answer
        leftover = _strip_tool_json(remaining).strip()
        if leftover:
            history.append({"role": "assistant", "content": leftover})
            return _stream_tokens([leftover]), history

        # Otherwise loop back to get the model's final response

    timeout = f"[agent] Reached max iterations ({MAX_ITERATIONS})."
    history.append({"role": "assistant", "content": timeout})
    return _single(timeout), history


def _extract_code_block_as_tool_call(response: str, user_input: str) -> dict | None:
    """
    Fallback: if the model outputs a fenced code block instead of a tool call,
    extract the code and synthesize a file_write tool call.
    Infers the filename from the user's request or the code language.
    """
    # Find a fenced code block with a language tag
    pattern = re.compile(r"```(\w+)?\s*\n(.*?)```", re.DOTALL)
    match   = pattern.search(response)
    if not match:
        return None

    lang    = (match.group(1) or "").lower().strip()
    content = match.group(2).strip()

    if not content or not lang:
        return None

    # Try to extract filename from user input
    # e.g. "make a C file called swap.c" -> "swap.c"
    filename_match = re.search(r'\b([\w\-]+\.\w+)\b', user_input)
    if filename_match:
        filename = filename_match.group(1)
    else:
        # Infer from language
        ext_map = {
            'python': 'main.py', 'py': 'main.py',
            'c': 'main.c', 'cpp': 'main.cpp', 'c++': 'main.cpp',
            'javascript': 'main.js', 'js': 'main.js',
            'typescript': 'main.ts', 'ts': 'main.ts',
            'java': 'Main.java', 'go': 'main.go',
            'rust': 'main.rs', 'bash': 'script.sh', 'sh': 'script.sh',
            'html': 'index.html', 'css': 'style.css',
        }
        filename = ext_map.get(lang, f'main.{lang}')

    return {
        "tool": "file_write",
        "parameters": {"path": filename, "content": content}
    }


def _strip_one_tool_call(text: str) -> str:
    """Remove only the first tool call JSON from text, leaving the rest."""
    # Remove first fenced block
    import re as _re
    m = _re.search(r"```(?:json)?\s*\{.*?\}\s*```", text, flags=_re.DOTALL)
    if m:
        return (text[:m.start()] + text[m.end():]).strip()
    # Remove first bare JSON tool call
    decoder = json.JSONDecoder()
    s = text.strip()
    start = s.find("{")
    if start == -1:
        return text
    try:
        _, end = decoder.raw_decode(s, start)
        return (s[:start] + s[end:]).strip()
    except json.JSONDecodeError:
        return text


def _strip_tool_json(text: str) -> str:
    """
    Remove ALL tool call JSON and tool result noise from a response.
    Leaves only the human-readable final message.
    """
    import re as _re

    # Remove fenced JSON blocks
    text = _re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=_re.DOTALL)

    # Remove bare JSON tool calls (loop until none left)
    decoder = json.JSONDecoder()
    for _ in range(20):
        s = text.strip()
        idx = s.find("{")
        if idx == -1:
            break
        # Only strip if it looks like a tool call
        snippet = s[idx:idx+300]
        if '"tool"' not in snippet or '"parameters"' not in snippet:
            break
        try:
            _, end = decoder.raw_decode(s, idx)
            text = (s[:idx] + s[end:]).strip()
        except json.JSONDecodeError:
            break

    # Remove leftover tool result lines: "result:", "[ok] ...", "parameters: ..."
    lines = text.splitlines()
    clean = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("result:"):       continue
        if stripped.startswith("[ok]"):          continue
        if stripped.startswith("[error]"):       continue
        if stripped.startswith("parameters:"):  continue
        if stripped.startswith("[tool:"):        continue
        clean.append(line)

    return "\n".join(clean).strip()


def _stream_tokens(tokens: list[str]) -> Generator[str, None, None]:
    """Yield pre-collected tokens one by one."""
    for t in tokens:
        yield t


def _single(text: str) -> Generator[str, None, None]:
    yield text
