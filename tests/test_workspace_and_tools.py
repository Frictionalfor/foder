"""
Tests for Foder workspace awareness, filesystem tools, shell execution,
syntax verification, path traversal protection, tool-result context flow,
and the calculator regression scenario.
"""
import os
import sys
import tempfile
import json
from pathlib import Path
import pytest

import foder.config as config
from foder.context import detect_project, build_context_summary, invalidate_cache
from foder.security import validate_path, validate_command, SecurityError
from foder.verification import verify_python_syntax, verify_file
from foder.tools.dir_list import execute as dir_list_exec
from foder.tools.file_read import execute as file_read_exec
from foder.tools.file_write import execute as file_write_exec
from foder.tools.file_edit import execute as file_edit_exec
from foder.tools.file_delete import execute as file_delete_exec
from foder.tools.shell_exec import execute as shell_exec_exec
from foder.tools.registry import dispatch
from foder.agent import run, AgentCallbacks, _infer_filename, _extract_code_block_as_tool_call


# ── 1. Workspace Awareness & Detection ────────────────────────────────────────

def test_workspace_empty_detection():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        profile = detect_project(ws)
        assert "empty workspace" in profile.project_type
        assert profile.summary == "empty workspace"

        summary = build_context_summary(ws)
        assert "empty workspace" in summary


def test_workspace_standalone_python_detection():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "calculator.py").write_text("def add(x, y): return x + y\n")
        invalidate_cache(ws)
        profile = detect_project(ws)
        assert "python" in profile.project_type
        assert "calculator.py" in profile.entry_points


def test_workspace_summary_lists_files():
    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "calculator.py").write_text("def add(a, b): return a + b\n")
        (ws / "README.md").write_text("# Calc\n")
        invalidate_cache(ws)
        summary = build_context_summary(ws)
        assert "WORKSPACE FILES:" in summary
        assert "calculator.py" in summary
        assert "README.md" in summary


# ── 2. Filesystem Tools ───────────────────────────────────────────────────────

def test_tool_dir_list_empty_and_populated():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        # Empty workspace
        res = dir_list_exec(".")
        assert res == "[empty directory]"

        # Create files and subdirs
        (Path(d) / "calc.py").write_text("x = 1\n")
        (Path(d) / "src").mkdir()
        res2 = dir_list_exec(".")
        assert "calc.py" in res2
        assert "src/" in res2
        # Verify no Rich hex color markup tags in output
        assert "[#" not in res2
    config.WORKSPACE = orig_ws


def test_tool_file_creation_and_reading():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        # Create in subfolder
        res = file_write_exec("pkg/module.py", "x = 42\n")
        assert "[ok]" in res
        assert (Path(d) / "pkg" / "module.py").exists()

        # Read
        read_res = file_read_exec("pkg/module.py")
        assert "x = 42" in read_res
    config.WORKSPACE = orig_ws


def test_tool_file_modification():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        file_write_exec("app.py", "def run():\n    return 1\n")
        res = file_edit_exec("app.py", old_str="return 1", new_str="return 2")
        assert "[ok]" in res
        content = (Path(d) / "app.py").read_text()
        assert "return 2" in content
    config.WORKSPACE = orig_ws


def test_tool_file_delete_safety():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        file_write_exec("temp.txt", "data")
        # Attempt delete without confirm
        res_no_confirm = file_delete_exec("temp.txt", confirm=False)
        assert "[error]" in res_no_confirm
        assert (Path(d) / "temp.txt").exists()

        # Delete with confirm
        res_confirm = file_delete_exec("temp.txt", confirm=True)
        assert "[ok]" in res_confirm
        assert not (Path(d) / "temp.txt").exists()
    config.WORKSPACE = orig_ws


# ── 3. Shell Execution ────────────────────────────────────────────────────────

def test_tool_shell_exec_in_workspace():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        res = shell_exec_exec("pwd")
        assert Path(d).name in res

        # Run python code inside workspace
        file_write_exec("hello.py", "print('foder_test_success')\n")
        res2 = shell_exec_exec("python3 hello.py")
        assert "foder_test_success" in res2


def test_tool_shell_exec_exit_code_and_stderr():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        res = shell_exec_exec("python3 -c 'import sys; sys.stderr.write(\"sample_err\\n\"); sys.exit(42)'")
        assert "[exit code 42]" in res
        assert "sample_err" in res
    config.WORKSPACE = orig_ws


# ── 4. Security & Path Traversal Protection ───────────────────────────────────

def test_security_path_traversal_blocked():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        with pytest.raises(SecurityError):
            validate_path("../../etc/passwd")

        with pytest.raises(SecurityError):
            validate_path("/etc/shadow")

        with pytest.raises(SecurityError):
            validate_path("sub/../../etc/passwd")

        # Via tool
        err_res = file_write_exec("../../outside.py", "evil = True")
        assert "[security error]" in err_res
    config.WORKSPACE = orig_ws


def test_security_blocked_commands():
    with pytest.raises(SecurityError):
        validate_command("rm -rf /")

    with pytest.raises(SecurityError):
        validate_command("rm -rf /*")

    with pytest.raises(SecurityError):
        validate_command("sudo mkfs /dev/sda")


