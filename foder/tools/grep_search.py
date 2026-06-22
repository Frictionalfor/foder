"""
grep_search — search for a pattern across workspace files.

Uses ripgrep (rg) when available for speed; falls back to Python's re module.
Results are capped at 50 matches to avoid blowing up context.

Supports:
- Literal string search
- Regex search
- File pattern filtering (e.g. "*.py")
- Case-insensitive mode
"""

import re
import subprocess
from pathlib import Path
import foder.config as config
from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "grep_search",
    "description": (
        "Search for a text pattern across files in the workspace. "
        "Returns matching lines with file paths and line numbers. "
        "Use for finding function definitions, variable usages, TODO comments, etc."
    ),
    "parameters": {
        "pattern": {
            "type": "string",
            "description": "Search pattern (literal string or regex).",
        },
        "path": {
            "type": "string",
            "description": "Directory or file to search in. Defaults to workspace root.",
            "default": ".",
        },
        "file_pattern": {
            "type": "string",
            "description": "Glob pattern to filter files, e.g. '*.py' or '*.ts'.",
            "default": "",
        },
        "case_sensitive": {
            "type": "boolean",
            "description": "Case-sensitive search. Default false.",
            "default": False,
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of matching lines to return. Default 30.",
            "default": 30,
        },
    },
    "required": ["pattern"],
}

_MAX_RESULTS_HARD = 50


def execute(
    pattern: str,
    path: str = ".",
    file_pattern: str = "",
    case_sensitive: bool = False,
    max_results: int = 30,
) -> str:
    # Clamp max_results
    max_results = min(int(max_results), _MAX_RESULTS_HARD)

    # Validate search root
    try:
        search_root = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not search_root.exists():
        return f"[error] Path not found: {path}"

    # Try ripgrep first (much faster on large repos)
    rg_result = _try_ripgrep(pattern, search_root, file_pattern, case_sensitive, max_results)
    if rg_result is not None:
        return rg_result

    # Python fallback
    return _python_grep(pattern, search_root, file_pattern, case_sensitive, max_results)


def _try_ripgrep(
    pattern: str,
    root: Path,
    file_pattern: str,
    case_sensitive: bool,
    max_results: int,
) -> str | None:
    """Returns results string if rg is available, None otherwise."""
    try:
        args = ["rg", "--line-number", "--no-heading", "--color=never"]
        if not case_sensitive:
            args.append("--ignore-case")
        if file_pattern:
            args.extend(["--glob", file_pattern])
        args.extend(["--max-count", str(max_results)])
        args.extend([pattern, str(root)])

        result = subprocess.run(
            args,
            capture_output=True, text=True,
            timeout=10, cwd=str(config.WORKSPACE),
        )
        output = result.stdout.strip()
        if not output and result.returncode not in (0, 1):
            return None  # rg not installed or error

        if not output:
            return f"[no matches] Pattern '{pattern}' not found."

        lines = output.splitlines()[:max_results]
        # Make paths relative to workspace
        ws_str = str(config.WORKSPACE)
        cleaned = []
        for line in lines:
            if line.startswith(ws_str):
                line = line[len(ws_str):].lstrip("/")
            cleaned.append(line)

        count = len(cleaned)
        header = f"[{count} match{'es' if count != 1 else ''} for '{pattern}']\n"
        return header + "\n".join(cleaned)

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    except Exception:
        return None


def _python_grep(
    pattern: str,
    root: Path,
    file_pattern: str,
    case_sensitive: bool,
    max_results: int,
) -> str:
    """Pure-Python grep fallback."""
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        # Treat as literal string
        compiled = re.compile(re.escape(pattern), flags)

    # Collect candidate files
    if root.is_file():
        candidates = [root]
    else:
        if file_pattern:
            candidates = list(root.rglob(file_pattern))
        else:
            from foder.context import list_workspace_files
            candidates = list_workspace_files(root, max_files=300)

    results: list[str] = []
    for fpath in candidates:
        if not fpath.is_file():
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if compiled.search(line):
                rel = str(fpath.relative_to(config.WORKSPACE))
                results.append(f"{rel}:{i}: {line.strip()}")
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    if not results:
        return f"[no matches] Pattern '{pattern}' not found."

    count  = len(results)
    header = f"[{count} match{'es' if count != 1 else ''} for '{pattern}']\n"
    return header + "\n".join(results)
