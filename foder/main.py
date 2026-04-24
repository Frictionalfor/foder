"""Foder CLI - fast, clean, shows work."""
import sys, time, json, subprocess, difflib, re
import foder.config as config
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import is_done
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
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

# ── Themes ────────────────────────────────────────────────────────────────────

THEMES = {
    "green": {"name":"Green","desc":"classic terminal green",
              "A1":"#BBF7D0","A2":"#4ADE80","A3":"#16A34A","A4":"#166534","A5":"#052E16",
              "logo":["#BBF7D0","#4ADE80","#4ADE80","#16A34A","#166534"]},
    "teal":  {"name":"Cyber Teal","desc":"sharp, technical, hacker-ish",
              "A1":"#67E8F9","A2":"#06B6D4","A3":"#0E7490","A4":"#155E75","A5":"#164E63",
              "logo":["#A5F3FC","#67E8F9","#06B6D4","#0E7490","#164E63"]},
    "amber": {"name":"Amber","desc":"warm, energetic, stands out",
              "A1":"#FDE68A","A2":"#F59E0B","A3":"#B45309","A4":"#78350F","A5":"#451A03",
              "logo":["#FDE68A","#FCD34D","#F59E0B","#B45309","#451A03"]},
    "rose":  {"name":"Rose","desc":"bold, modern, memorable",
              "A1":"#FECDD3","A2":"#FB7185","A3":"#E11D48","A4":"#9F1239","A5":"#4C0519",
              "logo":["#FECDD3","#FDA4AF","#FB7185","#E11D48","#9F1239"]},
    "blue":  {"name":"Electric Blue","desc":"clean, professional",
              "A1":"#BAE6FD","A2":"#38BDF8","A3":"#0284C7","A4":"#075985","A5":"#0C4A6E",
              "logo":["#BAE6FD","#7DD3FC","#38BDF8","#0284C7","#0369A1"]},
    "lime":  {"name":"Neon Lime","desc":"aggressive, terminal-native",
              "A1":"#D9F99D","A2":"#A3E635","A3":"#65A30D","A4":"#3F6212","A5":"#1A2E05",
              "logo":["#D9F99D","#BEF264","#A3E635","#65A30D","#3F6212"]},
}

_THEME_FILE = Path.home() / ".foder" / "theme.json"
_A1 = _A2 = _A3 = _A4 = _A5 = ""
_DIM = "#6B7280"
_OK  = "#86efac"
_ERR = "#fca5a5"
_LOGO_COLORS: list[str] = []
_PROMPT_STYLE: Style    = Style.from_dict({})


def _apply_theme(key: str) -> None:
    global _A1,_A2,_A3,_A4,_A5,_LOGO_COLORS,_PROMPT_STYLE,_logo_cache
    t = THEMES.get(key, THEMES["green"])
    _A1=t["A1"]; _A2=t["A2"]; _A3=t["A3"]; _A4=t["A4"]; _A5=t["A5"]
    _LOGO_COLORS = t["logo"]
    _PROMPT_STYLE = Style.from_dict({"prompt": f"{_A2} bold"})
    _logo_cache = None

def _save_theme(key: str) -> None:
    try:
        _THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
        _THEME_FILE.write_text(json.dumps({"theme": key}), encoding="utf-8")
    except Exception: pass

def _load_theme() -> str:
    try:
        if _THEME_FILE.exists():
            d = json.loads(_THEME_FILE.read_text(encoding="utf-8"))
            k = d.get("theme","green")
            if k in THEMES: return k
    except Exception: pass
    return "green"

def _pick_theme() -> str:
    keys = list(THEMES.keys())
    console.print()
    table = Table(show_header=True, header_style=_DIM, box=box.SIMPLE_HEAD, padding=(0,2))
    table.add_column("#", style=_DIM, width=4, justify="right")
    table.add_column("theme", style="bold")
    table.add_column("desc",  style=_DIM)
    table.add_column("",      width=3)
    for i,key in enumerate(keys,1):
        t = THEMES[key]
        table.add_row(str(i), Text(t["name"], style=t["A2"]), t["desc"],
                      "◆" if key==_load_theme() else "")
    console.print(table); console.print()
    while True:
        try: raw = input("  pick › ").strip()
        except (EOFError, KeyboardInterrupt): return _load_theme()
        if raw.isdigit() and 1<=int(raw)<=len(keys): return keys[int(raw)-1]
        if raw in keys: return raw
        console.print(f"  [yellow]enter 1-{len(keys)}[/yellow]")

_apply_theme(_load_theme())

# ── Globals ───────────────────────────────────────────────────────────────────

_HISTORY_DIR        = Path.home() / ".foder"
_HISTORY_FILE       = _HISTORY_DIR / "session.json"
_PROMPT_HISTORY     = _HISTORY_DIR / "prompt_history"
_SNAPSHOT_FILE      = _HISTORY_DIR / "snapshot.json"
_MAX_SAVED_MESSAGES = 20

_cwd: Path            = config.WORKSPACE
_session_start: float = 0.0
_undo_store: dict     = {}
_last_write: dict     = {}
_last_shell_cmd: str  = ""
_last_response: str   = ""
_logo_cache           = None
_pinned_files: list   = []       # /pin - files injected into every prompt
_session_tool_calls   = 0        # /cost counter
_session_files_written= 0        # /cost counter

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
    "/git":       "show git status",
    "/pin":       "pin a file to every prompt",
    "/unpin":     "remove pinned file",
    "/pins":      "list pinned files",
    "/snapshot":  "snapshot workspace state",
    "/cost":      "show session stats",
    "/arch":      "show architecture diagram",
    "/help":      "show this help",
    "/exit":      "quit",
}

