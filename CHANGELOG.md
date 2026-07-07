# Foder — Changelog

All changes tracked by version. Most recent first.

---

## v0.3.0 — 2026-07-07

### Improvements

| # | Feature | Description | Files |
|---|---------|-------------|-------|
| 1 | `file_edit` fuzzy whitespace fallback | When `old_str` isn't found by exact match, a second pass normalises per-line leading whitespace using a regex and retries. Handles the common failure where the model sends slightly different indentation than what's on disk. On failure, returns a nearest-match context snippet so the next attempt is more precise. | `tools/file_edit.py` |
| 2 | `file_read` line range support | New optional `start_line` / `end_line` parameters (1-indexed, inclusive, negative values count from end). Returns a `[lines S-E of N]` header so the agent knows which slice it's reading. Cuts token waste on large files — agent reads only the relevant section before editing. | `tools/file_read.py` |
| 3 | `dir_remove` recursive flag | New optional `recursive` boolean parameter. Without it, non-empty directories return an error listing their contents and instructions to pass `recursive=true`. With it, uses `shutil.rmtree`. Workspace root is always protected regardless of flag. | `tools/dir_remove.py` |
| 4 | `dir_remove` in prompt tool list | `dir_remove` added to `_PROMPT_TOOLS` in the registry so the model sees its new `recursive` parameter in the system prompt. | `tools/registry.py` |
| 5 | System prompt updated | `DIFF-BASED EDITING` rule block updated to mention whitespace-normalisation fallback and `start_line`/`end_line` usage for large files. | `prompt.py` |

### Bug Fixes

| # | Bug | Fix |
|---|-----|-----|
| 1 | `/build` crashes with `rich.errors.MarkupError` on rose theme | `_handle_build` used a typo `[/{_A2}]` as closing tag where the opening tag was `[{_DIM}]`. When theme is rose, `_A2 = #FB7185`, generating `[/#FB7185]` which Rich cannot match. Fixed by rewriting the Panel content as a `Text()` object (no f-string markup). | `main.py` |
| 2 | `/build` result panel used f-string markup for `_A2` | Same class of bug in the "Project generated" success Panel — `out.append(f"  [{_A2}]✓ ...[/{_A2}]")` is invalid inside a `Text` object. Fixed by passing the style as a keyword argument. | `main.py` |
| 3 | `dir_remove` counted entries after `shutil.rmtree` | `len(contents)` was referenced in the success message after the directory was already deleted, which would always return the correct value but was logically unsound. Captured `entry_count` before calling `shutil.rmtree`. | `tools/dir_remove.py` |

### Test Suite

| # | Change | Description |
|---|--------|-------------|
| 1 | `test_unit.py` rewritten as pytest module | Removed module-level `sys.exit()` that caused pytest `INTERNALERROR` on collection. All 42 original tests preserved plus 9 new tests covering the three new tool features. | `tests/test_unit.py` |
| 2 | `test_agent_logic.py` rewritten as pytest module | Same fix — module-level `sys.exit()` removed, all checks converted to `def test_*` functions. | `tests/test_agent_logic.py` |
| 3 | New tests for `file_read` line ranges | `test_tool_file_read_line_range`, `test_tool_file_read_negative_line_range` | `tests/test_unit.py` |
| 4 | New tests for `file_edit` normalization | `test_tool_file_edit_exact_match`, `test_tool_file_edit_normalized_whitespace_fallback`, `test_tool_file_edit_not_found_gives_context_hint` | `tests/test_unit.py` |
| 5 | New tests for `dir_remove` recursive | `test_tool_dir_remove_empty_dir`, `test_tool_dir_remove_non_empty_requires_recursive`, `test_tool_dir_remove_recursive_flag` | `tests/test_unit.py` |
| 6 | Total passing tests | **82 / 82** (up from 42) in 2.3s | — |

---

## v0.2.0 — 2026-06-23

### Major Features

