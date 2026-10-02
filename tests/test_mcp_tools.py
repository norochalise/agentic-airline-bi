import anyio
import pytest

from agentic_bi.core.reliability import PermanentToolError, TransientToolError
from agentic_bi.mcp.tools import _classify_mcp_failure


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        anyio.ClosedResourceError(),
        ExceptionGroup("task group", [anyio.BrokenResourceError()]),
    ],
)
def test_connection_failures_are_transient(error):
    assert isinstance(_classify_mcp_failure(error), TransientToolError)


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("uv not found"),
        ExceptionGroup("task group", [FileNotFoundError("uv not found")]),
        ValueError("bad arguments"),
        RuntimeError("server bug"),
    ],
)
def test_other_failures_are_permanent(error):
    assert isinstance(_classify_mcp_failure(error), PermanentToolError)
