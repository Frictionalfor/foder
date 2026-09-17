import subprocess
import foder.config as config
from foder.security import validate_command, SecurityError

SCHEMA = {
    "name": "shell_exec",
    "description": (
        "Execute a shell command scoped to the workspace directory. "
        "Use for running tests, builds, linters, or inspecting output. "
        "Destructive or system-level commands are blocked."
    ),
    "parameters": {
        "command": {
            "type": "string",
            "description": "The shell command to execute.",
        }
    },
    "required": ["command"],
}


def execute(command: str) -> str:
    try:
        validate_command(command)
    except SecurityError as e:
        return f"[security error] {e}"

    try:
        ws = config.WORKSPACE.resolve()
        cwd = str(ws) if ws.exists() else None
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=config.SHELL_TIMEOUT,
        )
        parts = []
        if result.stdout:
            parts.append(result.stdout.rstrip())
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr.rstrip()}")
        if result.returncode != 0:
            parts.append(f"[exit code {result.returncode}]")
        output = "\n".join(parts).strip()
        return output or "[ok] Command executed with no output"
    except subprocess.TimeoutExpired:
        return f"[error] Command timed out after {config.SHELL_TIMEOUT}s"
    except KeyboardInterrupt:
        return "[interrupted]"
    except Exception as e:
        return f"[error] Execution failed: {e}"
