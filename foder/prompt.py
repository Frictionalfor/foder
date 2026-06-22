"""
Prompt builder — constructs the system prompt for every LLM request.

The system prompt is built fresh on each call so:
- Workspace changes (cd) are always reflected.
- Memory updates (workspace memory, user instructions) are always current.
- Context engine results are injected when available.

Token budget:
- The system prompt is deliberately kept lean.
- Tool schemas are included but kept minimal.
- Memory is injected only if non-empty (saves tokens on clean projects).
- Project context is always injected (small, high-value).
"""

import json
import foder.config as config
from foder.tools.registry import TOOL_SCHEMAS

_TOOL_BLOCK = json.dumps(TOOL_SCHEMAS, indent=2)

# ── System prompt template ────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are Foder, a local AI coding agent. You act immediately — no explanations, no summaries unless asked.

WORKSPACE: {workspace}
{project_context}
{memory_block}
{git_context}
CORE RULES:
- To create/write a file → call file_write with COMPLETE working code immediately
- To modify part of a file → call file_read first, then file_edit (not file_write)
- To list files → call dir_list
- To run something → call shell_exec
- To search code → call grep_search
- To perform git operations → call git_tool
- NEVER show code in your response — always write it to a file first
- NEVER explain what you are about to do — just do it
- After completing a task, respond with ONE short sentence describing what was done
- If a task requires multiple files, call file_write multiple times in sequence

DIFF-BASED EDITING:
- Prefer file_edit over file_write when changing part of an existing file
- file_edit replaces old_str with new_str — old_str must match exactly once

TOOL FORMAT (JSON only, no markdown wrapper needed):
{{"tool": "<name>", "parameters": {{...}}}}

{custom_instructions}
AVAILABLE TOOLS:
{tools}
"""

# ── Git context helper ────────────────────────────────────────────────────────

def _get_git_context() -> str:
    """Return a compact git context string or empty string."""
    try:
        import subprocess as _sp
        branch = _sp.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(config.WORKSPACE), stderr=_sp.DEVNULL, timeout=2
        ).decode().strip()
        status = _sp.check_output(
            ["git", "status", "--short"],
            cwd=str(config.WORKSPACE), stderr=_sp.DEVNULL, timeout=2
        ).decode().strip()
        last = _sp.check_output(
            ["git", "log", "--oneline", "-1"],
            cwd=str(config.WORKSPACE), stderr=_sp.DEVNULL, timeout=2
        ).decode().strip()
        parts = [f"branch: {branch}"]
        if last:
            parts.append(f"last commit: {last}")
        if status:
            changed = len(status.splitlines())
            parts.append(f"changed files: {changed}")
        return "GIT: " + "  ".join(parts) + "\n"
    except Exception:
        return ""


def _get_project_context() -> str:
    """Return workspace context (project type, entry points, etc.)."""
    try:
        from foder.context import build_context_summary
        summary = build_context_summary()
        return summary + "\n"
    except Exception:
        return ""


def _get_memory_block() -> str:
    """Return workspace memory summary if non-empty."""
    try:
        from foder.memory import workspace_memory
        summary = workspace_memory().summary()
        if summary:
            return f"WORKSPACE MEMORY:\n{summary}\n"
    except Exception:
        pass
    return ""


# ── Public API ────────────────────────────────────────────────────────────────

def build_messages(history: list[dict]) -> list[dict]:
    """
    Build the complete message list for the LLM.
    Prepends a freshly constructed system prompt to the conversation history.
    """
    # Project context (cached lazily — fast on repeated calls)
    project_ctx = _get_project_context()
    git_ctx     = _get_git_context()
    memory_blk  = _get_memory_block()
    custom      = (
        f"PROJECT INSTRUCTIONS:\n{config.CUSTOM_INSTRUCTIONS}\n"
        if config.CUSTOM_INSTRUCTIONS else ""
    )

    system_content = _SYSTEM_TEMPLATE.format(
        workspace       = config.WORKSPACE,
        project_context = project_ctx,
        memory_block    = memory_blk,
        git_context     = git_ctx,
        tools           = _TOOL_BLOCK,
        custom_instructions = custom,
    )

    return [{"role": "system", "content": system_content}] + history


def build_planning_prompt(request: str, context_files: list[str] | None = None) -> str:
    """
    Build a structured planning prompt for /plan mode.
    Returns a string to be sent as the user message.
    """
    parts = [
        "PLANNING MODE — Analyze the following request and produce an implementation plan.\n",
        f"REQUEST: {request}\n",
        "Respond with:\n",
        "1. GOAL: one sentence describing what we're building\n",
        "2. FILES TO MODIFY: list of existing files that need changes\n",
        "3. FILES TO CREATE: list of new files needed\n",
        "4. STEPS: numbered implementation steps (keep each step small)\n",
        "5. RISKS: potential issues or edge cases\n",
        "6. ESTIMATED COMPLEXITY: low / medium / high\n",
    ]
    if context_files:
        parts.append(f"\nRELEVANT FILES:\n" + "\n".join(f"- {f}" for f in context_files))
    parts.append("\nDo NOT start implementing. Only produce the plan.")
    return "".join(parts)


def build_review_prompt(files_content: dict[str, str]) -> str:
    """
    Build a code review prompt for /review mode.
    files_content: {filename: content}
    """
    parts = [
        "CODE REVIEW MODE — Analyze the following code and produce an actionable report.\n\n",
        "Review for:\n",
        "- Bugs and logic errors\n",
        "- Security vulnerabilities\n",
        "- Performance issues\n",
        "- Code smells and maintainability issues\n",
        "- Missing error handling\n\n",
        "For each issue found:\n",
        "- Severity: critical / high / medium / low\n",
        "- File and line reference\n",
        "- Description of the problem\n",
        "- Suggested fix\n\n",
    ]
    for fname, content in files_content.items():
        parts.append(f"--- FILE: {fname} ---\n{content}\n--- END ---\n\n")
    return "".join(parts)


def build_explain_prompt(target: str, content: str, mode: str = "normal") -> str:
    """
    Build an explanation prompt for /explain mode.
    target: filename or function name
    content: file contents
    mode: "beginner" or "advanced" or "normal"
    """
    level = {
        "beginner":  "Use simple language. Explain concepts from scratch. Avoid jargon.",
        "advanced":  "Assume deep programming knowledge. Focus on architecture, trade-offs, and internals.",
        "normal":    "Use clear, professional language suitable for an experienced developer.",
    }.get(mode, "")

    return (
        f"EXPLAIN MODE — Explain the following code.\n\n"
        f"TARGET: {target}\n"
        f"STYLE: {level}\n\n"
        f"Explain:\n"
        f"1. What this code does (purpose)\n"
        f"2. How it works (key mechanisms)\n"
        f"3. Important design decisions\n"
        f"4. Any non-obvious behavior or gotchas\n\n"
        f"--- CODE ---\n{content}\n--- END ---"
    )
