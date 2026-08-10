import os
import sys
import threading

import pytest
from werkzeug.serving import make_server

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MOCK_PORT = 8196


class ServerThread(threading.Thread):
    def __init__(self, app, port):
        super().__init__(daemon=True)
        self.server = make_server("127.0.0.1", port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


@pytest.fixture(scope="session")
def mock_server():
    from mock_unified_server import app
    thread = ServerThread(app, MOCK_PORT)
    thread.start()
    yield f"http://127.0.0.1:{MOCK_PORT}"
    thread.shutdown()
    thread.join(timeout=5)


@pytest.fixture
def sample_fountain(tmp_path):
    path = tmp_path / "sample.fountain"
    path.write_text(
        "Title: E2E Test Script\nAuthor: Test\n\n"
        "INT. STUDY - NIGHT\n\n"
        "MARA unlocks a drawer and takes out an old REVOLVER, setting it on the desk.\n\n"
        "MARA\nI'll tell you everything when this is over.\n\n"
        "DEREK watches her, uneasy.\n\nDEREK\nJust don't do anything stupid.\n\n"
        "CUT TO:\n\n"
        "INT. KITCHEN - DAY\n\n"
        "Mara sits at the table.\n\nMARA\nI promise I'll explain everything.\n\n"
        "CUT TO:\n\n"
        "INT. STUDY - NIGHT\n\n"
        "The REVOLVER is still there, untouched.\n\nMARA\nSome things are better left alone.\n"
    )
    return str(path)
