"""
Foder unit test suite — pytest compatible.
Covers imports, config, security, tools, agent, session, prompt, @file, snapshot, themes.

Run with:  pytest tests/test_unit.py -v
"""
import os
import sys
import tempfile
import json
from pathlib import Path

import pytest

# Prevent config from making an HTTP call to Ollama at import time
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5-coder:3b")


# ── Imports ───────────────────────────────────────────────────────────────────

def test_imports_all_modules_load():
    from foder import main, agent, llm, prompt, config, security
    from foder.tools import registry, file_read, file_write, dir_list, shell_exec


# ── Config ────────────────────────────────────────────────────────────────────

def test_config_defaults_are_valid():
    import foder.config as c
    assert c.WORKSPACE.exists()
    assert c.OLLAMA_BASE_URL.startswith("http")
    assert c.LLM_TIMEOUT > 0
    assert c.SHELL_TIMEOUT > 0
    assert c.MAX_ITERATIONS > 0


def test_config_foder_json_overrides_defaults():
    import foder.config as c
    orig_model   = c.OLLAMA_MODEL
    orig_timeout = c.LLM_TIMEOUT
    orig_ws      = c.WORKSPACE
    had_env = "OLLAMA_MODEL" in os.environ
    os.environ.pop("OLLAMA_MODEL", None)
    try:
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "foder.json"
            cfg.write_text(json.dumps({"model": "test-model:1b", "llm_timeout": 42}))
            c.WORKSPACE = Path(d)
            c.load_project_config()
            assert c.OLLAMA_MODEL == "test-model:1b", f"got {c.OLLAMA_MODEL}"
            assert c.LLM_TIMEOUT == 42.0, f"got {c.LLM_TIMEOUT}"
    finally:
        c.WORKSPACE    = orig_ws
        c.OLLAMA_MODEL = orig_model
        c.LLM_TIMEOUT  = orig_timeout
        if had_env:
            os.environ["OLLAMA_MODEL"] = orig_model


def test_config_malformed_foder_json_silently_ignored():
    import foder.config as c
    orig_ws = c.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "foder.json").write_text("{bad json{{")
        c.WORKSPACE = Path(d)
        c.load_project_config()   # must not raise
    c.WORKSPACE = orig_ws


# ── Security ──────────────────────────────────────────────────────────────────

def test_security_path_escape_blocked():
    from foder.security import validate_path, SecurityError
    with pytest.raises(SecurityError):
        validate_path("../../etc/passwd")


def test_security_valid_relative_path_allowed():
    from foder.security import validate_path
    p = validate_path("somefile.txt")
    assert p is not None


def test_security_dangerous_commands_blocked():
    from foder.security import validate_command, SecurityError
    for cmd in ["rm -rf /", "sudo rm -rf /home", "shutdown", "mkfs"]:
        with pytest.raises(SecurityError):
            validate_command(cmd)


def test_security_safe_commands_allowed():
    from foder.security import validate_command
    for cmd in ["ls -la", "python3 main.py", "git status", "echo hello"]:
        validate_command(cmd)  # must not raise


# ── Tools ─────────────────────────────────────────────────────────────────────

def test_tool_file_write_read_roundtrip():
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_read  import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fw("test.txt", "hello foder")
        assert "[ok]" in r, f"write failed: {r}"
        content = fr("test.txt")
        assert content == "hello foder", f"read mismatch: {repr(content)}"


def test_tool_file_write_creates_parent_directories():
    import foder.config as c
    from foder.tools.file_write import execute as fw
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fw("subdir/nested/file.txt", "content")
        assert "[ok]" in r
        assert (Path(d) / "subdir" / "nested" / "file.txt").exists()


def test_tool_file_read_missing_file_returns_error():
    import foder.config as c
    from foder.tools.file_read import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fr("nonexistent.txt")
        assert "[error]" in r


def test_tool_file_read_line_range():
    """New feature: start_line / end_line parameters."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_read  import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("lines.txt", "line1\nline2\nline3\nline4\nline5")
        result = fr("lines.txt", start_line=2, end_line=4)
        assert "line2" in result
        assert "line4" in result
        assert "line1" not in result
        assert "line5" not in result
        assert "[lines 2-4 of 5]" in result


def test_tool_file_read_negative_line_range():
    """Negative indices: -1 means last line."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_read  import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("neg.txt", "a\nb\nc\nd\ne")
        result = fr("neg.txt", start_line=-2, end_line=-1)
        assert "d" in result
        assert "e" in result
        assert "a" not in result


