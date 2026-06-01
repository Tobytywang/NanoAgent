"""
名称提取模式

用于从文本中提取用户名和 Agent 名的正则表达式模式。
"""

# 用户名模式（明确引用用户）
USER_NAME_PATTERNS = [
    r"用户名[是为]\s*([^，。！,.]+)",
    r"用户的名字[是为]\s*([^，。！,.]+)",
    r"用户叫\s*([^，。！,.]+)",
]

# Agent 名模式（自我引用或用户称呼 Agent）
# 注意：memorize 内容由 Agent (LLM) 生成，所以：
# - "我的名字" 指的是 Agent 的名字
# - "用户的名字" 指的是用户的名字
AGENT_NAME_PATTERNS = [
    r"Agent名[是为]\s*([^，。！,.]+)",
    r"Agent的名字[是为]\s*([^，。！,.]+)",
    r"你的名字[是为叫]\s*([^，。！,.]+)",
    r"你叫\s*([^，。！,.]+)",
    r"我的名字[是为]\s*([^，。！,.]+)",
    r"我叫\s*([^，。！,.]+)",
]


def extract_name_from_patterns(content: str, patterns: list[str]) -> str | None:
    """
    使用模式列表从内容中提取名称。

    Args:
        content: 要搜索的内容
        patterns: 正则表达式模式列表

    Returns:
        提取的名称，如果没有匹配则返回 None
    """
    import re

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()
    return None
