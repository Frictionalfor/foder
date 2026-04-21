from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "dir_list",
    "description": "List files and directories at a given path inside the workspace.",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the directory. Use '.' for workspace root.",
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
        return f"[error] Path not found: {path}"
    if not target.is_dir():
        return f"[error] Path is not a directory: {path}"

    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = []
        for entry in entries:
            kind = "FILE" if entry.is_file() else "DIR "
            lines.append(f"  {kind}  {entry.name}")
        return "\n".join(lines) if lines else "[empty directory]"
    except Exception as e:
        return f"[error] Could not list directory: {e}"
