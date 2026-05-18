"""
Prompt 模块定义

每个模块包含:
- name: 模块名称
- description: 模块描述
- content: 模块内容模板
- priority: 优先级（数值越小越靠前）
- always_on: 是否始终启用
- token_estimate: 预估 token 数
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class PromptModule:
    """Prompt 模块定义"""
    name: str
    description: str
    content: str
    priority: int = 50
    always_on: bool = False
    token_estimate: int = 0
    enabled: bool = True


# 预定义模块
MODULES = {
    # ============ 基础模块 (priority 10-19) ============
    "core": PromptModule(
        name="core",
        description="核心工作循环",
        content="""You are an intelligent assistant that can use tools.

## Work Cycle
Think -> Act -> Observe -> Repeat until done.""",
        priority=10,
        always_on=True,
        token_estimate=50,
        enabled=True,
    ),

    "tools": PromptModule(
        name="tools",
        description="工具描述占位符",
        content="## Tools\n{tools_description}",
        priority=11,
        always_on=True,
        token_estimate=0,  # 动态计算
        enabled=True,
    ),

    # ============ 效率模块 (priority 20-29) ============
    "efficiency": PromptModule(
        name="efficiency",
        description="Token 效率规则",
        content="""## Efficiency Rules
1. Minimize iterations (aim for 2-3)
2. Batch tool calls when possible
3. Stop when you have the answer
4. Simple questions = simple answers""",
        priority=20,
        always_on=False,
        token_estimate=50,
        enabled=True,
    ),

    "modification": PromptModule(
        name="modification",
        description="修改约束",
        content="""## Modification Constraints
1. Only modify what's relevant
2. Don't refactor beyond request
3. One file at a time
4. Ask before expanding scope""",
        priority=21,
        always_on=False,
        token_estimate=40,
        enabled=True,
    ),

    # ============ 安全模块 (priority 30-39) ============
    "constitution": PromptModule(
        name="constitution",
        description="AI 行为准则",
        content="""## Security Guidelines
1. Assist security testing only with explicit authorization
2. Refuse malicious requests (DoS, mass targeting, etc.)
3. Never generate URLs unless confident they help with programming""",
        priority=30,
        always_on=False,
        token_estimate=50,
        enabled=True,
    ),

    "risk_awareness": PromptModule(
        name="risk_awareness",
        description="风险意识",
        content="""## Risk Awareness
Before dangerous operations:
- Can this be undone?
- What else is affected?
- Should I ask first?

High-risk: delete, force-push, CI changes, external messages
Safe: read, test, edit local files""",
        priority=31,
        always_on=False,
        token_estimate=60,
        enabled=True,
    ),

    "security_rules": PromptModule(
        name="security_rules",
        description="代码安全规则",
        content="""## Security Rules
Prevent vulnerabilities:
- Command injection → validate inputs
- XSS → escape content
- SQL injection → parameterized queries
- Path traversal → validate paths
- No hardcoded secrets""",
        priority=32,
        always_on=False,
        token_estimate=50,
        enabled=True,
    ),

    # ============ 输出模块 (priority 40-49) ============
    "output_style": PromptModule(
        name="output_style",
        description="输出风格",
        content="""## Output Style
- No emojis unless requested
- Keep responses concise
- Reference: file_path:line_number
- End with 1-2 sentences""",
        priority=40,
        always_on=False,
        token_estimate=30,
        enabled=True,
    ),

    "language": PromptModule(
        name="language",
        description="语言设置",
        content="Respond in user's language.",
        priority=99,  # 放在最后
        always_on=True,
        token_estimate=10,
        enabled=True,
    ),

    # ============ 上下文模块 (priority 50-59) ============
    "environment": PromptModule(
        name="environment",
        description="运行环境（动态）",
        content="",  # 动态生成
        priority=50,
        always_on=False,
        token_estimate=50,
        enabled=False,
    ),

    "git_status": PromptModule(
        name="git_status",
        description="Git 状态（动态）",
        content="",  # 动态生成
        priority=51,
        always_on=False,
        token_estimate=80,
        enabled=False,
    ),

    # ============ 记忆模块 (priority 60-69) ============
    "memory_guide": PromptModule(
        name="memory_guide",
        description="记忆系统指导",
        content="""## Memory System
Use `memorize` tool to store important information:
- User preferences
- Project context
- Important decisions

Use `recall` tool to retrieve stored memories.""",
        priority=60,
        always_on=False,
        token_estimate=50,
        enabled=True,
    ),
}


# Style 预设配置
STYLE_PRESETS = {
    "concise": {
        "description": "简洁模式 (~150 tokens)",
        "modules": ["core", "tools", "language"],
        "token_budget": 200,
    },
    "standard": {
        "description": "标准模式 (~800 tokens)",
        "modules": ["core", "tools", "efficiency", "modification", "constitution", "risk_awareness", "language"],
        "token_budget": 1000,
    },
    "detailed": {
        "description": "详细模式 (~1500 tokens)",
        "modules": ["core", "tools", "efficiency", "modification", "constitution", "risk_awareness", "security_rules", "output_style", "memory_guide", "language"],
        "token_budget": 2000,
    },
}
