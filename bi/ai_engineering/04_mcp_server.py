"""Exercise 4 - an MCP server: give an AI client safe, typed tools over your data.

MCP (Model Context Protocol) is the open standard for exposing tools/data to AI apps (Claude Desktop, IDEs, agents).
This server offers three READ-ONLY tools over the operations data.

    pip install mcp duckdb
    python 04_mcp_server.py          # speaks MCP over stdio - normally launched BY a client

Register it in Claude Desktop's config (claude_desktop_config.json), adjusting the path:
    { "mcpServers": { "bi-ops": { "command": "python", "args": ["C:/Users/YOU/Business Intelligence DB/ai_engineering/04_mcp_server.py"] } } }

Security checklist this file practises: read-only SQL, row cap, no filesystem args, descriptions that say what the tool does NOT do.
"""
try:  # mcp >= 2 renamed FastMCP
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server

from data import SCHEMA, connect, is_select_only

mcp = Server("bi-ops")
_con = connect()
ROW_CAP = 50


@mcp.tool()
def describe_schema() -> str:
    """Return the table schema. Call this before writing SQL."""
    return SCHEMA


@mcp.tool()
def run_select(sql: str) -> str:
    """Run ONE read-only SELECT against `operations` (max 50 rows). Cannot modify data or read files."""
    if not is_select_only(sql):
        return "Rejected: only a single SELECT/WITH statement is allowed."
    try:
        cur = _con.execute(sql)
        cols = [d[0] for d in cur.description]
        data = cur.fetchmany(ROW_CAP)
    except Exception as e:
        return f"SQL error: {str(e)[:200]}"
    return "\n".join([" | ".join(cols)] + [" | ".join(str(v) for v in r) for r in data])


@mcp.tool()
def kpi_summary() -> str:
    """Revenue, profit, margin (ratio of sums) and completion rate for the whole dataset."""
    r = _con.execute("""SELECT sum(revenue), sum(revenue-operational_cost),
        sum(revenue-operational_cost)/sum(revenue), avg((status='Completed')::int) FROM operations""").fetchone()
    return f"revenue={r[0]:,.0f} profit={r[1]:,.0f} margin={r[2]:.2%} completion={r[3]:.1%}"


if __name__ == "__main__":
    mcp.run()
