"""Structured logging configuration via loguru.

All MCP servers and the agent use this module for consistent log formatting.
Logs go to stderr by default (MCP stdio uses stdout for protocol messages).
"""

import sys
import os
from typing import Optional


def setup_logging(
    name: str = "mining-agent",
    level: Optional[str] = None,
    use_stderr: bool = True,
) -> None:
    """Configure structured logging for a component.

    Args:
        name: Component name for log prefix.
        level: Log level. Defaults to LOG_LEVEL env var or "INFO".
        use_stderr: If True, log to stderr (safe for MCP stdio mode).
                    If False, log to stdout.
    """
    from loguru import logger

    # Remove default handler
    logger.remove()

    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    log_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        f"{name}:{{function}}:{{line}} | {{message}}"
    )

    sink = sys.stderr if use_stderr else sys.stdout

    logger.add(
        sink,
        format=log_format,
        level=log_level,
        colorize=sys.stderr.isatty() if use_stderr else sys.stdout.isatty(),
        backtrace=True,
        diagnose=log_level == "DEBUG",
    )
