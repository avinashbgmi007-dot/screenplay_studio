"""One-shot patch: session resume + page-diff note in webapp_server.py."""
import io

p = "screenplay_studio/webapp_server.py"
src = io.open(p, encoding="utf-8").read()

# ---- 1. resume the latest idea session instead of always creating ----------
old1 = '''    store = SessionStore(IdeaStore(_ideas_dir()).sessions_dir(idea_id))
    session = store.create(title="Idea room")
    session.server_url = CONFIG["server_url"]'''
new1 = '''    store = SessionStore(IdeaStore(_ideas_dir()).sessions_dir(idea_id))
    # RESUME, don't abandon: an idea's Sameer conversation is one continuing
    # relationship. A reload (or a return visit) picks up the most recent
    # session; only a genuinely first summon (or after Clear chat) creates.
    existing = store.list()
    if existing:
        session = store.load(existing[0]["session_id"])
    else:
        session = store.create(title="Idea room")
    session.server_url = CONFIG["server_url"]'''
assert src.count(old1) == 1, "resume anchor"
src = src.replace(old1, new1)

# ---- 2. compute the page-diff note when building the idea engine ------------
old2 = '''    premise = dict(meta.get("card") or {})
    premise["content"] = meta.get("content") or ""
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory,
                            premise=premise,
                            memory_scope=f"idea:{idea_id}", writer_library_text=None)
    return session, engine, store'''
new2 = '''    premise = dict(meta.get("card") or {})
    premise["content"] = meta.get("content") or ""
    # Deterministic page-diff: what changed on the idea page since Sameer last
    # READ it (baseline persisted on the session). Computed here so ANY model
    # -- local GGUF or demo -- demonstrably notices edits without guessing.
    premise["page_update"] = _page_update_note(session.last_seen_content, premise["content"])
    engine = CoWriterEngine(client, script_ctx, report_ctx, store=store, memory=memory,
                            premise=premise,
                            memory_scope=f"idea:{idea_id}", writer_library_text=None)
    engine._current_page_content = premise["content"]
    return session, engine, store


def _page_update_note(last_seen, current):
    """Compact deterministic line-level diff of the idea page since Sameer's
    last read. Empty string when nothing changed (or no baseline yet)."""
    if last_seen is None:
        return ""
    import difflib
    old_lines = (last_seen or "").splitlines()
    new_lines = (current or "").splitlines()
    added, removed = [], []
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            removed.extend(old_lines[i1:i2])
        if tag in ("insert", "replace"):
            added.extend(new_lines[j1:j2])

    def _fmt(lines):
        out = []
        for ln in lines:
            t = ln.strip()
            if t:
                out.append('  - "' + (t[:120] + ("..." if len(t) > 120 else "")) + '"')
        return out

    parts = []
    a, r = _fmt(added), _fmt(removed)
    if a:
        parts.append("ADDED since your last read:\\n" + "\\n".join(a))
    if r:
        parts.append("REMOVED or changed since your last read:\\n" + "\\n".join(r))
    return "\\n\\n".join(parts)'''
assert src.count(old2) == 1, "engine-build anchor"
src = src.replace(old2, new2)

# ---- 3. persist the baseline after a SUCCESSFUL turn (blocking route) -------
old3 = '''        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)
    store.save(session)
    return jsonify({
        "reply": reply,
        "branch": session.current_branch,
        "messages": [msg.to_dict() for msg in session.branch.messages],
    })'''
new3 = '''        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)
    # he READ the page this turn -- move the diff baseline (failed turns keep
    # the old baseline so the next attempt re-reports the same changes)
    session.last_seen_content = getattr(engine, "_current_page_content", None)
    store.save(session)
    return jsonify({
        "reply": reply,
        "branch": session.current_branch,
        "messages": [msg.to_dict() for msg in session.branch.messages],
    })'''
assert src.count(old3) == 1, "blocking-route anchor"
src = src.replace(old3, new3)

# ---- 4. same for the streaming route: pass a success callback ----------------
old4 = '''def _sse_chat_stream(engine, session, store, text, quote, manifest=None):'''
new4 = '''def _sse_chat_stream(engine, session, store, text, quote, manifest=None, on_success=None):'''
assert src.count(old4) == 1, "stream sig anchor"
src = src.replace(old4, new4)

old5 = '''            if manifest is not None:
                try:
                    from .metrics import record_reply
                    record_reply(manifest, time.time() - t0, quoted=bool(quote))
                except Exception:
                    pass  # metrics are best-effort -- never break a chat turn'''
if old5 not in src:
    old5 = old5.replace("-- never break", "-- never break")  # em-dash variant guard
assert src.count(old5) == 1, "metrics anchor"
new5 = '''            if on_success is not None:
                try:
                    on_success()
                except Exception:
                    pass  # bookkeeping must never break the turn
''' + old5
src = src.replace(old5, new5)

old6 = '''    return _stream_response(_sse_chat_stream(engine, session, store, text, body.get("quote"), manifest=None))'''
count6 = src.count(old6)
# project stream route may pass manifest; patch only the IDEA one (last arg shape without manifest kwarg)
old6_idea = '''    return _stream_response(_sse_chat_stream(engine, session, store, text, body.get("quote")))'''
matches = [ln for ln in src.splitlines() if "_sse_chat_stream(engine, session, store, text, body.get(\"quote\")))" in ln]
assert len(matches) == 1, f"idea stream call anchor: {len(matches)}"
idea_line = matches[0]
new_idea_line = idea_line.replace(
    '_sse_chat_stream(engine, session, store, text, body.get("quote"))',
    '_sse_chat_stream(engine, session, store, text, body.get("quote"),\n'
    '                                on_success=lambda: setattr(session, "last_seen_content",\n'
    '                                                          getattr(engine, "_current_page_content", None)))'
)
src = src.replace(idea_line, new_idea_line)

io.open(p, "w", encoding="utf-8").write(src)
print("webapp_server patched")
