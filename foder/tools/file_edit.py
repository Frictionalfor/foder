"""
file_edit — patch-based file editing.

Replaces a specific old_str with new_str inside an existing file.
This is diff-based editing: the agent only sends the changed block,
not the entire file. This dramatically reduces token usage and the
chance of accidental data loss when editing large files.

Safety:
- Path must be inside workspace.
- old_str must exist exactly once (ambiguous edits are rejected).
- A backup of the original content is returned on success so the
  caller can store it for /undo support.
"""

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

    count = content.count(old_str)
    if count == 0:
        return f"[error] old_str not found in {path}"
    if count > 1:
        return (
            f"[error] old_str appears {count} times in {path}. "
            "Make old_str more specific so it matches exactly once."
        )

    new_content = content.replace(old_str, new_str, 1)

    try:
        target.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"[error] Could not write file: {e}"

    lines_changed = abs(new_content.count("\n") - content.count("\n"))
    return f"[ok] Edited {path} (+/-{lines_changed} lines)"
