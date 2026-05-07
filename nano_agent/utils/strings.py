"""
字符串工具函数
"""


def safe_str(text: str) -> str:
    """
    安全地将字符串转换为可打印格式，移除无效的 Unicode 字符。

    Args:
        text: 输入字符串

    Returns:
        处理后的安全字符串
    """
    if not text:
        return text
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text
