"""Unit tests for MessageProcessor."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

import discord

from src.message_processor import MessageProcessor, MessageContext, ResponseDecision
from src.conversation_state import ConversationState, ConversationContext


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
            message=mock_discord_message,
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
    """Test MessageProcessor class."""
    
    def test_initialization(self, message_processor, global_settings):
        """Test MessageProcessor initialization."""
        assert message_processor.context_depth == 10
        assert message_processor.max_concurrent_responses == 2
        assert message_processor.response_delay_range == (1.0, 3.0)
        assert message_processor.cooldown_period == 30
    
    def test_parse_delay_range_range(self, message_processor):
        """Test parsing delay range string."""
        result = message_processor._parse_delay_range("1.5-2.5")
        assert result == (1.5, 2.5)
    
    def test_parse_delay_range_single(self, message_processor):
        """Test parsing single delay value."""
        result = message_processor._parse_delay_range("2.0")
        assert result == (2.0, 2.0)
    
    @pytest.mark.asyncio
    async def test_should_bot_handle_message_bot_message(self, message_processor, mock_discord_message):
        """Test that bot messages are ignored."""
        mock_discord_message.author.bot = True
        
        result = await message_processor.should_bot_handle_message(
            "test-bot", mock_discord_message, ["test-channel"]
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_bot_handle_message_command(self, message_processor, mock_discord_message):
        """Test that command messages are ignored."""
        mock_discord_message.content = "!command test"
        
        result = await message_processor.should_bot_handle_message(
            "test-bot", mock_discord_message, ["test-channel"]
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_bot_handle_message_wrong_channel(self, message_processor, mock_discord_message):
        """Test that messages in non-whitelisted channels are ignored."""
        result = await message_processor.should_bot_handle_message(
            "test-bot", mock_discord_message, ["other-channel"]
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_bot_handle_message_valid(self, message_processor, mock_discord_message):
        """Test that valid messages are handled."""
        with patch.object(message_processor, '_should_coordinate_response', return_value=False):
            result = await message_processor.should_bot_handle_message(
                "test-bot", mock_discord_message, ["test-channel"]
            )
            
            assert result is True
    
    def test_matches_channel_patterns_exact(self, message_processor):
        """Test exact channel name matching."""
        channel = Mock()
        channel.name = "test-channel"
        
        result = message_processor._matches_channel_patterns(channel, ["test-channel"])
        assert result is True
        
        result = message_processor._matches_channel_patterns(channel, ["other-channel"])
        assert result is False
    
    def test_matches_channel_patterns_wildcard(self, message_processor):
        """Test wildcard channel pattern matching."""
        channel = Mock()
        channel.name = "test-general"
        
        result = message_processor._matches_channel_patterns(channel, ["test-*"])
        assert result is True
        
        result = message_processor._matches_channel_patterns(channel, ["other-*"])
        assert result is False
    
    def test_matches_channel_patterns_prefix(self, message_processor):
        """Test prefix channel pattern matching."""
        channel = Mock()
        channel.name = "test-general"
        
        result = message_processor._matches_channel_patterns(channel, ["test-"])
        assert result is True
        
        result = message_processor._matches_channel_patterns(channel, ["other-"])
        assert result is False
    
    def test_matches_channel_patterns_empty(self, message_processor):
        """Test empty patterns (should match all)."""
        channel = Mock()
        channel.name = "any-channel"
        
        result = message_processor._matches_channel_patterns(channel, [])
        assert result is True
    
    @pytest.mark.asyncio
    async def test_should_coordinate_response_no_history(self, message_processor, mock_discord_message):
        """Test coordination when no response history exists."""
        result = await message_processor._should_coordinate_response("test-bot", mock_discord_message)
        assert result is False  # Should not coordinate (can respond)
    
    @pytest.mark.asyncio
    async def test_should_coordinate_response_too_many_active(self, message_processor, mock_discord_message):
        """Test coordination when too many bots are active."""
        channel_id = mock_discord_message.channel.id
        message_processor.active_responses[channel_id] = {"bot1", "bot2"}  # Max is 2
        
        result = await message_processor._should_coordinate_response("test-bot", mock_discord_message)
        assert result is True  # Should coordinate (don't respond)
    
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
    
    @pytest.mark.asyncio
    async def test_make_response_decision_mentioned(self, message_processor, mock_discord_message):
        """Test response decision when bot is mentioned."""
        context = Mock()
        context.messages = []
        
        message_context = MessageContext(
            message=mock_discord_message,
            channel_name="test",
            channel_id=123,
            user_id=456,
            user_name="user",
            content="hello sage",
            timestamp=datetime.now(),
            is_bot_message=False,
            mentioned_bots=["sage"]
        )
        
        with patch('random.random', return_value=0.5):  # Mock random for deterministic test
            decision = await message_processor._make_response_decision(
                "sage", message_context, context
            )
            
            assert decision.confidence > 0.3  # Should be higher due to mention
            assert "mentioned" in decision.reasoning
    
    @pytest.mark.asyncio
    async def test_make_response_decision_question(self, message_processor, mock_discord_message):
        """Test response decision for questions."""
        context = Mock()
        context.messages = []
        
        message_context = MessageContext(
            message=mock_discord_message,
            channel_name="test",
            channel_id=123,
            user_id=456,
            user_name="user",
            content="What do you think?",
            timestamp=datetime.now(),
            is_bot_message=False,
            mentioned_bots=[]
        )
        
        decision = await message_processor._make_response_decision(
            "test-bot", message_context, context
        )
        
        assert "question" in decision.reasoning
    
    @pytest.mark.asyncio
    async def test_record_response(self, message_processor):
        """Test recording bot responses."""
        channel_id = 123
        bot_name = "test-bot"
        
        await message_processor._record_response(bot_name, channel_id)
        
        assert channel_id in message_processor.recent_responses
        responses = message_processor.recent_responses[channel_id]
        assert len(responses) == 1
        assert responses[0][0] == bot_name
    
    @pytest.mark.asyncio
    async def test_get_channel_activity(self, message_processor):
        """Test getting channel activity information."""
        channel_id = 123
        
        # Add some test data
        message_processor.recent_responses[channel_id] = [("bot1", datetime.now())]
        message_processor.active_responses[channel_id] = {"bot2"}
        
        activity = await message_processor.get_channel_activity(channel_id)
        
        assert activity['recent_responses'] == 1
        assert activity['active_bots'] == 1
        assert activity['active_bot_names'] == ['bot2']
        assert activity['can_respond'] is True  # 1 < max_concurrent_responses (2)
    
    @pytest.mark.asyncio
    async def test_reset_channel_state(self, message_processor):
        """Test resetting channel state."""
        channel_id = 123
        
        # Add some test data
        message_processor.recent_responses[channel_id] = [("bot1", datetime.now())]
        message_processor.active_responses[channel_id] = {"bot2"}
        
        await message_processor.reset_channel_state(channel_id)
        
        assert channel_id not in message_processor.recent_responses
        assert channel_id not in message_processor.active_responses
    
    @pytest.mark.asyncio
    async def test_get_processor_stats(self, message_processor):
        """Test getting processor statistics."""
        # Add some test data
        message_processor.active_responses[123] = {"bot1"}
        message_processor.recent_responses[123] = [("bot1", datetime.now())]
        
        stats = await message_processor.get_processor_stats()
        
        assert stats['active_channels'] == 1
        assert stats['total_recent_responses'] == 1
        assert stats['total_active_bots'] == 1
        assert stats['context_depth'] == 10
        assert stats['max_concurrent_responses'] == 2


class TestMessageProcessorIntegration:
    """Integration tests for MessageProcessor."""
    
    @pytest.mark.asyncio
    async def test_process_message_flow(self, message_processor, mock_discord_message, mock_conversation_state):
        """Test the complete message processing flow."""
        # Setup mocks
        context = Mock()
        context.messages = []
        
        original_handler = AsyncMock()
        
        # Mock response decision to respond
        with patch.object(message_processor, '_make_response_decision') as mock_decision:
            mock_decision.return_value = ResponseDecision(
                should_respond=True,
                confidence=0.8,
                reasoning="test",
                delay_seconds=0.1,
                priority=1
            )
            
            await message_processor.process_message(
                "test-bot", mock_discord_message, context, original_handler
            )
        
        # Verify conversation state was updated
        mock_conversation_state.add_message.assert_called_once()
        
        # Verify original handler was called
        original_handler.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_message_no_response(self, message_processor, mock_discord_message, mock_conversation_state):
        """Test message processing when bot decides not to respond."""
        context = Mock()
        context.messages = []
        
        original_handler = AsyncMock()
        
        # Mock response decision to not respond
        with patch.object(message_processor, '_make_response_decision') as mock_decision:
            mock_decision.return_value = ResponseDecision(
                should_respond=False,
                confidence=0.1,
                reasoning="low confidence",
                delay_seconds=0.0,
                priority=0
            )
            
            await message_processor.process_message(
                "test-bot", mock_discord_message, context, original_handler
            )
        
        # Verify conversation state was not updated
        mock_conversation_state.add_message.assert_not_called()
        
        # Verify original handler was not called
        original_handler.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__])