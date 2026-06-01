"""
Tests for skill mechanism.
"""

import pytest

pytestmark = pytest.mark.unit
import tempfile
from pathlib import Path

from nano_agent.skills.base import BaseSkill, SkillRegistry, SkillDefinition
from nano_agent.skills.loader import SkillLoader
from nano_agent.tools.base import BaseTool, ToolResult


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def execute(self) -> ToolResult:
        return ToolResult(success=True, output="mock result")


class MockSkill(BaseSkill):
    """Mock skill for testing."""

    name = "mock_skill"
    description = "A mock skill for testing"

    @property
    def system_prompt(self) -> str:
        return "You are a mock skill assistant."

    @property
    def tools(self) -> list[BaseTool]:
        return [MockTool()]


class TestSkillDefinition:
    """Tests for SkillDefinition."""

    def test_create_definition(self):
        """Test creating a skill definition."""
        definition = SkillDefinition(
            name="test_skill",
            description="Test skill",
            system_prompt="Test prompt",
            tools=["tool1", "tool2"],
            enabled=True,
        )

        assert definition.name == "test_skill"
        assert definition.description == "Test skill"
        assert definition.system_prompt == "Test prompt"
        assert definition.tools == ["tool1", "tool2"]
        assert definition.enabled is True

    def test_default_values(self):
        """Test default values."""
        definition = SkillDefinition(name="test")

        assert definition.description == ""
        assert definition.system_prompt is None
        assert definition.tools == []
        assert definition.knowledge == []
        assert definition.enabled is True


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_register_skill(self):
        """Test registering a skill."""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)

        assert registry.get("mock_skill") == skill
        assert "mock_skill" in registry.list_skills()

    def test_get_active_skills(self):
        """Test getting active skills."""
        registry = SkillRegistry()
        skill = MockSkill()
        skill.enabled = True

        registry.register(skill)

        active = registry.get_active_skills()
        assert len(active) == 1
        assert active[0] == skill

    def test_get_all_tools(self):
        """Test getting all tools from skills."""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)

        tools = registry.get_all_tools()
        assert len(tools) == 1
        assert tools[0].name == "mock_tool"

    def test_get_combined_system_prompt(self):
        """Test getting combined system prompt."""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)

        prompt = registry.get_combined_system_prompt()
        assert "mock_skill" in prompt
        assert "mock skill assistant" in prompt

    def test_unregister_skill(self):
        """Test unregistering a skill."""
        registry = SkillRegistry()
        skill = MockSkill()

        registry.register(skill)
        result = registry.unregister("mock_skill")

        assert result is True
        assert registry.get("mock_skill") is None

    def test_unregister_nonexistent(self):
        """Test unregistering a nonexistent skill."""
        registry = SkillRegistry()

        result = registry.unregister("nonexistent")

        assert result is False


class TestSkillLoader:
    """Tests for SkillLoader."""

    def test_load_from_yaml(self):
        """Test loading skill from YAML file."""
        with tempfile.TemporaryDirectory() as d:
            yaml_path = Path(d) / "test_skill.yaml"
            yaml_path.write_text("""
name: test_skill
description: A test skill
system_prompt: You are a test assistant.
tools:
  - tool1
  - tool2
enabled: true
""")

            loader = SkillLoader()
            definition = loader.load_from_yaml(yaml_path)

            assert definition is not None
            assert definition.name == "test_skill"
            assert definition.description == "A test skill"
            assert definition.system_prompt == "You are a test assistant."
            assert definition.tools == ["tool1", "tool2"]
            assert definition.enabled is True

    def test_load_from_directory(self):
        """Test loading skills from directory."""
        with tempfile.TemporaryDirectory() as d:
            # Create multiple skill files
            skill1 = Path(d) / "skill1.yaml"
            skill1.write_text("name: skill1\ndescription: First skill")

            skill2 = Path(d) / "skill2.yaml"
            skill2.write_text("name: skill2\ndescription: Second skill")

            loader = SkillLoader()
            definitions = loader.load_from_directory(d)

            assert len(definitions) == 2
            names = [d.name for d in definitions]
            assert "skill1" in names
            assert "skill2" in names

    def test_load_from_nonexistent_directory(self):
        """Test loading from nonexistent directory."""
        loader = SkillLoader()
        definitions = loader.load_from_directory("/nonexistent/path")

        assert definitions == []

    def test_load_from_nonexistent_yaml(self):
        """Test loading from nonexistent YAML file."""
        loader = SkillLoader()
        definition = loader.load_from_yaml("/nonexistent/skill.yaml")

        assert definition is None


