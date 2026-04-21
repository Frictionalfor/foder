# Foder

A terminal-based AI coding agent powered by local LLMs via Ollama.
No cloud. No API keys. Runs entirely on your machine.

```
 ███████╗ ██████╗ ██████╗ ███████╗██████╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
 █████╗  ██║   ██║██║  ██║█████╗  ██████╔╝
 ██╔══╝  ██║   ██║██║  ██║██╔══╝  ██╔══██╗
 ██║     ╚██████╔╝██████╔╝███████╗██║  ██║
 ╚═╝      ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
```

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally

---

## Install

### Linux / macOS

```bash
git clone https://github.com/Frictionalfor/foder.git
cd foder
bash install.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/Frictionalfor/foder.git
cd foder
powershell -ExecutionPolicy Bypass -File install.ps1
```

### Manual

```bash
pip install -e .
```

---

## Usage

```bash
foder
```

Opens an interactive REPL. The agent reads files, writes files, lists directories,
and runs shell commands — all scoped to your working directory.

---

## Shell Commands

Prefix any terminal command with `!` to run it directly:

```
foder ❯ !ls -la
foder ❯ !git status
foder ❯ !python3 main.py
foder ❯ !cd src          ← changes cwd for the session
foder ❯ !                ← shows current directory
```

Output streams live. `Ctrl+C` kills the running process cleanly.

---

## @file Context Injection

Reference a file directly in your message — foder injects its contents into the prompt automatically, skipping a round trip:

```
foder ❯ @main.py fix the null check on line 42
foder ❯ @config.json what does the timeout setting do
foder ❯ @src/auth.py @src/models.py refactor these to share the validation logic
```

Files larger than 32KB are skipped with a notice.

---

## Slash Commands

| Command | Description |
|---|---|
| `/models` | list available Ollama models |
| `/switch` | switch model mid-session |
| `/switch <name>` | switch to a specific model directly |
| `/model` | show active model |
| `/clear` | clear terminal + conversation history |
| `/workspace` | show current workspace path |
| `/help` | show all commands |
| `/exit` | quit foder (unloads model from RAM) |

---

## Per-Project Config

Drop a `foder.json` in your project root to configure foder per project:

```json
{
  "model": "qwen2.5-coder:3b",
  "llm_timeout": 120,
  "shell_timeout": 60,
  "max_iterations": 15,
  "instructions": "This is a Python 3.12 project using FastAPI and PostgreSQL."
}
```

Foder loads it automatically on startup. Environment variables take precedence over `foder.json`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FODER_WORKSPACE` | current directory | root directory for all file operations |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | model to use |
| `FODER_MAX_ITER` | `20` | max agent loop iterations per turn |
| `FODER_SHELL_TIMEOUT` | `30` | shell command timeout in seconds |
| `FODER_LLM_TIMEOUT` | `300` | LLM request timeout in seconds |
| `FODER_INSTRUCTIONS` | _(empty)_ | custom instructions appended to system prompt |

---

## Session Memory

Foder saves the last 20 messages to `~/.foder/session.json` after every turn.
The next time you run `foder` it resumes where you left off.

Use `/clear` to wipe the session completely.

---

## Tools

The agent has access to four tools:

| Tool | Description |
|---|---|
| `file_read` | read a file |
| `file_write` | write / create a file |
| `dir_list` | list directory contents |
| `shell_exec` | run a shell command (sandboxed) |

---

## Security

- All file operations are restricted to the current workspace
- Destructive shell commands are blocked (`rm -rf /`, `mkfs`, `shutdown`, etc.)
- No system directory access
- Shell commands run with a configurable timeout
- Model is unloaded from RAM on clean exit

---

## Memory

Foder is designed to stay lean:

- Conversation history capped at 30 messages in memory, 20 on disk
- Single LLM request per turn (no double requests)
- `@file` injection capped at 32KB per file
- Model unloaded from Ollama RAM on exit (`/exit` or `Ctrl+D`)

---

## Recommended Models

| Model | Size | Good for |
|---|---|---|
| `qwen2.5-coder:3b` | ~2GB | fast, low RAM |
| `qwen2.5-coder:7b` | ~4GB | balanced |
| `qwen2.5-coder:14b` | ~8GB | best quality |
| `llama3.2:3b` | ~2GB | general tasks |

Pull a model:

```bash
ollama pull qwen2.5-coder:7b
```

---

## Project Structure

```
foder/
├── foder/
│   ├── main.py        CLI entry point + REPL
│   ├── agent.py       agent loop (single-pass streaming)
│   ├── llm.py         Ollama HTTP client
│   ├── prompt.py      system prompt builder
│   ├── config.py      config + foder.json loader
│   ├── security.py    path jail + command blocklist
│   └── tools/
│       ├── file_read.py
│       ├── file_write.py
│       ├── dir_list.py
│       ├── shell_exec.py
│       └── registry.py
├── install.sh         Linux/macOS installer
├── install.ps1        Windows installer
└── pyproject.toml
```
