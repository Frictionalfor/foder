"""
file_delete — delete a file inside the workspace.

Safety:
- Path must resolve inside workspace.
- Directories are not deleted (use dir_remove for that).
- A safety confirmation flag prevents accidental deletion.
"""

from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "file_delete",
    "description": (
        "Delete a file inside the workspace. "
        "confirm must be true. Directories cannot be deleted with this tool."
    ),
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the file to delete.",
        },
        "confirm": {
            "type": "boolean",
            "description": "Must be true to confirm deletion.",
        },
    },
    "required": ["path", "confirm"],
}


def execute(path: str, confirm: bool = False) -> str:
    if not confirm:
        return "[error] confirm must be true to delete a file."

    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] File not found: {path}"
    if target.is_dir():
        return f"[error] {path} is a directory. Use dir_remove to remove directories."

    try:
        target.unlink()
        return f"[ok] Deleted {path}"
    except Exception as e:
        return f"[error] Could not delete file: {e}"
