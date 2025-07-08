"""Unit tests for MessageProcessor (updated for Ports & Adapters)."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

import discord

from src.message_processor import MessageProcessor
from src.conversation_state import ConversationState, ConversationContext
from src.domain_services import MessageContext, ResponseDecision


@pytest.fixture
def mock_conversation_state():
    """Create a mock ConversationState."""
    state = Mock(spec=ConversationState)
    state.add_message = AsyncMock()
    state.get_context = AsyncMock()
    return state


@pytest.fixture
def global_settings():
    """Create test global settings."""
    return {
        'context_depth': 10,
        'response_delay': '1-3',
        'max_concurrent_responses': 2,
        'cooldown_period': 30
    }


@pytest.fixture
def message_processor(mock_conversation_state, global_settings):
    """Create a MessageProcessor instance."""
    return MessageProcessor(mock_conversation_state, global_settings)


@pytest.fixture
def mock_discord_message():
    """Create a mock Discord message."""
    message = Mock(spec=discord.Message)
    message.author = Mock()
    message.author.bot = False
    message.author.id = 12345
    message.author.display_name = "TestUser"
    message.channel = Mock()
    message.channel.id = 67890
    message.channel.name = "test-channel"
    message.content = "Hello, world!"
    message.created_at = datetime.now()
    message.mentions = []
    message.id = 999
    return message


class TestMessageContext:
    """Test MessageContext dataclass."""
    
    def test_message_context_creation(self, mock_discord_message):
        """Test creating MessageContext."""
        context = MessageContext(
            channel_name="test",
            channel_id=123,
            user_id=456,
            user_name="user",
            content="hello",
            timestamp=datetime.now(),
            is_bot_message=False,
            mentioned_bots=[]
        )
        
        assert context.channel_name == "test"
        assert context.channel_id == 123
        assert context.user_id == 456
        assert context.is_bot_message is False


class TestResponseDecision:
    """Test ResponseDecision dataclass."""
    
    def test_response_decision_creation(self):
        """Test creating ResponseDecision."""
        decision = ResponseDecision(
            should_respond=True,
            confidence=0.8,
            reasoning="High confidence",
            delay_seconds=2.0,
            priority=1
        )
        
        assert decision.should_respond is True
        assert decision.confidence == 0.8
        assert decision.reasoning == "High confidence"
        assert decision.delay_seconds == 2.0
        assert decision.priority == 1


class TestMessageProcessor:
    """Test MessageProcessor class (updated for Ports & Adapters)."""
    
    def test_initialization(self, message_processor, global_settings):
        """Test MessageProcessor initialization with new services."""
        # MessageProcessor now creates domain services internally
        assert message_processor.context_depth == 10
        assert message_processor.max_concurrent_responses == 2
        assert message_processor.response_delay_range == (1.0, 3.0)
        assert message_processor.cooldown_period == 30
        
        # Check that new services are created
        assert message_processor.storage is not None
        assert message_processor.ai_model is not None
        assert message_processor.rate_limiter is not None
        assert message_processor.notification_sender is not None
        assert message_processor.coordinator is not None
        assert message_processor.response_generator is not None
        assert message_processor.orchestrator is not None
    
    def test_parse_delay_range_range(self, message_processor):
        """Test parsing delay range string."""
        result = message_processor._parse_delay_range("1.5-2.5")
        assert result == (1.5, 2.5)
    
    def test_parse_delay_range_single(self, message_processor):
        """Test parsing single delay value."""
        result = message_processor._parse_delay_range("2.0")
        assert result == (2.0, 2.0)
    
    @pytest.mark.asyncio
    async def test_should_bot_handle_message_delegates_to_coordinator(self, message_processor, mock_discord_message):
        """Test that should_bot_handle_message delegates to coordinator."""
        # Since MessageProcessor now delegates to coordinator, we just test the delegation
        with patch.object(message_processor.coordinator, 'should_handle_message', new_callable=AsyncMock) as mock_should_handle:
            mock_should_handle.return_value = True
            
            result = await message_processor.should_bot_handle_message(
                "test-bot", mock_discord_message, ["test-channel"]
            )
            
            assert result is True
            mock_should_handle.assert_called_once_with(
                "test-bot", mock_discord_message, ["test-channel"]
            )
    
    @pytest.mark.asyncio
    async def test_process_message_delegates_to_orchestrator(self, message_processor, mock_discord_message, mock_conversation_state):
        """Test that process_message delegates to orchestrator."""
        # Create a mock context
        mock_context = Mock(spec=ConversationContext)
        
        with patch.object(message_processor.orchestrator, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = True
            
            result = await message_processor.process_message(
                "test-bot", mock_discord_message, mock_context
            )
            
            assert result is True
            # Orchestrator should be called with empty channel patterns (legacy compatibility)
            mock_process.assert_called_once_with("test-bot", mock_discord_message, [])
    
    def test_matches_channel_patterns_empty(self, message_processor):
        """Test empty patterns (should match all)."""
        channel = Mock()
        channel.name = "any-channel"
        
        result = message_processor._matches_channel_patterns(channel, [])
        assert result is True
    
    def test_extract_mentioned_bots_mentions(self, message_processor, mock_discord_message):
        """Test extracting bot names from Discord mentions."""
        mock_bot = Mock()
        mock_bot.bot = True
        mock_bot.display_name = "TestBot"
        
        mock_discord_message.mentions = [mock_bot]
        
        result = message_processor._extract_mentioned_bots(mock_discord_message)
        assert "testbot" in result
    
    def test_extract_mentioned_bots_content(self, message_processor, mock_discord_message):
        """Test extracting bot names from message content."""
        mock_discord_message.content = "Hey sage, what do you think?"
        mock_discord_message.mentions = []
        
        result = message_processor._extract_mentioned_bots(mock_discord_message)
        assert "sage" in result


class TestMessageProcessorIntegration:
    """Integration tests for MessageProcessor."""
    
    @pytest.mark.asyncio
    async def test_process_message_flow(self, message_processor, mock_discord_message, mock_conversation_state):
        """Test the complete message processing flow (delegated to orchestrator)."""
        # Since this is now delegated to orchestrator, just test delegation
        with patch.object(message_processor.orchestrator, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = True
            
            context = Mock()
            context.messages = []
            
            result = await message_processor.process_message(
                "test-bot", mock_discord_message, context
            )
            
            assert result is True
            mock_process.assert_called_once_with("test-bot", mock_discord_message, [])
    
    @pytest.mark.asyncio
    async def test_process_message_no_response(self, message_processor, mock_discord_message, mock_conversation_state):
        """Test message processing when bot decides not to respond (delegated to orchestrator)."""
        # Since this is now delegated to orchestrator, just test delegation
        with patch.object(message_processor.orchestrator, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = False  # Orchestrator decides not to respond
            
            context = Mock()
            context.messages = []
            
            result = await message_processor.process_message(
                "test-bot", mock_discord_message, context
            )
            
            assert result is False
            mock_process.assert_called_once_with("test-bot", mock_discord_message, [])


if __name__ == "__main__":
    pytest.main([__file__])