"""Integration tests for the Ports & Adapters architecture."""

import pytest
import tempfile
from unittest.mock import patch, Mock, AsyncMock
from pathlib import Path

from src.service_factory import create_services, create_multi_bot_services
from src.config import Config, BotConfig, DiscordConfig, OllamaConfig, StorageConfig, MessageConfig, RateLimitConfig, LoggingConfig
from src.multi_bot_config import MultiBotConfig, BotInstanceConfig, GlobalSettings
from src.domain_services import BotOrchestrator


class TestServiceFactory:
    """Test service factory integration."""
    
    def test_create_services_with_config(self):
        """Test creating services from configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                bot=BotConfig(name="testbot", description="Test bot"),
                discord=DiscordConfig(token="test_token"),
                ollama=OllamaConfig(base_url="http://localhost:11434", model="llama3"),
                storage=StorageConfig(path=temp_dir),
                message=MessageConfig(),
                rate_limit=RateLimitConfig(),
                logging=LoggingConfig()
            )
            
            orchestrator, coordinator, response_generator = create_services(config)
            
            assert isinstance(orchestrator, BotOrchestrator)
            assert orchestrator.coordinator is coordinator
            assert orchestrator.response_generator is response_generator
            
            # Test that adapters are properly configured
            assert orchestrator.storage is not None
            assert orchestrator.rate_limiter is not None
            assert orchestrator.notification_sender is not None
    
    def test_create_multi_bot_services(self):
        """Test creating services for multi-bot deployment."""
        multi_bot_config = MultiBotConfig(
            bots=[
                BotInstanceConfig(
                    name="bot1",
                    config_file="config/bot1.yaml",
                    channels=["general"]
                )
            ],
            global_settings=GlobalSettings(
                context_depth=15,
                max_concurrent_responses=3,
                storage_path="./test_data"
            )
        )
        
        orchestrator, coordinator, response_generator, conversation_state = create_multi_bot_services(multi_bot_config)
        
        assert isinstance(orchestrator, BotOrchestrator)
        assert conversation_state is not None
        
        # Test that global settings are applied
        assert coordinator.storage is not None
        assert conversation_state.context_depth == 15


class TestEndToEndFlow:
    """Test complete end-to-end message flow."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mocked services for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                bot=BotConfig(name="testbot"),
                discord=DiscordConfig(token="test_token"),
                ollama=OllamaConfig(),
                storage=StorageConfig(path=temp_dir),
                message=MessageConfig(),
                rate_limit=RateLimitConfig(enabled=False),  # Disable rate limiting for tests
                logging=LoggingConfig()
            )
            
            orchestrator, coordinator, response_generator = create_services(config)
            yield orchestrator
    
    @pytest.mark.asyncio
    @patch('src.adapters.requests.post')
    async def test_complete_message_flow(self, mock_post, mock_services):
        """Test complete message processing flow from start to finish."""
        # Mock Ollama response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "message": {"content": "Hello! How can I help you today?"}
        }
        mock_post.return_value = mock_response
        
        # Create mock Discord message with proper channel mock
        mock_channel = AsyncMock()
        mock_channel.id = 67890
        mock_channel.name = "general"
        
        mock_message = Mock()
        mock_message.content = "Hello bot"
        mock_message.author.id = 12345
        mock_message.author.display_name = "TestUser"
        mock_message.author.bot = False
        mock_message.channel = mock_channel
        mock_message.created_at = Mock()
        mock_message.id = 999
        
        # Process the message
        result = await mock_services.process_message("testbot", mock_message, ["general"])
        
        # Verify the flow worked
        assert result is True
        
        # Verify Ollama was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json']['model'] == 'llama3'
        assert len(call_args[1]['json']['messages']) >= 2  # At least user message + system prompt
        
        # Verify response was sent to Discord
        mock_channel.send.assert_called_once()
        sent_message = mock_channel.send.call_args[0][0]
        assert "Hello! How can I help you today?" in sent_message
        
        # Verify messages were stored
        context = await mock_services.storage.get_context(67890, 12345)
        assert len(context.messages) == 2  # User message + bot response
        assert context.messages[0].role == "user"
        assert context.messages[0].content == "Hello bot"
        assert context.messages[1].role == "assistant"
        assert context.messages[1].bot_name == "testbot"
    
    @pytest.mark.asyncio
    async def test_message_rejection_flow(self, mock_services):
        """Test message rejection scenarios."""
        # Test bot message rejection
        mock_channel_1 = Mock()
        mock_channel_1.name = "general"
        
        bot_message = Mock()
        bot_message.author.bot = True
        bot_message.channel = mock_channel_1
        
        result = await mock_services.process_message("testbot", bot_message, ["general"])
        assert result is False
        
        # Test channel pattern mismatch
        mock_channel_2 = Mock()
        mock_channel_2.name = "private"
        
        user_message = Mock()
        user_message.author.bot = False
        user_message.channel = mock_channel_2
        user_message.content = "Hello"
        
        result = await mock_services.process_message("testbot", user_message, ["general"])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_conversation_context_preservation(self, mock_services):
        """Test that conversation context is preserved across messages."""
        with patch('src.adapters.requests.post') as mock_post:
            # Mock Ollama responses
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "message": {"content": "Response"}
            }
            mock_post.return_value = mock_response
            
            # Create mock channel
            mock_channel = AsyncMock()
            mock_channel.id = 67890
            mock_channel.name = "general"
            
            # Create mock message
            mock_message = Mock()
            mock_message.author.id = 12345
            mock_message.author.display_name = "TestUser"
            mock_message.author.bot = False
            mock_message.channel = mock_channel
            mock_message.created_at = Mock()
            mock_message.id = 999
            
            # Send first message
            mock_message.content = "First message"
            result1 = await mock_services.process_message("testbot", mock_message, ["general"])
            assert result1 is True
            
            # Send second message
            mock_message.content = "Second message"
            mock_message.id = 1000
            result2 = await mock_services.process_message("testbot", mock_message, ["general"])
            assert result2 is True
            
            # Verify context was preserved
            context = await mock_services.storage.get_context(67890, 12345)
            assert len(context.messages) == 4  # 2 user + 2 bot messages
            assert context.messages[0].content == "First message"
            assert context.messages[2].content == "Second message"
            
            # Verify second call included context from first message
            assert mock_post.call_count == 2
            second_call_messages = mock_post.call_args[1]['json']['messages']
            
            # Should include messages from first exchange in context
            message_contents = [msg['content'] for msg in second_call_messages]
            assert any("First message" in content for content in message_contents)


