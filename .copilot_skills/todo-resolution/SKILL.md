---
name: todo-resolution
description: >
  Strategies for resolving TODO, FIXME, HACK, and XXX comments
  including implementation patterns and issue conversion.
---

# TODO Resolution Skill

## Resolution Strategies by Tag

### TODO — Planned Implementation
The code author intended to add something. Resolve by:
1. Implementing the described functionality
2. If implementation is complex, create a GitHub issue and reference it
3. If the TODO is obsolete (feature already exists), remove the comment

### FIXME — Known Bug or Workaround
Something is broken or suboptimal. Resolve by:
1. Fixing the identified bug
2. Replacing the workaround with a proper solution
3. Adding a test that validates the fix

### HACK — Temporary Workaround
A deliberate shortcut. Resolve by:
1. Replacing with a proper implementation
2. Document why the "hack" existed (in commit message)
3. Verify the proper solution handles edge cases the hack covered

### XXX — Attention Required
Marks areas needing review. Resolve by:
1. Reviewing and either fixing or documenting the decision
2. Converting to a more specific tag (TODO/FIXME) if work remains

## Common Patterns

### Error Handling TODOs
```python
# TODO: Add proper error handling
try:
    result = process(data)
except Exception:
    pass

# RESOLVED
try:
    result = process(data)
except ValidationError as exc:
    logger.warning("Validation failed: %s", exc)
    raise
except ConnectionError as exc:
    logger.error("Connection failed: %s", exc)
    raise ProcessingError("Upstream unavailable") from exc
```

### Logging TODOs
```python
# TODO: Add logging
def sync_data(source):
    data = source.fetch()
    transform(data)

# RESOLVED
def sync_data(source):
    logger.info("Starting data sync from %s", source.name)
    data = source.fetch()
    logger.debug("Fetched %d records", len(data))
    transform(data)
    logger.info("Data sync complete")
```

### Validation TODOs
```python
# TODO: Validate input
def create_user(email, name):
    return User(email=email, name=name)

# RESOLVED
def create_user(email: str, name: str) -> User:
    if not email or "@" not in email:
        raise ValueError(f"Invalid email: {email!r}")
    if not name or len(name) > 200:
        raise ValueError(f"Invalid name length: {len(name)}")
    return User(email=email.strip().lower(), name=name.strip())
```

## Resolution Principles

1. **Respect the author's intent** — Read surrounding code to understand what was planned
2. **Minimal scope** — Implement only what the TODO describes, not extra features
3. **Test coverage** — Add a test for the resolved functionality
4. **Remove the comment** — Once resolved, delete the TODO/FIXME/HACK/XXX comment
5. **Commit separately** — Each resolved TODO should be a distinct, reviewable change
