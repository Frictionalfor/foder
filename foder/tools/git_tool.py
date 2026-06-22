"""
git_tool — Git operations for Foder.

Supported operations:
- status:   working tree status
- diff:     show changes (staged or unstaged)
- log:      recent commit history
- branch:   list branches
- add:      stage files
- commit:   create a commit with a message
- checkout: switch branch or restore file

All operations are scoped to the current workspace.
Destructive operations (reset --hard, branch -D, force push) are not exposed.
"""

import subprocess
from pathlib import Path
import foder.config as config
from foder.security import SecurityError

SCHEMA = {
    "name": "git_tool",
    "description": (
        "Run Git operations in the workspace. "
        "Supported operations: status, diff, log, branch, add, commit, checkout."
    ),
    "parameters": {
        "operation": {
            "type": "string",
            "description": (
                "Git operation to perform. "
                "One of: status, diff, log, branch, add, commit, checkout."
            ),
        },
        "args": {
            "type": "string",
            "description": (
                "Additional arguments for the operation. "
                "For 'add': file path or '.' for all. "
                "For 'commit': commit message. "
                "For 'checkout': branch name or file path. "
                "For 'log': number of commits (default 5). "
                "For 'diff': optional file path."
            ),
            "default": "",
        },
    },
    "required": ["operation"],
}

_ALLOWED_OPS = {"status", "diff", "log", "branch", "add", "commit", "checkout"}
_MAX_OUTPUT  = 4000


def execute(operation: str, args: str = "") -> str:
    op = operation.strip().lower()
    if op not in _ALLOWED_OPS:
        return (
            f"[error] Unknown git operation: '{operation}'. "
            f"Allowed: {', '.join(sorted(_ALLOWED_OPS))}"
        )

    ws = config.WORKSPACE

    if op == "status":
        return _run_git(ws, ["git", "status", "--short", "--branch"])

    elif op == "diff":
        cmd = ["git", "diff", "--stat"]
        if args.strip():
            cmd.append("--")
            cmd.append(args.strip())
        return _run_git(ws, cmd)

    elif op == "log":
        try:
            n = int(args.strip()) if args.strip().isdigit() else 10
            n = min(n, 30)
        except ValueError:
            n = 10
        return _run_git(ws, [
            "git", "log", f"-{n}",
            "--oneline", "--decorate", "--graph"
        ])

    elif op == "branch":
        return _run_git(ws, ["git", "branch", "-a"])

    elif op == "add":
        target = args.strip() or "."
        # Safety: target must not escape workspace
        if ".." in target:
            return "[security error] Path traversal in git add target."
        return _run_git(ws, ["git", "add", target])

    elif op == "commit":
        msg = args.strip()
        if not msg:
            return "[error] Commit message required. Pass it as 'args'."
        if len(msg) > 500:
            return "[error] Commit message too long (max 500 chars)."
        return _run_git(ws, ["git", "commit", "-m", msg])

    elif op == "checkout":
        target = args.strip()
        if not target:
            return "[error] Branch name or file path required for checkout."
        if ".." in target:
            return "[security error] Path traversal in checkout target."
        return _run_git(ws, ["git", "checkout", target])

    return f"[error] Unhandled operation: {op}"


def _run_git(cwd: Path, cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=15,
        )
        out = (result.stdout + result.stderr).strip()
        if result.returncode != 0 and not out:
            return f"[error] git exited with code {result.returncode}"
        if not out:
            return "[ok] No output."
        # Truncate very long output
        lines = out.splitlines()
        if sum(len(l) for l in lines) > _MAX_OUTPUT:
            kept = []
            total = 0
            for line in lines:
                total += len(line) + 1
                if total > _MAX_OUTPUT:
                    kept.append(f"... [{len(lines) - len(kept)} more lines truncated]")
                    break
                kept.append(line)
            out = "\n".join(kept)
        return out
    except FileNotFoundError:
        return "[error] git not found. Is it installed?"
    except subprocess.TimeoutExpired:
        return "[error] git command timed out."
    except Exception as e:
        return f"[error] {e}"
