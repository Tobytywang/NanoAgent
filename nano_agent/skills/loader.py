"""
Skill loader - load skills from YAML config and directories.
"""

import importlib
import sys
from pathlib import Path

import yaml

from .base import BaseSkill, SkillDefinition, SkillRegistry


class SkillLoader:
    """技能包加载器"""

    def __init__(self, registry: SkillRegistry | None = None):
        self.registry = registry or SkillRegistry()

    def load_from_yaml(self, yaml_path: str | Path) -> SkillDefinition | None:
        """从 YAML 文件加载技能包定义"""
        path = Path(yaml_path)
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        definition = SkillDefinition(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt"),
            tools=data.get("tools", []),
            knowledge=data.get("knowledge", []),
            enabled=data.get("enabled", True),
            config=data.get("config", {}),
        )

        self.registry.register_definition(definition)
        return definition

    def load_from_directory(self, directory: str | Path) -> list[SkillDefinition]:
        """从目录加载所有技能包定义"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return []

        definitions = []
        for yaml_file in dir_path.glob("*.yaml"):
            definition = self.load_from_yaml(yaml_file)
            if definition:
                definitions.append(definition)

        for yaml_file in dir_path.glob("*.yml"):
            definition = self.load_from_yaml(yaml_file)
            if definition:
                definitions.append(definition)

        return definitions

    def load_skill_class(self, module_path: str, class_name: str = "Skill") -> BaseSkill | None:
        """动态加载技能包类"""
        try:
            # 支持从文件路径加载
            if module_path.endswith(".py"):
                path = Path(module_path)
                if not path.exists():
                    return None

                # 动态导入模块
                spec = importlib.util.spec_from_file_location(path.stem, path)
                if spec is None or spec.loader is None:
                    return None

                module = importlib.util.module_from_spec(spec)
                sys.modules[path.stem] = module
                spec.loader.exec_module(module)
            else:
                # 从模块名加载
                module = importlib.import_module(module_path)

            # 获取技能包类
            skill_class = getattr(module, class_name, None)
            if skill_class is None:
                return None

            # 实例化
            skill = skill_class()
            if isinstance(skill, BaseSkill):
                self.registry.register(skill)
                return skill

            return None

        except Exception:
            return None

    def load_from_config(self, config: dict) -> list[BaseSkill]:
        """从配置加载技能包"""
        skills_config = config.get("skills", {})
        enabled_skills = skills_config.get("enabled", [])
        skills_directory = skills_config.get("directory", ".nano_agent/skills")

        loaded_skills = []

        # 从目录加载
        if skills_directory:
            self.load_from_directory(skills_directory)

        # 加载启用的技能包类
        for skill_name in enabled_skills:
            # 尝试从内置技能包加载
            try:
                module_path = f"nano_agent.skills.builtin.{skill_name}"
                skill = self.load_skill_class(module_path)
                if skill:
                    loaded_skills.append(skill)
            except Exception:
                pass

        return loaded_skills
