from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "dir_create",
    "description": "Create a new directory inside the workspace.",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path of the directory to create.",
        }
    },
    "required": ["path"],
}


def execute(path: str) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    try:
        if target.exists() and target.is_dir():
            return f"[ok] Directory already exists: {path}"
        target.mkdir(parents=True, exist_ok=True)
        return f"[ok] Created directory {path}"
    except Exception as e:
        return f"[error] Could not create directory: {e}"
