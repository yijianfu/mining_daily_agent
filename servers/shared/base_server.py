"""Base MCP server wrapper with shared lifecycle hooks.

Provides transport auto-detection (stdio vs SSE), health-check registration,
and consistent error formatting.
"""

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from loguru import logger


class BaseMCPServer:
    """Wrapper around FastMCP with shared startup and error-handling logic.

    Usage::

        from servers.shared.base_server import BaseMCPServer

        mcp = FastMCP("my-server")
        server = BaseMCPServer(mcp, name="my-server")

        @mcp.tool()
        def my_tool(x: str) -> str: ...

        if __name__ == "__main__":
            server.run()
    """

    def __init__(
        self,
        mcp: FastMCP,
        name: str,
        description: Optional[str] = None,
    ) -> None:
        """Initialize the base server.

        Args:
            mcp: The FastMCP instance.
            name: Server name (displayed in logs and health checks).
            description: Optional server description.
        """
        self.mcp = mcp
        self.name = name
        self.description = description or name
        self._register_health()

    def _register_health(self) -> None:
        """Register a health-check resource."""

        @self.mcp.resource(f"health://{self.name}")
        def health_check() -> str:
            """Health check endpoint."""
            return f"{self.name}: OK"

        @self.mcp.resource(f"info://{self.name}")
        def server_info() -> str:
            """Server information."""
            import json
            return json.dumps({
                "name": self.name,
                "description": self.description,
                "transport": os.getenv("MCP_TRANSPORT", "stdio"),
            })

    def run(self) -> None:
        """Run the server with auto-detected transport.

        Reads `MCP_TRANSPORT` env var:
        - "sse": Start SSE server on MCP_HOST:MCP_PORT
        - "stdio" (default): Standard MCP stdio transport
        """
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

        if transport == "sse":
            host = os.getenv("MCP_HOST", "0.0.0.0")
            port = int(os.getenv("MCP_PORT", "8000"))
            logger.info(
                f"Starting {self.name} on {host}:{port} (SSE transport)"
            )
            self.mcp.run(transport="sse", host=host, port=port)
        else:
            logger.info(f"Starting {self.name} (stdio transport)")
            self.mcp.run()

    @staticmethod
    def format_error(error: Exception, error_code: str = "INTERNAL_ERROR") -> str:
        """Format an exception into a structured JSON error string.

        Args:
            error: The exception to format.
            error_code: Machine-readable error code.

        Returns:
            JSON string with error details.
        """
        import json
        return json.dumps({
            "error": True,
            "error_code": error_code,
            "message": str(error),
            "recoverable": True,
        }, ensure_ascii=False)

    @staticmethod
    def format_warning(message: str) -> str:
        """Format a warning message consistently.

        Args:
            message: The warning text.

        Returns:
            Formatted warning string.
        """
        return f"[WARNING] {message}"
