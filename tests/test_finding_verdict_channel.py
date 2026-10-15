"""The verdict channel — the writer's ground-truth judgment on a finding.

The product had no channel for whether a finding is TRUE. `finding_marks.json`
records what the writer will DO (addressed / deferred); nothing recorded truth.
Until something did, "98.58 % accurate" was unfalsifiable — there was no data
from which to compute it. This file pins the new axis end to end: one store, two
routes, and the meter that turns the writer's verdicts into a measured number.

The load-bearing properties, in the order the risk matters:

1. INDEPENDENCE — truth and intent are two files, so a torn verdict store can
   never cost the writer their intent marks, and vice versa.
2. DAMAGE DISCIPLINE — a torn store is reported and never overwritten (the same
   contract `test_store_fault_injection.py` enforces for every other store).
3. THE DENOMINATOR — unjudged findings are excluded from the accuracy rate, not
   counted as failures. This is the whole metric: a writer who judges 1 of 40
   findings must not score 2.5 %.
4. ID SURVIVAL — a verdict is keyed, never positional. It follows the finding
   when the id survives a re-analysis, and the id survives exactly when the
   finding's content does (the quoted tier survives a re-wording; the no-quote
   tier, which hashes the model's own prose, does not).
"""
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from screenplay_studio import revision  # noqa: E402
from screenplay_studio.jsonio import StoreUnreadable  # noqa: E402
from screenplay_studio.manifest import ProjectManifest  # noqa: E402


def _finding(i):
    """A no-quote finding with a scene key, so every id is distinct."""
    return {"category": "dialogue", "issue": f"issue number {i}", "severity": "low",
            "evidence_quote": None, "scene_refs": [i + 1], "scene_key": f"INT ROOM {i}"}


def _write_report(m, findings):
    with open(m.report_findings_path, "w", encoding="utf-8") as f:
        json.dump({"findings": findings}, f)


@pytest.fixture
def project(tmp_path, sample_fountain):
    m = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain)
    m.save()
    _write_report(m, [_finding(i) for i in range(4)])
    m.mark_complete("analyze")
    return m


@pytest.fixture
def served(tmp_path, sample_fountain, monkeypatch):
    """A project the Flask test client can reach, with a 3-finding report."""
    import screenplay_studio.webapp_server as webapp_server

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server.app.config["TESTING"] = True
    m = ProjectManifest.create(str(root / "p1"), sample_fountain)
    m.save()
    _write_report(m, [_finding(i) for i in range(3)])
    m.mark_complete("analyze")
    return webapp_server.app.test_client(), m


# ---------- 1. independence: two axes, two files ----------

def test_verdict_and_intent_are_independent(project):
    """Writing one judgment must leave the other's file byte-identical — the
    reason the store is separate rather than a second field on the marks."""
    marks_path = revision.finding_marks_path(project)
    verdicts_path = revision.finding_verdicts_path(project)
    revision.set_finding_verdict(project, "f_alpha", "correct")
    revision.set_finding_intent(project, "f_alpha", "deferred")
    marks = open(marks_path, "rb").read()
    verdicts = open(verdicts_path, "rb").read()

    # a verdict write changes ONLY the verdict store
    revision.set_finding_verdict(project, "f_alpha", "incorrect")
    assert open(marks_path, "rb").read() == marks, \
        "a verdict write touched the intent store"
    verdicts = open(verdicts_path, "rb").read()   # the new truth, to compare against

    # an intent write changes ONLY the marks store
    revision.set_finding_intent(project, "f_alpha", "addressed")
    assert open(verdicts_path, "rb").read() == verdicts, \
        "an intent write touched the verdict store"

    assert revision.finding_intents(project) == {"f_alpha": "addressed"}
    assert revision.finding_verdicts(project) == {"f_alpha": "incorrect"}


# ---------- 2. damage discipline ----------

