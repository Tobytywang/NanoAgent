"""
Load plan tool for loading execution plans from files.
"""

from ...base import BaseTool, ToolResult
from .. import plan_helpers
from ....agent.types import RiskLevel


class LoadPlanTool(BaseTool):
    """Load plan from file."""

    name = "load_plan"
    description = "从文件加载计划"
    risk_level = RiskLevel.SAFE  # Read-only operation

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "plan_name": {
                    "type": "string",
                    "description": "计划名称或文件名"
                }
            },
            "required": ["plan_name"]
        }

    def execute(self, **kwargs) -> ToolResult:
        plan_name = kwargs.get("plan_name", "")

        # Try to find the plan file
        slug = plan_helpers._slugify(plan_name)
        plan_file = plan_helpers.PLANS_DIR / f"{slug}.md"

        if not plan_file.exists():
            # Try exact name
            plan_file = plan_helpers.PLANS_DIR / f"{plan_name}.md"

        if not plan_file.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"未找到计划: {plan_name}"
            )

        try:
            content = plan_file.read_text(encoding="utf-8")
            plan = plan_helpers.markdown_to_plan(content, plan_file.stem)

            # Format output
            lines = [
                f"# {plan.name}",
                f"状态: {plan.status}",
                f"创建时间: {plan.created_at}",
                "",
                "## 任务描述",
                plan.task,
                "",
                "## 分析",
                plan.analysis,
                "",
                "## 实现阶段",
            ]
            for i, phase in enumerate(plan.phases, 1):
                status_mark = "✅" if phase.status == "completed" else "⬜"
                lines.append(f"  {i}. {status_mark} {phase.version} - {phase.description}")

            if plan.risks:
                lines.extend(["", "## 风险与约束"])
                for risk in plan.risks:
                    lines.append(f"  - {risk}")

            return ToolResult(
                success=True,
                output="\n".join(lines),
                metadata={"plan": plan}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"加载计划失败: {e}"
            )
