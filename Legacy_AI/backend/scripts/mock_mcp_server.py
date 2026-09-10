"""
A self-contained MOCK MCP server for testing the MCP integration end to end —
no credentials, no external network, deterministic tools.

It speaks the stdio transport, so connect to it from the API with a launcher
connection string, e.g. (Docker / installed venv):

    python -m backend.scripts.mock_mcp_server

or from a source checkout:

    uv run python -m backend.scripts.mock_mcp_server

Exposed tools:
  - echo(text)            -> returns the same text
  - add(a, b)             -> a + b
  - reverse(text)         -> text reversed
  - mock_weather(city)    -> a fake, fixed weather report for the city
  - whoami()              -> identifies this as the mock server

Run it directly to sanity-check it starts:  python -m backend.scripts.mock_mcp_server
(then Ctrl-C — it waits on stdio for an MCP client).
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Mock MCP")


@mcp.tool()
def echo(text: str) -> str:
    """Echo back the provided text unchanged."""
    return text


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@mcp.tool()
def reverse(text: str) -> str:
    """Return the input text reversed."""
    return text[::-1]


@mcp.tool()
def mock_weather(city: str) -> str:
    """Return a fake, fixed weather report for a city (for testing only)."""
    return f"Weather in {city}: 24°C, sunny with light wind. (mock data)"


@mcp.tool()
def whoami() -> str:
    """Identify this server."""
    return "I am the One-AI mock MCP server. My tools are: echo, add, reverse, mock_weather, whoami."


if __name__ == "__main__":
    mcp.run(transport="stdio")
