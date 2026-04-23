"""Foder CLI - simple, clear, shows work."""
import sys, time, json, subprocess, difflib
import foder.config as config
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich.live import Live
from rich import box
from foder.agent import run
from foder.llm import list_models, unload_model, LLMError
from foder.security import validate_command, SecurityError

console = Console(highlight=False)

# ── Themes ────────────────────────────────────────────────────────────────────

THEMES = {
    "green": {
        "name": "Green",
        "desc": "classic terminal green",
        "A1": "#BBF7D0", "A2": "#4ADE80", "A3": "#16A34A",
        "A4": "#166534", "A5": "#052E16",
        "logo": ["#F0FDF4","#BBF7D0","#4ADE80","#16A34A","#166534","#052E16"],
    },
    "teal": {
        "name": "Cyber Teal",
        "desc": "sharp, technical, hacker-ish",
        "A1": "#67E8F9", "A2": "#06B6D4", "A3": "#0E7490",
        "A4": "#155E75", "A5": "#164E63",
        "logo": ["#ECFEFF","#A5F3FC","#67E8F9","#06B6D4","#0E7490","#164E63"],
    },
    "amber": {
        "name": "Amber",
        "desc": "warm, energetic, stands out",
        "A1": "#FDE68A", "A2": "#F59E0B", "A3": "#B45309",
        "A4": "#78350F", "A5": "#451A03",
        "logo": ["#FFFBEB","#FDE68A","#FCD34D","#F59E0B","#B45309","#451A03"],
    },
    "rose": {
        "name": "Rose",
        "desc": "bold, modern, memorable",
        "A1": "#FECDD3", "A2": "#FB7185", "A3": "#E11D48",
        "A4": "#9F1239", "A5": "#4C0519",
        "logo": ["#FFF1F2","#FECDD3","#FDA4AF","#FB7185","#E11D48","#9F1239"],
    },
    "blue": {
        "name": "Electric Blue",
        "desc": "clean, professional, classic dev tool",
        "A1": "#BAE6FD", "A2": "#38BDF8", "A3": "#0284C7",
        "A4": "#075985", "A5": "#0C4A6E",
        "logo": ["#F0F9FF","#BAE6FD","#7DD3FC","#38BDF8","#0284C7","#0369A1"],
    },
    "lime": {
        "name": "Neon Lime",
        "desc": "aggressive, terminal-native, very visible",
        "A1": "#D9F99D", "A2": "#A3E635", "A3": "#65A30D",
        "A4": "#3F6212", "A5": "#1A2E05",
        "logo": ["#F7FEE7","#D9F99D","#BEF264","#A3E635","#65A30D","#3F6212"],
    },
}

_THEME_FILE = Path.home() / ".foder" / "theme.json"

# Active palette - populated by _load_theme()
_A1 = _A2 = _A3 = _A4 = _A5 = ""
_DIM = "#6B7280"
_OK  = "#86efac"
_ERR = "#fca5a5"
_LOGO_COLORS: list[str] = []
_PROMPT_STYLE: Style = Style.from_dict({})


def _apply_theme(key: str) -> None:
    """Apply a theme by key, updating all palette globals."""
    global _A1, _A2, _A3, _A4, _A5, _LOGO_COLORS, _PROMPT_STYLE, _logo_cache
    t = THEMES.get(key, THEMES["green"])
    _A1 = t["A1"]; _A2 = t["A2"]; _A3 = t["A3"]
    _A4 = t["A4"]; _A5 = t["A5"]
    _LOGO_COLORS = t["logo"]
    _PROMPT_STYLE = Style.from_dict({"prompt": f"{_A2} bold"})
    _logo_cache = None  # invalidate cache on theme change


def _save_theme(key: str) -> None:
    try:
        _THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
        _THEME_FILE.write_text(json.dumps({"theme": key}), encoding="utf-8")
    except Exception:
        pass


def _load_theme() -> str:
    """Load saved theme key, or return 'green' as default."""
    try:
        if _THEME_FILE.exists():
            data = json.loads(_THEME_FILE.read_text(encoding="utf-8"))
            key  = data.get("theme", "green")
            if key in THEMES:
                return key
    except Exception:
        pass
    return "green"


def _pick_theme() -> str:
    """Show theme picker and return chosen key."""
    keys = list(THEMES.keys())
    console.print()
    table = Table(show_header=True, header_style=_DIM, box=box.SIMPLE_HEAD, padding=(0, 2))
    table.add_column("#",      style=_DIM, width=4, justify="right")
    table.add_column("theme",  style="bold")
    table.add_column("desc",   style=_DIM)
    table.add_column("",       width=3)

    for i, key in enumerate(keys, 1):
        t      = THEMES[key]
        active = (key == _load_theme())
        # Show a colour swatch using the theme's A2
        swatch = Text("██", style=t["A2"])
        table.add_row(str(i), t["name"], t["desc"], "◆" if active else "")

    console.print(table)
    console.print()

    while True:
        try:
            raw = input("  pick › ").strip()
        except (EOFError, KeyboardInterrupt):
            return _load_theme()
        if raw.isdigit() and 1 <= int(raw) <= len(keys):
            return keys[int(raw) - 1]
        if raw in keys:
            return raw
        console.print(f"  [yellow]enter 1–{len(keys)}[/yellow]")


