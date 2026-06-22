"""Foder CLI — production-grade terminal coding agent."""
import sys, time, json, subprocess, difflib, re
import foder.config as config
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import Completer, Completion
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box
from foder.agent import run, plan as agent_plan, AgentCallbacks
from foder.llm import list_models, unload_model, LLMError, get_token_stats
from foder.security import validate_command, SecurityError
from foder.commands import COMMANDS as _COMMANDS, get_model_hint

console = Console(highlight=False)

# ── Themes ─────────────────────────────────────────────────────────────────────

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

_THEME_FILE = config.THEME_FILE
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

# ── Globals ────────────────────────────────────────────────────────────────────

_HISTORY_DIR        = config.USER_DIR
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
_pinned_files: list   = []
_session_tool_calls   = 0
_session_files_written= 0
_session_history: list= []

# ── Logo ───────────────────────────────────────────────────────────────────────

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

# ── Banner ─────────────────────────────────────────────────────────────────────

def _print_banner() -> None:
    try:
        from foder.context import detect_project
        profile  = detect_project()
        ctx_line = profile.summary[:44]
    except Exception:
        ctx_line = ""

    meta = Table.grid(padding=(0,1))
    meta.add_row(Text("  workspace ", style=_DIM), Text(str(config.WORKSPACE), style=_A2))
    meta.add_row(Text("  model     ", style=_DIM), Text(config.OLLAMA_MODEL,   style=f"bold {_A1}"))
    if ctx_line:
        meta.add_row(Text("  project   ", style=_DIM), Text(ctx_line, style=_DIM))
    meta.add_row(Text("",style=""), Text("",style=""))
    meta.add_row(Text("  ! <cmd>   ", style=_DIM), Text("shell command",         style=_DIM))
    meta.add_row(Text("  @file     ", style=_DIM), Text("inject file context",   style=_DIM))
    meta.add_row(Text("  @dir/     ", style=_DIM), Text("inject directory",      style=_DIM))
    meta.add_row(Text("  /build    ", style=_DIM), Text("generate full project", style=f"bold {_A2}"))
    meta.add_row(Text("  /help     ", style=_DIM), Text("all commands",          style=_DIM))

    console.print()
    console.print(Panel(
        Columns([_logo(), meta], padding=(0, 6), equal=False),
        border_style=_A4, padding=(0, 1),
        title=f"[{_A3}] ◆ foder [/{_A3}]", title_align="left",
        subtitle=f"[{_DIM}]v0.2.0 · local AI agent · Ollama-powered · 100% offline[/{_DIM}]",
        subtitle_align="right",
    ))
    console.print()

def _status() -> None:
    console.print(f"  [{_DIM}]model[/{_DIM}]  [{_A1}]{config.OLLAMA_MODEL}[/{_A1}]  "
                  f"[{_DIM}]workspace[/{_DIM}]  [{_A2}]{config.WORKSPACE}[/{_A2}]")


# ── Model picker ───────────────────────────────────────────────────────────────

def _pick_model(models: list[str]) -> str:
    table=Table(show_header=True,header_style=_DIM,box=box.SIMPLE_HEAD,padding=(0,2))
    table.add_column("#",style=_DIM,width=4,justify="right")
    table.add_column("model",style=_A2)
    table.add_column("ram",style=_DIM,width=8)
    table.add_column("best for",style=_DIM)
    table.add_column("",style=_A3,width=2)
    for i,name in enumerate(models,1):
        hint = get_model_hint(name)
        table.add_row(str(i), name,
                      hint.get("ram",""),
                      hint.get("best_for",""),
                      "◆" if name==config.OLLAMA_MODEL else "")
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

# ── Git helpers ────────────────────────────────────────────────────────────────

def _git_branch() -> str:
    try:
        return subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                        cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=2).decode().strip()
    except Exception: return ""

def _get_git_context() -> str:
    try:
        branch=subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                         cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=3).decode().strip()
        status=subprocess.check_output(["git","status","--short"],
                                         cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=3).decode().strip()
        last  =subprocess.check_output(["git","log","--oneline","-1"],
                                         cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=3).decode().strip()
        parts=[f"git branch: {branch}"]
        if last:   parts.append(f"last commit: {last}")
        if status: parts.append(f"changed files: {len(status.splitlines())}")
        return "  ".join(parts)
    except Exception: return ""

def _print_git() -> None:
    try:
        branch=subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"],
                                         cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=3).decode().strip()
        status=subprocess.check_output(["git","status","--short"],
                                         cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=3).decode().strip()
        last  =subprocess.check_output(["git","log","--oneline","-5"],
                                         cwd=str(_cwd),stderr=subprocess.DEVNULL,timeout=3).decode().strip()
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


