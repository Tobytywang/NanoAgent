"""
Tests for v0.6.2 plan mode: Plan types, plan tools, and plan mode.
"""

import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import tempfile
import os

from nano_agent.agent import Plan, PlanPhase
from nano_agent.tools.builtin.plan_tools import (
    plan_to_markdown,
    markdown_to_plan,
    _slugify,
    SavePlanTool,
    ListPlansTool,
    LoadPlanTool,
    PLANS_DIR,
)


class TestPlanTypes:
    """Tests for Plan and PlanPhase dataclasses."""

    def test_create_plan_phase(self):
        """Test creating a plan phase."""
        phase = PlanPhase(
            version="v0.7.0", description="Implement basic features", status="pending"
        )
        assert phase.version == "v0.7.0"
        assert phase.description == "Implement basic features"
        assert phase.status == "pending"

    def test_create_plan(self):
        """Test creating a plan."""
        phases = [
            PlanPhase(version="v0.7.0", description="Phase 1"),
            PlanPhase(version="v0.7.1", description="Phase 2"),
        ]
        plan = Plan(
            name="test-plan",
            task="Build a test system",
            analysis="Need to build a comprehensive test system",
            phases=phases,
            risks=["Time constraint", "Resource limitation"],
        )
        assert plan.name == "test-plan"
        assert plan.task == "Build a test system"
        assert len(plan.phases) == 2
        assert len(plan.risks) == 2
        assert plan.status == "planning"
        assert plan.created_at  # Should be auto-generated

    def test_plan_default_values(self):
        """Test plan default values."""
        plan = Plan(name="minimal", task="Task", analysis="Analysis", phases=[])
        assert plan.risks == []
        assert plan.status == "planning"


class TestSlugify:
    """Tests for slugify function."""

    def test_simple_name(self):
        """Test simple name conversion."""
        assert _slugify("Test Plan") == "test-plan"

    def test_special_chars(self):
        """Test special character removal."""
        assert _slugify("Test@Plan#123") == "testplan123"

    def test_multiple_spaces(self):
        """Test multiple spaces handling."""
        assert _slugify("Test   Plan") == "test-plan"

    def test_chinese_name(self):
        """Test Chinese name handling."""
        # Chinese characters are kept
        slug = _slugify("测试计划")
        assert "测试计划" in slug or slug == "plan"


class TestPlanMarkdown:
    """Tests for plan Markdown conversion."""

    def test_plan_to_markdown(self):
        """Test converting plan to Markdown."""
        plan = Plan(
            name="Test Plan",
            task="Build a test system",
            analysis="Need comprehensive testing",
            phases=[
                PlanPhase(version="v0.7.0", description="Phase 1"),
                PlanPhase(version="v0.7.1", description="Phase 2", status="completed"),
            ],
            risks=["Risk 1", "Risk 2"],
            created_at="2026-05-07 10:00",
        )

        md = plan_to_markdown(plan)

        assert "# Test Plan" in md
        assert "**创建时间**: 2026-05-07 10:00" in md
        assert "**状态**: planning" in md
        assert "## 任务描述" in md
        assert "Build a test system" in md
        assert "## 分析" in md
        assert "## 实现阶段" in md
        assert "- [ ] v0.7.0 - Phase 1" in md
        assert "- [x] v0.7.1 - Phase 2" in md
        assert "## 风险与约束" in md
        assert "- Risk 1" in md

    def test_markdown_to_plan(self):
        """Test parsing Markdown to plan."""
        md = """# Test Plan

**创建时间**: 2026-05-07 10:00
**状态**: executing

## 任务描述
Build a test system

## 分析
Need comprehensive testing

## 实现阶段
- [ ] v0.7.0 - Phase 1
- [x] v0.7.1 - Phase 2

## 风险与约束
- Risk 1
- Risk 2

## 执行进度

## 变更历史
- 2026-05-07 10:00: 创建计划
"""
        plan = markdown_to_plan(md, "test-plan")

        assert plan.name == "Test Plan"
        assert plan.status == "executing"
        assert plan.task == "Build a test system"
        assert plan.analysis == "Need comprehensive testing"
        assert len(plan.phases) == 2
        assert plan.phases[0].version == "v0.7.0"
        assert plan.phases[0].status == "pending"
        assert plan.phases[1].status == "completed"
        assert len(plan.risks) == 2

    def test_roundtrip_conversion(self):
        """Test roundtrip conversion."""
        original = Plan(
            name="Roundtrip Test",
            task="Test roundtrip",
            analysis="Analysis text",
            phases=[
                PlanPhase(version="v0.7.0", description="Phase 1"),
            ],
            risks=["Risk"],
            created_at="2026-05-07 12:00",
        )

        md = plan_to_markdown(original)
        parsed = markdown_to_plan(md, "roundtrip-test")

        assert parsed.name == original.name
        assert parsed.task == original.task
        assert parsed.analysis == original.analysis
        assert len(parsed.phases) == len(original.phases)


