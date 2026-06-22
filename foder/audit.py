"""
Audit log — lightweight action tracking for Foder.

Every tool call is logged to ~/.foder/audit.log with:
- ISO timestamp
- tool name
- key parameters (path or command, truncated)
- result status (ok / error / security_error)

Design:
- Append-only (never overwrites).
- Truncates to 10,000 lines automatically to prevent unbounded growth.
- Never raises — logging failure must never crash the agent.
- Log format: JSONL (one JSON object per line), easy to grep.
"""

import json
import time
from pathlib import Path
import foder.config as config

_MAX_LOG_LINES = 10_000


def _log_path() -> Path:
    return config.LOG_FILE


def log_action(
    tool_name: str,
    parameters: dict,
    result: str,
    workspace: str | None = None,
) -> None:
    """
    Append one audit entry to the log file.
    Silently ignores all errors.
    """
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Summarize parameters — avoid logging large file contents
        param_summary: dict = {}
        if "path" in parameters:
            param_summary["path"] = str(parameters["path"])[:200]
        if "command" in parameters:
            param_summary["command"] = str(parameters["command"])[:200]
        if "content" in parameters:
            content = parameters["content"]
            param_summary["content_bytes"] = len(content)
        # Include any other params (non-content)
        for k, v in parameters.items():
            if k not in ("path", "command", "content"):
                param_summary[k] = str(v)[:100]

        # Determine result status
        r_lower = (result or "").lower()
        if r_lower.startswith("[security error]"):
            status = "security_error"
        elif r_lower.startswith("[error]"):
            status = "error"
        elif r_lower.startswith("[ok]") or r_lower.startswith("[interrupted]"):
            status = "ok"
        else:
            status = "ok"

        entry = {
            "ts":         int(time.time()),
            "tool":       tool_name,
            "params":     param_summary,
            "status":     status,
            "workspace":  workspace or str(config.WORKSPACE),
        }

        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        _maybe_rotate(path)

    except Exception:
        pass  # audit failure must never crash the agent


def _maybe_rotate(path: Path) -> None:
    """Keep the log file under _MAX_LOG_LINES lines."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > _MAX_LOG_LINES:
            # Keep the most recent half
            keep = lines[len(lines) // 2:]
            path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    except Exception:
        pass


def read_recent(n: int = 20) -> list[dict]:
    """Return the n most recent audit entries as dicts."""
    path = _log_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
            if len(entries) >= n:
                break
        return list(reversed(entries))
    except Exception:
        return []
