"""
Foder CLI — interactive REPL with streaming output.
"""

import sys
import time
import json
import subprocess
import foder.config as config
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box

from foder.agent import run
from foder.llm import list_models, unload_model, LLMError
from foder.security import validate_command, SecurityError

console = Console(highlight=False)

# Session history file — stored in ~/.foder/
_HISTORY_DIR  = Path.home() / ".foder"
_HISTORY_FILE = _HISTORY_DIR / "session.json"
_MAX_SAVED_MESSAGES = 20  # only persist the last N messages to keep file small

_PROMPT_STYLE = Style.from_dict({
    "prompt":      "white bold",
    "path":        "#888888",
    "separator":   "#333333",
})

_cwd: Path = config.WORKSPACE  # updated on !cd, always mirrors config.WORKSPACE
_session_start: float = 0.0    # set in main() at session start

_COMMANDS = {
    "/models":    "list available ollama models",
    "/switch":    "switch model mid-session",
    "/model":     "show active model",
    "/clear":     "clear conversation history",
    "/workspace": "show workspace path",
    "/help":      "show this help",
    "/exit":      "quit foder",
}

# Gradient colours for the logo (top → bottom)
_LOGO_LINES = [
    " ███████╗ ██████╗ ██████╗ ███████╗██████╗ ",
    " ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗",
    " █████╗  ██║   ██║██║  ██║█████╗  ██████╔╝",
    " ██╔══╝  ██║   ██║██║  ██║██╔══╝  ██╔══██╗",
    " ██║     ╚██████╔╝██████╔╝███████╗██║  ██║ ",
    " ╚═╝      ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝",
]
_LOGO_COLORS = ["#ffffff", "#e0e0e0", "#c0c0c0", "#a0a0a0", "#707070", "#404040"]


def _make_logo() -> Text:
    logo = Text()
    for line, color in zip(_LOGO_LINES, _LOGO_COLORS):
        logo.append(line + "\n", style=f"bold {color}")
    return logo


# ── Banner ────────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    logo = _make_logo()

    info = Table.grid(padding=(0, 2))
    info.add_row(
        Text("  workspace", style="dim"),
        Text(str(config.WORKSPACE), style="white"),        # read at call time
    )
    info.add_row(
        Text("  model    ", style="dim"),
        Text(config.OLLAMA_MODEL, style="bold white"),  # read at call time
    )
    info.add_row(Text("", style=""), Text("", style=""))   # spacer
    info.add_row(
        Text("  shell    ", style="dim"),
        Text("! <cmd>  to run terminal commands", style="dim"),
    )
    info.add_row(
        Text("  help     ", style="dim"),
        Text("/help  for all commands", style="dim"),
    )

    console.print()
    console.print(Panel(
        Columns([logo, info], padding=(0, 4), equal=False),
        border_style="dim",
        padding=(0, 1),
        subtitle="[dim]local AI coding agent[/dim]",
    ))
    console.print()


def _print_status() -> None:
    """Compact one-line status — shown after /switch or on demand."""
    console.print(
        f"  [dim]model[/dim]     [bold white]{config.OLLAMA_MODEL}[/bold white]  "
        f"[dim]workspace[/dim]  [white]{config.WORKSPACE}[/white]"
    )


# ── Model selection ───────────────────────────────────────────────────────────

def _pick_model(models: list[str], prompt_text: str = "  pick › ") -> str:
    table = Table(
        show_header=True, header_style="dim",
        box=box.SIMPLE_HEAD, padding=(0, 2),
    )
    table.add_column("#",     style="dim",  width=4, justify="right")
    table.add_column("model", style="white")
    table.add_column("",      style="dim", width=3)

    for i, name in enumerate(models, 1):
        active = name == config.OLLAMA_MODEL
        table.add_row(str(i), name, "●" if active else "")

    console.print(table)

    while True:
        try:
            raw = input(prompt_text).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye.[/dim]")
            sys.exit(0)
        if raw.isdigit() and 1 <= int(raw) <= len(models):
            return models[int(raw) - 1]
        if raw in models:
            return raw
        console.print(f"  [yellow]enter a number between 1 and {len(models)}[/yellow]")


