"""Gate 9 — the feedback ledger: the system of record across runs.

Amendment 6 measured the fact this gate exists for. Across two real runs of the
same model on the same script, only 25 % of the writer's marks had their point
re-raised; 65 % were not re-raised at all — and no identity function fixes that,
because the judgment tier churns by nature while the deterministic tier re-raised
100 %. So "nothing lost" cannot mean every mark SURVIVES. It must mean every mark
stays ACCOUNTED FOR.

The load-bearing properties, in the order the risk matters:

1. THE PARTITION — every prior thread lands in exactly one of same / maybe /
   likely_resolved / not_re_raised, and every current thread in exactly one of
   same / maybe / new. If the buckets do not partition, "accounted for" is a
   claim, not a fact.
2. THE CONSERVATIVE WEAK MATCH — `maybe` requires the same category, and never
   promotes a weak counterpart to `same`. A dialogue note is not the same point
   as a structure note, and carrying a writer's mark onto a different point is
   worse than leaving it un-reconciled.
3. `likely_resolved` REQUIRES A MARK — a thread that vanished is only "likely
   resolved" if the writer had marked it. An unmarked vanished thread is
   `not_re_raised`, which is the honest answer and the reason a matcher can never
   satisfy "nothing lost" while a ledger can.
4. STORE DISCIPLINE — its own file, damage reads as damage, a write refuses
   rather than overwriting, and one delivery is one run however many times the
   button was pressed.
"""
import json
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from screenplay_studio import feedback_ledger as fl  # noqa: E402
from screenplay_studio.jsonio import StoreUnreadable  # noqa: E402
from screenplay_studio.manifest import ProjectManifest  # noqa: E402


def _t(tid, category="dialogue", issue="a note", scenes=(1,)):
    return {"id": tid, "category": category, "issue": issue,
            "scene_refs": list(scenes), "severity": "low", "scene_key": f"K{tid}",
            "quote": None}


def _report(*findings):
    return {"model_used": "test", "findings": list(findings)}


def _finding(issue, category="dialogue", scenes=(1,), quote=None):
    return {"category": category, "issue": issue, "severity": "low",
            "scene_refs": list(scenes), "evidence_quote": quote,
            "scene_key": f"INT ROOM {issue[:8]}"}


@pytest.fixture
def project(tmp_path, sample_fountain):
    m = ProjectManifest.create(str(tmp_path / "proj"), sample_fountain)
    m.save()
    return m


@pytest.fixture
def served(tmp_path, sample_fountain, monkeypatch):
    import screenplay_studio.webapp_server as webapp_server

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(webapp_server, "PROJECTS_DIR", str(root))
    webapp_server.app.config["TESTING"] = True
    m = ProjectManifest.create(str(root / "p1"), sample_fountain)
    m.save()
    return webapp_server.app.test_client(), m


# ---------- 1. store discipline ----------

def test_missing_ledger_reads_as_an_empty_history(project):
    assert fl.load_ledger(project) == {"runs": []}


