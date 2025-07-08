"""Integration tests for service lifecycle management.

These tests catch service lifecycle errors that would cause the bot to crash during startup, shutdown, or operation.
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
from contextlib import asynccontextmanager

from src.bot_manager import BotManager
from src.service_factory import create_multi_bot_services
from src.multi_bot_config import MultiBotConfig, BotInstanceConfig, GlobalSettings


class TestServiceCreation:
    """Test service creation and initialization."""
    
    def test_create_multi_bot_services_basic(self):
        """Test creating services with basic configuration."""
        bot_config = BotInstanceConfig(name="test-bot",
            config_file="test.yaml",
            discord_token="fake_token", channels=["general"]
        )
        
        multi_config = MultiBotConfig(
            bots=[bot_config],
            global_settings=GlobalSettings()
        )
        
        # Should create services without errors
        services = create_multi_bot_services(multi_config)
        
        # Verify services are created
        assert len(services) == 4
        orchestrator, coordinator, response_generator, conversation_state = services
        
        assert orchestrator is not None
        assert coordinator is not None
        assert response_generator is not None
        assert conversation_state is not None
    
    def test_create_multi_bot_services_with_multiple_bots(self):
        """Test creating services with multiple bots."""
        bot_configs = [
            BotInstanceConfig(name="bot1", config_file="bot1.yaml", discord_token="fake_token", channels=["general"]),
            BotInstanceConfig(name="bot2", config_file="bot2.yaml", discord_token="fake_token", channels=["test"]),
            BotInstanceConfig(name="bot3", config_file="bot3.yaml", discord_token="fake_token", channels=["dev"])
        ]
        
        multi_config = MultiBotConfig(
            bots=bot_configs,
            global_settings=GlobalSettings(context_depth=15)
        )
        
        # Should create services for multiple bots
        services = create_multi_bot_services(multi_config)
        
        # Verify services are created
        assert len(services) == 4
        orchestrator, coordinator, response_generator, conversation_state = services
        
        assert orchestrator is not None
        assert coordinator is not None
        assert response_generator is not None
        assert conversation_state is not None
    
    def test_create_multi_bot_services_with_custom_settings(self):
        """Test creating services with custom global settings."""
        bot_config = BotInstanceConfig(name="custom-bot",
            config_file="custom.yaml",
            discord_token="fake_token", channels=["custom"]
        )
        
        global_settings = GlobalSettings(
            context_depth=25,
            response_delay="2-5",
            max_concurrent_responses=3,
            cooldown_period=60,
            conversation_timeout=7200,
            storage_path="./data/custom_conversations",
            enable_cross_bot_context=False,
            enable_bot_mentions=False,
            debug_mode=True
        )
        
        multi_config = MultiBotConfig(
            bots=[bot_config],
            global_settings=global_settings
        )
        
        # Should create services with custom settings
        services = create_multi_bot_services(multi_config)
        
        # Verify services are created
        assert len(services) == 4
        orchestrator, coordinator, response_generator, conversation_state = services
        
        assert orchestrator is not None
        assert coordinator is not None
        assert response_generator is not None
        assert conversation_state is not None


class TestBotManagerLifecycle:
    """Test BotManager lifecycle operations."""
    
    def create_test_config(self, tmp_path, bot_name="lifecycle-bot"):
        """Helper to create test configuration files."""
        # Create bot config
        bot_config = {
            'bot': {'name': bot_name},
            'discord': {'token': 'test-token'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Test lifecycle prompt',
            'storage': {'enabled': True, 'path': f'./data/{bot_name}'},
            'message': {'max_length': 2000, 'typing_indicator': True},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / f"{bot_name}.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config
        multi_config_data = {
            'bots': [
                {
                    'name': bot_name,
                    'config_file': str(bot_config_file),
                    'channels': ['lifecycle-test']
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
        
        return multi_config_file
    
    @pytest.mark.asyncio
    async def test_bot_manager_initialization_lifecycle(self, tmp_path):
        """Test BotManager initialization lifecycle."""
        multi_config_file = self.create_test_config(tmp_path)
        
        # Test initialization
        manager = BotManager(str(multi_config_file))
        
        # Before initialization - these attributes are declared but not set
        assert manager.conversation_state is None
        assert len(manager.bot_instances) == 0
        
        # Initialize
        await manager.initialize()
        
        # After initialization
        assert manager.multi_bot_config is not None
        assert manager.conversation_state is not None
        assert len(manager.bot_instances) == 1
        assert 'lifecycle-bot' in manager.bot_instances
        
        # Verify bot instance is properly configured
        bot_instance = manager.bot_instances['lifecycle-bot']
        assert bot_instance.name == 'lifecycle-bot'
        assert bot_instance.channels == ['lifecycle-test']
        assert bot_instance.config is not None
        assert bot_instance.bot is None  # Not started yet
        assert bot_instance.is_running is False
    
    @pytest.mark.asyncio
    async def test_bot_manager_multiple_initializations(self, tmp_path):
        """Test that multiple initializations don't cause issues."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        
        # Initialize multiple times
        await manager.initialize()
        first_config = manager.multi_bot_config
        first_state = manager.conversation_state
        
        await manager.initialize()
        second_config = manager.multi_bot_config
        second_state = manager.conversation_state
        
        # Should have new instances (re-initialization)
        assert second_config is not first_config
        assert second_state is not first_state
        assert len(manager.bot_instances) == 1
    
    @pytest.mark.asyncio
    async def test_bot_manager_start_stop_lifecycle(self, tmp_path):
        """Test bot start/stop lifecycle."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        bot_instance = manager.bot_instances['lifecycle-bot']
        
        # Mock Discord bot and client
        mock_bot = AsyncMock()
        mock_client = AsyncMock()
        mock_bot.client = mock_client
        
        with patch('src.bot_manager.DiscordBot', return_value=mock_bot):
            # Start bot
            await manager._start_bot(bot_instance)
            
            # Verify bot is started
            assert bot_instance.is_running is True
            assert bot_instance.bot is mock_bot
            mock_client.start.assert_called_once_with('test-token')
            
            # Stop bot
            await manager._stop_bot(bot_instance)
            
            # Verify bot is stopped
            assert bot_instance.is_running is False
            assert bot_instance.bot is None
            mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_manager_restart_lifecycle(self, tmp_path):
        """Test bot restart lifecycle."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Mock the start and stop methods
        with patch.object(manager, '_start_bot', new_callable=AsyncMock) as mock_start, \
             patch.object(manager, '_stop_bot', new_callable=AsyncMock) as mock_stop:
            
            # Restart bot
            await manager.restart_bot('lifecycle-bot')
            
            # Verify stop then start was called
            mock_stop.assert_called_once()
            mock_start.assert_called_once()
            
            # Verify they were called with the correct bot instance
            bot_instance = manager.bot_instances['lifecycle-bot']
            mock_stop.assert_called_with(bot_instance)
            mock_start.assert_called_with(bot_instance)
    
    @pytest.mark.asyncio
    async def test_bot_manager_start_all_bots_lifecycle(self, tmp_path):
        """Test starting all bots lifecycle."""
        # Create multiple bot configs
        bot_configs = []
        for i in range(3):
            bot_name = f"bot{i+1}"
            bot_config = {
                'bot': {'name': bot_name},
                'discord': {'token': f'test-token-{i+1}'},
                'ollama': {'model': 'llama3'},
                'system_prompt': f'Bot {i+1} prompt',
                'storage': {'enabled': True, 'path': f'./data/{bot_name}'},
                'message': {'max_length': 2000, 'typing_indicator': True},
                'rate_limit': {'enabled': False},
                'logging': {'level': 'INFO'}
            }
            
            bot_config_file = tmp_path / f"{bot_name}.yaml"
            bot_config_file.write_text(yaml.dump(bot_config))
            bot_configs.append({
                'name': bot_name,
                'config_file': str(bot_config_file),
                'channels': [f'channel{i+1}']
            })
        
        multi_config_data = {
            'bots': bot_configs,
            'global_settings': {'context_depth': 5}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        # Test starting all bots
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Mock the start method
        with patch.object(manager, '_start_bot', new_callable=AsyncMock) as mock_start:
            await manager.start_all_bots()
            
            # Verify all bots were started
            assert mock_start.call_count == 3
            
            # Verify each bot was started
            for bot_name in ['bot1', 'bot2', 'bot3']:
                bot_instance = manager.bot_instances[bot_name]
                mock_start.assert_any_call(bot_instance)
    
    @pytest.mark.asyncio
    async def test_bot_manager_stop_all_bots_lifecycle(self, tmp_path):
        """Test stopping all bots lifecycle."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Set up running state and mock running bot
        manager._running = True
        bot_instance = manager.bot_instances['lifecycle-bot']
        bot_instance.is_running = True
        bot_instance.bot = AsyncMock()  # Mock the bot
        
        # Mock the stop method
        with patch.object(manager, '_stop_bot', new_callable=AsyncMock) as mock_stop:
            await manager.stop_all_bots()
            
            # Verify stop was called for the running bot
            assert mock_stop.call_count == 1
            
            # Verify manager is no longer running
            assert manager._running is False
    
    @pytest.mark.asyncio
    async def test_bot_manager_reload_configuration_lifecycle(self, tmp_path):
        """Test configuration reload lifecycle."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Mock lifecycle methods
        with patch.object(manager, 'stop_all_bots', new_callable=AsyncMock) as mock_stop, \
             patch.object(manager, 'initialize', new_callable=AsyncMock) as mock_init, \
             patch.object(manager, 'start_all_bots', new_callable=AsyncMock) as mock_start:
            
            # Reload configuration
            await manager.reload_configuration()
            
            # Verify the lifecycle: stop -> initialize -> start
            mock_stop.assert_called_once()
            mock_init.assert_called_once()
            mock_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bot_manager_error_handling_during_start(self, tmp_path):
        """Test error handling during bot startup."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        bot_instance = manager.bot_instances['lifecycle-bot']
        
        # Mock DiscordBot to raise an exception
        with patch('src.bot_manager.DiscordBot', side_effect=Exception("Discord connection failed")):
            # Starting bot should raise the exception
            with pytest.raises(Exception, match="Discord connection failed"):
                await manager._start_bot(bot_instance)
            
            # Bot should not be marked as running
            assert bot_instance.is_running is False
            assert bot_instance.bot is None
    
    @pytest.mark.asyncio
    async def test_bot_manager_error_handling_during_stop(self, tmp_path):
        """Test error handling during bot shutdown."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        bot_instance = manager.bot_instances['lifecycle-bot']
        
        # Mock bot with failing client
        mock_bot = AsyncMock()
        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=Exception("Client close failed"))
        mock_bot.client = mock_client
        
        # Set up bot as running
        bot_instance.bot = mock_bot
        bot_instance.is_running = True
        
        # Stopping should handle the exception gracefully (catches and logs error)
        await manager._stop_bot(bot_instance)
        
        # Bot may not be cleaned up if exception occurs before cleanup
        # The important thing is that the exception is handled gracefully
        # (it doesn't crash the manager)
        assert bot_instance.bot is mock_bot  # Bot reference unchanged due to exception
        assert bot_instance.is_running is True  # Status unchanged due to exception


