"""Integration tests for message processing functionality.

These tests catch message processing errors that would cause the bot to crash when handling Discord messages.
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from datetime import datetime

import discord

from src.bot_manager import BotManager
from src.multi_bot_config import MultiBotConfig, BotInstanceConfig, GlobalSettings
from src.domain_services import BotOrchestrator, MessageCoordinator, ResponseGenerator
from src.conversation_state import ConversationState
from src.adapters import FileMessageStorage, MemoryRateLimiter, DiscordNotificationSender
from src.service_factory import create_multi_bot_services


class TestMessageProcessingIntegration:
    """Test message processing integration across the full stack."""
    
    def create_test_config(self, tmp_path, bot_name="message-bot"):
        """Helper to create test configuration files."""
        # Create bot config
        bot_config = {
            'bot': {'name': bot_name},
            'discord': {'token': 'test-token'},
            'ollama': {'model': 'llama3', 'base_url': 'http://localhost:11434', 'timeout': 30},
            'system_prompt': 'Test message processing prompt',
            'storage': {'enabled': True, 'path': f'./data/{bot_name}'},
            'message': {'max_length': 2000, 'typing_indicator': True},
            'rate_limit': {'enabled': True, 'max_requests': 10, 'window_seconds': 60},
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
                    'channels': ['message-test']
                }
            ],
            'global_settings': {
                'context_depth': 10,
                'response_delay': '1-2',
                'max_concurrent_responses': 2,
                'cooldown_period': 30,
                'conversation_timeout': 3600,
                'storage_path': f'./data/{bot_name}_conversations',
                'enable_cross_bot_context': True,
                'enable_bot_mentions': True,
                'debug_mode': False
            }
        }
        
        multi_config_file = tmp_path / "multi_bot.yaml"
        multi_config_file.write_text(yaml.dump(multi_config_data))
        
        return multi_config_file
    
    def create_mock_message(self, content="Hello bot!", author_id=12345, channel_name="message-test", 
                           channel_id=67890, is_bot=False):
        """Create a mock Discord message."""
        message = Mock(spec=discord.Message)
        message.content = content
        message.id = 98765
        
        # Mock author
        author = Mock()
        author.id = author_id
        author.display_name = "TestUser"
        author.bot = is_bot
        message.author = author
        
        # Mock channel
        channel = Mock()
        channel.id = channel_id
        channel.name = channel_name
        message.channel = channel
        
        return message
    
    @pytest.mark.asyncio
    async def test_message_processing_with_orchestrator(self, tmp_path):
        """Test message processing through the orchestrator."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create mock message
        message = self.create_mock_message("Hello orchestrator!")
        
        # Create mock AI response
        mock_ai_response = "Hello! I'm here to help."
        
        # Mock the AI model to return our test response
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value=mock_ai_response):
            # Mock the notification sender
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                # Process the message
                result = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", message, ["message-test"]
                )
                
                # Verify processing succeeded
                assert result is True
                
                # Verify notification was sent
                mock_send.assert_called_once()
                send_args = mock_send.call_args[0]
                assert send_args[0] == message.channel
                assert send_args[1] == mock_ai_response
    
    @pytest.mark.asyncio
    async def test_message_processing_with_rate_limiting(self, tmp_path):
        """Test message processing with rate limiting."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test messages from same user
        message1 = self.create_mock_message("First message", author_id=12345)
        message2 = self.create_mock_message("Second message", author_id=12345)
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value="Test response"):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Process first message - should succeed
                result1 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", message1, ["message-test"]
                )
                assert result1 is True
                
                # Set up rate limiting to reject second message
                manager.bot_services['test-bot'].orchestrator.rate_limiter.requests = {}  # Reset for test
                manager.bot_services['test-bot'].orchestrator.rate_limiter.max_requests_per_minute = 1
                manager.bot_services['test-bot'].orchestrator.rate_limiter.record_request(str(message1.author.id))
                
                # Process second message - should be rate limited
                result2 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", message2, ["message-test"]
                )
                assert result2 is False
                
                # Verify only one message was sent
                assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_message_processing_with_conversation_storage(self, tmp_path):
        """Test message processing with conversation storage."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test message
        message = self.create_mock_message("Tell me about Python")
        
        # Mock AI response
        mock_ai_response = "Python is a programming language."
        
        # Mock the AI model
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value=mock_ai_response):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock):
                
                # Process the message
                result = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", message, ["message-test"]
                )
                
                # Verify processing succeeded
                assert result is True
                
                # Verify message was stored in conversation state
                context = await manager.bot_services['test-bot'].conversation_state.get_context(
                    message.channel.id, message.author.id
                )
                
                # Should have both user message and bot response
                assert len(context.messages) >= 2
                
                # Find our test message and response (may not be first due to test isolation issues)
                user_messages = [msg for msg in context.messages if msg.role == 'user' and msg.content == "Tell me about Python"]
                bot_messages = [msg for msg in context.messages if msg.role == 'assistant' and msg.content == mock_ai_response]
                
                # Check we have the user message
                assert len(user_messages) >= 1
                user_message = user_messages[0]
                assert user_message.content == "Tell me about Python"
                assert user_message.role == 'user'
                assert user_message.bot_name is None
                
                # Check we have the bot response
                assert len(bot_messages) >= 1
                bot_message = bot_messages[0]
                assert bot_message.content == mock_ai_response
                assert bot_message.role == 'assistant'
                assert bot_message.bot_name == "message-bot"
    
    @pytest.mark.asyncio
    async def test_message_processing_error_handling(self, tmp_path):
        """Test message processing error handling."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test message
        message = self.create_mock_message("Cause an error")
        
        # Mock AI model to raise an exception
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, side_effect=Exception("AI model error")):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_message', 
                             new_callable=AsyncMock) as mock_error_send:
                
                # Process the message - should handle error gracefully
                result = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", message, ["message-test"]
                )
                
                # Verify processing failed but didn't crash
                assert result is False
                
                # Verify error message was sent to user
                mock_error_send.assert_called_once()
                error_args = mock_error_send.call_args[0]
                assert error_args[0] == message.channel
                assert "error" in error_args[1].lower()
    
    @pytest.mark.asyncio
    async def test_message_processing_channel_filtering(self, tmp_path):
        """Test message processing with channel filtering."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create messages from different channels
        allowed_message = self.create_mock_message("Hello from allowed channel", 
                                                  channel_name="message-test")
        blocked_message = self.create_mock_message("Hello from blocked channel", 
                                                  channel_name="blocked-channel")
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value="Test response"):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Process message from allowed channel - should succeed
                result1 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", allowed_message, ["message-test"]
                )
                assert result1 is True
                
                # Process message from blocked channel - should be filtered
                result2 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", blocked_message, ["message-test"]
                )
                assert result2 is False
                
                # Verify only one message was sent
                assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_message_processing_bot_coordination(self, tmp_path):
        """Test message processing with bot coordination."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create test message
        message = self.create_mock_message("Test coordination")
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value="Test response"):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Simulate multiple bots trying to respond simultaneously
                channel_id = message.channel.id
                
                # First bot starts responding
                await manager.bot_services['test-bot'].orchestrator.coordinator.mark_bot_responding("bot1", channel_id)
                await manager.bot_services['test-bot'].orchestrator.coordinator.mark_bot_responding("bot2", channel_id)
                
                # Third bot should be blocked due to max_concurrent_responses = 2
                should_coordinate = await manager.bot_services['test-bot'].orchestrator.coordinator._should_coordinate_response(
                    "bot3", message
                )
                
                # Should coordinate (block) because max concurrent responses reached
                assert should_coordinate is True
                
                # Complete one response
                await manager.bot_services['test-bot'].orchestrator.coordinator.mark_response_complete("bot1", channel_id)
                
                # Now bot3 should be able to respond
                should_coordinate = await manager.bot_services['test-bot'].orchestrator.coordinator._should_coordinate_response(
                    "bot3", message
                )
                assert should_coordinate is False
    
    @pytest.mark.asyncio
    async def test_message_processing_with_command_filtering(self, tmp_path):
        """Test message processing with command message filtering."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create command and regular messages
        command_message = self.create_mock_message("!help", channel_name="message-test")
        regular_message = self.create_mock_message("Hello bot", channel_name="message-test")
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value="Test response"):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Process command message - should be filtered
                result1 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", command_message, ["message-test"]
                )
                assert result1 is False
                
                # Process regular message - should succeed
                result2 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", regular_message, ["message-test"]
                )
                assert result2 is True
                
                # Verify only regular message was processed
                assert mock_send.call_count == 1
    
    @pytest.mark.asyncio
    async def test_message_processing_with_bot_message_filtering(self, tmp_path):
        """Test message processing with bot message filtering."""
        # Create test configuration
        multi_config_file = self.create_test_config(tmp_path)
        
        # Load configuration
        manager = BotManager(str(multi_config_file))
        await manager.initialize()
        
        # Create bot and user messages
        bot_message = self.create_mock_message("I am a bot", channel_name="message-test", is_bot=True)
        user_message = self.create_mock_message("I am a user", channel_name="message-test", is_bot=False)
        
        # Mock AI responses
        with patch.object(manager.bot_services['test-bot'].response_generator.ai_model, 'generate_response', 
                         new_callable=AsyncMock, return_value="Test response"):
            with patch.object(manager.bot_services['test-bot'].orchestrator.notification_sender, 'send_chunked_message', 
                             new_callable=AsyncMock) as mock_send:
                
                # Process bot message - should be filtered
                result1 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", bot_message, ["message-test"]
                )
                assert result1 is False
                
                # Process user message - should succeed
                result2 = await manager.bot_services['test-bot'].orchestrator.process_message(
                    "message-bot", user_message, ["message-test"]
                )
                assert result2 is True
                
                # Verify only user message was processed
                assert mock_send.call_count == 1


