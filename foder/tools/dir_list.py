from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "dir_list",
    "description": "List files and directories at a given path inside the workspace. Defaults to '.' (workspace root).",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the directory. Use '.' for workspace root. Defaults to '.'.",
        }
    },
    "required": [],
}


def execute(path: str = ".") -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] Path not found: {path}"
    if not target.is_dir():
        return f"[error] Path is not a directory: {path}"

    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        if not entries:
            return "[empty directory]"

        items = []
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                items.append(f"{entry.name}/")
            else:
                items.append(entry.name)

        if not items:
            return "[empty directory]"

        return "  " + "  ".join(items)
    except Exception as e:
        return f"[error] Could not list directory: {e}"
