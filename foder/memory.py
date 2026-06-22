"""
Memory system — three-layer persistence for Foder.

Layer 1 — Session Memory:    Current conversation (in-process list).
Layer 2 — Workspace Memory:  .foder/memory.json (project facts, decisions).
Layer 3 — User Preferences:  ~/.foder/preferences.json (model, theme, style).

Design goals:
- Zero mandatory dependencies (plain JSON, stdlib only).
- Thread-safe reads/writes via atomic file replacement.
- Graceful degradation: any layer can fail without crashing the agent.
"""

import json
import time
import tempfile
import os
from pathlib import Path
from typing import Any
import foder.config as config


# ── Atomic write helper ───────────────────────────────────────────────────────

def _atomic_write(path: Path, data: dict) -> None:
    """Write JSON atomically: write to tmp then rename (POSIX-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def _safe_read(path: Path) -> dict:
    """Read JSON file, return {} on any error."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


# ── Layer 2: Workspace Memory ─────────────────────────────────────────────────

class WorkspaceMemory:
    """
    Persistent project-level memory stored in <workspace>/.foder/memory.json.

    Stores:
    - project_facts: list of short fact strings the agent or user has noted
    - architecture_notes: free-form text about the project's design
    - important_decisions: timestamped decision log
    - user_instructions: standing instructions for this project
    """

    _MAX_FACTS       = 50
    _MAX_DECISIONS   = 30

    def __init__(self) -> None:
        self._path = config.WORKSPACE / ".foder" / "memory.json"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        self._data = _safe_read(self._path)

    def _save(self) -> None:
        try:
            _atomic_write(self._path, self._data)
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    def add_fact(self, fact: str) -> None:
        """Remember a project fact (deduplicates by content)."""
        facts: list = self._data.setdefault("project_facts", [])
        if fact not in facts:
            facts.append(fact)
            if len(facts) > self._MAX_FACTS:
                facts[:] = facts[-self._MAX_FACTS:]
            self._save()

    def remove_fact(self, fact: str) -> bool:
        facts: list = self._data.get("project_facts", [])
        if fact in facts:
            facts.remove(fact)
            self._save()
            return True
        return False

    def get_facts(self) -> list[str]:
        return list(self._data.get("project_facts", []))

    def set_architecture_notes(self, notes: str) -> None:
        self._data["architecture_notes"] = notes
        self._save()

    def get_architecture_notes(self) -> str:
        return self._data.get("architecture_notes", "")

    def add_decision(self, decision: str) -> None:
        """Log an important architectural decision with a timestamp."""
        decisions: list = self._data.setdefault("important_decisions", [])
        entry = {"ts": int(time.time()), "decision": decision}
        decisions.append(entry)
        if len(decisions) > self._MAX_DECISIONS:
            decisions[:] = decisions[-self._MAX_DECISIONS:]
        self._save()

    def get_decisions(self) -> list[dict]:
        return list(self._data.get("important_decisions", []))

    def set_instructions(self, instructions: str) -> None:
        """Set standing project-level instructions (replaces previous)."""
        self._data["user_instructions"] = instructions
        self._save()

    def get_instructions(self) -> str:
        return self._data.get("user_instructions", "")

    def clear(self) -> None:
        self._data = {}
        self._save()

    def summary(self) -> str:
        """Return a compact summary suitable for injection into the system prompt."""
        parts: list[str] = []
        facts = self.get_facts()
        if facts:
            parts.append("PROJECT FACTS:\n" + "\n".join(f"- {f}" for f in facts))
        notes = self.get_architecture_notes()
        if notes:
            parts.append(f"ARCHITECTURE:\n{notes}")
        instructions = self.get_instructions()
        if instructions:
            parts.append(f"STANDING INSTRUCTIONS:\n{instructions}")
        decisions = self.get_decisions()
        if decisions:
            recent = decisions[-5:]
            lines  = "\n".join(f"- {d['decision']}" for d in recent)
            parts.append(f"RECENT DECISIONS:\n{lines}")
        return "\n\n".join(parts)

    def refresh(self) -> None:
        """Re-read from disk (call after workspace changes)."""
        self._path = config.WORKSPACE / ".foder" / "memory.json"
        self._load()


# ── Layer 3: User Preferences ─────────────────────────────────────────────────

class UserPreferences:
    """
    Persistent user-level preferences stored in ~/.foder/preferences.json.

    Includes: preferred_model, coding_style, theme, formatting_preferences,
    and any arbitrary key-value pairs the user wants persisted.
    """

    _DEFAULTS: dict[str, Any] = {
        "preferred_model":         "qwen2.5-coder:3b",
        "theme":                   "green",
        "coding_style":            "",
        "formatting_preferences":  "",
        "auto_run_tests":          False,
        "stream_tool_output":      True,
        "diff_before_write":       False,
        "max_context_files":       10,
    }

    def __init__(self) -> None:
        self._path = config.PREFS_FILE
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        raw = _safe_read(self._path)
        self._data = {**self._DEFAULTS, **raw}

    def _save(self) -> None:
        try:
            _atomic_write(self._path, self._data)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def get_all(self) -> dict:
        return dict(self._data)

    def reset(self) -> None:
        self._data = dict(self._DEFAULTS)
        self._save()


# ── Module-level singletons (lazy-init on first access) ──────────────────────

_workspace_memory: WorkspaceMemory | None = None
_user_prefs: UserPreferences | None = None


def workspace_memory() -> WorkspaceMemory:
    """Get the workspace memory singleton (lazy init)."""
    global _workspace_memory
    if _workspace_memory is None:
        _workspace_memory = WorkspaceMemory()
    return _workspace_memory


def user_prefs() -> UserPreferences:
    """Get the user preferences singleton (lazy init)."""
    global _user_prefs
    if _user_prefs is None:
        _user_prefs = UserPreferences()
    return _user_prefs


def refresh_workspace() -> None:
    """
    Call this after the user changes directory so workspace memory
    reloads from the new workspace path.
    """
    global _workspace_memory
    _workspace_memory = WorkspaceMemory()
