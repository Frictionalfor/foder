"""
Foder on-site test runner.
Runs real tasks against the agent using workspace /home/frictional/Desktop/AAAfree
Requires Ollama to be running.
"""
import sys
import time
from pathlib import Path

# Set workspace before importing foder modules
import foder.config as config
config.WORKSPACE = Path("/home/frictional/Desktop/AAAfree")

from foder.agent import run
from foder.agent import _extract_tool_call

PASS  = "\033[92m PASS \033[0m"
FAIL  = "\033[91m FAIL \033[0m"
INFO  = "\033[94m INFO \033[0m"
RESET = "\033[0m"

results = []

def task(name: str, prompt: str, expect_files: list[str] = None, expect_text: list[str] = None):
    """Run a single task and verify results."""
    print(f"\n{'─'*60}")
    print(f"{INFO} Task: {name}")
    print(f"      Prompt: {prompt}")
    print(f"{'─'*60}")

    history = []
    start   = time.monotonic()

    try:
        token_gen, history = run(prompt, history)
        response = "".join(token_gen)
        elapsed  = time.monotonic() - start
    except Exception as e:
        print(f"{FAIL} Exception: {e}")
        results.append((name, False, str(e)))
        return

    print(f"      Response: {response[:200]}")
    print(f"      Time: {elapsed:.1f}s")
    print(f"      Tool calls: {sum(1 for m in history if m['role'] == 'user' and m['content'].startswith('[tool:'))}")

    passed = True
    errors = []

    # Check expected files exist
    if expect_files:
        for f in expect_files:
            p = config.WORKSPACE / f
            if p.exists():
                print(f"      {PASS} file exists: {f}")
            else:
                print(f"      {FAIL} missing file: {f}")
                passed = False
                errors.append(f"missing: {f}")

    # Check expected text in response
    if expect_text:
        for t in expect_text:
            if t.lower() in response.lower():
                print(f"      {PASS} response contains: '{t}'")
            else:
                print(f"      {FAIL} response missing: '{t}'")
                passed = False
                errors.append(f"response missing: {t}")

    results.append((name, passed, ", ".join(errors) if errors else "ok"))
    print(f"\n  {'PASSED' if passed else 'FAILED'}: {name}")


# ── Run tasks ─────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("  FODER ON-SITE TEST SUITE")
print(f"  workspace: {config.WORKSPACE}")
print("="*60)

# Task 1 — simple file creation
task(
    name="Create Python file",
    prompt='create a python file called greet.py that prints "Hello from Foder"',
    expect_files=["greet.py"],
)

# Task 2 — file with logic
task(
    name="Create calculator",
    prompt="create a python file called calc.py that defines add(a,b) and prints add(3,4)",
    expect_files=["calc.py"],
)

# Task 3 — directory creation
task(
    name="Create directory",
    prompt='create a directory called test-output',
    expect_files=["test-output"],
)

# Task 4 — list files
task(
    name="List workspace files",
    prompt="list all files in the current directory",
    expect_text=["greet", "calc"],
)

# Task 5 — read and modify
task(
    name="Edit existing file",
    prompt='read greet.py and add a second print statement that says "Version 1.0"',
    expect_files=["greet.py"],
)

# Task 6 — C file
task(
    name="Create C file",
    prompt='create a C file called hello.c that prints "Hello from C"',
    expect_files=["hello.c"],
)

# Task 7 — run a command
task(
    name="Run Python file",
    prompt="run greet.py using python3",
    expect_text=["Hello", "Foder"],
)

# ── Summary ───────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("  RESULTS")
print("="*60)

passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)

for name, p, msg in results:
    icon = PASS if p else FAIL
    print(f"  {icon} {name:<30} {msg}")

print(f"\n  {passed} passed  {failed} failed  ({len(results)} total)")
print("="*60 + "\n")

sys.exit(0 if failed == 0 else 1)
