"""
Security layer — validates all tool inputs before execution.
All file paths must resolve inside WORKSPACE.
Shell commands are checked against a blocklist.
"""

from pathlib import Path
import foder.config as config

# Commands that are never allowed regardless of context
_BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf ~", "mkfs", "dd if=",
    ":(){ :|:& };:", "chmod -R 777 /", "chown -R",
    "shutdown", "reboot", "halt", "poweroff",
    "format", "del /f /s /q c:\\",
}

_BLOCKED_PREFIXES = (
    "sudo rm -rf",
    "sudo mkfs",
    "sudo dd",
    "sudo chmod -R 777",
)


class SecurityError(Exception):
    """Raised when a tool call violates security constraints."""


def validate_path(raw_path: str) -> Path:
    """
    Resolve path and ensure it is inside the current WORKSPACE.
    Reads config.WORKSPACE dynamically so !cd changes are respected.
    Prevents directory traversal escapes (../, /etc, etc.).
    """
    workspace = config.WORKSPACE.resolve()
    if not raw_path or not str(raw_path).strip():
        return workspace

    raw = Path(raw_path)
    if raw.is_absolute():
        target = raw.resolve()
    else:
        target = (workspace / raw).resolve()

    try:
        target.relative_to(workspace)
    except ValueError:
        raise SecurityError(
            f"Path '{raw_path}' resolves outside workspace '{workspace}'. Denied."
        )
    return target


def validate_command(command: str) -> None:
    normalized = command.strip()
    low = normalized.lower()
    for blocked in _BLOCKED_COMMANDS:
        if blocked in low:
            raise SecurityError(f"Command blocked by security policy: '{blocked}'")
    for prefix in _BLOCKED_PREFIXES:
        if low.startswith(prefix):
            raise SecurityError(f"Command blocked by security policy: '{prefix}'")
    if "rm -rf /*" in low or "rm -rf / *" in low:
        raise SecurityError("Command blocked by security policy: 'rm -rf /*'")
