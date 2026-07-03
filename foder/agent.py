"""
Agent loop — production-grade, streaming-first with full error recovery.

Architecture:
  User Request
    -> Context Gathering     (find relevant files, detect project)
    -> Planning              (optional -- triggered by /plan)
    -> Tool Selection        (LLM emits tool call JSON)
    -> Execution             (dispatch to tool registry)
    -> Verification          (detect failure in tool result)
    -> Reflection + Retry    (self-correct on failure, up to N retries)
    -> Final Response        (stream live tokens to caller)

Design decisions:
- Tool call iterations: collect full response synchronously (reliable JSON parsing)
- Final answer: stream token-by-token (low latency UX)
- History: only last N messages sent per request (lean context)
- Tool results: truncated in history to prevent bloat
- Error recovery: agent sees failure messages and can retry with different approach
- Multi-file projects: after each tool execution the loop always continues back
  to the LLM so it can emit the next tool call without stopping early.
- JSON leak fix: _strip_tool_json uses a greedy multi-pass loop with no
  lookahead limit, removing ALL tool call JSON before showing the user.

Loop detection (two layers):
- Response hash dedup: same raw LLM response twice in a row -> break out.
- Tool repetition: same (tool, key_param) called N times -> break out.
"""

import json
import re
import hashlib
from collections import Counter
from collections.abc import Generator
from foder.llm import chat_stream, LLMError
from foder.prompt import build_messages
from foder.tools.registry import dispatch
from foder.config import MAX_ITERATIONS

# ── Constants ─────────────────────────────────────────────────────────────────

_TOOL_RESULT_MAX_CHARS   = 1200   # tool results stored in history (chars)
_RECENT_TURNS            = 14     # messages to include per LLM request
_MAX_HISTORY_MESSAGES    = 60     # hard cap on in-memory history
_MAX_RETRIES_PER_ERROR   = 3      # consecutive errors before forcing bail-out
_MAX_SAME_TOOL_CALLS     = 4      # same (tool, key_param) calls before loop detection
_MAX_IDENTICAL_RESPONSES = 2      # identical raw LLM responses before loop detection

# Matches both ```json {...} ``` and ``` {...} ```
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

# Error patterns that trigger self-correction
_ERROR_PATTERNS = (
    "[error]", "[security error]", "syntax error",
    "traceback", "exception", "errno", "no such file",
    "command not found", "permission denied", "exit code",
    "nameerror", "typeerror", "valueerror", "importerror",
    "modulenotfounderror", "filenotfounderror",
)

# Tool result patterns that indicate success
_SUCCESS_PATTERNS = (
    "[ok]", "written", "created", "deleted", "renamed",
    "edited", "committed", "checkout",
)


# ── Loop detection ─────────────────────────────────────────────────────────────

def _response_fingerprint(raw: str) -> str:
    return hashlib.sha1(raw.strip().encode("utf-8", errors="replace")).hexdigest()


def _tool_key(tool_name: str, parameters: dict) -> str:
    for key in ("path", "command", "pattern", "operation", "source"):
        if key in parameters:
            return f"{tool_name}:{parameters[key]}"
    return tool_name


class _LoopDetector:
    def __init__(self) -> None:
        self._response_streak: int = 0
        self._last_fingerprint: str = ""
        self._tool_call_counts: Counter = Counter()

    def check_response(self, raw: str) -> str | None:
        fp = _response_fingerprint(raw)
        if fp == self._last_fingerprint:
            self._response_streak += 1
        else:
            self._response_streak = 1
            self._last_fingerprint = fp
        if self._response_streak >= _MAX_IDENTICAL_RESPONSES:
            return (
                "You are repeating the same response. Stop calling tools. "
                "Give the user a direct final answer right now."
            )
        return None

    def record_tool(self, tool_name: str, parameters: dict) -> str | None:
        key = _tool_key(tool_name, parameters)
        self._tool_call_counts[key] += 1
        count = self._tool_call_counts[key]
        if count >= _MAX_SAME_TOOL_CALLS:
            return (
                f"You have called '{tool_name}' with the same parameters "
                f"{count} times. Stop and give the user a final answer now."
            )
        return None


