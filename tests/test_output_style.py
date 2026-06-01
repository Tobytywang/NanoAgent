"""
Tests for output style configuration and token efficiency.
"""

import pytest
from nano_agent.config.schema import OutputStyleConfig
from nano_agent.agent.prompts import (
    REACT_SYSTEM_PROMPT,
    REACT_SYSTEM_PROMPT_CONCISE,
    REACT_SYSTEM_PROMPT_STANDARD,
)
from nano_agent.agent.token_utils import estimate_text_tokens
from nano_agent.agent.result_summarizer import ToolResultSummarizer, SummarizerConfig
from nano_agent.agent.react import _is_simple_question


class TestOutputStyleConfig:
    """Tests for OutputStyleConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = OutputStyleConfig()
        assert config.style == "standard"
        assert config.tool_output_max_tokens == 500

    def test_concise_style(self):
        """Test concise style configuration."""
        config = OutputStyleConfig(style="concise")
        assert config.style == "concise"

    def test_detailed_style(self):
        """Test detailed style configuration."""
        config = OutputStyleConfig(style="detailed", tool_output_max_tokens=1000)
        assert config.style == "detailed"
        assert config.tool_output_max_tokens == 1000

    def test_invalid_style_accepted_but_invalid(self):
        """Test that invalid style is accepted (dataclass doesn't validate Literal)."""
        # Note: Python dataclass doesn't validate Literal types at runtime
        # This test documents that behavior
        config = OutputStyleConfig(style="invalid")
        assert config.style == "invalid"  # Accepted but won't work in practice


class TestPromptTokenEfficiency:
    """Tests for prompt token efficiency."""

    def test_concise_prompt_is_short(self):
        """Concise prompt should be under 400 tokens."""
        tokens = estimate_text_tokens(REACT_SYSTEM_PROMPT_CONCISE)
        assert tokens < 400, f"Concise prompt has {tokens} tokens, expected < 400"

    def test_standard_prompt_is_medium(self):
        """Standard prompt should be under 1000 tokens."""
        tokens = estimate_text_tokens(REACT_SYSTEM_PROMPT_STANDARD)
        assert tokens < 1000, f"Standard prompt has {tokens} tokens, expected < 1000"

    def test_detailed_prompt_is_longest(self):
        """Detailed prompt should be longer than standard."""
        detailed_tokens = estimate_text_tokens(REACT_SYSTEM_PROMPT)
        standard_tokens = estimate_text_tokens(REACT_SYSTEM_PROMPT_STANDARD)
        assert detailed_tokens > standard_tokens

    def test_all_prompts_have_tools_placeholder(self):
        """All prompts should have {tools_description} placeholder."""
        assert "{tools_description}" in REACT_SYSTEM_PROMPT_CONCISE
        assert "{tools_description}" in REACT_SYSTEM_PROMPT_STANDARD
        assert "{tools_description}" in REACT_SYSTEM_PROMPT


class TestToolDescriptionFormatting:
    """Tests for tool description formatting."""

    def test_concise_format_is_short(self):
        """Concise tool description should be minimal."""
        # Simulate concise format
        tool_name = "file_read"
        description = "Read contents of a file. Returns file content as string."
        first_sentence = description.split(".")[0]
        concise_desc = f"- {tool_name}: {first_sentence}"

        # Should be short
        assert len(concise_desc) < 100
        assert "Read contents of a file" in concise_desc

    def test_standard_format_includes_required_params(self):
        """Standard format should include required parameters."""
        # Simulate standard format
        tool_name = "file_read"
        description = "Read contents of a file."
        required = ["file_path"]
        params_str = ", ".join(required)
        standard_desc = f"- {tool_name}: {description}\n  Required params: {params_str}"

        assert "Required params: file_path" in standard_desc


class TestOutputTruncation:
    """Tests for tool output truncation."""

    def test_short_output_not_truncated(self):
        """Short output should not be truncated."""
        max_tokens = 500
        max_chars = max_tokens * 4
        short_output = "Hello world"

        assert len(short_output) <= max_chars
        # No truncation needed
        assert short_output == "Hello world"

    def test_long_output_is_truncated(self):
        """Long output should be truncated."""
        max_tokens = 500
        max_chars = max_tokens * 4
        long_output = "x" * 3000  # 3000 chars > 2000 max

        if len(long_output) > max_chars:
            truncated = long_output[:max_chars] + "\n... [输出已截断]"

        assert len(truncated) < len(long_output)
        assert "已截断" in truncated

    def test_chinese_output_truncation(self):
        """Chinese output should be truncated correctly."""
        max_tokens = 100
        max_chars = max_tokens * 4
        chinese_output = "测试" * 500  # 1000 chars > 400 max

        if len(chinese_output) > max_chars:
            truncated = chinese_output[:max_chars] + "\n... [输出已截断]"

        assert len(truncated) < len(chinese_output)


class TestToolResultSummarizer:
    """Tests for tool result summarizer."""

    def test_summarizer_file_read_short(self):
        """Short file content should not be summarized."""
        summarizer = ToolResultSummarizer()
        content = "line1\nline2\nline3"
        result = summarizer.summarize(content, "file_read")
        assert result == content

    def test_summarizer_file_read_long(self):
        """Long file content should be summarized."""
        config = SummarizerConfig(max_lines=10, keep_first_lines=2, keep_last_lines=2)
        summarizer = ToolResultSummarizer(config)
        content = "\n".join([f"line{i}" for i in range(30)])
        result = summarizer.summarize(content, "file_read")
        assert "skipped" in result
        assert len(result) < len(content)

    def test_summarizer_shell_filters_noise(self):
        """Shell output should filter noise."""
        summarizer = ToolResultSummarizer()
        content = "total 8\ndrwxr-xr-x 2 user user 4096 .\n-rw-r--r-- 1 user user  123 file.txt"
        result = summarizer.summarize(content, "shell_execute")
        # Should filter out 'total' line
        assert "total" not in result or "file.txt" in result

    def test_summarizer_file_search(self):
        """File search should limit results."""
        config = SummarizerConfig(max_lines=5)
        summarizer = ToolResultSummarizer(config)
        content = "\n".join([f"file{i}.txt" for i in range(20)])
        result = summarizer.summarize(content, "file_search")
        assert "more" in result  # Should show count of remaining files


class TestSimpleQuestionDetection:
    """Tests for simple question detection."""

    def test_greeting_is_simple(self):
        """Greetings should be detected as simple."""
        assert _is_simple_question("你好")
        assert _is_simple_question("hello")
        assert _is_simple_question("Hi there")

    def test_thanks_is_simple(self):
        """Thanks should be detected as simple."""
        assert _is_simple_question("谢谢")
        assert _is_simple_question("thanks")
        assert _is_simple_question("Thank you!")

    def test_identity_question_is_simple(self):
        """Identity questions should be detected as simple."""
        assert _is_simple_question("你是谁")
        assert _is_simple_question("Who are you?")

    def test_complex_question_not_simple(self):
        """Complex questions should not be detected as simple."""
        assert not _is_simple_question("请帮我查看当前目录的文件")
        assert not _is_simple_question("分析这个项目的结构")

    def test_short_question_is_simple(self):
        """Very short questions should be detected as simple."""
        assert _is_simple_question("好的")
        assert _is_simple_question("ok")


class TestIntelligentSummarization:
    """Tests for intelligent tool result summarization."""

    def test_extract_imports_from_python_file(self):
        """Should extract import statements."""
        config = SummarizerConfig(extract_imports=True, max_lines=5)
        summarizer = ToolResultSummarizer(config)
        content = "import os\nimport sys\nprint('hello')\nprint('world')\n" * 10
        result = summarizer.summarize(content, "file_read")
        assert "import os" in result
        assert "Imports:" in result

    def test_extract_class_signatures(self):
        """Should extract class definitions."""
        config = SummarizerConfig(extract_signatures=True, max_lines=5)
        summarizer = ToolResultSummarizer(config)
        content = (
            "class MyClass:\n    pass\n\nclass Another:\n    pass\n\n# other code\n"
            * 10
        )
        result = summarizer.summarize(content, "file_read")
        assert "class MyClass" in result
        assert "Structure:" in result

    def test_extract_function_signatures(self):
        """Should extract function definitions."""
        config = SummarizerConfig(extract_signatures=True, max_lines=5)
        summarizer = ToolResultSummarizer(config)
        content = "def helper():\n    pass\n\ndef main():\n    pass\n\n# code\n" * 10
        result = summarizer.summarize(content, "file_read")
        assert "def helper" in result or "def main" in result

    def test_extract_shell_errors(self):
        """Should extract error messages from shell output."""
        config = SummarizerConfig(extract_errors=True)
        summarizer = ToolResultSummarizer(config)
        content = (
            "Success line\nError: file not found\nAnother success\nFailed to connect\n"
            * 10
        )
        result = summarizer.summarize(content, "shell_execute")
        assert "Error: file not found" in result
        assert "Failed to connect" in result
        assert "Errors:" in result

    def test_file_search_count_only(self):
        """Should show only count when configured."""
        config = SummarizerConfig(file_search_count_only=True)
        summarizer = ToolResultSummarizer(config)
        content = "50\nfile1.py\nfile2.py\nfile3.py"
        result = summarizer.summarize(content, "file_search")
        assert "[50 files found]" in result
        assert "file1.py" not in result

    def test_combined_extraction(self):
        """Should combine multiple extraction types."""
        config = SummarizerConfig(
            extract_imports=True, extract_signatures=True, max_lines=5
        )
        summarizer = ToolResultSummarizer(config)
        content = """
import os
import sys

class MyClass:
    def method(self):
        pass

def helper():
    pass

# long body here
""" * 20
        result = summarizer.summarize(content, "file_read")
        assert "Imports:" in result
        assert "Structure:" in result
        assert "import os" in result

    def test_disabled_extraction(self):
        """Should not extract when disabled."""
        config = SummarizerConfig(
            extract_imports=False, extract_signatures=False, max_lines=5
        )
        summarizer = ToolResultSummarizer(config)
        content = "import os\nclass MyClass:\n    pass\n" * 20
        result = summarizer.summarize(content, "file_read")
        # Should still have content but no extraction markers
        assert "Imports:" not in result
        assert "Structure:" not in result

    def test_async_function_signature(self):
        """Should extract async function definitions."""
        config = SummarizerConfig(extract_signatures=True, max_lines=5)
        summarizer = ToolResultSummarizer(config)
        content = "async def fetch():\n    pass\n\n# code\n" * 20
        result = summarizer.summarize(content, "file_read")
        assert "async def fetch" in result

    def test_no_meaningful_shell_output(self):
        """Should handle empty shell output."""
        summarizer = ToolResultSummarizer()
        content = "total 8\ndrwxr-xr-x 2 user user 4096 ."
        result = summarizer.summarize(content, "shell_execute")
        # Should filter noise and return meaningful output or empty message
        assert "total" not in result or result == "[No meaningful output]"
