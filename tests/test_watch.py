"""Tests for screenplay_studio.watch — watch-folder batch processing."""

import os

from screenplay_studio.watch import process_pending


def _write_script(watch_dir, name="batch.fountain"):
    path = os.path.join(watch_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "Title: Batch Test\nAuthor: T\n\n"
            "INT. STUDY - NIGHT\n\n"
            "MARA takes out an old REVOLVER.\n\n"
            "MARA\nI'll tell you everything when this is over.\n\n"
            "CUT TO:\n\n"
            "INT. KITCHEN - DAY\n\n"
            "Mara sits at the table.\n\n"
            "MARA\nI promise I'll explain everything.\n"
        )
    return path


class TestProcessPending:
    def test_processes_and_moves_file(self, tmp_path, mock_server):
        watch_dir = str(tmp_path / "watch")
        projects_dir = str(tmp_path / "projects")
        os.makedirs(watch_dir)
        _write_script(watch_dir)

        results = process_pending(watch_dir, projects_dir, mock_server)

        assert len(results) == 1
        assert results[0]["ok"] is True
        assert results[0]["project"]
        # source moved to done/
        assert os.path.exists(os.path.join(watch_dir, "done", "batch.fountain"))
        # project exists with a completed report
        project_dir = os.path.join(projects_dir, results[0]["project"])
        assert os.path.exists(os.path.join(project_dir, "report.findings.json"))

    def test_skips_non_screenplay_files(self, tmp_path):
        watch_dir = str(tmp_path / "watch")
        projects_dir = str(tmp_path / "projects")
        os.makedirs(watch_dir)
        open(os.path.join(watch_dir, "notes.txt.bak"), "w").write("ignore me")
        open(os.path.join(watch_dir, "README.md"), "w").write("# Not a script\n")  # .md IS supported

        results = process_pending(watch_dir, projects_dir, "http://127.0.0.1:9")
        names = [r["filename"] for r in results]
        assert "notes.txt.bak" not in names  # unsupported extension skipped

    def test_move_done_false_keeps_file(self, tmp_path, mock_server):
        watch_dir = str(tmp_path / "watch")
        projects_dir = str(tmp_path / "projects")
        os.makedirs(watch_dir)
        _write_script(watch_dir)

        results = process_pending(watch_dir, projects_dir, mock_server, move_done=False)
        assert results[0]["ok"] is True
        assert os.path.exists(os.path.join(watch_dir, "batch.fountain"))