class TestMessageCoordinatorIntegration:
    """Test message coordinator integration."""
    
    def test_message_coordinator_initialization(self):
        """Test message coordinator initialization with global settings."""
        # Create mock storage and rate limiter
        storage = Mock()
        rate_limiter = Mock()
        
        # Test with default settings
        global_settings = {}
        coordinator = MessageCoordinator(storage, rate_limiter, global_settings)
        
        # Verify defaults are applied
        assert coordinator.max_concurrent_responses == 2
        assert coordinator.response_delay_range == (1.0, 3.0)
        assert coordinator.cooldown_period == 30
        
        # Test with custom settings
        custom_settings = {
            'max_concurrent_responses': 5,
            'response_delay': '2-4',
            'cooldown_period': 60
        }
        coordinator = MessageCoordinator(storage, rate_limiter, custom_settings)
        
        assert coordinator.max_concurrent_responses == 5
        assert coordinator.response_delay_range == (2.0, 4.0)
        assert coordinator.cooldown_period == 60
    
    def test_message_coordinator_delay_parsing(self):
        """Test delay range parsing."""
        storage = Mock()
        rate_limiter = Mock()
        
        # Test single value
        coordinator = MessageCoordinator(storage, rate_limiter, {'response_delay': '2.5'})
        assert coordinator.response_delay_range == (2.5, 2.5)
        
        # Test range
        coordinator = MessageCoordinator(storage, rate_limiter, {'response_delay': '1.5-3.5'})
        assert coordinator.response_delay_range == (1.5, 3.5)
        
        # Test integer values
        coordinator = MessageCoordinator(storage, rate_limiter, {'response_delay': '1-5'})
        assert coordinator.response_delay_range == (1.0, 5.0)
    
    def test_message_coordinator_channel_pattern_matching(self):
        """Test channel pattern matching logic."""
        storage = Mock()
        rate_limiter = Mock()
        coordinator = MessageCoordinator(storage, rate_limiter, {})
        
        # Mock channel
        channel = Mock()
        channel.name = "general-chat"
        
        # Test exact match
        assert coordinator._matches_channel_patterns(channel, ["general-chat"]) is True
        assert coordinator._matches_channel_patterns(channel, ["other-channel"]) is False
        
        # Test wildcard patterns
        assert coordinator._matches_channel_patterns(channel, ["general-*"]) is True
        assert coordinator._matches_channel_patterns(channel, ["*-chat"]) is True
        assert coordinator._matches_channel_patterns(channel, ["*general*"]) is True
        assert coordinator._matches_channel_patterns(channel, ["test-*"]) is False
        
        # Test prefix patterns
        assert coordinator._matches_channel_patterns(channel, ["general-"]) is True
        assert coordinator._matches_channel_patterns(channel, ["chat-"]) is False
        
        # Test empty patterns (should match all)
        assert coordinator._matches_channel_patterns(channel, []) is True
        
        # Test case insensitive matching
        assert coordinator._matches_channel_patterns(channel, ["GENERAL-CHAT"]) is True
        assert coordinator._matches_channel_patterns(channel, ["General-*"]) is True