class TestPlanTools:
    """Tests for plan tools."""

    def test_save_plan_tool(self, tmp_path):
        """Test saving a plan."""
        # Override PLANS_DIR for testing
        import nano_agent.tools.builtin.plan_tools as plan_tools

        original_dir = plan_tools.PLANS_DIR
        plan_tools.PLANS_DIR = tmp_path / "plans"

        try:
            tool = SavePlanTool()
            result = tool.execute(
                plan_name="Test Plan",
                task="Build something",
                analysis="Need to build",
                phases=[{"version": "v0.7.0", "description": "Phase 1"}],
                risks=["Risk 1"],
            )

            assert result.success is True
            assert "test-plan.md" in result.output

            # Verify file was created
            plan_file = plan_tools.PLANS_DIR / "test-plan.md"
            assert plan_file.exists()
        finally:
            plan_tools.PLANS_DIR = original_dir

    def test_list_plans_tool_empty(self, tmp_path):
        """Test listing plans when empty."""
        import nano_agent.tools.builtin.plan_tools as plan_tools

        original_dir = plan_tools.PLANS_DIR
        plan_tools.PLANS_DIR = tmp_path / "empty_plans"

        try:
            tool = ListPlansTool()
            result = tool.execute()

            assert result.success is True
            assert "暂无计划" in result.output
        finally:
            plan_tools.PLANS_DIR = original_dir

    def test_load_plan_tool(self, tmp_path):
        """Test loading a plan."""
        import nano_agent.tools.builtin.plan_tools as plan_tools

        original_dir = plan_tools.PLANS_DIR
        plan_tools.PLANS_DIR = tmp_path / "plans"

        try:
            # First save a plan
            save_tool = SavePlanTool()
            save_tool.execute(
                plan_name="Load Test",
                task="Test loading",
                analysis="Analysis",
                phases=[{"version": "v0.7.0", "description": "Phase"}],
            )

            # Then load it
            load_tool = LoadPlanTool()
            result = load_tool.execute(plan_name="load-test")

            assert result.success is True
            assert "Load Test" in result.output
        finally:
            plan_tools.PLANS_DIR = original_dir

    def test_load_nonexistent_plan(self, tmp_path):
        """Test loading a plan that doesn't exist."""
        import nano_agent.tools.builtin.plan_tools as plan_tools

        original_dir = plan_tools.PLANS_DIR
        plan_tools.PLANS_DIR = tmp_path / "plans"

        try:
            tool = LoadPlanTool()
            result = tool.execute(plan_name="nonexistent")

            assert result.success is False
            assert "未找到计划" in result.error
        finally:
            plan_tools.PLANS_DIR = original_dir


