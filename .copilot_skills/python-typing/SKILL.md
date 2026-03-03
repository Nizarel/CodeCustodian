---
name: python-typing
description: >
  Modern Python typing expertise for Python 3.11+, including generic syntax,
  Protocol, TypeVar, ParamSpec, and mypy/pyright compatibility.
---

# Python Typing Skill

## Modern Syntax (Python 3.10+)

### Built-in Generics (PEP 585)
```python
# OLD
from typing import List, Dict, Tuple, Set, FrozenSet, Type

# MODERN — use built-in types directly
list[str]
dict[str, int]
tuple[int, ...]
set[float]
frozenset[str]
type[MyClass]
```

### Union Syntax (PEP 604)
```python
# OLD
from typing import Optional, Union
x: Optional[str]       # → str | None
y: Union[str, int]     # → str | int

# MODERN
x: str | None
y: str | int
```

### TypeAlias (PEP 613) and `type` statement (PEP 695, 3.12+)
```python
# Python 3.10+
from typing import TypeAlias
Vector: TypeAlias = list[float]

# Python 3.12+
type Vector = list[float]
```

## Advanced Patterns

### Protocol (Structural Subtyping)
```python
from typing import Protocol

class Readable(Protocol):
    def read(self, n: int = -1) -> str: ...

def process(source: Readable) -> str:
    return source.read()
# Works with any object that has a read() method
```

### TypeVar and Generics
```python
from typing import TypeVar

T = TypeVar("T")

def first(items: list[T]) -> T:
    return items[0]

# Python 3.12+ syntax
def first[T](items: list[T]) -> T:
    return items[0]
```

### ParamSpec (PEP 612)
```python
from typing import ParamSpec, TypeVar, Callable

P = ParamSpec("P")
R = TypeVar("R")

def retry(fn: Callable[P, R]) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(*args, **kwargs)
    return wrapper
```

### TypeGuard and TypeIs
```python
from typing import TypeGuard, TypeIs  # TypeIs: 3.13+

def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
    return all(isinstance(x, str) for x in val)
```

### Literal and Final
```python
from typing import Literal, Final

Mode = Literal["read", "write", "append"]
MAX_SIZE: Final = 1024

def open_file(path: str, mode: Mode = "read") -> None: ...
```

## Common Annotation Patterns

### Return types
```python
# Functions that may return None
def find(key: str) -> str | None: ...

# Async functions
async def fetch(url: str) -> bytes: ...

# Generators
def count() -> Iterator[int]: ...

# Context managers
def connect() -> ContextManager[Connection]: ...
```

### Callable types
```python
from collections.abc import Callable

# Simple callback
handler: Callable[[str, int], bool]

# No-arg callback
on_done: Callable[[], None]

# Any args
logger: Callable[..., None]
```

### Class patterns
```python
from typing import Self, ClassVar

class Builder:
    count: ClassVar[int] = 0

    def set_name(self, name: str) -> Self:
        self.name = name
        return self
```

## mypy/pyright Compatibility Notes

- Always use `from __future__ import annotations` for Python <3.10 PEP 604 syntax
- `dict[str, Any]` is preferred over `Dict[str, Any]` from 3.9+
- Use `@overload` for functions with different return types based on input
- Avoid bare `Callable` — always specify params: `Callable[[int], str]`
- Use `cast()` sparingly — prefer type narrowing with `isinstance()`