# ── Shell ──────────────────────────────────────────────────────────────────────

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
    if command in ("ls","ll","ls -la","ls -l","ls -a") or command.startswith("ls "):
        path="."; parts=command.split()
        for p in parts[1:]:
            if not p.startswith("-"): path=p; break
        console.print(Rule(f"[{_DIM}]$ {command}[/{_DIM}]",style=_A5,align="left"))
        _ls_colored(path)
        console.print(Rule(f"[{_DIM}]✓[/{_DIM}]",style=_A5,align="left")); return
    if command=="cd" or command.startswith(("cd ","cd\t")):
        parts=command.split(None,1)
        target=parts[1] if len(parts)>1 else str(Path.home())
        new=(_cwd/target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
        if new.is_dir():
            _cwd=new; config.WORKSPACE=new
            config.load_project_config()
            from foder.memory import refresh_workspace
            from foder.context import invalidate_cache
            refresh_workspace()
            invalidate_cache(new)
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


# ── Auto-run ───────────────────────────────────────────────────────────────────

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

# ── Snapshot ───────────────────────────────────────────────────────────────────

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


# ── Architecture diagram ───────────────────────────────────────────────────────

def _print_arch() -> None:
    lines=[
        (_DIM, "                     foder v0.2 architecture                     "),
        (_DIM, ""),
        (_A2,  "  ┌──────────────────────────────────────────────────────────┐  "),
        (_A2,  "  │                       USER INPUT                         │  "),
        (_A2,  "  └─────────────────────────────┬────────────────────────────┘  "),
        (_DIM, "                                │                               "),
        (_A1,  "  ┌──────────────────────────────────────────────────────────┐  "),
        (_A1,  "  │              FODER CLI  (main.py)                        │  "),
        (_A1,  "  │  prompt · tab-complete · themes · session · slash cmds   │  "),
        (_A1,  "  └──────┬────────────────┬────────────────┬─────────────────┘  "),
        (_DIM, "         │                │                │                    "),
        (_A2,  "  ┌──────┴──────┐  ┌─────┴──────┐  ┌─────┴──────────────────┐ "),
        (_A2,  "  │  CONTEXT    │  │  MEMORY    │  │  AGENT LOOP (agent.py) │ "),
        (_A2,  "  │  ENGINE     │  │  3 layers  │  │  plan→tool→verify→retry│ "),
        (_A2,  "  │  (context)  │  │  (memory)  │  └──────┬─────────────────┘ "),
        (_A2,  "  └──────┬──────┘  └──────┬─────┘         │                   "),
        (_DIM, "         └────────┬────────┘               │                   "),
        (_DIM, "                  │                         │                   "),
        (_A4,  "  ┌───────────────┴──────────┐   ┌─────────┴──────────────────┐"),
        (_A4,  "  │  PROMPT BUILDER          │   │  TOOL REGISTRY             │"),
        (_A4,  "  │  system prompt + context │   │  file · dir · git · grep   │"),
        (_A4,  "  │  memory injection        │   │  shell · edit · rename     │"),
        (_A4,  "  └──────────────────────────┘   └─────────┬──────────────────┘"),
        (_DIM, "                                            │                   "),
        (_A3,  "  ┌────────────────────────────────────────┴──────────────────┐"),
        (_A3,  "  │               OLLAMA  (local LLM, no cloud)               │"),
        (_A3,  "  │  qwen2.5-coder · deepseek-coder · codellama · mistral     │"),
        (_A3,  "  └────────────────────────────────────────────────────────────┘"),
        (_DIM, ""),
        (_DIM, "  memory layers: session (RAM) · workspace (.foder/) · user (~/.foder/)"),
        (_DIM, "  security: workspace jail · command blocklist · audit log"),
    ]
    console.print()
    for style,line in lines: console.print(Text(line,style=style))
    console.print()


# ── Tool display (AgentCallbacks) ──────────────────────────────────────────────

_TOOL_LABEL={
    "file_read":"read","file_write":"write","file_edit":"edit",
    "file_delete":"delete","file_rename":"rename",
    "dir_list":"list","dir_create":"mkdir","dir_remove":"rmdir",
    "shell_exec":"exec","grep_search":"grep","git_tool":"git",
}


# ── Agent state machine + OpenCode-style UI ────────────────────────────────────
#
# States mirror OpenCode's visual feedback:
#   IDLE -> PLANNING -> EXECUTING -> VERIFYING -> COMPLETED / FAILED
#
# Each tool call gets a structured log line with:
#   - state icon  (spinner / tick / cross)
#   - tool label  (write / exec / read / git / grep ...)
#   - target hint (filename / command / pattern)
#   - result badge ([ok] / [error] / [skipped])
#
# The final response is streamed token-by-token with live Markdown rendering.
# ──────────────────────────────────────────────────────────────────────────────

# Agent states
_STATE_IDLE      = "IDLE"
_STATE_PLANNING  = "PLANNING"
_STATE_EXECUTING = "EXECUTING"
_STATE_VERIFYING = "VERIFYING"
_STATE_COMPLETED = "COMPLETED"
_STATE_FAILED    = "FAILED"

# Per-tool display config: (label, icon, color_attr)
_TOOL_UI: dict[str, tuple[str, str, str]] = {
    "file_read":    ("read",    "◎", "_A2"),
    "file_write":   ("write",   "◆", "_A2"),
    "file_edit":    ("edit",    "◈", "_A2"),
    "file_delete":  ("delete",  "✕", "_ERR"),
    "file_rename":  ("rename",  "↪", "_A1"),
    "dir_list":     ("list",    "≡", "_DIM"),
    "dir_create":   ("mkdir",   "+", "_A2"),
    "dir_remove":   ("rmdir",   "-", "_DIM"),
    "shell_exec":   ("exec",    "$", "_YLW"),
    "grep_search":  ("grep",    "?", "_A3"),
    "git_tool":     ("git",     "⎇", "_A3"),
}

_YLW = "#F59E0B"   # amber — used for shell/exec

class REPLCallbacks(AgentCallbacks):
    """
    OpenCode-style agent UI callbacks.

    Renders a structured execution trace as the agent works:
      ┌ PLANNING ──────────────────────────────────────────┐
      │  ◆ write   src/app.py                              │
      │  $ exec    pip install -r requirements.txt   [ok]  │
      │  ◎ read    README.md                               │
      └────────────────────────────────────────────────────┘

    State transitions are shown inline with color-coded badges.
    """

    def __init__(self) -> None:
        self._state       = _STATE_PLANNING
        self._tool_count  = 0
        self._start_time  = time.monotonic()
        self._shown_header= False

    def _ensure_header(self) -> None:
        if self._shown_header:
            return
        self._shown_header = True
        console.print()
        console.print(
            f"  [{_A4}]┌ PLANNING {'─' * 46}┐[/{_A4}]"
        )

    def _state_badge(self) -> str:
        if self._state == _STATE_PLANNING:
            return f"[{_A3}]planning[/{_A3}]"
        if self._state == _STATE_EXECUTING:
            return f"[{_A2}]executing[/{_A2}]"
        if self._state == _STATE_VERIFYING:
            return f"[{_A1}]verifying[/{_A1}]"
        return ""

    def on_tool_call(self, tool_name: str, parameters: dict) -> None:
        global _session_tool_calls, _session_files_written
        _session_tool_calls += 1
        self._tool_count   += 1
        self._state         = _STATE_EXECUTING

        self._ensure_header()

        label, icon, color_key = _TOOL_UI.get(tool_name, (tool_name, "▸", "_A2"))
        color = globals().get(color_key, _A2)

        # Build hint string
        hint = ""
        if "path" in parameters:
            hint = str(parameters["path"])
            if tool_name == "file_write":
                _session_files_written += 1
                try:
                    from foder.security import validate_path
                    target = validate_path(parameters["path"])
                    before = target.read_bytes() if target.exists() else b""
                    _undo_store[str(target)] = before
                    _last_write.update({
                        "path":   str(target),
                        "before": before,
                        "after":  parameters.get("content", "").encode(),
                    })
                except Exception:
                    pass
        elif "command" in parameters:
            cmd = str(parameters["command"])
            hint = cmd[:55] + ("..." if len(cmd) > 55 else "")
        elif "operation" in parameters:
            hint = f"{parameters.get('operation','')} {parameters.get('path','')}".strip()
        elif "pattern" in parameters:
            hint = f"'{parameters['pattern']}'"
        elif "source" in parameters:
            src  = parameters.get("source", "")
            dest = parameters.get("destination", "")
            hint = f"{src} -> {dest}"

        # Truncate hint to keep the line clean
        if len(hint) > 52:
            hint = hint[:49] + "..."

        t = Text()
        t.append(f"  {icon} ", style=f"bold {color}")
        t.append(f"{label:<6}", style=f"bold {_A1}")
        t.append(f"  {hint}", style=_DIM)
        console.print(t)

    def on_tool_result(self, tool_name: str, result: str, is_error: bool) -> None:
        if is_error:
            short = result.split("\n")[0][:70]
            console.print(f"  [{_ERR}]    ✗ {short}[/{_ERR}]")
        else:
            # Show a compact success summary for important tools
            if tool_name == "file_write":
                console.print(f"  [{_OK}]    [ok] written[/{_OK}]")
            elif tool_name == "shell_exec":
                # Show first line of output if short
                first = result.split("\n")[0][:60].strip()
                if first and not first.startswith("[ok]"):
                    console.print(f"  [{_DIM}]    > {first}[/{_DIM}]")
                console.print(f"  [{_OK}]    [ok][/{_OK}]")

    def on_retry(self, attempt: int, reason: str) -> None:
        self._state = _STATE_VERIFYING
        if attempt >= 0:
            console.print(f"  [{_YLW}]  ~ retry {attempt} — self-correcting[/{_YLW}]")
        else:
            console.print(f"  [{_DIM}]  ~ loop detected — breaking out[/{_DIM}]")

    def close_trace(self, status: str = _STATE_COMPLETED) -> None:
        """Print the closing line of the execution trace box."""
        if not self._shown_header:
            return
        elapsed = time.monotonic() - self._start_time
        tools   = self._tool_count
        if status == _STATE_COMPLETED:
            badge = f"[{_OK}]DONE[/{_OK}]"
        elif status == _STATE_FAILED:
            badge = f"[{_ERR}]FAILED[/{_ERR}]"
        else:
            badge = f"[{_DIM}]{status}[/{_DIM}]"
        console.print(
            f"  [{_A4}]└{'─' * 54}┘[/{_A4}]  "
            f"[{_DIM}]{tools} tool(s) · {elapsed:.1f}s[/{_DIM}]  {badge}"
        )
        console.print()



# ── Tab completer ──────────────────────────────────────────────────────────────

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


# ── Prompt label ───────────────────────────────────────────────────────────────

def _prompt_label() -> HTML:
    try:
        rel=_cwd.relative_to(config.WORKSPACE)
        path=f"foder/{rel}" if str(rel)!="." else "foder"
    except ValueError: path=str(_cwd)
    model=config.OLLAMA_MODEL.split(":")[0]
    branch=_git_branch()
    branch_part=(f'<style color="{_A3}">{branch}</style>'
                 f'<style color="{_A5}"> · </style>') if branch else ""

    # Use real token counts from Ollama when available, fall back to char estimate
    stats = get_token_stats()
    total_tokens = stats["session_total"]
    if total_tokens == 0:
        # Char-based fallback: ~4 chars per token
        msgs_len = sum(len(m.get("content","")) for m in _session_history)
        total_tokens = msgs_len // 4

    # Show token count once it exceeds 200 (always visible after first real turn)
    if total_tokens > 200:
        if total_tokens >= 1000:
            tok_label = f"~{total_tokens/1000:.1f}k"
        else:
            tok_label = f"~{total_tokens}"
        tok_part = (f'<style color="{_A5}">[</style>'
                    f'<style color="{_DIM}">{tok_label}</style>'
                    f'<style color="{_A5}">] </style>')
    else:
        tok_part = ""

    return HTML(
        f'<style color="{_DIM}">{model}</style>'
        f'<style color="{_A5}"> ❙ </style>'
        f'{tok_part}'
        f'{branch_part}'
        f'<prompt>{path} ❯ </prompt>'
    )


# ── Response renderer ──────────────────────────────────────────────────────────

def _render_response(token_gen, cbs: "REPLCallbacks | None" = None) -> str:
    """
    Stream response tokens live, then render Markdown panel if applicable.
    Closes the execution trace box before printing the answer.
    """
    global _last_response

    # Close the execution trace (the ┌...┐ box) if one was opened
    if cbs is not None:
        cbs.close_trace(_STATE_COMPLETED)

    # Stream the response
    label = Text()
    label.append("  ◆ ", style=_A3)
    label.append("foder  ", style=_A1)
    console.print(label, end="")

    collected: list[str] = []
    try:
        for token in token_gen:
            console.print(token, end="", markup=False)
            collected.append(token)
        console.print()
    except KeyboardInterrupt:
        console.print()
        console.print(Text("  cancelled", style=_DIM))

    full = "".join(collected).strip()
    _last_response = full

    # Render Markdown panel for structured responses
    if full and any(c in full for c in ("```", "**", "##", "\n- ", "\n* ", "\n1.")):
        console.print()
        console.print(Panel(Markdown(full), border_style=_A5, padding=(1, 2)))

    return full


# ── Session ────────────────────────────────────────────────────────────────────

def _load_session() -> list:
    try:
        if _HISTORY_FILE.exists():
            data=json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data,list): return data[-_MAX_SAVED_MESSAGES:]
    except Exception: pass
    return []

