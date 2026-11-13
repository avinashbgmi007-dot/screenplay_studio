"""Shared state proxy for the webapp server.

Routes import ``state`` from this module and access attributes like
``state.CONFIG``, ``state._DEMO_MODEL_ACTIVE = False``.  All reads and
writes go through to ``webapp_server`` (resolved lazily to handle the
``__main__`` case when the server is started with ``-m``).
"""

class _State:
    def __getattr__(self, name):
        import sys
        ws = sys.modules.get("screenplay_studio.webapp_server") or sys.modules.get("__main__")
        return getattr(ws, name)

    def __setattr__(self, name, value):
        import sys
        ws = sys.modules.get("screenplay_studio.webapp_server") or sys.modules.get("__main__")
        setattr(ws, name, value)

    def __dir__(self):
        import sys
        ws = sys.modules.get("screenplay_studio.webapp_server") or sys.modules.get("__main__")
        return dir(ws)


state = _State()
