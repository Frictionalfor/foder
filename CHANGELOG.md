# Foder — Changelog & Bug Tracker

All bugs fixed, features added, and improvements made during development.

---

## Bug Fixes

| # | Bug | Symptom | Fix | File |
|---|-----|---------|-----|------|
| 1 | `KeyboardInterrupt` crash on `!sudo apt` | Full traceback on Ctrl+C during shell command | Wrapped `proc.wait()` in `try/except KeyboardInterrupt`, added `proc.kill(); proc.wait()` cleanup | `main.py` |
| 2 | `KeyboardInterrupt` crash during LLM request | Traceback from deep inside `httpx` socket read | Caught `KeyboardInterrupt` inside `chat()` and `chat_stream()`, converted to `LLMError("[interrupted]")` | `llm.py` |
| 3 | `[dim]cancelled[/dim]` printed as raw text | Rich markup tags visible in terminal output | Replaced f-string markup with `Text.append(..., style=_DIM)` — `Text` objects don't parse markup strings | `main.py` |
| 4 | `file_write` creating files instead of directories | `mkdir Todo-List` created a file named `Todo-List` | Added `dir_create` tool with proper `Path.mkdir()` implementation | `tools/dir_create.py` |
| 5 | `cd Todo-List` going to agent instead of shell | User typed `cd` without `!`, agent tried to execute it | Added `cd` as a direct shell shortcut in the REPL loop | `main.py` |
| 6 | Tool call JSON leaking into final response | Raw `{"tool": "file_write", ...}` printed as output | Added `_strip_tool_json()` to clean model responses before display | `agent.py` |
| 7 | Double output — plain text + markdown panel | Response rendered twice (streamed + re-rendered in panel) | Changed `_render_response` to collect tokens silently, render once | `main.py` |
| 8 | `_TOOL_CALL_MAX_LEN = 512` cutting off large file writes | Model's `file_write` with full file content not detected as tool call | Removed length cap, replaced regex with `json.JSONDecoder.raw_decode()` | `agent.py` |
| 9 | Fenced JSON with indentation not detected | `\`\`\`json\n    {"tool":...}` not recognized as tool call | Updated `_looks_like_tool_call` to check for `"tool"` + `"parameters"` anywhere in buffer | `agent.py` |
| 10 | `shell_exec` crash when workspace dir deleted | `[Errno 2] No such file or directory` on temp dir cleanup | Added `if config.WORKSPACE.exists()` check, fallback to `None` cwd | `tools/shell_exec.py` |
| 11 | Theme not persisting across restarts | Saved blue theme, reopened foder, got green | Stale `_LOGO_COLORS = [green values]` line after `_apply_theme()` overwrote the loaded theme | `main.py` |
| 12 | `[#6B7280]you[/#6B7280]` printed as raw text | Markup tags visible in "you ›" prompt prefix | Replaced f-string markup with `Text.append(..., style=_DIM)` | `main.py` |
| 13 | `_on_tool_call() takes 2 positional arguments but 3 were given` | Crash on every agent tool call | `agent.py` was calling `on_tool_call(name, params, None)` — removed extra arg | `agent.py` |
| 14 | Tool result text shown as final response | `[tool: file_write] parameters: {...} result: [ok]` printed as answer | Fixed `_build_messages` to strip old tool results and anchor current turn correctly | `agent.py` |
| 15 | `dir_create` looping 14 times | Model kept calling `dir_create` because `exist_ok=True` always returned `[ok] Created` | Added check: if directory already exists, return `[ok] Directory already exists` | `tools/dir_create.py` |
| 16 | `nano style.css` sent to agent instead of shell | User typed shell command without `!`, agent tried to write a file | Added auto-detection of common shell commands (`nano`, `vim`, `cat`, `git`, `ls`, etc.) | `main.py` |
| 17 | Token counter `~1.0k` appearing inline with typed text | `~1.0k` appended after `❯` cursor, overlapping user input | Moved token counter before the path in prompt label, not after cursor | `main.py` |
| 18 | History contamination across sessions | Old tool results from previous session shown as final answer | `_build_messages` was anchoring to first-ever user message; fixed to anchor current turn only | `agent.py` |
| 19 | `_is_tool_call` false positive on tool results | Tool result messages in history matched `"tool"` + `"parameters"` check | Added `startswith("[tool:")` exclusion to `_is_tool_call` | `agent.py` |
| 20 | Model writing files to wrong directory after `!cd` | `file_write` used static `WORKSPACE` set at startup | Made `security.py` read `config.WORKSPACE` dynamically; `!cd` now updates `config.WORKSPACE` | `main.py`, `security.py` |
| 21 | Ollama model cold-load taking 11 seconds | Every new session reloaded model from disk | Added `keep_alive: 10m` to all chat requests; model stays warm between sessions | `llm.py` |
| 22 | `write/read/write` infinite loop on file tasks | Model wrote file, read it back to verify, rewrote, repeated | Added prompt rule: "After writing a file, do NOT read it back to verify" | `prompt.py` |
| 23 | `<full game code here>` written to file literally | Prompt example used placeholder text, model copied it | Removed the bad example from system prompt | `prompt.py` |
| 24 | `_logo_cache` not invalidated on theme change | Logo stayed old color after `/theme` switch | Added `_logo_cache = None` in `_apply_theme()` | `main.py` |

