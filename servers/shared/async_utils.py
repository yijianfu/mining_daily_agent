"""Async utility to safely call async functions from sync or async contexts.

MCP tools are called as sync functions (FastMCP wraps them), but internally
they need to run async HTTP/IO. This helper detects the current event loop
state and calls the coroutine accordingly.
"""

import asyncio
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine, handling both sync and async calling contexts.

    When called from a sync context (no running event loop), uses
    `asyncio.run()`. When called from within an existing event loop
    (e.g., the agent's LangGraph async execution), runs the coroutine
    on that loop in a thread-safe manner.

    Args:
        coro: The coroutine to execute.

    Returns:
        The coroutine's return value.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop — safe to use asyncio.run()
        return asyncio.run(coro)
    else:
        # Running inside an event loop — use run_coroutine_threadsafe
        # or create a new event loop in a thread
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