# ── Logo ──────────────────────────────────────────────────────────────────────

_LOGO = [
    "  ███████  ██████  ██████  ███████ ██████  ",
    "  ██      ██    ██ ██   ██ ██      ██   ██ ",
    "  █████   ██    ██ ██   ██ █████   ██████  ",
    "  ██      ██    ██ ██   ██ ██      ██   ██ ",
    "  ██       ██████  ██████  ███████ ██   ██ ",
]

def _hex_to_rgb(h):
    h=h.lstrip("#"); return int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
def _lerp_color(c1,c2,t):
    return f"#{int(c1[0]+(c2[0]-c1[0])*t):02x}{int(c1[1]+(c2[1]-c1[1])*t):02x}{int(c1[2]+(c2[2]-c1[2])*t):02x}"
def _darken(h,f=0.35):
    r,g,b=_hex_to_rgb(h); return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"
def _brighten(h,f=1.6):
    r,g,b=_hex_to_rgb(h); return f"#{min(255,int(r*f)):02x}{min(255,int(g*f)):02x}{min(255,int(b*f)):02x}"

def _logo() -> Text:
    global _logo_cache
    if _logo_cache is not None: return _logo_cache
    rows=len(_LOGO); colors=_LOGO_COLORS[:rows]; text=Text()
    max_len=max(len(l) for l in _LOGO); lines=[l.ljust(max_len) for l in _LOGO]
    for ri,line in enumerate(lines):
        fr=_hex_to_rgb(colors[ri]); nr=_hex_to_rgb(colors[min(ri+1,rows-1)])
        is_top=ri==0; is_bot=ri==rows-1
        for ci,ch in enumerate(line):
            t=ci/max(max_len-1,1); base=_lerp_color(fr,nr,t*0.35)
            bright=_brighten(base,1.8); mid=_brighten(base,1.2)
            dark=_darken(base,0.45); deep=_darken(base,0.22)
            if ch!="█":
                lb=ci>0 and lines[ri][ci-1]=="█"
                ab=ri>0 and ci<len(lines[ri-1]) and lines[ri-1][ci]=="█"
                if lb: text.append("▌",style=dark)
                elif ab and not is_top: text.append("▀",style=deep)
                else: text.append(" ")
            else:
                if is_top: text.append("█",style=f"bold {bright}")
                elif is_bot: text.append("█",style=f"bold {mid}")
                elif ci<3 or (ci>0 and lines[ri][ci-1]!="█"): text.append("█",style=f"bold {bright}")
                else: text.append("█",style=f"bold {base}")
        text.append("\n")
    sr=_darken(colors[-1],0.18); text.append(" ")
    for ci,ch in enumerate(lines[-1]):
        if ch=="█": text.append("▀",style=sr)
        else:
            lb=ci>0 and lines[-1][ci-1]=="█"
            text.append("▄" if lb else " ",style=sr)
    text.append("\n")
    _logo_cache=text; return text


# ── Banner ────────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    meta = Table.grid(padding=(0,1))
    meta.add_row(Text("  workspace",style=_DIM), Text(str(config.WORKSPACE),style=_A2))
    meta.add_row(Text("  model    ",style=_DIM), Text(config.OLLAMA_MODEL,  style=f"bold {_A1}"))
    meta.add_row(Text("",style=""), Text("",style=""))
    meta.add_row(Text("  ! <cmd>  ",style=_DIM), Text("shell command",      style=_DIM))
    meta.add_row(Text("  @file    ",style=_DIM), Text("inject file context",style=_DIM))
    meta.add_row(Text("  /help    ",style=_DIM), Text("all commands",       style=_DIM))
    console.print()
    console.print(Panel(
        Columns([_logo(),meta],padding=(0,6),equal=False),
        border_style=_A4,padding=(0,1),
        title=f"[{_A3}] ◆ foder [/{_A3}]",title_align="left",
        subtitle=f"[{_DIM}]v0.1.0 · local AI coding agent[/{_DIM}]",subtitle_align="right",
    ))
    console.print()

def _status() -> None:
    console.print(f"  [{_DIM}]model[/{_DIM}]  [{_A1}]{config.OLLAMA_MODEL}[/{_A1}]  "
                  f"[{_DIM}]workspace[/{_DIM}]  [{_A2}]{config.WORKSPACE}[/{_A2}]")


# ── Model picker ──────────────────────────────────────────────────────────────

def _pick_model(models):
    table=Table(show_header=True,header_style=_DIM,box=box.SIMPLE_HEAD,padding=(0,2))
    table.add_column("#",style=_DIM,width=4,justify="right")
    table.add_column("model",style=_A2)
    table.add_column("",style=_A3,width=2)
    for i,name in enumerate(models,1):
        table.add_row(str(i),name,"◆" if name==config.OLLAMA_MODEL else "")
    console.print(table)
    while True:
        try: raw=input("  pick › ").strip()
        except (EOFError,KeyboardInterrupt): sys.exit(0)
        if raw.isdigit() and 1<=int(raw)<=len(models): return models[int(raw)-1]
        if raw in models: return raw
        console.print(f"  [yellow]enter 1-{len(models)}[/yellow]")