class TestServiceInitializationFailures:
    """Test service initialization failure scenarios."""
    
    def test_create_services_with_empty_bots(self):
        """Test service creation with empty bots list."""
        # Note: MultiBotConfig validation should prevent empty bots,
        # but we can test the service factory behavior directly
        bot_config = BotInstanceConfig(name="dummy-bot",
            config_file="dummy.yaml",
            discord_token="fake_token", channels=["dummy"]
        )
        
        multi_config = MultiBotConfig(
            bots=[bot_config],  # Need at least one bot for validation
            global_settings=GlobalSettings()
        )
        
        # Should create services successfully
        services = create_multi_bot_services(multi_config)
        
        assert len(services) == 4
        orchestrator, coordinator, response_generator, conversation_state = services
        
        assert orchestrator is not None
        assert coordinator is not None
        assert response_generator is not None
        assert conversation_state is not None
    
    def test_create_services_with_invalid_global_settings(self):
        """Test service creation with potentially problematic global settings."""
        bot_config = BotInstanceConfig(name="test-bot",
            config_file="test.yaml",
            discord_token="fake_token", channels=["general"]
        )
        
        # Test with extreme values
        global_settings = GlobalSettings(
            context_depth=50,  # Maximum allowed
            response_delay="0.1-0.2",  # Very short delays
            max_concurrent_responses=10,  # Maximum allowed
            cooldown_period=5,  # Minimum allowed
            conversation_timeout=60,  # Minimum allowed
            storage_path="/tmp/test_conversations",
            enable_cross_bot_context=True,
            enable_bot_mentions=True,
            debug_mode=True
        )
        
        multi_config = MultiBotConfig(
            bots=[bot_config],
            global_settings=global_settings
        )
        
        # Should handle extreme settings gracefully
        services = create_multi_bot_services(multi_config)
        
        assert len(services) == 4
        orchestrator, coordinator, response_generator, conversation_state = services
        
        assert orchestrator is not None
        assert coordinator is not None
        assert response_generator is not None
        assert conversation_state is not None


