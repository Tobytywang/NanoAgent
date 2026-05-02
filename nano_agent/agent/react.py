"""
ReAct Agent implementation.
"""

import time
import uuid
from typing import Generator
from .base import BaseAgent
from .prompts import REACT_SYSTEM_PROMPT, TOOL_DESCRIPTION_TEMPLATE
from ..llm.messages import ToolCall
from ..tools.base import ToolResult
from ..monitoring import MetricsTracker


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning + Acting) Agent implementation.

    Follows the Think -> Act -> Observe cycle to solve problems.
    """

    def __init__(
        self,
        llm,
        memory,
        tool_registry,
        max_iterations: int = 10,
        verbose: bool = True,
        skill_prompt: str = "",
        tracker: MetricsTracker | None = None,
    ):
        """
        Initialize the ReAct agent.

        Args:
            llm: LLM client instance
            memory: Memory system instance
            tool_registry: Tool registry instance
            max_iterations: Maximum reasoning iterations
            verbose: Whether to print debug information
            skill_prompt: Additional prompt from skills
            tracker: Metrics tracker for monitoring
        """
        super().__init__(llm, memory, tool_registry, max_iterations)
        self.verbose = verbose
        self.skill_prompt = skill_prompt
        self.tracker = tracker or MetricsTracker()
        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """Set up the system prompt with tool descriptions."""
        tools_desc = self._format_tools_description()
        system_prompt = REACT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        # Add skill prompt if available
        if self.skill_prompt:
            system_prompt = f"{system_prompt}\n\n## Skills\n\n{self.skill_prompt}"

        self.memory.set_system_prompt(system_prompt)

    def _format_tools_description(self) -> str:
        """Format tool descriptions for the system prompt."""
        descriptions = []
        for tool_name in self.tool_registry.list_tools():
            tool = self.tool_registry.get(tool_name)
            desc = TOOL_DESCRIPTION_TEMPLATE.format(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters_schema
            )
            descriptions.append(desc)
        return "\n".join(descriptions)

    def run(self, user_input: str) -> str:
        """
        Run the ReAct loop to process user input.

        Args:
            user_input: The user's input text

        Returns:
            The agent's final response
        """
        # Add user message to memory
        self.memory.add_user_message(user_input)

        # Start tracking
        self.tracker.start_run(user_input)

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            self.tracker.start_iteration(iteration)

            if self.verbose:
                print(f"\n[Iteration {iteration}/{self.max_iterations}]")

            # Call LLM with current context
            messages = self.memory.get_all()
            tools_schema = self.tool_registry.get_all_schemas()

            llm_start = time.perf_counter()
            response_text, tool_calls, usage = self.llm.chat(
                messages=messages,
                tools=tools_schema if tools_schema else None
            )
            llm_latency = (time.perf_counter() - llm_start) * 1000

            # Record LLM call
            self.tracker.record_llm_call(
                model=self.llm.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=llm_latency,
                tool_calls_count=len(tool_calls),
            )

            # If no tool calls, return the final answer
            if not tool_calls:
                self.memory.add_assistant_message(response_text)
                self.tracker.end_iteration()
                self.tracker.end_run(response_text)
                return response_text

            # There are tool calls - execute them
            if self.verbose and response_text:
                print(f"[Think] {response_text[:200]}...")

            # Add assistant message with tool calls
            self.memory.add_assistant_message(
                response_text,
                tool_calls=[tc.to_dict() for tc in tool_calls]
            )

            # Execute each tool call
            for tool_call in tool_calls:
                tool_start = time.perf_counter()
                result = self._execute_tool_call(tool_call)
                tool_latency = (time.perf_counter() - tool_start) * 1000

                # Record tool execution
                self.tracker.record_tool_execution(
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    success=result.success,
                    latency_ms=tool_latency,
                    output_length=len(result.output) if result.output else 0,
                    error=result.error,
                )

                if self.verbose:
                    status = "success" if result.success else "failed"
                    print(f"[Tool Call] {tool_call.name}({tool_call.arguments}) -> {status}")
                    if result.output:
                        preview = result.output[:200] + "..." if len(result.output) > 200 else result.output
                        print(f"[Observe] {preview}")

                # Add tool result to memory
                result_content = result.output if result.success else f"Error: {result.error}"
                self.memory.add_tool_result(
                    tool_call_id=tool_call.id,
                    content=result_content
                )

            self.tracker.end_iteration()

        # Reached max iterations
        response = "I apologize, I couldn't complete this task within the iteration limit. Please try simplifying your request."
        self.tracker.end_run(response)
        return response

    def run_stream(self, user_input: str) -> Generator[str, None, None]:
        """
        Stream the response (simplified version).

        For now, this runs the full loop and yields the final result.
        True streaming with tool calls requires more complex handling.

        Args:
            user_input: The user's input text

        Yields:
            Text chunks from the response
        """
        result = self.run(user_input)
        yield result

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a single tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            ToolResult from the execution
        """
        return self.execute_tool(tool_call.name, tool_call.arguments)

    def add_tool(self, tool) -> None:
        """
        Add a new tool to the agent.

        Args:
            tool: Tool instance to add
        """
        self.tool_registry.register(tool)
        # Update system prompt with new tool
        self._setup_system_prompt()
