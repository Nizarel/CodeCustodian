"""Tests for policy management."""

from __future__ import annotations

import tempfile

import yaml

from codecustodian.config.policies import PolicyManager, PolicyOverride, _deep_merge


class TestPolicyOverride:
    def test_create(self):
        po = PolicyOverride(
            scope="org:contoso",
            overrides={"behavior": {"auto_merge": True}},
            description="Org-wide defaults",
        )
        assert po.scope == "org:contoso"
        assert po.enabled is True


class TestPolicyManager:
    def test_create_default(self):
        pm = PolicyManager()
        assert pm._org_policy == {}
        assert pm._repo_overrides == {}

    def test_create_with_org_policy(self):
        pm = PolicyManager(org_policy={"behavior": {"auto_merge": False}})
        assert pm._org_policy["behavior"]["auto_merge"] is False

    def test_add_and_resolve(self):
        pm = PolicyManager()
        pm.add_policy(
            PolicyOverride(
                scope="org:test",
                overrides={"behavior": {"auto_merge": True}},
            )
        )
        config = pm.resolve()
        assert config.behavior.auto_merge is True

    def test_resolve_repo_overrides(self):
        pm = PolicyManager(
            repo_overrides={
                "frontend": {"behavior": {"confidence_threshold": 9}},
            }
        )
        config = pm.resolve(repo_name="frontend")
        assert config.behavior.confidence_threshold == 9

    def test_get_effective_policy(self):
        pm = PolicyManager(
            org_policy={"behavior": {"auto_merge": False}},
            repo_overrides={"api": {"behavior": {"auto_merge": True}}},
        )
        effective = pm.get_effective_policy("api")
        assert effective["behavior"]["auto_merge"] is True

    def test_load_policies_from_file(self):
        data = {
            "policies": [
                {
                    "scope": "org:test",
                    "overrides": {"behavior": {"auto_merge": True}},
                    "enabled": True,
                }
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            yaml.dump(data, f)
            f.flush()
            pm = PolicyManager()
            pm.load_policies_from_file(f.name)
            assert len(pm._policies) == 1


class TestPathControls:
    def test_is_path_allowed_default(self):
        pm = PolicyManager()
        assert pm.is_path_allowed("src/main.py") is True

    def test_is_path_denied(self):
        pm = PolicyManager(
            repo_overrides={
                "repo1": {"denylist": ["vendor/*"]},
            }
        )
        assert pm.is_path_allowed("vendor/lib.py", repo_name="repo1") is False
        assert pm.is_path_allowed("src/main.py", repo_name="repo1") is True

    def test_should_use_proposal_mode_sensitive_path(self):
        pm = PolicyManager()
        assert pm.should_use_proposal_mode(
            "src/auth/login.py",
            sensitive_paths=["**/auth/**"],
        ) is True

    def test_should_use_proposal_mode_normal_path(self):
        pm = PolicyManager()
        assert pm.should_use_proposal_mode(
            "src/utils/helpers.py",
            sensitive_paths=["**/auth/**"],
        ) is False

    def test_should_use_proposal_mode_finding_type(self):
        pm = PolicyManager()
        assert pm.should_use_proposal_mode(
            "src/main.py",
            finding_type="security",
            proposal_only_types={"security"},
        ) is True


class TestDeepMerge:
    def test_simple_merge(self):
        result = _deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        result = _deep_merge(base, override)
        assert result == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_override_replaces_non_dict(self):
        result = _deep_merge({"a": "old"}, {"a": "new"})
        assert result["a"] == "new"


class TestEnvOverrides:
    def test_env_override_applied(self, monkeypatch):
        monkeypatch.setenv("CODECUSTODIAN_BEHAVIOR__AUTO_MERGE", "true")
        pm = PolicyManager()
        config = pm.resolve()
        assert config.behavior.auto_merge is True

    def test_env_override_int(self, monkeypatch):
        monkeypatch.setenv("CODECUSTODIAN_BEHAVIOR__CONFIDENCE_THRESHOLD", "9")
        pm = PolicyManager()
        config = pm.resolve()
        assert config.behavior.confidence_threshold == 9
