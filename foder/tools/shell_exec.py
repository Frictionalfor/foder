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
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(config.WORKSPACE),
            capture_output=True,
            text=True,
            timeout=config.SHELL_TIMEOUT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        if result.returncode != 0:
            output += f"\n[exit code {result.returncode}]"
        return output.strip() or "[no output]"
    except subprocess.TimeoutExpired:
        return f"[error] Command timed out after {config.SHELL_TIMEOUT}s"
    except KeyboardInterrupt:
        return "[interrupted]"
    except Exception as e:
        return f"[error] Execution failed: {e}"
