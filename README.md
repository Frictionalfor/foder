# Foder

A terminal-based AI coding agent powered by local LLMs via Ollama.
No cloud. No API keys. Runs entirely on your machine.

```
  ███████  ██████  ██████  ███████ ██████
  ██      ██    ██ ██   ██ ██      ██   ██
  █████   ██    ██ ██   ██ █████   ██████
  ██      ██    ██ ██   ██ ██      ██   ██
  ██       ██████  ██████  ███████ ██   ██
```

> Built by [Frictionalfor](https://github.com/Frictionalfor) · [github.com/Frictionalfor/foder](https://github.com/Frictionalfor/foder)

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

### Update

```bash
bash update.sh
```

---

## Usage

```bash
foder
```

Opens an interactive REPL. The agent reads files, writes files, creates directories,
and runs shell commands — all scoped to your working directory.

### Non-interactive mode

```bash
foder "create a hello world python file"
```

Runs the prompt, prints output, and exits. Useful for scripts and automation.

---

## Shell Commands

Common shell commands work directly — no `!` prefix needed:

```
foder ❯ ls -la
foder ❯ cd src
foder ❯ git status
foder ❯ cat main.py
foder ❯ nano style.css
foder ❯ python3 app.py
foder ❯ gcc hello.c -o hello
foder ❯ npm install
```

For any other shell command, prefix with `!`:

```
foder ❯ !htop
foder ❯ !df -h
foder ❯ !!          ← re-runs the last shell command
```

Output streams live. `Ctrl+C` kills the running process cleanly.
Risky commands (`sudo`, `rm`, `apt`, etc.) ask for confirmation before running.

---

## @file Context Injection

Reference a file directly in your message — foder injects its contents into the prompt:

```
foder ❯ @main.py fix the null check on line 42
foder ❯ @config.json what does the timeout setting do
foder ❯ @src/auth.py @src/models.py refactor these to share validation logic
```

Files larger than 32KB are skipped with a notice.

---

## Tab Completion

- Press `Tab` to complete `/` commands
- Press `Tab` after `@` to complete filenames in the current directory
- Press `Ctrl+R` for reverse history search (persists across sessions)

---

## Multi-line Input

End a line with `\` to continue on the next line:

```
foder ❯ create a python file that reads a CSV, \
         filters rows where age > 18, \
         and saves the result to output.csv
```

---

## Slash Commands

| Command | Description |
|---|---|
| `/models` | list available Ollama models |
| `/switch` | switch model mid-session |
| `/switch <name>` | switch to a specific model directly |
| `/model` | show active model |
| `/theme` | change color theme |
| `/clear` | clear terminal + conversation history |
| `/workspace` | show current workspace path |
| `/last` | show last response again (no API call) |
| `/undo` | revert last file write |
| `/diff` | show diff of last file write |
| `/run` | auto-detect and run the project |
| `/git` | show git status (branch, changes, recent commits) |
| `/pin <file>` | pin a file to every prompt automatically |
| `/unpin <file>` | remove a pinned file |
| `/pins` | list all pinned files |
| `/snapshot` | save current workspace file state |
| `/snapshot diff` | show what changed since last snapshot |
| `/cost` | show session stats (messages, tool calls, ~tokens) |
| `/arch` | show architecture diagram |
| `/help` | show all commands |
| `/exit` | quit foder (unloads model from RAM) |

---

## Themes

Foder ships with 6 built-in color themes. Pick one with `/theme`:

| Key | Name | Description |
|---|---|---|
| `green` | Green | classic terminal green (default) |
| `teal` | Cyber Teal | sharp, technical, hacker-ish |
| `amber` | Amber | warm, energetic, stands out |
| `rose` | Rose | bold, modern, memorable |
| `blue` | Electric Blue | clean, professional |
| `lime` | Neon Lime | aggressive, terminal-native |

Theme choice is saved to `~/.foder/theme.json` and persists across sessions.

---

## Per-Project Config

Drop a `foder.json` in your project root:

```json
{
  "model": "qwen2.5-coder:7b",
  "llm_timeout": 300,
  "shell_timeout": 60,
  "max_iterations": 15,
  "instructions": "This is a Python 3.12 project using FastAPI and PostgreSQL."
}
```

Foder loads it automatically on startup and when you `cd` into the directory.
Environment variables take precedence over `foder.json`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FODER_WORKSPACE` | current directory | root directory for all file operations |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5-coder:3b` | model to use |
| `FODER_MAX_ITER` | `20` | max agent loop iterations per turn |
| `FODER_SHELL_TIMEOUT` | `30` | shell command timeout in seconds |
| `FODER_LLM_TIMEOUT` | `600` | LLM request timeout in seconds |
| `FODER_INSTRUCTIONS` | _(empty)_ | custom instructions appended to system prompt |

---

## Session Memory

Foder saves the last 20 messages to `~/.foder/session.json` after every turn.
The next time you run `foder` it resumes where you left off.

Use `/clear` to wipe the session completely.

Prompt history persists across sessions — use `Ctrl+R` to search previous inputs.

---

## Tools

The agent has access to five tools:

| Tool | Description |
|---|---|
| `file_read` | read a file |
| `file_write` | write / create a file |
| `dir_list` | list directory contents |
| `dir_create` | create a directory |
| `shell_exec` | run a shell command (sandboxed) |

---

## Security

- All file operations are restricted to the current workspace
- Destructive shell commands are blocked (`rm -rf /`, `mkfs`, `shutdown`, etc.)
- Risky commands ask for confirmation before running
- No system directory access
- Shell commands run with a configurable timeout
- Model is unloaded from RAM on `/exit`

---

## Performance Tips

- Use `qwen2.5-coder:3b` for speed, `7b` for quality
- Model stays warm in RAM for 10 minutes between requests (fast subsequent calls)
- Only the last 10 messages are sent per LLM request
- Tool results are truncated to 500 chars in history
- Use `/clear` when starting a new unrelated task to reset context
- Break large tasks into smaller steps for faster, more reliable results

---

## Recommended Models

| Model | Size | Speed | Best for |
|---|---|---|---|
| `qwen2.5-coder:3b` | ~2GB | fast | default, everyday coding |
| `qwen2.5-coder:7b` | ~4GB | medium | better quality responses |
| `qwen2.5-coder:14b` | ~8GB | slow | complex tasks, best quality |

Pull a model:

```bash
ollama pull qwen2.5-coder:3b
```

---

## Running Tests

```bash
python3 test_foder.py
```

42 tests covering imports, config, security, tools, agent, session, prompt, themes, and snapshot.

---

## Project Structure

```
foder/
├── foder/
│   ├── main.py        CLI entry point + REPL
│   ├── agent.py       agent loop (streaming, history management)
│   ├── llm.py         Ollama HTTP client
│   ├── prompt.py      system prompt builder
│   ├── config.py      config + foder.json loader
│   ├── security.py    path jail + command blocklist
│   └── tools/
│       ├── file_read.py
│       ├── file_write.py
│       ├── dir_list.py
│       ├── dir_create.py
│       ├── shell_exec.py
│       └── registry.py
├── test_foder.py      test suite (42 tests)
├── run_tests.py       on-site integration test runner
├── install.sh         Linux/macOS installer
├── install.ps1        Windows installer
├── update.sh          auto-updater
└── pyproject.toml
```