# ── Init theme on module load ─────────────────────────────────────────────────
_apply_theme(_load_theme())

# ── Rest of globals ───────────────────────────────────────────────────────────
_HISTORY_DIR        = Path.home() / ".foder"
_HISTORY_FILE       = _HISTORY_DIR / "session.json"
_PROMPT_HISTORY     = _HISTORY_DIR / "prompt_history"   # persisted prompt history for Ctrl+R
_MAX_SAVED_MESSAGES = 20

_cwd: Path          = config.WORKSPACE
_session_start: float = 0.0
_undo_store: dict   = {}
_last_write: dict   = {}
_last_shell_cmd: str = ""    # for !! re-run
_last_response: str  = ""    # for /last
_logo_cache: Text | None = None  # cached rendered logo

_COMMANDS = {
    "/models":    "list ollama models",
    "/switch":    "switch model",
    "/model":     "show active model",
    "/theme":     "change color theme",
    "/clear":     "clear screen + history",
    "/workspace": "show workspace",
    "/last":      "show last response again",
    "/undo":      "revert last file write",
    "/diff":      "diff of last file write",
    "/run":       "auto-run the project",
    "/arch":      "show architecture diagram",
    "/help":      "show this help",
    "/exit":      "quit",
}

_LOGO = [
    "  ███████  ██████  ██████  ███████ ██████  ",
    "  ██      ██    ██ ██   ██ ██      ██   ██ ",
    "  █████   ██    ██ ██   ██ █████   ██████  ",
    "  ██      ██    ██ ██   ██ ██      ██   ██ ",
    "  ██       ██████  ██████  ███████ ██   ██ ",
]

# Shadow version - same shape, shifted right+down by 1, rendered darker
_LOGO_SHADOW = [
    "   ███████  ██████  ██████  ███████ ██████  ",
    "   ██      ██    ██ ██   ██ ██      ██   ██ ",
    "   █████   ██    ██ ██   ██ █████   ██████  ",
    "   ██      ██    ██ ██   ██ ██      ██   ██ ",
    "   ██       ██████  ██████  ███████ ██   ██ ",
]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_color(c1: tuple, c2: tuple, t: float) -> str:
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(h: str, factor: float = 0.35) -> str:
    r, g, b = _hex_to_rgb(h)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


def _brighten(h: str, factor: float = 1.6) -> str:
    r, g, b = _hex_to_rgb(h)
    return f"#{min(255,int(r*factor)):02x}{min(255,int(g*factor)):02x}{min(255,int(b*factor)):02x}"


def _logo() -> Text:
    """3D extruded logo - result is cached per theme. Recomputed only when theme changes."""
    global _logo_cache
    if _logo_cache is not None:
        return _logo_cache

    rows   = len(_LOGO)
    colors = _LOGO_COLORS[:rows]
    text   = Text()
    # Pad all rows to same length
    max_len = max(len(l) for l in _LOGO)
    lines   = [l.ljust(max_len) for l in _LOGO]

    for row_idx, line in enumerate(lines):
        face_rgb  = _hex_to_rgb(colors[row_idx])
        next_rgb  = _hex_to_rgb(colors[min(row_idx + 1, rows - 1)])
        is_top    = row_idx == 0
        is_bottom = row_idx == rows - 1

        for col_idx, ch in enumerate(line):
            t      = col_idx / max(max_len - 1, 1)
            base   = _lerp_color(face_rgb, next_rgb, t * 0.35)
            bright = _brighten(base, 1.8)
            mid    = _brighten(base, 1.2)
            dark   = _darken(base, 0.45)
            deep   = _darken(base, 0.22)

            is_block = ch == "█"

            if not is_block:
                # Space - check if the cell to the left or above was a block
                # to render the right-side extrusion shadow
                left_block  = col_idx > 0 and lines[row_idx][col_idx - 1] == "█"
                above_block = row_idx > 0 and col_idx < len(lines[row_idx - 1]) and lines[row_idx - 1][col_idx] == "█"

                if left_block:
                    # Right-side extrusion: dark ▌ (left half) = shadow wall
                    text.append("▌", style=f"{dark}")
                elif above_block and not is_top:
                    # Bottom extrusion: ▀ top half in dark = bottom face of letter
                    text.append("▀", style=f"{deep}")
                else:
                    text.append(" ")
            else:
                if is_top:
                    # Top face: bright ▀ on top + full block
                    text.append("█", style=f"bold {bright}")
                elif is_bottom:
                    # Bottom face: slightly darker
                    text.append("█", style=f"bold {mid}")
                elif col_idx < 3 or (col_idx > 0 and lines[row_idx][col_idx - 1] != "█"):
                    # Left edge or first block in a run: highlight strip
                    text.append("█", style=f"bold {bright}")
                else:
                    text.append("█", style=f"bold {base}")

        text.append("\n")

    # Ground shadow row - ▀ blocks in very dark color, offset +1
    shadow_rgb = _darken(colors[-1], 0.18)
    text.append(" ")  # offset
    for col_idx, ch in enumerate(lines[-1]):
        if ch == "█":
            text.append("▀", style=f"{shadow_rgb}")
        else:
            left_block = col_idx > 0 and lines[-1][col_idx - 1] == "█"
            text.append("▄" if left_block else " ", style=f"{shadow_rgb}")
    text.append("\n")

    _logo_cache = text  # cache for this theme
    return text


