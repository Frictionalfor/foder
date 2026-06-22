# Foder — System Design Document

Complete technical specification for the Foder ecosystem.
Local-first AI coding agent powered entirely by Ollama.

---

## 1. Product Vision

Foder is an **OpenCode-class developer agent** that runs 100% locally.

**Non-negotiable constraints:**
- All AI inference through local Ollama models only
- No OpenAI / Anthropic / Gemini / cloud API calls
- Works fully offline once installed
- Zero data leaves the user's machine

**Target experience:** "OpenCode UX — but fully self-hosted and offline."

---

## 2. Architecture Overview

```
  User Input (terminal)
        |
  ┌─────▼──────────────────────────────────────────────────┐
  │  FODER CLI  (main.py)                                  │
  │  REPL + OpenCode-style trace UI + slash commands       │
  │  Agent state: IDLE / PLANNING / EXECUTING / DONE       │
  └──────┬──────────────────────────┬──────────────────────┘
         |                          |
  ┌──────▼──────┐          ┌────────▼────────────────────┐
  │  CONTEXT    │          │  AGENT LOOP  (agent.py)     │
  │  ENGINE     │          │  plan -> tool -> verify     │
  │  (context)  │          │  -> retry -> final response │
  └──────┬──────┘          └────────┬────────────────────┘
         |                          |
  ┌──────▼──────┐          ┌────────▼────────────────────┐
  │  MEMORY     │          │  TOOL REGISTRY              │
  │  3 layers   │          │  11 tools + 30 aliases      │
  │  (memory)   │          │  file / dir / shell / git   │
  └─────────────┘          └────────┬────────────────────┘
                                     |
  ┌──────────────────────────────────▼────────────────────┐
  │  OLLAMA  (local LLM — no cloud)                       │
  │  qwen2.5-coder / qwen3 / deepseek-coder / llama /    │
  │  mistral / codellama / phi3 / any pulled model        │
  └───────────────────────────────────────────────────────┘

  Skills:  ~/.foder/skills/  +  ./skills/  +  built-in /skills/
  Memory:  session(RAM)  +  workspace(.foder/)  +  user(~/.foder/)
  Security: workspace jail  +  command blocklist  +  audit log
```

---

## 3. Agent Loop Design

### State Machine

```
IDLE -> PLANNING -> EXECUTING -> VERIFYING -> COMPLETED
                              \-> FAILED -> retry -> EXECUTING
```

**State transitions:**

| From | To | Trigger |
|------|----|---------|
| IDLE | PLANNING | User sends a prompt |
| PLANNING | EXECUTING | LLM returns first tool call |
| EXECUTING | EXECUTING | Tool succeeds, more tool calls in response |
| EXECUTING | VERIFYING | All tool calls executed, checking results |
| VERIFYING | COMPLETED | No errors in results |
| VERIFYING | FAILED | Error detected in tool result |
| FAILED | EXECUTING | Self-correction prompt sent, LLM retries |
| FAILED | COMPLETED | Max retries reached, bail out gracefully |
| EXECUTING | COMPLETED | LLM returns plain text (no tool call) |

### Loop Implementation (agent.py)

```
for iteration in range(MAX_ITERATIONS):
    raw = collect_full_llm_response()       # synchronous collect

    # Loop detection (2 layers)
    if response_is_identical_to_last():
        inject_breakout_prompt(); get_final_answer(); return

    tool_call = extract_tool_call(raw)

    if tool_call is None:                   # final answer
        return strip_json(raw)

    # Execute ALL tool calls in this response
    while has_more_tool_calls(remaining):
        if same_tool_called_N_times():      # loop detection layer 2
            inject_breakout_prompt(); return
        result = dispatch(tool_call)
        store_in_history(tool_call, result)
        remaining = strip_one_tool_call(remaining)

    # Check leftover natural language
    leftover = strip_all_json(remaining)
    if leftover and len(leftover) > 10:
        return leftover                     # final answer

    # Otherwise: loop back — LLM will write next file/call next tool
    continue
```

**Key design decision:** the loop only returns early on a genuine final answer (>10 chars of human-readable text). This enables multi-file project generation — the LLM writes file 1, loop continues, LLM writes file 2, etc.

### Tool Call Extraction

