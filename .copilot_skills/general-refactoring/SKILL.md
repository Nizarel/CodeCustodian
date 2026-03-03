---
name: general-refactoring
description: >
  General Python modernization patterns and best practices.
  Fallback skill for findings not covered by specialised skills.
---

# General Refactoring Skill

## Python 3.11+ Modernization

### Structural Pattern Matching (3.10+)
```python
# BEFORE
if isinstance(event, ClickEvent):
    handle_click(event)
elif isinstance(event, KeyEvent):
    handle_key(event)
else:
    handle_unknown(event)

# MODERN
match event:
    case ClickEvent():
        handle_click(event)
    case KeyEvent():
        handle_key(event)
    case _:
        handle_unknown(event)
```

### Exception Groups (3.11+)
```python
# When handling multiple independent errors
try:
    results = await asyncio.gather(*tasks, return_exceptions=True)
except* ValueError as eg:
    for exc in eg.exceptions:
        logger.warning("Validation error: %s", exc)
except* OSError as eg:
    for exc in eg.exceptions:
        logger.error("IO error: %s", exc)
```

### f-string Improvements (3.12+)
```python
# Nested quotes now allowed
msg = f"User {user['name']} logged in"  # works in 3.12+
```

### `@override` Decorator (3.12+)
```python
from typing import override

class Child(Parent):
    @override
    def method(self) -> str:
        return "child"
```

## General Best Practices

### Use Pathlib over os.path
```python
# OLD
import os
path = os.path.join(base, "subdir", "file.txt")
if os.path.exists(path):
    with open(path) as f:
        content = f.read()

# MODERN
from pathlib import Path
path = Path(base) / "subdir" / "file.txt"
if path.exists():
    content = path.read_text()
```

### Context Managers for Resources
```python
# BAD
f = open("data.txt")
data = f.read()
f.close()

# GOOD
with open("data.txt") as f:
    data = f.read()

# For custom resources
from contextlib import contextmanager

@contextmanager
def managed_connection(url):
    conn = connect(url)
    try:
        yield conn
    finally:
        conn.close()
```

### Dataclasses over Plain Classes
```python
# BEFORE
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# MODERN
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float
```

### Enumerate over Range-Len
```python
# BAD
for i in range(len(items)):
    print(i, items[i])

# GOOD
for i, item in enumerate(items):
    print(i, item)
```

## Refactoring Safety Rules

1. **One refactoring at a time** — Don't combine multiple changes in one diff
2. **Preserve behavior** — Refactoring changes structure, not functionality
3. **Test before and after** — Ensure tests pass both before and after the change
4. **Keep changes minimal** — Touch only the code that needs to change
5. **Respect existing patterns** — Follow the conventions already in the codebase
