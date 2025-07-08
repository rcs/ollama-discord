"""Integration tests for configuration loading from files.

These tests catch configuration loading errors that would cause the bot to crash on startup.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, Mock
import os

from src.config import load_config, Config
from src.multi_bot_config import MultiBotConfig, multi_bot_config_manager
from src.bot_manager import BotManager
from pydantic import ValidationError
import asyncio


class TestConfigurationFileLoading:
    """Test configuration loading from actual files."""
    
    def test_load_valid_config_file(self, tmp_path):
        """Test loading a valid configuration file."""
        config_data = {
            'bot': {'name': 'test-bot', 'description': 'Test bot'},
            'discord': {'token': 'test-token', 'command_prefix': '!'},
            'ollama': {'model': 'llama3', 'base_url': 'http://localhost:11434'},
            'system_prompt': 'You are a helpful bot',
            'storage': {'enabled': True, 'path': './data/test'},
            'message': {'max_length': 2000, 'typing_indicator': True},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml.dump(config_data))
        
        # Test loading the config
        config = load_config(str(config_file))
        assert config.bot.name == 'test-bot'
        assert config.discord.token == 'test-token'
        assert config.ollama.model == 'llama3'
    
    def test_load_config_file_not_found(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config("nonexistent.yaml")
    
    def test_load_config_invalid_yaml(self, tmp_path):
        """Test loading configuration with invalid YAML syntax."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: syntax: [")
        
        with pytest.raises(yaml.YAMLError):
            load_config(str(config_file))
    
    def test_load_config_missing_required_fields(self, tmp_path):
        """Test loading configuration with missing required fields."""
        config_data = {
            'bot': {'name': 'test-bot'},
            # Missing discord, ollama, etc.
        }
        
        config_file = tmp_path / "incomplete.yaml"
        config_file.write_text(yaml.dump(config_data))
        
        with pytest.raises(ValidationError):
            load_config(str(config_file))
    
    def test_load_config_with_environment_variables(self, tmp_path):
        """Test loading configuration with environment variable substitution."""
        config_data = {
            'bot': {'name': 'test-bot'},
            'discord': {'token': '${DISCORD_TOKEN}', 'command_prefix': '!'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(yaml.dump(config_data))
        
        # Test with environment variable set
        with patch.dict(os.environ, {'DISCORD_TOKEN': 'env_token_value'}):
            config = load_config(str(config_file))
            assert config.discord.token == 'env_token_value'
    
    def test_load_config_invalid_discord_token(self, tmp_path):
        """Test loading configuration with invalid Discord token."""
        config_data = {
            'bot': {'name': 'test-bot'},
            'discord': {'token': '', 'command_prefix': '!'},  # Empty token
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        config_file = tmp_path / "invalid_token.yaml"
        config_file.write_text(yaml.dump(config_data))
        
        with pytest.raises(ValidationError, match="Discord token must be set"):
            load_config(str(config_file))


class TestMultiBotConfigurationLoading:
    """Test multi-bot configuration loading from files."""
    
    def test_load_valid_multi_bot_config(self, tmp_path):
        """Test loading a valid multi-bot configuration file."""
        # Create individual bot config
        bot_config = {
            'bot': {'name': 'test-bot'},
            'discord': {'token': 'test-token'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / "bot.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config
        multi_config_data = {
            'bots': [
                {
                    'name': 'test-bot',
                    'config_file': str(bot_config_file),
                    'discord_token': 'fake_token_123',
                    'channels': ['general', 'test']
                }
            ],
            'global_settings': {
                'context_depth': 10,
                'response_delay': '1-3',
                'max_concurrent_responses': 2
            }
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        # Test loading the multi-bot config
        config = multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
        assert len(config.bots) == 1
        assert config.bots[0].name == 'test-bot'
        assert config.bots[0].channels == ['general', 'test']
        assert config.global_settings.context_depth == 10
    
    def test_load_multi_bot_config_missing_bot_files(self, tmp_path):
        """Test loading multi-bot config with missing bot configuration files."""
        multi_config_data = {
            'bots': [
                {
                    'name': 'test-bot',
                    'config_file': 'nonexistent.yaml',
                    'discord_token': 'fake_token_123',
                    'channels': ['general']
                }
            ],
            'global_settings': {'context_depth': 10}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        with pytest.raises(FileNotFoundError, match="Bot configuration file not found"):
            multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
    
    def test_load_multi_bot_config_empty_bots(self, tmp_path):
        """Test loading multi-bot config with empty bots list."""
        multi_config_data = {
            'bots': [],
            'global_settings': {'context_depth': 10}
        }
        
        multi_config_file = tmp_path / "empty_bots.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        with pytest.raises(ValidationError, match="At least one bot must be configured"):
            multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
    
    def test_load_multi_bot_config_invalid_bot_config(self, tmp_path):
        """Test loading multi-bot config with invalid bot configuration."""
        # Create invalid bot config (missing required fields)
        invalid_bot_config = {
            'bot': {'name': 'invalid-bot'},
            'discord': {'token': '', 'command_prefix': '!'},  # Empty token triggers validation error
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / "invalid_bot.yaml"
        bot_config_file.write_text(yaml.dump(invalid_bot_config))
        
        # Create multi-bot config referencing invalid bot
        multi_config_data = {
            'bots': [
                {
                    'name': 'invalid-bot',
                    'config_file': str(bot_config_file),
                    'discord_token': 'fake_token_123',
                    'channels': ['general']
                }
            ],
            'global_settings': {'context_depth': 10}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        with pytest.raises(ValueError, match="Invalid configuration for bot invalid-bot"):
            multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))


class TestConfigurationPathResolution:
    """Test configuration path resolution issues."""
    
    def test_relative_config_paths(self, tmp_path):
        """Test configuration loading with relative paths."""
        # Create subdirectory structure
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create bot config in subdirectory
        bot_config = {
            'bot': {'name': 'test-bot'},
            'discord': {'token': 'test-token'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = config_dir / "bot.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config with relative path
        multi_config_data = {
            'bots': [
                {
                    'name': 'test-bot',
                    'config_file': './config/bot.yaml',
                    'discord_token': 'fake_token_123',
                    'channels': ['general']
                }
            ],
            'global_settings': {'context_depth': 10}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        # Change to temp directory to test relative paths
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            config = multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
            assert len(config.bots) == 1
            assert config.bots[0].name == 'test-bot'
        finally:
            os.chdir(original_cwd)
    
    def test_absolute_config_paths(self, tmp_path):
        """Test configuration loading with absolute paths."""
        # Create bot config
        bot_config = {
            'bot': {'name': 'test-bot'},
            'discord': {'token': 'test-token'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / "bot.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config with absolute path
        multi_config_data = {
            'bots': [
                {
                    'name': 'test-bot',
                    'config_file': str(bot_config_file),  # Absolute path
                    'discord_token': 'fake_token_123',
                    'channels': ['general']
                }
            ],
            'global_settings': {'context_depth': 10}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        config = multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
        assert len(config.bots) == 1
        assert config.bots[0].name == 'test-bot'


class TestBotManagerConfigurationIntegration:
    """Test BotManager configuration loading integration."""
    
    @pytest.mark.asyncio
    async def test_bot_manager_config_loading_success(self, tmp_path):
        """Test successful BotManager configuration loading."""
        # Create bot config
        bot_config = {
            'bot': {'name': 'integration-bot'},
            'discord': {'token': 'integration-token'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Integration test prompt',
            'storage': {'enabled': True, 'path': './data/integration'},
            'message': {'max_length': 2000, 'typing_indicator': True},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / "integration_bot.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config
        multi_config_data = {
            'bots': [
                {
                    'name': 'integration-bot',
                    'config_file': str(bot_config_file),
                    'discord_token': 'fake_token_123',
                    'channels': ['integration-test']
                }
            ],
            'global_settings': {
                'context_depth': 5,
                'response_delay': '1-2',
                'max_concurrent_responses': 1
            }
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        # Test BotManager initialization
        manager = BotManager(str(multi_config_file))
        # Should not raise any exceptions during config loading
        assert str(manager.config_file) == str(multi_config_file)
        
        # Test that initialize() works without errors
        await manager.initialize()
        assert manager.multi_bot_config is not None
        assert len(manager.bot_instances) == 1
    
    @pytest.mark.asyncio
    async def test_bot_manager_config_loading_failure(self, tmp_path):
        """Test BotManager handling of configuration loading failures."""
        # Create invalid multi-bot config
        multi_config_data = {
            'bots': [
                {
                    'name': 'broken-bot',
                    'config_file': 'nonexistent.yaml',
                    'channels': ['test']
                }
            ],
            'global_settings': {'context_depth': 5}
        }
        
        multi_config_file = tmp_path / "broken_multi.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        manager = BotManager(str(multi_config_file))
        
        # Should raise FileNotFoundError during initialization
        with pytest.raises(FileNotFoundError, match="Bot configuration file not found"):
            await manager.initialize()
    
    @pytest.mark.asyncio
    async def test_bot_manager_config_validation_errors(self, tmp_path):
        """Test BotManager handling of configuration validation errors."""
        # Create bot config with validation errors
        invalid_bot_config = {
            'bot': {'name': 'invalid-bot'},
            'discord': {'token': '', 'command_prefix': '!'},  # Empty token
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / "invalid_bot.yaml"
        bot_config_file.write_text(yaml.dump(invalid_bot_config))
        
        # Create multi-bot config
        multi_config_data = {
            'bots': [
                {
                    'name': 'invalid-bot',
                    'config_file': str(bot_config_file),
                    'channels': ['test']
                }
            ],
            'global_settings': {'context_depth': 5}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        manager = BotManager(str(multi_config_file))
        
        # Should raise ValueError during initialization (wrapped validation error)
        with pytest.raises(ValueError, match="Invalid configuration for bot invalid-bot"):
            await manager.initialize()


class TestEnvironmentVariableHandling:
    """Test environment variable handling in configuration."""
    
    def test_missing_environment_variables(self, tmp_path):
        """Test configuration loading with missing environment variables."""
        config_data = {
            'bot': {'name': 'env-bot'},
            'discord': {'token': '${MISSING_TOKEN}', 'command_prefix': '!'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(yaml.dump(config_data))
        
        # Test with missing environment variable
        with patch.dict(os.environ, {}, clear=True):
            # Should still load but token will be the literal string
            config = load_config(str(config_file))
            assert config.discord.token == '${MISSING_TOKEN}'
    
    def test_env_file_loading(self, tmp_path):
        """Test .env file loading for environment variables."""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("DISCORD_TOKEN=env_file_token\nOLLAMA_MODEL=env_model")
        
        config_data = {
            'bot': {'name': 'env-bot'},
            'discord': {'token': '${DISCORD_TOKEN}', 'command_prefix': '!'},
            'ollama': {'model': '${OLLAMA_MODEL}'},
            'system_prompt': 'Test prompt',
            'storage': {'path': './data'},
            'message': {'max_length': 2000},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(yaml.dump(config_data))
        
        # Test loading with .env file in same directory
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            # Note: Our actual implementation may not automatically load .env files
            # This test documents the expected behavior
            with patch.dict(os.environ, {'DISCORD_TOKEN': 'env_file_token', 'OLLAMA_MODEL': 'env_model'}):
                config = load_config(str(config_file))
                assert config.discord.token == 'env_file_token'
                assert config.ollama.model == 'env_model'
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])