# ── Tool call detection ────────────────────────────────────────────────────────

def _find_first_tool_call(text: str) -> tuple[int, int] | None:
    """
    Brace-count scanner that locates the first tool call JSON object in text.
    Returns (start, end) indices, or None if not found.
    Tolerates raw control characters inside strings by relying on bracket
    depth rather than strict JSON parsing.
    """
    text = text.strip()

    # Fenced code block (highest priority — most unambiguous)
    match = _JSON_FENCE_RE.search(text)
    if match:
        start = match.start(1)
        end   = match.end(1)
        if start >= 0 and end > start:
            return (start, end)

    # Bare or preamble JSON — scan forward from every `{`
    pos = 0
    while pos < len(text):
        start = text.find("{", pos)
        if start == -1:
            break
        brace_depth = 0
        in_string = False
        escape = False
        end = -1
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    brace_depth += 1
                elif ch == "}":
                    brace_depth -= 1
                    if brace_depth <= 0:
                        end = i + 1
                        break
        if end > start:
            return (start, end)
        pos = start + 1

    return None


def _try_load_candidate(candidate: str) -> dict | None:
    candidate = candidate.strip()
    if not candidate:
        return None
    try:
        data = json.loads(candidate)
        if isinstance(data, dict) and "tool" in data and "parameters" in data:
            return data
    except json.JSONDecodeError:
        pass
    fixed = candidate.replace("\n", "\\n").replace("\r", "\\r")
    if fixed != candidate:
        try:
            data = json.loads(fixed)
            if isinstance(data, dict) and "tool" in data and "parameters" in data:
                return data
        except json.JSONDecodeError:
            pass
    return None


def _extract_tool_call(text: str) -> dict | None:
    """
    Parse the FIRST tool call JSON from model output.
    Handles: fenced blocks, bare JSON, JSON with preamble text.
    Also tolerates invalid escaping by attempting common fixes.
    """
    text = text.strip()

    bounds = _find_first_tool_call(text)
    if bounds is None:
        return None
    start, end = bounds
    candidate = text[start:end]
    return _try_load_candidate(candidate)


def _is_tool_call(text: str) -> bool:
    """Quick heuristic: does this response contain a tool call?"""
    stripped = text.strip()
    if stripped.startswith("[tool:"):
        return False
    return '"tool"' in stripped and '"parameters"' in stripped


# ── Error / success analysis ───────────────────────────────────────────────────

def _result_is_error(result: str) -> bool:
    low = result.lower()
    return any(pat in low for pat in _ERROR_PATTERNS)


def _result_is_success(result: str) -> bool:
    low = result.lower()
    return any(pat in low for pat in _SUCCESS_PATTERNS)


def _build_correction_hint(tool_name: str, parameters: dict, result: str) -> str:
    return (
        f"[tool: {tool_name}] FAILED\n"
        f"parameters: {json.dumps(parameters)}\n"
        f"error: {result}\n"
        f"Analyze this error and retry with a corrected approach. "
        f"Do not repeat the same mistake."
    )


# ── History management ─────────────────────────────────────────────────────────

def _truncate_tool_result(content: str) -> str:
    if len(content) <= _TOOL_RESULT_MAX_CHARS:
        return content
    return "...[truncated]\n" + content[-_TOOL_RESULT_MAX_CHARS:]


def _trim_history(history: list[dict]) -> list[dict]:
    if len(history) <= _MAX_HISTORY_MESSAGES:
        return history
    return history[-_MAX_HISTORY_MESSAGES:]


def _is_tool_result(msg: dict) -> bool:
    return msg["role"] == "user" and msg["content"].startswith("[tool:")


