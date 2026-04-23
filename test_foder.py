"""
Foder test suite — covers imports, config, security, tools, agent, session, prompt.
Run with: python3 test_foder.py
"""
import sys
import tempfile
import json
from pathlib import Path

results = []

def test(name, fn):
    try:
        fn()
        results.append(("PASS", name))
    except Exception as e:
        results.append(("FAIL", f"{name}  ->  {e}"))


# ── Imports ───────────────────────────────────────────────────────────────────

def t_imports():
    from foder import main, agent, llm, prompt, config, security
    from foder.tools import registry, file_read, file_write, dir_list, shell_exec

test("imports: all modules load", t_imports)


# ── Config ────────────────────────────────────────────────────────────────────

def t_config_defaults():
    import foder.config as c
    assert c.WORKSPACE.exists()
    assert c.OLLAMA_BASE_URL.startswith("http")
    assert c.LLM_TIMEOUT > 0
    assert c.SHELL_TIMEOUT > 0
    assert c.MAX_ITERATIONS > 0

test("config: defaults are valid", t_config_defaults)


def t_config_foder_json():
    import foder.config as c
    orig_model   = c.OLLAMA_MODEL
    orig_timeout = c.LLM_TIMEOUT
    orig_ws      = c.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / "foder.json"
        cfg.write_text(json.dumps({"model": "test-model:1b", "llm_timeout": 42}))
        c.WORKSPACE = Path(d)
        c.load_project_config()
        assert c.OLLAMA_MODEL == "test-model:1b", f"got {c.OLLAMA_MODEL}"
        assert c.LLM_TIMEOUT == 42.0, f"got {c.LLM_TIMEOUT}"
    c.WORKSPACE    = orig_ws
    c.OLLAMA_MODEL = orig_model
    c.LLM_TIMEOUT  = orig_timeout

test("config: foder.json overrides defaults", t_config_foder_json)


def t_config_malformed_json():
    import foder.config as c
    orig_ws = c.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "foder.json").write_text("{bad json{{")
        c.WORKSPACE = Path(d)
        c.load_project_config()   # should not raise
    c.WORKSPACE = orig_ws

test("config: malformed foder.json is silently ignored", t_config_malformed_json)


# ── Security ──────────────────────────────────────────────────────────────────

def t_security_path_escape():
    from foder.security import validate_path, SecurityError
    try:
        validate_path("../../etc/passwd")
        raise AssertionError("should have raised SecurityError")
    except SecurityError:
        pass

test("security: path escape blocked", t_security_path_escape)


def t_security_valid_path():
    from foder.security import validate_path
    p = validate_path("somefile.txt")
    assert p is not None

test("security: valid relative path allowed", t_security_valid_path)


def t_security_blocked_commands():
    from foder.security import validate_command, SecurityError
    blocked = ["rm -rf /", "sudo rm -rf /home", "shutdown", "mkfs"]
    for cmd in blocked:
        try:
            validate_command(cmd)
            raise AssertionError(f"should have blocked: {cmd}")
        except SecurityError:
            pass

test("security: dangerous commands blocked", t_security_blocked_commands)


def t_security_safe_commands():
    from foder.security import validate_command
    for cmd in ["ls -la", "python3 main.py", "git status", "echo hello"]:
        validate_command(cmd)

test("security: safe commands allowed", t_security_safe_commands)


# ── Tools ─────────────────────────────────────────────────────────────────────

def t_tool_write_read():
    import foder.config as c
    from foder.tools.file_write import execute as fw
    from foder.tools.file_read import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fw("test.txt", "hello foder")
        assert "[ok]" in r, f"write failed: {r}"
        content = fr("test.txt")
        assert content == "hello foder", f"read mismatch: {repr(content)}"

test("tools: file_write + file_read roundtrip", t_tool_write_read)


def t_tool_write_creates_dirs():
    import foder.config as c
    from foder.tools.file_write import execute as fw
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fw("subdir/nested/file.txt", "content")
        assert "[ok]" in r
        assert (Path(d) / "subdir" / "nested" / "file.txt").exists()

test("tools: file_write creates parent directories", t_tool_write_creates_dirs)


def t_tool_read_missing():
    import foder.config as c
    from foder.tools.file_read import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fr("nonexistent.txt")
        assert "[error]" in r

test("tools: file_read missing file returns error", t_tool_read_missing)


def t_tool_dir_list():
    import foder.config as c
    from foder.tools.dir_list import execute as dl
    from foder.tools.file_write import execute as fw
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        fw("a.txt", "a"); fw("b.txt", "b")
        r = dl(".")
        assert "a.txt" in r and "b.txt" in r

test("tools: dir_list shows files", t_tool_dir_list)


def t_tool_dir_list_missing():
    import foder.config as c
    from foder.tools.dir_list import execute as dl
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = dl("nonexistent_dir")
        assert "[error]" in r

