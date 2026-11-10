"""Make the Python gap gate run the JS regression for this UI-only change."""

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_connection_card_demo_lifetime_contract():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable; the dedicated JS suite owns this contract")
    result = subprocess.run(
        [node, "--test", "tests/js/demo_server_lifetime.test.js"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
