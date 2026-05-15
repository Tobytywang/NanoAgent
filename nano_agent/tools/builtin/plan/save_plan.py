"""
Save plan tool for saving execution plans to files.
"""

from ...base import BaseTool, ToolResult
from .. import plan_helpers
from ....agent.types import RiskLevel, Plan, PlanPhase


class SavePlanTool(BaseTool):
    """Save plan to file."""

    name = "save_plan"
    description = "将计划保存到 .nano_agent/plans/ 目录"
    risk_level = RiskLevel.MODERATE  # Write operation

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "plan_name": {
                    "type": "string",
                    "description": "计划名称"
                },
                "task": {
                    "type": "string",
                    "description": "任务描述"
                },
                "analysis": {
                    "type": "string",
                    "description": "任务分析"
                },
                "phases": {
                    "type": "array",
                    "description": "实现阶段",
                    "items": {
                        "type": "object",
                        "properties": {
                            "version": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                },
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "风险与约束"
                }
            },
            "required": ["plan_name", "task", "analysis", "phases"]
        }

    def execute(self, **kwargs) -> ToolResult:
        plan_name = kwargs.get("plan_name", "unnamed-plan")
        task = kwargs.get("task", "")
        analysis = kwargs.get("analysis", "")
        phases_data = kwargs.get("phases", [])
        risks = kwargs.get("risks", [])

        # Build phases
        phases = [
            PlanPhase(
                version=p.get("version", ""),
                description=p.get("description", "")
            )
            for p in phases_data
        ]

        plan = Plan(
            name=plan_name,
            task=task,
            analysis=analysis,
            phases=phases,
            risks=risks
        )

        # Save to file
        plan_helpers._ensure_plans_dir()
        slug = plan_helpers._slugify(plan_name)
        plan_file = plan_helpers.PLANS_DIR / f"{slug}.md"
        plan_file.write_text(plan_helpers.plan_to_markdown(plan), encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"计划已保存到 {plan_file}"
        )
