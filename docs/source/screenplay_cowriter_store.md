# screenplay_cowriter/store.py

## Purpose
Session persistence for the CoWriter. Handles saving, loading, listing, and deleting sessions.

## Key Types

### `SessionStore`
```python
class SessionStore:
    def __init__(self, path: str):
        self.path = path
```
Manages session storage on disk.

## Key Functions

### `create(store: SessionStore, title: str) -> Session`
Creates a new session.

### `load(store: SessionStore, session_id: str) -> Session`
Loads a session by ID.

### `save(store: SessionStore, session: Session)`
Saves a session to disk.

### `list(store: SessionStore) -> list[dict]`
Lists all sessions (id, title, branch count, last updated). Lightweight listing without full deserialization.

### `delete(store: SessionStore, session_id: str)`
Deletes a session.

## Dependencies
- `screenplay_cowriter.models` (Session)
- `json` (stdlib)
- `pathlib` (stdlib)
- `os` (stdlib)

## Usage Example
```python
from screenplay_cowriter.store import SessionStore, create, load, save, list, delete

store = SessionStore(path="./sessions")
session = create(store, "My Script")
save(store, session)
sessions = list(store)
delete(store, session.id)
```

## Graph Notes
- `SessionStore` is the 10th most connected node (18 edges)
- Lightweight listing (id, title, branch count) — 1 inferred edge to Session