def test_tool_dir_list_shows_files():
    import foder.config as c
    from foder.tools.dir_list   import execute as dl
    from foder.tools.file_write import execute as fw
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("a.txt", "a"); fw("b.txt", "b")
        r = dl(".")
        assert "a.txt" in r and "b.txt" in r


def test_tool_dir_list_missing_dir_returns_error():
    import foder.config as c
    from foder.tools.dir_list import execute as dl
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = dl("nonexistent_dir")
        assert "[error]" in r


def test_tool_dir_create_creates_directory():
    import foder.config as c
    from foder.tools.dir_create import execute as dc
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = dc("my-folder")
        assert "[ok]" in r
        assert (Path(d) / "my-folder").is_dir()
        r2 = dc("my-folder")
        assert "already exists" in r2


def test_tool_dir_remove_empty_dir():
    """dir_remove on an empty dir must work without recursive flag."""
    import foder.config as c
    from foder.tools.dir_create import execute as dc
    from foder.tools.dir_remove import execute as dr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        dc("empty-dir")
        r = dr("empty-dir")
        assert "[ok]" in r
        assert not (Path(d) / "empty-dir").exists()


def test_tool_dir_remove_non_empty_requires_recursive():
    """dir_remove on non-empty dir without recursive=True must return an error."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.dir_remove import execute as dr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("nonempty/file.txt", "content")
        r = dr("nonempty")
        assert "[error]" in r
        assert "recursive" in r.lower()


def test_tool_dir_remove_recursive_flag():
    """dir_remove with recursive=True must remove a non-empty directory."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.dir_remove import execute as dr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("todelete/file1.txt", "a")
        fw("todelete/sub/file2.txt", "b")
        r = dr("todelete", recursive=True)
        assert "[ok]" in r
        assert not (Path(d) / "todelete").exists()


def test_tool_file_edit_exact_match():
    """file_edit exact-match path."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_edit  import execute as fe
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("edit_me.py", "def greet():\n    return 'hello'\n")
        r = fe("edit_me.py", old_str="return 'hello'", new_str="return 'hi'")
        assert "[ok]" in r
        content = (Path(d) / "edit_me.py").read_text()
        assert "return 'hi'" in content


def test_tool_file_edit_normalized_whitespace_fallback():
    """file_edit normalized-whitespace fallback: model sends wrong indent."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_edit  import execute as fe
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        # File uses 4-space indent
        fw("app.py", "def run():\n    print('start')\n    print('end')\n")
        # Model sends 2-space indent in old_str — should still match via normalization
        r = fe("app.py",
               old_str="  print('start')",
               new_str="    print('STARTED')")
        assert "[ok]" in r, f"Expected [ok], got: {r}"
        content = (Path(d) / "app.py").read_text()
        assert "STARTED" in content


def test_tool_file_edit_not_found_gives_context_hint():
    """file_edit error message includes a nearby-lines hint when possible."""
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_edit  import execute as fe
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("hint.py", "x = 1\ny = 2\nz = 3\n")
        r = fe("hint.py", old_str="definitely_not_in_file()", new_str="x")
        assert "[error]" in r


def test_tool_shell_exec_runs_command():
    import foder.config as c
    from foder.tools.shell_exec import execute as se
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = se("echo hello_foder_test")
        assert "hello_foder_test" in r, f"got: {r}"


def test_tool_shell_exec_blocks_dangerous_command():
    import foder.config as c
    from foder.tools.shell_exec import execute as se
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = se("rm -rf /")
        assert "security error" in r.lower() or "blocked" in r.lower(), f"got: {r}"


def test_tool_shell_exec_captures_non_zero_exit_code():
    import foder.config as c
    from foder.tools.shell_exec import execute as se
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = se("python3 -c 'import sys; sys.exit(2)'")
        assert "exit code" in r and "2" in r, f"got: {r}"