| Feature | Description | Files |
|---------|-------------|-------|
| OpenCode-style agent UI | Structured execution trace: `┌ PLANNING ─┐` box with per-tool icons, state badges (PLANNING / EXECUTING / VERIFYING / DONE), elapsed time | `main.py` |
| Agent state machine | Internal states: IDLE, PLANNING, EXECUTING, VERIFYING, COMPLETED, FAILED — each renders differently in the UI | `main.py` |
| Multi-file project fix | Agent now correctly loops back to LLM after each tool call, enabling full multi-file project generation without stopping early | `agent.py` |
| JSON leak fix | `_strip_tool_json()` rewritten with unlimited-pass loop and no lookahead size cap — ALL tool call JSON removed before display | `agent.py` |
| `/test` command | Auto-detects test framework (pytest / unittest / jest / vitest / go test / cargo test), runs suite, displays pass/fail, auto-suggests fixes on failure | `main.py`, `commands.py` |
| `/refactor <file>` | Targeted diff-based refactor — uses file_edit only, never rewrites whole file, shows confirmation before applying | `main.py`, `commands.py` |
| `/chat <question>` | Lightweight Q&A mode — no tools, no system context overhead, fast responses for simple questions | `main.py`, `commands.py` |
| `/watch [pattern]` | Polling file watcher with 1.5s debounce — triggers agent automatically on file save | `main.py`, `commands.py` |
| `/doctor` | Full system health check: Python version, pip, foder in PATH, ~/.foder structure, Ollama API, installed models, git, foder.json | `commands.py` |
| `/compress` | Summarizes and compresses conversation history into a compact context block to reduce token usage | `main.py`, `commands.py` |
| `/history [query]` | Persistent prompt history saved to `~/.foder/history.jsonl`, searchable by keyword | `main.py`, `commands.py` |
| `foder init` | Interactive project setup wizard — select model, set instructions, choose skill preset, creates `foder.json` | `main.py` |
| `foder --timeout <secs>` | Override `LLM_TIMEOUT` for a single session without env vars | `main.py` |
| `@dir/` multi-file injection | `@src/` injects all relevant files from a directory respecting token budget | `main.py` |
| Skills system v2 | 11 built-in skills (was 6): added `next_app`, `django_backend`, `mobile_app`, `saas_cloner`, `cli_tool` | `skills/` |
| Ollama model auto-detect | On startup, detects which model is actually installed and auto-selects it — no manual config needed | `config.py` |
| Ollama crash recovery | `_run_agent_turn` retries up to 2x on `ConnectError` with 2s backoff | `main.py` |
| `--timeout` flag | `foder --timeout 300` overrides LLM timeout for the session | `main.py` |
| `HISTORY_FILE` + `TEMPLATES_DIR` paths | New paths in config for persistent history and template caching | `config.py` |

### Skills Added

| Skill | Description |
|-------|-------------|
| `next_app` | Next.js 14 App Router + TypeScript + Tailwind CSS |
| `django_backend` | Django + DRF + PostgreSQL + JWT auth |
| `mobile_app` | React Native + Expo Router + TypeScript |
| `saas_cloner` | Clone Instagram / Twitter / Airbnb / Stripe — full-stack |
| `cli_tool` | Python or Node.js CLI with Rich/Commander |

### Bug Fixes

