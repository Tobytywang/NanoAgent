"""
Plan file helper functions.

Helper functions for saving, loading, and listing plans in .nano_agent/plans/ directory.
Used by CLI plan mode, not registered as agent tools.
"""

import re
from pathlib import Path

from ...agent.types import Plan, PlanPhase


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
