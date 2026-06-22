"""
file_rename — rename or move a file within the workspace.

Both source and destination must resolve inside the workspace.
Parent directories of the destination are created automatically.
"""

from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "file_rename",
    "description": (
        "Rename or move a file within the workspace. "
        "Both paths must be inside the workspace. "
        "Parent directories of destination are created automatically."
    ),
    "parameters": {
        "source": {
            "type": "string",
            "description": "Relative path to the file to rename/move.",
        },
        "destination": {
            "type": "string",
            "description": "New relative path (including new filename).",
        },
    },
    "required": ["source", "destination"],
}


def execute(source: str, destination: str) -> str:
    try:
        src  = validate_path(source)
        dest = validate_path(destination)
    except SecurityError as e:
        return f"[security error] {e}"

    if not src.exists():
        return f"[error] Source not found: {source}"
    if src.is_dir():
        return f"[error] {source} is a directory. Use dir_move instead."
    if dest.exists():
        return f"[error] Destination already exists: {destination}. Delete it first."

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
        return f"[ok] Renamed {source} → {destination}"
    except Exception as e:
        return f"[error] Could not rename: {e}"