| # | Bug | Fix |
|---|-----|-----|
| 1 | Multi-file projects stop after first file | `agent.py` inner loop now only returns early when leftover text is >10 chars and not a tool call — otherwise loops back to LLM |
| 2 | Tool call JSON leaking into user output | `_strip_tool_json()` rewritten: unlimited passes, no 300-char lookahead limit, handles 20 tool calls per response |
| 3 | `_detect_default_model()` hanging on import | Changed `httpx.get(timeout=3.0)` to explicit `httpx.Timeout(connect=2.0, read=2.0)` — prevents blocking import |
| 4 | `~/.foder/skills/` missing causing doctor FAIL | `/doctor` now auto-creates missing directories instead of failing |
| 5 | `qwen2.5-coder:3b` shown as FAIL when different model installed | Downgraded to `[WARN]` with `[INFO] Auto-using: <model>` message |
| 6 | `OLLAMA_MODEL` env var ignored by `load_project_config` | Fixed precedence check — env var always wins over foder.json |
| 7 | `_TOOL_RESULT_MAX_CHARS = 800` too small for complex outputs | Raised to 1200 — reduces truncation on shell output and file listings |
| 8 | Test runner using deleted workspace path | `run_tests.py` updated to use `~/timepass` — created automatically |
| 9 | `config: foder.json overrides defaults` test failing when OLLAMA_MODEL env set | Test now temporarily unsets env var during assertion |
| 10 | `agent: tool result truncation` test using hardcoded threshold | Test now imports `_TOOL_RESULT_MAX_CHARS` and checks against it |

### Website Updates

| Change | Description |
|--------|-------------|
| Terminal demo fixed | Idle cursor no longer shows "qw" — fixed height container, separated prefix from text, only shows idle cursor after full sequence |
| Emoji removed | `🔒` → `[S]`, `⚛` → `[R]` — standard ASCII only |
| Install commands updated | All install commands now point to `https://foder.vercel.app/install.sh` (official source) |
| `HowItWorks` redesigned | Shows Ollama → Agent → Tools → Workspace → Result flow diagram |
| `Features` upgraded | 9 features with ecosystem badges: Local-First AI, Project Generation, Skills System, File Ops, Shell, Memory, Secure Sandbox, Context Injection, Git-Aware |
| `BuildAnything` upgraded | 6 project categories with skill annotations, SaaS cloner added |
| `Comparison` redesigned | Now compares against OpenCode instead of Claude Code — added rows for project generation, skills system, works without internet |
| `StatsBar` updated | Shows 11 skills, 11 tools, 42 tests, 6 themes, 0 cloud calls, 100% local |
| `Footer` updated | 4-column layout with install strip showing official curl command |
| `Nav` updated | Skills link added |
| Terminal demo added | FastAPI tab added alongside Python, HTML/CSS/JS, Git |

---

## v0.1.0 — 2026-05-01 (initial release)

### Agent Core

| Feature | Description |
|---------|-------------|
| Streaming output | Tokens stream live from Ollama to terminal |
| Tool call detection | Handles bare JSON, fenced JSON, preamble text |
| Code block fallback | Converts `\`\`\`python...` to `file_write` tool call |
| Loop detection | SHA-1 response dedup + per-tool call counter |
| Error recovery | Self-correction with up to 2 retries on tool failure |
| History management | Last 14 turns sent per request, hard cap 60 in memory |

### Tools (11 total)

`file_read` `file_write` `file_edit` `file_delete` `file_rename`
`dir_list` `dir_create` `dir_remove`
`shell_exec` `grep_search` `git_tool`

Plus 30+ tool aliases (`file_create`, `bash`, `mkdir`, `run`, `grep`, etc.)

### CLI

| Feature | Description |
|---------|-------------|
| Interactive REPL | prompt_toolkit with tab completion, history, multi-line input |
| 6 color themes | green, teal, amber, rose, blue, lime — persisted in `~/.foder/theme.json` |
| 3D ASCII logo | Per-character color gradient, cached per theme |
| Shell passthrough | `!cmd`, `!!`, auto-detect for `ls cd git nano vim python3 npm cargo go` |
| `@file` injection | Injects file content into prompt |
| `/pin` / `/unpin` | Pin files to every prompt |
| Session memory | Last 20 messages saved to `~/.foder/session.json` |
| `/undo` / `/diff` | Revert last write, show colored diff |
| `/snapshot` | Save workspace state, diff later |
| `/cost` | Session stats: time, messages, tool calls, ~tokens |
| `/arch` | ASCII architecture diagram |

### Skills System v1 (6 skills)

`react_app` `fastapi_backend` `node_api` `fullstack_app` `auth_system` `database_schema`