def test_verdict_store_survives_damage(project):
    """A torn verdict file is reported, and the next verdict refuses to
    overwrite it — the discipline the intent store already documents."""
    revision.set_finding_verdict(project, "f_alpha", "correct")
    path = revision.finding_verdicts_path(project)
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"f_alpha": "corr')          # torn, written outside the store API

    with pytest.raises(StoreUnreadable):
        revision.finding_verdicts(project)
    with pytest.raises(StoreUnreadable):
        revision.set_finding_verdict(project, "f_beta", "incorrect")
    with open(path, encoding="utf-8") as f:
        assert f.read() == '{"f_alpha": "corr', "the damaged file was rewritten"


def test_a_wrong_shape_reads_as_damage_not_as_empty(project):
    """A dict where a dict belongs but with a non-verdict value is filtered, not
    fatal; a LIST is damage. Both halves of the store contract."""
    revision.set_finding_verdict(project, "f_alpha", "correct")
    path = revision.finding_verdicts_path(project)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"f_alpha": "correct", "f_junk": "maybe"}, f)
    assert revision.finding_verdicts(project) == {"f_alpha": "correct"}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(["not", "an", "object"], f)
    with pytest.raises(StoreUnreadable):
        revision.finding_verdicts(project)


def test_damaged_verdict_store_answers_the_writer_with_damage(served):
    """Unit honesty is not enough: the SPA must not be handed an empty object
    that reads as 'nothing judged', and the write behind it must be refused."""
    client, m = served
    ok = client.get("/api/projects/p1/findings/verdicts")
    assert ok.status_code == 200 and ok.json.get("verdicts") == {}

    path = revision.finding_verdicts_path(m)
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"f_a": "corr')

    damaged = client.get("/api/projects/p1/findings/verdicts")
    assert damaged.status_code == 503, damaged.data[:200]

    refused = client.post("/api/projects/p1/findings/verdict",
                          json={"finding_id": "f_a", "verdict": "correct"})
    assert refused.status_code == 503, refused.data[:200]
    with open(path, encoding="utf-8") as f:
        assert f.read() == '{"f_a": "corr', "the damaged file was rewritten"


# ---------- 3. the routes ----------

def test_verdict_routes_roundtrip(served):
    """POST sets, GET reads it back, POST null clears. One axis, one value."""
    client, _m = served
    resp = client.post("/api/projects/p1/findings/verdict",
                       json={"finding_id": "f_a", "verdict": "partial"})
    assert resp.status_code == 200 and resp.json["verdict"] == "partial"
    assert client.get("/api/projects/p1/findings/verdicts").json["verdicts"] == {"f_a": "partial"}

    cleared = client.post("/api/projects/p1/findings/verdict",
                          json={"finding_id": "f_a", "verdict": None})
    assert cleared.status_code == 200
    assert client.get("/api/projects/p1/findings/verdicts").json["verdicts"] == {}

    bad = client.post("/api/projects/p1/findings/verdict", json={"verdict": "correct"})
    assert bad.status_code == 400


def test_verdict_batch_is_one_call(served):
    """N verdicts in one POST, N persisted — the fix-loop cadence, not N
    round-trips. Each goes through the same per-id writer the single route uses."""
    client, m = served
    ids = [revision.compute_finding_id(f) for f in [_finding(i) for i in range(3)]]
    want = {ids[0]: "correct", ids[1]: "partial", ids[2]: "incorrect"}

    resp = client.post("/api/projects/p1/findings/verdict/batch", json={"verdicts": want})
    assert resp.status_code == 200, resp.data[:200]
    assert resp.json["ok"] is True and len(resp.json["applied"]) == 3
    with open(os.path.join(m.project_dir, "finding_verdicts.json"), encoding="utf-8") as f:
        assert json.load(f) == want

    empty = client.post("/api/projects/p1/findings/verdict/batch", json={"verdicts": {}})
    assert empty.status_code == 400


# ---------- 4. the metric's denominator ----------