def test_tool_registry_returns_error_for_unknown_tool():
    from foder.tools.registry import dispatch
    r = dispatch("nonexistent_tool", {})
    assert "unknown" in r.lower()


def test_tool_registry_catches_missing_required_param():
    from foder.tools.registry import dispatch
    r = dispatch("file_write", {"path": "x.txt"})   # missing 'content'
    assert "missing" in r.lower() or "error" in r.lower()


def test_tool_file_read_blocks_path_escape():
    import foder.config as c
    from foder.tools.file_read import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fr("../../etc/passwd")
        assert "security error" in r.lower() or "denied" in r.lower(), f"got: {r}"


# ── Agent tool call detection ─────────────────────────────────────────────────

def test_agent_detects_bare_json_tool_call():
    from foder.agent import _extract_tool_call
    r = _extract_tool_call('{"tool": "dir_list", "parameters": {"path": "."}}')
    assert r is not None and r["tool"] == "dir_list"


def test_agent_detects_fenced_json_tool_call():
    from foder.agent import _extract_tool_call
    r = _extract_tool_call('```json\n{"tool": "file_read", "parameters": {"path": "x"}}\n```')
    assert r is not None and r["tool"] == "file_read"


def test_agent_detects_large_file_write_payload():
    from foder.agent import _extract_tool_call
    big     = "x" * 8000
    payload = json.dumps({"tool": "file_write", "parameters": {"path": "f.py", "content": big}})
    r = _extract_tool_call(payload)
    assert r is not None and r["tool"] == "file_write"


def test_agent_handles_nested_braces_in_file_content():
    from foder.agent import _extract_tool_call
    content = 'def f():\n    d = {"key": "val"}\n    return d\n'
    payload = json.dumps({"tool": "file_write", "parameters": {"path": "f.py", "content": content}})
    r = _extract_tool_call(payload)
    assert r is not None
    assert r["parameters"]["content"] == content


def test_agent_detects_json_with_preamble_text():
    from foder.agent import _extract_tool_call
    r = _extract_tool_call('Sure!\n{"tool": "dir_list", "parameters": {"path": "."}}')
    assert r is not None


def test_agent_detects_fenced_json_with_indentation():
    from foder.agent import _extract_tool_call, _is_tool_call
    text = ('```json\n            '
            '{"tool": "shell_exec", "parameters": {"command": "gcc hello.c -o hello"}}'
            '\n```')
    assert _is_tool_call(text)
    r = _extract_tool_call(text)
    assert r is not None and r["tool"] == "shell_exec"


def test_agent_no_false_positives_on_plain_text():
    from foder.agent import _extract_tool_call
    for text in [
        "The file has been created.",
        "Here is the code:\n```python\nprint('hi')\n```",
        "Done! tictactoe.py has been written.",
        "",
    ]:
        r = _extract_tool_call(text)
        assert r is None, f"false positive on: {repr(text)}"


def test_agent_history_trimming_caps_at_limit():
    from foder.agent import _trim_history, _MAX_HISTORY_MESSAGES
    history = [{"role": "user", "content": str(i)} for i in range(50)]
    trimmed = _trim_history(history)
    assert len(trimmed) <= _MAX_HISTORY_MESSAGES


def test_agent_tool_result_truncation_works():
    from foder.agent import _truncate_tool_result, _TOOL_RESULT_MAX_CHARS
    short = "x" * 100
    assert _truncate_tool_result(short) == short
    long  = "x" * (_TOOL_RESULT_MAX_CHARS * 3)
    result = _truncate_tool_result(long)
    assert len(result) <= _TOOL_RESULT_MAX_CHARS + 30, f"len={len(result)}"
    assert "truncated" in result


# ── Prompt ────────────────────────────────────────────────────────────────────

def test_prompt_system_message_prepended_correctly():
    from foder.prompt import build_messages
    msgs = build_messages([{"role": "user", "content": "hello"}])
    assert msgs[0]["role"] == "system"
    assert "WORKSPACE" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"


def test_prompt_all_tool_names_present():
    from foder.prompt import build_messages
    msgs    = build_messages([])
    content = msgs[0]["content"]
    for tool in ["file_write", "file_read", "dir_list", "shell_exec"]:
        assert tool in content, f"missing tool: {tool}"