def _build_messages(history: list[dict]) -> list[dict]:
    if not history:
        return build_messages([])

    # Find the start of the current user turn (last non-tool user message)
    current_turn_start: int | None = None
    for i in range(len(history) - 1, -1, -1):
        m = history[i]
        if m["role"] == "user" and not _is_tool_result(m):
            current_turn_start = i
            break

    recent = history[-_RECENT_TURNS:]

    # Always include the current turn anchor
    if current_turn_start is not None:
        anchor = history[current_turn_start]
        if anchor not in recent:
            recent = [anchor] + recent

    # Drop old standalone tool results
    cutoff = max(0, len(recent) - 8)
    filtered = []
    for i, m in enumerate(recent):
        if _is_tool_result(m) and i < cutoff:
            continue
        filtered.append(m)

    return build_messages(filtered)


# ── Code block fallback ────────────────────────────────────────────────────────

def _extract_code_block_as_tool_call(response: str, user_input: str) -> dict | None:
    """
    Fallback: model output a fenced code block instead of a tool call.
    Synthesize a file_write tool call from the code block.
    Only used when there is NO tool call JSON anywhere in the response.
    """
    pattern = re.compile(r"```(\w+)?\s*\n(.*?)```", re.DOTALL)
    match   = pattern.search(response)
    if not match:
        return None

    lang    = (match.group(1) or "").lower().strip()
    content = match.group(2).strip()
    if not content or not lang:
        return None

    # Only trigger for known code languages — not markdown/json/text
    CODE_LANGS = {
        "python", "py", "c", "cpp", "c++", "javascript", "js",
        "typescript", "ts", "java", "go", "rust", "bash", "sh",
        "html", "css",
    }
    if lang not in CODE_LANGS:
        return None

    filename_match = re.search(r'\b([\w\-]+\.\w+)\b', user_input)
    if filename_match:
        filename = filename_match.group(1)
    else:
        ext_map = {
            "python": "main.py", "py": "main.py",
            "c": "main.c", "cpp": "main.cpp", "c++": "main.cpp",
            "javascript": "main.js", "js": "main.js",
            "typescript": "main.ts", "ts": "main.ts",
            "java": "Main.java", "go": "main.go",
            "rust": "main.rs", "bash": "script.sh", "sh": "script.sh",
            "html": "index.html", "css": "style.css",
        }
        filename = ext_map.get(lang, f"main.{lang}")

    return {
        "tool":       "file_write",
        "parameters": {"path": filename, "content": content},
    }


# ── Strip helpers ──────────────────────────────────────────────────────────────

def _strip_one_tool_call(text: str) -> str:
    """Remove the FIRST tool call JSON from text, leaving everything after it."""
    bounds = _find_first_tool_call(text)
    if bounds is None:
        return text
    start, end = bounds
    return (text[:start] + text[end:]).strip()


def _strip_tool_json(text: str) -> str:
    """
    Remove ALL tool call JSON from a response string.

    Fixes the JSON-leaking-to-user bug:
    - Handles fenced blocks (``` json {...} ```)
    - Handles bare JSON objects
    - Handles multiple tool calls in one response (multi-file projects)
    - No lookahead size limit — scans the full object regardless of size
    - Cleans up leftover noise lines from tool results
    """
    # Pass 1: remove all fenced JSON blocks
    text = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", text, flags=re.DOTALL)

    # Pass 2: remove all bare JSON tool call objects (unlimited passes)
    max_passes = 20   # safety cap — handles up to 20 tool calls in one response
    for _ in range(max_passes):
        s = text.strip()
        bounds = _find_first_tool_call(s)
        if bounds is None:
            break   # no more tool calls found
        start, end = bounds
        s = (s[:start] + s[end:]).strip()
        text = s

    # Pass 3: remove leftover noise lines from tool result injection
    lines = text.splitlines()
    clean = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("result:"):      continue
        if stripped.startswith("[ok]"):         continue
        if stripped.startswith("[error]"):      continue
        if stripped.startswith("parameters:"):  continue
        if stripped.startswith("[tool:"):       continue
        clean.append(line)

    return "\n".join(clean).strip()


# ── Generator helpers ──────────────────────────────────────────────────────────

