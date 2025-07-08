"""Unit tests for BotManager."""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.bot_manager import BotManager, BotInstance
from src.multi_bot_config import MultiBotConfig, BotInstanceConfig, GlobalSettings
from src.config import load_config
from src.service_factory import create_multi_bot_services


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory with test configurations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)
        
        # Create test bot configuration
        bot_config = {
            'bot': {'name': 'test-bot', 'description': 'Test bot'},
            'discord': {'token': 'test-token', 'command_prefix': '!test'},
            'ollama': {'base_url': 'http://localhost:11434', 'model': 'test-model'},
            'system_prompt': 'Test prompt',
            'storage': {'enabled': True, 'path': './data/test'},
            'message': {'max_length': 1900, 'typing_indicator': True},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = config_dir / "test_bot.yaml"
        with open(bot_config_file, 'w') as f:
            import yaml
            yaml.dump(bot_config, f)
        
        # Create multi-bot configuration
        multi_config = {
            'bots': [
                {
                    'name': 'test-bot',
                    'config_file': str(bot_config_file),
                    'channels': ['test-channel']
                }
            ],
            'global_settings': {
                'context_depth': 5,
                'response_delay': '1-2',
                'max_concurrent_responses': 1
            }
        }
        
        multi_config_file = config_dir / "multi_bot.yaml"
        with open(multi_config_file, 'w') as f:
            import yaml
            yaml.dump(multi_config, f)
        
        yield config_dir, multi_config_file


@pytest.fixture
def bot_manager(temp_config_dir):
    """Create a BotManager instance with test configuration."""
    config_dir, multi_config_file = temp_config_dir
    return BotManager(str(multi_config_file))


class TestBotInstance:
    """Test BotInstance dataclass."""
    
    def test_bot_instance_creation(self):
        """Test creating a BotInstance."""
        config = Mock()
        config.bot.name = "test-bot"
        
        instance = BotInstance(
            name="test-bot",
            config=config,
            channels=["test-channel"]
        )
        
        assert instance.name == "test-bot"
        assert instance.config == config
        assert instance.channels == ["test-channel"]
        assert instance.bot is None
        assert instance.is_running is False
        assert instance.last_activity is None
    
    def test_bot_instance_default_channels(self):
        """Test BotInstance with default channels."""
        config = Mock()
        instance = BotInstance(name="test", config=config)
        assert instance.channels == []


class TestMultiBotConfig:
    """Test MultiBotConfig dataclass."""
    
    def test_multibot_config_creation(self):
        """Test creating MultiBotConfig with proper Pydantic models."""
        bot_config = BotInstanceConfig(
            name='test',
            config_file='test.yaml',
            channels=['test']
        )
        global_settings = GlobalSettings(context_depth=10)
        
        config = MultiBotConfig(
            bots=[bot_config],
            global_settings=global_settings
        )
        assert len(config.bots) == 1
        assert config.bots[0].name == 'test'
        assert config.global_settings.context_depth == 10
    
    def test_multibot_config_defaults(self):
        """Test MultiBotConfig with default values."""
        bot_config = BotInstanceConfig(
            name='test',
            config_file='test.yaml',
            channels=['test']
        )
        
        config = MultiBotConfig(bots=[bot_config])  # global_settings gets default
        assert len(config.bots) == 1
        assert config.global_settings.context_depth == 10  # default value


class TestBotManager:
    """Test BotManager class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, bot_manager):
        """Test BotManager initialization with new services."""
        await bot_manager.initialize()
        
        assert bot_manager.multi_bot_config is not None
        assert bot_manager.conversation_state is not None
        assert bot_manager.message_processor is not None
        
        # Check new services created by service factory
        assert bot_manager.orchestrator is not None
        assert bot_manager.coordinator is not None
        assert bot_manager.response_generator is not None
        
        assert len(bot_manager.bot_instances) == 1
        assert 'test-bot' in bot_manager.bot_instances
    
    @pytest.mark.asyncio
    
    
    
    @pytest.mark.asyncio
    async def test_load_bot_configurations(self, bot_manager):
        """Test loading individual bot configurations."""
        await bot_manager.initialize()
        
        # Check that bot instance was created
        assert 'test-bot' in bot_manager.bot_instances
        instance = bot_manager.bot_instances['test-bot']
        assert instance.name == 'test-bot'
        assert instance.channels == ['test-channel']
        assert instance.config is not None
    
    def test_get_bot_status(self, bot_manager):
        """Test getting bot status."""
        # Add a mock bot instance
        mock_config = Mock()
        mock_config.bot.name = "test-bot"
        
        instance = BotInstance(
            name="test-bot",
            config=mock_config,
            is_running=True,
            last_activity=datetime.now()
        )
        bot_manager.bot_instances['test-bot'] = instance
        
        status = bot_manager.get_bot_status()
        assert 'test-bot' in status
        assert status['test-bot']['is_running'] is True
        assert status['test-bot']['config_name'] == 'test-bot'
    
    @pytest.mark.asyncio
    async def test_start_bot_mock(self, bot_manager):
        """Test starting a bot with mocked dependencies."""
        await bot_manager.initialize()
        
        instance = bot_manager.bot_instances['test-bot']
        
        with patch('src.bot_manager.DiscordBot') as mock_discord_bot:
            mock_bot = AsyncMock()
            mock_bot.client = AsyncMock()
            mock_bot.client.start = AsyncMock()
            mock_discord_bot.return_value = mock_bot
            
            await bot_manager._start_bot(instance)
            
            assert instance.is_running is True
            assert instance.bot == mock_bot
            # DiscordBot should be called with orchestrator and channel patterns
            mock_discord_bot.assert_called_once_with(
                config=instance.config,
                orchestrator=bot_manager.orchestrator,
                channel_patterns=instance.channels
            )
            mock_bot.client.start.assert_called_once_with(instance.config.discord.token)
    
    @pytest.mark.asyncio
    async def test_stop_bot_mock(self, bot_manager):
        """Test stopping a bot with mocked dependencies."""
        mock_bot = AsyncMock()
        mock_bot.client = AsyncMock()
        mock_bot.client.close = AsyncMock()
        mock_config = Mock()
        mock_config.bot.name = "test-bot"
        
        instance = BotInstance(
            name="test-bot",
            config=mock_config,
            bot=mock_bot,
            is_running=True
        )
        
        await bot_manager._stop_bot(instance)
        
        assert instance.is_running is False
        assert instance.bot is None
        mock_bot.client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restart_bot(self, bot_manager):
        """Test restarting a bot."""
        await bot_manager.initialize()
        
        with patch.object(bot_manager, '_stop_bot') as mock_stop, \
             patch.object(bot_manager, '_start_bot') as mock_start:
            
            await bot_manager.restart_bot('test-bot')
            
            mock_stop.assert_called_once()
            mock_start.assert_called_once()
    
    def test_restart_bot_not_found(self, bot_manager):
        """Test restarting a non-existent bot."""
        with pytest.raises(ValueError, match="Bot not found"):
            asyncio.run(bot_manager.restart_bot('nonexistent-bot'))
    
    @pytest.mark.asyncio
    async def test_stop_all_bots(self, bot_manager):
        """Test stopping all bots."""
        # Add mock bot instances
        mock_bot1 = AsyncMock()
        mock_bot1.client = AsyncMock()
        mock_bot1.client.close = AsyncMock()
        mock_bot2 = AsyncMock()
        mock_bot2.client = AsyncMock()
        mock_bot2.client.close = AsyncMock()
        
        mock_config1 = Mock()
        mock_config1.bot.name = "bot1"
        mock_config2 = Mock()
        mock_config2.bot.name = "bot2"
        
        instance1 = BotInstance(name="bot1", config=mock_config1, bot=mock_bot1, is_running=True)
        instance2 = BotInstance(name="bot2", config=mock_config2, bot=mock_bot2, is_running=True)
        
        bot_manager.bot_instances = {'bot1': instance1, 'bot2': instance2}
        bot_manager._running = True
        
        await bot_manager.stop_all_bots()
        
        assert bot_manager._running is False
        mock_bot1.client.close.assert_called_once()
        mock_bot2.client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reload_configuration(self, bot_manager):
        """Test reloading configuration."""
        with patch.object(bot_manager, 'stop_all_bots') as mock_stop, \
             patch.object(bot_manager, 'initialize') as mock_init, \
             patch.object(bot_manager, 'start_all_bots') as mock_start:
            
            await bot_manager.reload_configuration()
            
            mock_stop.assert_called_once()
            mock_init.assert_called_once()
            mock_start.assert_called_once()


class TestBotManagerIntegration:
    """Integration tests for BotManager."""
    
    @pytest.mark.asyncio
    async def test_full_initialization_flow(self, temp_config_dir):
        """Test the complete initialization flow."""
        config_dir, multi_config_file = temp_config_dir
        manager = BotManager(str(multi_config_file))
        
        await manager.initialize()
        
        # Verify all components are initialized
        assert manager.multi_bot_config is not None
        assert manager.conversation_state is not None
        assert manager.message_processor is not None
        assert len(manager.bot_instances) == 1
        
        # Verify bot instance configuration
        instance = manager.bot_instances['test-bot']
        assert instance.name == 'test-bot'
        assert instance.channels == ['test-channel']
        assert instance.config.bot.name == 'test-bot'
    
    @pytest.mark.asyncio
    async def test_invalid_bot_config_handling(self, temp_config_dir):
        """Test handling of invalid bot configuration."""
        config_dir, _ = temp_config_dir
        
        # Create multi-bot config with invalid bot config file
        invalid_multi_config = {
            'bots': [
                {
                    'name': 'invalid-bot',
                    'config_file': 'nonexistent.yaml',
                    'channels': ['test']
                }
            ],
            'global_settings': {'context_depth': 5}
        }
        
        invalid_config_file = config_dir / "invalid_multi.yaml"
        with open(invalid_config_file, 'w') as f:
            import yaml
            yaml.dump(invalid_multi_config, f)
        
        manager = BotManager(str(invalid_config_file))
        
        # Should raise exception for invalid bot config files (strict validation)
        with pytest.raises(FileNotFoundError, match="Bot configuration file not found"):
            await manager.initialize()


if __name__ == "__main__":
    pytest.main([__file__])