def _save_session(history: list) -> None:
    try:
        _HISTORY_DIR.mkdir(parents=True,exist_ok=True)
        _HISTORY_FILE.write_text(
            json.dumps(history[-_MAX_SAVED_MESSAGES:],ensure_ascii=False),encoding="utf-8")
    except Exception: pass


# ── @file / @dir context injection ────────────────────────────────────────────

def _inject_file_context(user_input: str) -> str:
    pattern = re.compile(r"@([\w./\-]+)")
    matches = pattern.findall(user_input)
    all_refs = list(dict.fromkeys(_pinned_files + matches))
    if not all_refs:
        return user_input

    injected: list[str] = []
    total_chars = 0
    MAX_TOTAL = 60_000  # ~15k tokens — stay within context budget

    for ref in all_refs:
        try:
            from foder.security import validate_path
            target = validate_path(ref)

            # @dir/ — inject top relevant files from that directory
            if target.is_dir():
                from foder.context import list_workspace_files
                dir_files = list_workspace_files(target, max_files=20)
                dir_injected: list[str] = []
                for fp in dir_files:
                    if total_chars >= MAX_TOTAL:
                        break
                    try:
                        rel  = str(fp.relative_to(config.WORKSPACE))
                        raw  = fp.read_bytes()
                        if len(raw) > 32_000:
                            dir_injected.append(f"[{rel} - too large, use /index to see it]")
                            continue
                        text = raw.decode("utf-8", errors="replace")
                        entry = f"--- @{rel} ---\n{text}\n--- end {rel} ---"
                        dir_injected.append(entry)
                        total_chars += len(entry)
                    except Exception:
                        continue
                if dir_injected:
                    header = f"--- directory: {ref} ({len(dir_injected)} files) ---"
                    injected.append(header + "\n" + "\n\n".join(dir_injected))
                continue

            # @file — single file
            if not target.is_file():
                continue
            raw = target.read_bytes()
            if total_chars + len(raw) > MAX_TOTAL:
                injected.append(f"[{ref} - skipped (context limit reached)]")
                continue
            if len(raw) > 32_000:
                injected.append(f"[{ref} - too large, use file_read]")
                continue
            text  = raw.decode("utf-8", errors="replace")
            entry = f"--- @{ref} ---\n{text}\n--- end {ref} ---"
            injected.append(entry)
            total_chars += len(entry)
        except Exception:
            continue

    if not injected:
        return user_input

    clean = pattern.sub("", user_input).strip()
    return "\n\n".join(injected) + f"\n\n{clean}"


# ── Exit screen ────────────────────────────────────────────────────────────────

