"""
Plan file operations.

Tools for saving, loading, and listing plans in .nano_agent/plans/ directory.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from ...agent.types import Plan, PlanPhase
from ..base import BaseTool, ToolResult


PLANS_DIR = Path(".nano_agent/plans")


def _ensure_plans_dir() -> Path:
    """Ensure plans directory exists."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    return PLANS_DIR


def _slugify(name: str) -> str:
    """Convert plan name to filename-safe slug."""
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-') or 'plan'


def plan_to_markdown(plan: Plan) -> str:
    """Convert Plan to Markdown format."""
    lines = [
        f"# {plan.name}",
        "",
        f"**创建时间**: {plan.created_at}",
        f"**状态**: {plan.status}",
        "",
        "## 任务描述",
        plan.task,
        "",
        "## 分析",
        plan.analysis,
        "",
        "## 实现阶段",
    ]

    for phase in plan.phases:
        checkbox = "[x]" if phase.status == "completed" else "[ ]"
        lines.append(f"- {checkbox} {phase.version} - {phase.description}")

    if plan.risks:
        lines.extend(["", "## 风险与约束"])
        for risk in plan.risks:
            lines.append(f"- {risk}")

    lines.extend([
        "",
        "## 执行进度",
        "",
        "## 变更历史",
        f"- {plan.created_at}: 创建计划",
    ])

    return "\n".join(lines)


def markdown_to_plan(content: str, filename: str) -> Plan:
    """Parse Markdown content to Plan."""
    lines = content.split("\n")

    # Extract name from first heading
    name = filename
    for line in lines:
        if line.startswith("# "):
            name = line[2:].strip()
            break

    # Extract status
    status = "planning"
    for line in lines:
        if line.startswith("**状态**:"):
            status = line.split(":", 1)[1].strip()
            break

    # Extract created_at
    created_at = ""
    for line in lines:
        if line.startswith("**创建时间**:"):
            created_at = line.split(":", 1)[1].strip()
            break

    # Extract sections
    def extract_section(section_name: str) -> str:
        in_section = False
        section_lines = []
        for line in lines:
            if line.startswith(f"## {section_name}"):
                in_section = True
                continue
            if in_section:
                if line.startswith("## "):
                    break
                section_lines.append(line)
        return "\n".join(section_lines).strip()

    task = extract_section("任务描述")
    analysis = extract_section("分析")

    # Extract phases
    phases = []
    in_phases = False
    for line in lines:
        if line.startswith("## 实现阶段"):
            in_phases = True
            continue
        if in_phases:
            if line.startswith("## "):
                break
            if line.startswith("- ["):
                # Parse: - [ ] v0.7.0 - Description
                match = re.match(r'- \[([ x])\] (\S+) - (.+)', line)
                if match:
                    checked, version, desc = match.groups()
                    phase_status = "completed" if checked == "x" else "pending"
                    phases.append(PlanPhase(
                        version=version,
                        description=desc.strip(),
                        status=phase_status
                    ))

    # Extract risks
    risks = []
    in_risks = False
    for line in lines:
        if line.startswith("## 风险与约束"):
            in_risks = True
            continue
        if in_risks:
            if line.startswith("## "):
                break
            if line.startswith("- "):
                risks.append(line[2:].strip())

    return Plan(
        name=name,
        task=task,
        analysis=analysis,
        phases=phases,
        risks=risks,
        created_at=created_at,
        status=status
    )


class SavePlanTool(BaseTool):
    """Save plan to file."""

    name = "save_plan"
    description = "将计划保存到 .nano_agent/plans/ 目录"

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
        _ensure_plans_dir()
        slug = _slugify(plan_name)
        plan_file = PLANS_DIR / f"{slug}.md"
        plan_file.write_text(plan_to_markdown(plan), encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"计划已保存到 {plan_file}"
        )


class ListPlansTool(BaseTool):
    """List all plans."""

    name = "list_plans"
    description = "列出 .nano_agent/plans/ 中的所有计划"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self, **kwargs) -> ToolResult:
        if not PLANS_DIR.exists():
            return ToolResult(
                success=True,
                output="暂无计划。使用 /plan 命令创建新计划。"
            )

        plan_files = list(PLANS_DIR.glob("*.md"))
        if not plan_files:
            return ToolResult(
                success=True,
                output="暂无计划。使用 /plan 命令创建新计划。"
            )

        lines = ["已保存的计划：", ""]
        for plan_file in sorted(plan_files):
            try:
                content = plan_file.read_text(encoding="utf-8")
                plan = markdown_to_plan(content, plan_file.stem)
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


class LoadPlanTool(BaseTool):
    """Load plan from file."""

    name = "load_plan"
    description = "从文件加载计划"

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
        slug = _slugify(plan_name)
        plan_file = PLANS_DIR / f"{slug}.md"

        if not plan_file.exists():
            # Try exact name
            plan_file = PLANS_DIR / f"{plan_name}.md"

        if not plan_file.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"未找到计划: {plan_name}"
            )

        try:
            content = plan_file.read_text(encoding="utf-8")
            plan = markdown_to_plan(content, plan_file.stem)

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
