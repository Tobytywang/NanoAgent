"""
撤销机制：追踪和回滚工具操作
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class UndoRecord:
    """可撤销操作的记录"""

    tool_name: str
    undo_data: dict
    timestamp: str
    round_id: str  # 标识此操作属于哪个对话轮次


class UndoStack:
    """
    管理按对话轮次组织的可撤销操作栈。

    每个轮次对应一条用户消息及其相关的工具调用。
    撤销操作会回滚当前轮次的所有更改。
    """

    def __init__(self):
        self._records: list[UndoRecord] = []
        self._current_round: str = ""

    def start_round(self, round_id: str) -> None:
        """
        开始新的对话轮次。

        Args:
            round_id: 此轮次的唯一标识符
        """
        self._current_round = round_id

    def push(self, tool_name: str, undo_data: dict) -> None:
        """
        记录一个可撤销操作。

        Args:
            tool_name: 已执行的工具名称
            undo_data: 撤销此操作所需的数据
        """
        if undo_data:
            self._records.append(
                UndoRecord(
                    tool_name=tool_name,
                    undo_data=undo_data,
                    timestamp=datetime.now().isoformat(),
                    round_id=self._current_round,
                )
            )

    def get_round_records(self) -> list[UndoRecord]:
        """
        获取当前轮次的所有记录。

        Returns:
            当前轮次的 UndoRecord 列表，按执行顺序排列
        """
        return [r for r in self._records if r.round_id == self._current_round]

    def has_round_records(self) -> bool:
        """检查当前轮次是否有可撤销操作"""
        return any(r.round_id == self._current_round for r in self._records)

    def clear_round(self) -> None:
        """清除当前轮次的所有记录（成功撤销或轮次完成后）"""
        self._records = [r for r in self._records if r.round_id != self._current_round]

    def remove_record(self, record: UndoRecord) -> None:
        """撤销后移除特定记录"""
        if record in self._records:
            self._records.remove(record)

    def clear_all(self) -> None:
        """清除所有记录"""
        self._records = []

    def count(self) -> int:
        """返回记录总数"""
        return len(self._records)

    def count_round(self) -> int:
        """返回当前轮次的记录数"""
        return len(self.get_round_records())