Priority order:
1. Fenced JSON block: ` ```json {"tool":...} ``` `
2. Bare JSON object: `{"tool":..., "parameters":...}`
3. JSON with preamble: `Sure! {"tool":...}`
4. Code block fallback: ` ```python\n<code>\n``` ` → synthesized `file_write`

All extraction uses `json.JSONDecoder.raw_decode()` — no regex size limits.

---

## 4. Tool System

### Tool Registry (tools/registry.py)

All tools share the interface:
```python
SCHEMA: dict           # name, description, parameters, required
execute(**kwargs) -> str  # always returns string, never raises
```

### Tools

| Tool | Category | Description |
|------|----------|-------------|
| `file_read` | FILE | Read file contents |
| `file_write` | FILE | Write / create file (creates parent dirs) |
| `file_edit` | FILE | Patch-based edit: replace old_str with new_str |
| `file_delete` | FILE | Delete a file |
| `file_rename` | FILE | Rename or move a file |
| `dir_list` | DIR | List directory contents |
| `dir_create` | DIR | Create directory (idempotent) |
| `dir_remove` | DIR | Remove empty directory |
| `shell_exec` | SHELL | Run shell command with timeout |
| `grep_search` | SEARCH | Pattern search across files (ripgrep + Python fallback) |
| `git_tool` | GIT | git status / diff / log / add / commit / checkout |

### Tool Aliases (30+)

Models use different names. All are mapped transparently:

```
file_create, write_file, create_file  -> file_write
read_file, read                        -> file_read
edit_file, patch_file, str_replace     -> file_edit
bash, run, exec, run_command           -> shell_exec
mkdir, create_dir                      -> dir_create
ls, list_dir, list_files               -> dir_list
grep, search, ripgrep                  -> grep_search
git, git_status, git_diff              -> git_tool
```

### Security Layer (security.py)

**Path jail:** `validate_path(raw)` resolves the path and checks it stays inside `config.WORKSPACE`. Reads `config.WORKSPACE` dynamically so `cd` changes are respected.

**Command blocklist:** Absolute blocks regardless of context:
```
rm -rf /    rm -rf ~    mkfs    dd if=
shutdown    reboot      halt    poweroff
:(){ :|:& };:    chmod -R 777 /    format
```

**Risky commands** (ask confirmation):
`sudo apt rm mv chmod chown curl wget systemctl kill pkill pip install npm install`

**Audit log:** every tool call logged to `~/.foder/audit.log` as JSON.

---

## 5. Skills System

### Architecture

```
User request
    |
detect_skill(text)   <- keyword scoring: phrase=3pts, word=1pt, threshold=2
    |
inject_skill(prompt, skill)   <- prepends structured instructions
    |
Agent loop runs with enhanced context
```

### Skill JSON Format

```json
{
  "name": "skill_name",
  "version": "1.0.0",
  "description": "...",
  "tags": ["tag1", "tag2"],
  "intent_keywords": ["phrase match", "word"],
  "steps": ["Step 1", "Step 2"],
  "best_practices": ["Practice 1"],
  "templates": {
    "filename": "content"
  },
  "system_prompt_injection": "Injected before user message."
}
```

### Skill Search Paths (priority order)

1. `<workspace>/skills/` — project-level (highest priority)
2. `~/.foder/skills/` — user-level
3. `<package>/skills/` — built-in (lowest priority, always available)

### Built-in Skills (11)

| Skill | Stack |
|-------|-------|
| `react_app` | React 18 + Vite + Tailwind + React Router v6 |
| `next_app` | Next.js 14 App Router + TypeScript + Tailwind |
| `fastapi_backend` | FastAPI + SQLAlchemy + Pydantic v2 + JWT |
| `django_backend` | Django 5 + DRF + PostgreSQL + JWT |
| `node_api` | Express + better-sqlite3 + Zod + JWT |
| `fullstack_app` | React frontend + FastAPI/Express backend |
| `saas_cloner` | Instagram / Twitter / Airbnb / Stripe clone |
| `mobile_app` | React Native + Expo Router + TypeScript |
| `auth_system` | JWT auth added to any existing project |
| `database_schema` | SQLAlchemy models + migrations + seed data |
| `cli_tool` | Python (Rich/Typer) or Node.js (Commander) CLI |

---

## 6. Memory System

### Three Layers

