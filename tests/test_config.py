"""
Tests for configuration system.
"""

import pytest
import tempfile
import os
from pathlib import Path

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
        config = ConfigLoader.load("docs/examples/config.yaml")
        # Just verify the config loads correctly and has expected fields
        assert config.llm.model is not None
        assert len(config.llm.model) > 0
        assert config.llm.base_url is not None


class TestFindConfigFile:
    """Test config file discovery with priority."""

    def test_explicit_path_takes_priority(self):
        """Test that explicitly specified path has highest priority."""
        from nano_agent.cli.main import _find_config_file

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create explicit config
            explicit_config = Path(tmpdir) / "explicit.yaml"
            explicit_config.write_text("llm:\n  model: explicit_model\n")

            # Create global config (should be ignored)
            global_dir = Path(tmpdir) / "home" / ".nano_agent"
            global_dir.mkdir(parents=True)
            global_config = global_dir / "config.yaml"
            global_config.write_text("llm:\n  model: global_model\n")

            # Create local config (should be ignored)
            local_dir = Path(tmpdir) / "project" / ".nano_agent"
            local_dir.mkdir(parents=True)
            local_config = local_dir / "config.yaml"
            local_config.write_text("llm:\n  model: local_model\n")

            # Test with explicit path
            found, source = _find_config_file(str(explicit_config))
            assert found == explicit_config
            assert "specified" in source

    def test_global_config_priority(self):
        """Test that global config has priority over local config."""
        from nano_agent.cli.main import _find_config_file

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create global config
            global_dir = Path(tmpdir) / ".nano_agent"
            global_dir.mkdir(parents=True)
            global_config = global_dir / "config.yaml"
            global_config.write_text("llm:\n  model: global_model\n")

            # Create local config
            local_dir = Path(tmpdir) / "project" / ".nano_agent"
            local_dir.mkdir(parents=True)
            local_config = local_dir / "config.yaml"
            local_config.write_text("llm:\n  model: local_model\n")

            # Mock home directory
            import os
            original_home = os.environ.get("HOME")
            try:
                os.environ["HOME"] = tmpdir
                # Change to project directory
                original_cwd = os.getcwd()
                os.chdir(Path(tmpdir) / "project")

                found, source = _find_config_file()
                assert found == global_config
                assert "global" in source
            finally:
                os.environ["HOME"] = original_home or ""
                os.chdir(original_cwd)

    def test_local_config_when_no_global(self):
        """Test that local config is used when no global config exists."""
        from nano_agent.cli.main import _find_config_file

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only local config (no global)
            local_dir = Path(tmpdir) / ".nano_agent"
            local_dir.mkdir(parents=True)
            local_config = local_dir / "config.yaml"
            local_config.write_text("llm:\n  model: local_model\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                found, source = _find_config_file()
                # Resolve paths for comparison (macOS temp dirs use symlinks)
                assert found.resolve() == local_config.resolve()
                assert "local" in source
            finally:
                os.chdir(original_cwd)

    def test_no_config_returns_none(self):
        """Test that None is returned when no config file exists."""
        from nano_agent.cli.main import _find_config_file

        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            original_home = os.environ.get("HOME")
            try:
                os.chdir(tmpdir)
                os.environ["HOME"] = tmpdir
                found, source = _find_config_file()
                assert found is None
                assert "default" in source
            finally:
                os.chdir(original_cwd)
                os.environ["HOME"] = original_home or ""


class TestConfigMerge:
    """Test configuration merge logic."""

    def test_merge_adds_missing_keys(self):
        """Test that merge adds missing keys from default."""
        from nano_agent.cli.main import _merge_config

        default = {
            "llm": {"model": "default_model", "timeout": 120},
            "agent": {"max_iterations": 10},
        }
        existing = {
            "llm": {"model": "custom_model"},
        }

        merged = _merge_config(default, existing)

        assert merged["llm"]["model"] == "custom_model"  # Preserved
        assert merged["llm"]["timeout"] == 120  # Added from default
        assert merged["agent"]["max_iterations"] == 10  # Added from default

    def test_merge_preserves_user_values(self):
        """Test that merge preserves user-modified values."""
        from nano_agent.cli.main import _merge_config

        default = {
            "llm": {"model": "default_model", "timeout": 120},
            "memory": {"type": "short_term"},
        }
        existing = {
            "llm": {"model": "custom_model", "timeout": 60},
            "memory": {"type": "hybrid"},
        }

        merged = _merge_config(default, existing)

        assert merged["llm"]["model"] == "custom_model"  # User value
        assert merged["llm"]["timeout"] == 60  # User value
        assert merged["memory"]["type"] == "hybrid"  # User value

    def test_merge_deep_nested(self):
        """Test that merge works with deeply nested configs."""
        from nano_agent.cli.main import _merge_config

        default = {
            "llm": {
                "model": "default",
                "extra": {"param1": "val1", "param2": "val2"}
            }
        }
        existing = {
            "llm": {
                "model": "custom",
                "extra": {"param1": "custom_val1"}
            }
        }

        merged = _merge_config(default, existing)

        assert merged["llm"]["model"] == "custom"
        assert merged["llm"]["extra"]["param1"] == "custom_val1"
        assert merged["llm"]["extra"]["param2"] == "val2"  # Added from default