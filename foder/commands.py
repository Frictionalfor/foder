"""
Slash command implementations for Foder.

Each command is a standalone function that:
- Receives the full command string (including the slash command name)
- Has access to the console, history, config, and workspace
- Returns a string result or None (for commands that print directly)

Commands are registered in the COMMAND_MAP at the bottom of this file.
This module intentionally has no Rich imports — those live in main.py.
The functions return raw strings; main.py handles the rendering.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import foder.config as config


# ── /memory commands ──────────────────────────────────────────────────────────

def cmd_memory_show() -> str:
    """Show current workspace memory."""
    from foder.memory import workspace_memory
    wm = workspace_memory()
    parts: list[str] = []

    facts = wm.get_facts()
    if facts:
        parts.append("FACTS:\n" + "\n".join(f"  • {f}" for f in facts))

    notes = wm.get_architecture_notes()
    if notes:
        parts.append(f"ARCHITECTURE NOTES:\n  {notes}")

    instructions = wm.get_instructions()
    if instructions:
        parts.append(f"STANDING INSTRUCTIONS:\n  {instructions}")

    decisions = wm.get_decisions()
    if decisions:
        lines = []
        for d in decisions[-10:]:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(d["ts"]))
            lines.append(f"  [{ts}] {d['decision']}")
        parts.append("DECISIONS:\n" + "\n".join(lines))

    if not parts:
        return "Workspace memory is empty.\nUse /memory add <fact> to add project facts."
    return "\n\n".join(parts)


def cmd_memory_add(fact: str) -> str:
    """Add a fact to workspace memory."""
    from foder.memory import workspace_memory
    if not fact.strip():
        return "[error] Provide a fact to remember. Example: /memory add this project uses FastAPI"
    workspace_memory().add_fact(fact.strip())
    return f"[ok] Remembered: {fact.strip()}"


def cmd_memory_clear() -> str:
    """Clear all workspace memory."""
    from foder.memory import workspace_memory
    workspace_memory().clear()
    return "[ok] Workspace memory cleared."


def cmd_memory_notes(notes: str) -> str:
    """Set architecture notes."""
    from foder.memory import workspace_memory
    workspace_memory().set_architecture_notes(notes.strip())
    return "[ok] Architecture notes updated."


def cmd_memory_instructions(instructions: str) -> str:
    """Set standing project instructions."""
    from foder.memory import workspace_memory
    workspace_memory().set_instructions(instructions.strip())
    config.CUSTOM_INSTRUCTIONS = instructions.strip()
    return "[ok] Project instructions updated."


def cmd_memory_decide(decision: str) -> str:
    """Log an important decision."""
    from foder.memory import workspace_memory
    if not decision.strip():
        return "[error] Provide a decision description."
    workspace_memory().add_decision(decision.strip())
    return f"[ok] Decision logged: {decision.strip()}"


# ── /prefs commands ───────────────────────────────────────────────────────────

def cmd_prefs_show() -> str:
    """Show user preferences."""
    from foder.memory import user_prefs
    prefs = user_prefs().get_all()
    lines = [f"  {k}: {v}" for k, v in prefs.items()]
    return "USER PREFERENCES:\n" + "\n".join(lines)


def cmd_prefs_set(key: str, value: str) -> str:
    """Set a user preference."""
    from foder.memory import user_prefs
    if not key or not value:
        return "[error] Usage: /prefs set <key> <value>"
    # Attempt type coercion
    val: object = value
    if value.lower() in ("true", "yes"):
        val = True
    elif value.lower() in ("false", "no"):
        val = False
    elif value.isdigit():
        val = int(value)
    user_prefs().set(key, val)
    return f"[ok] Set {key} = {val}"


def cmd_prefs_reset() -> str:
    """Reset preferences to defaults."""
    from foder.memory import user_prefs
    user_prefs().reset()
    return "[ok] User preferences reset to defaults."


# ── /context command ──────────────────────────────────────────────────────────

def cmd_context() -> str:
    """Show detected project context."""
    from foder.context import detect_project, build_context_summary
    try:
        profile = detect_project()
        summary = build_context_summary()
        lines   = [
            f"PROJECT TYPE:    {', '.join(profile.project_type)}",
            f"PACKAGE MANAGER: {profile.package_manager}",
            f"TEST FRAMEWORK:  {profile.test_framework}",
            f"BUILD SYSTEM:    {profile.build_system}",
            f"LINTER:          {profile.linter}",
            f"FORMATTER:       {profile.formatter}",
            f"DOCKER:          {'yes' if profile.docker else 'no'}",
        ]
        if profile.entry_points:
            lines.append(f"ENTRY POINTS:    {', '.join(profile.entry_points)}")
        if profile.config_files:
            lines.append(f"CONFIG FILES:    {', '.join(profile.config_files)}")
        return "\n".join(lines)
    except Exception as e:
        return f"[error] Context detection failed: {e}"


# ── /audit command ────────────────────────────────────────────────────────────

def cmd_audit(n: int = 20) -> str:
    """Show recent audit log entries."""
    from foder.audit import read_recent
    entries = read_recent(n)
    if not entries:
        return "No audit entries yet."
    lines = []
    for e in entries:
        ts     = time.strftime("%H:%M:%S", time.localtime(e.get("ts", 0)))
        tool   = e.get("tool", "?")
        status = e.get("status", "?")
        params = e.get("params", {})
        hint   = params.get("path") or params.get("command", "")[:40] or ""
        lines.append(f"  {ts}  {tool:16s}  {status:14s}  {hint}")
    return "AUDIT LOG (recent):\n" + "\n".join(lines)


# ── /tools command ────────────────────────────────────────────────────────────

def cmd_tools() -> str:
    """List all available tools."""
    from foder.tools.registry import list_tools, get_schema
    lines = ["AVAILABLE TOOLS:\n"]
    for name in sorted(set(
        t for t in list_tools()
        # Skip aliases for display
        if not any(t == a for a in (
            "read_file", "write_file", "file_create", "create_file", "bash",
            "run", "mkdir", "list_dir", "grep", "search", "git", "ls",
            "read", "write", "exec", "rmdir", "edit_file", "patch_file",
            "rename_file", "move_file", "delete_file", "remove_file",
        ))
    )):
        schema = get_schema(name)
        if schema:
            desc = schema.get("description", "")[:60]
            lines.append(f"  {name:20s}  {desc}")
    return "\n".join(lines)


# ── /models enhanced ─────────────────────────────────────────────────────────

# Model capability hints (best-effort, kept in sync manually)
_MODEL_HINTS: dict[str, dict] = {
    "qwen2.5-coder:3b":  {"ctx": 32768, "ram": "~2GB",  "best_for": "fast everyday coding"},
    "qwen2.5-coder:7b":  {"ctx": 32768, "ram": "~4GB",  "best_for": "quality coding"},
    "qwen2.5-coder:14b": {"ctx": 32768, "ram": "~8GB",  "best_for": "complex tasks"},
    "qwen2.5-coder:32b": {"ctx": 32768, "ram": "~20GB", "best_for": "best quality"},
    "deepseek-coder:6.7b": {"ctx": 16384, "ram": "~4GB", "best_for": "code generation"},
    "deepseek-coder:33b":  {"ctx": 16384, "ram": "~20GB","best_for": "expert coding"},
    "codellama:7b":        {"ctx": 16384, "ram": "~4GB", "best_for": "code completion"},
    "codellama:13b":       {"ctx": 16384, "ram": "~8GB", "best_for": "code tasks"},
    "llama3.1:8b":         {"ctx": 131072,"ram": "~5GB", "best_for": "general tasks"},
    "llama3.1:70b":        {"ctx": 131072,"ram": "~40GB","best_for": "best general"},
    "mistral:7b":          {"ctx": 32768, "ram": "~4GB", "best_for": "fast general"},
    "phi3:mini":           {"ctx": 128000,"ram": "~2GB", "best_for": "lightweight tasks"},
    "phi3:medium":         {"ctx": 128000,"ram": "~8GB", "best_for": "capable + lean"},
}


def get_model_hint(model_name: str) -> dict:
    """Return capability hints for a model name (prefix match)."""
    name = model_name.lower()
    # Exact match first
    if name in _MODEL_HINTS:
        return _MODEL_HINTS[name]
    # Prefix match
    for key, val in _MODEL_HINTS.items():
        if name.startswith(key.split(":")[0]):
            return val
    return {}


# ── /skills commands ──────────────────────────────────────────────────────────

def cmd_skills_list() -> str:
    """List all available skills."""
    from foder.skills import skills_summary
    return skills_summary()


def cmd_skills_show(name: str) -> str:
    """Show details of a specific skill."""
    from foder.skills import load_skill
    skill = load_skill(name.strip())
    if not skill:
        return f"[error] Skill '{name}' not found. Run /skills list to see available skills."
    lines = [
        f"NAME:        {skill.get('name','')}",
        f"VERSION:     {skill.get('version','')}",
        f"DESCRIPTION: {skill.get('description','')}",
        f"TAGS:        {', '.join(skill.get('tags',[]))}",
        f"KEYWORDS:    {', '.join(skill.get('intent_keywords',[]))}",
        "",
        "STEPS:",
    ]
    for i, step in enumerate(skill.get("steps", []), 1):
        lines.append(f"  {i}. {step}")
    lines.append("")
    lines.append("BEST PRACTICES:")
    for p in skill.get("best_practices", []):
        lines.append(f"  • {p}")
    return "\n".join(lines)


def cmd_skills_detect(user_input: str) -> str:
    """Show which skill would be auto-detected for a given input."""
    from foder.skills import detect_skill
    skill = detect_skill(user_input)
    if not skill:
        return f"No skill detected for: '{user_input}'"
    return f"Detected skill: {skill['name']}\n{skill.get('description','')}"


# ── Command registry ──────────────────────────────────────────────────────────

COMMANDS: dict[str, str] = {
    # Existing commands
    "/models":    "list available Ollama models",
    "/switch":    "switch model  [/switch <name>]",
    "/model":     "show active model",
    "/theme":     "change color theme",
    "/clear":     "clear screen + history",
    "/workspace": "show workspace info",
    "/last":      "show last response",
    "/undo":      "revert last file write",
    "/diff":      "diff of last file write",
    "/run":       "auto-detect and run project",
    "/git":       "show git status",
    "/pin":       "pin a file to every prompt  [/pin <file>]",
    "/unpin":     "remove pinned file  [/unpin <file>]",
    "/pins":      "list pinned files",
    "/snapshot":  "snapshot workspace  [/snapshot diff]",
    "/cost":      "show session stats",
    "/arch":      "show architecture diagram",
    "/help":      "show this help",
    "/exit":      "quit foder",
    # Agent mode commands
    "/plan":      "plan before executing  [/plan <request>]",
    "/review":    "code review current file or dir  [/review <path>]",
    "/explain":   "explain code  [/explain <file> [beginner|advanced]]",
    "/auto":      "autonomous mode  [/auto <task>]",
    "/build":     "generate complete project  [/build <description>]",
    "/chat":      "lightweight Q&A mode  [/chat <question>]",
    "/test":      "run project test suite  [/test [path]]",
    "/refactor":  "targeted refactor with diff preview  [/refactor <file>]",
    "/watch":     "watch files and trigger agent on save  [/watch [pattern]]",
    "/compress":  "summarize + compress conversation context",
    "/history":   "search prompt history  [/history [query]]",
    # Skills
    "/skills":    "manage skills  [/skills list|use|show|detect]",
    # Workspace
    "/context":   "show detected project context",
    "/memory":    "manage workspace memory  [/memory add|show|clear|notes|decide]",
    "/prefs":     "manage user preferences  [/prefs show|set|reset]",
    "/tools":     "list all available tools",
    "/audit":     "show recent audit log",
    "/index":     "show workspace file index",
    "/doctor":    "system health check",
}


# ── /test command ─────────────────────────────────────────────────────────────

# Maps detected test framework -> (run command, failure signal strings)
_TEST_RUNNERS: dict[str, tuple[str, list[str]]] = {
    "pytest":    ("python -m pytest -v --tb=short", ["FAILED", "ERROR", "error"]),
    "unittest":  ("python -m unittest discover -v",  ["FAIL", "ERROR"]),
    "jest":      ("npx jest --no-coverage",           ["FAIL", "Tests failed"]),
    "vitest":    ("npx vitest run",                   ["FAIL", "Tests failed"]),
    "go test":   ("go test ./...",                    ["FAIL", "--- FAIL"]),
    "cargo test":("cargo test",                       ["FAILED", "test result: FAILED"]),
    "cargo":     ("cargo test",                       ["FAILED"]),
}


def cmd_test(target: str = "") -> tuple[str, bool]:
    """
    Auto-detect and run the project's test suite.
    Returns (output_text, had_failures).
    """
    from foder.context import detect_project
    import subprocess
    import foder.config as cfg

    ws = cfg.WORKSPACE

    profile   = detect_project(ws)
    framework = profile.test_framework.lower()

    # Find the best runner
    runner, fail_signals = None, []
    for key, (cmd, sigs) in _TEST_RUNNERS.items():
        if key in framework:
            runner, fail_signals = cmd, sigs
            break

    if runner is None:
        # Fallback: try pytest if any .py files exist
        py_files = list(ws.glob("**/*.py"))
        if py_files:
            runner, fail_signals = _TEST_RUNNERS["pytest"]
        else:
            return "[test] Could not detect test framework. Try: /test pytest", False

    # If target path specified, append to runner
    if target.strip():
        runner = f"{runner} {target.strip()}"

    cwd = ws
    # For jest/vitest, run from directory containing package.json
    if "jest" in runner or "vitest" in runner:
        pkg = ws / "package.json"
        if not pkg.exists():
            # walk up
            for p in ws.parents:
                if (p / "package.json").exists():
                    cwd = p
                    break

    try:
        result = subprocess.run(
            runner,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output   = result.stdout + result.stderr
        rc       = result.returncode
        failures = rc != 0 or any(sig in output for sig in fail_signals)
        return output, failures
    except subprocess.TimeoutExpired:
        return "[test] Test run timed out after 120s. Use /test with a specific path to narrow scope.", True
    except Exception as e:
        return f"[test] Failed to run tests: {e}", True


# ── /doctor command ───────────────────────────────────────────────────────────

def cmd_doctor() -> str:
    """
    System health check — Python, Ollama, PATH, ~/.foder, models.
    Returns a structured report string.
    """
    import subprocess
    import shutil
    import sys
    import foder.config as cfg

    lines: list[str] = ["FODER SYSTEM HEALTH CHECK\n"]

    def check(label: str, ok: bool, detail: str = "") -> None:
        status = "[OK]  " if ok else "[FAIL]"
        lines.append(f"  {status}  {label}{('  -- ' + detail) if detail else ''}")

    # Python version
    major, minor = sys.version_info.major, sys.version_info.minor
    check(
        f"Python {major}.{minor}",
        major == 3 and minor >= 10,
        "3.10+ required" if not (major == 3 and minor >= 10) else sys.executable,
    )

    # pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=5
        )
        check("pip", result.returncode == 0, result.stdout.split()[1] if result.returncode == 0 else "not found")
    except Exception:
        check("pip", False, "not found")

    # foder binary in PATH
    foder_path = shutil.which("foder")
    check("foder in PATH", foder_path is not None, foder_path or "run: pip install -e .")

    # ~/.foder directory
    user_dir = cfg.USER_DIR
    check("~/.foder/ exists", user_dir.exists(), str(user_dir))
    skills_dir = user_dir / "skills"
    if not skills_dir.exists():
        try:
            skills_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / "sessions").mkdir(parents=True, exist_ok=True)
            check("~/.foder/skills/ created", True, str(skills_dir))
        except Exception as e:
            check("~/.foder/skills/ exists", False, str(e))
    else:
        check("~/.foder/skills/ exists", True, str(skills_dir))

    # Workspace
    check("Workspace readable", cfg.WORKSPACE.exists(), str(cfg.WORKSPACE))

    # Ollama process
    ollama_bin = shutil.which("ollama")
    check("ollama in PATH", ollama_bin is not None, ollama_bin or "install from https://ollama.com")

    if ollama_bin:
        # Ollama API reachable
        try:
            import httpx
            resp = httpx.get(f"{cfg.OLLAMA_BASE_URL}/api/tags", timeout=4.0)
            models = [m["name"] for m in resp.json().get("models", [])]
            check(
                "Ollama API",
                True,
                f"{cfg.OLLAMA_BASE_URL}  ({len(models)} model(s) available)",
            )
            # Active model — also show what's actually installed
            model_ok = cfg.OLLAMA_MODEL in models
            # Downgrade to WARN if model isn't pulled but another model is available
            # (Foder auto-selects at startup so it still works)
            if not model_ok and models:
                lines.append(
                    f"  [WARN]  Model '{cfg.OLLAMA_MODEL}' not pulled"
                    f"  -- run: ollama pull {cfg.OLLAMA_MODEL}"
                )
                lines.append(f"  [INFO] Auto-using: {models[0]}  (works fine)")
            else:
                check(f"Model '{cfg.OLLAMA_MODEL}'", model_ok, "READY")
            if models:
                lines.append("")
                lines.append("  Available models:")
                for m in models[:10]:
                    lines.append(f"    - {m}")
                if len(models) > 10:
                    lines.append(f"    ... and {len(models) - 10} more")
        except Exception as e:
            check("Ollama API", False, f"not reachable at {cfg.OLLAMA_BASE_URL} -- run: ollama serve")
    else:
        check("Ollama API", False, "ollama not in PATH")

    # Git
    git_bin = shutil.which("git")
    check("git in PATH", git_bin is not None, git_bin or "optional but recommended")

    # Config file
    foder_json = cfg.WORKSPACE / "foder.json"
    if foder_json.exists():
        check("foder.json", True, str(foder_json))
    else:
        lines.append("  [INFO] No foder.json in workspace  (run: foder init)")

    lines.append("")
    failures = sum(1 for l in lines if "[FAIL]" in l)
    warnings = sum(1 for l in lines if "[WARN]" in l)
    if failures == 0 and warnings == 0:
        lines.append("  All checks passed. Foder is healthy.")
    elif failures == 0:
        lines.append(f"  {warnings} warning(s). Foder is functional -- see [WARN] items above.")
    else:
        lines.append(f"  {failures} issue(s) found. Fix the [FAIL] items above.")

    return "\n".join(lines)


# ── /compress command ─────────────────────────────────────────────────────────

def cmd_compress_prompt(history: list[dict]) -> str:
    """
    Build a prompt asking the LLM to compress the conversation history.
    Returns the compression prompt to run through the agent.
    """
    user_turns = [
        m["content"] for m in history
        if m["role"] == "user" and not m["content"].startswith("[tool:")
    ]
    assistant_turns = [
        m["content"] for m in history
        if m["role"] == "assistant"
    ]
    combined = "\n\n".join(
        f"USER: {u}\nASSISTANT: {a}"
        for u, a in zip(user_turns[-10:], assistant_turns[-10:])
    )
    return (
        "COMPRESS MODE: Summarize this conversation into a compact context block.\n\n"
        "Rules:\n"
        "- Keep: all technical decisions, file names, code structure choices, errors encountered\n"
        "- Keep: the current task and what has been completed\n"
        "- Drop: pleasantries, repeated context, verbose explanations\n"
        "- Output format: bullet points, max 300 words\n"
        "- Start with: CONTEXT SUMMARY:\n\n"
        f"CONVERSATION:\n{combined}\n\n"
        "Produce the summary now."
    )


# ── /history command ──────────────────────────────────────────────────────────

def cmd_history_search(query: str = "", limit: int = 30) -> str:
    """
    Search the persistent prompt history file (~/.foder/history.jsonl).
    Returns formatted results.
    """
    import foder.config as cfg
    history_file = cfg.HISTORY_FILE

    if not history_file.exists():
        return "No history yet. History is saved as you use foder."

    entries: list[dict] = []
    try:
        for line in history_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    except Exception as e:
        return f"[error] Could not read history: {e}"

    if not entries:
        return "History file is empty."

    query_lower = query.lower().strip()
    if query_lower:
        entries = [
            e for e in entries
            if query_lower in e.get("prompt", "").lower()
        ]

    # Most recent first
    entries = entries[-limit:][::-1]

    if not entries:
        return f"No history matches '{query}'."

    lines = [f"HISTORY ({len(entries)} entries{f'  filter: {query}' if query else ''}):\n"]
    for e in entries:
        ts    = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("ts", 0)))
        prompt = e.get("prompt", "")[:80]
        if len(e.get("prompt", "")) > 80:
            prompt += "..."
        lines.append(f"  {ts}  {prompt}")
    return "\n".join(lines)


def cmd_history_append(prompt: str) -> None:
    """Append a prompt to the persistent history file."""
    import foder.config as cfg
    history_file = cfg.HISTORY_FILE
    try:
        history_file.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({"ts": int(time.time()), "prompt": prompt}, ensure_ascii=False)
        with history_file.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass


# ── /chat mode ────────────────────────────────────────────────────────────────

CHAT_MODE_SYSTEM = """\
You are Foder in lightweight chat mode.
Answer questions directly and concisely.
Do NOT call any tools.
Do NOT write files.
Do NOT execute commands.
Just answer the question in plain text.
Keep responses short unless the question requires detail.
"""

def build_chat_messages(question: str, history: list[dict]) -> list[dict]:
    """Build messages for /chat mode — no tools, no system context overhead."""
    recent = [
        m for m in history[-6:]
        if not m["content"].startswith("[tool:")
    ]
    return [
        {"role": "system",    "content": CHAT_MODE_SYSTEM},
        *recent,
        {"role": "user",      "content": question},
    ]


# ── /refactor support ─────────────────────────────────────────────────────────

def build_refactor_prompt(filename: str, content: str, instruction: str) -> str:
    """
    Build the refactor prompt that returns only diff-based edits.
    The agent must use file_edit (str-replace) not file_write.
    """
    return (
        f"REFACTOR MODE for: {filename}\n\n"
        f"INSTRUCTION: {instruction if instruction else 'Improve code quality, readability, and structure.'}\n\n"
        "RULES (follow strictly):\n"
        "- Use file_edit tool with old_str/new_str — do NOT rewrite the entire file\n"
        "- Make targeted, minimal changes only\n"
        "- Preserve all existing functionality\n"
        "- Each edit must have a clear reason\n"
        "- After all edits, confirm what changed and why\n\n"
        f"--- FILE: {filename} ---\n"
        f"{content}\n"
        "--- END ---\n\n"
        "Begin refactoring now using file_edit calls."
    )


# ── /watch mode support ───────────────────────────────────────────────────────

def build_watch_trigger_prompt(filepath: str, event: str) -> str:
    """
    Build the agent prompt triggered by a file change in /watch mode.
    """
    return (
        f"[WATCH TRIGGER] File {event}: {filepath}\n\n"
        "Analyze what changed. If there are obvious issues (syntax errors, "
        "broken imports, test failures), fix them. "
        "If the change looks intentional and correct, confirm it briefly. "
        "Keep the response short — you are running in watch mode."
    )
