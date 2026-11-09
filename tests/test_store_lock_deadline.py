"""Gap 68: every store-lock layer honors the shared monotonic wait budget."""

import threading
import time

import pytest

from screenplay_studio import jsonio


def _start_holder(path, hold_event):
    entered = threading.Event()

    def hold():
        with jsonio.lock_for(path):
            entered.set()
            hold_event.wait(2)

    thread = threading.Thread(target=hold, daemon=True)
    thread.start()
    assert entered.wait(1), "holder did not acquire the store lock"
    return thread


def test_same_process_waiter_times_out_at_lock_deadline_with_truthful_source(tmp_path):
    path = str(tmp_path / "held.json")
    release = threading.Event()
    holder = _start_holder(path, release)
    started = time.monotonic()

    try:
        with jsonio.lock_deadline(0.05):
            with pytest.raises(jsonio.StoreLockTimeout) as exc:
                with jsonio.lock_for(path):
                    pytest.fail("same-process waiter acquired before the holder released")
        elapsed = time.monotonic() - started
        assert elapsed < 0.2, f"the 50ms deadline took {elapsed:.3f}s"
        assert exc.value.wait_for == "another thread in this process"
        assert "another thread in this process" in str(exc.value)
        assert "held.json" in str(exc.value)
        assert "after 0.05s" in str(exc.value)
    finally:
        release.set()
        holder.join(1)
    assert not holder.is_alive()


def test_waiter_acquires_if_same_process_holder_releases_before_deadline(tmp_path):
    path = str(tmp_path / "held.json")
    release = threading.Event()
    holder = _start_holder(path, release)
    acquired = threading.Event()
    result = []

    def wait_for_lock():
        try:
            with jsonio.lock_deadline(0.5):
                with jsonio.lock_for(path):
                    acquired.set()
        except Exception as exc:  # preserve the worker's failure for assertion
            result.append(exc)

    waiter = threading.Thread(target=wait_for_lock, daemon=True)
    waiter.start()
    try:
        time.sleep(0.04)
        release.set()
        assert acquired.wait(0.4), "a live waiter should acquire once the holder releases"
    finally:
        release.set()
        waiter.join(1)
        holder.join(1)
    assert not result, result
    assert not waiter.is_alive() and not holder.is_alive()


def test_nested_deadline_takes_the_tighter_budget_for_local_wait(tmp_path):
    path = str(tmp_path / "held.json")
    release = threading.Event()
    holder = _start_holder(path, release)
    started = time.monotonic()

    try:
        with jsonio.lock_deadline(0.4):
            with jsonio.lock_deadline(0.04):
                with pytest.raises(jsonio.StoreLockTimeout) as exc:
                    with jsonio.lock_for(path):
                        pytest.fail("nested budget did not block the contended lock")
        elapsed = time.monotonic() - started
        assert elapsed < 0.2
        assert "after 0.04s" in str(exc.value)
    finally:
        release.set()
        holder.join(1)
    assert not holder.is_alive()


def test_same_thread_reentry_and_uncontended_lock_survive_an_expired_budget(tmp_path):
    path = str(tmp_path / "held.json")
    with jsonio.lock_deadline(0.01):
        with jsonio.lock_for(path):
            time.sleep(0.02)
            # Re-entering the RLock by its owner does not wait and must remain
            # legal even though the outer deadline elapsed while held.
            with jsonio.lock_for(path):
                pass
    # Likewise an uncontended acquisition has no wait to time out.
    with jsonio.lock_deadline(0.001):
        with jsonio.lock_for(path):
            pass
