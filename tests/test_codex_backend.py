import pytest

from pds_research.codex_backend import CodexCliBackend


def test_codex_backend_enforces_tiny_smoke_limit() -> None:
    with pytest.raises(ValueError, match="hard-capped"):
        CodexCliBackend(model="test", max_requests=4)
