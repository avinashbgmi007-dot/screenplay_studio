"""Loop instrumentation (IMPROVEMENT_AUDIT 1.3): metrics.json recording and
the summarize() view the status strip reads."""

import json
import os
import time

import pytest

from screenplay_studio.metrics import (
    load,
    record_analysis,
    record_findings,
    record_reply,
    summarize,
)


class FakeManifest:
    def __init__(self, project_dir):
        self.project_dir = project_dir


@pytest.fixture
def m(tmp_path):
    return FakeManifest(str(tmp_path))


def test_record_analysis_and_summary(m):
    record_analysis(m, 123.4)
    record_reply(m, 3.2)
    record_reply(m, 4.6)
    record_reply(m, 1.8, quoted=True)
    s = summarize(m)
    assert s["analysis_seconds"] == 123.4
    assert s["avg_reply_seconds"] == pytest.approx(3.2)  # (3.2+4.6+1.8)/3
    assert s["discussed"] == 1
    assert s["findings_open"] is None  # no findings recorded yet


def test_findings_per_fix(m):
    record_findings(m, open_count=5, total=12)
    s = summarize(m)
    assert s["findings_open"] == 5
    assert s["findings_total"] == 12
    assert s["findings_fixed"] == 7
    assert s["findings_fixed_pct"] == 58


def test_reply_samples_capped(m):
    for i in range(50):
        record_reply(m, float(i))
    s = summarize(m)
    # only the last 40 are kept — the first 10 (0..9) are dropped
    assert len(load(m)["reply_seconds"]) == 40
    assert load(m)["reply_seconds"][0] == 10.0


def test_persists_to_project_dir(m):
    record_analysis(m, 1.0)
    path = os.path.join(m.project_dir, "metrics.json")
    assert os.path.exists(path)
    data = json.load(open(path, encoding="utf-8"))
    assert data["analysis_seconds"] == 1.0
    assert "last_analysis_ts" in data


def test_summarize_empty(m):
    s = summarize(m)
    assert s["avg_reply_seconds"] is None
    assert s["discussed"] == 0
