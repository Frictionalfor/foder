"""
dir_remove — remove a directory inside the workspace.

By default, refuses to delete non-empty directories (safety constraint).
Pass recursive=True to remove a directory and all its contents.

The recursive flag requires an explicit opt-in so the agent cannot
accidentally wipe a directory it shouldn't. The workspace root itself
is always protected regardless of the flag.
"""

import shutil
from foder.security import validate_path, SecurityError
import foder.config as config

SCHEMA = {
    "name": "dir_remove",
    "description": (
        "Remove a directory inside the workspace. "
        "Set recursive=true to remove a non-empty directory and all its contents. "
        "The workspace root cannot be removed."
    ),
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the directory to remove.",
        },
        "recursive": {
            "type": "boolean",
            "description": (
                "If true, remove the directory and all its contents recursively. "
                "Defaults to false — non-empty directories will not be removed."
            ),
        },
    },
    "required": ["path"],
}


def execute(path: str, recursive: bool = False) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] Directory not found: {path}"
    if not target.is_dir():
        return f"[error] {path} is not a directory."

    # Protect workspace root — never allow removing it
    try:
        if target.resolve() == config.WORKSPACE.resolve():
            return "[security error] Cannot remove the workspace root directory."
    except Exception:
        pass

    try:
        contents = list(target.iterdir())
    except Exception as e:
        return f"[error] Could not inspect directory: {e}"

    if contents and not recursive:
        names = [p.name for p in contents[:5]]
        more  = len(contents) - 5
        hint  = ", ".join(names) + (f" (+{more} more)" if more > 0 else "")
        return (
            f"[error] Directory not empty: {path}\n"
            f"Contents: {hint}\n"
            "Use recursive=true to remove it along with all contents, "
            "or delete the files first."
        )

    try:
        if contents and recursive:
            entry_count = len(contents)   # capture count BEFORE rmtree deletes them
            shutil.rmtree(target)
            return f"[ok] Removed directory {path} and its contents ({entry_count} top-level entries)"
        else:
            target.rmdir()
            return f"[ok] Removed directory {path}"
    except Exception as e:
        return f"[error] Could not remove directory: {e}"
