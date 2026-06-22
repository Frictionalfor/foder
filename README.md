# Foder

**Local AI Coding Agent — powered entirely by Ollama. No cloud. No API keys. Just code.**

```
  ███████  ██████  ██████  ███████ ██████
  ██      ██    ██ ██   ██ ██      ██   ██
  █████   ██    ██ ██   ██ █████   ██████
  ██      ██    ██ ██   ██ ██      ██   ██
  ██       ██████  ██████  ███████ ██   ██
```

> **Website:** [foder.vercel.app](https://foder.vercel.app)
> **GitHub:** [github.com/Frictionalfor/foder](https://github.com/Frictionalfor/foder)
> Built by [Frictionalfor](https://github.com/Frictionalfor)

---

## What is Foder?

Foder is a terminal-based AI coding agent that runs 100% locally using [Ollama](https://ollama.com).
It is the **OpenCode alternative that works completely offline** — no subscriptions, no API keys, no data leaving your machine.

**Core capabilities:**
- Interactive REPL coding agent
- Project generation — full apps, SaaS clones, full-stack systems
- 11 built-in skills — React, Next.js, FastAPI, Django, Node, mobile, auth, DB design, SaaS cloner, CLI tools
- /test — auto-detects and runs your test suite
- /refactor — targeted diff-based file refactoring
- /chat — lightweight Q&A without tool overhead
- /watch — file watcher that triggers agent on save
- /doctor — full system health check
- Multi-file @src/ context injection
- Git-aware, workspace-sandboxed file operations
- Shell execution with security guardrails
- Session memory across restarts
- Auto-detects your installed Ollama model on startup

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with at least one model pulled

---

## Install

### One-line (official — Linux / macOS)

```bash
curl -fsSL https://foder.vercel.app/install.sh | bash
```

### One-line (official — Windows PowerShell)

```powershell
irm https://foder.vercel.app/install.ps1 | iex
```

### From source

```bash
git clone https://github.com/Frictionalfor/foder.git
cd foder
bash install.sh
```

The installer:
- Detects your OS
- Checks Python 3.10+ and Ollama
- Installs foder and creates `~/.foder/`
- Offers to pull `qwen2.5-coder:3b` if no model is found

---

## Usage

```bash
foder                          # start interactive REPL
foder "create a todo app"      # single prompt, non-interactive
foder init                     # interactive project setup wizard
foder --help                   # full help and command reference
foder --update                 # update to latest version
foder --uninstall              # remove foder
foder --timeout 300            # override LLM timeout for this session
```

---

## Project Generation

Build complete, runnable projects with a single command:

```
foder > /build a full React dashboard with auth and dark mode
foder > /build a FastAPI backend with JWT auth and SQLite
foder > /build a full-stack Instagram clone
foder > /build a Next.js app with TypeScript and Tailwind
foder > /build a Django REST API with PostgreSQL
foder > /build a React Native mobile app with Expo
```

The agent will:
1. Detect the right skill automatically
2. Design the architecture
3. Generate every file completely (no TODOs, no placeholders)
4. Install dependencies
5. Build and verify
6. Fix any errors automatically
7. Report what was built and how to run it

---

## Skills System

11 built-in skills ship with Foder. Skills are auto-detected from your request.

```
foder > /skills list             # see all skills
foder > /skills show next_app    # see steps and best practices
foder > /skills use django_backend
```

| Skill | Description |
|---|---|
| `react_app` | React + Vite + Tailwind + React Router |
| `next_app` | Next.js 14 App Router + TypeScript + Tailwind |
| `fastapi_backend` | FastAPI + SQLAlchemy + Pydantic + JWT |
| `django_backend` | Django + DRF + PostgreSQL + JWT |
| `node_api` | Express + SQLite + Zod + JWT |
| `fullstack_app` | React frontend + FastAPI/Express backend |
| `saas_cloner` | Clone Instagram, Twitter, Airbnb, etc. |
| `mobile_app` | React Native + Expo Router |
| `auth_system` | Add JWT auth to any existing project |
| `database_schema` | Design and implement DB schemas |
| `cli_tool` | Python or Node.js CLI with Rich/Commander |

Add custom skills to `~/.foder/skills/` or `./skills/` as JSON files.

---

## Agent Modes

```
foder > /plan build a payment system    # plan first, execute after approval
foder > /auto refactor this codebase    # autonomous mode
foder > /chat what is a closure?        # Q&A without tool overhead
foder > /test                           # run project test suite
foder > /test src/                      # run tests in specific path
foder > /refactor src/auth.py           # targeted diff-based refactor
foder > /watch                          # watch files, trigger agent on save
foder > /review src/auth.py             # code review with actionable report
foder > /explain main.py advanced       # explain architecture + decisions
foder > /compress                       # compress conversation context
foder > /history fastapi                # search prompt history
foder > /doctor                         # system health check
```

---

## Multi-file Context

```
foder > @main.py fix the null check
foder > @src/ review all files in this directory
foder > @config.json @app.py refactor to use environment variables
foder > /pin src/auth.py          # pin a file to every prompt
```

- `@file` — injects a single file
- `@dir/` — injects all relevant files in a directory (respects token limits)
- `/pin` — pins a file to every future prompt in the session

---

## Slash Commands Reference

| Command | Description |
|---|---|
| `/build <desc>` | generate a complete project end-to-end |
| `/plan <request>` | build an implementation plan before executing |
| `/auto <task>` | autonomous mode |
| `/chat <question>` | lightweight Q&A, no tools |
| `/test [path]` | auto-detect and run test suite |
| `/refactor <file>` | targeted diff-based refactor |
| `/watch [pattern]` | watch files, trigger agent on save |
| `/review [path]` | code review a file or directory |
| `/explain <file>` | explain code `[beginner\|advanced]` |
| `/compress` | summarize and compress conversation history |
| `/history [query]` | search persistent prompt history |
| `/doctor` | system health check |
| `/skills list` | list all available skills |
| `/skills show <name>` | show skill steps and best practices |
| `/skills use <name>` | load a skill explicitly |
| `/models` | list available Ollama models |
| `/switch [model]` | switch model mid-session |
| `/model` | show active model info |
| `/theme` | pick color theme (6 built-in) |
| `/context` | show detected project type |
| `/memory add <fact>` | remember a project fact |
| `/memory show` | view all workspace memory |
| `/index` | list workspace files ranked by relevance |
| `/git` | git status, branch, recent commits |
| `/pin <file>` | pin file to every prompt |
| `/undo` | revert last file write |
| `/diff` | show diff of last file write |
| `/snapshot` | save workspace file state |
| `/snapshot diff` | show what changed since snapshot |
| `/cost` | session stats |
| `/audit` | recent tool call log |
| `/arch` | Foder architecture diagram |
| `/clear` | clear screen and conversation history |
| `/exit` | quit (unloads model from RAM) |

---

## Project Setup Wizard

```bash
foder init
```

Interactive wizard that creates `foder.json` in your project:
- Selects a model from available Ollama models
- Sets project instructions (tech stack, conventions)
- Sets max agent iterations
- Optionally sets a default skill preset

---

## Shell Integration

Common shell commands work without a prefix:

```bash
foder > ls -la
foder > cd src
foder > git status
foder > python3 app.py
foder > npm run dev
```

Use `!` for any other shell command:

```bash
foder > !htop
foder > !!          # re-run last shell command
```

---

## Tools

The agent has access to 11 tools:

| Tool | Description |
|---|---|
| `file_read` | read a file |
| `file_write` | write / create a file |
| `file_edit` | patch-based editing (replaces a specific string) |
| `file_delete` | delete a file |
| `file_rename` | rename or move a file |
| `dir_list` | list directory contents |
| `dir_create` | create a directory |
| `dir_remove` | remove a directory |
| `shell_exec` | run a shell command (sandboxed) |
| `grep_search` | search for patterns across files |
| `git_tool` | git status, diff, log, add, commit, checkout |

---

## Memory System

Three memory layers:

| Layer | Storage | Contains |
|---|---|---|
| Session | RAM | Current conversation |
| Workspace | `.foder/memory.json` | Project facts, architecture notes, decisions |
| User | `~/.foder/preferences.json` | Model, theme, coding style |

```
foder > /memory add this project uses PostgreSQL, not SQLite
foder > /memory notes monorepo: React in /frontend, FastAPI in /api
foder > /memory show
```

---

## Per-Project Config

Drop a `foder.json` in your project root (or run `foder init`):

```json
{
  "model": "qwen2.5-coder:7b",
  "instructions": "This is a Python 3.12 project using FastAPI and PostgreSQL.",
  "max_iterations": 15,
  "llm_timeout": 300,
  "shell_timeout": 60
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | auto-detected | model to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `FODER_WORKSPACE` | current directory | workspace root |
| `FODER_MAX_ITER` | `20` | max agent loop iterations |
| `FODER_LLM_TIMEOUT` | `600` | LLM request timeout (seconds) |
| `FODER_SHELL_TIMEOUT` | `30` | shell command timeout (seconds) |
| `FODER_INSTRUCTIONS` | _(empty)_ | custom instructions appended to system prompt |

---

## System Health Check

```bash
foder > /doctor
```

Checks Python version, pip, PATH, `~/.foder/` structure, Ollama running status, available models, git, and workspace config. Auto-creates missing directories.

---

## Security

- All file operations are **workspace-jailed** (cannot escape the working directory)
- Dangerous commands are blocked (`rm -rf /`, `mkfs`, `shutdown`, etc.)
- Risky commands require confirmation
- Shell commands run with configurable timeouts
- All tool calls are logged to `~/.foder/audit.log`
- Model is unloaded from RAM on `/exit`

---

## Recommended Models

| Model | RAM | Best For |
|---|---|---|
| `qwen2.5-coder:3b` | ~2GB | fast, everyday coding |
| `qwen2.5-coder:7b` | ~4GB | better quality |
| `qwen2.5-coder:14b` | ~8GB | complex tasks |
| `qwen3.5:9b` | ~6GB | balanced reasoning + coding |
| `deepseek-coder:6.7b` | ~4GB | code generation |

Foder auto-detects which model you have installed — no manual config needed.

```bash
ollama pull qwen2.5-coder:3b   # recommended start
ollama pull qwen3.5:9b         # step up in quality
```

---

## Architecture

```
  User Input
       |
  Foder CLI  (main.py)
  REPL + themes + session + slash commands
       |
  +----------+  +----------+  +------------------+
  | Context  |  | Memory   |  | Agent Loop       |
  | Engine   |  | 3 layers |  | plan>tool>verify |
  +----------+  +----------+  +-------+----------+
                                       |
                              Tool Registry (11 tools)
                              file + dir + git + grep + shell
                                       |
                              Ollama  (local LLM, no cloud)
                              any model you have pulled

  Skills: ~/.foder/skills/ + ./skills/ + built-in /skills/
  Memory: session (RAM) + workspace (.foder/) + user (~/.foder/)
  Security: workspace jail + command blocklist + audit log
```

---

## Project Structure

```
foder/
+-- foder/
|   +-- main.py        CLI entry point + REPL + all slash commands
|   +-- agent.py       agent loop (multi-file + JSON-clean output)
|   +-- llm.py         Ollama HTTP client with timeout + crash recovery
|   +-- prompt.py      system prompt builder
|   +-- config.py      configuration + foder.json loader + model auto-detect
|   +-- context.py     project detection + smart file selection
|   +-- memory.py      3-layer memory system
|   +-- skills.py      skills engine + intent detection + /build mode
|   +-- commands.py    all slash command implementations
|   +-- cli.py         --help / --update / --uninstall
|   +-- audit.py       tool call audit logging
|   +-- security.py    path jail + command blocklist
|   +-- tools/
|       +-- registry.py     tool dispatch + aliases
|       +-- file_read.py
|       +-- file_write.py
|       +-- file_edit.py
|       +-- file_delete.py
|       +-- file_rename.py
|       +-- dir_list.py
|       +-- dir_create.py
|       +-- dir_remove.py
|       +-- shell_exec.py
|       +-- grep_search.py
|       +-- git_tool.py
+-- skills/
|   +-- react_app.json
|   +-- next_app.json
|   +-- fastapi_backend.json
|   +-- django_backend.json
|   +-- node_api.json
|   +-- fullstack_app.json
|   +-- saas_cloner.json
|   +-- mobile_app.json
|   +-- auth_system.json
|   +-- database_schema.json
|   +-- cli_tool.json
+-- foder-website/     landing page (React + Vite + Tailwind)
+-- install.sh         Linux/macOS installer
+-- install.ps1        Windows installer
+-- run_tests.py       live agent test suite (requires Ollama)
+-- test_foder.py      unit test suite (no Ollama needed)
+-- test_agent_logic.py  agent logic unit tests (no Ollama needed)
+-- pyproject.toml
```

---

## Running Tests

```bash
# Unit tests — no Ollama needed
OLLAMA_MODEL=qwen3.5:9b python3 tests/test_unit.py
OLLAMA_MODEL=qwen3.5:9b python3 tests/test_agent_logic.py

# Live agent tests — requires Ollama running
python3 tests/test_integration.py
```

---

## License

MIT — see [LICENSE](LICENSE)

---

## Links

| | |
|---|---|
| Website | [foder.vercel.app](https://foder.vercel.app) |
| GitHub | [github.com/Frictionalfor/foder](https://github.com/Frictionalfor/foder) |
| Install | [foder.vercel.app/install.sh](https://foder.vercel.app/install.sh) |
| Issues | [github.com/Frictionalfor/foder/issues](https://github.com/Frictionalfor/foder/issues) |
| Author | [github.com/Frictionalfor](https://github.com/Frictionalfor) |
