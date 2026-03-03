---
name: dependency-management
description: >
  Version compatibility analysis, breaking change detection, and safe
  dependency upgrade strategies for Python projects.
---

# Dependency Management Skill

## Upgrade Strategy

### Semver Analysis
- **Patch** (1.2.3 → 1.2.4): Bug fixes only — safe to upgrade
- **Minor** (1.2.3 → 1.3.0): New features, backward compatible — review changelog
- **Major** (1.2.3 → 2.0.0): Breaking changes likely — migration guide required

### Safe Upgrade Process
1. Check the library's CHANGELOG/release notes for breaking changes
2. Review the diff between pinned and target versions
3. Check if any deprecated APIs you use are removed in the new version
4. Update the version pin
5. Run full test suite
6. Check for new deprecation warnings in test output

## Common Breaking Change Patterns

### Import Path Changes
```python
# Library moved modules in major version
# OLD (library v1)
from library.utils import helper
# NEW (library v2)
from library.core.utils import helper
```

### API Signature Changes
```python
# Parameter renamed or removed
# OLD
client.send(data, timeout=30)
# NEW — parameter renamed
client.send(data, request_timeout=30)
```

### Return Type Changes
```python
# Function returns different type in new version
# OLD — returned dict
result = api.get_user(id)  # -> dict
# NEW — returns Pydantic model
result = api.get_user(id)  # -> User model
result.name  # works
result["name"]  # breaks!
```

### Default Behavior Changes
```python
# Default parameter value changed
# OLD — verify=False by default
requests.get(url)
# NEW — verify=True by default (security improvement)
requests.get(url)  # now validates SSL
```

## Lockfile Management

### pyproject.toml — Version Specifiers
```toml
# Flexible (recommended for libraries)
dependencies = ["requests>=2.28,<3"]

# Pinned (recommended for applications)
dependencies = ["requests==2.31.0"]

# Compatible release
dependencies = ["requests~=2.28"]  # >=2.28, <3.0
```

### requirements.txt Best Practices
- Pin exact versions for reproducible builds
- Use `pip-compile` (pip-tools) to generate from `requirements.in`
- Separate dev/test/prod requirement files
- Include hashes for supply-chain security: `--require-hashes`

## Compatibility Checklist

- [ ] Target version supports our Python version (check `python_requires`)
- [ ] No removed APIs we depend on (check CHANGELOG)
- [ ] No renamed parameters in our call sites
- [ ] No return type changes affecting our code
- [ ] No new required dependencies that conflict with existing ones
- [ ] No known security vulnerabilities in target version
- [ ] All tests pass with the new version
