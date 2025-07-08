"""End-to-end integration tests for the Discord bot system.

These tests verify the complete system functionality from configuration loading to message processing.
"""

import pytest
import asyncio
import tempfile
import yaml
import os
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, MagicMock

import discord

from src.bot_manager import BotManager
from src.multi_bot_config import multi_bot_config_manager
from src.bot import DiscordBot
from src.config import load_config


class TestEndToEndIntegration:
    """Test complete end-to-end integration scenarios."""
    
    def create_complete_test_setup(self, tmp_path):
        """Create a complete test setup with all configuration files."""
        # Create individual bot configurations
        bots = []
        for i in range(3):
            bot_name = f"test-bot-{i+1}"
            
            # Create bot config
            bot_config = {
                'bot': {
                    'name': bot_name,
                    'description': f'Test bot {i+1}'
                },
                'discord': {
                    'token': f'test-token-{i+1}',
                    'command_prefix': '!'
                },
                'ollama': {
                    'model': 'llama3',
                    'base_url': 'http://localhost:11434',
                    'timeout': 30
                },
                'system_prompt': f'You are test bot {i+1}. Be helpful and concise.',
                'storage': {
                    'enabled': True,
                    'path': f'./data/{bot_name}',
                    'max_history': 100
                },
                'message': {
                    'max_length': 2000,
                    'typing_indicator': True
                },
                'rate_limit': {
                    'enabled': True,
                    'max_requests': 30,
                    'window_seconds': 60
                },
                'logging': {
                    'level': 'INFO',
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                }
            }
            
            bot_config_file = tmp_path / f"bot_{i+1}.yaml"
            bot_config_file.write_text(yaml.dump(bot_config))
            
            # Add to bots list
            bots.append({
                'name': bot_name,
                'config_file': str(bot_config_file),
                'channels': [f'channel-{i+1}', f'shared-channel']
            })
        
        # Create multi-bot configuration
        multi_config = {
            'bots': bots,
            'global_settings': {
                'context_depth': 20,
                'response_delay': '2-4',
                'max_concurrent_responses': 3,
                'cooldown_period': 45,
                'conversation_timeout': 7200,
                'storage_path': './data/conversations',
                'enable_cross_bot_context': True,
                'enable_bot_mentions': True,
                'debug_mode': False
            }
        }
        
        multi_config_file = tmp_path / "multi_bot_config.yaml"
        multi_config_file.write_text(yaml.dump(multi_config))
        
        return multi_config_file
    
    def create_mock_message(self, content, channel_name="test-channel", user_id=12345, message_id=98765):
        """Create a mock Discord message for testing."""
        message = Mock(spec=discord.Message)
        message.content = content
        message.id = message_id
        
        # Mock author
        author = Mock()
        author.id = user_id
        author.display_name = "TestUser"
        author.bot = False
        message.author = author
        
        # Mock channel
        channel = Mock()
        channel.id = hash(channel_name) % (10**6)  # Simple hash for consistent channel IDs
        channel.name = channel_name
        channel.send = AsyncMock()
        message.channel = channel
        
        return message
    
    @pytest.mark.asyncio
    async def test_complete_bot_lifecycle(self, tmp_path):
        """Test complete bot lifecycle from initialization to shutdown."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        
        # Test initialization
        await manager.initialize()
        
        # Verify all components are initialized
        assert manager.multi_bot_config is not None
        assert len(manager.multi_bot_config.bots) == 3
        assert manager.bot_services['test-bot-1'].conversation_state is not None
        assert manager.bot_services['test-bot-1'].orchestrator is not None
        assert manager.shared_coordinator is not None
        assert manager.bot_services['test-bot-1'].response_generator is not None
        
        # Verify all bot instances are created
        assert len(manager.bot_instances) == 3
        for i in range(3):
            bot_name = f"test-bot-{i+1}"
            assert bot_name in manager.bot_instances
            bot_instance = manager.bot_instances[bot_name]
            assert bot_instance.name == bot_name
            assert bot_instance.config is not None
            assert bot_instance.channels == [f'channel-{i+1}', 'shared-channel']
            assert bot_instance.is_running is False
        
        # Test bot status
        status = manager.get_bot_status()
        assert len(status) == 3
        for bot_name in status:
            assert status[bot_name]['is_running'] is False
            assert status[bot_name]['channels'] is not None
    
    @pytest.mark.asyncio
    async def test_configuration_loading_and_validation(self, tmp_path):
        """Test configuration loading with validation."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Test direct configuration loading
        multi_config = multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
        
        # Verify configuration structure
        assert len(multi_config.bots) == 3
        assert multi_config.global_settings.context_depth == 20
        assert multi_config.global_settings.max_concurrent_responses == 3
        assert multi_config.global_settings.enable_cross_bot_context is True
        
        # Verify individual bot configs
        for i, bot_config in enumerate(multi_config.bots):
            expected_name = f"test-bot-{i+1}"
            assert bot_config.name == expected_name
            assert bot_config.config_file.endswith(f"bot_{i+1}.yaml")
            assert f'channel-{i+1}' in bot_config.channels
            assert 'shared-channel' in bot_config.channels
        
        # Test loading individual bot configurations
        for i, bot_config in enumerate(multi_config.bots):
            individual_config = load_config(bot_config.config_file)
            assert individual_config.bot.name == f"test-bot-{i+1}"
            assert individual_config.discord.token == f"test-token-{i+1}"
            assert individual_config.ollama.model == "llama3"
            assert individual_config.storage.enabled is True
            assert individual_config.rate_limit.enabled is True
    
    @pytest.mark.asyncio
    async def test_multi_bot_message_processing(self, tmp_path):
        """Test message processing with multiple bots."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test messages for different channels
        message1 = self.create_mock_message("Hello bot 1!", "channel-1")
        message2 = self.create_mock_message("Hello bot 2!", "channel-2")
        message3 = self.create_mock_message("Hello everyone!", "shared-channel")
        
        # Mock AI model responses
        responses = {
            "test-bot-1": "Hello! I'm bot 1.",
            "test-bot-2": "Hello! I'm bot 2.",
            "test-bot-3": "Hello! I'm bot 3."
        }
        
        with patch.object(manager.bot_services['test-bot-1'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock) as mock_ai:
            with patch.object(manager.bot_services['test-bot-1'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Configure mock to return different responses
                mock_ai.side_effect = lambda msgs: responses.get(
                    "test-bot-1", "Default response"
                )
                
                # Test bot 1 processing message from channel-1
                result1 = await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-1", message1, ["channel-1", "shared-channel"]
                )
                assert result1 is True
                
                # Test bot 2 processing message from channel-2
                mock_ai.side_effect = lambda msgs: responses.get(
                    "test-bot-2", "Default response"
                )
                result2 = await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-2", message2, ["channel-2", "shared-channel"]
                )
                assert result2 is True
                
                # Test bot 3 processing message from shared-channel
                mock_ai.side_effect = lambda msgs: responses.get(
                    "test-bot-3", "Default response"
                )
                result3 = await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-3", message3, ["shared-channel"]
                )
                assert result3 is True
                
                # Verify all messages were processed
                assert mock_send.call_count == 3
    
    @pytest.mark.asyncio
    async def test_conversation_state_integration(self, tmp_path):
        """Test conversation state management across multiple bots."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test messages
        user_id = 12345
        channel_id = 67890
        
        message1 = self.create_mock_message("What is Python?", "test-channel", user_id)
        message1.channel.id = channel_id
        
        message2 = self.create_mock_message("Tell me more about it", "test-channel", user_id)
        message2.channel.id = channel_id
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot-1'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock) as mock_ai:
            with patch.object(manager.bot_services['test-bot-1'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock):
                
                # First message
                mock_ai.return_value = "Python is a programming language."
                await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-1", message1, ["test-channel"]
                )
                
                # Second message
                mock_ai.return_value = "Python is great for data science and web development."
                await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-1", message2, ["test-channel"]
                )
                
                # Verify conversation state
                context = await manager.bot_services['test-bot-1'].conversation_state.get_context(channel_id, user_id)
                
                # Should have 4 messages: 2 user messages + 2 bot responses
                assert len(context.messages) >= 4
                
                # Find our specific messages
                user_messages = [msg for msg in context.messages if msg.role == 'user']
                bot_messages = [msg for msg in context.messages if msg.role == 'assistant']
                
                # Verify we have the expected messages
                user_contents = [msg.content for msg in user_messages]
                bot_contents = [msg.content for msg in bot_messages]
                
                assert "What is Python?" in user_contents
                assert "Tell me more about it" in user_contents
                assert "Python is a programming language." in bot_contents
                assert "Python is great for data science and web development." in bot_contents
    
    @pytest.mark.asyncio
    async def test_bot_coordination_and_rate_limiting(self, tmp_path):
        """Test bot coordination and rate limiting in multi-bot scenario."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test message
        message = self.create_mock_message("Test coordination", "shared-channel")
        
        # Mock AI response
        with patch.object(manager.bot_services['test-bot-1'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value="Test response"):
            with patch.object(manager.bot_services['test-bot-1'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Simulate multiple bots trying to respond to same message
                tasks = []
                for i in range(3):
                    bot_name = f"test-bot-{i+1}"
                    task = asyncio.create_task(
                        manager.bot_services['test-bot-1'].orchestrator.process_message(
                            bot_name, message, ["shared-channel"]
                        )
                    )
                    tasks.append(task)
                
                # Wait for all tasks to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify coordination worked - not all bots should have responded
                successful_responses = sum(1 for result in results if result is True)
                
                # Should respect max_concurrent_responses (3 in our config)
                assert successful_responses <= 3
                
                # Verify some responses were sent
                assert mock_send.call_count >= 1
                assert mock_send.call_count <= 3
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, tmp_path):
        """Test error handling and recovery in various scenarios."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test message
        message = self.create_mock_message("Cause an error", "test-channel")
        
        # Test AI model error handling
        with patch.object(manager.bot_services['test-bot-1'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, side_effect=Exception("AI model failed")):
            with patch.object(manager.bot_services['test-bot-1'].orchestrator.notification_sender, 'send_message', 
                             new_callable=AsyncMock) as mock_error_send:
                
                # Process message - should handle error gracefully
                result = await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-1", message, ["test-channel"]
                )
                
                # Should return False but not crash
                assert result is False
                
                # Should send error message to user
                mock_error_send.assert_called_once()
                error_args = mock_error_send.call_args[0]
                assert "error" in error_args[1].lower()
        
        # Test storage error handling
        with patch.object(manager.bot_services['test-bot-1'].conversation_state, 'add_message', 
                         new_callable=AsyncMock, side_effect=Exception("Storage failed")):
            with patch.object(manager.bot_services['test-bot-1'].response_generator.ai_model, 'generate_response', 
                             new_callable=AsyncMock, return_value="Test response"):
                with patch.object(manager.bot_services['test-bot-1'].orchestrator.notification_sender, 'send_message', 
                                 new_callable=AsyncMock) as mock_error_send:
                    
                    # Process message - should handle storage error
                    result = await manager.bot_services['test-bot-1'].orchestrator.process_message(
                        "test-bot-1", message, ["test-channel"]
                    )
                    
                    # Should return False due to storage error
                    assert result is False
    
    @pytest.mark.asyncio
    async def test_configuration_reload(self, tmp_path):
        """Test configuration reload functionality."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Get initial configuration
        initial_config = manager.multi_bot_config
        initial_bots = len(manager.bot_instances)
        
        # Verify initial state
        assert initial_bots == 3
        assert initial_config.global_settings.context_depth == 20
        
        # Mock the lifecycle methods to avoid actual Discord connections
        with patch.object(manager, 'stop_all_bots', new_callable=AsyncMock) as mock_stop:
            with patch.object(manager, 'start_all_bots', new_callable=AsyncMock) as mock_start:
                
                # Reload configuration
                await manager.reload_configuration()
                
                # Verify reload sequence
                mock_stop.assert_called_once()
                mock_start.assert_called_once()
                
                # Verify configuration was reloaded
                assert manager.multi_bot_config is not initial_config
                assert len(manager.bot_instances) == 3
    
    @pytest.mark.asyncio
    async def test_cross_bot_context_sharing(self, tmp_path):
        """Test cross-bot context sharing functionality."""
        # Create test setup
        multi_config_file = self.create_complete_test_setup(tmp_path)
        
        # Initialize bot manager
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Verify cross-bot context is enabled
        assert manager.multi_bot_config.global_settings.enable_cross_bot_context is True
        
        # Create messages from different bots to same channel
        user_id = 12345
        channel_id = 67890
        
        message1 = self.create_mock_message("Hello from bot 1", "shared-channel", user_id)
        message1.channel.id = channel_id
        
        message2 = self.create_mock_message("Hello from bot 2", "shared-channel", user_id)
        message2.channel.id = channel_id
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot-1'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock) as mock_ai:
            with patch.object(manager.bot_services['test-bot-1'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock):
                
                # Bot 1 responds
                mock_ai.return_value = "Hi! I'm bot 1."
                await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-1", message1, ["shared-channel"]
                )
                
                # Bot 2 responds
                mock_ai.return_value = "Hi! I'm bot 2."
                await manager.bot_services['test-bot-1'].orchestrator.process_message(
                    "test-bot-2", message2, ["shared-channel"]
                )
                
                # Verify shared context
                context = await manager.bot_services['test-bot-1'].conversation_state.get_context(channel_id, user_id)
                
                # Should have messages from both bots
                bot_messages = [msg for msg in context.messages if msg.role == 'assistant']
                bot_names = [msg.bot_name for msg in bot_messages if msg.bot_name]
                
                # Should have responses from both bots
                assert "test-bot-1" in bot_names
                assert "test-bot-2" in bot_names
    
    def test_system_integration_with_real_config_structure(self, tmp_path):
        """Test system integration with realistic configuration structure."""
        # Create a more realistic configuration that mirrors production setup
        
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("DISCORD_TOKEN=test-token-from-env\nOLLAMA_BASE_URL=http://localhost:11434\n")
        
        # Create bot config that uses environment variables
        bot_config = {
            'bot': {
                'name': 'production-bot',
                'description': 'Production-like bot configuration'
            },
            'discord': {
                'token': '${DISCORD_TOKEN}',
                'command_prefix': '!'
            },
            'ollama': {
                'model': 'llama3',
                'base_url': '${OLLAMA_BASE_URL}',
                'timeout': 60
            },
            'system_prompt': '''You are a helpful AI assistant. 
            You should be concise but informative in your responses.
            If you don't know something, say so clearly.''',
            'storage': {
                'enabled': True,
                'path': './data/production_bot',
                'max_history': 1000
            },
            'message': {
                'max_length': 1900,
                'typing_indicator': True
            },
            'rate_limit': {
                'enabled': True,
                'max_requests_per_minute': 60
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        }
        
        bot_config_file = tmp_path / "production_bot.yaml"
        bot_config_file.write_text(yaml.dump(bot_config))
        
        # Create multi-bot config
        multi_config = {
            'bots': [
                {
                    'name': 'production-bot',
                    'config_file': str(bot_config_file),
                    'channels': ['general', 'support', 'dev-*']
                }
            ],
            'global_settings': {
                'context_depth': 50,
                'response_delay': '1-3',
                'max_concurrent_responses': 2,
                'cooldown_period': 30,
                'conversation_timeout': 3600,
                'storage_path': './data/conversations',
                'enable_cross_bot_context': False,
                'enable_bot_mentions': True,
                'debug_mode': False
            }
        }
        
        multi_config_file = tmp_path / "production_config.yaml"
        multi_config_file.write_text(yaml.dump(multi_config))
        
        # Test configuration loading with environment variables
        with patch.dict(os.environ, {
            'DISCORD_TOKEN': 'test-token-from-env',
            'OLLAMA_BASE_URL': 'http://localhost:11434'
        }):
            # Load configuration
            loaded_config = multi_bot_config_manager.load_multi_bot_config(str(multi_config_file))
            
            # Verify configuration was loaded correctly
            assert len(loaded_config.bots) == 1
            bot = loaded_config.bots[0]
            assert bot.name == 'production-bot'
            assert bot.channels == ['general', 'support', 'dev-*']
            
            # Verify global settings
            assert loaded_config.global_settings.context_depth == 50
            assert loaded_config.global_settings.enable_cross_bot_context is False
            assert loaded_config.global_settings.enable_bot_mentions is True
            
            # Load individual bot config to verify environment variable substitution
            individual_config = load_config(str(bot_config_file))
            assert individual_config.discord.token == 'test-token-from-env'
            assert individual_config.ollama.base_url == 'http://localhost:11434'
            assert individual_config.storage.max_history == 1000
            assert individual_config.rate_limit.max_requests_per_minute == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])