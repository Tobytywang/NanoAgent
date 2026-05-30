"""
Context management for long conversations.

Implements a three-layer compression strategy:
1. Light cleanup: Remove expired temporary messages
2. Summary mark: Mark old messages as deletable, keep key messages
3. Model compression: Generate nine-section summary to replace messages
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory import BaseMemory


@dataclass
class NineSectionSummary:
    """
    Nine-section summary for context compression.

    This structure preserves key information when compressing long conversations.
    """
    user_request: str       # Original user request
    technical_concepts: str  # Technical concepts and decisions
    files_and_code: str      # Files and code involved
    errors_and_fixes: str    # Errors encountered and fixes applied
    problem_solving: str     # Problem-solving process
    user_messages: str       # Additional user messages
    pending_tasks: str       # Pending tasks
    current_work: str        # Current work status
    next_steps: str          # Next steps planned

    def to_message(self) -> dict:
        """
        Convert to system message format for context injection.

        Returns:
            Dictionary with role='system' and name='context_summary'
        """
        content = """## 对话摘要

### 用户请求
{user_request}

### 技术概念
{technical_concepts}

### 文件与代码
{files_and_code}

### 错误与修复
{errors_and_fixes}

### 问题解决
{problem_solving}

### 用户补充
{user_messages}

### 待处理任务
{pending_tasks}

### 当前工作
{current_work}

### 下一步
{next_steps}
""".format(
            user_request=self.user_request or "无",
            technical_concepts=self.technical_concepts or "无",
            files_and_code=self.files_and_code or "无",
            errors_and_fixes=self.errors_and_fixes or "无",
            problem_solving=self.problem_solving or "无",
            user_messages=self.user_messages or "无",
            pending_tasks=self.pending_tasks or "无",
            current_work=self.current_work or "无",
            next_steps=self.next_steps or "无"
        )
        return {"role": "system", "content": content, "name": "context_summary"}


class ContextManager:
    """
    Context manager for handling context pressure and compression.

    Implements a three-layer compression strategy based on context pressure:
    - 70-85%: Light cleanup (remove expired temp messages)
    - 85-95%: Summary mark (mark old messages for deletion)
    - >95%: Model compression (generate nine-section summary)
    """

    def __init__(
        self,
        memory: "BaseMemory",
        llm,
        config,
        verbose: bool = False,
        llm_config=None,
    ):
        self.memory = memory
        self.llm = llm
        self.config = config
        self.verbose = verbose
        self._llm_config = llm_config
        self.compress_failures = 0
        self._round = 0

    def check_and_compress(
        self,
        max_context_tokens: int | None = None,
        last_prompt_tokens: int | None = None,
    ) -> bool:
        """
        Check context pressure and execute compression if needed.

        Args:
            max_context_tokens: Override max context tokens (uses config if None)
            last_prompt_tokens: Real prompt_tokens from previous LLM call (v0.7.12).
                If provided, use this instead of estimate_tokens().
                If None (first iteration), fall back to estimate_tokens().

        Returns:
            True if compression was performed, False otherwise
        """
        from .token_utils import estimate_tokens

        # Get effective max context tokens
        if max_context_tokens is None:
            if self.config.max_context_tokens is not None:
                max_context_tokens = self.config.max_context_tokens
            elif self._llm_config is not None:
                max_context_tokens = self._llm_config.get_context_length()
            else:
                from ..config.schema import CONSERVATIVE_CONTEXT_FALLBACK
                max_context_tokens = CONSERVATIVE_CONTEXT_FALLBACK

        messages = self.memory.get_all()

        # v0.7.12: Use real prompt_tokens if available, otherwise estimate
        if last_prompt_tokens is not None:
            tokens = last_prompt_tokens
            token_source = "real"
        else:
            tokens = estimate_tokens(messages)
            token_source = "estimated"

        ratio = tokens / max_context_tokens

        if self.verbose:
            print(f"[Context] Tokens: {tokens}/{max_context_tokens} ({ratio:.1%}) [{token_source}]")

        if ratio < self.config.pressure_threshold_low:
            return False

        if ratio < self.config.pressure_threshold_mid:
            return self._try_light_cleanup()

        if ratio < self.config.pressure_threshold_high:
            return self._try_summary_mark()

        return self._try_model_compress()

    def _try_light_cleanup(self) -> bool:
        """
        First layer: Light cleanup.

        Removes expired temporary messages (tool results, intermediate outputs).

        Returns:
            True if any cleanup was performed
        """
        messages = self.memory.get_all()
        if len(messages) <= 10:
            return False

        cleaned = []
        kept_count = 0

        for i, msg in enumerate(messages):
            role = msg.get("role", "")

            # Always keep system and user messages
            if role in ("system", "user"):
                cleaned.append(msg)
                kept_count += 1
            # Keep recent messages
            elif i >= len(messages) - self.config.temp_message_age * 3:
                cleaned.append(msg)
                kept_count += 1
            # Keep assistant messages with content (might have important info)
            elif role == "assistant" and msg.get("content"):
                cleaned.append(msg)
                kept_count += 1

        if len(cleaned) < len(messages):
            if self.verbose:
                removed = len(messages) - len(cleaned)
                print(f"[Context] Light cleanup: removed {removed} messages")
            self._replace_messages(cleaned)
            return True

        return False

    def _try_summary_mark(self) -> bool:
        """
        Second layer: Summary mark.

        Marks old messages as deletable while preserving key messages.
        Currently implemented as enhanced light cleanup.

        Returns:
            True if any cleanup was performed
        """
        messages = self.memory.get_all()
        if len(messages) <= 15:
            return False

        cleaned = []
        recent_start = max(0, len(messages) - 10)

        for i, msg in enumerate(messages):
            role = msg.get("role", "")

            # Always keep system messages
            if role == "system":
                cleaned.append(msg)
            # Keep all user messages (they contain requests)
            elif role == "user":
                cleaned.append(msg)
            # Keep recent messages
            elif i >= recent_start:
                cleaned.append(msg)
            # Keep assistant messages with error info
            elif role == "assistant":
                content = msg.get("content", "")
                if "error" in content.lower() or "fix" in content.lower():
                    cleaned.append(msg)

        if len(cleaned) < len(messages):
            if self.verbose:
                removed = len(messages) - len(cleaned)
                print(f"[Context] Summary mark: removed {removed} messages")
            self._replace_messages(cleaned)
            return True

        return self._try_light_cleanup()

    def _try_model_compress(self) -> bool:
        """
        Third layer: Model compression.

        Uses LLM to generate a nine-section summary and replaces
        most messages with the summary.

        Returns:
            True if compression was performed
        """
        # Circuit breaker: stop if too many failures
        if self.compress_failures >= self.config.max_compress_failures:
            if self.verbose:
                print(f"[Context] Circuit breaker active: {self.compress_failures} failures")
            return False

        try:
            summary = self._generate_summary()
            if summary:
                self._replace_with_summary(summary)
                self.compress_failures = 0
                if self.verbose:
                    print("[Context] Model compression: generated summary")
                return True
            else:
                # Summary generation returned None (not enough messages or internal error)
                self.compress_failures += 1
                if self.verbose:
                    print("[Context] Compression failed: no summary generated")
        except Exception as e:
            self.compress_failures += 1
            if self.verbose:
                print(f"[Context] Compression failed: {e}")

        return False

    def _generate_summary(self) -> NineSectionSummary | None:
        """
        Generate nine-section summary using LLM.

        Returns:
            NineSectionSummary instance or None if generation failed
        """
        messages = self.memory.get_all()

        # Skip if not enough messages to summarize
        if len(messages) < 10:
            return None

        prompt = """分析以下对话历史，生成结构化摘要。