class TestSkillsConfig:
    """Tests for skills configuration."""

    def test_skills_config_defaults(self):
        """Test default skills config."""
        from nano_agent.config.schema import SkillsConfig

        config = SkillsConfig()

        assert config.enabled == []
        assert config.directory == ".nano_agent/skills"
        assert config.configs == {}

    def test_config_with_skills(self):
        """Test config parsing with skills."""
        from nano_agent.config.loader import ConfigLoader

        with tempfile.TemporaryDirectory() as d:
            config_path = Path(d) / "config.yaml"
            config_path.write_text("""
skills:
  enabled:
    - coding
    - translation
  directory: ./skills
""")

            config = ConfigLoader.load(config_path)

            assert config.skills.enabled == ["coding", "translation"]
            assert config.skills.directory == "./skills"


class TestSkillHotReload:
    """Tests for skill hot-reload functionality."""

    def test_list_loaded_skills(self):
        """Test listing loaded skills."""
        with tempfile.TemporaryDirectory() as d:
            yaml_path = Path(d) / "test_skill.yaml"
            yaml_path.write_text("name: test_skill\ndescription: Test")

            loader = SkillLoader()
            loader.load_from_yaml(yaml_path)

            skills = loader.list_loaded_skills()
            assert "test_skill" in skills

    def test_get_skill_source(self):
        """Test getting skill source path."""
        with tempfile.TemporaryDirectory() as d:
            yaml_path = Path(d) / "test_skill.yaml"
            yaml_path.write_text("name: test_skill\ndescription: Test")

            loader = SkillLoader()
            loader.load_from_yaml(yaml_path)

            source = loader.get_skill_source("test_skill")
            assert source == str(yaml_path)

    def test_unload_skill(self):
        """Test unloading a skill."""
        with tempfile.TemporaryDirectory() as d:
            yaml_path = Path(d) / "test_skill.yaml"
            yaml_path.write_text("name: test_skill\ndescription: Test")

            loader = SkillLoader()
            loader.load_from_yaml(yaml_path)

            assert "test_skill" in loader.list_loaded_skills()

            result = loader.unload_skill("test_skill")
            assert result is True
            assert "test_skill" not in loader.list_loaded_skills()

    def test_unload_nonexistent_skill(self):
        """Test unloading a nonexistent skill."""
        loader = SkillLoader()
        result = loader.unload_skill("nonexistent")
        assert result is False

    def test_reload_skill(self):
        """Test reloading a skill."""
        with tempfile.TemporaryDirectory() as d:
            yaml_path = Path(d) / "test_skill.yaml"
            yaml_path.write_text("name: test_skill\ndescription: Original")

            loader = SkillLoader()
            loader.load_from_yaml(yaml_path)

            # Modify the file
            yaml_path.write_text("name: test_skill\ndescription: Modified")

            # Reload
            result = loader.reload_skill("test_skill")
            assert result is True

            # Verify reloaded
            definition = loader.registry.get_definition("test_skill")
            assert definition is not None
            assert definition.description == "Modified"

    def test_reload_nonexistent_skill(self):
        """Test reloading a nonexistent skill."""
        loader = SkillLoader()
        result = loader.reload_skill("nonexistent")
        assert result is False


