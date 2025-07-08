"""Tests for config.py validation and error handling."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from src.config import DiscordConfig, Config, load_config


class TestDiscordConfigValidation:
    """Test DiscordConfig validation error scenarios."""
    
    def test_empty_token_validation_error(self):
        """Test that empty token raises validation error."""
        with pytest.raises(ValueError, match="Discord token must be set and not be a placeholder"):
            DiscordConfig(token="", command_prefix="!")
    
    def test_placeholder_token_validation_error(self):
        """Test that placeholder token raises validation error."""
        with pytest.raises(ValueError, match="Discord token must be set and not be a placeholder"):
            DiscordConfig(token="YOUR_DISCORD_TOKEN_HERE", command_prefix="!")
    
    def test_your_prefix_token_validation_error(self):
        """Test that any token starting with 'YOUR_' raises validation error."""
        with pytest.raises(ValueError, match="Discord token must be set and not be a placeholder"):
            DiscordConfig(token="YOUR_SECRET_TOKEN", command_prefix="!")
    
    def test_valid_token_passes_validation(self):
        """Test that valid token passes validation."""
        config = DiscordConfig(token="valid_token_123", command_prefix="!")
        assert config.token == "valid_token_123"
        assert config.command_prefix == "!"


class TestConfigLoading:
    """Test config loading error scenarios."""
    
    def test_load_config_file_not_found(self):
        """Test that missing config file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")
    
    def test_load_config_invalid_yaml(self, tmp_path):
        """Test that invalid YAML raises appropriate error."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))
    
    def test_load_config_missing_required_fields(self, tmp_path):
        """Test that config missing required fields raises validation error."""
        config_file = tmp_path / "incomplete.yaml"
        incomplete_config = {
            "bot": {"name": "test"},
            # Missing discord, ollama, etc.
        }
        config_file.write_text(yaml.dump(incomplete_config))
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            load_config(str(config_file))
    
    @patch('src.config.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_config_file_permission_error(self, mock_file, mock_exists):
        """Test that file permission error is handled appropriately."""
        mock_exists.return_value = True
        mock_file.side_effect = PermissionError("Permission denied")
        
        with pytest.raises(PermissionError):
            load_config("/some/config.yaml")


class TestConfigWithEnvironmentVariables:
    """Test config loading with environment variable substitution."""
    
    def test_config_with_valid_env_var(self, tmp_path):
        """Test config loading with environment variable substitution."""
        config_file = tmp_path / "env_config.yaml"
        config_content = {
            "bot": {"name": "test-bot"},
            "discord": {"token": "${TEST_TOKEN}", "command_prefix": "!"},
            "ollama": {"model": "llama3", "base_url": "http://localhost:11434"},
            "storage": {"path": "./data"},
            "message": {"max_length": 2000},
            "rate_limit": {"enabled": False},
            "logging": {"level": "INFO"}
        }
        config_file.write_text(yaml.dump(config_content))
        
        # Test with environment variable set
        with patch.dict('os.environ', {'TEST_TOKEN': 'valid_token_123'}):
            config = load_config(str(config_file))
            assert config.discord.token == "valid_token_123"
    
    def test_config_with_missing_env_var_keeps_placeholder(self, tmp_path):
        """Test that missing environment variables keep the placeholder."""
        config_file = tmp_path / "env_config.yaml"
        config_content = {
            "bot": {"name": "test-bot"},
            "discord": {"token": "${MISSING_TOKEN}", "command_prefix": "!"},
            "ollama": {"model": "llama3", "base_url": "http://localhost:11434"},
            "storage": {"path": "./data"},
            "message": {"max_length": 2000},
            "rate_limit": {"enabled": False},
            "logging": {"level": "INFO"}
        }
        config_file.write_text(yaml.dump(config_content))
        
        # Should keep the placeholder since env var doesn't exist
        config = load_config(str(config_file))
        assert config.discord.token == "${MISSING_TOKEN}"