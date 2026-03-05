---
name: framework-migrations
description: Multi-stage framework migration planning with dependency ordering
---

# Framework Migrations Skill

## Purpose

Plan and execute multi-stage framework/library upgrades using
dependency-aware ordering, staged PRs, and per-stage verification.

## Supported Migration Patterns

- Major version upgrades (e.g., Flask 2.x → 3.x)
- API renames and import path changes
- Deprecated parameter removal
- Configuration format changes
- ORM schema/query migrations

## Planning Strategy

1. **Detect** the framework and version range from scanner findings.
2. **Load playbook** if one exists in config — provides known find/replace patterns.
3. **Ask AI** to produce a JSON array of migration stages if no playbook matches.
4. **Build DAG** — each stage declares `depends_on` for other stages.
5. **Topological sort** stages via `networkx` to honour dependencies.
6. **Estimate complexity**: simple (≤2 stages, ≤5 files), complex, expert-only.

## Execution Model

Each stage is executed atomically:

1. Apply file changes via `SafeFileEditor` (backup first).
2. Run `TestRunner` + `LinterRunner` to verify.
3. On pass → mark stage `passed`.
4. On fail → rollback stage, mark `failed`, skip dependent stages.

## PR Strategy

| Strategy | Behaviour |
|----------|-----------|
| `single` | One PR with all stages combined |
| `staged` | One PR per stage (default) — easier to review |

## Breaking Changes

When findings include severity `high` or `critical`, flag them as
breaking changes in the `MigrationPlan.breaking_changes` list.