# ── 5. Python Syntax Verification ─────────────────────────────────────────────

def test_python_syntax_verification_valid():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "calc.py"
        p.write_text("def add(x, y):\n    return x + y\n")
        valid, msg = verify_python_syntax(p)
        assert valid is True
        assert "valid Python syntax" in msg


def test_python_syntax_verification_invalid_colon():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "calc.py"
        # Invalid syntax from the user request
        p.write_text("def add(x, y):\n    return x + y\n\ndef subtract(x, y)::\n    return x - y\n")
        valid, msg = verify_python_syntax(p)
        assert valid is False
        assert "SyntaxError on line 4" in msg
        assert "def subtract(x, y)::" in msg
        assert "^" in msg


def test_file_write_auto_verifies_syntax():
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)
        # Invalid syntax
        bad_code = "def subtract(x, y)::\n    return x - y\n"
        res = file_write_exec("bad_calc.py", bad_code)
        assert "[error]" in res
        assert "syntax verification failed" in res
        assert "def subtract(x, y)::" in res

        # Fixed code
        good_code = "def subtract(x, y):\n    return x - y\n"
        res2 = file_write_exec("bad_calc.py", good_code)
        assert "[ok]" in res2
        assert "valid Python syntax" in res2
    config.WORKSPACE = orig_ws


# ── 6. Tool Synthesis and Filename Inference ──────────────────────────────────

def test_infer_filename_calculator():
    fname = _infer_filename("def add(a, b): return a + b", "write me a python program which adds, subtracts, multiplies and divides two numbers", "python")
    assert fname == "calculator.py"


def test_code_block_fallback_synthesizes_tool_call():
    code_resp = "```python\ndef add(a, b):\n    return a + b\n```"
    user_req = "write me a python program which adds, subtracts, multiplies and divides two numbers"
    tc = _extract_code_block_as_tool_call(code_resp, user_req)
    assert tc is not None
    assert tc["tool"] == "file_write"
    assert tc["parameters"]["path"] == "calculator.py"
    assert "def add(a, b):" in tc["parameters"]["content"]


# ── 7. Regression Test: Self-Correction Loop ──────────────────────────────────

def test_calculator_regression_self_correction_flow():
    """
    Test the full agent loop flow:
    1. User asks for calculator program
    2. Model generates code with invalid syntax: def subtract(x, y)::
    3. Tool detects syntax error and captures line/pointer
    4. Error context is sent back to model in history
    5. Model produces corrected code: def subtract(x, y):
    6. Tool verifies valid Python syntax
    7. Code executes via shell_exec to verify runtime output
    """
    orig_ws = config.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        config.WORKSPACE = Path(d)

        # Step 1: Initial buggy response with syntax error
        bad_code = (
            "```python\n"
            "def add(x, y):\n"
            "    return x + y\n"
            "\n"
            "def subtract(x, y)::\n"
            "    return x - y\n"
            "\n"
            "def multiply(x, y):\n"
            "    return x * y\n"
            "\n"
            "def divide(x, y):\n"
            "    return x / y\n"
            "```"
        )
        user_prompt = "write me a python program which adds, subtracts, multiplies and divides two numbers"

        # Synthesize tool call
        tc = _extract_code_block_as_tool_call(bad_code, user_prompt)
        assert tc is not None
        assert tc["parameters"]["path"] == "calculator.py"

        # Execute tool call
        res1 = dispatch(tc["tool"], tc["parameters"])
        assert "[error]" in res1
        assert "syntax verification failed" in res1
        assert "def subtract(x, y)::" in res1

        # Step 2: Model receives error in history and corrects it
        fixed_code = (
            "```python\n"
            "def add(x, y):\n"
            "    return x + y\n"
            "\n"
            "def subtract(x, y):\n"
            "    return x - y\n"
            "\n"
            "def multiply(x, y):\n"
            "    return x * y\n"
            "\n"
            "def divide(x, y):\n"
            "    if y == 0:\n"
            "        raise ValueError('Cannot divide by zero')\n"
            "    return x / y\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    print('4 + 2 =', add(4, 2))\n"
            "    print('4 - 2 =', subtract(4, 2))\n"
            "    print('4 * 2 =', multiply(4, 2))\n"
            "    print('4 / 2 =', divide(4, 2))\n"
            "```"
        )

        tc_fixed = _extract_code_block_as_tool_call(fixed_code, user_prompt)
        res2 = dispatch(tc_fixed["tool"], tc_fixed["parameters"])
        assert "[ok]" in res2
        assert "valid Python syntax" in res2

        # Step 3: Run the code inside workspace
        exec_res = shell_exec_exec("python3 calculator.py")
        assert "4 + 2 = 6" in exec_res
        assert "4 - 2 = 2" in exec_res
        assert "4 * 2 = 8" in exec_res
        assert "4 / 2 = 2.0" in exec_res

        # Step 4: Final verification on disk
        target_file = Path(d) / "calculator.py"
        assert target_file.exists()
        is_valid, msg = verify_file(target_file)
        assert is_valid is True

    config.WORKSPACE = orig_ws