def _select_model() -> None:
    with console.status(f"[{_DIM}]  connecting to Ollama...[/{_DIM}]",spinner="dots2",spinner_style=_A3):
        try: models=list_models()
        except LLMError as e:
            console.print(); console.print(Panel(f"[red]{e}[/red]",title="[red]connection error[/red]",border_style="red")); sys.exit(1)
    if not models:
        console.print(Panel(f"[yellow]No models found.[/yellow]\n\nPull one:\n  [{_A2}]ollama pull qwen2.5-coder:3b[/{_A2}]",
                            title="[yellow]no models[/yellow]",border_style="yellow")); sys.exit(1)
    if config.OLLAMA_MODEL in models: return
    console.print(Panel(f"[{_A2}]{config.OLLAMA_MODEL}[/{_A2}] not found.\n[{_DIM}]Select a model:[/{_DIM}]",
                        border_style=_A4,padding=(0,1))); console.print()
    config.OLLAMA_MODEL=_pick_model(models)
    console.print(f"\n  [{_DIM}]using[/{_DIM}] [{_A1}]{config.OLLAMA_MODEL}[/{_A1}]\n")


# ── Git helpers ───────────────────────────────────────────────────────────────

def _git_branch() -> str:
    """Return current git branch, empty string if not a git repo."""
    try:
        import subprocess as _sp
        return _sp.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                 cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=2).decode().strip()
    except Exception: return ""

def _get_git_context() -> str:
    try:
        import subprocess as _sp
        branch=_sp.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                  cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=3).decode().strip()
        status=_sp.check_output(["git","status","--short"],
                                  cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=3).decode().strip()
        last  =_sp.check_output(["git","log","--oneline","-1"],
                                  cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=3).decode().strip()
        parts=[f"git branch: {branch}"]
        if last:   parts.append(f"last commit: {last}")
        if status: parts.append(f"changed files: {len(status.splitlines())}")
        return "  ".join(parts)
    except Exception: return ""

def _print_git() -> None:
    """Render a rich git status panel."""
    try:
        import subprocess as _sp
        branch=_sp.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                  cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=3).decode().strip()
        status=_sp.check_output(["git","status","--short"],
                                  cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=3).decode().strip()
        last  =_sp.check_output(["git","log","--oneline","-3"],
                                  cwd=str(_cwd),stderr=_sp.DEVNULL,timeout=3).decode().strip()
    except Exception:
        console.print(f"  [{_DIM}]not a git repository[/{_DIM}]"); return

    out = Text()
    out.append(f"  branch  ", style=_DIM); out.append(branch+"\n", style=f"bold {_A2}")
    if status:
        out.append(f"\n  changes\n", style=_DIM)
        for line in status.splitlines():
            code=line[:2].strip()
            color = _OK if code in ("A","M","AM") else (_ERR if code in ("D","??") else _A1)
            out.append(f"    {line}\n", style=color)
    if last:
        out.append(f"\n  recent commits\n", style=_DIM)
        for line in last.splitlines():
            out.append(f"    {line}\n", style=_DIM)
    console.print(Panel(out, border_style=_A5, padding=(0,1),
                        title=f"[{_DIM}]git[/{_DIM}]", title_align="left"))


# ── Shell ─────────────────────────────────────────────────────────────────────

_RISKY = ("sudo ","apt ","apt-get ","pip install","npm install","yarn add",
          "rm ","mv ","chmod ","chown ","curl ","wget ","systemctl","service ","kill ","pkill ")

def _confirm(prompt: str) -> bool:
    try: return input(f"  {prompt} [y/N] ").strip().lower() in ("y","yes")
    except (EOFError,KeyboardInterrupt): return False

