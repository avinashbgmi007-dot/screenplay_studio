# screenplay_cowriter/models.py

## Purpose
Defines the data models for the CoWriter session system: sessions, branches, messages, and the operations to manage them.

## Key Types

### `Session`
```python
@dataclass
class Session:
    id: str
    title: str
    branch: str
    messages: list[Message]
    created_at: str
    updated_at: str
```
A conversation session with a title, current branch, and message history.

### `Branch`
```python
@dataclass
class Branch:
    name: str
    messages: list[Message]
```
A branch within a session (forked conversation).

### `Message`
```python
@dataclass
class Message:
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
```
A single message in the conversation.

## Key Functions

### `fork(session: Session, branch_name: str) -> Session`
Forks a session into a new branch.

### `switch(session: Session, branch_name: str) -> Session`
Switches to a different branch.

### `delete_branch(session: Session, branch_name: str) -> Session`
Deletes a branch.

## Dependencies
- `dataclasses` (stdlib)
- `datetime` (stdlib)
- `screenplay_cowriter.store` (SessionStore)

## Usage Example
```python
from screenplay_cowriter.models import Session, fork, switch

session = Session(id="1", title="My Script", branch="main", messages=[], ...)
session = fork(session, "experiment")
session = switch(session, "experiment")
```

## Graph Notes
- `SessionStore` (18 edges) — manages persistence of sessions
- `Session` is connected to `SessionStore` (1 inferred edge)
