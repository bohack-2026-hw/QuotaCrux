import threading

from quotacrux import db


def test_observer_is_after_commit_and_nested_scopes_restore(monkeypatch):
    committed, outer, inner = [], [], []
    monkeypatch.setattr(db, "insert", lambda table, row: committed.append((table, row)))

    def observe(event):
        assert committed[-1][1]["payload_json"] == db.dumps(event["payload"])
        outer.append(event)

    with db.observe_events(observe):
        db.add_event("run-test", "first", {"n": 1})
        with db.observe_events(inner.append):
            db.add_event("run-test", "nested", {"n": 2})
        db.add_event("run-test", "restored", {"n": 3})
    db.add_event("run-test", "outside", {})
    assert [event["type"] for event in outer] == ["first", "restored"]
    assert [event["type"] for event in inner] == ["nested"]
    assert len(committed) == 4


def test_observers_are_thread_local(monkeypatch):
    monkeypatch.setattr(db, "insert", lambda *_: None)
    events = []
    with db.observe_events(events.append):
        worker = threading.Thread(target=lambda: db.add_event("other-run", "other-thread", {}))
        worker.start()
        worker.join()
        db.add_event("run-test", "own-thread", {})
    assert [event["type"] for event in events] == ["own-thread"]