def test_a_damaged_ledger_reads_as_damage_and_refuses_a_write(project):
    """Not as an empty history — that would read as 'no runs yet', which is the
    A3 shape (a damaged file presented as 'you have nothing here')."""
    fl.record_run(project, _report(_finding("first")))
    path = fl.ledger_path(project)
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"runs": [')
    with pytest.raises(StoreUnreadable):
        fl.load_ledger(project)
    with pytest.raises(StoreUnreadable):
        fl.record_run(project, _report(_finding("second")))
    with open(path, encoding="utf-8") as f:
        assert f.read() == '{"runs": [', "the damaged ledger was overwritten"


def test_one_delivery_is_one_run(project):
    """Recording the same delivered set twice must not log two runs — the writer
    pressing the button again did not produce a second run."""
    fl.record_run(project, _report(_finding("first")))
    fl.record_run(project, _report(_finding("first")))
    assert len(fl.load_ledger(project)["runs"]) == 1
    fl.record_run(project, _report(_finding("second")))
    runs = fl.load_ledger(project)["runs"]
    assert len(runs) == 2 and [r["run"] for r in runs] == [1, 2]


# ---------- 2. the partition ----------

def test_every_thread_lands_in_exactly_one_bucket():
    prev = [_t("a"), _t("b", issue="act two sags"),
            _t("c", category="theme"), _t("d", category="voice")]
    cur = [_t("a"), _t("e", category="genre")]
    r = fl.reconcile(prev, cur, addressed_ids=["c"])
    assert len(r["same"]) + len(r["maybe"]) + len(r["likely_resolved"]) \
        + len(r["not_re_raised"]) == len(prev)
    assert len(r["same"]) + len(r["maybe"]) + len(r["new"]) == len(cur)


# ---------- 3. the five buckets, each firing ----------

def test_same_requires_the_id_to_survive():
    prev = [_t("a", issue="the same point")]
    cur = [_t("a", issue="the same point")]
    r = fl.reconcile(prev, cur)
    assert [x["prev"]["id"] for x in r["same"]] == ["a"]
    assert not r["maybe"] and not r["new"]


def test_maybe_fires_on_a_reworded_point_in_the_same_scene():
    prev = [_t("a", category="structure", issue="act two sags in the middle", scenes=(5,))]
    cur = [_t("b", category="structure", issue="act two sags badly in the middle", scenes=(5,))]
    r = fl.reconcile(prev, cur)
    assert len(r["maybe"]) == 1
    assert r["maybe"][0]["prev"]["id"] == "a" and r["maybe"][0]["cur"]["id"] == "b"
    assert r["maybe"][0]["similarity"] >= fl.MAYBE_SIMILARITY
    assert not r["new"], "a weak match must claim the current thread"


def test_maybe_is_refused_across_categories():
    """The conservative near-miss: identical text, different shelf — NOT a weak
    counterpart. Carrying a mark onto a different kind of note is worse than
    leaving it un-reconciled."""
    prev = [_t("a", category="dialogue", issue="the same words", scenes=(5,))]
    cur = [_t("b", category="structure", issue="the same words", scenes=(5,))]
    r = fl.reconcile(prev, cur)
    assert not r["maybe"]
    assert [x["id"] for x in r["not_re_raised"]] == ["a"]
    assert [x["id"] for x in r["new"]] == ["b"]


def test_maybe_is_refused_when_the_scenes_do_not_overlap():
    prev = [_t("a", category="structure", issue="act two sags in the middle", scenes=(5,))]
    cur = [_t("b", category="structure", issue="act two sags in the middle", scenes=(9,))]
    r = fl.reconcile(prev, cur)
    assert not r["maybe"]


def test_likely_resolved_requires_a_mark():
    prev = [_t("a", issue="you fixed this"), _t("b", issue="you never marked this")]
    cur = []
    r = fl.reconcile(prev, cur, addressed_ids=["a"])
    assert [x["id"] for x in r["likely_resolved"]] == ["a"]
    assert [x["id"] for x in r["not_re_raised"]] == ["b"]


def test_dismissed_also_counts_as_a_mark():
    prev = [_t("a")]
    r = fl.reconcile(prev, [], dismissed_ids=["a"])
    assert [x["id"] for x in r["likely_resolved"]] == ["a"]


# ---------- 4. the view ----------

def test_one_run_has_nothing_to_reconcile(project):
    fl.record_run(project, _report(_finding("first")))
    v = fl.ledger_view(project)
    assert v["runs"] == 1 and v["reconcile"] is None and v["previous"] is None


def test_two_runs_reconcile_against_each_other(project):
    fl.record_run(project, _report(_finding("kept"), _finding("dropped")))
    fl.record_run(project, _report(_finding("kept"), _finding("brand new")))
    v = fl.ledger_view(project)
    assert v["runs"] == 2 and v["reconcile"] is not None
    rc = v["reconcile"]
    assert rc["counts"]["same"] == 1          # "kept" re-raised with the same id
    assert rc["counts"]["not_re_raised"] == 1  # "dropped" vanished, unmarked
    assert rc["counts"]["new"] == 1            # "brand new" has no counterpart


# ---------- 5. the route ----------

def test_the_route_serves_the_view(served):
    client, m = served
    fl.record_run(m, _report(_finding("kept")))
    fl.record_run(m, _report(_finding("kept"), _finding("new one")))
    r = client.get("/api/projects/p1/feedback/ledger")
    assert r.status_code == 200
    assert r.json["runs"] == 2 and r.json["reconcile"]["counts"]["new"] == 1


def test_a_damaged_ledger_is_409_not_an_empty_history(served):
    client, m = served
    fl.record_run(m, _report(_finding("kept")))
    with open(fl.ledger_path(m), "w", encoding="utf-8") as f:
        f.write("{{{")
    r = client.get("/api/projects/p1/feedback/ledger")
    assert r.status_code == 409, r.data