def test_prompt_workspace_updates_dynamically():
    import foder.config as c
    from foder.prompt import build_messages
    orig = c.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        msgs = build_messages([])
        assert d in msgs[0]["content"], "workspace not in prompt"
    c.WORKSPACE = orig


def test_prompt_custom_instructions_injected():
    import foder.config as c
    from foder.prompt import build_messages
    orig = c.CUSTOM_INSTRUCTIONS
    c.CUSTOM_INSTRUCTIONS = "USE_TYPESCRIPT_ONLY"
    msgs = build_messages([])
    assert "USE_TYPESCRIPT_ONLY" in msgs[0]["content"]
    c.CUSTOM_INSTRUCTIONS = orig


# ── Session persistence ───────────────────────────────────────────────────────

def test_session_save_load_roundtrip():
    import foder.main as m
    orig_dir  = m._HISTORY_DIR
    orig_file = m._HISTORY_FILE
    with tempfile.TemporaryDirectory() as d:
        m._HISTORY_DIR  = Path(d)
        m._HISTORY_FILE = Path(d) / "session.json"
        history = [
            {"role": "user",      "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        m._save_session(history)
        loaded = m._load_session()
        assert loaded == history, f"mismatch: {loaded}"
    m._HISTORY_DIR  = orig_dir
    m._HISTORY_FILE = orig_file


def test_session_missing_file_returns_empty_list():
    import foder.main as m
    orig = m._HISTORY_FILE
    m._HISTORY_FILE = Path("/tmp/foder_no_such_file_xyz.json")
    r = m._load_session()
    assert r == []
    m._HISTORY_FILE = orig


def test_session_corrupted_file_returns_empty_list():
    import foder.main as m
    orig_dir  = m._HISTORY_DIR
    orig_file = m._HISTORY_FILE
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "session.json"
        f.write_text("{corrupted{{")
        m._HISTORY_DIR  = Path(d)
        m._HISTORY_FILE = f
        r = m._load_session()
        assert r == []
    m._HISTORY_DIR  = orig_dir
    m._HISTORY_FILE = orig_file


def test_session_large_history_trimmed_on_save():
    import foder.main as m
    orig_dir  = m._HISTORY_DIR
    orig_file = m._HISTORY_FILE
    with tempfile.TemporaryDirectory() as d:
        m._HISTORY_DIR  = Path(d)
        m._HISTORY_FILE = Path(d) / "session.json"
        big = [{"role": "user", "content": str(i)} for i in range(100)]
        m._save_session(big)
        loaded = m._load_session()
        assert len(loaded) <= m._MAX_SAVED_MESSAGES
    m._HISTORY_DIR  = orig_dir
    m._HISTORY_FILE = orig_file


# ── @file context injection ───────────────────────────────────────────────────

def test_at_file_no_refs_passes_through_unchanged():
    from foder.main import _inject_file_context
    r = _inject_file_context("just a normal message")
    assert r == "just a normal message"


def test_at_file_injects_file_content():
    import foder.config as c
    from foder.main import _inject_file_context
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        (Path(d) / "hello.py").write_text('print("hi")')
        r = _inject_file_context("@hello.py fix this")
        assert "--- @hello.py ---" in r
        assert 'print("hi")' in r
        assert "fix this" in r


def test_at_file_missing_file_doesnt_crash():
    import foder.config as c
    from foder.main import _inject_file_context
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = _inject_file_context("@nonexistent.py do something")
        assert "do something" in r


# ── Snapshot ──────────────────────────────────────────────────────────────────

def test_snapshot_captures_workspace_files():
    import foder.config as c
    import foder.main as m
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        m._cwd = Path(d)
        (Path(d) / "a.py").write_text("print(1)")
        snap = m._take_snapshot()
        assert "a.py" in snap
        assert snap["a.py"]["size"] > 0


# ── Theme system ──────────────────────────────────────────────────────────────

def test_themes_all_apply_correctly():
    import foder.main as m
    from foder.main import THEMES, _apply_theme
    for key in THEMES:
        _apply_theme(key)
        assert m._A2 == THEMES[key]["A2"], f"theme {key} A2 mismatch"