对话历史：
{history}

请按以下格式输出摘要（每个部分一行，用冒号分隔标题和内容）：
---
用户请求: [用户的原始请求和目标]
技术概念: [涉及的技术概念、决策和设计]
文件与代码: [涉及的文件和关键代码]
错误与修复: [遇到的错误和修复过程]
问题解决: [问题解决的关键步骤]
用户补充: [用户提供的补充信息]
待处理任务: [尚未完成的任务]
当前工作: [当前正在进行的工作]
下一步: [建议的下一步行动]
---

只输出摘要内容，不要输出其他内容。如果某个部分没有内容，写"无"。""".format(
            history=self._format_messages(messages)
        )

        # Let exceptions propagate to caller for circuit breaker handling
        response, _, _ = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None
        )
        return self._parse_summary(response)

    def _parse_summary(self, text: str) -> NineSectionSummary:
        """
        Parse LLM output into NineSectionSummary.

        Args:
            text: LLM response text

        Returns:
            NineSectionSummary instance
        """
        sections = {
            "用户请求": "",
            "技术概念": "",
            "文件与代码": "",
            "错误与修复": "",
            "问题解决": "",
            "用户补充": "",
            "待处理任务": "",
            "当前工作": "",
            "下一步": ""
        }

        current_section = None
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check for section header
            found_section = None
            for section_name in sections:
                if line.startswith(section_name + ":") or line.startswith(section_name + "："):
                    found_section = section_name
                    # Extract content after colon
                    if ":" in line:
                        content = line.split(":", 1)[1].strip()
                    elif "：" in line:
                        content = line.split("：", 1)[1].strip()
                    else:
                        content = ""
                    sections[section_name] = content
                    break

            if found_section:
                current_section = found_section
            elif current_section and not line.startswith("---"):
                # Append to current section
                sections[current_section] += "\n" + line

        return NineSectionSummary(
            user_request=sections["用户请求"].strip(),
            technical_concepts=sections["技术概念"].strip(),
            files_and_code=sections["文件与代码"].strip(),
            errors_and_fixes=sections["错误与修复"].strip(),
            problem_solving=sections["问题解决"].strip(),
            user_messages=sections["用户补充"].strip(),
            pending_tasks=sections["待处理任务"].strip(),
            current_work=sections["当前工作"].strip(),
            next_steps=sections["下一步"].strip()
        )

    def _replace_with_summary(self, summary: NineSectionSummary):
        """
        Replace messages with summary.

        Keeps system message and recent messages, inserts summary.

        Args:
            summary: NineSectionSummary to insert
        """
        messages = self.memory.get_all()

        # Keep system message
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None

        # Keep recent messages (last 6)
        recent = messages[-6:] if len(messages) > 6 else messages[1:] if system_msg else messages

        # Build new message list
        new_messages = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.append(summary.to_message())
        new_messages.extend(recent)

        self._replace_messages(new_messages)

    def _replace_messages(self, messages: list[dict]):
        """
        Replace all messages in memory.

        Args:
            messages: New message list
        """
        # Clear and rebuild
        self.memory.clear()
        for msg in messages:
            self.memory.add(msg)

    def _format_messages(self, messages: list[dict], max_length: int = 500) -> str:
        """
        Format messages for LLM prompt.

        Args:
            messages: Message list to format
            max_length: Max length per message content

        Returns:
            Formatted string
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Truncate long content
            if len(content) > max_length:
                content = content[:max_length] + "..."

            # Add tool call info if present
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                tool_names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
                content += f" [工具调用: {', '.join(tool_names)}]"

            lines.append(f"[{role}] {content}")

        return "\n".join(lines)