def _print_banner() -> None:
    meta = Table.grid(padding=(0, 1))
    meta.add_row(Text("  workspace", style=_DIM), Text(str(config.WORKSPACE), style=_A2))
    meta.add_row(Text("  model    ", style=_DIM), Text(config.OLLAMA_MODEL,   style=f"bold {_A1}"))
    meta.add_row(Text("", style=""), Text("", style=""))
    meta.add_row(Text("  ! <cmd>  ", style=_DIM), Text("shell command",       style=_DIM))
    meta.add_row(Text("  @file    ", style=_DIM), Text("inject file context", style=_DIM))
    meta.add_row(Text("  /help    ", style=_DIM), Text("all commands",        style=_DIM))
    console.print()
    console.print(Panel(
        Columns([_logo(), meta], padding=(0, 6), equal=False),
        border_style=_A4, padding=(0, 1),
        title=f"[{_A3}] ◆ foder [/{_A3}]", title_align="left",
        subtitle=f"[{_DIM}]v0.1.0 · local AI coding agent[/{_DIM}]", subtitle_align="right",
    ))
    console.print()


def _status() -> None:
    console.print(f"  [{_DIM}]model[/{_DIM}]  [{_A1}]{config.OLLAMA_MODEL}[/{_A1}]  "
                  f"[{_DIM}]workspace[/{_DIM}]  [{_A2}]{config.WORKSPACE}[/{_A2}]")


# ── Model picker ──────────────────────────────────────────────────────────────

