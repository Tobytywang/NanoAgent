"""
Plan mode implementation.

Provides an interactive planning mode where users can create, refine,
and save execution plans before actual execution.

Design for evolution:
- PlanMode is a pure logic class (no I/O)
- I/O is handled by caller (CLI for now, future: independent agent)
- Uses EventEmitter for extensibility
"""

import re
from typing import TYPE_CHECKING, Callable

from ..agent.types import Plan, PlanPhase
from ..agent.events import EventEmitter
from ..tools.builtin.plan_tools import (
    _ensure_plans_dir,
    _slugify,
    plan_to_markdown,
    PLANS_DIR,
)

if TYPE_CHECKING:
    from ..llm.base import BaseLLM
    from ..config.schema import Config


PLAN_PROMPT = """分析以下任务，制定分阶段实现计划。

任务：{task}

请按以下格式输出：
---
计划名称: [简洁的计划名称]
任务分析: [分析任务目标和约束]
实现阶段:
- 阶段一: [描述] (v0.x.x)
- 阶段二: [描述] (v0.x.x)
...
风险与约束: [列出潜在风险，用逗号分隔]
---

注意：
1. 计划名称要简洁，用于文件命名
2. 版本号要合理递增
3. 每个阶段要明确具体
"""

ADJUST_PROMPT = """当前计划：
{current_plan}

用户反馈：{feedback}

请根据反馈调整计划，保持相同格式输出。只输出调整后的计划，不要解释。
"""


class PlanMode:
    """
    规划模式：只规划不执行。

    Design for evolution:
    - Core logic is I/O free
    - Communication via EventEmitter
    - Can be wrapped by CLI or independent agent

    Events emitted:
    - "plan_generated": When a new plan is generated
    - "plan_adjusted": When plan is adjusted
    - "plan_saved": When plan is saved to file
    """

    def __init__(
        self, llm: "BaseLLM", config: "Config", events: EventEmitter | None = None
    ):
        self.llm = llm
        self.config = config
        self.events = events or EventEmitter()
        self.current_plan: Plan | None = None

    def generate_plan(self, task: str) -> Plan:
        """
        Generate initial plan for a task.

        Args:
            task: Task description

        Returns:
            Generated Plan
        """
        prompt = PLAN_PROMPT.format(task=task)
        response, _, _ = self.llm.chat(
            messages=[{"role": "user", "content": prompt}], tools=None
        )
        self.current_plan = self._parse_plan_response(response, task)
        self.events.emit("plan_generated", {"plan": self.current_plan})
        return self.current_plan

    def adjust_plan(self, feedback: str) -> Plan:
        """
        Adjust current plan based on feedback.

        Args:
            feedback: User feedback

        Returns:
            Adjusted Plan
        """
        if not self.current_plan:
            raise ValueError("No plan to adjust. Call generate_plan() first.")

        current_plan_text = self._plan_to_text(self.current_plan)
        prompt = ADJUST_PROMPT.format(current_plan=current_plan_text, feedback=feedback)
        response, _, _ = self.llm.chat(
            messages=[{"role": "user", "content": prompt}], tools=None
        )
        self.current_plan = self._parse_plan_response(response, self.current_plan.task)
        self.events.emit("plan_adjusted", {"plan": self.current_plan})
        return self.current_plan

    def save_plan(self) -> str:
        """
        Save current plan to file.

        Returns:
            File path of saved plan
        """
        if not self.current_plan:
            raise ValueError("No plan to save.")

        _ensure_plans_dir()
        slug = _slugify(self.current_plan.name)
        plan_file = PLANS_DIR / f"{slug}.md"
        plan_file.write_text(plan_to_markdown(self.current_plan), encoding="utf-8")

        self.events.emit(
            "plan_saved", {"plan": self.current_plan, "path": str(plan_file)}
        )
        return str(plan_file)

    def _parse_plan_response(self, response: str, original_task: str) -> Plan:
        """解析 LLM 返回的计划。"""
        # Extract plan name
        name = "unnamed-plan"
        name_match = re.search(r"计划名称[：:]\s*(.+)", response)
        if name_match:
            name = name_match.group(1).strip()

        # Extract analysis
        analysis = ""
        analysis_match = re.search(
            r"任务分析[：:]\s*(.+?)(?=\n实现阶段|\n风险|\n---|$)", response, re.DOTALL
        )
        if analysis_match:
            analysis = analysis_match.group(1).strip()

        # Extract phases
        phases = []
        phase_pattern = r"-\s*阶段[^:]*[：:]\s*(.+?)\s*\((v[\d.]+)\)"
        for match in re.finditer(phase_pattern, response):
            description = match.group(1).strip()
            version = match.group(2).strip()
            phases.append(PlanPhase(version=version, description=description))

        # If no phases found with pattern, try simpler extraction
        if not phases:
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("- ") and "v0" in line:
                    parts = line[2:].split("(")
                    if len(parts) == 2:
                        desc = parts[0].strip()
                        version = parts[1].rstrip(")").strip()
                        phases.append(PlanPhase(version=version, description=desc))

        # Extract risks
        risks = []
        risks_match = re.search(
            r"风险与约束[：:]\s*(.+?)(?=\n---|\n##|$)", response, re.DOTALL
        )
        if risks_match:
            risks_text = risks_match.group(1).strip()
            for risk in re.split(r"[,\n]", risks_text):
                risk = risk.strip()
                if risk and not risk.startswith("-"):
                    risks.append(risk)

        return Plan(
            name=name, task=original_task, analysis=analysis, phases=phases, risks=risks
        )

    def _plan_to_text(self, plan: Plan) -> str:
        """将计划转换为文本格式。"""
        lines = [f"计划名称: {plan.name}", f"任务分析: {plan.analysis}", "实现阶段:"]
        for i, phase in enumerate(plan.phases, 1):
            lines.append(f"- 阶段{i}: {phase.description} ({phase.version})")
        if plan.risks:
            lines.append(f"风险与约束: {', '.join(plan.risks)}")
        return "\n".join(lines)


