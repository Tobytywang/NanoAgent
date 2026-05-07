"""
Token estimation utilities.

Provides simple heuristic-based token counting for context management.
"""


def estimate_tokens(messages: list[dict]) -> int:
    """
    Estimate token count for a list of messages.

    Uses simple heuristics:
    - English: ~4 characters = 1 token
    - Chinese: ~1.5 characters = 1 token
    - Each message has ~4 tokens overhead (role, formatting)

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys

    Returns:
        Estimated total token count
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if not content:
            total += 4  # Message overhead even with empty content
            continue

        # Count Chinese characters (CJK range)
        chinese_chars = sum(1 for c in content if '一' <= c <= '鿿')

        # Count other characters
        other_chars = len(content) - chinese_chars

        # Token estimation
        # Chinese: ~1.5 chars per token (Chinese tokens are denser)
        # English/other: ~4 chars per token
        tokens = chinese_chars / 1.5 + other_chars / 4

        # Add message overhead (role, formatting, etc.)
        total += int(tokens) + 4

    return total


def estimate_text_tokens(text: str) -> int:
    """
    Estimate token count for a single text string.

    Args:
        text: Text string to estimate

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Count Chinese characters (CJK range)
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')

    # Count other characters
    other_chars = len(text) - chinese_chars

    # Token estimation
    tokens = chinese_chars / 1.5 + other_chars / 4

    return int(tokens)