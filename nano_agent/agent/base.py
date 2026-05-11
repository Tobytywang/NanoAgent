"""
Agent 基类
"""

from abc import ABC, abstractmethod
from ..llm.base import BaseLLM
from ..memory.base import BaseMemory
from ..tools import ToolRegistry
from ..tools.base import ToolResult


class BaseAgent(ABC):
    """Agent 抽象基类"""

    def __init__(
        self,
        llm: BaseLLM,
        memory: BaseMemory,
        tool_registry: ToolRegistry,
        max_iterations: int = 10
    ):
        """
        初始化 Agent。

        Args:
            llm: LLM 客户端实例
            memory: 记忆系统实例
            tool_registry: 工具注册表实例
            max_iterations: 最大推理迭代次数
        """
        self.llm = llm
        self.memory = memory
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    @abstractmethod
    def run(self, user_input: str) -> str:
        """
        处理用户输入并返回响应。

        Args:
            user_input: 用户输入文本

        Returns:
            Agent 的响应
        """
        pass

    def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """
        根据名称和参数执行工具。

        Args:
            tool_name: 要执行的工具名称
            arguments: 传递给工具的参数

        Returns:
            工具执行的 ToolResult
        """
        tool = self.tool_registry.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"未知工具: {tool_name}"
            )
        return tool.execute(**arguments)

    def reset(self) -> None:
        """重置 Agent 的记忆"""
        self.memory.clear()
