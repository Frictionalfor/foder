from foder.security import validate_path, SecurityError
from foder.verification import verify_file

SCHEMA = {
    "name": "file_write",
    "description": "Write or overwrite a file inside the workspace. Automatically verifies syntax for supported languages.",
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

        # Invalidate workspace cache so context detects new files immediately
        try:
            from foder.context import invalidate_cache
            invalidate_cache()
        except Exception:
            pass

        # Verify syntax (e.g. Python ast/py_compile check)
        is_valid, vmsg = verify_file(target)
        if not is_valid:
            return (
                f"[error] File written to {path}, but syntax verification failed:\n"
                f"{vmsg}\n"
                "Please analyze this error and fix the syntax immediately using file_edit or file_write."
            )

        return f"[ok] Written {len(content)} bytes to {path} ({vmsg})"
    except Exception as e:
        return f"[error] Could not write file: {e}"
