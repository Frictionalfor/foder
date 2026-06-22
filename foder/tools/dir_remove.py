"""
dir_remove — remove an empty directory inside the workspace.

Refuses to recursively delete non-empty directories for safety.
Use shell_exec with a safe rm -rf if recursive deletion is truly needed
(the user can explicitly confirm that in the shell).
"""

from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "dir_remove",
    "description": (
        "Remove an empty directory inside the workspace. "
        "Will not remove non-empty directories (safety constraint)."
    ),
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the directory to remove.",
        },
    },
    "required": ["path"],
}


def execute(path: str) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] Directory not found: {path}"
    if not target.is_dir():
        return f"[error] {path} is not a directory."

    try:
        contents = list(target.iterdir())
        if contents:
            names = [p.name for p in contents[:5]]
            more  = len(contents) - 5
            hint  = ", ".join(names) + (f" (+{more} more)" if more > 0 else "")
            return (
                f"[error] Directory not empty: {path}\n"
                f"Contents: {hint}\n"
                "Delete files first, or use shell_exec for recursive removal."
            )
        target.rmdir()
        return f"[ok] Removed directory {path}"
    except Exception as e:
        return f"[error] Could not remove directory: {e}"
