"""
Tool call merging for reducing iteration count.

Detects similar/related tool calls and merges them into single batched operations.
"""

import re

from ..llm.messages import ToolCall
from ..config.schema import ToolMergeConfig


class ToolCallMerger:
    """
    Analyzes and merges similar tool calls.

    Merge strategies by tool type:
    - file_search: Multiple patterns -> single search with glob alternatives
    - shell_execute: Multiple commands -> compound command (cmd1 && cmd2)
    - file_read: Not merged (different content)
    """

    def __init__(self, config: ToolMergeConfig | None = None):
        self.config = config or ToolMergeConfig()

    def analyze_and_merge(self, tool_calls: list[ToolCall]) -> list[ToolCall]:
        """
        Analyze tool calls and merge similar ones.

        Args:
            tool_calls: Original tool calls from LLM

        Returns:
            Merged/reduced tool calls list
        """
        if not self.config.enabled or not tool_calls:
            return tool_calls

        # Group by tool name
        grouped = self._group_by_tool(tool_calls)

        merged = []
        for tool_name, calls in grouped.items():
            if tool_name in self.config.merge_tools and len(calls) > 1:
                merged_calls = self._merge_tool_group(tool_name, calls)
                merged.extend(merged_calls)
            else:
                merged.extend(calls)

        return merged

    def _group_by_tool(self, tool_calls: list[ToolCall]) -> dict[str, list[ToolCall]]:
        """Group tool calls by tool name."""
        grouped: dict[str, list[ToolCall]] = {}
        for call in tool_calls:
            if call.name not in grouped:
                grouped[call.name] = []
            grouped[call.name].append(call)
        return grouped

    def _merge_tool_group(
        self, tool_name: str, calls: list[ToolCall]
    ) -> list[ToolCall]:
        """
        Merge multiple calls of the same tool.

        Args:
            tool_name: Name of the tool
            calls: List of calls to potentially merge

        Returns:
            Merged calls (possibly fewer than input)
        """
        if tool_name == "file_search":
            return self._merge_file_searches(calls)
        elif tool_name == "shell_execute":
            return self._merge_shell_commands(calls)
        else:
            return calls

    def _merge_file_searches(self, calls: list[ToolCall]) -> list[ToolCall]:
        """
        Merge file search calls.

        Strategy: Combine patterns into glob alternatives.
        Example: "*.py" + "*.ts" -> "*.{py,ts}"
        Example: "*plan*" + "*.md" -> "*plan*|*.md" (pipe separator)

        Note: file_search tool supports pipe separator for multiple patterns.
        """
        if len(calls) <= 1:
            return calls

        # Check if all searches are in same directory
        directories = [call.arguments.get("directory") for call in calls]
        if len(set(filter(None, directories))) > 1:
            # Different directories, can't merge
            return calls

        # Combine patterns
        patterns = []
        for call in calls:
            pattern = call.arguments.get("pattern", "")
            if pattern:
                patterns.append(pattern)

        if not patterns:
            return calls

        # Use first call as base, update pattern
        merged_call = ToolCall(
            id=calls[0].id,
            name=calls[0].name,
            arguments=calls[0].arguments.copy(),
        )

        # Combine patterns
        combined_pattern = self._combine_patterns(patterns)
        merged_call.arguments["pattern"] = combined_pattern

        return [merged_call]

    def _combine_patterns(self, patterns: list[str]) -> str:
        """
        Combine multiple glob patterns into one.

        Uses pipe separator for complex patterns (file_search supports it).
        Uses {ext1,ext2} syntax for simple extension patterns.
        """
        # Check if all are simple extension patterns (*.ext)
        extensions = []
        for p in patterns:
            match = re.match(r"^\*\.(\w+)$", p)
            if match:
                extensions.append(match.group(1))
            else:
                # Not a simple extension pattern, use pipe separator
                # file_search tool supports pipe separator for multiple patterns
                return "|".join(patterns)

        # All are simple extension patterns, use {ext1,ext2} syntax
        if len(extensions) > 1:
            return f"*.{{{','.join(extensions)}}}"
        return patterns[0]

    def _merge_shell_commands(self, calls: list[ToolCall]) -> list[ToolCall]:
        """
        Merge shell command calls.

        Strategy: Combine with && for sequential execution.
        Example: "ls" + "pwd" -> "ls && pwd"
        """
        if len(calls) <= 1:
            return calls

        commands = []
        for call in calls:
            cmd = call.arguments.get("command", "")
            if cmd:
                commands.append(cmd)

        if not commands:
            return calls

        # Filter out dangerous commands (don't merge if any is dangerous)
        for cmd in commands:
            if self._is_dangerous(cmd):
                return calls

        # Limit batch size
        if len(commands) > self.config.max_batch_size:
            # Merge first N, keep rest
            merged_commands = commands[: self.config.max_batch_size]
            remaining = commands[self.config.max_batch_size :]

            # Create merged call
            merged_call = ToolCall(
                id=calls[0].id,
                name=calls[0].name,
                arguments={"command": " && ".join(merged_commands)},
            )

            # Create remaining calls
            remaining_calls = []
            for i, cmd in enumerate(remaining):
                remaining_calls.append(
                    ToolCall(
                        id=calls[self.config.max_batch_size + i].id,
                        name=calls[0].name,
                        arguments={"command": cmd},
                    )
                )

            return [merged_call] + remaining_calls

        # Merge all commands
        merged_call = ToolCall(
            id=calls[0].id,
            name=calls[0].name,
            arguments={"command": " && ".join(commands)},
        )

        return [merged_call]

    def _is_dangerous(self, command: str) -> bool:
        """Check if command is potentially dangerous."""
        dangerous_patterns = [
            "rm ",
            "rm -",
            "delete",
            "format",
            "sudo",
            "chmod 777",
            "mv /*",
            "> /dev/",
            "mkfs",
            "dd if=",
        ]
        cmd_lower = command.lower().strip()
        return any(p in cmd_lower for p in dangerous_patterns)