class TestPlanMode:
    """Tests for PlanMode class."""

    def test_plan_mode_initialization(self):
        """Test PlanMode initialization."""
        from nano_agent.cli.plan_mode import PlanMode

        llm = Mock()
        config = Mock()

        mode = PlanMode(llm, config)
        assert mode.llm is llm
        assert mode.config is config
        assert mode.current_plan is None
        assert mode.events is not None  # EventEmitter created

    def test_generate_plan(self):
        """Test generating initial plan."""
        from nano_agent.cli.plan_mode import PlanMode

        llm = Mock()
        llm.chat = Mock(
            return_value=(
                """计划名称: Test Plan
任务分析: This is a test analysis
实现阶段:
- 阶段一: Build core (v0.7.0)
- 阶段二: Add features (v0.7.1)
风险与约束: Time, Resources
""",
                [],
                Mock(total_tokens=100),
            )
        )

        config = Mock()
        mode = PlanMode(llm, config)

        plan = mode.generate_plan("Build a test system")

        assert plan.name == "Test Plan"
        assert plan.task == "Build a test system"
        assert len(plan.phases) == 2
        assert plan.phases[0].version == "v0.7.0"
        assert mode.current_plan is plan

    def test_adjust_plan(self):
        """Test adjusting plan based on feedback."""
        from nano_agent.cli.plan_mode import PlanMode

        llm = Mock()
        # First call for initial plan, second for adjustment
        llm.chat = Mock(
            side_effect=[
                (
                    """计划名称: Original
任务分析: Original analysis
实现阶段:
- 阶段一: Phase 1 (v0.7.0)
风险与约束: None
""",
                    [],
                    Mock(),
                ),
                (
                    """计划名称: Adjusted
任务分析: Adjusted analysis
实现阶段:
- 阶段一: Phase 1 (v0.7.0)
- 阶段二: Phase 2 (v0.7.1)
风险与约束: Time
""",
                    [],
                    Mock(),
                ),
            ]
        )

        config = Mock()
        mode = PlanMode(llm, config)

        # Generate initial
        mode.generate_plan("Test")
        # Adjust
        adjusted = mode.adjust_plan("Add more phases")

        assert adjusted.name == "Adjusted"
        assert len(adjusted.phases) == 2

    def test_save_plan(self):
        """Test saving plan."""
        from nano_agent.cli.plan_mode import PlanMode
        import tempfile
        import os

        # Use a temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch both modules
            import nano_agent.tools.builtin.plan_tools as plan_tools
            import nano_agent.cli.plan_mode as plan_mode

            original_tool_dir = plan_tools.PLANS_DIR
            original_mode_dir = plan_mode.PLANS_DIR

            plan_tools.PLANS_DIR = Path(tmpdir)
            plan_mode.PLANS_DIR = Path(tmpdir)

            try:
                llm = Mock()
                llm.chat = Mock(
                    return_value=(
                        """计划名称: Save Test
任务分析: Analysis
实现阶段:
- 阶段一: Phase 1 (v0.7.0)
风险与约束: None
""",
                        [],
                        Mock(),
                    )
                )

                config = Mock()
                mode = PlanMode(llm, Mock())
                mode.generate_plan("Test")

                path = mode.save_plan()

                assert "save-test.md" in path
                assert Path(path).exists()
            finally:
                plan_tools.PLANS_DIR = original_tool_dir
                plan_mode.PLANS_DIR = original_mode_dir

    def test_events_emitted(self):
        """Test that events are emitted."""
        from nano_agent.cli.plan_mode import PlanMode
        from nano_agent.agent.events import EventEmitter

        llm = Mock()
        llm.chat = Mock(
            return_value=(
                """计划名称: Event Test
任务分析: Analysis
实现阶段:
- 阶段一: Phase 1 (v0.7.0)
风险与约束: None
""",
                [],
                Mock(),
            )
        )

        events = EventEmitter()
        mode = PlanMode(llm, Mock(), events=events)

        # Track events
        emitted = []
        events.on("plan_generated", lambda e, d: emitted.append(("generated", d)))
        events.on("plan_adjusted", lambda e, d: emitted.append(("adjusted", d)))

        mode.generate_plan("Test")
        mode.adjust_plan("Change")

        assert len(emitted) == 2
        assert emitted[0][0] == "generated"
        assert emitted[1][0] == "adjusted"


class TestPlanParsing:
    """Tests for plan response parsing."""

    def test_parse_plan_response(self):
        """Test parsing LLM plan response."""
        from nano_agent.cli.plan_mode import PlanMode

        llm = Mock()
        config = Mock()
        mode = PlanMode(llm, config)

        response = """计划名称: Code Review System
任务分析: Need to build a comprehensive code review system with multiple stages.
实现阶段:
- 阶段一: Basic review (v0.7.0)
- 阶段二: Advanced features (v0.7.1)
- 阶段三: Integration (v0.7.2)
风险与约束: Time constraint, API changes
"""

        plan = mode._parse_plan_response(response, "Build code review")

        assert plan.name == "Code Review System"
        assert plan.task == "Build code review"
        assert len(plan.phases) == 3
        assert plan.phases[0].version == "v0.7.0"
        assert len(plan.risks) == 2