---

## Features Added

| # | Feature | Description | Added in |
|---|---------|-------------|----------|
| 1 | Streaming output | Tokens stream to terminal as they arrive from Ollama | agent.py rewrite |
| 2 | Model auto-detection | On startup, detects all Ollama models and shows picker if configured model not found | main.py |
| 3 | `/switch` command | Change model mid-session without restarting | main.py |
| 4 | `!` shell passthrough | Run any terminal command with `!` prefix | main.py |
| 5 | `!cd` directory navigation | Changes working directory for the session, updates workspace | main.py |
| 6 | `!!` re-run last command | Re-executes the previous shell command | main.py |
| 7 | Auto shell detection | Common commands (`ls`, `cd`, `git`, `nano`, etc.) work without `!` | main.py |
| 8 | Tab completion | `/` commands and `@filenames` complete on Tab | main.py |
| 9 | Ctrl+R history search | Persistent prompt history across sessions | main.py |
| 10 | `@file` context injection | `@filename` injects file content into prompt | main.py |
| 11 | `/pin` / `/unpin` | Pin files to be injected into every prompt automatically | main.py |
| 12 | Session memory | Last 20 messages saved to `~/.foder/session.json`, resumed on next start | main.py |
| 13 | `/undo` | Reverts last file write | main.py |
| 14 | `/diff` | Shows colored diff of last file write | main.py |
| 15 | `/run` | Auto-detects project type and runs it | main.py |
| 16 | `/git` | Rich git status panel with branch, changes, recent commits | main.py |
| 17 | `/snapshot` + `/snapshot diff` | Save workspace state, compare changes | main.py |
| 18 | `/cost` | Session stats: time, messages, tool calls, files written, ~tokens | main.py |
| 19 | `/arch` | ASCII architecture diagram | main.py |
| 20 | `/theme` | 6 color themes (green, teal, amber, rose, blue, lime), persisted | main.py |
| 21 | 3D logo | Per-character color gradient with extrusion shadow effect | main.py |
| 22 | Colored `ls` | Directories, files, scripts colored by type | main.py |
| 23 | `dir_create` tool | Proper directory creation (separate from file_write) | tools/dir_create.py |
| 24 | `foder.json` project config | Per-project config loaded on startup and on `cd` | config.py |
| 25 | `foder "prompt"` CLI mode | Non-interactive single-prompt execution | main.py |
| 26 | Multi-line input | Lines ending with `\` continue on next line | main.py |
| 27 | Token counter in prompt | Shows `~1.0k` estimate when context grows | main.py |
| 28 | Git branch in prompt | Shows current branch next to path | main.py |
| 29 | Risky command confirmation | `sudo`, `rm`, `apt` etc. ask before running | main.py |
| 30 | Timeout confirmation | Long-running commands ask before terminating | main.py |
| 31 | Model unload on exit | `/exit` sends `keep_alive: 0` to free RAM | llm.py |
| 32 | `update.sh` | Auto-updater: pulls latest git, reinstalls | update.sh |
| 33 | History trimming | Only last 10 messages sent per LLM request | agent.py |
| 34 | Tool result truncation | Tool results capped at 500 chars in history | agent.py |
| 35 | Logo caching | 3D logo computed once per theme, cached | main.py |
| 36 | 42-test suite | Full test coverage: imports, config, security, tools, agent, session, prompt, themes | test_foder.py |

---

## Known Limitations

| # | Limitation | Notes |
|---|-----------|-------|
| 1 | Generation speed | Depends on hardware and model size. Use `qwen2.5-coder:3b` for speed |
| 2 | Multi-file projects | 3b model sometimes stops after 1-2 files. Use 7b or break into smaller tasks |
| 3 | Interactive TUI apps | `nano`, `vim` open but may have display issues inside foder's terminal handling |
| 4 | Windows support | Tested primarily on Linux. Windows install script provided but less tested |
