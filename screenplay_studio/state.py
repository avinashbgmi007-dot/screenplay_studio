"""Shared state proxy for the webapp server.

Routes import ``state`` from this module and access attributes like
``state.CONFIG``, ``state._DEMO_MODEL_ACTIVE = False``.  All reads and
writes go through to ``webapp_server`` (resolved lazily to handle the
``__main__`` case when the server is started with ``-m``).
"""
import sys


class _State:
    def _ws(self):
        return sys.modules.get("screenplay_studio.webapp_server") or sys.modules.get("__main__")

    def __getattr__(self, name):
        return getattr(self._ws(), name)

    def __setattr__(self, name, value):
        setattr(self._ws(), name, value)


state = _State()