def _print_exit(history: list, start_time: float) -> None:
    import datetime
    elapsed=time.monotonic()-start_time
    mins,secs=int(elapsed//60),int(elapsed%60)
    duration=f"{mins}m {secs}s" if mins else f"{secs}s"
    turns=sum(1 for m in history if m["role"]=="user" and not m["content"].startswith("[tool:"))
    # Real token counts from Ollama
    stats = get_token_stats()
    total_tokens = stats["session_total"]
    if total_tokens == 0:
        total_tokens = sum(len(m.get("content","")) for m in history) // 4
    now=datetime.datetime.now().strftime("%H:%M")
    grid=Table.grid(padding=(0,4))
    grid.add_row(Text("  ended    ",style=_DIM),Text(now,style=_A1))
    grid.add_row(Text("  duration ",style=_DIM),Text(duration,style=_A1))
    grid.add_row(Text("  messages ",style=_DIM),Text(str(turns),style=_A1))
    grid.add_row(Text("  tokens   ",style=_DIM),Text(f"{total_tokens:,}",style=_A1))
    grid.add_row(Text("  tools    ",style=_DIM),Text(str(_session_tool_calls),style=_A1))
    grid.add_row(Text("  model    ",style=_DIM),Text(config.OLLAMA_MODEL,style=_A2))
    console.print()
    console.print(Panel(grid,border_style=_A4,padding=(0,2),
                    title=f"[{_A3}] ◆ foder [/{_A3}]",title_align="left",
                    subtitle=f"[{_DIM}]session saved · model unloaded[/{_DIM}]",subtitle_align="right"))
    console.print()

# ── Slash commands ─────────────────────────────────────────────────────────────

def _handle_slash(cmd: str, history: list) -> tuple[bool, list]:
    global _pinned_files
    parts=cmd.strip().split(None,1); verb=parts[0].lower(); arg=parts[1].strip() if len(parts)>1 else ""

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
        hint = get_model_hint(config.OLLAMA_MODEL)
        out = Text()
        out.append(f"  {config.OLLAMA_MODEL}", style=f"bold {_A1}")
        if hint:
            out.append(f"  {hint.get('ram','')}  {hint.get('best_for','')}", style=_DIM)
        console.print(out)
        return True,history

    if verb=="/models":
        try: models=list_models()
        except LLMError as e: console.print(f"  [red]{e}[/red]"); return True,history
        table=Table(show_header=True,header_style=_DIM,box=box.SIMPLE_HEAD,padding=(0,2))
        table.add_column("model",style=_A2)
        table.add_column("ram",style=_DIM)
        table.add_column("best for",style=_DIM)
        table.add_column("",style=_A3,width=2)
        for name in models:
            hint = get_model_hint(name)
            table.add_row(name, hint.get("ram",""), hint.get("best_for",""),
                          "◆" if name==config.OLLAMA_MODEL else "")
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
            except Exception: console.print(f"  [{_DIM}]no snapshot — run /snapshot first[/{_DIM}]")
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
        # Use real token counts from Ollama (captured from streaming done chunks)
        stats = get_token_stats()
        total_tokens = stats["session_total"]
        prompt_tokens = stats["session_prompt"]
        response_tokens = stats["session_response"]
        # Fallback to char estimate if Ollama hasn't reported any tokens yet
        if total_tokens == 0:
            msgs_len = sum(len(m.get("content","")) for m in history)
            total_tokens = max(1, msgs_len // 4)
            prompt_tokens = total_tokens
            response_tokens = 0
        grid=Table.grid(padding=(0,4))
        grid.add_row(Text("  session time  ",style=_DIM),Text(f"{mins}m {secs}s",style=_A1))
        grid.add_row(Text("  messages      ",style=_DIM),Text(str(turns),style=_A1))
        grid.add_row(Text("  tool calls    ",style=_DIM),Text(str(_session_tool_calls),style=_A1))
        grid.add_row(Text("  files written ",style=_DIM),Text(str(_session_files_written),style=_A1))
        grid.add_row(Text("  prompt tokens ",style=_DIM),Text(f"{prompt_tokens:,}",style=_A2))
        grid.add_row(Text("  output tokens ",style=_DIM),Text(f"{response_tokens:,}",style=_A2))
        grid.add_row(Text("  total tokens  ",style=_DIM),Text(f"{total_tokens:,}",style=f"bold {_A1}"))
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

    # ── New commands ───────────────────────────────────────────────────────────

    if verb=="/context":
        from foder.commands import cmd_context
        console.print(Panel(cmd_context(),border_style=_A5,
                            title=f"[{_DIM}]project context[/{_DIM}]",padding=(0,1)))
        return True,history

    if verb=="/tools":
        from foder.commands import cmd_tools
        console.print(Panel(cmd_tools(),border_style=_A5,
                            title=f"[{_DIM}]tools[/{_DIM}]",padding=(0,1)))
        return True,history

    if verb=="/audit":
        from foder.commands import cmd_audit
        try: n=int(arg) if arg else 20
        except ValueError: n=20
        console.print(Panel(cmd_audit(n),border_style=_A5,
                            title=f"[{_DIM}]audit log[/{_DIM}]",padding=(0,1)))
        return True,history

    if verb=="/index":
        from foder.context import list_workspace_files
        files = list_workspace_files(max_files=50)
        lines = [f"  {str(f.relative_to(config.WORKSPACE))}" for f in files]
        console.print(Panel("\n".join(lines) or "  (empty)",
                            border_style=_A5,title=f"[{_DIM}]workspace index (top 50)[/{_DIM}]",padding=(0,1)))
        return True,history

    if verb=="/memory":
        _handle_memory(arg); return True,history

    if verb=="/prefs":
        _handle_prefs(arg); return True,history

    if verb=="/plan":
        if not arg:
            console.print(f"  [{_DIM}]usage: /plan <request>[/{_DIM}]"); return True,history
        _handle_plan(arg, history); return True,history

    if verb=="/review":
        _handle_review(arg, history); return True,history

    if verb=="/explain":
        _handle_explain(arg, history); return True,history

    if verb=="/auto":
        if not arg:
            console.print(f"  [{_DIM}]usage: /auto <task description>[/{_DIM}]"); return True,history
        _handle_auto(arg, history); return True,history

    if verb=="/skills":
        _handle_skills(arg); return True,history

    if verb=="/build":
        if not arg:
            console.print(f"  [{_DIM}]usage: /build <project description>[/{_DIM}]"); return True,history
        _handle_build(arg, history); return True,history

    if verb=="/chat":
        if not arg:
            console.print(f"  [{_DIM}]usage: /chat <question>[/{_DIM}]"); return True,history
        _handle_chat(arg, history); return True,history

    if verb=="/test":
        _handle_test(arg, history); return True,history

    if verb=="/refactor":
        if not arg:
            console.print(f"  [{_DIM}]usage: /refactor <file> [instruction][/{_DIM}]"); return True,history
        _handle_refactor(arg, history); return True,history

    if verb=="/doctor":
        _handle_doctor(); return True,history

    if verb=="/compress":
        _handle_compress(history); return True,history

    if verb=="/history":
        _handle_history(arg); return True,history

    if verb=="/watch":
        _handle_watch(arg, history); return True,history

    if verb=="/help":
        console.print()
        console.print(Rule(f"[{_DIM}]  commands  [/{_DIM}]",style=_A5))
        t=Table(show_header=False,box=None,padding=(0,2))
        for c,d in _COMMANDS.items(): t.add_row(Text(c,style=f"bold {_A2}"),Text(d,style=_DIM))
        console.print(t); console.print()
        console.print(Rule(f"[{_DIM}]  shortcuts  [/{_DIM}]",style=_A5))
        s=Table(show_header=False,box=None,padding=(0,2))
        s.add_row(Text("! <cmd>",    style=f"bold {_A2}"),Text("shell command",       style=_DIM))
        s.add_row(Text("!!",         style=f"bold {_A2}"),Text("re-run last command", style=_DIM))
        s.add_row(Text("cd <path>",  style=f"bold {_A2}"),Text("change directory",    style=_DIM))
        s.add_row(Text("@filename",  style=f"bold {_A2}"),Text("inject file context", style=_DIM))
        s.add_row(Text("\\",         style=f"bold {_A2}"),Text("multi-line input",    style=_DIM))
        console.print(s); console.print()
        return True,history

    console.print(f"  [yellow]unknown:[/yellow] {verb}  [{_DIM}](try /help)[/{_DIM}]")
    return True,history

# ── /memory handler ────────────────────────────────────────────────────────────

def _handle_memory(arg: str) -> None:
    from foder.commands import (cmd_memory_show, cmd_memory_add, cmd_memory_clear,
                                  cmd_memory_notes, cmd_memory_instructions, cmd_memory_decide)
    parts = arg.split(None, 1)
    sub   = parts[0].lower() if parts else "show"
    rest  = parts[1] if len(parts) > 1 else ""

    dispatch = {
        "show":         lambda: cmd_memory_show(),
        "add":          lambda: cmd_memory_add(rest),
        "clear":        lambda: cmd_memory_clear(),
        "notes":        lambda: cmd_memory_notes(rest),
        "instructions": lambda: cmd_memory_instructions(rest),
        "decide":       lambda: cmd_memory_decide(rest),
    }
    fn = dispatch.get(sub, lambda: cmd_memory_show())
    result = fn()
    console.print(Panel(result, border_style=_A5,
                        title=f"[{_DIM}]memory[/{_DIM}]", padding=(0,1)))


# ── /prefs handler ─────────────────────────────────────────────────────────────

def _handle_prefs(arg: str) -> None:
    from foder.commands import cmd_prefs_show, cmd_prefs_set, cmd_prefs_reset
    parts = arg.split(None, 2)
    sub   = parts[0].lower() if parts else "show"

    if sub == "show" or not sub:
        result = cmd_prefs_show()
    elif sub == "set" and len(parts) >= 3:
        result = cmd_prefs_set(parts[1], parts[2])
    elif sub == "reset":
        result = cmd_prefs_reset()
    else:
        result = "Usage: /prefs show|set <key> <value>|reset"
    console.print(Panel(result, border_style=_A5,
                        title=f"[{_DIM}]preferences[/{_DIM}]", padding=(0,1)))


# ── /plan handler ──────────────────────────────────────────────────────────────

def _handle_plan(request: str, history: list) -> None:
    console.print()
    console.print(Rule(f"[{_DIM}]  planning  [/{_DIM}]", style=_A5))
    console.print()

    cbs = REPLCallbacks()
    console.print(Text(f"  [{_DIM}]analyzing request...[/{_DIM}]"), end="\r")
    try:
        token_gen, _ = agent_plan(request, [], callbacks=cbs)
    except KeyboardInterrupt:
        console.print(Text("  cancelled", style=_DIM)); return

    console.print(" " * 30, end="\r")
    full = _render_response(token_gen)
    console.print()
    console.print(Rule(style=_A5))

    # Offer to execute
    console.print()
    console.print(f"  [{_DIM}]execute this plan?[/{_DIM}] [{_A2}]y/N[/{_A2}]", end=" ")
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    if answer in ("y", "yes"):
        console.print()
        _run_agent_turn(request, history)


# ── /review handler ────────────────────────────────────────────────────────────

def _handle_review(target: str, history: list) -> None:
    from foder.prompt import build_review_prompt
    from foder.security import validate_path, SecurityError

    files_content: dict[str, str] = {}

    if not target:
        target = "."

    try:
        p = validate_path(target)
        if p.is_file():
            files_content[target] = p.read_text(encoding="utf-8", errors="replace")
        elif p.is_dir():
            from foder.context import list_workspace_files
            for fp in list_workspace_files(p, max_files=5):
                try:
                    rel = str(fp.relative_to(config.WORKSPACE))
                    content = fp.read_text(encoding="utf-8", errors="replace")
                    if len(content) < 10000:
                        files_content[rel] = content
                except Exception:
                    pass
    except SecurityError as e:
        console.print(f"  [red]{e}[/red]"); return

    if not files_content:
        console.print(f"  [{_DIM}]no readable files found at '{target}'[/{_DIM}]"); return

    review_prompt = build_review_prompt(files_content)
    console.print()
    console.print(Rule(f"[{_DIM}]  code review: {target}  [/{_DIM}]", style=_A5))
    console.print()
    _run_agent_turn(review_prompt, history)


# ── /explain handler ───────────────────────────────────────────────────────────

def _handle_explain(arg: str, history: list) -> None:
    from foder.prompt import build_explain_prompt
    from foder.security import validate_path, SecurityError

    parts = arg.split()
    target = parts[0] if parts else ""
    mode   = parts[1].lower() if len(parts) > 1 else "normal"

    if not target:
        console.print(f"  [{_DIM}]usage: /explain <file> [beginner|advanced][/{_DIM}]"); return

    try:
        p = validate_path(target)
        if not p.is_file():
            console.print(f"  [red]not a file: {target}[/red]"); return
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 8000:
            content = content[:8000] + "\n...[truncated]"
    except SecurityError as e:
        console.print(f"  [red]{e}[/red]"); return
    except Exception as e:
        console.print(f"  [red]could not read {target}: {e}[/red]"); return

    explain_prompt = build_explain_prompt(target, content, mode)
    console.print()
    console.print(Rule(f"[{_DIM}]  explain: {target}  [/{_DIM}]", style=_A5))
    console.print()
    _run_agent_turn(explain_prompt, history)


# ── /auto handler (autonomous mode) ───────────────────────────────────────────

_AUTO_MAX_TURNS = 10

def _handle_auto(task: str, history: list) -> None:
    console.print()
    console.print(Panel(
        f"  [{_A2}]AUTONOMOUS MODE[/{_A2}]\n\n"
        f"  [{_DIM}]Task:[/{_DIM}] {task}\n\n"
        f"  [{_DIM}]Foder will execute up to {_AUTO_MAX_TURNS} turns autonomously.[/{_DIM}]\n"
        f"  [{_DIM}]Press Ctrl+C at any time to interrupt.[/{_DIM}]",
        border_style=_A4, padding=(0,1)
    ))
    console.print()

    if not _confirm("start autonomous mode?"):
        console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return

    console.print()
    cbs = REPLCallbacks()

    # Build an autonomous task prompt that asks the agent to iterate
    auto_prompt = (
        f"AUTONOMOUS TASK: {task}\n\n"
        f"Execute this task step by step. Use tools to inspect the project, "
        f"create/edit files, run commands, and verify results. "
        f"After each action, assess whether the task is complete. "
        f"When done, say TASK COMPLETE and summarize what was accomplished."
    )

    try:
        token_gen, history[:] = run(auto_prompt, history, callbacks=cbs)
        full = _render_response(token_gen)
        _save_session(history)

        if "task complete" in full.lower():
            console.print()
            console.print(Panel(f"[{_OK}]✓ Task completed autonomously[/{_OK}]",
                                border_style=_A4, padding=(0,1)))
    except KeyboardInterrupt:
        console.print()
        console.print(f"  [{_DIM}]autonomous mode interrupted[/{_DIM}]")

    console.print()
    console.print(Rule(style=_A5))


# ── Shared agent runner ────────────────────────────────────────────────────────

def _run_agent_turn(user_input: str, history: list, max_retries: int = 2) -> str:
    """
    Execute one agent turn with OpenCode-style execution trace.
    Includes Ollama crash recovery — retries up to max_retries on connection errors.
    Returns the response text.
    """
    from foder.llm import LLMError
    cbs = REPLCallbacks()

    # Show "thinking" state while waiting for first token
    console.print(Text("  ◆ thinking...", style=_DIM), end="\r")

    for attempt in range(max_retries + 1):
        try:
            token_gen, history[:] = run(user_input, history, callbacks=cbs)
            break
        except KeyboardInterrupt:
            console.print(" " * 30, end="\r")
            cbs.close_trace(_STATE_FAILED)
            console.print(Text("  cancelled", style=_DIM))
            return ""
        except Exception as e:
            err_str = str(e)
            if attempt < max_retries and ("Cannot connect" in err_str or "ConnectError" in err_str):
                console.print(f"\n  [{_YLW}]! Ollama disconnected — retrying ({attempt + 1}/{max_retries})...[/{_YLW}]")
                import time as _t; _t.sleep(2)
                cbs = REPLCallbacks()   # fresh callbacks for retry
                continue
            else:
                console.print(" " * 30, end="\r")
                cbs.close_trace(_STATE_FAILED)
                err_msg = f"[llm error] {err_str}"
                history.append({"role": "assistant", "content": err_msg})
                return err_msg

    console.print(" " * 30, end="\r")
    full = _render_response(token_gen, cbs)
    _save_session(history)
    return full

# ── /skills handler ────────────────────────────────────────────────────────────

def _handle_skills(arg: str) -> None:
    from foder.commands import cmd_skills_list, cmd_skills_show, cmd_skills_detect
    parts = arg.split(None, 1)
    sub   = parts[0].lower() if parts else "list"
    rest  = parts[1] if len(parts) > 1 else ""

    if sub == "list" or not sub:
        result = cmd_skills_list()
    elif sub in ("show", "info") and rest:
        result = cmd_skills_show(rest)
    elif sub in ("use", "load") and rest:
        # Load skill and show what will be injected
        from foder.skills import load_skill
        skill = load_skill(rest)
        if not skill:
            result = f"[error] Skill '{rest}' not found."
        else:
            result = (
                f"Skill '{skill['name']}' loaded.\n"
                f"{skill.get('description','')}\n\n"
                f"It will auto-activate when your request matches:\n"
                f"  {', '.join(skill.get('intent_keywords',[]))}\n\n"
                f"Or type your request now and it will use this skill."
            )
    elif sub == "detect" and rest:
        result = cmd_skills_detect(rest)
    else:
        result = cmd_skills_list()

    console.print(Panel(result, border_style=_A5,
                        title=f"[{_DIM}]skills[/{_DIM}]", padding=(0,1)))


# ── /build handler (Project Generation Mode) ───────────────────────────────────

def _handle_build(description: str, history: list) -> None:
    from foder.skills import build_project_prompt, detect_skill

    skill = detect_skill(description)
    skill_name = skill['name'] if skill else 'general'

    console.print()
    console.print(Panel(
        f"  [{_A2}]PROJECT GENERATION MODE[/{_A2}]\n\n"
        f"  [{_DIM}]Building:[/{_DIM}] {description}\n"
        f"  [{_DIM}]Skill:   [/{_DIM}] {skill_name}\n\n"
        f"  [{_DIM}]Foder will architect, generate, and verify a complete project.[/{_DIM}]\n"
        f"  [{_DIM}]This may take several iterations. Press Ctrl+C to interrupt.[/{_DIM}]",
        border_style=_A4, padding=(0,1)
    ))
    console.print()

    if not _confirm("start project generation?"):
        console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return

    console.print()

    # Take a snapshot before so we can show what was created
    snap_before = _take_snapshot()

    build_input = build_project_prompt(description)
    full = _run_agent_turn(build_input, history)

    # Show what was created
    snap_after = _take_snapshot()
    added = [k for k in snap_after if k not in snap_before]
    if added:
        console.print()
        out = Text()
        out.append(f"  [{_A2}]✓ Project generated — {len(added)} file(s) created[/{_A2}]\n\n")
        for f in sorted(added)[:20]:
            out.append(f"    + {f}\n", style=_OK)
        if len(added) > 20:
            out.append(f"    ... and {len(added)-20} more\n", style=_DIM)
        console.print(Panel(out, border_style=_A4, padding=(0,1),
                            title=f"[{_DIM}]generated[/{_DIM}]"))
    console.print()
    console.print(Rule(style=_A5))


# ── /chat handler (lightweight Q&A, no tools) ──────────────────────────────────

def _handle_chat(question: str, history: list) -> None:
    from foder.commands import build_chat_messages
    from foder.llm import chat_stream, LLMError

    console.print()
    console.print(Rule(f"[{_DIM}]  chat mode  [/{_DIM}]", style=_A5))
    console.print()

    try:
        messages = build_chat_messages(question, history)
        label = Text(); label.append("  ◆ ", style=_A3); label.append("foder  ", style=_A1)
        console.print(label, end="")
        collected: list[str] = []
        for token in chat_stream(messages):
            console.print(token, end="", markup=False)
            collected.append(token)
        console.print()
        full = "".join(collected).strip()
        # Add to session history as a lightweight pair
        history.append({"role": "user",      "content": f"[chat] {question}"})
        history.append({"role": "assistant",  "content": full})
        _save_session(history)
    except KeyboardInterrupt:
        console.print(Text("\n  cancelled", style=_DIM))
    except LLMError as e:
        console.print(f"\n  [{_ERR}]{e}[/{_ERR}]")
    console.print()
    console.print(Rule(style=_A5))


# ── /test handler ──────────────────────────────────────────────────────────────

def _handle_test(target: str, history: list) -> None:
    from foder.commands import cmd_test
    from foder.context import detect_project

    profile = detect_project()
    console.print()
    console.print(Rule(
        f"[{_DIM}]  test: {profile.test_framework}  [/{_DIM}]", style=_A5
    ))
    console.print()

    with console.status(f"  [{_DIM}]running tests...[/{_DIM}]", spinner="dots2", spinner_style=_A3):
        output, had_failures = cmd_test(target)

    # Display output
    output_lines = output.splitlines()
    DISPLAY_LINES = 60
    if len(output_lines) > DISPLAY_LINES:
        shown = output_lines[:DISPLAY_LINES]
        truncated = len(output_lines) - DISPLAY_LINES
    else:
        shown = output_lines
        truncated = 0

    out_text = Text()
    for line in shown:
        line_lower = line.lower()
        if any(kw in line_lower for kw in ("passed", "ok", "success", "[ok]")):
            out_text.append(line + "\n", style=_OK)
        elif any(kw in line_lower for kw in ("failed", "error", "fail", "exception")):
            out_text.append(line + "\n", style=_ERR)
        elif line.startswith("  ") or line.startswith("    "):
            out_text.append(line + "\n", style=_DIM)
        else:
            out_text.append(line + "\n", style="white")

    if truncated:
        out_text.append(f"\n  ... {truncated} more lines (run tests manually for full output)\n", style=_DIM)

    border = "red" if had_failures else _A4
    title_text = f"[{_ERR}]FAILED[/{_ERR}]" if had_failures else f"[{_OK}]PASSED[/{_OK}]"
    console.print(Panel(out_text, border_style=border, padding=(0,1),
                        title=title_text, title_align="left"))

    # If failures, ask agent to suggest fixes
    if had_failures:
        console.print()
        console.print(f"  [{_DIM}]Tests failed — asking agent for fix suggestions...[/{_DIM}]")
        console.print()
        fix_prompt = (
            f"The test suite failed. Here is the output:\n\n"
            f"```\n{output[-3000:]}\n```\n\n"
            "Analyze the failures and suggest specific fixes. "
            "If the fixes are clear, apply them using file_edit. "
            "Do not rewrite files completely — use targeted edits only."
        )
        _run_agent_turn(fix_prompt, history)

    console.print()
    console.print(Rule(style=_A5))


# ── /refactor handler ──────────────────────────────────────────────────────────

def _handle_refactor(arg: str, history: list) -> None:
    from foder.commands import build_refactor_prompt
    from foder.security import validate_path, SecurityError

    parts      = arg.split(None, 1)
    target     = parts[0] if parts else ""
    instruction= parts[1] if len(parts) > 1 else ""

    if not target:
        console.print(f"  [{_DIM}]usage: /refactor <file> [instruction][/{_DIM}]"); return

    try:
        p = validate_path(target)
        if not p.is_file():
            console.print(f"  [red]not a file: {target}[/red]"); return
        content = p.read_text(encoding="utf-8", errors="replace")
    except SecurityError as e:
        console.print(f"  [red]{e}[/red]"); return
    except Exception as e:
        console.print(f"  [red]cannot read {target}: {e}[/red]"); return

    console.print()
    console.print(Rule(f"[{_DIM}]  refactor: {target}  [/{_DIM}]", style=_A5))
    console.print()
    console.print(f"  [{_DIM}]file:[/{_DIM}]  [{_A2}]{target}[/{_A2}]  [{_DIM}]({len(content.splitlines())} lines)[/{_DIM}]")
    if instruction:
        console.print(f"  [{_DIM}]task:[/{_DIM}]  {instruction}")
    console.print()

    if not _confirm("start refactor? (edits will be shown before applying)"):
        console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return

    console.print()
    refactor_prompt = build_refactor_prompt(target, content, instruction)
    _run_agent_turn(refactor_prompt, history)
    console.print()
    console.print(Rule(style=_A5))


# ── /doctor handler ────────────────────────────────────────────────────────────

def _handle_doctor() -> None:
    from foder.commands import cmd_doctor

    console.print()
    with console.status(f"  [{_DIM}]running diagnostics...[/{_DIM}]", spinner="dots2", spinner_style=_A3):
        report = cmd_doctor()

    out = Text()
    for line in report.splitlines():
        if "[OK]" in line:
            out.append(line + "\n", style=_OK)
        elif "[FAIL]" in line:
            out.append(line + "\n", style=_ERR)
        elif "[INFO]" in line:
            out.append(line + "\n", style=_DIM)
        elif "HEALTH CHECK" in line or "checks passed" in line or "issue(s)" in line:
            out.append(line + "\n", style=f"bold {_A1}")
        else:
            out.append(line + "\n", style=_DIM)

    console.print(Panel(out, border_style=_A5, padding=(0,1),
                        title=f"[{_DIM}]doctor[/{_DIM}]", title_align="left"))
    console.print()


# ── /compress handler ──────────────────────────────────────────────────────────

def _handle_compress(history: list) -> None:
    from foder.commands import cmd_compress_prompt

    if len(history) < 4:
        console.print(f"  [{_DIM}]not enough history to compress[/{_DIM}]"); return

    console.print()
    console.print(f"  [{_DIM}]compressing {len(history)} messages...[/{_DIM}]")
    console.print()

    prompt  = cmd_compress_prompt(history)
    summary = _run_agent_turn(prompt, [])   # fresh history — don't pollute

    if summary and not summary.startswith("[llm error]"):
        # Replace history with a single compressed context message
        history.clear()
        history.append({
            "role":    "user",
            "content": f"[COMPRESSED CONTEXT]\n{summary}",
        })
        history.append({
            "role":    "assistant",
            "content": "Context compressed and loaded. Ready to continue.",
        })
        _save_session(history)
        console.print(f"  [{_A2}]✓[/{_A2}]  [{_DIM}]history compressed to summary[/{_DIM}]")
    console.print()


# ── /history handler ───────────────────────────────────────────────────────────

def _handle_history(arg: str) -> None:
    from foder.commands import cmd_history_search
    result = cmd_history_search(query=arg.strip(), limit=40)
    console.print(Panel(result, border_style=_A5,
                        title=f"[{_DIM}]history[/{_DIM}]", padding=(0,1)))
    console.print()


# ── /watch handler (file watcher) ─────────────────────────────────────────────

def _handle_watch(pattern: str, history: list) -> None:
    """
    Watch workspace for file changes and trigger the agent on save.
    Uses polling (stdlib only, no watchdog dependency).
    Debounced: 1.5s quiet period after last change before triggering.
    """
    import time as _time
    from foder.commands import build_watch_trigger_prompt

    watch_pattern = pattern.strip() or "**/*"
    ws = config.WORKSPACE

    console.print()
    console.print(Panel(
        f"  [{_A2}]WATCH MODE[/{_A2}]\n\n"
        f"  [{_DIM}]Pattern:[/{_DIM}]  {watch_pattern}\n"
        f"  [{_DIM}]Workspace:[/{_DIM}] {ws}\n\n"
        f"  [{_DIM}]Foder will trigger on file saves (1.5s debounce).[/{_DIM}]\n"
        f"  [{_DIM}]Press Ctrl+C to stop watching.[/{_DIM}]",
        border_style=_A4, padding=(0,1)
    ))
    console.print()

    if not _confirm("start watch mode?"):
        console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return

    # Build initial snapshot of file mtimes
    def _snapshot() -> dict[str, float]:
        snap: dict[str, float] = {}
        try:
            for p in ws.rglob("*"):
                if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts:
                    try:
                        snap[str(p)] = p.stat().st_mtime
                    except Exception:
                        pass
        except Exception:
            pass
        return snap

    mtimes    = _snapshot()
    pending: dict[str, tuple[str, float]] = {}   # path -> (event, trigger_time)
    DEBOUNCE  = 1.5  # seconds

    console.print(f"  [{_A2}]Watching...[/{_A2}]  [{_DIM}]Ctrl+C to stop[/{_DIM}]\n")

    try:
        while True:
            _time.sleep(0.4)
            now = _time.monotonic()

            # Detect changes
            current = _snapshot()
            for path, mtime in current.items():
                old = mtimes.get(path)
                if old is None:
                    pending[path] = ("created", now + DEBOUNCE)
                elif mtime != old:
                    pending[path] = ("modified", now + DEBOUNCE)
            for path in list(mtimes):
                if path not in current:
                    pending[path] = ("deleted", now + DEBOUNCE)
            mtimes = current

            # Fire debounced triggers
            for path, (event, fire_at) in list(pending.items()):
                if now >= fire_at:
                    del pending[path]
                    rel = str(Path(path).relative_to(ws)) if Path(path).is_relative_to(ws) else path
                    console.print(f"\n  [{_A3}]~ file {event}:[/{_A3}] [{_DIM}]{rel}[/{_DIM}]")
                    console.print()
                    trigger_prompt = build_watch_trigger_prompt(rel, event)
                    _run_agent_turn(trigger_prompt, history)
                    console.print()
                    console.print(Rule(style=_A5))
                    console.print(f"  [{_A2}]Watching...[/{_A2}]  [{_DIM}]Ctrl+C to stop[/{_DIM}]")

    except KeyboardInterrupt:
        console.print(f"\n\n  [{_DIM}]Watch mode stopped.[/{_DIM}]")
    console.print()


# ── foder init wizard ──────────────────────────────────────────────────────────

def _foder_init() -> None:
    """
    Interactive project setup wizard.
    Creates foder.json in the current workspace.
    """
    import json as _json
    from foder.llm import list_models, LLMError

    console.print()
    console.print(Panel(
        f"  [{_A2}]foder init[/{_A2}]\n\n"
        f"  [{_DIM}]Creates a foder.json config in the current workspace.[/{_DIM}]\n"
        f"  [{_DIM}]All settings are optional — press Enter to keep defaults.[/{_DIM}]",
        border_style=_A4, padding=(0,1)
    ))
    console.print()

    cfg: dict = {}

    # Model selection
    try:
        models = list_models()
    except LLMError:
        models = []

    if models:
        console.print(f"  [{_DIM}]Available models:[/{_DIM}]")
        for i, m in enumerate(models[:8], 1):
            marker = " *" if m == config.OLLAMA_MODEL else ""
            console.print(f"  [{_A2}]{i}[/{_A2}]  {m}{marker}")
        console.print()

    try:
        raw = input(f"  Model [{config.OLLAMA_MODEL}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print(f"  [{_DIM}]cancelled[/{_DIM}]"); return

    if raw:
        if raw.isdigit() and models and 1 <= int(raw) <= len(models):
            cfg["model"] = models[int(raw) - 1]
        else:
            cfg["model"] = raw
    else:
        cfg["model"] = config.OLLAMA_MODEL

    # Project instructions
    console.print()
    console.print(f"  [{_DIM}]Project instructions (tech stack, conventions, etc.):[/{_DIM}]")
    try:
        instructions = input("  Instructions [none]: ").strip()
    except (EOFError, KeyboardInterrupt):
        instructions = ""
    if instructions:
        cfg["instructions"] = instructions

    # Max iterations
    try:
        raw = input(f"  Max agent iterations [{config.MAX_ITERATIONS}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""
    if raw.isdigit():
        cfg["max_iterations"] = int(raw)

    # Skill preset
    from foder.skills import list_skills
    skills = list_skills()
    if skills:
        console.print()
        console.print(f"  [{_DIM}]Default skill preset (auto-detect intent):[/{_DIM}]")
        for i, s in enumerate(skills[:8], 1):
            console.print(f"  [{_A2}]{i}[/{_A2}]  {s['name']}  [{_DIM}]{s.get('description','')[:50]}[/{_DIM}]")
        try:
            raw = input("  Skill preset [none]: ").strip()
        except (EOFError, KeyboardInterrupt):
            raw = ""
        if raw.isdigit() and 1 <= int(raw) <= len(skills[:8]):
            cfg["default_skill"] = skills[int(raw) - 1]["name"]

    # Write foder.json
    out_path = config.WORKSPACE / "foder.json"
    try:
        out_path.write_text(_json.dumps(cfg, indent=2), encoding="utf-8")
        console.print()
        console.print(Panel(
            _json.dumps(cfg, indent=2),
            border_style=_A4, padding=(0,1),
            title=f"[{_DIM}]foder.json created[/{_DIM}]", title_align="left",
        ))
        console.print()
        console.print(f"  [{_A2}]✓[/{_A2}]  [{_DIM}]Saved to {out_path}[/{_DIM}]")
        # Reload config
        config.load_project_config()
    except Exception as e:
        console.print(f"  [red]Could not write foder.json: {e}[/red]")
    console.print()

def main() -> None:
    global _cwd, _session_start, _last_shell_cmd, _session_history

    # ── Lifecycle flags (must be checked before anything else) ────────────────
    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help", "help"):
        from foder.cli import show_help
        show_help()
        return

    if args and args[0] == "--update":
        from foder.cli import do_update
        do_update()
        return

    if args and args[0] == "--uninstall":
        from foder.cli import do_uninstall
        do_uninstall()
        return

    if args and args[0] == "init":
        config.load_project_config()
        _apply_theme(_load_theme())
        _foder_init()
        return

    # --timeout <seconds>  — override LLM_TIMEOUT for this session
    if len(args) >= 2 and args[0] == "--timeout":
        try:
            config.LLM_TIMEOUT = float(args[1])
            args = args[2:]
        except ValueError:
            console.print(f"  [red]--timeout requires a number in seconds[/red]")
            return

    # ── CLI arg mode — single prompt, print output, exit ─────────────────────
    if args:
        prompt = " ".join(args)
        config.load_project_config()
        _apply_theme(_load_theme())
        _select_model()
        _cwd = config.WORKSPACE
        history: list = []
        cbs = REPLCallbacks()
        token_gen, _ = run(prompt, history, callbacks=cbs)
        for token in token_gen:
            sys.stdout.write(token); sys.stdout.flush()
        sys.stdout.write("\n")
        return

    # Interactive REPL
    config.load_project_config()
    _select_model()
    _cwd = config.WORKSPACE
    _print_banner()
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    session = PromptSession(
        history            = FileHistory(str(_PROMPT_HISTORY)),
        style              = _PROMPT_STYLE,
        completer          = FoderCompleter(),
        complete_while_typing = False,
    )

    conversation_history = _load_session()
    _session_history     = conversation_history
    if conversation_history:
        console.print(f"  [{_A3}]◆[/{_A3}] [{_DIM}]resumed {len(conversation_history)} messages[/{_DIM}]\n")

    _session_start = time.monotonic()

    while True:
        try:
            # Multi-line input: lines ending with \ continue on next line
            lines: list[str] = []
            while True:
                prompt_fn = _prompt_label if not lines else lambda: HTML(f'<style color="{_A5}">  ... </style>')
                part = session.prompt(prompt_fn, style=_PROMPT_STYLE)
                if part.endswith("\\"):
                    lines.append(part[:-1])
                else:
                    lines.append(part); break
            user_input = " ".join(lines).strip()
        except (EOFError, KeyboardInterrupt):
            _save_session(conversation_history)
            _print_exit(conversation_history, _session_start); break

        if not user_input:
            continue

        # Auto-detect unambiguous shell commands (no ! prefix needed)
        shell_cmds = ("cd","ls","ll","pwd","cat","nano","vim","vi","less","more",
                      "head","tail","grep","find","git","gcc","g++","clang","node",
                      "npm","cargo","go","python3","python","pip","rustc","make",)
        first_word = user_input.split()[0] if user_input.split() else ""
        if first_word in shell_cmds:
            _last_shell_cmd = user_input
            console.print(); _run_shell(user_input); console.print(); continue

        # !! re-run last shell command
        if user_input == "!!":
            if not _last_shell_cmd:
                console.print(f"  [{_DIM}]no previous command[/{_DIM}]\n")
            else:
                console.print(); _run_shell(_last_shell_cmd); console.print()
            continue

        # ! prefix = shell command
        if user_input.startswith("!"):
            cmd = user_input[1:].strip(); _last_shell_cmd = cmd
            console.print(); _run_shell(cmd); console.print(); continue

        # / prefix = slash command
        if user_input.startswith("/"):
            console.print()
            _, conversation_history = _handle_slash(user_input, conversation_history)
            console.print(); continue

        # Regular prompt — inject @file context + auto-detect skills + run agent
        resolved = _inject_file_context(user_input)

        # Auto-detect skill and inject if matched
        from foder.skills import apply_skill_auto
        resolved, matched_skill = apply_skill_auto(resolved)
        if matched_skill:
            console.print(f"  [{_A3}]◆ skill[/{_A3}] [{_DIM}]{matched_skill['name']}[/{_DIM}]")

        console.print()
        you = Text()
        you.append("  you", style=_DIM)
        you.append(" › ", style=_A5)
        you.append(user_input, style="white")
        console.print(you)
        console.print(Rule(style=_A5)); console.print()

        # Save to persistent prompt history
        from foder.commands import cmd_history_append
        cmd_history_append(user_input)

        full = _run_agent_turn(resolved, conversation_history)
        _session_history = conversation_history

        # Error hints panel
        if full.strip().startswith("[llm error]"):
            msg = full.strip()
            if "timed out" in msg:
                hint = (f"[yellow]Ollama timed out.[/yellow]\n\n"
                        f"  [{_DIM}]took longer than[/{_DIM}] [{_A2}]{config.LLM_TIMEOUT:.0f}s[/{_A2}]\n\n"
                        f"  [{_DIM}]try smaller tasks  →[/{_DIM}]  break it into steps\n"
                        f"  [{_DIM}]faster model       →[/{_DIM}]  /switch\n"
                        f"  [{_DIM}]raise limit        →[/{_DIM}]  FODER_LLM_TIMEOUT=900 foder")
            elif "Cannot connect" in msg:
                hint = "[yellow]Cannot reach Ollama.[/yellow]\n\n  ollama serve"
            else:
                hint = f"[yellow]{msg}[/yellow]"
            console.print(Panel(hint, border_style="yellow", padding=(0,1)))

        console.print()
        console.print(Rule(style=_A5)); console.print()


if __name__ == "__main__":
    main()
