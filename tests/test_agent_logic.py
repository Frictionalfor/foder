"""
Agent logic unit tests — pytest compatible. No Ollama connection required.

Run with:  pytest tests/test_agent_logic.py -v
"""
import os
import pytest

# Prevent config from making HTTP call at import time
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5-coder:3b")

from foder.agent import (
    _extract_tool_call,
    _strip_tool_json,
    _strip_one_tool_call,
    _is_tool_call,
    _LoopDetector,
    _trim_history,
    _truncate_tool_result,
    _MAX_HISTORY_MESSAGES,
    _TOOL_RESULT_MAX_CHARS,
)


# ── _extract_tool_call ────────────────────────────────────────────────────────

def test_extract_bare_json():
    r = _extract_tool_call('{"tool":"dir_list","parameters":{"path":"."}}')
    assert r is not None and r["tool"] == "dir_list"


def test_extract_with_preamble():
    r = _extract_tool_call('Sure!\n{"tool":"dir_list","parameters":{"path":"."}}')
    assert r is not None and r["tool"] == "dir_list"


def test_extract_fenced_json_block():
    fenced = '```json\n{"tool":"file_read","parameters":{"path":"x"}}\n```'
    r = _extract_tool_call(fenced)
    assert r is not None and r["tool"] == "file_read"


def test_extract_plain_fenced_block():
    fenced = '```\n{"tool":"shell_exec","parameters":{"command":"ls"}}\n```'
    r = _extract_tool_call(fenced)
    assert r is not None and r["tool"] == "shell_exec"


def test_extract_large_payload():
    big_content = "x" * 5000
    big_json = (
        '{"tool":"file_write","parameters":{"path":"f.py","content":"'
        + big_content + '"}}'
    )
    r = _extract_tool_call(big_json)
    assert r is not None and r["tool"] == "file_write"


def test_extract_nested_braces_in_content():
    nested = (
        '{"tool":"file_write","parameters":{"path":"f.py",'
        '"content":"def f():\\n    d = {\\"key\\": \\"val\\"}\\n"}}'
    )
    r = _extract_tool_call(nested)
    assert r is not None


def test_extract_no_false_positive_plain_text():
    assert _extract_tool_call("The file has been created.") is None


def test_extract_no_false_positive_empty_string():
    assert _extract_tool_call("") is None


def test_extract_no_false_positive_tool_result_line():
    assert _extract_tool_call("[tool: file_write]\nresult:\n[ok]") is None


def test_extract_no_false_positive_python_code_block():
    assert _extract_tool_call("Here is the code:\n```python\nprint('hi')\n```") is None


# ── _is_tool_call ─────────────────────────────────────────────────────────────

def test_is_tool_call_bare_json():
    assert _is_tool_call('{"tool":"dir_list","parameters":{"path":"."}}')


def test_is_tool_call_with_preamble():
    assert _is_tool_call('Done!\n{"tool":"dir_list","parameters":{"path":"."}}')


def test_is_tool_call_plain_text_false():
    assert not _is_tool_call("Just a response.")


def test_is_tool_call_tool_result_false():
    assert not _is_tool_call("[tool: file_write]\nresult:\n[ok]")


# ── _strip_tool_json ──────────────────────────────────────────────────────────

def test_strip_single_tool_call():
    single = '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}'
    c = _strip_tool_json(single)
    assert '"tool"' not in c


def test_strip_multi_file_two_tool_calls():
    multi = (
        '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\n'
        '{"tool":"file_write","parameters":{"path":"b.py","content":"y"}}'
    )
    c = _strip_tool_json(multi)
    assert '"tool"' not in c


def test_strip_large_content():
    big = '{"tool":"file_write","parameters":{"path":"f.py","content":"' + "x" * 500 + '"}}'
    c = _strip_tool_json(big)
    assert '"tool"' not in c


def test_strip_plain_text_preserved():
    plain = "Done! Created greet.py. Run: python3 greet.py"
    assert _strip_tool_json(plain) == plain


def test_strip_mixed_json_and_text():
    mixed = '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\nDone! File created.'
    c = _strip_tool_json(mixed)
    assert '"tool"' not in c
    assert "Done" in c


def test_strip_triple_tool_calls():
    triple = (
        '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\n'
        '{"tool":"file_write","parameters":{"path":"b.py","content":"y"}}\n'
        '{"tool":"shell_exec","parameters":{"command":"python a.py"}}'
    )
    c = _strip_tool_json(triple)
    assert '"tool"' not in c


# ── _strip_one_tool_call ──────────────────────────────────────────────────────

def test_strip_one_removes_first_keeps_second():
    multi = (
        '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\n'
        '{"tool":"file_write","parameters":{"path":"b.py","content":"y"}}'
    )
    after = _strip_one_tool_call(multi)
    # The second tool call must still be present
    assert '"tool"' in after


# ── _LoopDetector ─────────────────────────────────────────────────────────────

def test_loop_detector_first_response_no_trigger():
    ld = _LoopDetector()
    assert ld.check_response("response A") is None


def test_loop_detector_different_response_no_trigger():
    ld = _LoopDetector()
    ld.check_response("response A")
    assert ld.check_response("response B") is None


def test_loop_detector_repeated_response_triggers():
    ld = _LoopDetector()
    ld.check_response("response B")
    msg = ld.check_response("response B")   # second identical → streak=2
    assert msg is not None


def test_loop_detector_tool_first_call_no_trigger():
    ld = _LoopDetector()
    assert ld.record_tool("file_write", {"path": "a.py"}) is None


def test_loop_detector_tool_second_call_no_trigger():
    ld = _LoopDetector()
    ld.record_tool("file_write", {"path": "a.py"})
    assert ld.record_tool("file_write", {"path": "a.py"}) is None


def test_loop_detector_tool_third_call_no_trigger():
    ld = _LoopDetector()
    for _ in range(3):
        result = ld.record_tool("file_write", {"path": "a.py"})
    assert result is None


def test_loop_detector_tool_fourth_call_triggers():
    ld = _LoopDetector()
    for _ in range(4):
        msg = ld.record_tool("file_write", {"path": "a.py"})
    assert msg is not None


# ── _trim_history ─────────────────────────────────────────────────────────────

def test_history_trim_capped_at_limit():
    big_hist = [{"role": "user", "content": str(i)} for i in range(100)]
    trimmed  = _trim_history(big_hist)
    assert len(trimmed) <= _MAX_HISTORY_MESSAGES


def test_history_trim_keeps_latest_messages():
    big_hist = [{"role": "user", "content": str(i)} for i in range(100)]
    trimmed  = _trim_history(big_hist)
    assert trimmed[-1]["content"] == "99"


# ── _truncate_tool_result ─────────────────────────────────────────────────────

def test_truncate_short_result_unchanged():
    short = "short result"
    assert _truncate_tool_result(short) == short


def test_truncate_long_result_shortened():
    long_r = "x" * 2000
    t = _truncate_tool_result(long_r)
    assert len(t) < 2000
    assert "truncated" in t