| Layer | File | Scope | Contents |
|-------|------|-------|---------|
| Session | RAM only | Current session | Conversation history (list[dict]) |
| Workspace | `<ws>/.foder/memory.json` | Per project | Facts, architecture notes, decisions, standing instructions |
| User | `~/.foder/preferences.json` | Global | Model preference, theme, coding style |

### Session Memory

- Last 14 turns sent to LLM per request (`_RECENT_TURNS = 14`)
- Hard cap: 60 messages in memory (`_MAX_HISTORY_MESSAGES = 60`)
- Tool results truncated to 1200 chars in history to prevent bloat
- Saved to `~/.foder/session.json` (last 20 messages) on every agent turn

### Workspace Memory

Stored in `<workspace>/.foder/memory.json`. Injected into system prompt when non-empty:

```
WORKSPACE MEMORY:
PROJECT FACTS:
- this project uses PostgreSQL, not SQLite
ARCHITECTURE:
  monorepo: React in /frontend, FastAPI in /api
STANDING INSTRUCTIONS:
  always use type hints and docstrings
```

### Persistent History

All user prompts appended to `~/.foder/history.jsonl` (one JSON object per line):
```json
{"ts": 1719123456, "prompt": "build a fastapi backend"}
```

Searchable via `/history [query]`.

---

## 7. Context Engine

### Project Detection (context.py)

Scans workspace for marker files:

| Detected | Markers |
|----------|---------|
| Python | `pyproject.toml`, `setup.py`, `requirements.txt` |
| FastAPI | `requirements.txt` contains "fastapi" |
| Django | `requirements.txt` contains "django" |
| Node.js | `package.json` |
| Next.js | `package.json` contains `"next"` |
| React | `package.json` contains `"react"` |
| Go | `go.mod` |
| Rust | `Cargo.toml` |
| Java | `pom.xml`, `build.gradle` |
| Docker | `Dockerfile`, `docker-compose.yml` |

Detection result injected into system prompt:
```
PROJECT: python/fastapi · pkg:pip · test:pytest · build:setuptools/build
ENTRY POINTS: main.py, app.py
TEST FRAMEWORK: pytest
```

### Smart File Selection

`find_relevant_files(query, max_files=10)` scoring:
- Token match in file path: +2pts per token
- Token match in filename: +1pt per token
- Language extension match (e.g. "python" → .py): +1.5pts
- High-value file (README, package.json, etc.): +0.5pts
- Recently modified (<24h): +0.3pts

Ignored directories: `.git __pycache__ node_modules .venv dist build .next target vendor`

---

## 8. LLM Client (llm.py)

### Timeout Strategy

```python
per_token_timeout = max(30.0, LLM_TIMEOUT / 4)   # idle timeout per token
wall_clock_deadline = now + LLM_TIMEOUT            # hard total deadline

httpx.Timeout(
    connect = 10.0,
    read    = per_token_timeout,   # resets on each received token
    write   = 10.0,
    pool    = 10.0,
)
```

Slow-but-alive models work fine (read timeout resets per token). Truly stalled streams are killed.

### Model Keep-Alive

Every request includes `"keep_alive": "10m"` — Ollama keeps the model loaded between requests. On `/exit`, sends `"keep_alive": 0` to free RAM immediately.

### Crash Recovery

`_run_agent_turn()` retries up to 2x on `ConnectError` with 2s sleep between attempts. This handles Ollama restarts and brief disconnections without losing the session.

### Model Auto-Detection

`_detect_default_model()` in `config.py`:
1. If `OLLAMA_MODEL` env var is set — use it, skip detection
2. Query `GET /api/tags` with 2s timeout
3. If configured model is installed — use it
4. Otherwise prefer in order: `qwen2.5-coder` > `deepseek-coder` > `codellama` > `qwen3` > `qwen2.5` > `llama3` > `mistral` > first available
5. Called lazily inside `load_project_config()` — never blocks import

---

## 9. CLI System (main.py + cli.py)

### Entry Points

```
foder                    interactive REPL
foder "prompt"           single-turn non-interactive
foder init               project setup wizard
foder --help             structured help output
foder --update           git pull + pip reinstall (preserves ~/.foder/)
foder --uninstall        pip uninstall + optional ~/.foder/ removal
foder --timeout <secs>   override LLM_TIMEOUT for this session
```

### REPL Loop

