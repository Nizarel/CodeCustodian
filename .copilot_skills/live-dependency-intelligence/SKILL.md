---
name: live-dependency-intelligence
description: >
  Live PyPI version checking, semantic versioning analysis, changelog
  interpretation, and migration planning from release notes.
---

# Live Dependency Intelligence Skill

## PyPI Version Analysis

### Semantic Versioning Rules
- **Patch** (1.2.3 → 1.2.4): Bug fixes — safe, upgrade immediately
- **Minor** (1.2.3 → 1.3.0): New features, backward compatible — review changelog
- **Major** (1.2.3 → 2.0.0): Breaking changes — migration plan required

### Live PyPI Data Points
When `live_pypi` is enabled, each finding is enriched with:
- `pypi_latest`: Current latest version on PyPI
- `pypi_release_date`: When the latest version was published
- `major_version_jump`: Whether upgrading crosses a major version boundary
- `changelog_url`: Link to the project's changelog for review

### Priority Escalation
- **Major version jump + security fix**: CRITICAL — upgrade with migration plan
- **Major version jump**: HIGH — plan migration for next sprint
- **Minor version behind by 3+**: MEDIUM — schedule upgrade
- **Patch behind**: LOW — include in next dependency update batch

## Migration Planning

### Changelog Analysis Strategy
1. Read the CHANGELOG between current and target versions
2. Search for keywords: "breaking", "removed", "renamed", "deprecated"
3. Map each breaking change to affected code in the codebase
4. Generate import path updates, parameter renames, type changes

### Common Breaking Change Patterns

#### Import Path Reorganization
```python
# Many libraries reorganize in major versions
# v1: from library.utils import helper
# v2: from library.core.utils import helper
# Fix: Update all import statements, check __init__.py re-exports
```

#### Parameter Renames
```python
# v1: client.request(timeout=30)
# v2: client.request(request_timeout=30)
# Fix: Search for all call sites, update keyword arguments
```

#### Return Type Changes
```python
# v1: result = api.get(id)  # returns dict
# v2: result = api.get(id)  # returns Pydantic model
# Fix: Update all result access patterns (.key vs ["key"])
```

#### Default Behavior Changes
```python
# v1: requests.get(url)  # verify=True by default
# v2: requests.get(url)  # verify=True (unchanged, but new warning)
# Note: Sometimes defaults change silently — always check release notes
```

## Transitive Dependency Risk

### Identifying Transitive Conflicts
- Use `pip list --outdated` or `uv pip list --outdated`
- Check `pyproject.toml` dependency bounds vs transitive requirements
- Flag packages where direct + transitive requirements conflict

### Safe Upgrade Workflow
1. Lock current environment state
2. Upgrade one package at a time
3. Run full test suite after each upgrade
4. Check for deprecation warnings in test output
5. Commit each successful upgrade separately
