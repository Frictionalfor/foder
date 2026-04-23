from foder.security import validate_path, SecurityError

SCHEMA = {
    "name": "dir_list",
    "description": "List files and directories at a given path inside the workspace.",
    "parameters": {
        "path": {
            "type": "string",
            "description": "Relative path to the directory. Use '.' for workspace root.",
        }
    },
    "required": ["path"],
}

# File extension → color
_EXT_COLORS = {
    ".py":   "#4ADE80",   # green
    ".js":   "#FCD34D",   # yellow
    ".ts":   "#60A5FA",   # blue
    ".jsx":  "#FCD34D",
    ".tsx":  "#60A5FA",
    ".html": "#F97316",   # orange
    ".css":  "#A78BFA",   # violet
    ".json": "#FB923C",   # amber
    ".md":   "#94A3B8",   # slate
    ".c":    "#67E8F9",   # cyan
    ".cpp":  "#67E8F9",
    ".h":    "#A5F3FC",
    ".sh":   "#86EFAC",
    ".txt":  "#D1D5DB",
    ".zip":  "#F472B6",
    ".tar":  "#F472B6",
    ".gz":   "#F472B6",
}
_DIR_COLOR  = "#60A5FA"   # blue for directories
_FILE_COLOR = "#E5E7EB"   # light grey default for files


def execute(path: str) -> str:
    try:
        target = validate_path(path)
    except SecurityError as e:
        return f"[security error] {e}"

    if not target.exists():
        return f"[error] Path not found: {path}"
    if not target.is_dir():
        return f"[error] Path is not a directory: {path}"

    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        if not entries:
            return "[empty directory]"

        lines = []
        for entry in entries:
            if entry.is_dir():
                # Directories: blue + trailing slash
                lines.append(f"[{_DIR_COLOR}]{entry.name}/[/{_DIR_COLOR}]")
            else:
                # Files: color by extension
                ext   = entry.suffix.lower()
                color = _EXT_COLORS.get(ext, _FILE_COLOR)
                lines.append(f"[{color}]{entry.name}[/{color}]")

        return "  " + "  ".join(lines)
    except Exception as e:
        return f"[error] Could not list directory: {e}"