def _select_model() -> None:
    with console.status("[dim]  connecting to Ollama...[/dim]", spinner="dots", spinner_style="white"):
        try:
            models = list_models()
        except LLMError as e:
            console.print()
            console.print(Panel(
                f"[red]{e}[/red]",
                title="[red]● connection error[/red]",
                border_style="red",
            ))
            sys.exit(1)

    if not models:
        console.print(Panel(
            "[yellow]No models found in Ollama.[/yellow]\n\n"
            "Pull one first:\n  [bold white]ollama pull qwen2.5-coder:7b[/bold white]",
            title="[yellow]no models[/yellow]",
            border_style="yellow",
        ))
        sys.exit(1)

    if config.OLLAMA_MODEL in models:
        return

    console.print(Panel(
        f"Model [white]{config.OLLAMA_MODEL}[/white] not found locally.\n"
        "[dim]Select one of the available models below:[/dim]",
        border_style="yellow",
        padding=(0, 1),
    ))
    console.print()
    chosen = _pick_model(models)
    config.OLLAMA_MODEL = chosen
    console.print(f"\n  [dim]using[/dim] [bold white]{config.OLLAMA_MODEL}[/bold white]\n")


# ── Shell execution ───────────────────────────────────────────────────────────

def _run_shell(command: str) -> None:
    global _cwd
    command = command.strip()

    if not command:
        console.print(f"  [dim]cwd →[/dim] [white]{_cwd}[/white]")
        return

    # cd handled in-process
    if command == "cd" or command.startswith(("cd ", "cd\t")):
        parts = command.split(None, 1)
        target = parts[1] if len(parts) > 1 else str(Path.home())
        new_path = (
            (_cwd / target).resolve()
            if not Path(target).is_absolute()
            else Path(target).resolve()
        )
        if new_path.is_dir():
            _cwd = new_path
            config.WORKSPACE = new_path
            console.print(f"  [dim]cwd →[/dim] [white]{_cwd}[/white]")
        else:
            console.print(f"  [red]cd: no such directory:[/red] {target}")
        return

    try:
        validate_command(command)
    except SecurityError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[red]● blocked[/red]", border_style="red"))
        return

    # Header
    console.print(Rule(
        f"[dim]$ {command}[/dim]",
        style="dim",
        align="left",
    ))

    proc = None
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            command, shell=True, cwd=str(_cwd),
            stdout=sys.stdout, stderr=sys.stderr, text=True,
        )
        proc.wait(timeout=config.SHELL_TIMEOUT)
        elapsed = time.monotonic() - start
        code = proc.returncode

        if code in (0, None):
            console.print(Rule(
                f"[dim]✓ done[/dim] [dim]({elapsed:.2f}s)[/dim]",
                style="dim",
                align="left",
            ))
        else:
            console.print(Rule(
                f"[dim red]✗ exit {code}[/dim red] [dim]({elapsed:.2f}s)[/dim]",
                style="dim",
                align="left",
            ))

    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            proc.wait()
        console.print(Rule(
            f"[yellow]⏱ timed out after {config.SHELL_TIMEOUT}s[/yellow]",
            style="yellow", align="left",
        ))
    except KeyboardInterrupt:
        if proc:
            proc.kill()
            proc.wait()
        console.print(Rule("[dim]interrupted[/dim]", style="dim", align="left"))
    except Exception as e:
        console.print(f"  [red]error:[/red] {e}")


# ── Tool call display ─────────────────────────────────────────────────────────

def _on_tool_call(tool_name: str, parameters: dict) -> None:
    icons = {
        "file_read":  "[dim]~[/dim]",
        "file_write": "[dim]+[/dim]",
        "dir_list":   "[dim]>[/dim]",
        "shell_exec": "[dim]$[/dim]",
    }
    icon = icons.get(tool_name, "[dim]*[/dim]")
    param_hint = ""
    if "path" in parameters:
        param_hint = f" [dim]{parameters['path']}[/dim]"
    elif "command" in parameters:
        short = parameters["command"][:55]
        ellipsis = "…" if len(parameters["command"]) > 55 else ""
        param_hint = f" [dim]{short}{ellipsis}[/dim]"
    console.print(f"  {icon} [white]{tool_name}[/white]{param_hint}")


# ── Slash commands ────────────────────────────────────────────────────────────