class TestArchitecturalBoundaries:
    """Test that architectural boundaries are respected."""
    
    def test_domain_services_have_no_external_dependencies(self):
        """Test that domain services only depend on ports, not adapters."""
        from src.domain_services import MessageCoordinator, ResponseGenerator, BotOrchestrator
        import inspect
        
        # Check MessageCoordinator
        coordinator_deps = inspect.signature(MessageCoordinator.__init__).parameters
        assert 'storage' in coordinator_deps  # Should depend on port
        assert 'rate_limiter' in coordinator_deps  # Should depend on port
        
        # Check ResponseGenerator  
        generator_deps = inspect.signature(ResponseGenerator.__init__).parameters
        assert 'ai_model' in generator_deps  # Should depend on port
        assert 'storage' in generator_deps  # Should depend on port
        
        # Check BotOrchestrator
        orchestrator_deps = inspect.signature(BotOrchestrator.__init__).parameters
        assert 'coordinator' in orchestrator_deps
        assert 'response_generator' in orchestrator_deps
        assert 'notification_sender' in orchestrator_deps  # Should depend on port
    
    def test_adapters_implement_ports(self):
        """Test that all adapters properly implement their port interfaces."""
        from src.adapters import FileMessageStorage, OllamaAI, MemoryRateLimiter, DiscordNotificationSender
        from src.ports import MessageStorage, AIModel, RateLimiter, NotificationSender
        
        # Check that adapters have the required methods
        assert hasattr(FileMessageStorage, 'add_message')
        assert hasattr(FileMessageStorage, 'get_context')
        
        assert hasattr(OllamaAI, 'generate_response')
        
        assert hasattr(MemoryRateLimiter, 'can_request')
        assert hasattr(MemoryRateLimiter, 'record_request')
        
        assert hasattr(DiscordNotificationSender, 'send_message')
        assert hasattr(DiscordNotificationSender, 'send_chunked_message')
    
    def test_no_direct_infrastructure_in_domain(self):
        """Test that domain services don't directly use infrastructure."""
        from src.domain_services import MessageCoordinator, ResponseGenerator
        import inspect
        
        # Get source code of domain services
        coordinator_source = inspect.getsource(MessageCoordinator)
        generator_source = inspect.getsource(ResponseGenerator)
        
        # Should not contain direct infrastructure imports
        assert 'import requests' not in coordinator_source
        assert 'import discord' not in coordinator_source
        assert 'import json' not in coordinator_source
        
        # ResponseGenerator should not have direct infrastructure
        assert 'import requests' not in generator_source
        
        # Note: discord import is allowed since we need the Message type for now
        # In a pure implementation, we'd create our own domain message type


if __name__ == "__main__":
    pytest.main([__file__])