```
PromptSession (prompt_toolkit)
    |
input parsing:
    - "/" prefix  -> slash command handler
    - "!" prefix  -> shell execution
    - "!!" -> re-run last shell command
    - known shell cmd (ls, cd, git, ...) -> shell execution
    - anything else -> @file injection + skill detection + agent turn
```

### OpenCode-Style Execution Trace

When the agent executes tools, the UI renders:

```
  ┌ PLANNING ──────────────────────────────────────────────┐
  ◆ write   src/app.py
      [ok] written
  $ exec    pip install -r requirements.txt
      > Successfully installed fastapi uvicorn
      [ok]
  ◆ write   src/models.py
      [ok] written
  ◆ write   src/routers/auth.py
      [ok] written
  └──────────────────────────────────────────────────────┘  4 tool(s) · 18.3s  DONE

  ◆ foder  Project created. Run: uvicorn src.app:app --reload
```

State badges: `planning` (cyan) / `executing` (green) / `verifying` (white) / `DONE` (green) / `FAILED` (red)

Tool icons:
```
◆  file_write     (green)
◎  file_read      (green)
◈  file_edit      (green)
$  shell_exec     (amber)
⎇  git_tool       (cyan)
?  grep_search    (cyan)
≡  dir_list       (dim)
+  dir_create     (green)
```

### Prompt Label

```
qwen3.5 ❙ [~2.1k] main · foder/src ❯
```

Components:
- Model name (short, no tag)
- Token estimate (shown when >500 tokens)
- Git branch (when in git repo)
- Workspace-relative path
- Prompt cursor

---

## 10. Configuration

### Priority (highest to lowest)

1. Environment variable (`OLLAMA_MODEL`, `FODER_WORKSPACE`, etc.)
2. `foder.json` in workspace root
3. Built-in defaults

### foder.json Schema

```json
{
  "model": "qwen2.5-coder:7b",
  "instructions": "This project uses Python 3.12, FastAPI, PostgreSQL.",
  "max_iterations": 15,
  "llm_timeout": 300,
  "shell_timeout": 60,
  "indexing": false,
  "default_skill": "fastapi_backend"
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | auto-detected | Model to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `FODER_WORKSPACE` | `cwd` | Workspace root |
| `FODER_MAX_ITER` | `20` | Max agent loop iterations |
| `FODER_LLM_TIMEOUT` | `600` | LLM timeout (seconds) |
| `FODER_SHELL_TIMEOUT` | `30` | Shell command timeout |
| `FODER_INSTRUCTIONS` | empty | Custom system prompt suffix |

---

## 11. File Structure

```
foder/
├── foder/
│   ├── main.py          REPL + OpenCode UI + all slash command handlers
│   ├── agent.py         agent loop + multi-file support + JSON clean
│   ├── llm.py           Ollama HTTP client + streaming + crash recovery
│   ├── prompt.py        system prompt builder + planning/review/explain prompts
│   ├── config.py        config loading + model auto-detection
│   ├── context.py       project detection + smart file selection
│   ├── memory.py        3-layer memory (session + workspace + user)
│   ├── skills.py        skill engine + intent detection + /build mode
│   ├── commands.py      all slash command implementations
│   ├── cli.py           --help / --update / --uninstall
│   ├── audit.py         tool call audit logging
│   ├── security.py      path jail + command blocklist
│   └── tools/
│       ├── registry.py      dispatch + aliases + TOOL_SCHEMAS
│       ├── file_read.py
│       ├── file_write.py    creates parent dirs automatically
│       ├── file_edit.py     str_replace patch-based editing
│       ├── file_delete.py
│       ├── file_rename.py
│       ├── dir_list.py
│       ├── dir_create.py    idempotent mkdir
│       ├── dir_remove.py
│       ├── shell_exec.py    timeout + workspace cwd
│       ├── grep_search.py   ripgrep + Python fallback
│       └── git_tool.py
├── skills/
│   ├── react_app.json
│   ├── next_app.json
│   ├── fastapi_backend.json
│   ├── django_backend.json
│   ├── node_api.json
│   ├── fullstack_app.json
│   ├── saas_cloner.json
│   ├── mobile_app.json
│   ├── auth_system.json
│   ├── database_schema.json
│   └── cli_tool.json
├── foder-website/           separate git repo -> github.com/Frictionalfor/foder-website
├── install.sh               Linux/macOS installer (official: foder.vercel.app/install.sh)
├── install.ps1              Windows installer (official: foder.vercel.app/install.ps1)
├── run_tests.py             live agent tests (requires Ollama)
├── test_foder.py            unit tests (no Ollama needed)
├── test_agent_logic.py      agent logic unit tests (no Ollama needed)
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── DESIGN.md
└── TRY_THIS.md
```

---

## 12. Website Architecture

**Repo:** `github.com/Frictionalfor/foder-website`
**Deployed:** `foder.vercel.app`
**Stack:** React 18 + Vite + Tailwind CSS + Framer Motion

### Components

| Component | Purpose |
|-----------|---------|
| `Nav.jsx` | Floating pill navbar, scroll-spy active links, live GitHub stars |
| `Hero.jsx` | ASCII logo (typewriter effect), tagline, install CTA |
| `StatsBar.jsx` | Animated count-up: 11 skills, 11 tools, 42 tests, 0 cloud calls |
| `HowItWorks.jsx` | 3-step setup + Ollama→Agent→Tools→Result flow diagram |
| `Features.jsx` | 9 feature cards with ecosystem badges |
| `BuildAnything.jsx` | 6 project type cards with skill annotations |
| `Terminal.jsx` | Animated terminal demo (Python / HTML+CSS / FastAPI / Git tabs) |
| `Comparison.jsx` | Feature comparison: foder vs OpenCode vs Cursor vs Copilot |
| `Themes.jsx` | 6 live theme switcher cards |
| `Install.jsx` | Install tabs (Linux/macOS / Windows / From Source) + lifecycle commands |
| `Commands.jsx` | Slash command reference table |
| `Testimonials.jsx` | User quotes |
| `About.jsx` | Author section with GitHub stats |
| `Footer.jsx` | 4-column footer + install strip |

### Install Source Rule

**Install:** `https://foder.vercel.app/install.sh` (and `.ps1`)
**Update:** `https://github.com/Frictionalfor/foder` (git pull)