def _handle_slash(cmd: str, history: list[dict]) -> tuple[bool, list[dict]]:
    parts = cmd.strip().split(None, 1)
    verb  = parts[0].lower()
    arg   = parts[1] if len(parts) > 1 else ""

    if verb in ("/exit", "/quit"):
        _save_session(history)
        unload_model()
        _print_exit(history, _session_start)
        sys.exit(0)

    if verb == "/clear":
        history.clear()
        _save_session([])
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        _print_banner()
        return True, history

    if verb == "/workspace":
        console.print(f"  [white]{config.WORKSPACE}[/white]")
        return True, history

    if verb == "/model":
        console.print(f"  [bold white]{config.OLLAMA_MODEL}[/bold white]")
        return True, history

    if verb == "/models":
        try:
            models = list_models()
        except LLMError as e:
            console.print(f"  [red]{e}[/red]")
            return True, history
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        for name in models:
            active = name == config.OLLAMA_MODEL
            table.add_row(
                Text("●" if active else " ", style="white" if active else "dim"),
                Text(name, style="bold white" if active else "white"),
            )
        console.print(table)
        return True, history

    if verb == "/switch":
        try:
            models = list_models()
        except LLMError as e:
            console.print(f"  [red]{e}[/red]")
            return True, history
        if arg and arg in models:
            config.OLLAMA_MODEL = arg
            console.print(f"  [dim]switched →[/dim] [bold white]{config.OLLAMA_MODEL}[/bold white]")
            _print_status()
            return True, history
        console.print("[dim]  select a model:[/dim]\n")
        chosen = _pick_model(models)
        config.OLLAMA_MODEL = chosen
        console.print()
        _print_status()
        return True, history

    if verb == "/help":
        console.print()
        console.print(Rule("[dim]commands[/dim]", style="dim"))
        t1 = Table(show_header=False, box=None, padding=(0, 2))
        for c, desc in _COMMANDS.items():
            t1.add_row(Text(c, style="bold white"), Text(desc, style="dim"))
        console.print(t1)

        console.print()
        console.print(Rule("[dim]shell[/dim]", style="dim"))
        t2 = Table(show_header=False, box=None, padding=(0, 2))
        t2.add_row(Text("! <cmd>",     style="bold white"), Text("run a terminal command", style="dim"))
        t2.add_row(Text("! cd <path>", style="bold white"), Text("change working directory", style="dim"))
        t2.add_row(Text("!",           style="bold white"), Text("show current directory", style="dim"))
        console.print(t2)
        console.print()
        return True, history

    console.print(f"  [yellow]unknown:[/yellow] {verb}  [dim](try /help)[/dim]")
    return True, history


# ── Prompt ────────────────────────────────────────────────────────────────────

def _prompt_label() -> HTML:
    try:
        rel = _cwd.relative_to(config.WORKSPACE)
        path = f"foder/{rel}" if str(rel) != "." else "foder"
    except ValueError:
        path = str(_cwd)
    model_short = config.OLLAMA_MODEL.split(":")[0]   # strip tag for brevity
    return HTML(
        f'<style color="#888888">{model_short}</style>'
        f'<style color="#333333"> │ </style>'
        f'<prompt>{path} ❯ </prompt>'
    )


# ── Response renderer ─────────────────────────────────────────────────────────

def _stream_response(token_iter) -> str:
    collected = []
    try:
        console.print("  ", end="")
        for token in token_iter:
            console.print(token, end="", markup=False)
            collected.append(token)
        console.print()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        console.print(Text("  cancelled", style="dim"))

    full = "".join(collected)

    # Re-render markdown in a panel
    if full and any(c in full for c in ("```", "**", "##", "- ", "* ", "1.")):
        console.print()
        console.print(Panel(
            Markdown(full),
            border_style="dim",
            padding=(0, 2),
        ))

    return full


# ── Session persistence ───────────────────────────────────────────────────────

def _load_session() -> list[dict]:
    """Load last N messages from ~/.foder/session.json. Returns [] on any error."""
    try:
        if _HISTORY_FILE.exists():
            data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[-_MAX_SAVED_MESSAGES:]
    except Exception:
        pass
    return []


