---
name: api-migration
description: >
  Expert knowledge on migrating deprecated Python APIs to modern replacements
  across popular libraries including pandas, requests, django, and flask.
---

# API Migration Skill

## Migration Strategy

1. **Identify the exact deprecated API** and its removal timeline
2. **Find the official replacement** from library migration guides
3. **Check for behavioral differences** between old and new API
4. **Preserve function signatures** when the deprecated call is part of a public interface
5. **Update imports** if the replacement lives in a different module
6. **Run existing tests** to verify behavioral equivalence

## Python Standard Library Migrations

### `datetime` Module (Python 3.12+)
```python
# DEPRECATED (Python 3.12)
datetime.datetime.utcnow()
datetime.datetime.utcfromtimestamp(ts)

# MODERN
from datetime import UTC
datetime.datetime.now(UTC)
datetime.datetime.fromtimestamp(ts, tz=UTC)
```

### `typing` Module (Python 3.9–3.12 graduations)
```python
# DEPRECATED — typing generics (Python 3.9+)
from typing import List, Dict, Tuple, Optional, Set

# MODERN — built-in generics
list[str], dict[str, int], tuple[int, ...], str | None, set[int]

# DEPRECATED — typing.Union (Python 3.10+)
Union[str, int]

# MODERN — pipe syntax
str | int
```

### `asyncio` Deprecations
```python
# DEPRECATED (Python 3.10)
loop = asyncio.get_event_loop()
asyncio.coroutine  # removed in 3.11

# MODERN
loop = asyncio.get_running_loop()  # inside async context
asyncio.run(main())                # entry point
```

### `importlib` vs `pkg_resources`
```python
# DEPRECATED
import pkg_resources
pkg_resources.get_distribution("package").version

# MODERN
from importlib.metadata import version
version("package")
```

## Library-Specific Migrations

### pandas
```python
# DEPRECATED: append (removed in pandas 2.0)
df = df.append(new_row)
# MODERN
df = pd.concat([df, pd.DataFrame([new_row])])

# DEPRECATED: inplace parameter discouraged
df.drop(columns=["col"], inplace=True)
# MODERN — method chaining
df = df.drop(columns=["col"])
```

### requests
```python
# DEPRECATED: requests.packages.urllib3
import requests.packages.urllib3
# MODERN
import urllib3
```

### Django
```python
# DEPRECATED (Django 4.0+): url() with regex
from django.conf.urls import url
url(r'^articles/(?P<year>[0-9]{4})/$', views.year_archive)
# MODERN
from django.urls import path, re_path
path('articles/<int:year>/', views.year_archive)

# DEPRECATED (Django 4.1+): default_app_config
default_app_config = 'myapp.apps.MyAppConfig'
# MODERN — remove, Django auto-discovers
```

### Flask
```python
# DEPRECATED: before_first_request (Flask 2.3+)
@app.before_first_request
def init_db(): ...
# MODERN
with app.app_context():
    init_db()

# DEPRECATED: json attribute (Flask 2.2+)
data = request.json
# MODERN — preferred
data = request.get_json()
```

## Migration Checklist

- [ ] Replacement API is available in the minimum Python/library version target
- [ ] No behavioral changes between old and new API (or differences documented)
- [ ] Import statements updated
- [ ] All call sites migrated (not just the flagged one)
- [ ] Type annotations remain valid
- [ ] Existing tests pass without modification
- [ ] Backward compatibility wrapper added if public API changes
