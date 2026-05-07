"""
ReAct Agent 实现
"""

import time
import uuid
from typing import Generator
from .base import BaseAgent
from .prompts import REACT_SYSTEM_PROMPT, TOOL_DESCRIPTION_TEMPLATE
from .undo import UndoStack
from ..llm.messages import ToolCall
from ..tools.base import ToolResult
from ..monitoring import MetricsTracker
from ..utils.strings import safe_str


class ReActAgent(BaseAgent):
    """
    ReAct (Reasoning + Acting) Agent 实现。

    遵循 思考 -> 行动 -> 观察 循环来解决问题。
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
        初始化 ReAct Agent。

        Args:
            llm: LLM 客户端实例
            memory: 记忆系统实例
            tool_registry: 工具注册表实例
            max_iterations: 最大推理迭代次数
            verbose: 是否打印调试信息
            skill_prompt: 来自技能的额外提示
            tracker: 监控指标追踪器
        """
        super().__init__(llm, memory, tool_registry, max_iterations)
        self.verbose = verbose
        self.skill_prompt = skill_prompt
        self.tracker = tracker or MetricsTracker()
        self._undo_stack = UndoStack()
        self._round_counter = 0
        self._pending_name_updates: list[tuple[str, str]] = []  # (name_type, name_value) 列表
        self._prev_name_values: dict[str, str] = {}  # 用于撤销的上一次名字值
        self._setup_system_prompt()

    def _setup_system_prompt(self) -> None:
        """设置包含工具描述的系统提示"""
        tools_desc = self._format_tools_description()
        system_prompt = REACT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        # 如果有技能提示，添加到系统提示
        if self.skill_prompt:
            system_prompt = f"{system_prompt}\n\n## Skills\n\n{self.skill_prompt}"

        self.memory.set_system_prompt(system_prompt)

    def _format_tools_description(self) -> str:
        """格式化工具描述用于系统提示"""
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
        运行 ReAct 循环处理用户输入。

        Args:
            user_input: 用户输入文本

        Returns:
            Agent 的最终响应
        """
        # 开始新的撤销轮次
        self._round_counter += 1
        self._undo_stack.start_round(f"round_{self._round_counter}")

        # 添加用户消息到记忆
        self.memory.add_user_message(user_input)

        # 开始追踪
        self.tracker.start_run(user_input)

        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            self.tracker.start_iteration(iteration)

            if self.verbose:
                print(f"\n[Iteration {iteration}/{self.max_iterations}]")

            # 调用 LLM 处理当前上下文
            messages = self.memory.get_all()
            tools_schema = self.tool_registry.get_all_schemas()

            llm_start = time.perf_counter()
            response_text, tool_calls, usage = self.llm.chat(
                messages=messages,
                tools=tools_schema if tools_schema else None
            )
            llm_latency = (time.perf_counter() - llm_start) * 1000

            # 记录 LLM 调用
            self.tracker.record_llm_call(
                model=self.llm.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=llm_latency,
                tool_calls_count=len(tool_calls),
            )

            # 如果没有工具调用，返回最终答案
            if not tool_calls:
                self.memory.add_assistant_message(response_text)
                self.tracker.end_iteration()
                self.tracker.end_run(response_text)
                return response_text

            # 有工具调用 - 执行它们
            if self.verbose and response_text:
                print(f"[Think] {safe_str(response_text[:200])}...")

            # 添加包含工具调用的助手消息
            self.memory.add_assistant_message(
                response_text,
                tool_calls=[tc.to_dict() for tc in tool_calls]
            )

            # 执行每个工具调用
            for tool_call in tool_calls:
                tool_start = time.perf_counter()
                result = self._execute_tool_call(tool_call)
                tool_latency = (time.perf_counter() - tool_start) * 1000

                # 记录工具执行
                self.tracker.record_tool_execution(
                    tool_name=tool_call.name,
                    arguments=tool_call.arguments,
                    success=result.success,
                    latency_ms=tool_latency,
                    output_length=len(result.output) if result.output else 0,
                    error=result.error,
                )

                if self.verbose:
                    status = "成功" if result.success else "失败"
                    args_str = safe_str(str(tool_call.arguments))
                    print(f"[Tool Call] {tool_call.name}({args_str}) -> {status}")
                    if result.output:
                        output = safe_str(result.output)
                        preview = output[:200] + "..." if len(output) > 200 else output
                        print(f"[Observe] {preview}")

                # 添加工具结果到记忆
                result_content = result.output if result.success else f"错误: {result.error}"
                self.memory.add_tool_result(
                    tool_call_id=tool_call.id,
                    content=result_content
                )

            self.tracker.end_iteration()

        # 达到最大迭代次数
        response = "抱歉，我无法在迭代限制内完成此任务。请尝试简化您的请求。"
        self.tracker.end_run(response)
        return response

    def run_stream(self, user_input: str) -> Generator[str, None, None]:
        """
        流式返回响应（简化版本）。

        目前运行完整循环并返回最终结果。
        带工具调用的真正流式处理需要更复杂的实现。

        Args:
            user_input: 用户输入文本

        Yields:
            响应的文本片段
        """
        result = self.run(user_input)
        yield result

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        执行单个工具调用。

        Args:
            tool_call: 要执行的工具调用

        Returns:
            执行结果的 ToolResult
        """
        result = self.execute_tool(tool_call.name, tool_call.arguments)

        # 追踪可撤销操作
        if result.success and result.undo_data:
            tool = self.tool_registry.get(tool_call.name)
            if tool and tool.supports_undo:
                self._undo_stack.push(tool_call.name, result.undo_data)

        # 检测 memorize 工具的名字更新（用于 CLI 回调）
        if tool_call.name == "memorize" and result.success and result.metadata:
            name_type = result.metadata.get("name_type")
            name_value = result.metadata.get("name_value")
            if name_type and name_value:
                self._pending_name_updates.append((name_type, name_value))

        return result

    def undo_current_round(self, context: dict) -> list[str]:
        """
        撤销当前轮次的所有操作。

        Args:
            context: 执行上下文（包含 memory, config 等）

        Returns:
            成功撤销的工具名称列表
        """
        undone = []
        records = self._undo_stack.get_round_records()

        # 按逆序撤销
        for record in reversed(records):
            tool = self.tool_registry.get(record.tool_name)
            if tool and tool.supports_undo:
                if tool.undo(record.undo_data, context):
                    undone.append(record.tool_name)
                    self._undo_stack.remove_record(record)

        self._undo_stack.clear_round()
        return undone

    def has_undoable_operations(self) -> bool:
        """检查当前轮次是否有可撤销操作"""
        return self._undo_stack.has_round_records()

    def add_tool(self, tool) -> None:
        """
        添加新工具到 Agent。

        Args:
            tool: 要添加的工具实例
        """
        self.tool_registry.register(tool)
        # 用新工具更新系统提示
        self._setup_system_prompt()