Auto-detection: keyword scoring (phrase=3pts, word=1pt, threshold=2pts)

### Memory System

| Layer | Storage | Contents |
|-------|---------|---------|
| Session | RAM | Current conversation |
| Workspace | `.foder/memory.json` | Facts, architecture notes, decisions, instructions |
| User | `~/.foder/preferences.json` | Model, theme, coding style |

### Security

- Workspace path jail (all file ops restricted to WORKSPACE)
- Dangerous command blocklist (`rm -rf /`, `shutdown`, `mkfs`, etc.)
- Risky command confirmation (`sudo`, `apt`, `rm`, `curl`, etc.)
- Shell timeouts + audit log to `~/.foder/audit.log`

### Installers

- `install.sh` — Linux/macOS, detects Python 3.10+, checks Ollama, handles pip install edge cases
- `install.ps1` — Windows PowerShell, mirrors bash installer
- Official source: `https://foder.vercel.app`

---

## Bug History (v0.1.0 development)

| # | Bug | Fix |
|---|-----|-----|
| 1 | `KeyboardInterrupt` crash on `!sudo apt` | Wrapped `proc.wait()` in try/except, added `proc.kill()` cleanup |
| 2 | `KeyboardInterrupt` crash during LLM request | Caught in `chat()` and `chat_stream()`, converted to `LLMError("[interrupted]")` |
| 3 | Rich markup printed as raw text | Replaced f-string markup with `Text.append(..., style=...)` objects |
| 4 | `file_write` creating files instead of dirs | Added `dir_create` tool with `Path.mkdir()` |
| 5 | `cd` sent to agent instead of shell | Added `cd` as direct shell shortcut in REPL loop |
| 6 | Tool call JSON leaking into response | Added `_strip_tool_json()` to clean responses |
| 7 | Double output (stream + Markdown panel) | `_render_response` collects tokens once, renders once |
| 8 | `_TOOL_CALL_MAX_LEN = 512` cutting off large writes | Removed cap, replaced regex with `JSONDecoder.raw_decode()` |
| 9 | Fenced JSON with indentation not detected | Updated `_is_tool_call` to check for `"tool"` + `"parameters"` anywhere |
| 10 | `shell_exec` crash when workspace deleted | Added `if config.WORKSPACE.exists()` check |
| 11 | Theme not persisting | `_logo_cache = None` added to `_apply_theme()` |
| 12 | `_on_tool_call()` takes 2 args but 3 given | Removed extra `None` arg from agent.py call |
| 13 | Tool result shown as final response | Fixed `_build_messages` anchor logic |
| 14 | `dir_create` looping 14 times | Return "already exists" instead of "[ok] Created" on second call |
| 15 | `nano style.css` sent to agent | Added common shell commands to auto-detect list |
| 16 | Token counter `~1.0k` appearing inline | Moved counter before path in prompt label |
| 17 | History contamination across sessions | Fixed turn anchor logic in `_build_messages` |
| 18 | `_is_tool_call` false positive on tool results | Added `startswith("[tool:")` exclusion |
| 19 | File write to wrong dir after `!cd` | `security.py` reads `config.WORKSPACE` dynamically |
| 20 | Ollama cold-load 11 seconds | Added `keep_alive: 10m` to all chat requests |
| 21 | `write/read/write` infinite loop | Added prompt rule: never read a file back to verify after writing |
| 22 | `<full game code here>` written literally | Removed placeholder example from system prompt |
| 23 | `make a python file` triggering `make` | Removed `make`, `python`, `python3` from auto-detect shell list |
| 24 | `list(clean)` streams one character at a time | Fixed to `_stream_tokens([clean])` — one chunk not one char |
| 25 | `file_create` unknown tool | Added 30+ tool aliases to registry |
| 26 | Model narrating instead of acting | Added explicit ban on narration in system prompt |
| 27 | Model stopping after `dir_create` | Prompt rule: after mkdir, immediately write files inside it |