test("tools: dir_list missing dir returns error", t_tool_dir_list_missing)


def t_tool_dir_create():
    import foder.config as c
    from foder.tools.dir_create import execute as dc
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = dc("my-folder")
        assert "[ok]" in r
        assert (Path(d) / "my-folder").is_dir()
        # Second call should say already exists
        r2 = dc("my-folder")
        assert "already exists" in r2

test("tools: dir_create creates directory", t_tool_dir_create)


def t_tool_shell_exec():
    import foder.config as c
    from foder.tools.shell_exec import execute as se
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = se("echo hello_foder_test")
        assert "hello_foder_test" in r, f"got: {r}"

test("tools: shell_exec runs command", t_tool_shell_exec)


def t_tool_shell_exec_blocked():
    import foder.config as c
    from foder.tools.shell_exec import execute as se
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = se("rm -rf /")
        assert "security error" in r.lower() or "blocked" in r.lower(), f"got: {r}"

test("tools: shell_exec blocks dangerous command", t_tool_shell_exec_blocked)


def t_tool_shell_exec_exit_code():
    import foder.config as c
    from foder.tools.shell_exec import execute as se
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = se("python3 -c 'import sys; sys.exit(2)'")
        assert "exit code" in r and "2" in r, f"got: {r}"

test("tools: shell_exec captures non-zero exit code", t_tool_shell_exec_exit_code)


def t_tool_registry_unknown():
    from foder.tools.registry import dispatch
    r = dispatch("nonexistent_tool", {})
    assert "unknown" in r.lower()

test("tools: registry returns error for unknown tool", t_tool_registry_unknown)


def t_tool_registry_missing_param():
    from foder.tools.registry import dispatch
    r = dispatch("file_write", {"path": "x.txt"})
    assert "missing" in r.lower() or "error" in r.lower()

test("tools: registry catches missing required param", t_tool_registry_missing_param)


def t_tool_path_escape_via_tool():
    import foder.config as c
    from foder.tools.file_read import execute as fr
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = fr("../../etc/passwd")
        assert "security error" in r.lower() or "denied" in r.lower(), f"got: {r}"

test("tools: file_read blocks path escape", t_tool_path_escape_via_tool)


# ── Agent tool call detection ─────────────────────────────────────────────────

def t_agent_bare_json():
    from foder.agent import _extract_tool_call
    r = _extract_tool_call('{"tool": "dir_list", "parameters": {"path": "."}}')
    assert r is not None and r["tool"] == "dir_list"

test("agent: detects bare JSON tool call", t_agent_bare_json)


def t_agent_fenced_json():
    from foder.agent import _extract_tool_call
    r = _extract_tool_call('```json\n{"tool": "file_read", "parameters": {"path": "x"}}\n```')
    assert r is not None and r["tool"] == "file_read"

test("agent: detects fenced JSON tool call", t_agent_fenced_json)


def t_agent_large_payload():
    from foder.agent import _extract_tool_call
    big = "x" * 8000
    payload = json.dumps({"tool": "file_write", "parameters": {"path": "f.py", "content": big}})
    r = _extract_tool_call(payload)
    assert r is not None and r["tool"] == "file_write"

test("agent: detects large file_write payload (>512 chars)", t_agent_large_payload)


def t_agent_nested_braces():
    from foder.agent import _extract_tool_call
    content = 'def f():\n    d = {"key": "val"}\n    return d\n'
    payload = json.dumps({"tool": "file_write", "parameters": {"path": "f.py", "content": content}})
    r = _extract_tool_call(payload)
    assert r is not None
    assert r["parameters"]["content"] == content

test("agent: handles nested braces in file content", t_agent_nested_braces)


def t_agent_preamble():
    from foder.agent import _extract_tool_call
    r = _extract_tool_call('Sure!\n{"tool": "dir_list", "parameters": {"path": "."}}')
    assert r is not None

test("agent: detects JSON with preamble text", t_agent_preamble)


def t_agent_fenced_with_indent():
    from foder.agent import _extract_tool_call, _is_tool_call
    text = '```json\n            {"tool": "shell_exec", "parameters": {"command": "gcc hello.c -o hello"}}\n```'
    assert _is_tool_call(text)
    r = _extract_tool_call(text)
    assert r is not None and r["tool"] == "shell_exec"

test("agent: detects fenced JSON with indentation", t_agent_fenced_with_indent)


def t_agent_no_false_positive():
    from foder.agent import _extract_tool_call
    for text in [
        "The file has been created.",
        "Here is the code:\n```python\nprint('hi')\n```",
        "Done! tictactoe.py has been written.",
        "",
    ]:
        r = _extract_tool_call(text)
        assert r is None, f"false positive on: {repr(text)}"

test("agent: no false positives on plain text", t_agent_no_false_positive)


