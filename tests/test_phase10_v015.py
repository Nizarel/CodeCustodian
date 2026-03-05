"""Tests for v0.15.0 features: AI Test Synthesis, Agentic Migrations, ChatOps."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from codecustodian.config.schema import (
    ChatOpsConfig,
    MigrationsConfig,
    TestSynthesisConfig,
)
from codecustodian.models import (
    ChatOpsNotification,
    CodeContext,
    Finding,
    FindingType,
    MigrationPlan,
    MigrationPlaybook,
    MigrationStage,
    SeverityLevel,
    TestSynthesisResult,
)

# ═══════════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════════


class TestTestSynthesisResult:
    def test_defaults(self):
        r = TestSynthesisResult(finding_id="f1")
        assert r.test_code == ""
        assert r.test_count == 0
        assert r.passed_original is False
        assert r.passed_refactored is None
        assert r.discarded is False

    def test_discard_reason(self):
        r = TestSynthesisResult(
            finding_id="f1", discarded=True, discard_reason="syntax error"
        )
        assert r.discarded is True
        assert r.discard_reason == "syntax error"


class TestMigrationStage:
    def test_defaults(self):
        s = MigrationStage(name="step-1")
        assert s.order == 0
        assert s.status == "pending"
        assert s.depends_on == []

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            MigrationStage(name="s", status="invalid")

    def test_valid_statuses(self):
        for status in ("pending", "running", "passed", "failed", "rolled_back"):
            s = MigrationStage(name="s", status=status)
            assert s.status == status


class TestMigrationPlan:
    def test_defaults(self):
        p = MigrationPlan(framework="flask", from_version="2.0", to_version="3.0")
        assert p.estimated_complexity == "simple"
        assert p.pr_strategy == "staged"
        assert len(p.id) == 12

    def test_invalid_complexity(self):
        with pytest.raises(ValidationError):
            MigrationPlan(
                framework="x", from_version="1", to_version="2",
                estimated_complexity="unknown",
            )

    def test_invalid_pr_strategy(self):
        with pytest.raises(ValidationError):
            MigrationPlan(
                framework="x", from_version="1", to_version="2",
                pr_strategy="parallel",
            )


class TestMigrationPlaybook:
    def test_basic(self):
        pb = MigrationPlaybook(name="flask", framework="flask", guide_url="https://example.com")
        assert pb.patterns == []


class TestChatOpsNotification:
    def test_defaults(self):
        n = ChatOpsNotification(message_type="scan_complete")
        assert n.delivered is False
        assert len(n.id) == 12

    def test_invalid_message_type(self):
        with pytest.raises(ValidationError):
            ChatOpsNotification(message_type="unknown_type")

    def test_valid_types(self):
        for mt in ("pr_created", "approval_needed", "scan_complete", "verification_failed"):
            n = ChatOpsNotification(message_type=mt)
            assert n.message_type == mt


# ═══════════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════════


class TestTestSynthesisConfig:
    def test_defaults(self):
        c = TestSynthesisConfig()
        assert c.enabled is False
        assert c.max_per_run == 3
        assert c.timeout_per_test == 30
        assert c.require_passing_original is True

    def test_min_max_per_run(self):
        with pytest.raises(ValidationError):
            TestSynthesisConfig(max_per_run=0)

    def test_min_timeout(self):
        with pytest.raises(ValidationError):
            TestSynthesisConfig(timeout_per_test=2)


class TestMigrationsConfig:
    def test_defaults(self):
        c = MigrationsConfig()
        assert c.enabled is False
        assert c.pr_strategy == "staged"
        assert c.max_files_per_stage == 10
        assert c.playbooks == {}


class TestChatOpsConfig:
    def test_defaults(self):
        c = ChatOpsConfig()
        assert c.enabled is False
        assert c.connector == "teams"
        assert c.teams_webhook_url == ""
        assert c.crunch_time_digest is True


class TestRootConfigWiring:
    def test_new_sections_exist(self):
        from codecustodian.config.schema import CodeCustodianConfig
        cfg = CodeCustodianConfig()
        assert isinstance(cfg.test_synthesis, TestSynthesisConfig)
        assert isinstance(cfg.migrations, MigrationsConfig)
        assert isinstance(cfg.chatops, ChatOpsConfig)


# ═══════════════════════════════════════════════════════════════════════════
# AI Test Synthesizer
# ═══════════════════════════════════════════════════════════════════════════


class TestTestSynthesizer:
    @pytest.mark.asyncio
    async def test_disabled_config(self):
        from codecustodian.planner.test_synthesizer import TestSynthesizer

        config = TestSynthesisConfig(enabled=False)
        synth = TestSynthesizer(config=config)
        finding = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.MEDIUM,
            file="x.py", line=1, description="test",
        )
        ctx = CodeContext(
            source_code="pass", file_path="x.py", language="python",
            start_line=1, end_line=1,
        )
        result = await synth.synthesize(finding, ctx)
        assert result.discarded is True
        assert "disabled" in result.discard_reason

    def test_strip_fencing(self):
        from codecustodian.planner.test_synthesizer import TestSynthesizer

        code = "```python\ndef test_foo():\n    pass\n```"
        assert "```" not in TestSynthesizer._strip_fencing(code)
        assert "def test_foo" in TestSynthesizer._strip_fencing(code)

    def test_check_syntax_valid(self):
        from codecustodian.planner.test_synthesizer import TestSynthesizer

        errors = TestSynthesizer._check_syntax("def test_ok():\n    assert True\n")
        assert errors == []

    def test_check_syntax_invalid(self):
        from codecustodian.planner.test_synthesizer import TestSynthesizer

        errors = TestSynthesizer._check_syntax("def test_bad(:\n")
        assert len(errors) == 1
        assert "SyntaxError" in errors[0]

    def test_count_tests(self):
        from codecustodian.planner.test_synthesizer import TestSynthesizer

        code = "def test_a(): pass\ndef test_b(): pass\ndef helper(): pass\n"
        assert TestSynthesizer._count_tests(code) == 2

    def test_count_tests_syntax_error(self):
        from codecustodian.planner.test_synthesizer import TestSynthesizer

        assert TestSynthesizer._count_tests("def test_bad(:") == 0


# ═══════════════════════════════════════════════════════════════════════════
# SDK Tools (run_pytest_subset, check_test_syntax)
# ═══════════════════════════════════════════════════════════════════════════


class TestSDKToolCheckTestSyntax:
    @pytest.mark.asyncio
    async def test_valid_code(self):
        from codecustodian.planner.tools import CheckTestSyntaxParams, _get_impl, check_test_syntax

        result = await _get_impl(check_test_syntax)(CheckTestSyntaxParams(code="def test_x(): pass"))
        assert "1 test function" in result

    @pytest.mark.asyncio
    async def test_invalid_code(self):
        from codecustodian.planner.tools import CheckTestSyntaxParams, _get_impl, check_test_syntax

        result = await _get_impl(check_test_syntax)(CheckTestSyntaxParams(code="def bad(:"))
        assert "SyntaxError" in result


class TestSDKToolRunPytestSubset:
    @pytest.mark.asyncio
    async def test_missing_file(self):
        from codecustodian.planner.tools import RunPytestSubsetParams, _get_impl, run_pytest_subset

        result = await _get_impl(run_pytest_subset)(RunPytestSubsetParams(test_file="/nonexistent/test.py"))
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_non_py_file(self, tmp_path):
        from codecustodian.planner.tools import RunPytestSubsetParams, _get_impl, run_pytest_subset

        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        result = await _get_impl(run_pytest_subset)(RunPytestSubsetParams(test_file=str(txt)))
        assert "must be a .py file" in result


# ═══════════════════════════════════════════════════════════════════════════
# Agentic Migrations
# ═══════════════════════════════════════════════════════════════════════════


class TestMigrationEngine:
    @pytest.mark.asyncio
    async def test_disabled_config(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=False)
        engine = MigrationEngine(config=config)
        result = await engine.plan_migration([])
        assert result is None

    @pytest.mark.asyncio
    async def test_no_findings(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        result = await engine.plan_migration([])
        assert result is None

    def test_detect_framework(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        finding = Finding(
            type=FindingType.DEPRECATED_API,
            severity=SeverityLevel.HIGH,
            file="app.py", line=1,
            description="Deprecated Flask API — migrate to v3",
        )
        fw, _from_v, _to_v = MigrationEngine._detect_framework([finding])
        assert fw == "flask"

    def test_detect_framework_no_match(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        finding = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.LOW,
            file="app.py", line=1,
            description="Function too long",
        )
        fw, _, _ = MigrationEngine._detect_framework([finding])
        assert fw == ""

    def test_topological_sort_simple(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        stages = [
            MigrationStage(name="b", order=1, depends_on=["a"]),
            MigrationStage(name="a", order=0),
        ]
        sorted_stages = engine._topological_sort(stages)
        names = [s.name for s in sorted_stages]
        assert names.index("a") < names.index("b")

    def test_estimate_complexity_simple(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        stages = [MigrationStage(name="s1", files_affected=["a.py", "b.py"])]
        assert MigrationEngine._estimate_complexity(stages) == "simple"

    def test_estimate_complexity_expert(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        stages = [MigrationStage(name=f"s{i}", files_affected=[f"f{j}.py" for j in range(5)]) for i in range(6)]
        assert MigrationEngine._estimate_complexity(stages) == "expert-only"

    def test_playbook_loading(self):
        from codecustodian.config.schema import (
            MigrationPlaybookConfig,
            MigrationPlaybookPatternConfig,
        )
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(
            enabled=True,
            playbooks={
                "flask": MigrationPlaybookConfig(
                    guide_url="https://flask.palletsprojects.com/en/3.0.x/changes/",
                    patterns=[
                        MigrationPlaybookPatternConfig(pattern="from flask.ext", replacement="from flask"),
                    ],
                )
            },
        )
        engine = MigrationEngine(config=config)
        pb = engine._load_playbook("flask")
        assert pb is not None
        assert pb.framework == "flask"
        assert len(pb.patterns) == 1

    def test_playbook_not_found(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        assert engine._load_playbook("nonexistent") is None

    def test_stages_from_playbook(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        pb = MigrationPlaybook(
            name="flask", framework="flask",
            patterns=[
                {"pattern": "old1", "replacement": "new1"},
                {"pattern": "old2", "replacement": "new2"},
            ],
        )
        stages = engine._stages_from_playbook(pb)
        assert len(stages) == 2
        assert stages[0].name == "step-1"
        assert stages[1].depends_on == ["step-1"]

    @pytest.mark.asyncio
    async def test_execute_plan_marks_stages(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        plan = MigrationPlan(
            framework="test", from_version="1", to_version="2",
            stages=[
                MigrationStage(name="a", order=0),
                MigrationStage(name="b", order=1, depends_on=["a"]),
            ],
        )
        result = await engine.execute_plan(plan)
        assert result.stages[0].status == "passed"
        assert result.stages[1].status == "passed"

    @pytest.mark.asyncio
    async def test_execute_plan_rollback_on_failure(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)

        async def fail_verify():
            return False

        mock_verifier = MagicMock()
        mock_verifier.verify_all = fail_verify

        plan = MigrationPlan(
            framework="test", from_version="1", to_version="2",
            stages=[
                MigrationStage(name="a", order=0),
                MigrationStage(name="b", order=1, depends_on=["a"]),
            ],
        )

        result = await engine.execute_plan(plan, verifier=mock_verifier)
        assert result.stages[0].status == "failed"
        assert result.stages[1].status == "rolled_back"

    def test_parse_stages_valid(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        raw = json.dumps([
            {"name": "step1", "description": "First step", "order": 0},
            {"name": "step2", "description": "Second", "order": 1, "depends_on": ["step1"]},
        ])
        stages = engine._parse_stages(raw)
        assert len(stages) == 2
        assert stages[1].depends_on == ["step1"]

    def test_parse_stages_malformed(self):
        from codecustodian.intelligence.migrations import MigrationEngine

        config = MigrationsConfig(enabled=True)
        engine = MigrationEngine(config=config)
        assert engine._parse_stages("not json") == []


# ═══════════════════════════════════════════════════════════════════════════
# ChatOps Teams
# ═══════════════════════════════════════════════════════════════════════════


class TestAdaptiveCards:
    def test_scan_complete_card(self):
        from codecustodian.integrations.teams_chatops import build_scan_complete_card

        card = build_scan_complete_card(total_findings=42, critical=5, high=10, repo="myrepo")
        assert card["type"] == "AdaptiveCard"
        assert any("42" in str(b) for b in card["body"])

    def test_pr_created_card(self):
        from codecustodian.integrations.teams_chatops import build_pr_created_card

        card = build_pr_created_card(
            pr_url="https://github.com/org/repo/pull/1",
            pr_title="Fix deprecated APIs",
            finding_count=3,
            confidence=8,
        )
        assert card["type"] == "AdaptiveCard"

    def test_approval_needed_card_with_callback(self):
        from codecustodian.integrations.teams_chatops import build_approval_needed_card

        card = build_approval_needed_card(
            finding_id="f1", summary="Fix XSS", risk="high",
            callback_url="https://callback.example.com",
        )
        assert card["type"] == "AdaptiveCard"
        actions = [b for b in card["body"] if b.get("type") == "ActionSet"]
        assert len(actions) == 1

    def test_verification_failed_card(self):
        from codecustodian.integrations.teams_chatops import build_verification_failed_card

        card = build_verification_failed_card(
            finding_id="f1", errors=["Test failed", "Lint error"]
        )
        assert card["type"] == "AdaptiveCard"

    def test_migration_card(self):
        from codecustodian.integrations.teams_chatops import build_migration_card

        plan = MigrationPlan(
            framework="flask", from_version="2.0", to_version="3.0",
            stages=[MigrationStage(name="s1", description="Step 1")],
        )
        card = build_migration_card(plan)
        assert card["type"] == "AdaptiveCard"
        assert "flask" in str(card["body"][0])

    def test_build_card_for_notification(self):
        from codecustodian.integrations.teams_chatops import build_card_for_notification

        n = ChatOpsNotification(
            message_type="scan_complete",
            payload={"total_findings": 10, "critical": 1, "high": 3},
        )
        card = build_card_for_notification(n)
        assert card["type"] == "AdaptiveCard"

    def test_build_card_for_unknown_type_fallback(self):
        from codecustodian.integrations.teams_chatops import build_card_for_notification

        # bypass validation for test
        n = ChatOpsNotification.model_construct(
            id="test", message_type="custom_event", payload={"key": "val"},
            adaptive_card_json={}, channel="", delivered=False,
        )
        card = build_card_for_notification(n)
        assert card["type"] == "AdaptiveCard"


class TestTeamsConnector:
    @pytest.mark.asyncio
    async def test_disabled_config(self):
        config = ChatOpsConfig(enabled=False)
        from codecustodian.integrations.teams_chatops import TeamsConnector

        connector = TeamsConnector(config=config)
        n = ChatOpsNotification(message_type="scan_complete")
        result = await connector.send(n)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_webhook_url(self):
        config = ChatOpsConfig(enabled=True, teams_webhook_url="")
        from codecustodian.integrations.teams_chatops import TeamsConnector

        connector = TeamsConnector(config=config)
        n = ChatOpsNotification(message_type="scan_complete")
        result = await connector.send(n)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        from codecustodian.integrations.teams_chatops import TeamsConnector

        config = ChatOpsConfig(
            enabled=True, teams_webhook_url="https://webhook.example.com"
        )
        connector = TeamsConnector(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        connector._client = mock_client

        n = ChatOpsNotification(message_type="scan_complete", payload={
            "total_findings": 5, "critical": 0, "high": 1,
        })
        result = await connector.send(n)
        assert result is True
        assert n.delivered is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_batch(self):
        from codecustodian.integrations.teams_chatops import TeamsConnector

        config = ChatOpsConfig(enabled=True, teams_webhook_url="https://webhook.example.com")
        connector = TeamsConnector(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        connector._client = mock_client

        notifications = [
            ChatOpsNotification(message_type="scan_complete", payload={"total_findings": 1, "critical": 0, "high": 0}),
            ChatOpsNotification(message_type="pr_created", payload={"pr_url": "x", "pr_title": "t", "finding_count": 1, "confidence": 8}),
        ]
        results = await connector.send_batch(notifications)
        assert results == [True, True]
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_close(self):
        from codecustodian.integrations.teams_chatops import TeamsConnector

        config = ChatOpsConfig(enabled=True)
        connector = TeamsConnector(config=config)
        mock_client = AsyncMock()
        connector._client = mock_client
        await connector.close()
        mock_client.aclose.assert_called_once()
        assert connector._client is None


# ═══════════════════════════════════════════════════════════════════════════
# MCP Cache — migrations
# ═══════════════════════════════════════════════════════════════════════════


class TestCacheMigrations:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        from codecustodian.mcp.cache import ScanCache

        cache = ScanCache()
        plan = MigrationPlan(framework="flask", from_version="2", to_version="3")
        await cache.store_migration(plan.id, plan)
        retrieved = await cache.get_migration(plan.id)
        assert retrieved is not None
        assert retrieved.framework == "flask"

    @pytest.mark.asyncio
    async def test_list_migrations(self):
        from codecustodian.mcp.cache import ScanCache

        cache = ScanCache()
        p1 = MigrationPlan(framework="flask", from_version="2", to_version="3")
        p2 = MigrationPlan(framework="django", from_version="3", to_version="4")
        await cache.store_migration(p1.id, p1)
        await cache.store_migration(p2.id, p2)
        plans = await cache.list_migrations()
        assert len(plans) == 2

    @pytest.mark.asyncio
    async def test_stats_includes_migrations(self):
        from codecustodian.mcp.cache import ScanCache

        cache = ScanCache()
        plan = MigrationPlan(framework="x", from_version="1", to_version="2")
        await cache.store_migration(plan.id, plan)
        stats = await cache.stats()
        assert "migrations" in stats
        assert stats["migrations"] == 1

    @pytest.mark.asyncio
    async def test_clear_includes_migrations(self):
        from codecustodian.mcp.cache import ScanCache

        cache = ScanCache()
        plan = MigrationPlan(framework="x", from_version="1", to_version="2")
        await cache.store_migration(plan.id, plan)
        await cache.clear()
        plans = await cache.list_migrations()
        assert len(plans) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Agent profiles (v0.15.0)
# ═══════════════════════════════════════════════════════════════════════════


class TestV15Agents:
    def test_test_synthesizer_profile(self):
        from codecustodian.planner.agents import AGENT_REGISTRY

        profile = AGENT_REGISTRY["test-synthesizer"]
        assert profile.model_preference == "fast"
        assert "test-synthesis" in profile.skill_names
        assert profile.tool_filter is not None
        assert "run_pytest_subset" in profile.tool_filter

    def test_migration_engineer_profile(self):
        from codecustodian.planner.agents import AGENT_REGISTRY

        profile = AGENT_REGISTRY["migration-engineer"]
        assert profile.model_preference == "reasoning"
        assert "framework-migrations" in profile.skill_names

    def test_notification_composer_profile(self):
        from codecustodian.planner.agents import AGENT_REGISTRY

        profile = AGENT_REGISTRY["notification-composer"]
        assert profile.model_preference == "fast"
        assert "chatops-delivery" in profile.skill_names


# ═══════════════════════════════════════════════════════════════════════════
# SKILL.md files exist
# ═══════════════════════════════════════════════════════════════════════════


class TestV15Skills:
    def test_skill_files_exist(self):
        from pathlib import Path

        skills_dir = Path(".copilot_skills")
        for name in ("test-synthesis", "framework-migrations", "chatops-delivery"):
            skill_file = skills_dir / name / "SKILL.md"
            assert skill_file.exists(), f"Missing {skill_file}"
