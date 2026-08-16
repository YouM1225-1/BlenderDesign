from __future__ import annotations

from pathlib import Path

import pytest

from tests.distribution.fake_host import HostHarness, create_host


@pytest.fixture
def host(tmp_path: Path) -> HostHarness:
    return create_host(tmp_path)
