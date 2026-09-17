"""
code_verify — verify code syntax and integrity for files in the workspace.
"""
from pathlib import Path
from foder.security import validate_path, SecurityError
from foder.verification import verify_file

SCHEMA = {
    "name": "code_verify",
    "description": "Verify code syntax for a file in the workspace (supports Python, JSON, shell scripts).",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the file to verify.",
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

    is_valid, msg = verify_file(target)
    if is_valid:
        return f"[ok] {path}: {msg}"
    else:
        return f"[error] {path}: syntax verification failed:\n{msg}"
