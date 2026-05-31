"""
Prompt 模块定义

每个模块包含:
- name: 模块名称
- description: 模块描述
- content: 模块内容模板
- priority: 优先级（数值越小越靠前）
- always_on: 是否始终启用
- token_estimate: 预估 token 数
- is_stable: 是否属于稳定部分（用于 LLM API 缓存优化）
- category: 模块分类（core/efficiency/security/output/context/memory）
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
    is_stable: bool = True  # 是否属于稳定部分（适合缓存）
    category: str = "core"  # 模块分类


# 预定义模块
MODULES = {
    # ============ 基础模块 (priority 10-19) ============
    "core": PromptModule(
        name="core",
        description="核心工作循环",
        content="""You are an intelligent assistant that can use tools.

## Work Cycle
Think -> Act -> Observe -> Repeat until done.

## Confidence Assessment
After each thought, assess your confidence (0.0-1.0):
- 0.9+: Can answer definitively without more tools
- 0.7-0.9: Likely can answer, but may need verification
- 0.5-0.7: Need more information
- <0.5: Significant uncertainty, must gather more data

When confident (0.8+), provide your answer directly.""",
        priority=10,
        always_on=True,
        token_estimate=80,
        enabled=True,
        is_stable=True,
        category="core",
    ),

    "tools": PromptModule(
        name="tools",
        description="工具描述占位符",
        content="## Tools\n{tools_description}",
        priority=11,
        always_on=True,
        token_estimate=0,  # 动态计算
        enabled=True,
        is_stable=True,
        category="core",
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
        is_stable=True,
        category="efficiency",
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
        is_stable=True,
        category="efficiency",
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
        is_stable=True,
        category="security",
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
        is_stable=True,
        category="security",
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
        is_stable=True,
        category="security",
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
        is_stable=True,
        category="output",
    ),

    "aggressive_output": PromptModule(
        name="aggressive_output",
        description="激进输出简化",
        content="",  # Dynamic content based on level
        priority=41,
        always_on=False,
        token_estimate=40,
        enabled=False,
        is_stable=True,
        category="output",
    ),

    "language": PromptModule(
        name="language",
        description="语言设置",
        content="Respond in user's language.",
        priority=99,  # 放在最后
        always_on=True,
        token_estimate=10,
        enabled=True,
        is_stable=True,
        category="output",
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
        is_stable=False,  # 动态内容，不适合缓存
        category="context",
    ),

    "git_status": PromptModule(
        name="git_status",
        description="Git 状态（动态）",
        content="",  # 动态生成
        priority=51,
        always_on=False,
        token_estimate=80,
        enabled=False,
        is_stable=False,  # 动态内容，不适合缓存
        category="context",
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
        is_stable=True,
        category="memory",
    ),
}


# Aggressive output content templates (v0.7.15)
AGGRESSIVE_OUTPUT_CONTENTS = {
    "mild": """## Output Constraints
- No emojis unless explicitly requested
- Keep responses to 2-3 sentences maximum
- No Markdown tables; use inline descriptions
- Reference: file_path:line_number""",
    "aggressive": """## Output Constraints
- Respond in exactly ONE sentence
- No emojis, no Markdown formatting
- No tables, no bullet lists, no numbered lists
- If multiple points needed, use semicolons in one sentence
- Reference: file_path:line_number""",
    "extreme": """## Output Constraints
- Respond in ONE short sentence (under 50 chars if possible)
- No formatting of any kind
- No explanations unless explicitly asked
- Single word answers when possible""",
}


# Style 预设配置
STYLE_PRESETS = {
    "concise": {
        "description": "简洁模式 (~150 tokens)",
        "modules": ["core", "tools", "output_style", "language"],
        "token_budget": 200,
    },
    "standard": {
        "description": "标准模式 (~800 tokens)",
        "modules": ["core", "tools", "efficiency", "modification", "constitution", "risk_awareness", "output_style", "language"],
        "token_budget": 1000,
    },
    "detailed": {
        "description": "详细模式 (~1500 tokens)",
        "modules": ["core", "tools", "efficiency", "modification", "constitution", "risk_awareness", "security_rules", "output_style", "memory_guide", "language"],
        "token_budget": 2000,
    },
}