def _save_session(history: list[dict]) -> None:
    """Persist the last N messages to disk. Silent on failure."""
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        _HISTORY_FILE.write_text(
            json.dumps(history[-_MAX_SAVED_MESSAGES:], ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


# ── @file context injection ───────────────────────────────────────────────────

def _inject_file_context(user_input: str) -> str:
    """
    Replace @filename tokens with the file contents inline.
    e.g. "@main.py fix the bug" → prepends the file content to the message.
    Only reads files inside WORKSPACE. Skips files that don't exist or are too large.
    """
    import re
    _MAX_INJECT_BYTES = 32_000  # ~32KB per file — keeps context lean

    pattern = re.compile(r"@([\w./\-]+)")
    matches = pattern.findall(user_input)
    if not matches:
        return user_input

    injected = []
    for ref in matches:
        try:
            from foder.security import validate_path, SecurityError
            target = validate_path(ref)
            if not target.is_file():
                continue
            content = target.read_bytes()
            if len(content) > _MAX_INJECT_BYTES:
                injected.append(f"[{ref} — file too large to inject, use file_read instead]")
                continue
            text = content.decode("utf-8", errors="replace")
            injected.append(f"--- @{ref} ---\n{text}\n--- end {ref} ---")
        except Exception:
            continue

    if not injected:
        return user_input

    context_block = "\n\n".join(injected)
    # Strip the @refs from the message and prepend the file contents
    clean_input = pattern.sub("", user_input).strip()
    return f"{context_block}\n\n{clean_input}"


# ── Main REPL ─────────────────────────────────────────────────────────────────

def _print_exit(history: list[dict], start_time: float) -> None:
    """A proper goodbye — session stats + farewell."""
    import datetime

    elapsed   = time.monotonic() - start_time
    minutes   = int(elapsed // 60)
    seconds   = int(elapsed % 60)
    duration  = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

    # Count only user turns (not tool result injections)
    turns = sum(1 for m in history if m["role"] == "user" and not m["content"].startswith("[tool:"))

    now = datetime.datetime.now().strftime("%H:%M")

    grid = Table.grid(padding=(0, 3))
    grid.add_row(
        Text("session ended", style="dim"),
        Text(now, style="white"),
    )
    grid.add_row(
        Text("duration     ", style="dim"),
        Text(duration, style="white"),
    )
    grid.add_row(
        Text("messages     ", style="dim"),
        Text(str(turns), style="white"),
    )
    grid.add_row(
        Text("model        ", style="dim"),
        Text(config.OLLAMA_MODEL, style="white"),
    )

    console.print()
    console.print(Panel(
        grid,
        border_style="#333333",
        padding=(0, 2),
        title="[dim]foder[/dim]",
        title_align="left",
        subtitle="[dim]session saved · model unloaded[/dim]",
    ))
    console.print()


def main() -> None:
    global _cwd
    config.load_project_config()
    _select_model()
    _cwd = config.WORKSPACE
    _print_banner()

    session: PromptSession = PromptSession(
        history=InMemoryHistory(),
        style=_PROMPT_STYLE,
    )

    conversation_history: list[dict] = _load_session()
    if conversation_history:
        console.print(f"  [dim]resumed {len(conversation_history)} messages from last session[/dim]\n")

    session_start = time.monotonic()
    global _session_start
    _session_start = session_start

    while True:
        try:
            user_input = session.prompt(_prompt_label, style=_PROMPT_STYLE)
        except (EOFError, KeyboardInterrupt):
            _save_session(conversation_history)
            unload_model()
            _print_exit(conversation_history, session_start)
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # ── Shell passthrough ──────────────────────────────────────────────
        if user_input.startswith("!"):
            console.print()
            _run_shell(user_input[1:].strip())
            console.print()
            continue

        # ── Slash commands ─────────────────────────────────────────────────
        if user_input.startswith("/"):
            console.print()
            _, conversation_history = _handle_slash(user_input, conversation_history)
            console.print()
            continue

        # ── @file context injection ────────────────────────────────────────
        resolved_input = _inject_file_context(user_input)

        # ── Agent turn ─────────────────────────────────────────────────────
        console.print()
        console.print(Panel(
            Text(user_input, style="white"),   # show original, not injected
            border_style="#333333",
            padding=(0, 1),
            title="[dim]you[/dim]",
            title_align="left",
        ))
        console.print()

        try:
            token_iter, conversation_history = run(
                resolved_input,
                conversation_history,
                on_tool_call=_on_tool_call,
            )
        except KeyboardInterrupt:
            console.print(Text("\n  cancelled", style="dim"))
            continue

        console.print(Text("  foder", style="bold white"), end="  ")
        full = _stream_response(token_iter)

        # Save after every turn — lightweight, only last 20 messages
        _save_session(conversation_history)

        if full.strip().startswith("[llm error]"):
            msg = full.strip()
            if "timed out" in msg:
                hint = (
                    f"[yellow]Ollama timed out.[/yellow]\n\n"
                    f"  The model took longer than [white]{config.LLM_TIMEOUT:.0f}s[/white].\n\n"
                    f"  [dim]Try a faster model →[/dim]  /switch\n"
                    f"  [dim]Raise the limit    →[/dim]  FODER_LLM_TIMEOUT=600 foder"
                )
            elif "Cannot connect" in msg:
                hint = (
                    "[yellow]Cannot reach Ollama.[/yellow]\n\n"
                    "  [dim]Start it with:[/dim]  [bold]ollama serve[/bold]"
                )
            else:
                hint = f"[yellow]{msg}[/yellow]"
            console.print(Panel(hint, border_style="yellow", padding=(0, 1)))

        console.print()
        console.print(Rule(style="#1a1a1a"))
        console.print()


if __name__ == "__main__":
    main()
