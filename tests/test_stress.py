"""Stress E2E tests: full pipeline at scale, with timing."""
import time

from screenplay_studio.manifest import ProjectManifest
from screenplay_studio.orchestrator import Orchestrator


def _generate_fountain(path, num_scenes, num_characters=10):
    characters = [f"CHAR{i}" for i in range(num_characters)]
    locations = ["OFFICE", "STREET", "APARTMENT", "CAR", "DINER", "PARK", "STATION", "ROOFTOP"]
    lines = ["Title: Stress E2E Test", ""]
    for i in range(1, num_scenes + 1):
        loc = locations[i % len(locations)]
        speaker = characters[i % len(characters)]
        other = characters[(i + 1) % len(characters)]
        lines.append(
            f"INT. {loc} {i} - DAY\n\n{speaker} enters.\n\n{speaker}\n"
            f"This is scene {i}.\n\n{other}\nUnderstood.\n"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class TestFullPipelineAtScale:
    def test_50_scene_script_full_pipeline_with_timing(self, tmp_path, mock_server):
        source = tmp_path / "big.fountain"
        _generate_fountain(str(source), 50, num_characters=8)

        manifest = ProjectManifest.create(str(tmp_path / "big_proj"), str(source))
        manifest.server_url = mock_server
        manifest.save()

        orch = Orchestrator(manifest)

        start = time.time()
        orch.run_parse()
        parse_elapsed = time.time() - start
        assert manifest.stage("parse").status == "complete"
        assert parse_elapsed < 5.0

        start = time.time()
        orch.run_analyze()
        analyze_elapsed = time.time() - start
        assert manifest.stage("analyze").status == "complete"
        assert analyze_elapsed < 60.0, f"analyze on 50 scenes took {analyze_elapsed:.2f}s"

        start = time.time()
        session, engine, store = orch.start_chat()
        for i in range(10):
            engine.send_message(session, f"Question {i} about the script")
        chat_elapsed = time.time() - start
        assert chat_elapsed < 30.0
        assert len(session.branch.messages) == 20


class TestManyForksAcrossOrchestratedSession:
    def test_orchestrated_session_supports_forking_normally(self, tmp_path, sample_fountain, mock_server):
        """Confirms Piece 3's forking still works when reached through the
        orchestrator, not just when Piece 3 is used directly."""
        manifest = ProjectManifest.create(str(tmp_path / "fork_proj"), sample_fountain)
        manifest.server_url = mock_server
        manifest.save()

        orch = Orchestrator(manifest)
        orch.run_parse()
        orch.run_analyze()
        session, engine, store = orch.start_chat()

        engine.send_message(session, "Setup message")
        for i in range(10):
            session.switch("main")
            session.fork(f"branch_{i}")
            engine.send_message(session, f"Branch {i} message")
        store.save(session)

        assert len(session.branches) == 11  # main + 10 forks
        session.switch("main")
        assert len(session.branch.messages) == 2  # only setup, untouched by forks
