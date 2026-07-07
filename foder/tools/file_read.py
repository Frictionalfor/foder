"""
file_read — read a file inside the workspace.

Supports optional line range (start_line / end_line) to read only a slice
of a large file. This keeps token usage low when the agent only needs a
specific section rather than the full contents.

Line numbers are 1-indexed and inclusive on both ends.
Negative values count from the end of the file (-1 = last line).
"""

from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "file_read",
    "description": (
        "Read the contents of a file inside the workspace. "
        "Use start_line and end_line to read only a specific section of a large file."
    ),
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the file from workspace root.",
        },
        "start_line": {
            "type": "integer",
            "description": (
                "First line to read (1-indexed, inclusive). "
                "Negative values count from the end (-1 = last line). "
                "Defaults to 1 (start of file)."
            ),
        },
        "end_line": {
            "type": "integer",
            "description": (
                "Last line to read (1-indexed, inclusive). "
                "Negative values count from the end (-1 = last line). "
                "Defaults to -1 (end of file)."
            ),
        },
    },
    "required": ["path"],
}


def execute(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
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

    # No line range requested — return full content
    if start_line is None and end_line is None:
        return content

    lines     = content.splitlines(keepends=True)
    total     = len(lines)

    if total == 0:
        return ""

    # Resolve negative indices (Python-style, but 1-based interface)
    def _resolve(n: int, default: int) -> int:
        if n is None:
            return default
        if n < 0:
            # -1 → total, -2 → total-1, etc.
            resolved = total + n + 1
        else:
            resolved = n
        return max(1, min(resolved, total))

    s = _resolve(start_line, 1)
    e = _resolve(end_line,  total)

    if s > e:
        return (
            f"[error] start_line ({start_line}) is after end_line ({end_line}) "
            f"in a file with {total} lines."
        )

    # Slice is 0-indexed; s and e are 1-indexed inclusive
    selected = lines[s - 1 : e]
    result   = "".join(selected)

    # Prepend a small header so the agent knows which lines it's seeing
    header = f"[lines {s}-{e} of {total}]\n"
    return header + result