def run_plan_mode_interactive(
    llm: "BaseLLM",
    config: "Config",
    task: str,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
) -> str:
    """
    Run plan mode interactively (CLI wrapper).

    This is a convenience function for CLI usage.
    Future: Will be replaced by independent agent.

    Args:
        llm: LLM client
        config: Configuration
        task: Task description
        input_fn: Input function (default: input)
        print_fn: Print function (default: print)

    Returns:
        Result message
    """
    print_fn("\n" + "=" * 50)
    print_fn("进入规划模式（工具不会实际执行）")
    print_fn("输入 'done' 确认计划，'cancel' 取消")
    print_fn("=" * 50 + "\n")

    mode = PlanMode(llm, config)

    # Generate initial plan
    print_fn("正在分析任务...\n")
    mode.generate_plan(task)
    _display_plan(mode.current_plan, print_fn)

    # Multi-round adjustment
    while True:
        feedback = input_fn("\n您的反馈（或 'done'/'cancel'）: ").strip()

        if feedback.lower() == "done":
            path = mode.save_plan()
            return f"\n✅ 计划已保存到 {path}\n输入 `/start {mode.current_plan.name}` 开始执行第一阶段。"
        elif feedback.lower() == "cancel":
            return "\n已取消规划"
        elif feedback:
            print_fn("\n正在调整计划...\n")
            mode.adjust_plan(feedback)
            _display_plan(mode.current_plan, print_fn)

    return "\n已取消规划"


def _display_plan(plan: Plan | None, print_fn: Callable[[str], None] = print) -> None:
    """Display plan to user."""
    if not plan:
        return

    print_fn("─" * 40)
    print_fn(f"📋 计划: {plan.name}")
    print_fn("─" * 40)
    print_fn(f"\n📝 任务分析:")
    print_fn(f"   {plan.analysis}")

    print_fn(f"\n📊 实现阶段:")
    for i, phase in enumerate(plan.phases, 1):
        print_fn(f"   {i}. {phase.version} - {phase.description}")

    if plan.risks:
        print_fn(f"\n⚠️  风险与约束:")
        for risk in plan.risks:
            print_fn(f"   - {risk}")

    print_fn("─" * 40)


def list_plans() -> str:
    """列出所有已保存的计划。"""
    if not PLANS_DIR.exists():
        return "暂无计划。使用 /plan 命令创建新计划。"

    plan_files = list(PLANS_DIR.glob("*.md"))
    if not plan_files:
        return "暂无计划。使用 /plan 命令创建新计划。"

    from ..tools.builtin.plan_tools import markdown_to_plan

    lines = ["已保存的计划：\n"]
    for plan_file in sorted(plan_files):
        try:
            content = plan_file.read_text(encoding="utf-8")
            plan = markdown_to_plan(content, plan_file.stem)
            status_icon = {"planning": "📝", "executing": "🔄", "completed": "✅"}.get(
                plan.status, "❓"
            )
            lines.append(f"  {status_icon} {plan.name} ({plan.status})")
            if plan.phases:
                completed = sum(1 for p in plan.phases if p.status == "completed")
                lines.append(f"      {completed}/{len(plan.phases)} 阶段完成")
        except Exception:
            lines.append(f"  ❓ {plan_file.stem} (解析失败)")

    return "\n".join(lines)