class TestWebSearchSkill:
    """Tests for web_search skill."""

    def test_web_search_skill_file_exists(self):
        """Test that web_search skill file exists in examples."""
        skill_path = Path("examples/skills/web_search.yaml")
        assert skill_path.exists(), "web_search.yaml should exist in examples/skills"

    def test_web_search_skill_loading(self):
        """Test loading web_search skill."""
        skill_path = Path("examples/skills/web_search.yaml")

        loader = SkillLoader()
        definition = loader.load_from_yaml(skill_path)

        assert definition is not None
        assert definition.name == "web_search"
        assert definition.enabled is True
        assert "shell_execute" in definition.tools
        assert "python_execute" in definition.tools

    def test_web_search_skill_has_system_prompt(self):
        """Test that web_search skill has system prompt."""
        skill_path = Path("examples/skills/web_search.yaml")

        loader = SkillLoader()
        definition = loader.load_from_yaml(skill_path)

        assert definition.system_prompt is not None
        assert len(definition.system_prompt) > 0
        assert "web search" in definition.system_prompt.lower()
        assert "curl" in definition.system_prompt.lower()

    def test_web_search_skill_registry(self):
        """Test registering web_search skill."""
        skill_path = Path("examples/skills/web_search.yaml")

        registry = SkillRegistry()
        loader = SkillLoader(registry)
        loader.load_from_yaml(skill_path)

        definition = registry.get_definition("web_search")
        assert definition is not None
        assert definition.name == "web_search"


class TestSkillLoaderPythonClass:
    """Tests for loading Python skill classes."""

    def test_load_skill_class_from_file(self):
        """Test loading a skill class from a Python file."""
        with tempfile.TemporaryDirectory() as d:
            skill_file = Path(d) / "my_skill.py"
            skill_file.write_text("""
from nano_agent.skills.base import BaseSkill
from nano_agent.tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "My tool"

    @property
    def parameters_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self):
        return ToolResult(success=True, output="done")

class Skill(BaseSkill):
    name = "my_python_skill"
    description = "A Python skill"

    @property
    def tools(self):
        return [MyTool()]
""")

            loader = SkillLoader()
            skill = loader.load_skill_class(str(skill_file))

            assert skill is not None
            assert skill.name == "my_python_skill"
            assert len(skill.tools) == 1
            assert skill.tools[0].name == "my_tool"

    def test_load_skill_class_nonexistent_file(self):
        """Test loading from a nonexistent Python file."""
        loader = SkillLoader()
        skill = loader.load_skill_class("/nonexistent/skill.py")
        assert skill is None

    def test_load_skill_class_missing_class(self):
        """Test loading a file without the Skill class."""
        with tempfile.TemporaryDirectory() as d:
            skill_file = Path(d) / "no_skill.py"
            skill_file.write_text("""
# No Skill class here
def some_function():
    pass
""")

            loader = SkillLoader()
            skill = loader.load_skill_class(str(skill_file))
            assert skill is None

    def test_load_skill_class_custom_class_name(self):
        """Test loading a skill with custom class name."""
        with tempfile.TemporaryDirectory() as d:
            skill_file = Path(d) / "custom_skill.py"
            skill_file.write_text("""
from nano_agent.skills.base import BaseSkill

class CustomSkill(BaseSkill):
    name = "custom_skill"
""")

            loader = SkillLoader()
            skill = loader.load_skill_class(str(skill_file), class_name="CustomSkill")

            assert skill is not None
            assert skill.name == "custom_skill"

    def test_load_skill_class_registers_in_registry(self):
        """Test that loaded skill is registered."""
        with tempfile.TemporaryDirectory() as d:
            skill_file = Path(d) / "reg_skill.py"
            skill_file.write_text("""
from nano_agent.skills.base import BaseSkill

class Skill(BaseSkill):
    name = "registered_skill"
""")

            registry = SkillRegistry()
            loader = SkillLoader(registry)
            loader.load_skill_class(str(skill_file))

            assert registry.get("registered_skill") is not None


class TestSkillLoaderFromConfig:
    """Tests for loading skills from config."""

    def test_load_from_config_with_directory(self):
        """Test loading skills from config with directory."""
        with tempfile.TemporaryDirectory() as d:
            skill_file = Path(d) / "config_skill.yaml"
            skill_file.write_text("name: config_skill\ndescription: From config")

            config = {"skills": {"enabled": [], "directory": d}}

            loader = SkillLoader()
            skills = loader.load_from_config(config)

            # Should load from directory
            assert "config_skill" in loader.list_loaded_skills()

    def test_load_from_config_empty(self):
        """Test loading from empty config."""
        loader = SkillLoader()
        skills = loader.load_from_config({})
        assert skills == []
