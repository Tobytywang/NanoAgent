"""
Skill base classes and registry.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..tools.base import BaseTool


@dataclass
class SkillDefinition:
    """技能包定义（从配置加载）"""
    name: str
    description: str = ""
    system_prompt: str | None = None
    tools: list[str] = field(default_factory=list)  # 工具名称列表
    knowledge: list[dict] = field(default_factory=list)
    enabled: bool = True
    config: dict = field(default_factory=dict)  # 额外配置


class BaseSkill(ABC):
    """技能包抽象基类"""

    name: str
    description: str = ""
    enabled: bool = True  # 默认启用

    @property
    def system_prompt(self) -> str | None:
        """技能包的系统提示（可选）"""
        return None

    @property
    def tools(self) -> list[BaseTool]:
        """技能包提供的工具列表"""
        return []

    @property
    def knowledge(self) -> list[dict]:
        """技能包的知识库"""
        return []

    def setup(self, config: dict | None = None) -> None:
        """技能包初始化钩子"""
        pass

    def teardown(self) -> None:
        """技能包清理钩子"""
        pass


class SkillRegistry:
    """技能包注册表"""

    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}
        self._definitions: dict[str, SkillDefinition] = {}

    def register(self, skill: BaseSkill) -> None:
        """注册技能包"""
        self._skills[skill.name] = skill

    def register_definition(self, definition: SkillDefinition) -> None:
        """注册技能包定义"""
        self._definitions[definition.name] = definition

    def get(self, name: str) -> BaseSkill | None:
        """获取技能包"""
        return self._skills.get(name)

    def get_definition(self, name: str) -> SkillDefinition | None:
        """获取技能包定义"""
        return self._definitions.get(name)

    def get_all_skills(self) -> list[BaseSkill]:
        """获取所有技能包"""
        return list(self._skills.values())

    def get_active_skills(self) -> list[BaseSkill]:
        """获取所有启用的技能包"""
        return [s for s in self._skills.values() if getattr(s, 'enabled', True)]

    def get_all_tools(self) -> list[BaseTool]:
        """获取所有技能包的工具"""
        tools = []
        for skill in self.get_active_skills():
            tools.extend(skill.tools)
        return tools

    def get_combined_system_prompt(self) -> str:
        """获取合并后的系统提示"""
        prompts = []

        # From BaseSkill instances
        for skill in self.get_active_skills():
            if skill.system_prompt:
                prompts.append(f"## {skill.name}\n{skill.system_prompt}")

        # From SkillDefinition instances
        for definition in self._definitions.values():
            if definition.enabled and definition.system_prompt:
                prompts.append(f"## {definition.name}\n{definition.system_prompt}")

        if prompts:
            return "\n\n".join(prompts)
        return ""

    def list_skills(self) -> list[str]:
        """列出所有技能包名称"""
        return list(self._skills.keys())

    def unregister(self, name: str) -> bool:
        """注销技能包"""
        removed = False

        # Remove skill instance
        if name in self._skills:
            skill = self._skills[name]
            skill.teardown()
            del self._skills[name]
            removed = True

        # Remove skill definition
        if name in self._definitions:
            del self._definitions[name]
            removed = True

        return removed

    def clear(self) -> None:
        """清空所有技能包"""
        for skill in self._skills.values():
            skill.teardown()
        self._skills.clear()
        self._definitions.clear()