def _ls_colored(path: str=".") -> None:
    target=(_cwd/path).resolve()
    if not target.is_dir():
        console.print(f"  [red]not a directory:[/red] {path}"); return
    try: entries=sorted(target.iterdir(),key=lambda p:(p.is_file(),p.name.lower()))
    except PermissionError:
        console.print(f"  [red]permission denied:[/red] {path}"); return
    if not entries:
        console.print(f"  [{_DIM}]empty[/{_DIM}]"); return
    items=[]
    for e in entries:
        if e.is_dir(): items.append(Text(e.name+"/",style=f"bold {_A2}"))
        elif e.is_symlink(): items.append(Text(e.name+"@",style=_A1))
        else:
            ext=e.suffix.lower()
            if ext in (".py",".js",".ts",".go",".rs",".c",".cpp",".java"): s="white"
            elif ext in (".json",".yaml",".yml",".toml",".ini",".cfg"): s=_A1
            elif ext in (".md",".txt",".rst"): s=_DIM
            elif ext in (".sh",".bash",".zsh",".ps1"): s="yellow"
            elif ext in (".html",".css",".scss"): s="cyan"
            else: s="white"
            items.append(Text(e.name,style=s))
    col_width=max(len(str(i)) for i in items)+2
    cols=max(1,min(4,console.width//col_width)); row=[]
    for i,item in enumerate(items):
        row.append(item)
        if len(row)==cols or i==len(items)-1:
            line=Text()
            for j,cell in enumerate(row):
                line.append_text(cell)
                if j<len(row)-1: line.append(" "*(col_width-len(str(cell))))
            console.print("  ",end=""); console.print(line); row=[]

def _run_shell(command: str) -> None:
    global _cwd
    command=command.strip()
    if not command:
        console.print(f"  [{_DIM}]cwd →[/{_DIM}] [{_A2}]{_cwd}[/{_A2}]"); return
    # Intercept ls
    if command in ("ls","ll","ls -la","ls -l","ls -a") or command.startswith("ls "):
        path="."; parts=command.split()
        for p in parts[1:]:
            if not p.startswith("-"): path=p; break
        console.print(Rule(f"[{_DIM}]$ {command}[/{_DIM}]",style=_A5,align="left"))
        _ls_colored(path)
        console.print(Rule(f"[{_DIM}]✓[/{_DIM}]",style=_A5,align="left")); return
    # cd
    if command=="cd" or command.startswith(("cd ","cd\t")):
        parts=command.split(None,1)
        target=parts[1] if len(parts)>1 else str(Path.home())
        new=(_cwd/target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
        if new.is_dir():
            _cwd=new; config.WORKSPACE=new
            # Auto-reload foder.json when changing directories
            config.load_project_config()
            console.print(f"  [{_DIM}]cwd →[/{_DIM}] [{_A2}]{_cwd}[/{_A2}]")
        else:
            console.print(f"  [red]no such directory:[/red] {target}")
        return
    try: validate_command(command)
    except SecurityError as e:
        console.print(Panel(f"[red]{e}[/red]",title="[red]blocked[/red]",border_style="red")); return
    cmd_lower=command.lower()
    if any(cmd_lower.startswith(p) or f" {p}" in cmd_lower for p in _RISKY):
        console.print(f"  [yellow]risky:[/yellow] {command}")
        if not _confirm("run anyway?"):
            console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return
    console.print(Rule(f"[{_DIM}]$ {command}[/{_DIM}]",style=_A5,align="left"))
    proc=None; start=time.monotonic()
    try:
        proc=subprocess.Popen(command,shell=True,cwd=str(_cwd),
                               stdout=sys.stdout,stderr=sys.stderr,text=True)
        proc.wait(timeout=config.SHELL_TIMEOUT)
        elapsed=time.monotonic()-start; code=proc.returncode
        if code in (0,None):
            console.print(Rule(f"[{_DIM}]✓  {elapsed:.2f}s[/{_DIM}]",style=_A5,align="left"))
        else:
            console.print(Rule(f"[red]✗  exit {code}  ({elapsed:.2f}s)[/red]",style="red",align="left"))
    except subprocess.TimeoutExpired:
        elapsed=time.monotonic()-start
        console.print(f"\n  [yellow]still running after {elapsed:.0f}s[/yellow]")
        if _confirm("terminate?"):
            if proc: proc.kill(); proc.wait()
            console.print(Rule(f"[{_DIM}]terminated[/{_DIM}]",style=_A5,align="left"))
        else: console.print(f"  [{_DIM}]left running[/{_DIM}]")
    except KeyboardInterrupt:
        if proc: proc.kill(); proc.wait()
        console.print(Rule(f"[{_DIM}]interrupted[/{_DIM}]",style=_A5,align="left"))
    except Exception as e:
        console.print(f"  [red]error:[/red] {e}")


# ── Tool display + undo ───────────────────────────────────────────────────────

_TOOL_LABEL={"file_read":"read","file_write":"write","dir_list":"list",
             "dir_create":"mkdir","shell_exec":"exec"}

def _on_tool_call(tool_name: str, parameters: dict) -> None:
    global _session_tool_calls, _session_files_written
    _session_tool_calls += 1
    label=_TOOL_LABEL.get(tool_name,tool_name); hint=""
    if "path" in parameters:
        hint=parameters["path"]
        if tool_name=="file_write":
            _session_files_written += 1
            try:
                from foder.security import validate_path
                target=validate_path(parameters["path"])
                before=target.read_bytes() if target.exists() else b""
                _undo_store[str(target)]=before
                _last_write.update({"path":str(target),"before":before,
                                    "after":parameters.get("content","").encode()})
            except Exception: pass
    elif "command" in parameters:
        short=parameters["command"][:60]
        hint=short+("..." if len(parameters["command"])>60 else "")
    t=Text(); t.append("  ▸ ",style=_A4); t.append(label,style=_A2)
    if hint: t.append("  "+hint,style=_DIM)
    console.print(t)


# ── Auto-run ──────────────────────────────────────────────────────────────────

def _auto_run() -> None:
    cwd=_cwd
    for marker,cmd in [(cwd/"package.json","npm start"),(cwd/"Cargo.toml","cargo run"),
                       (cwd/"go.mod","go run ."),(cwd/"Makefile","make"),
                       (cwd/"manage.py","python manage.py runserver")]:
        if marker.exists():
            console.print(f"  [{_DIM}]→[/{_DIM}] [{_A2}]{cmd}[/{_A2}]")
            _run_shell(cmd); return
    py=list(cwd.glob("*.py"))
    if py:
        f=(cwd/"main.py") if (cwd/"main.py").exists() else py[0]
        cmd=f"python {f.name}"
        console.print(f"  [{_DIM}]→[/{_DIM}] [{_A2}]{cmd}[/{_A2}]")
        _run_shell(cmd); return
    c=list(cwd.glob("*.c"))
    if c:
        cmd=f"gcc {c[0].name} -o {c[0].stem} && ./{c[0].stem}"
        console.print(f"  [{_DIM}]→[/{_DIM}] [{_A2}]{cmd}[/{_A2}]")
        _run_shell(cmd); return
    console.print(f"  [{_DIM}]cannot detect project type[/{_DIM}]")


# ── Snapshot ──────────────────────────────────────────────────────────────────

def _take_snapshot() -> dict:
    snap={}
    try:
        for p in _cwd.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                try: snap[str(p.relative_to(_cwd))]={"size":p.stat().st_size,"mtime":p.stat().st_mtime}
                except Exception: pass
    except Exception: pass
    return snap

def _print_snapshot_diff(old: dict, new: dict) -> None:
    added   = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]
    changed = [k for k in new if k in old and new[k]["mtime"]!=old[k]["mtime"]]
    if not any([added,removed,changed]):
        console.print(f"  [{_DIM}]no changes since snapshot[/{_DIM}]"); return
    out=Text()
    for f in added:   out.append(f"  + {f}\n",style=_OK)
    for f in removed: out.append(f"  - {f}\n",style=_ERR)
    for f in changed: out.append(f"  ~ {f}\n",style=_A2)
    console.print(Panel(out,border_style=_A5,title=f"[{_DIM}]snapshot diff[/{_DIM}]",padding=(0,1)))


# ── Architecture diagram ──────────────────────────────────────────────────────

def _print_arch() -> None:
    lines=[
        (_DIM, "                    foder architecture                    "),
        (_DIM, ""),
        (_A2,  "  ┌─────────────────────────────────────────────────┐    "),
        (_A2,  "  │                    USER                          │    "),
        (_A2,  "  │         (types a prompt in the terminal)         │    "),
        (_A2,  "  └───────────────────────┬─────────────────────────┘    "),
        (_DIM, "                          │                               "),
        (_DIM, "                          ▼                               "),
        (_A1,  "  ┌─────────────────────────────────────────────────┐    "),
        (_A1,  "  │               FODER CLI  (main.py)               │    "),
        (_A1,  "  │   prompt · tab complete · themes · session       │    "),
        (_A1,  "  └──────────────┬──────────────────────────────────┘    "),
        (_DIM, "                 │                                        "),
        (_DIM, "                 ▼                                        "),
        (_A2,  "  ┌─────────────────────────────────────────────────┐    "),
        (_A2,  "  │             AGENT LOOP  (agent.py)               │    "),
        (_A2,  "  │   detect tool call · execute · loop · stream     │    "),
        (_A2,  "  └────────┬──────────────────────────┬─────────────┘    "),
        (_DIM, "           │                          │                   "),
        (_DIM, "           ▼                          ▼                   "),
        (_A4,  "  ┌─────────────────┐      ┌──────────────────────┐      "),
        (_A4,  "  │  TOOL SYSTEM    │      │  OLLAMA  (local LLM)  │      "),
        (_A4,  "  │  file_read      │      │  qwen · llama · etc   │      "),
        (_A4,  "  │  file_write     │      │  runs on your machine  │      "),
        (_A4,  "  │  dir_list       │      │  no cloud · no keys   │      "),
        (_A4,  "  │  shell_exec     │      └──────────────────────┘      "),
        (_A4,  "  └────────┬────────┘                                     "),
        (_DIM, "           ▼                                              "),
        (_A2,  "  ┌─────────────────────────────────────────────────┐    "),
        (_A2,  "  │              FILE SYSTEM / SHELL                 │    "),
        (_A2,  "  └─────────────────────────────────────────────────┘    "),
        (_DIM, ""),
    ]
    console.print()
    for style,line in lines: console.print(Text(line,style=style))
    console.print()


# ── Tab completer ─────────────────────────────────────────────────────────────

class FoderCompleter(Completer):
    def get_completions(self, document, complete_event):
        text=document.text_before_cursor
        if text.startswith("/"):
            word=text.lstrip("/").lower()
            for cmd in _COMMANDS:
                if cmd.lstrip("/").startswith(word):
                    yield Completion(cmd,start_position=-len(text))
            return
        at_pos=text.rfind("@")
        if at_pos!=-1:
            partial=text[at_pos+1:]
            try:
                for p in sorted(_cwd.iterdir()):
                    if p.name.startswith(partial):
                        yield Completion(p.name,start_position=-len(partial),
                                         display=p.name+("/" if p.is_dir() else ""))
            except Exception: pass


# ── Prompt label ──────────────────────────────────────────────────────────────

def _prompt_label() -> HTML:
    try:
        rel=_cwd.relative_to(config.WORKSPACE)
        path=f"foder/{rel}" if str(rel)!="." else "foder"
    except ValueError: path=str(_cwd)
    model=config.OLLAMA_MODEL.split(":")[0]
    # Git branch
    branch=_git_branch()
    branch_part=(f'<style color="{_A3}">{branch}</style>'
                 f'<style color="{_A5}"> · </style>') if branch else ""
    # Token estimate — shown as dim prefix, not after the cursor
    msgs_len=sum(len(m.get("content","")) for m in _session_history) if "_session_history" in globals() else 0
    tok_est=msgs_len//4
    tok_part=(f'<style color="{_A5}">[</style>'
              f'<style color="{_DIM}">~{tok_est//1000:.1f}k</style>'
              f'<style color="{_A5}">] </style>') if tok_est>500 else ""
    return HTML(
        f'<style color="{_DIM}">{model}</style>'
        f'<style color="{_A5}"> ❙ </style>'
        f'{tok_part}'
        f'{branch_part}'
        f'<prompt>{path} ❯ </prompt>'
    )


# ── Response renderer ─────────────────────────────────────────────────────────

_EXT_LANG = {".py":"python",".js":"javascript",".ts":"typescript",".c":"c",
             ".cpp":"cpp",".java":"java",".go":"go",".rs":"rust",
             ".html":"html",".css":"css",".json":"json",".sh":"bash",
             ".yaml":"yaml",".yml":"yaml",".toml":"toml",".md":"markdown"}

def _render_response(token_gen) -> str:
    global _last_response
    label=Text(); label.append("  ◆ ",style=_A3); label.append("foder  ",style=_A1)
    console.print(label,end="")
    collected=[]
    try:
        for token in token_gen:
            console.print(token,end="",markup=False); collected.append(token)
        console.print()
    except KeyboardInterrupt:
        console.print(); console.print(Text("  cancelled",style=_DIM))
    full="".join(collected).strip()
    _last_response=full
    if full and any(c in full for c in ("```","**","##","\n- ","\n* ","\n1.")):
        console.print()
        console.print(Panel(Markdown(full),border_style=_A5,padding=(1,2)))
    return full


# ── Session ───────────────────────────────────────────────────────────────────

def _load_session():
    try:
        if _HISTORY_FILE.exists():
            data=json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data,list): return data[-_MAX_SAVED_MESSAGES:]
    except Exception: pass
    return []

def _save_session(history):
    try:
        _HISTORY_DIR.mkdir(parents=True,exist_ok=True)
        _HISTORY_FILE.write_text(
            json.dumps(history[-_MAX_SAVED_MESSAGES:],ensure_ascii=False),encoding="utf-8")
    except Exception: pass


# ── @file injection ───────────────────────────────────────────────────────────

def _inject_file_context(user_input: str) -> str:
    pattern=re.compile(r"@([\w./\-]+)")
    matches=pattern.findall(user_input)
    # Also inject pinned files
    all_refs=list(dict.fromkeys(_pinned_files+matches))
    if not all_refs: return user_input
    injected=[]
    for ref in all_refs:
        try:
            from foder.security import validate_path
            target=validate_path(ref)
            if not target.is_file(): continue
            raw=target.read_bytes()
            if len(raw)>32_000:
                injected.append(f"[{ref} - too large, use file_read]"); continue
            injected.append(f"--- @{ref} ---\n{raw.decode('utf-8',errors='replace')}\n--- end {ref} ---")
        except Exception: continue
    if not injected: return user_input
    clean=pattern.sub("",user_input).strip()
    return "\n\n".join(injected)+f"\n\n{clean}"


# ── Exit screen ───────────────────────────────────────────────────────────────

def _print_exit(history,start_time):
    import datetime
    elapsed=time.monotonic()-start_time
    mins,secs=int(elapsed//60),int(elapsed%60)
    duration=f"{mins}m {secs}s" if mins else f"{secs}s"
    turns=sum(1 for m in history if m["role"]=="user" and not m["content"].startswith("[tool:"))
    tok_est=sum(len(m.get("content","")) for m in history)//4
    now=datetime.datetime.now().strftime("%H:%M")
    grid=Table.grid(padding=(0,4))
    grid.add_row(Text("  ended    ",style=_DIM),Text(now,style=_A1))
    grid.add_row(Text("  duration ",style=_DIM),Text(duration,style=_A1))
    grid.add_row(Text("  messages ",style=_DIM),Text(str(turns),style=_A1))
    grid.add_row(Text("  ~tokens  ",style=_DIM),Text(f"~{tok_est:,}",style=_A1))
    grid.add_row(Text("  model    ",style=_DIM),Text(config.OLLAMA_MODEL,style=_A2))
    console.print()
    console.print(Panel(grid,border_style=_A4,padding=(0,2),
                        title=f"[{_A3}] ◆ foder [/{_A3}]",title_align="left",
                        subtitle=f"[{_DIM}]session saved · model unloaded[/{_DIM}]",subtitle_align="right"))
    console.print()


# ── Slash commands ────────────────────────────────────────────────────────────

def _handle_slash(cmd,history):
    global _pinned_files
    parts=cmd.strip().split(None,1); verb=parts[0].lower(); arg=parts[1] if len(parts)>1 else ""

    if verb in ("/exit","/quit"):
        _save_session(history); unload_model(); _print_exit(history,_session_start); sys.exit(0)

    if verb=="/clear":
        history.clear(); _save_session([])
        sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
        _print_banner(); return True,history

    if verb=="/workspace":
        console.print(f"  [{_A2}]{config.WORKSPACE}[/{_A2}]"); return True,history

    if verb=="/last":
        if not _last_response: console.print(f"  [{_DIM}]no previous response[/{_DIM}]")
        else:
            is_md=any(c in _last_response for c in ("```","**","##","\n- ","\n* ","\n1."))
            label=Text(); label.append("  ◆ ",style=_A3); label.append("foder",style=_A1)
            if is_md: console.print(label); console.print(); console.print(Panel(Markdown(_last_response),border_style=_A5,padding=(1,2)))
            else: console.print(label,end="  "); console.print(_last_response)
        return True,history

    if verb=="/model":
        console.print(f"  [bold {_A1}]{config.OLLAMA_MODEL}[/bold {_A1}]"); return True,history

    if verb=="/models":
        try: models=list_models()
        except LLMError as e: console.print(f"  [red]{e}[/red]"); return True,history
        table=Table(show_header=False,box=box.SIMPLE,padding=(0,2))
        for name in models:
            active=name==config.OLLAMA_MODEL
            table.add_row(Text("◆" if active else " ",style=_A3 if active else _DIM),
                          Text(name,style=f"bold {_A1}" if active else _A2))
        console.print(table); return True,history

    if verb=="/switch":
        try: models=list_models()
        except LLMError as e: console.print(f"  [red]{e}[/red]"); return True,history
        if arg and arg in models: config.OLLAMA_MODEL=arg; _status(); return True,history
        console.print(f"  [{_DIM}]select a model:[/{_DIM}]\n")
        config.OLLAMA_MODEL=_pick_model(models); console.print(); _status(); return True,history

    if verb=="/theme":
        if arg and arg in THEMES: _apply_theme(arg); _save_theme(arg)
        else: key=_pick_theme(); _apply_theme(key); _save_theme(key)
        console.print(f"  [{_DIM}]theme →[/{_DIM}] [{_A2}]{THEMES[_load_theme()]['name']}[/{_A2}]")
        return True,history

    if verb=="/git":
        _print_git(); return True,history

    if verb=="/pin":
        if not arg: console.print(f"  [{_DIM}]usage: /pin <filename>[/{_DIM}]"); return True,history
        if arg not in _pinned_files: _pinned_files.append(arg)
        console.print(f"  [{_A2}]pinned[/{_A2}]  [{_DIM}]{arg}[/{_DIM}]"); return True,history

    if verb=="/unpin":
        if arg in _pinned_files: _pinned_files.remove(arg)
        console.print(f"  [{_DIM}]unpinned {arg}[/{_DIM}]"); return True,history

    if verb=="/pins":
        if not _pinned_files: console.print(f"  [{_DIM}]no pinned files[/{_DIM}]")
        else:
            for f in _pinned_files: console.print(f"  [{_A2}]◆[/{_A2}]  [{_DIM}]{f}[/{_DIM}]")
        return True,history

    if verb=="/snapshot":
        if arg=="diff":
            try:
                old=json.loads(_SNAPSHOT_FILE.read_text(encoding="utf-8"))
                _print_snapshot_diff(old,_take_snapshot())
            except Exception: console.print(f"  [{_DIM}]no snapshot found — run /snapshot first[/{_DIM}]")
        else:
            snap=_take_snapshot()
            _SNAPSHOT_FILE.parent.mkdir(parents=True,exist_ok=True)
            _SNAPSHOT_FILE.write_text(json.dumps(snap),encoding="utf-8")
            console.print(f"  [{_A2}]snapshot saved[/{_A2}]  [{_DIM}]{len(snap)} files[/{_DIM}]")
        return True,history

    if verb=="/cost":
        elapsed=time.monotonic()-_session_start
        mins,secs=int(elapsed//60),int(elapsed%60)
        turns=sum(1 for m in history if m["role"]=="user" and not m["content"].startswith("[tool:"))
        msgs_len=sum(len(m.get("content","")) for m in history)
        tok_est=msgs_len//4
        grid=Table.grid(padding=(0,4))
        grid.add_row(Text("  session time  ",style=_DIM),Text(f"{mins}m {secs}s",style=_A1))
        grid.add_row(Text("  messages      ",style=_DIM),Text(str(turns),style=_A1))
        grid.add_row(Text("  tool calls    ",style=_DIM),Text(str(_session_tool_calls),style=_A1))
        grid.add_row(Text("  files written ",style=_DIM),Text(str(_session_files_written),style=_A1))
        grid.add_row(Text("  ~tokens used  ",style=_DIM),Text(f"~{tok_est:,}",style=_A2))
        console.print(Panel(grid,border_style=_A5,padding=(0,2),
                            title=f"[{_DIM}]session stats[/{_DIM}]",title_align="left"))
        return True,history

    if verb=="/undo":
        if not _last_write.get("path"): console.print(f"  [{_DIM}]nothing to undo[/{_DIM}]"); return True,history
        path=_last_write["path"]; before=_undo_store.get(path,b"")
        try:
            p=Path(path)
            if before: p.write_bytes(before); console.print(f"  [{_A2}]restored[/{_A2}]  [{_DIM}]{path}[/{_DIM}]")
            else: p.unlink(missing_ok=True); console.print(f"  [{_A2}]deleted[/{_A2}]  [{_DIM}]{path}[/{_DIM}]")
            _undo_store.pop(path,None); _last_write.clear()
        except Exception as e: console.print(f"  [red]undo failed:[/red] {e}")
        return True,history

    if verb=="/diff":
        if not _last_write.get("path"): console.print(f"  [{_DIM}]no recent write[/{_DIM}]"); return True,history
        before=_last_write["before"].decode("utf-8",errors="replace").splitlines(keepends=True)
        after =_last_write["after"].decode("utf-8",errors="replace").splitlines(keepends=True)
        diff=list(difflib.unified_diff(before,after,fromfile="before",tofile="after",lineterm=""))
        if not diff: console.print(f"  [{_DIM}]no changes[/{_DIM}]"); return True,history
        out=Text()
        for line in diff[:80]:
            if   line.startswith("+") and not line.startswith("+++"): out.append(line+"\n",style=_OK)
            elif line.startswith("-") and not line.startswith("---"): out.append(line+"\n",style=_ERR)
            elif line.startswith("@@"):                                out.append(line+"\n",style=_A2)
            else:                                                      out.append(line+"\n",style=_DIM)
        console.print(Panel(out,border_style=_A5,title=f"[{_DIM}]{_last_write['path']}[/{_DIM}]",padding=(0,1)))
        return True,history

    if verb=="/run":  _auto_run(); return True,history
    if verb=="/arch": _print_arch(); return True,history

    if verb=="/help":
        console.print()
        console.print(Rule(f"[{_DIM}]  commands  [/{_DIM}]",style=_A5))
        t=Table(show_header=False,box=None,padding=(0,2))
        for c,d in _COMMANDS.items(): t.add_row(Text(c,style=f"bold {_A2}"),Text(d,style=_DIM))
        console.print(t); console.print()
        console.print(Rule(f"[{_DIM}]  shortcuts  [/{_DIM}]",style=_A5))
        s=Table(show_header=False,box=None,padding=(0,2))
        s.add_row(Text("! <cmd>",    style=f"bold {_A2}"),Text("run shell command",      style=_DIM))
        s.add_row(Text("!!",         style=f"bold {_A2}"),Text("re-run last command",    style=_DIM))
        s.add_row(Text("cd <path>",  style=f"bold {_A2}"),Text("change directory",       style=_DIM))
        s.add_row(Text("@filename",  style=f"bold {_A2}"),Text("inject file into prompt",style=_DIM))
        s.add_row(Text("\\",         style=f"bold {_A2}"),Text("multi-line input",       style=_DIM))
        console.print(s); console.print()
        return True,history

    console.print(f"  [yellow]unknown:[/yellow] {verb}  [{_DIM}](try /help)[/{_DIM}]")
    return True,history


# ── Main REPL ─────────────────────────────────────────────────────────────────

def main() -> None:
    global _cwd, _session_start, _last_shell_cmd, _session_history

    # CLI arg mode
    if len(sys.argv)>1:
        prompt=" ".join(sys.argv[1:])
        config.load_project_config(); _apply_theme(_load_theme()); _select_model()
        _cwd=config.WORKSPACE; history=[]
        token_gen,_=run(prompt,history,on_tool_call=_on_tool_call)
        for token in token_gen: sys.stdout.write(token); sys.stdout.flush()
        sys.stdout.write("\n"); return

    config.load_project_config(); _select_model()
    _cwd=config.WORKSPACE; _print_banner()
    _HISTORY_DIR.mkdir(parents=True,exist_ok=True)

    session=PromptSession(
        history=FileHistory(str(_PROMPT_HISTORY)),
        style=_PROMPT_STYLE,
        completer=FoderCompleter(),
        complete_while_typing=False,
    )

    conversation_history=_load_session()
    _session_history=conversation_history   # expose for token counter in prompt
    if conversation_history:
        console.print(f"  [{_A3}]◆[/{_A3}] [{_DIM}]resumed {len(conversation_history)} messages[/{_DIM}]\n")

    _session_start=time.monotonic()

    while True:
        try:
            # Multi-line input: lines ending with \ continue
            lines=[]
            while True:
                prompt_fn=_prompt_label if not lines else lambda: HTML(f'<style color="{_A5}">  ... </style>')
                part=session.prompt(prompt_fn,style=_PROMPT_STYLE)
                if part.endswith("\\"):
                    lines.append(part[:-1])
                else:
                    lines.append(part); break
            user_input=" ".join(lines).strip()
        except (EOFError,KeyboardInterrupt):
            _save_session(conversation_history)
            _print_exit(conversation_history,_session_start); break

        if not user_input: continue

        # Auto-detect unambiguous shell commands — no need for ! prefix
        # Only commands that would NEVER start a natural language sentence
        shell_cmds = ("cd","ls","ll","pwd","cat","nano","vim","vi","less","more",
                      "head","tail","grep","find","git","gcc","g++","clang","node","npm","cargo","go")
        first_word = user_input.split()[0] if user_input.split() else ""
        if first_word in shell_cmds:
            _last_shell_cmd = user_input
            console.print(); _run_shell(user_input); console.print(); continue

        # !! re-run
        if user_input=="!!":
            if not _last_shell_cmd: console.print(f"  [{_DIM}]no previous command[/{_DIM}]\n")
            else: console.print(); _run_shell(_last_shell_cmd); console.print()
            continue

        # Shell
        if user_input.startswith("!"):
            cmd=user_input[1:].strip(); _last_shell_cmd=cmd
            console.print(); _run_shell(cmd); console.print(); continue

        # Slash
        if user_input.startswith("/"):
            console.print(); _,conversation_history=_handle_slash(user_input,conversation_history)
            console.print(); continue

        # @file injection
        resolved=_inject_file_context(user_input)

        # Agent turn — clean inline "you ›" prefix, no panel
        console.print()
        you = Text()
        you.append("  you", style=_DIM)
        you.append(" › ", style=_A5)
        you.append(user_input, style="white")
        console.print(you)
        console.print(Rule(style=_A5)); console.print()

        console.print(Text("  ◆ thinking...",style=_DIM),end="\r")
        try:
            token_gen,conversation_history=run(resolved,conversation_history,on_tool_call=_on_tool_call)
        except KeyboardInterrupt:
            console.print(Text("  cancelled",style=_DIM)); continue

        console.print(" "*30,end="\r")
        full=_render_response(token_gen)
        _session_history=conversation_history
        _save_session(conversation_history)

        if full.strip().startswith("[llm error]"):
            msg=full.strip()
            if "timed out" in msg:
                hint=(f"[yellow]Ollama timed out.[/yellow]\n\n"
                      f"  [{_DIM}]took longer than[/{_DIM}] [{_A2}]{config.LLM_TIMEOUT:.0f}s[/{_A2}]\n\n"
                      f"  [{_DIM}]try smaller tasks  →[/{_DIM}]  e.g. 'make index.html' then 'make style.css'\n"
                      f"  [{_DIM}]faster model       →[/{_DIM}]  /switch\n"
                      f"  [{_DIM}]raise limit        →[/{_DIM}]  FODER_LLM_TIMEOUT=900 foder")
            elif "Cannot connect" in msg:
                hint="[yellow]Cannot reach Ollama.[/yellow]\n\n  ollama serve"
            else: hint=f"[yellow]{msg}[/yellow]"
            console.print(Panel(hint,border_style="yellow",padding=(0,1)))

        console.print()
        console.print(Rule(style=_A5)); console.print()


if __name__=="__main__":
    main()
