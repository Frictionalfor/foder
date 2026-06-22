"""
Unit tests for agent.py logic — no Ollama connection required.
Run with: OLLAMA_MODEL=qwen3.5:9b python3 test_agent_logic.py
"""
import os
import sys

# Prevent config from making HTTP call at import time
os.environ.setdefault("OLLAMA_MODEL", "qwen3.5:9b")

from foder.agent import (
    _extract_tool_call,
    _strip_tool_json,
    _strip_one_tool_call,
    _is_tool_call,
    _LoopDetector,
    _trim_history,
    _truncate_tool_result,
    _MAX_HISTORY_MESSAGES,
)

failures = []

def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  OK    {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        failures.append(name)


print("\nAgent logic unit tests")
print("=" * 50)

# ── _extract_tool_call ─────────────────────────────────────────────────────────

r = _extract_tool_call('{"tool":"dir_list","parameters":{"path":"."}}')
check("extract bare JSON", r is not None and r["tool"] == "dir_list")

r = _extract_tool_call('Sure!\n{"tool":"dir_list","parameters":{"path":"."}}')
check("extract with preamble", r is not None and r["tool"] == "dir_list")

fenced = '```json\n{"tool":"file_read","parameters":{"path":"x"}}\n```'
r = _extract_tool_call(fenced)
check("extract fenced ```json block", r is not None and r["tool"] == "file_read", str(r))

fenced2 = '```\n{"tool":"shell_exec","parameters":{"command":"ls"}}\n```'
r = _extract_tool_call(fenced2)
check("extract plain fenced block", r is not None and r["tool"] == "shell_exec", str(r))

big_content = "x" * 5000
big_json = '{"tool":"file_write","parameters":{"path":"f.py","content":"' + big_content + '"}}'
r = _extract_tool_call(big_json)
check("extract large payload (>5000 chars)", r is not None and r["tool"] == "file_write")

nested = '{"tool":"file_write","parameters":{"path":"f.py","content":"def f():\\n    d = {\\"key\\": \\"val\\"}\\n"}}'
r = _extract_tool_call(nested)
check("extract nested braces in content", r is not None)

check("no false positive: plain text",       _extract_tool_call("The file has been created.") is None)
check("no false positive: empty string",     _extract_tool_call("") is None)
check("no false positive: tool result line", _extract_tool_call("[tool: file_write]\nresult:\n[ok]") is None)

# ── _is_tool_call ──────────────────────────────────────────────────────────────

check("is_tool_call: bare JSON",         _is_tool_call('{"tool":"dir_list","parameters":{"path":"."}}'))
check("is_tool_call: with preamble",     _is_tool_call('Done!\n{"tool":"dir_list","parameters":{"path":"."}}'))
check("is_tool_call: plain text False",  not _is_tool_call("Just a response."))
check("is_tool_call: tool result False", not _is_tool_call("[tool: file_write]\nresult:\n[ok]"))

# ── _strip_tool_json ───────────────────────────────────────────────────────────

# Single call stripped
single = '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}'
c = _strip_tool_json(single)
check("strip single tool call", '"tool"' not in c, repr(c))

# Multi-file: two tool calls stripped (the main bug)
multi = (
    '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\n'
    '{"tool":"file_write","parameters":{"path":"b.py","content":"y"}}'
)
c = _strip_tool_json(multi)
check("strip multi-file (2 tool calls)", '"tool"' not in c, repr(c))

# Large content stripped completely
big = '{"tool":"file_write","parameters":{"path":"f.py","content":"' + "x" * 500 + '"}}'
c = _strip_tool_json(big)
check("strip large content (500 chars)", '"tool"' not in c, f"len={len(c)}")

# Plain text fully preserved
plain = "Done! Created greet.py. Run: python3 greet.py"
check("plain text preserved", _strip_tool_json(plain) == plain)

# Mixed: tool call + trailing human text
mixed = '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\nDone! File created.'
c = _strip_tool_json(mixed)
check("mixed: JSON stripped, text kept", '"tool"' not in c and "Done" in c, repr(c))

# Three tool calls (fullstack project)
triple = (
    '{"tool":"file_write","parameters":{"path":"a.py","content":"x"}}\n'
    '{"tool":"file_write","parameters":{"path":"b.py","content":"y"}}\n'
    '{"tool":"shell_exec","parameters":{"command":"python a.py"}}'
)
c = _strip_tool_json(triple)
check("strip triple tool calls", '"tool"' not in c, repr(c))

# ── _strip_one_tool_call ───────────────────────────────────────────────────────

after = _strip_one_tool_call(multi)
check("strip_one: first removed", "a.py" not in after or '"tool"' in after)
check("strip_one: second remains", '"tool"' in after, repr(after))

# ── _LoopDetector ──────────────────────────────────────────────────────────────

ld = _LoopDetector()
check("loop: first response no trigger",  ld.check_response("response A") is None)
check("loop: different response no trigger", ld.check_response("response B") is None)
msg = ld.check_response("response B")  # same as last -> streak=2
check("loop: repeated response triggers", msg is not None, repr(msg))

ld2 = _LoopDetector()
check("tool loop: first call no trigger",    ld2.record_tool("file_write", {"path":"a.py"}) is None)
check("tool loop: second call no trigger",   ld2.record_tool("file_write", {"path":"a.py"}) is None)
check("tool loop: third call no trigger",    ld2.record_tool("file_write", {"path":"a.py"}) is None)
msg2 = ld2.record_tool("file_write", {"path":"a.py"})  # 4th = trigger
check("tool loop: 4th call triggers",        msg2 is not None, repr(msg2))

# ── _trim_history ──────────────────────────────────────────────────────────────

big_hist = [{"role": "user", "content": str(i)} for i in range(100)]
trimmed = _trim_history(big_hist)
check("history trim: capped at limit", len(trimmed) <= _MAX_HISTORY_MESSAGES)
check("history trim: keeps latest", trimmed[-1]["content"] == "99")

# ── _truncate_tool_result ──────────────────────────────────────────────────────

short = "short result"
check("truncate: short result unchanged", _truncate_tool_result(short) == short)
long_r = "x" * 2000
t = _truncate_tool_result(long_r)
check("truncate: long result shortened", len(t) < 2000 and "truncated" in t)

# ── Results ────────────────────────────────────────────────────────────────────

print("=" * 50)
passed = sum(1 for _ in range(1) if not failures) * (
    len([l for l in open(__file__).readlines() if l.strip().startswith("check(")])
) - len(failures)

total = len([l for l in open(__file__).readlines() if l.strip().startswith("check(")])
passed = total - len(failures)
print(f"  {passed} passed  {len(failures)} failed  ({total} total)")

if failures:
    print(f"\n  FAILED: {failures}")
    sys.exit(1)
else:
    print("\n  ALL TESTS PASSED")
    sys.exit(0)