class TestResponseGeneratorIntegration:
    """Test response generator integration."""
    
    def test_response_generator_initialization(self):
        """Test response generator initialization."""
        # Mock dependencies
        ai_model = Mock()
        storage = Mock()
        
        # Create response generator
        generator = ResponseGenerator(ai_model, storage)
        
        # Verify initialization
        assert generator.ai_model is ai_model
        assert generator.storage is storage
        assert generator.logger is not None
        assert len(generator.system_prompts) > 0
    
    def test_response_generator_system_prompts(self):
        """Test system prompt configuration."""
        ai_model = Mock()
        storage = Mock()
        generator = ResponseGenerator(ai_model, storage)
        
        # Verify system prompts are configured
        assert 'sage' in generator.system_prompts
        assert 'spark' in generator.system_prompts
        assert 'logic' in generator.system_prompts
        
        # Verify prompts are descriptive
        assert len(generator.system_prompts['sage']) > 50
        assert len(generator.system_prompts['spark']) > 50
        assert len(generator.system_prompts['logic']) > 50
    
    @pytest.mark.asyncio
    async def test_response_generator_message_history_building(self):
        """Test message history building for AI model."""
        ai_model = Mock()
        storage = Mock()
        generator = ResponseGenerator(ai_model, storage)
        
        # Mock conversation context
        from src.conversation_state import ConversationContext, ConversationMessage
        context = ConversationContext(
            channel_id=12345,
            user_id=67890,
            messages=[
                ConversationMessage(
                    content="Hello there",
                    role="user",
                    timestamp=datetime.now()
                ),
                ConversationMessage(
                    content="Hello! How can I help?",
                    role="assistant",
                    timestamp=datetime.now(),
                    bot_name="sage"
                )
            ],
            last_updated=datetime.now()
        )
        
        # Build message history
        current_message = "Tell me about Python"
        messages = generator._build_message_history("sage", context, current_message)
        
        # Verify message structure
        assert len(messages) == 4  # system + 2 context + current
        
        # Check system message
        assert messages[0]["role"] == "system"
        assert "sage" in messages[0]["content"].lower()
        
        # Check context messages
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello there"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Hello! How can I help?"
        
        # Check current message
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Tell me about Python"
    
    @pytest.mark.asyncio
    async def test_response_generator_unknown_bot_system_prompt(self):
        """Test response generation for unknown bot (no system prompt)."""
        ai_model = Mock()
        storage = Mock()
        generator = ResponseGenerator(ai_model, storage)
        
        # Mock conversation context (empty)
        from src.conversation_state import ConversationContext
        context = ConversationContext(channel_id=12345, user_id=67890, messages=[], last_updated=datetime.now())
        
        # Build message history for unknown bot
        current_message = "Hello"
        messages = generator._build_message_history("unknown-bot", context, current_message)
        
        # Should only have the current message (no system prompt)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])