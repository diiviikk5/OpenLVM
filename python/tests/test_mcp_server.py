import inspect

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


def test_mcp_server_module_has_collection_and_trace_tools():
    source = inspect.getsource(mcp_server.build_mcp_server)
    assert "get_trace_summary" in source
    assert "inspect_collection" in source
