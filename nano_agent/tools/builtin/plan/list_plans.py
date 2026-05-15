"""
List plans tool for listing all saved execution plans.
"""

from ...base import BaseTool, ToolResult
from .. import plan_helpers
from ....agent.types import RiskLevel


class ListPlansTool(BaseTool):
    """List all plans."""

    name = "list_plans"
    description = "列出 .nano_agent/plans/ 中的所有计划"
    risk_level = RiskLevel.SAFE  # Read-only operation

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        if not plan_helpers.PLANS_DIR.exists():
            return ToolResult(
                success=True,
                output="暂无计划。使用 /plan 命令创建新计划。"
            )

        plan_files = list(plan_helpers.PLANS_DIR.glob("*.md"))
        if not plan_files:
            return ToolResult(
                success=True,
                output="暂无计划。使用 /plan 命令创建新计划。"
            )

        lines = ["已保存的计划：", ""]
        for plan_file in sorted(plan_files):
            try:
                content = plan_file.read_text(encoding="utf-8")
                plan = plan_helpers.markdown_to_plan(content, plan_file.stem)
                status_icon = {
                    "planning": "📝",
                    "executing": "🔄",
                    "completed": "✅"
                }.get(plan.status, "❓")
                lines.append(f"  {status_icon} {plan.name} ({plan.status})")
                if plan.phases:
                    completed = sum(1 for p in plan.phases if p.status == "completed")
                    lines.append(f"      {completed}/{len(plan.phases)} 阶段完成")
            except Exception:
                lines.append(f"  ❓ {plan_file.stem} (解析失败)")

        return ToolResult(success=True, output="\n".join(lines))