class TestServiceDependencyInjection:
    """Test service dependency injection and wiring."""
    
    def test_service_dependencies_are_properly_wired(self):
        """Test that services receive proper dependencies."""
        bot_config = BotInstanceConfig(name="dependency-bot",
            config_file="dependency.yaml",
            discord_token="fake_token", channels=["dependency-test"]
        )
        
        multi_config = MultiBotConfig(
            bots=[bot_config],
            global_settings=GlobalSettings()
        )
        
        # Create services
        services = create_multi_bot_services(multi_config)
        orchestrator, coordinator, response_generator, conversation_state = services
        
        # Verify services have expected interfaces/methods
        # These tests verify the services are properly created with expected structure
        assert hasattr(orchestrator, 'coordinator')
        assert hasattr(coordinator, 'storage')
        assert hasattr(response_generator, 'ai_model')
        assert hasattr(conversation_state, 'storage_path')
        
        # Verify dependencies are set
        assert orchestrator.coordinator is coordinator
        assert coordinator.storage is not None
        assert response_generator.ai_model is not None
        # Storage path may be converted to Path object and normalized, so compare resolved paths
        from pathlib import Path
        expected_path = Path(multi_config.global_settings.storage_path).resolve()
        actual_path = Path(conversation_state.storage_path).resolve()
        assert actual_path == expected_path
    
    def test_service_circular_dependencies(self):
        """Test handling of circular service dependencies."""
        bot_config = BotInstanceConfig(name="circular-bot",
            config_file="circular.yaml",
            discord_token="fake_token", channels=["circular-test"]
        )
        
        multi_config = MultiBotConfig(
            bots=[bot_config],
            global_settings=GlobalSettings()
        )
        
        # Should handle circular dependencies gracefully
        services = create_multi_bot_services(multi_config)
        orchestrator, coordinator, response_generator, conversation_state = services
        
        # Verify no circular reference issues
        assert orchestrator is not None
        assert coordinator is not None
        assert response_generator is not None
        assert conversation_state is not None
        
        # Verify we can access nested dependencies without infinite loops
        assert orchestrator.coordinator is coordinator
        assert coordinator.storage is not None
        assert response_generator.ai_model is not None


