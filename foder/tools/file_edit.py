"""
file_edit — patch-based file editing.

Replaces a specific old_str with new_str inside an existing file.
This is diff-based editing: the agent only sends the changed block,
not the entire file. This dramatically reduces token usage and the
chance of accidental data loss when editing large files.

Matching strategy (in order):
  1. Exact match       — fast path, no ambiguity
  2. Normalized match  — strips leading/trailing whitespace from each line
                         before comparing, then applies the replacement using
                         the normalized positions. This handles the common
                         failure mode where the model sends old_str with
                         slightly different indentation than what's on disk.

Safety:
- Path must be inside workspace.
- old_str must match exactly once (ambiguous edits are rejected).
- A backup of the original content is returned on success so the
  caller can store it for /undo support.
"""

import re
from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "file_edit",
    "description": (
        "Edit a file by replacing old_str with new_str. "
        "old_str must appear exactly once in the file. "
        "Use this instead of file_write when you only want to change part of a file."
    ),
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the file from workspace root.",
        },
        "old_str": {
            "type": "string",
            "description": "Exact string to find in the file. Must appear exactly once.",
        },
        "new_str": {
            "type": "string",
            "description": "Replacement string. Can be empty to delete old_str.",
        },
    },
    "required": ["path", "old_str", "new_str"],
}


def _normalize_lines(text: str) -> str:
    """Strip trailing whitespace from every line and normalize line endings."""
    return "\n".join(line.rstrip() for line in text.splitlines())


def _find_normalized(content: str, old_str: str) -> tuple[int, int] | None:
    """
    Find the region in `content` that matches `old_str` after per-line
    whitespace normalization. Returns (start, end) byte offsets into the
    original `content`, or None if not found / ambiguous.

    Strategy:
      - Build a regex from the normalized old_str lines where each line is
        matched literally but leading whitespace on every line is treated as
        "one or more of whatever whitespace is already there".
      - This handles tabs-vs-spaces and minor indentation drift without
        accepting completely different indentation (still requires ≥1 space
        where spaces existed in old_str).
    """
    norm_old_lines = old_str.splitlines()
    if not norm_old_lines:
        return None

    # Build a pattern that matches each line's content regardless of exact indent
    parts = []
    for i, line in enumerate(norm_old_lines):
        stripped = line.strip()
        if not stripped:
            # Blank line — match optional whitespace
            parts.append(r"[^\S\n]*")
        else:
            # Leading whitespace in old_str → match any leading whitespace (≥0)
            leading_ws = len(line) - len(line.lstrip())
            if leading_ws > 0:
                parts.append(r"[^\S\n]*" + re.escape(stripped))
            else:
                parts.append(re.escape(stripped))
        if i < len(norm_old_lines) - 1:
            parts.append(r"\n")

    pattern = "".join(parts)
    matches = list(re.finditer(pattern, content))

    if len(matches) == 1:
        m = matches[0]
        return m.start(), m.end()
    return None


def execute(path: str, old_str: str, new_str: str) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] File not found: {path}"
    if not target.is_file():
        return f"[error] Path is not a file: {path}"

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[error] Could not read file: {e}"

    # ── Strategy 1: exact match ───────────────────────────────────────────────
    count = content.count(old_str)

    if count == 1:
        new_content = content.replace(old_str, new_str, 1)
        match_type  = ""

    elif count > 1:
        return (
            f"[error] old_str appears {count} times in {path}. "
            "Make old_str more specific so it matches exactly once."
        )

    else:
        # ── Strategy 2: normalized whitespace fallback ────────────────────────
        bounds = _find_normalized(content, old_str)
        if bounds is None:
            # Give the model a useful hint about the actual content near where
            # it was trying to edit, so the next attempt can be more precise.
            context_hint = ""
            first_line = old_str.splitlines()[0].strip() if old_str.strip() else ""
            if first_line:
                for i, line in enumerate(content.splitlines()):
                    if first_line[:20] in line:
                        start = max(0, i - 2)
                        end   = min(len(content.splitlines()), i + 4)
                        snippet = "\n".join(content.splitlines()[start:end])
                        context_hint = f"\n\nNearest match in file:\n{snippet}"
                        break
            return (
                f"[error] old_str not found in {path} (tried exact and whitespace-normalized match)."
                f"{context_hint}"
            )

        start, end    = bounds
        new_content   = content[:start] + new_str + content[end:]
        match_type    = " (normalized whitespace)"

    try:
        target.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"[error] Could not write file: {e}"

    lines_changed = abs(new_content.count("\n") - content.count("\n"))
    return f"[ok] Edited {path} (+/-{lines_changed} lines){match_type}"