These are the ONLY official sources. No mirrors. No GitHub raw links for install.

### Theme System

CSS custom properties on `:root`, all animated with `transition: 0.3s`:
```css
--accent, --accent-light, --accent-dark
--bg, --surface, --border
--text, --text-sec, --text-dim
```

ThemeContext provides `theme` and `setTheme` to all components.

---

## 13. Deployment

### Foder CLI

```bash
# Official install
curl -fsSL https://foder.vercel.app/install.sh | bash

# From source
git clone https://github.com/Frictionalfor/foder
cd foder
pip install -e .
```

### Website

```bash
cd foder-website
npm install
npm run build    # outputs to dist/
```

Deployed on Vercel — auto-deploys on push to `master` branch of `foder-website` repo.

---

## 14. Performance Targets

| Metric | Target |
|--------|--------|
| Cold startup (REPL) | < 1s (excluding Ollama model load) |
| Token usage per turn | Lean — only last 14 turns sent, tool results truncated to 1200 chars |
| File injection limit | 60,000 chars (~15k tokens) total for @file / @dir |
| Tool timeout | 30s default (configurable per project) |
| LLM timeout | 600s default, wall-clock + per-token idle check |
| Max agent iterations | 20 per turn (prevents infinite loops) |
| Ollama model warm-up | keep_alive=10m — stays loaded between turns |

---

## 15. Testing

### Test Suites

| `test_foder.py` | Unit tests (42) | No |
| `test_agent_logic.py` | Agent logic (32) | No |
| `run_tests.py` | Live integration (10) | Yes |

### test_foder.py Coverage

imports, config defaults, foder.json loading, malformed JSON,
path escape blocking, valid path, dangerous command blocking, safe commands,
file_write/read roundtrip, parent dir creation, missing file error,
dir_list, dir_create, shell_exec, blocked command, non-zero exit code,
unknown tool, missing param, path escape via tool,
bare JSON detection, fenced JSON, large payload, nested braces, preamble,
fenced with indentation, no false positives, history trimming, truncation,
system message structure, tool names in prompt, workspace dynamic,
custom instructions, session roundtrip, missing file, corrupted file,
session trim, @file passthrough, @file inject, @file missing,
snapshot capture, all themes apply

### run_tests.py Tasks

Single file creation, file with logic, directory creation, list files,
edit existing file, C file, run Python file,
multi-file Python package, multi-file HTML+CSS, shell command
