# Foder — Local AI Coding Agent CLI

A terminal-based AI coding agent powered by a local LLM (Ollama).

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally

## Install

```bash
pip install -e .
```

## Usage

```bash
foder
```

Opens an interactive REPL. The agent can read files, write files, list directories, and run shell commands — all scoped to your working directory.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `FODER_WORKSPACE` | current directory | Root directory for all file operations |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen2.5-coder:7b` | Model to use |
| `FODER_MAX_ITER` | `20` | Max agent loop iterations per turn |
| `FODER_SHELL_TIMEOUT` | `30` | Shell command timeout in seconds |

## Slash Commands

| Command | Action |
|---|---|
| `/exit` | Quit |
| `/clear` | Clear conversation history |
| `/workspace` | Show workspace path |
| `/model` | Show active model |
| `/help` | Show help |

## Tools

| Tool | Description |
|---|---|
| `file_read` | Read a file |
| `file_write` | Write/create a file |
| `dir_list` | List directory contents |
| `shell_exec` | Run a shell command (sandboxed) |

## Security

- All file operations are restricted to `FODER_WORKSPACE`
- Destructive shell commands are blocked
- No system directory access