def t_agent_history_trim():
    from foder.agent import _trim_history, _MAX_HISTORY_MESSAGES
    history = [{"role": "user", "content": str(i)} for i in range(50)]
    trimmed = _trim_history(history)
    assert len(trimmed) <= _MAX_HISTORY_MESSAGES

test("agent: history trimming caps at limit", t_agent_history_trim)


def t_agent_tool_result_truncation():
    from foder.agent import _truncate_tool_result
    long = "x" * 2000
    result = _truncate_tool_result(long)
    assert len(result) <= 600
    assert "truncated" in result

test("agent: tool result truncation works", t_agent_tool_result_truncation)


# ── Prompt ────────────────────────────────────────────────────────────────────

def t_prompt_structure():
    from foder.prompt import build_messages
    msgs = build_messages([{"role": "user", "content": "hello"}])
    assert msgs[0]["role"] == "system"
    assert "WORKSPACE" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"

test("prompt: system message prepended correctly", t_prompt_structure)


def t_prompt_has_tools():
    from foder.prompt import build_messages
    msgs = build_messages([])
    content = msgs[0]["content"]
    for tool in ["file_write", "file_read", "dir_list", "shell_exec"]:
        assert tool in content, f"missing tool: {tool}"

test("prompt: all tool names present", t_prompt_has_tools)


def t_prompt_workspace_dynamic():
    import foder.config as c
    from foder.prompt import build_messages
    orig = c.WORKSPACE
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        msgs = build_messages([])
        assert d in msgs[0]["content"], "workspace not in prompt"
    c.WORKSPACE = orig

test("prompt: workspace updates dynamically with !cd", t_prompt_workspace_dynamic)


def t_prompt_custom_instructions():
    import foder.config as c
    from foder.prompt import build_messages
    orig = c.CUSTOM_INSTRUCTIONS
    c.CUSTOM_INSTRUCTIONS = "USE_TYPESCRIPT_ONLY"
    msgs = build_messages([])
    assert "USE_TYPESCRIPT_ONLY" in msgs[0]["content"]
    c.CUSTOM_INSTRUCTIONS = orig

test("prompt: custom instructions injected", t_prompt_custom_instructions)


# ── Session persistence ───────────────────────────────────────────────────────

def t_session_roundtrip():
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

test("session: save/load roundtrip", t_session_roundtrip)


def t_session_missing_file():
    import foder.main as m
    orig = m._HISTORY_FILE
    m._HISTORY_FILE = Path("/tmp/foder_no_such_file_xyz.json")
    r = m._load_session()
    assert r == []
    m._HISTORY_FILE = orig

test("session: missing file returns empty list", t_session_missing_file)


def t_session_corrupted():
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

test("session: corrupted file returns empty list", t_session_corrupted)


def t_session_trim_on_save():
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

test("session: large history trimmed on save", t_session_trim_on_save)


# ── @file injection ───────────────────────────────────────────────────────────

def t_inject_passthrough():
    from foder.main import _inject_file_context
    r = _inject_file_context("just a normal message")
    assert r == "just a normal message"

test("@file: no refs passes through unchanged", t_inject_passthrough)


def t_inject_file():
    import foder.config as c
    from foder.main import _inject_file_context
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        (Path(d) / "hello.py").write_text('print("hi")')
        r = _inject_file_context("@hello.py fix this")
        assert "--- @hello.py ---" in r
        assert 'print("hi")' in r
        assert "fix this" in r

test("@file: injects file content", t_inject_file)


def t_inject_missing_file():
    import foder.config as c
    from foder.main import _inject_file_context
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        r = _inject_file_context("@nonexistent.py do something")
        assert "do something" in r

test("@file: missing file doesn't crash", t_inject_missing_file)


# ── Snapshot ──────────────────────────────────────────────────────────────────

def t_snapshot():
    import foder.config as c
    import foder.main as m
    with tempfile.TemporaryDirectory() as d:
        c.WORKSPACE = Path(d)
        m._cwd = Path(d)
        (Path(d) / "a.py").write_text("print(1)")
        snap = m._take_snapshot()
        assert "a.py" in snap
        assert snap["a.py"]["size"] > 0

test("snapshot: captures workspace files", t_snapshot)


# ── Theme system ──────────────────────────────────────────────────────────────

def t_themes():
    from foder.main import THEMES, _apply_theme, _A2, _A3
    for key in THEMES:
        _apply_theme(key)
        import foder.main as m
        assert m._A2 == THEMES[key]["A2"], f"theme {key} A2 mismatch"

test("themes: all themes apply correctly", t_themes)


# ── Results ───────────────────────────────────────────────────────────────────

print()
passed = sum(1 for s, _ in results if s == "PASS")
failed = sum(1 for s, _ in results if s == "FAIL")

for status, name in results:
    icon = "✓" if status == "PASS" else "✗"
    print(f"  {icon}  {name}")

print()
print(f"  {passed} passed  ·  {failed} failed  ·  {len(results)} total")
print()

sys.exit(0 if failed == 0 else 1)