def _pick_model(models: list[str]) -> str:
    table = Table(show_header=True, header_style=_DIM, box=box.SIMPLE_HEAD, padding=(0, 2))
    table.add_column("#", style=_DIM, width=4, justify="right")
    table.add_column("model", style=_A2)
    table.add_column("", style=_A3, width=2)
    for i, name in enumerate(models, 1):
        table.add_row(str(i), name, "◆" if name == config.OLLAMA_MODEL else "")
    console.print(table)
    while True:
        try:
            raw = input("  pick › ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if raw.isdigit() and 1 <= int(raw) <= len(models):
            return models[int(raw) - 1]
        if raw in models:
            return raw
        console.print(f"  [yellow]enter 1–{len(models)}[/yellow]")


def _select_model() -> None:
    with console.status(f"[{_DIM}]  connecting to Ollama...[/{_DIM}]",
                        spinner="dots2", spinner_style=_A3):
        try:
            models = list_models()
        except LLMError as e:
            console.print()
            console.print(Panel(f"[red]{e}[/red]", title="[red]connection error[/red]", border_style="red"))
            sys.exit(1)
    if not models:
        console.print(Panel(
            f"[yellow]No models found.[/yellow]\n\nPull one:\n  [{_A2}]ollama pull qwen2.5-coder:7b[/{_A2}]",
            title="[yellow]no models[/yellow]", border_style="yellow"))
        sys.exit(1)
    if config.OLLAMA_MODEL in models:
        return
    console.print(Panel(
        f"[{_A2}]{config.OLLAMA_MODEL}[/{_A2}] not found.\n[{_DIM}]Select a model:[/{_DIM}]",
        border_style=_A4, padding=(0, 1)))
    console.print()
    config.OLLAMA_MODEL = _pick_model(models)
    console.print(f"\n  [{_DIM}]using[/{_DIM}] [{_A1}]{config.OLLAMA_MODEL}[/{_A1}]\n")


# ── Shell ─────────────────────────────────────────────────────────────────────

_RISKY = ("sudo ","apt ","apt-get ","pip install","npm install","yarn add",
          "rm ","mv ","chmod ","chown ","curl ","wget ","systemctl","service ","kill ","pkill ")

def _confirm(prompt: str) -> bool:
    try:
        return input(f"  {prompt} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def _ls_colored(path: str = ".") -> None:
    """Render directory listing with dirs and files in different colors."""
    target = (_cwd / path).resolve()
    if not target.is_dir():
        console.print(f"  [red]not a directory:[/red] {path}")
        return
    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        console.print(f"  [red]permission denied:[/red] {path}")
        return

    if not entries:
        console.print(f"  [{_DIM}]empty[/{_DIM}]")
        return

    # Build columns: dirs first (accent color + /), then files (white)
    items = []
    for e in entries:
        if e.is_dir():
            items.append(Text(e.name + "/", style=f"bold {_A2}"))
        elif e.is_symlink():
            items.append(Text(e.name + "@", style=f"{_A1}"))
        else:
            # Color by extension
            ext = e.suffix.lower()
            if ext in (".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp", ".java"):
                style = "white"
            elif ext in (".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"):
                style = f"{_A1}"
            elif ext in (".md", ".txt", ".rst"):
                style = _DIM
            elif ext in (".sh", ".bash", ".zsh", ".ps1"):
                style = "yellow"
            elif ext in (".html", ".css", ".scss"):
                style = "cyan"
            else:
                style = "white"
            items.append(Text(e.name, style=style))

    # Print in a grid — up to 4 columns
    col_width = max(len(str(i)) for i in items) + 2
    cols      = max(1, min(4, console.width // col_width))
    row       = []
    for i, item in enumerate(items):
        row.append(item)
        if len(row) == cols or i == len(items) - 1:
            line = Text()
            for j, cell in enumerate(row):
                line.append_text(cell)
                if j < len(row) - 1:
                    line.append(" " * (col_width - len(str(cell))))
            console.print("  ", end="")
            console.print(line)
            row = []


def _run_shell(command: str) -> None:
    global _cwd
    command = command.strip()
    if not command:
        console.print(f"  [{_DIM}]cwd →[/{_DIM}] [{_A2}]{_cwd}[/{_A2}]")
        return

    # Intercept ls/ll — render with colors
    if command in ("ls", "ll", "ls -la", "ls -l", "ls -a") or command.startswith("ls "):
        path = "."
        parts = command.split()
        # Extract path argument if present (skip flags)
        for p in parts[1:]:
            if not p.startswith("-"):
                path = p
                break
        console.print(Rule(f"[{_DIM}]$ {command}[/{_DIM}]", style=_A5, align="left"))
        _ls_colored(path)
        console.print(Rule(f"[{_DIM}]✓[/{_DIM}]", style=_A5, align="left"))
        return

    if command == "cd" or command.startswith(("cd ", "cd\t")):
        parts  = command.split(None, 1)
        target = parts[1] if len(parts) > 1 else str(Path.home())
        new    = (_cwd / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
        if new.is_dir():
            _cwd = new; config.WORKSPACE = new
            console.print(f"  [{_DIM}]cwd →[/{_DIM}] [{_A2}]{_cwd}[/{_A2}]")
        else:
            console.print(f"  [red]no such directory:[/red] {target}")
        return
    try:
        validate_command(command)
    except SecurityError as e:
        console.print(Panel(f"[red]{e}[/red]", title="[red]blocked[/red]", border_style="red"))
        return

    # Auto-add --color=auto to ls on Linux/macOS
    if command == "ls" or command.startswith("ls "):
        if "--color" not in command:
            command = command.replace("ls", "ls --color=auto", 1)
    cmd_lower = command.lower()
    if any(cmd_lower.startswith(p) or f" {p}" in cmd_lower for p in _RISKY):
        console.print(f"  [yellow]risky:[/yellow] {command}")
        if not _confirm("run anyway?"):
            console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return

    console.print(Rule(f"[{_DIM}]$ {command}[/{_DIM}]", style=_A5, align="left"))
    proc = None; start = time.monotonic()
    try:
        proc = subprocess.Popen(command, shell=True, cwd=str(_cwd),
                                stdout=sys.stdout, stderr=sys.stderr, text=True)
        proc.wait(timeout=config.SHELL_TIMEOUT)
        elapsed = time.monotonic() - start
        code = proc.returncode
        if code in (0, None):
            console.print(Rule(f"[{_DIM}]✓  {elapsed:.2f}s[/{_DIM}]", style=_A5, align="left"))
        else:
            console.print(Rule(f"[red]✗  exit {code}  ({elapsed:.2f}s)[/red]", style="red", align="left"))
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        console.print(f"\n  [yellow]still running after {elapsed:.0f}s[/yellow]")
        if _confirm("terminate?"):
            if proc: proc.kill(); proc.wait()
            console.print(Rule(f"[{_DIM}]terminated[/{_DIM}]", style=_A5, align="left"))
        else:
            console.print(f"  [{_DIM}]left running[/{_DIM}]")
    except KeyboardInterrupt:
        if proc: proc.kill(); proc.wait()
        console.print(Rule(f"[{_DIM}]interrupted[/{_DIM}]", style=_A5, align="left"))
    except Exception as e:
        console.print(f"  [red]error:[/red] {e}")


# ── Tool display + undo ───────────────────────────────────────────────────────

_TOOL_LABEL = {"file_read": "read", "file_write": "write", "dir_list": "list", "shell_exec": "exec"}


def _on_tool_call(tool_name: str, parameters: dict) -> None:
    label = _TOOL_LABEL.get(tool_name, tool_name)
    hint  = ""
    if "path" in parameters:
        hint = parameters["path"]
        if tool_name == "file_write":
            try:
                from foder.security import validate_path
                target = validate_path(parameters["path"])
                before = target.read_bytes() if target.exists() else b""
                _undo_store[str(target)] = before
                _last_write.update({"path": str(target), "before": before,
                                    "after": parameters.get("content", "").encode()})
            except Exception:
                pass
    elif "command" in parameters:
        short = parameters["command"][:60]
        hint  = short + ("…" if len(parameters["command"]) > 60 else "")

    t = Text()
    t.append("  ▸ ", style=_A4)
    t.append(label, style=_A2)
    if hint:
        t.append("  " + hint, style=_DIM)
    console.print(t)


# ── Auto-run ──────────────────────────────────────────────────────────────────

def _auto_run() -> None:
    cwd = _cwd
    for marker, cmd in [
        (cwd/"package.json", "npm start"), (cwd/"Cargo.toml", "cargo run"),
        (cwd/"go.mod", "go run ."),        (cwd/"Makefile", "make"),
        (cwd/"manage.py", "python manage.py runserver"),
    ]:
        if marker.exists():
            console.print(f"  [{_DIM}]→[/{_DIM}] [{_A2}]{cmd}[/{_A2}]")
            _run_shell(cmd); return
    py = list(cwd.glob("*.py"))
    if py:
        f = (cwd/"main.py") if (cwd/"main.py").exists() else py[0]
        cmd = f"python {f.name}"
        console.print(f"  [{_DIM}]→[/{_DIM}] [{_A2}]{cmd}[/{_A2}]")
        _run_shell(cmd); return
    c = list(cwd.glob("*.c"))
    if c:
        cmd = f"gcc {c[0].name} -o {c[0].stem} && ./{c[0].stem}"
        console.print(f"  [{_DIM}]→[/{_DIM}] [{_A2}]{cmd}[/{_A2}]")
        _run_shell(cmd); return
    console.print(f"  [{_DIM}]cannot detect project type - use[/{_DIM}] [{_A2}]! <cmd>[/{_A2}]")


# ── Git context ───────────────────────────────────────────────────────────────

def _get_git_context() -> str:
    try:
        import subprocess as _sp
        branch = _sp.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                   cwd=str(_cwd), stderr=_sp.DEVNULL, timeout=3).decode().strip()
        status = _sp.check_output(["git","status","--short"],
                                   cwd=str(_cwd), stderr=_sp.DEVNULL, timeout=3).decode().strip()
        last   = _sp.check_output(["git","log","--oneline","-1"],
                                   cwd=str(_cwd), stderr=_sp.DEVNULL, timeout=3).decode().strip()
        parts  = [f"git branch: {branch}"]
        if last:   parts.append(f"last commit: {last}")
        if status: parts.append(f"changed files: {len(status.splitlines())}")
        return "  ".join(parts)
    except Exception:
        return ""


# ── Architecture diagram ──────────────────────────────────────────────────────

def _print_arch() -> None:
    """Render the foder architecture as a styled diagram."""

    W  = _A2   # main color
    D  = _DIM  # dim
    B  = _A4   # border/box color
    H  = _A1   # highlight

    lines = [
        (D,  "                    foder architecture                    "),
        (D,  ""),
        (W,  "  ┌─────────────────────────────────────────────────┐    "),
        (W,  "  │                    USER                          │    "),
        (W,  "  │         (types a prompt in the terminal)         │    "),
        (W,  "  └───────────────────────┬─────────────────────────┘    "),
        (D,  "                          │                               "),
        (D,  "                          ▼                               "),
        (H,  "  ┌─────────────────────────────────────────────────┐    "),
        (H,  "  │               FODER CLI  (main.py)               │    "),
        (H,  "  │   prompt · tab complete · themes · session       │    "),
        (H,  "  └──────────────┬──────────────────────────────────┘    "),
        (D,  "                 │                                        "),
        (D,  "                 ▼                                        "),
        (W,  "  ┌─────────────────────────────────────────────────┐    "),
        (W,  "  │             AGENT LOOP  (agent.py)               │    "),
        (W,  "  │   detect tool call · execute · loop · stream     │    "),
        (W,  "  └────────┬──────────────────────────┬─────────────┘    "),
        (D,  "           │                          │                   "),
        (D,  "           ▼                          ▼                   "),
        (B,  "  ┌─────────────────┐      ┌──────────────────────┐      "),
        (B,  "  │  TOOL SYSTEM    │      │  OLLAMA  (local LLM)  │      "),
        (B,  "  │  (tools/)       │      │  qwen · llama · etc   │      "),
        (B,  "  │                 │      │  runs on your machine  │      "),
        (B,  "  │  file_read      │      │  no cloud · no keys   │      "),
        (B,  "  │  file_write     │      └──────────────────────┘      "),
        (B,  "  │  dir_list       │                                     "),
        (B,  "  │  shell_exec     │                                     "),
        (B,  "  └────────┬────────┘                                     "),
        (D,  "           │                                              "),
        (D,  "           ▼                                              "),
        (W,  "  ┌─────────────────────────────────────────────────┐    "),
        (W,  "  │              FILE SYSTEM / SHELL                 │    "),
        (W,  "  │   your project files · terminal commands         │    "),
        (W,  "  └─────────────────────────────────────────────────┘    "),
        (D,  ""),
    ]

    console.print()
    for style, line in lines:
        console.print(Text(line, style=style))
    console.print()


# ── Slash commands ────────────────────────────────────────────────────────────

def _handle_slash(cmd: str, history: list[dict]) -> tuple[bool, list[dict]]:
    parts = cmd.strip().split(None, 1)
    verb  = parts[0].lower()
    arg   = parts[1] if len(parts) > 1 else ""

    if verb in ("/exit", "/quit"):
        _save_session(history); unload_model(); _print_exit(history, _session_start); sys.exit(0)

    if verb == "/clear":
        history.clear(); _save_session([])
        sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
        _print_banner(); return True, history

    if verb == "/workspace":
        console.print(f"  [{_A2}]{config.WORKSPACE}[/{_A2}]"); return True, history

    if verb == "/last":
        if not _last_response:
            console.print(f"  [{_DIM}]no previous response[/{_DIM}]")
        else:
            is_md = any(c in _last_response for c in ("```", "**", "##", "\n- ", "\n* ", "\n1."))
            label = Text(); label.append("  ◆ ", style=_A3); label.append("foder", style=_A1)
            if is_md:
                console.print(label); console.print()
                console.print(Panel(Markdown(_last_response), border_style=_A5, padding=(1, 2)))
            else:
                console.print(label, end="  "); console.print(_last_response)
        return True, history

    if verb == "/model":
        console.print(f"  [bold {_A1}]{config.OLLAMA_MODEL}[/bold {_A1}]"); return True, history

    if verb == "/models":
        try:
            models = list_models()
        except LLMError as e:
            console.print(f"  [red]{e}[/red]"); return True, history
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        for name in models:
            active = name == config.OLLAMA_MODEL
            table.add_row(Text("◆" if active else " ", style=_A3 if active else _DIM),
                          Text(name, style=f"bold {_A1}" if active else _A2))
        console.print(table); return True, history

    if verb == "/switch":
        try:
            models = list_models()
        except LLMError as e:
            console.print(f"  [red]{e}[/red]"); return True, history
        if arg and arg in models:
            config.OLLAMA_MODEL = arg; _status(); return True, history
        console.print(f"  [{_DIM}]select a model:[/{_DIM}]\n")
        config.OLLAMA_MODEL = _pick_model(models)
        console.print(); _status(); return True, history

    if verb == "/theme":
        if arg and arg in THEMES:
            _apply_theme(arg); _save_theme(arg)
            console.print(f"  [{_DIM}]theme →[/{_DIM}] [{_A2}]{THEMES[arg]['name']}[/{_A2}]")
            return True, history
        key = _pick_theme()
        _apply_theme(key); _save_theme(key)
        console.print(f"\n  [{_DIM}]theme →[/{_DIM}] [{_A2}]{THEMES[key]['name']}[/{_A2}]")
        return True, history

    if verb == "/undo":
        if not _last_write.get("path"):
            console.print(f"  [{_DIM}]nothing to undo[/{_DIM}]"); return True, history
        path   = _last_write["path"]
        before = _undo_store.get(path, b"")
        try:
            p = Path(path)
            if before:
                p.write_bytes(before)
                console.print(f"  [{_A2}]restored[/{_A2}]  [{_DIM}]{path}[/{_DIM}]")
            else:
                p.unlink(missing_ok=True)
                console.print(f"  [{_A2}]deleted[/{_A2}]  [{_DIM}]{path}[/{_DIM}]")
            _undo_store.pop(path, None); _last_write.clear()
        except Exception as e:
            console.print(f"  [red]undo failed:[/red] {e}")
        return True, history

    if verb == "/diff":
        if not _last_write.get("path"):
            console.print(f"  [{_DIM}]no recent write[/{_DIM}]"); return True, history
        before = _last_write["before"].decode("utf-8", errors="replace").splitlines(keepends=True)
        after  = _last_write["after"].decode("utf-8", errors="replace").splitlines(keepends=True)
        diff   = list(difflib.unified_diff(before, after, fromfile="before", tofile="after", lineterm=""))
        if not diff:
            console.print(f"  [{_DIM}]no changes[/{_DIM}]"); return True, history
        out = Text()
        for line in diff[:80]:
            if   line.startswith("+") and not line.startswith("+++"): out.append(line+"\n", style=_OK)
            elif line.startswith("-") and not line.startswith("---"): out.append(line+"\n", style=_ERR)
            elif line.startswith("@@"):                                out.append(line+"\n", style=_A2)
            else:                                                      out.append(line+"\n", style=_DIM)
        console.print(Panel(out, border_style=_A5,
                            title=f"[{_DIM}]{_last_write['path']}[/{_DIM}]", padding=(0,1)))
        return True, history

    if verb == "/run":
        _auto_run(); return True, history

    if verb == "/arch":
        _print_arch(); return True, history

    if verb == "/help":
        console.print()
        console.print(Rule(f"[{_DIM}]  commands  [/{_DIM}]", style=_A5))
        t = Table(show_header=False, box=None, padding=(0, 2))
        for c, d in _COMMANDS.items():
            t.add_row(Text(c, style=f"bold {_A2}"), Text(d, style=_DIM))
        console.print(t)
        console.print()
        console.print(Rule(f"[{_DIM}]  shortcuts  [/{_DIM}]", style=_A5))
        s = Table(show_header=False, box=None, padding=(0, 2))
        s.add_row(Text("! <cmd>",     style=f"bold {_A2}"), Text("run shell command",       style=_DIM))
        s.add_row(Text("! cd <path>", style=f"bold {_A2}"), Text("change directory",        style=_DIM))
        s.add_row(Text("@filename",   style=f"bold {_A2}"), Text("inject file into prompt", style=_DIM))
        console.print(s)
        console.print()
        return True, history

    console.print(f"  [yellow]unknown:[/yellow] {verb}  [{_DIM}](try /help)[/{_DIM}]")
    return True, history


# ── Prompt ────────────────────────────────────────────────────────────────────

# ── Tab completer ─────────────────────────────────────────────────────────────

class FoderCompleter(Completer):
    """Tab completion for slash commands and @filenames."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        if text.startswith("/"):
            word = text.lstrip("/").lower()
            for cmd in _COMMANDS:
                if cmd.lstrip("/").startswith(word):
                    yield Completion(cmd, start_position=-len(text))
            return

        at_pos = text.rfind("@")
        if at_pos != -1:
            partial = text[at_pos + 1:]
            try:
                for p in sorted(_cwd.iterdir()):
                    if p.name.startswith(partial):
                        yield Completion(
                            p.name,
                            start_position=-len(partial),
                            display=p.name + ("/" if p.is_dir() else ""),
                        )
            except Exception:
                pass


def _prompt_label() -> HTML:
    try:
        rel  = _cwd.relative_to(config.WORKSPACE)
        path = f"foder/{rel}" if str(rel) != "." else "foder"
    except ValueError:
        path = str(_cwd)
    model = config.OLLAMA_MODEL.split(":")[0]
    return HTML(f'<style color="{_DIM}">{model}</style>'
                f'<style color="{_A5}"> ❙ </style>'
                f'<prompt>{path} ❯ </prompt>')


# ── Response renderer - streams live ─────────────────────────────────────────

def _render_response(token_gen) -> str:
    """
    Stream tokens to the terminal as they arrive.
    Collects full text, then re-renders markdown in a panel if needed.
    Returns the full response string.
    """
    global _last_response

    label = Text()
    label.append("  ◆ ", style=_A3)
    label.append("foder", style=_A1)
    console.print(label, end="  ")

    collected = []
    try:
        for token in token_gen:
            # Print each token immediately - no buffering
            console.print(token, end="", markup=False)
            collected.append(token)
        console.print()  # newline after stream ends
    except KeyboardInterrupt:
        console.print()
        console.print(Text("  cancelled", style=_DIM))

    full = "".join(collected).strip()
    _last_response = full  # store for /last

    # If markdown detected, re-render cleanly in a panel below
    if full and any(c in full for c in ("```", "**", "##", "\n- ", "\n* ", "\n1.")):
        console.print()
        console.print(Panel(Markdown(full), border_style=_A5, padding=(1, 2)))

    return full


# ── Session ───────────────────────────────────────────────────────────────────

def _load_session() -> list[dict]:
    try:
        if _HISTORY_FILE.exists():
            data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[-_MAX_SAVED_MESSAGES:]
    except Exception:
        pass
    return []


def _save_session(history: list[dict]) -> None:
    try:
        _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        _HISTORY_FILE.write_text(
            json.dumps(history[-_MAX_SAVED_MESSAGES:], ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ── @file injection ───────────────────────────────────────────────────────────

def _inject_file_context(user_input: str) -> str:
    import re
    pattern = re.compile(r"@([\w./\-]+)")
    matches = pattern.findall(user_input)
    if not matches:
        return user_input
    injected = []
    for ref in matches:
        try:
            from foder.security import validate_path
            target = validate_path(ref)
            if not target.is_file():
                continue
            raw = target.read_bytes()
            if len(raw) > 32_000:
                injected.append(f"[{ref} - too large, use file_read]")
                continue
            injected.append(f"--- @{ref} ---\n{raw.decode('utf-8', errors='replace')}\n--- end {ref} ---")
        except Exception:
            continue
    if not injected:
        return user_input
    clean = pattern.sub("", user_input).strip()
    return "\n\n".join(injected) + f"\n\n{clean}"


# ── Exit screen ───────────────────────────────────────────────────────────────

def _print_exit(history: list[dict], start_time: float) -> None:
    import datetime
    elapsed  = time.monotonic() - start_time
    mins, secs = int(elapsed // 60), int(elapsed % 60)
    duration = f"{mins}m {secs}s" if mins else f"{secs}s"
    turns    = sum(1 for m in history if m["role"] == "user" and not m["content"].startswith("[tool:"))
    now      = datetime.datetime.now().strftime("%H:%M")
    grid = Table.grid(padding=(0, 4))
    grid.add_row(Text("  ended    ", style=_DIM), Text(now,                 style=_A1))
    grid.add_row(Text("  duration ", style=_DIM), Text(duration,            style=_A1))
    grid.add_row(Text("  messages ", style=_DIM), Text(str(turns),          style=_A1))
    grid.add_row(Text("  model    ", style=_DIM), Text(config.OLLAMA_MODEL, style=_A2))
    console.print()
    console.print(Panel(grid, border_style=_A4, padding=(0, 2),
                        title=f"[{_A3}] ◆ foder [/{_A3}]", title_align="left",
                        subtitle=f"[{_DIM}]session saved · model unloaded[/{_DIM}]", subtitle_align="right"))
    console.print()


# ── Main REPL ─────────────────────────────────────────────────────────────────

def main() -> None:
    global _cwd, _session_start, _last_shell_cmd

    # ── CLI argument mode - foder "do something" ──────────────────────────
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        config.load_project_config()
        _apply_theme(_load_theme())
        _select_model()
        _cwd = config.WORKSPACE
        history: list[dict] = []
        token_gen, _ = run(prompt, history, on_tool_call=_on_tool_call)
        for token in token_gen:
            sys.stdout.write(token)
            sys.stdout.flush()
        sys.stdout.write("\n")
        return

    config.load_project_config()
    _select_model()
    _cwd = config.WORKSPACE
    _print_banner()

    # Persist prompt history across sessions for Ctrl+R search
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(_PROMPT_HISTORY)),
        style=_PROMPT_STYLE,
        completer=FoderCompleter(),
        complete_while_typing=False,   # only complete on Tab
    )

    conversation_history: list[dict] = _load_session()
    if conversation_history:
        console.print(f"  [{_A3}]◆[/{_A3}] [{_DIM}]resumed {len(conversation_history)} messages[/{_DIM}]\n")

    _session_start = time.monotonic()

    while True:
        try:
            user_input = session.prompt(_prompt_label, style=_PROMPT_STYLE)
        except (EOFError, KeyboardInterrupt):
            _save_session(conversation_history)
            _print_exit(conversation_history, _session_start)
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # ── cd shortcut — no need to type !cd ─────────────────────────────
        if user_input.startswith("cd ") or user_input == "cd":
            console.print()
            _run_shell(user_input)
            console.print()
            continue

        # ── !! re-run last shell command ───────────────────────────────────
        if user_input == "!!":
            if not _last_shell_cmd:
                console.print(f"  [{_DIM}]no previous command[/{_DIM}]\n")
            else:
                console.print()
                _run_shell(_last_shell_cmd)
                console.print()
            continue

        # ── Shell passthrough ──────────────────────────────────────────────
        if user_input.startswith("!"):
            cmd = user_input[1:].strip()
            _last_shell_cmd = cmd   # save for !!
            console.print()
            _run_shell(cmd)
            console.print()
            continue

        # ── Slash commands ─────────────────────────────────────────────────
        if user_input.startswith("/"):
            console.print()
            _, conversation_history = _handle_slash(user_input, conversation_history)
            console.print()
            continue

        # ── @file injection ────────────────────────────────────────────────
        resolved = _inject_file_context(user_input)

        # ── Agent turn ─────────────────────────────────────────────────────
        console.print()
        you = Text()
        you.append("  you  ", style=f"bold {_A2}")
        you.append(user_input, style="white")
        console.print(you)
        console.print(Rule(style=_A5))
        console.print()

        # Show thinking indicator, then stream response live
        # Tool calls print via _on_tool_call during the run() call
        console.print(Text("  ◆ thinking...", style=_DIM), end="\r")

        try:
            token_gen, conversation_history = run(
                resolved, conversation_history, on_tool_call=_on_tool_call)
        except KeyboardInterrupt:
            console.print(Text("  cancelled", style=_DIM))
            continue

        # Clear the thinking line before streaming
        console.print(" " * 30, end="\r")

        full = _render_response(token_gen)
        _save_session(conversation_history)

        if full.strip().startswith("[llm error]"):
            msg = full.strip()
            if "timed out" in msg:
                hint = (f"[yellow]Ollama timed out.[/yellow]\n\n"
                        f"  [{_DIM}]took longer than[/{_DIM}] [{_A2}]{config.LLM_TIMEOUT:.0f}s[/{_A2}]\n\n"
                        f"  [{_DIM}]try smaller tasks  →[/{_DIM}]  e.g. 'make index.html' then 'make style.css'\n"
                        f"  [{_DIM}]faster model       →[/{_DIM}]  /switch\n"
                        f"  [{_DIM}]raise limit        →[/{_DIM}]  FODER_LLM_TIMEOUT=900 foder")
            elif "Cannot connect" in msg:
                hint = "[yellow]Cannot reach Ollama.[/yellow]\n\n  ollama serve"
            else:
                hint = f"[yellow]{msg}[/yellow]"
            console.print(Panel(hint, border_style="yellow", padding=(0, 1)))

        console.print()
        console.print(Rule(style=_A5))
        console.print()


if __name__ == "__main__":
    main()