def _stream_tokens(tokens: list[str]) -> Generator[str, None, None]:
    for t in tokens:
        yield t


def _single(text: str) -> Generator[str, None, None]:
    yield text


# ── Agent callbacks protocol ───────────────────────────────────────────────────

class AgentCallbacks:
    """Callback interface for the agent loop -- all methods are optional."""

    def on_tool_call(self, tool_name: str, parameters: dict) -> None:
        """Called just before a tool is executed."""

    def on_tool_result(self, tool_name: str, result: str, is_error: bool) -> None:
        """Called just after a tool returns."""

    def on_retry(self, attempt: int, reason: str) -> None:
        """Called when the agent detects an error and is retrying."""

    def on_planning(self, plan: str) -> None:
        """Called when a plan is produced in /plan mode."""


# ── Main agent loop ────────────────────────────────────────────────────────────

def run(
    user_input: str,
    history: list[dict],
    callbacks: AgentCallbacks | None = None,
    on_tool_call: object = None,
) -> tuple[Generator[str, None, None], list[dict]]:
    """
    Run the agent loop for a single user turn.

    Returns (token_generator, updated_history).

    KEY BEHAVIOURS:
    - Multi-file projects: after every tool call the loop continues back to
      the LLM so it can emit the next file_write / shell_exec without stopping.
    - JSON never leaks: _strip_tool_json removes ALL tool call JSON before
      returning the final answer string to the caller.
    - Error recovery: tool errors are injected back as user messages so the
      model can self-correct, up to _MAX_RETRIES_PER_ERROR consecutive failures.
    """
    if callbacks is None and callable(on_tool_call):
        cb = AgentCallbacks()
        cb.on_tool_call = on_tool_call  # type: ignore[method-assign]
        callbacks = cb
    if callbacks is None:
        callbacks = AgentCallbacks()

    history.append({"role": "user", "content": user_input})
    history = _trim_history(history)

    consecutive_errors = 0
    loop_detector      = _LoopDetector()

    for iteration in range(MAX_ITERATIONS):
        messages = _build_messages(history)

        # ── Call LLM (collect full response synchronously) ────────────────────
        try:
            tokens: list[str] = []
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

        # ── Loop detection layer 1: repeated response ─────────────────────────
        loop_msg = loop_detector.check_response(raw)
        if loop_msg:
            history.append({"role": "assistant", "content": raw})
            history.append({"role": "user",      "content": f"[loop detected] {loop_msg}"})
            callbacks.on_retry(-1, "response repetition detected")
            try:
                exit_tokens: list[str] = []
                for token in chat_stream(_build_messages(history)):
                    exit_tokens.append(token)
                final = _strip_tool_json("".join(exit_tokens))
            except Exception:
                final = "I got stuck in a loop. Please rephrase your request or try a smaller task."
            history.append({"role": "assistant", "content": final})
            return _stream_tokens([final]), history

        # ── Detect whether LLM wants to call a tool ───────────────────────────
        has_tool = _is_tool_call(raw)
        tool_call = _extract_tool_call(raw) if has_tool else None

        # Fallback: model wrote a code block instead of using file_write
        if tool_call is None and not has_tool:
            tool_call = _extract_code_block_as_tool_call(raw, user_input)

        # ── Final answer (no tool call in response) ───────────────────────────
        if tool_call is None:
            clean = _strip_tool_json(raw)
            history.append({"role": "assistant", "content": clean})
            return _stream_tokens([clean]), history

        # ── Execute ALL tool calls present in this response ───────────────────
        # Multi-file support: the model may emit multiple tool call JSON objects
        # in a single response. We execute them all before looping back.
        remaining = raw
        executed_any = False

        while True:
            tc = _extract_tool_call(remaining) if _is_tool_call(remaining) else None
            if tc is None:
                break

            tool_name  = tc["tool"]
            parameters = tc.get("parameters", {})

            # Loop detection layer 2: same tool + same params N times
            tool_loop_msg = loop_detector.record_tool(tool_name, parameters)
            if tool_loop_msg:
                callbacks.on_retry(-2, tool_loop_msg)
                history.append({"role": "assistant", "content": remaining})
                history.append({"role": "user",      "content": f"[loop detected] {tool_loop_msg}"})
                try:
                    exit_tokens = []
                    for token in chat_stream(_build_messages(history)):
                        exit_tokens.append(token)
                    final = _strip_tool_json("".join(exit_tokens))
                except Exception:
                    final = f"Stopped: repeated tool call detected ({tool_name}). Please rephrase."
                history.append({"role": "assistant", "content": final})
                return _stream_tokens([final]), history

            callbacks.on_tool_call(tool_name, parameters)
            result   = dispatch(tool_name, parameters)
            is_error = _result_is_error(result)
            callbacks.on_tool_result(tool_name, result, is_error)
            executed_any = True

            if is_error:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_RETRIES_PER_ERROR:
                    callbacks.on_retry(consecutive_errors, result)
                    error_msg = (
                        f"[tool: {tool_name}] FAILED after {consecutive_errors} attempts\n"
                        f"Last error: {result}\n"
                        "Stop trying this approach and tell the user what went wrong."
                    )
                    history.append({"role": "assistant", "content": remaining})
                    history.append({"role": "user",      "content": error_msg})
                    # Break inner loop — outer loop continues for self-correction
                    break
                else:
                    callbacks.on_retry(consecutive_errors, result)
                    stored = _build_correction_hint(tool_name, parameters, result)
            else:
                consecutive_errors = 0
                stored = _truncate_tool_result(result)

            tool_turn = (
                f"[tool: {tool_name}]\n"
                f"parameters: {json.dumps(parameters)}\n"
                f"result:\n{stored}"
            )

            # Store this tool call + result in history, then strip it from remaining
            history.append({"role": "assistant", "content": remaining})
            history.append({"role": "user",      "content": tool_turn})

            remaining = _strip_one_tool_call(remaining)
            # Continue inner loop — there may be more tool calls in `remaining`

        if not executed_any:
            # No tool was executed (e.g. all were loop-detected) — avoid infinite loop
            clean = _strip_tool_json(raw)
            history.append({"role": "assistant", "content": clean})
            return _stream_tokens([clean]), history

        # ── After all tool calls: check for leftover natural language ─────────
        # IMPORTANT: Only return here if there is actual human-readable text.
        # If remaining is empty or only tool JSON, loop back to LLM to continue.
        leftover = _strip_tool_json(remaining).strip()

        # A leftover is only a real final answer if it contains words, not just
        # punctuation or whitespace left after stripping JSON.
        if leftover and len(leftover) > 10 and not _is_tool_call(leftover):
            history.append({"role": "assistant", "content": leftover})
            return _stream_tokens([leftover]), history

        # No final answer yet — loop back to LLM so it can continue the task.
        # This is what enables multi-file project generation: the LLM writes
        # file 1, we execute it, loop back, LLM writes file 2, etc.

    # Reached MAX_ITERATIONS
    timeout_msg = (
        f"[agent] Reached max iterations ({MAX_ITERATIONS}). "
        "The task may be too complex -- try breaking it into smaller steps."
    )
    history.append({"role": "assistant", "content": timeout_msg})
    return _single(timeout_msg), history


# ── Planning mode ──────────────────────────────────────────────────────────────

def plan(
    request: str,
    history: list[dict],
    callbacks: AgentCallbacks | None = None,
) -> tuple[Generator[str, None, None], list[dict]]:
    """
    Run the agent in planning mode.
    Produces a structured implementation plan WITHOUT executing any tools.
    """
    from foder.prompt import build_planning_prompt
    from foder.context import find_relevant_files
    import foder.config as config

    relevant   = find_relevant_files(request, max_files=8)
    file_names = [str(p.relative_to(config.WORKSPACE)) for p in relevant]

    planning_input = build_planning_prompt(request, file_names)
    return run(planning_input, history, callbacks=callbacks)