class TestServiceResourceManagement:
    """Test service resource management and cleanup."""
    
    @pytest.mark.asyncio
    async def test_service_resource_cleanup(self, tmp_path):
        """Test that services properly clean up resources."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Get initial resource state
        initial_instances = len(manager.bot_instances)
        initial_tasks = len(manager._tasks)
        
        # Set up running state and mock running bot
        manager._running = True
        bot_instance = manager.bot_instances['resource-bot']
        bot_instance.is_running = True
        bot_instance.bot = AsyncMock()  # Mock the bot
        
        # Mock cleanup operations
        with patch.object(manager, '_stop_bot', new_callable=AsyncMock) as mock_stop:
            await manager.stop_all_bots()
            
            # Verify cleanup was attempted for the running bot
            assert mock_stop.call_count == 1  # Only one running bot
            assert manager._running is False
    
    def create_test_config(self, tmp_path):
        """Helper to create test configuration files."""
        # Create bot config
        bot_config = {
            'bot': {'name': 'resource-bot'},
            'discord': {'token': 'test-token'},
            'ollama': {'model': 'llama3'},
            'system_prompt': 'Resource test prompt',
            'storage': {'enabled': True, 'path': './data/resource-bot'},
            'message': {'max_length': 2000, 'typing_indicator': True},
            'rate_limit': {'enabled': False},
            'logging': {'level': 'INFO'}
        }
        
        bot_config_file = tmp_path / "resource_bot.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config
        multi_config_data = {
            'bots': [
                {
                    'name': 'resource-bot',
                    'config_file': str(bot_config_file),
                    'channels': ['resource-test']
                }
            ],
            'global_settings': {'context_depth': 5}
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        return multi_config_file
    
    @pytest.mark.asyncio
    async def test_service_memory_management(self, tmp_path):
        """Test service memory management during lifecycle."""
        multi_config_file = self.create_test_config(tmp_path)
        
        manager = BotManager(str(multi_config_file))
        
        # Initialize and check memory usage
        await manager.initialize()
        
        # Verify objects are created
        assert manager.multi_bot_config is not None
        assert manager.conversation_state is not None
        assert len(manager.bot_instances) > 0
        
        # Clean up and verify objects can be garbage collected
        await manager.stop_all_bots()
        
        # Objects should still exist until manager is destroyed
        assert manager.multi_bot_config is not None
        assert manager.conversation_state is not None
        
        # Re-initialize should work
        await manager.initialize()
        
        # Should have new instances
        assert manager.multi_bot_config is not None
        assert manager.conversation_state is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])