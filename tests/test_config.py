"""
Tests for configuration system.
"""

import pytest
import tempfile
import os

from nano_agent.config.schema import Config, LLMConfig, AgentConfig, MemoryConfig, ToolConfig
from nano_agent.config.loader import ConfigLoader


class TestConfigSchema:
    """Test configuration data structures."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.llm.model == "llama3"
        assert config.llm.base_url == "http://localhost:11434"
        assert config.agent.max_iterations == 10
        assert config.memory.max_messages == 50

    def test_custom_llm_config(self):
        """Test custom LLM configuration."""
        llm_config = LLMConfig(
            model="qwen2",
            base_url="http://localhost:8080",
            timeout=60
        )
        assert llm_config.model == "qwen2"
        assert llm_config.timeout == 60

    def test_custom_agent_config(self):
        """Test custom agent configuration."""
        agent_config = AgentConfig(
            max_iterations=5,
            verbose=False,
            system_prompt="Custom prompt"
        )
        assert agent_config.max_iterations == 5
        assert agent_config.verbose is False
        assert agent_config.system_prompt == "Custom prompt"


class TestConfigLoader:
    """Test configuration loader."""

    def test_load_default_config(self):
        """Test loading default config when file doesn't exist."""
        config = ConfigLoader.load()
        assert config.llm.model == "llama3"

    def test_load_from_file(self):
        """Test loading config from YAML file."""
        yaml_content = """
llm:
  model: qwen2
  base_url: http://localhost:11434
  timeout: 60
agent:
  max_iterations: 5
  verbose: false
memory:
  max_messages: 30
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            config = ConfigLoader.load(path)
            assert config.llm.model == "qwen2"
            assert config.llm.timeout == 60
            assert config.agent.max_iterations == 5
            assert config.agent.verbose is False
            assert config.memory.max_messages == 30
        finally:
            os.unlink(path)

    def test_load_partial_config(self):
        """Test loading partial config (missing fields use defaults)."""
        yaml_content = """
llm:
  model: llama3.1
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = f.name

        try:
            config = ConfigLoader.load(path)
            assert config.llm.model == "llama3.1"
            # Other fields should be defaults
            assert config.agent.max_iterations == 10
        finally:
            os.unlink(path)

    def test_load_empty_file(self):
        """Test loading empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            path = f.name

        try:
            config = ConfigLoader.load(path)
            # Should return default config
            assert config.llm.model == "llama3"
        finally:
            os.unlink(path)

    def test_save_config(self):
        """Test saving config to file."""
        config = Config(
            llm=LLMConfig(model="test_model"),
            agent=AgentConfig(max_iterations=3)
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "config.yaml")
            ConfigLoader.save(config, path)

            # Load and verify
            loaded = ConfigLoader.load(path)
            assert loaded.llm.model == "test_model"
            assert loaded.agent.max_iterations == 3

    def test_load_project_config(self):
        """Test loading the project's config.yaml."""
        config = ConfigLoader.load("config/config.yaml")
        assert config.llm.model == "qwen3.5:9b"
        assert config.llm.base_url == "http://localhost:11434"