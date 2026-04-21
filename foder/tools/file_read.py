from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "file_read",
    "description": "Read the contents of a file inside the workspace.",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the file from workspace root.",
        }
    },
    "required": ["path"],
}


def execute(path: str) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] File not found: {path}"
    if not target.is_file():
        return f"[error] Path is not a file: {path}"

    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[error] Could not read file: {e}"
