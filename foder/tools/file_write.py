from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "file_write",
    "description": "Write or overwrite a file inside the workspace.",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the file from workspace root.",
        },
        "content": {
            "type": "string",
            "description": "Full content to write into the file.",
        },
    },
    "required": ["path", "content"],
}


def execute(path: str, content: str) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"[ok] Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"[error] Could not write file: {e}"
