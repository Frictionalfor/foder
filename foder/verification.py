"""
Code verification module for Foder.

Provides syntax and correctness verification for generated or modified code.
Supports:
  - Python: ast parse + py_compile (capturing exact line numbers and syntax errors)
  - JSON: json.loads syntax validation
  - Shell / Bash: bash -n syntax check (if bash available)
"""

import ast
import json
import subprocess
import sys
from pathlib import Path


def verify_python_syntax(file_path: Path) -> tuple[bool, str]:
    """
    Verify Python file syntax using both ast.parse and py_compile.
    Returns (is_valid, message).
    """
    if not file_path.exists():
        return False, f"File not found: {file_path}"

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return False, f"Could not read file for verification: {e}"

    # Pass 1: In-process AST parsing (fast, detailed Python-native syntax errors)
    try:
        ast.parse(source, filename=str(file_path.name))
    except SyntaxError as e:
        line = e.lineno or "?"
        offset = e.offset or 0
        error_line = e.text.rstrip() if e.text else ""
        pointer = " " * (offset - 1) + "^" if offset > 0 else "^"
        details = [
            f"SyntaxError on line {line}: {e.msg}",
            f"  {error_line}",
            f"  {pointer}",
        ]
        return False, "\n".join(details)
    except Exception as e:
        return False, f"Syntax parsing failed: {e}"

    # Pass 2: py_compile subprocess (matches exact runtime compilation behavior)
    try:
        res = subprocess.run(
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "Compilation failed"
            return False, f"py_compile error:\n{err}"
    except Exception:
        # If py_compile process fails to spawn, ast.parse check is sufficient
        pass

    return True, "valid Python syntax"


def verify_json_syntax(file_path: Path) -> tuple[bool, str]:
    """Verify JSON file syntax. Returns (is_valid, message)."""
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        json.loads(content)
        return True, "valid JSON syntax"
    except json.JSONDecodeError as e:
        return False, f"JSONDecodeError on line {e.lineno}, col {e.colno}: {e.msg}"
    except Exception as e:
        return False, f"JSON validation failed: {e}"


def verify_shell_syntax(file_path: Path) -> tuple[bool, str]:
    """Verify shell script syntax using bash -n if available."""
    if not file_path.exists():
        return False, f"File not found: {file_path}"
    try:
        res = subprocess.run(
            ["bash", "-n", str(file_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "Syntax check failed"
            return False, f"Shell syntax error:\n{err}"
        return True, "valid shell syntax"
    except FileNotFoundError:
        return True, "bash not installed, skipped syntax check"
    except Exception as e:
        return False, f"Shell validation error: {e}"


def verify_file(file_path: Path | str, workspace: Path | None = None) -> tuple[bool, str]:
    """
    Dispatcher to verify a file based on its file extension.
    Returns (is_valid, message).
    """
    path = Path(file_path)
    if workspace and not path.is_absolute():
        path = (workspace / path).resolve()

    suffix = path.suffix.lower()

    if suffix in (".py", ".pyw"):
        return verify_python_syntax(path)
    elif suffix == ".json":
        return verify_json_syntax(path)
    elif suffix in (".sh", ".bash"):
        return verify_shell_syntax(path)

    # For other file types without automated validator
    return True, "no validator needed"