def test_accuracy_meter_excludes_unjudged(project):
    """The denominator rule, which IS the metric: unjudged is not a failure.

    A rate over the JUDGED set, with coverage printed beside it. Counting
    unjudged as wrong would let a writer who judges 1 of 40 score 2.5 %, and
    would repeat the shrinking/expanding-denominator error the metric exists to
    avoid."""
    findings = [_finding(i) for i in range(4)]
    _write_report(project, findings)
    ids = [revision.compute_finding_id(f) for f in findings]
    revision.set_finding_verdict(project, ids[0], "correct")
    revision.set_finding_verdict(project, ids[1], "partial")
    revision.set_finding_verdict(project, ids[2], "incorrect")
    # ids[3] deliberately left unjudged

    acc = revision.verdict_accuracy(project)
    assert acc["total"] == 4 and acc["judged"] == 3
    assert acc["tally"] == {"correct": 1, "partial": 1, "incorrect": 1, "unjudged": 1}
    assert acc["accuracy"] == 66.7          # (1+1)/3 — NOT (1+1)/4
    assert acc["strict"] == 33.3
    assert acc["incorrect_rate"] == 33.3
    assert acc["coverage"] == 75.0          # 3 of 4 carry a verdict
    assert acc["target"] == 98.58
    # a wrong finding is the only thing that costs accuracy — a partial one does not
    assert acc["by_category"]["dialogue"]["judged"] == 3


def test_accuracy_meter_is_none_before_any_verdict(project):
    """No verdicts -> the rate is undefined, not zero. Zero would read as
    'perfectly inaccurate', which is a different and false claim."""
    acc = revision.verdict_accuracy(project)
    assert acc["total"] == 4 and acc["judged"] == 0
    assert acc["accuracy"] is None and acc["strict"] is None
    assert acc["coverage"] == 0.0


def test_accuracy_route_serves_the_meter(served):
    client, m = served
    ids = [revision.compute_finding_id(f) for f in [_finding(i) for i in range(3)]]
    client.post("/api/projects/p1/findings/verdict/batch",
                json={"verdicts": {ids[0]: "correct", ids[1]: "correct", ids[2]: "incorrect"}})
    body = client.get("/api/projects/p1/findings/accuracy").json
    assert body["total"] == 3 and body["judged"] == 3
    assert body["accuracy"] == 66.7 and body["strict"] == 66.7
    assert body["verifiability"]["verified"] == 0


# ---------- 5. id survival (gate 3), measured not assumed ----------

def test_verdict_survives_reanalysis_by_id_not_by_position(project):
    """A verdict follows its finding when the ID survives — and the id survives
    exactly when the content does.

    Two tiers, pinned: a QUOTED finding's id is anchored on the quote, so
    re-wording its `issue` leaves the verdict attached; a NO-QUOTE finding's id
    hashes the model's own prose, so re-wording moves it. This is the honest
    reading of gate 3 — the store is keyed, nothing is lost by re-ordering, and
    the churn is confined to the tier that was always documented as weak."""
    quoted = {"category": "dialogue", "issue": "the line is flat",
              "evidence_quote": "MARA\nI'll tell you everything.", "scene_refs": [1],
              "scene_key": "INT STUDY NIGHT"}
    unquoted = _finding(2)
    _write_report(project, [quoted, unquoted])
    for f in (quoted, unquoted):
        revision.set_finding_verdict(project, revision.compute_finding_id(f), "correct")

    # a re-analysis re-words the ISSUE; the quote is unchanged
    after = [dict(quoted, issue="the line reads flat and inert"),
             dict(unquoted, issue="issue number 2, reworded")]
    ids_after = {revision.compute_finding_id(f) for f in after}

    assert revision.compute_finding_id(quoted) in ids_after, \
        "a quoted finding's id must survive an issue re-wording"
    assert revision.compute_finding_id(unquoted) not in ids_after, \
        "a no-quote finding's id hashes model prose and must churn"
    # both verdicts are still stored: a moved id orphans nothing, it just stops
    # matching — the store is keyed and never rewritten by a read
    assert len(revision.finding_verdicts(project)) == 2
