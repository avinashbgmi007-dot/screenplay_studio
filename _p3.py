"""Patch part 3: persist the diff baseline after successful idea turns."""
import io

p = "screenplay_studio/webapp_server.py"
src = io.open(p, encoding="utf-8").read()

# ---- blocking idea route -----------------------------------------------------
old3 = """        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)
    store.save(session)
    return jsonify({
        "reply": reply,
        "branch": session.current_branch,
        "messages": [msg.to_dict() for msg in session.branch.messages],
    })"""
new3 = """        return _error(f"The model server couldn't be reached or returned an error: {e}", 502)
    # he READ the page this turn -- move the diff baseline (failed turns keep
    # the old baseline so the next attempt re-reports the same changes)
    session.last_seen_content = getattr(engine, "_current_page_content", None)
    store.save(session)
    return jsonify({
        "reply": reply,
        "branch": session.current_branch,
        "messages": [msg.to_dict() for msg in session.branch.messages],
    })"""
assert src.count(old3) == 1, "blocking anchor"
src = src.replace(old3, new3)

# ---- streaming: add on_success hook ------------------------------------------
old4 = "def _sse_chat_stream(engine, session, store, text, quote, manifest=None):"
new4 = "def _sse_chat_stream(engine, session, store, text, quote, manifest=None, on_success=None):"
assert src.count(old4) == 1, "stream sig anchor"
src = src.replace(old4, new4)

old5 = "            store.save(session)  # engine already saved under the store's lock; idempotent"
new5 = """            if on_success is not None:
                try:
                    on_success()
                except Exception:
                    pass  # bookkeeping must never break the turn
            store.save(session)  # engine already saved under the store's lock; idempotent"""
assert src.count(old5) == 1, "save anchor"
src = src.replace(old5, new5)

# ---- idea stream call passes the callback -------------------------------------
old6 = '    return _stream_response(_sse_chat_stream(engine, session, store, text, body.get("quote")))'
matches = src.count(old6)
assert matches == 1, f"idea stream anchor: {matches}"
new6 = """    return _stream_response(_sse_chat_stream(
        engine, session, store, text, body.get("quote"),
        on_success=lambda: setattr(session, "last_seen_content",
                                   getattr(engine, "_current_page_content", None))))"""
src = src.replace(old6, new6)

io.open(p, "w", encoding="utf-8").write(src)
print("part3 ok")
