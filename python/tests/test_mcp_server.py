from openlvm import mcp_server


def test_build_mcp_server_requires_fastmcp_when_missing():
    original = mcp_server.FastMCP
    mcp_server.FastMCP = None
    try:
        try:
            mcp_server.build_mcp_server()
        except RuntimeError:
            return
        raise AssertionError("Expected RuntimeError when FastMCP is unavailable")
    finally:
        mcp_server.FastMCP = original
