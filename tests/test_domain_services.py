"""Tests for domain services with mocked dependencies."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import discord

from src.domain_services import MessageCoordinator, ResponseGenerator, BotOrchestrator
from src.ports import MessageStorage, AIModel, RateLimiter, NotificationSender
from src.conversation_state import ConversationContext, ConversationMessage


class MockMessageStorage(MessageStorage):
    """Mock implementation of MessageStorage for testing."""
    
    def __init__(self):
        self.messages = []
        self.contexts = {}
    
    async def add_message(self, channel_id: int, user_id: int, role: str, content: str, 
                         bot_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            bot_name=bot_name,
            metadata=metadata or {}
        )
        self.messages.append(message)
        return message
    
    async def get_context(self, channel_id: int, user_id: int) -> ConversationContext:
        key = f"{channel_id}_{user_id}"
        if key not in self.contexts:
            self.contexts[key] = ConversationContext(
                channel_id=channel_id,
                user_id=user_id,
                messages=[],
                last_updated=datetime.now()
            )
        return self.contexts[key]


class MockAIModel(AIModel):
    """Mock implementation of AIModel for testing."""
    
    def __init__(self, response_text: str = "Mock AI response"):
        self.response_text = response_text
        self.call_count = 0
        self.last_messages = None
    
    async def generate_response(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        self.call_count += 1
        self.last_messages = messages
        return f"{self.response_text} #{self.call_count}"


class MockRateLimiter(RateLimiter):
    """Mock implementation of RateLimiter for testing."""
    
    def __init__(self, allow_requests: bool = True):
        self.allow_requests = allow_requests
        self.recorded_requests = []
    
    def can_request(self, user_id: str) -> bool:
        return self.allow_requests
    
    def record_request(self, user_id: str) -> None:
        self.recorded_requests.append((user_id, datetime.now()))


class MockNotificationSender(NotificationSender):
    """Mock implementation of NotificationSender for testing."""
    
    def __init__(self):
        self.sent_messages = []
    
    async def send_message(self, channel, content: str) -> None:
        self.sent_messages.append(content)
    
    async def send_chunked_message(self, channel, content: str) -> None:
        self.sent_messages.append(content)


class MockDiscordMessage:
    """Mock Discord message for testing."""
    
    def __init__(self, content: str, author_name: str = "TestUser", channel_name: str = "test-channel", 
                 author_id: int = 12345, channel_id: int = 67890, is_bot: bool = False):
        self.content = content
        self.author = Mock()
        self.author.display_name = author_name
        self.author.id = author_id
        self.author.bot = is_bot
        
        self.channel = Mock()
        self.channel.name = channel_name
        self.channel.id = channel_id
        
        self.created_at = datetime.now()
        self.id = 999


class TestMessageCoordinator:
    """Test MessageCoordinator business logic."""
    
    @pytest.fixture
    def coordinator(self):
        storage = MockMessageStorage()
        rate_limiter = MockRateLimiter()
        global_settings = {
            'max_concurrent_responses': 2,
            'response_delay': '1-3',
            'cooldown_period': 30
        }
        return MessageCoordinator(storage, rate_limiter, global_settings)
    
    @pytest.mark.asyncio
    async def test_should_handle_message_bot_message_rejected(self, coordinator):
        """Test that bot messages are rejected."""
        message = MockDiscordMessage("Hello", is_bot=True)
        result = await coordinator.should_handle_message("testbot", message, ["test-channel"])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_handle_message_channel_pattern_match(self, coordinator):
        """Test channel pattern matching."""
        message = MockDiscordMessage("Hello", channel_name="general")
        
        # Should match exact channel name
        result = await coordinator.should_handle_message("testbot", message, ["general"])
        assert result is True
        
        # Should match wildcard pattern
        result = await coordinator.should_handle_message("testbot", message, ["gen*"])
        assert result is True
        
        # Should not match different channel
        result = await coordinator.should_handle_message("testbot", message, ["different"])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_handle_message_command_rejected(self, coordinator):
        """Test that command messages are rejected."""
        message = MockDiscordMessage("!help", channel_name="general")
        result = await coordinator.should_handle_message("testbot", message, ["general"])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_should_handle_message_rate_limited(self, coordinator):
        """Test rate limiting behavior."""
        # Mock rate limiter to reject requests
        coordinator.rate_limiter.allow_requests = False
        
        message = MockDiscordMessage("Hello", channel_name="general")
        result = await coordinator.should_handle_message("testbot", message, ["general"])
        assert result is False
    
    @pytest.mark.asyncio
    async def test_mark_bot_responding_and_complete(self, coordinator):
        """Test bot response tracking."""
        channel_id = 12345
        bot_name = "testbot"
        
        # Mark bot as responding
        await coordinator.mark_bot_responding(bot_name, channel_id)
        assert channel_id in coordinator.active_responses
        assert bot_name in coordinator.active_responses[channel_id]
        
        # Mark response complete
        await coordinator.mark_response_complete(bot_name, channel_id)
        assert channel_id not in coordinator.active_responses


class TestResponseGenerator:
    """Test ResponseGenerator business logic."""
    
    @pytest.fixture
    def response_generator(self):
        ai_model = MockAIModel("Test response")
        storage = MockMessageStorage()
        return ResponseGenerator(ai_model, storage)
    
    @pytest.mark.asyncio
    async def test_generate_response_success(self, response_generator):
        """Test successful response generation."""
        response = await response_generator.generate_response(
            "sage", "What is wisdom?", 12345, 67890
        )
        
        assert "Test response" in response
        assert response_generator.ai_model.call_count == 1
        assert response_generator.ai_model.last_messages is not None
        
        # Check that system prompt was included
        messages = response_generator.ai_model.last_messages
        assert any(msg.get('role') == 'system' for msg in messages)
        assert any('sage' in msg.get('content', '').lower() for msg in messages if msg.get('role') == 'system')
    
    @pytest.mark.asyncio
    async def test_generate_response_with_context(self, response_generator):
        """Test response generation with conversation context."""
        # Add some context to storage
        context = await response_generator.storage.get_context(12345, 67890)
        context.messages.append(ConversationMessage(
            role="user",
            content="Previous question",
            timestamp=datetime.now(),
            bot_name=None
        ))
        context.messages.append(ConversationMessage(
            role="assistant",
            content="Previous answer",
            timestamp=datetime.now(),
            bot_name="sage"
        ))
        
        response = await response_generator.generate_response(
            "sage", "Follow up question", 12345, 67890
        )
        
        assert "Test response" in response
        messages = response_generator.ai_model.last_messages
        
        # Should include context messages
        assert len(messages) >= 3  # system + context + current
        assert any(msg.get('content') == "Previous question" for msg in messages)
    
    def test_build_message_history_includes_system_prompt(self, response_generator):
        """Test that system prompts are included for known bots."""
        context = ConversationContext(
            channel_id=12345,
            user_id=67890,
            messages=[],
            last_updated=datetime.now()
        )
        
        messages = response_generator._build_message_history("sage", context, "Test message")
        
        assert len(messages) == 2  # system + user message
        assert messages[0]['role'] == 'system'
        assert 'sage' in messages[0]['content'].lower()
        assert messages[1]['role'] == 'user'
        assert messages[1]['content'] == "Test message"


class TestBotOrchestrator:
    """Test BotOrchestrator integration."""
    
    @pytest.fixture
    def orchestrator(self):
        storage = MockMessageStorage()
        rate_limiter = MockRateLimiter()
        notification_sender = MockNotificationSender()
        global_settings = {'max_concurrent_responses': 2, 'response_delay': '1-3', 'cooldown_period': 30}
        
        coordinator = MessageCoordinator(storage, rate_limiter, global_settings)
        ai_model = MockAIModel("Orchestrator response")
        response_generator = ResponseGenerator(ai_model, storage)
        
        return BotOrchestrator(coordinator, response_generator, storage, rate_limiter, notification_sender)
    
    @pytest.mark.asyncio
    async def test_process_message_success_flow(self, orchestrator):
        """Test complete message processing flow."""
        message = MockDiscordMessage("Hello world", channel_name="general")
        
        result = await orchestrator.process_message("testbot", message, ["general"])
        
        assert result is True
        assert len(orchestrator.notification_sender.sent_messages) == 1
        assert "Orchestrator response" in orchestrator.notification_sender.sent_messages[0]
        assert len(orchestrator.storage.messages) == 2  # user + bot messages
    
    @pytest.mark.asyncio
    async def test_process_message_rejected_by_coordinator(self, orchestrator):
        """Test message rejection by coordinator."""
        # Bot message should be rejected
        message = MockDiscordMessage("Hello", is_bot=True)
        
        result = await orchestrator.process_message("testbot", message, ["general"])
        
        assert result is False
        assert len(orchestrator.notification_sender.sent_messages) == 0
        assert len(orchestrator.storage.messages) == 0
    
    @pytest.mark.asyncio
    async def test_process_message_rate_limited(self, orchestrator):
        """Test rate limiting behavior."""
        orchestrator.rate_limiter.allow_requests = False
        message = MockDiscordMessage("Hello", channel_name="general")
        
        result = await orchestrator.process_message("testbot", message, ["general"])
        
        assert result is False
        assert len(orchestrator.notification_sender.sent_messages) == 0
    
    @pytest.mark.asyncio
    async def test_process_message_handles_errors_gracefully(self, orchestrator):
        """Test error handling in message processing."""
        # Make AI model fail
        orchestrator.response_generator.ai_model = Mock()
        orchestrator.response_generator.ai_model.generate_response = AsyncMock(side_effect=Exception("AI Error"))
        
        message = MockDiscordMessage("Hello", channel_name="general")
        
        result = await orchestrator.process_message("testbot", message, ["general"])
        
        # Should return False on error but not crash
        assert result is False
        
        # Should send error message to user
        assert len(orchestrator.notification_sender.sent_messages) == 1
        assert "error" in orchestrator.notification_sender.sent_messages[0].lower()
        
        # Coordination state should be cleaned up
        assert len(orchestrator.coordinator.active_responses) == 0


@pytest.mark.asyncio
async def test_integration_multiple_bots_coordination():
    """Integration test for multiple bot coordination."""
    storage = MockMessageStorage()
    rate_limiter = MockRateLimiter()
    notification_sender = MockNotificationSender()
    global_settings = {'max_concurrent_responses': 1, 'response_delay': '0-0', 'cooldown_period': 1}
    
    coordinator = MessageCoordinator(storage, rate_limiter, global_settings)
    ai_model = MockAIModel("Response")
    response_generator = ResponseGenerator(ai_model, storage)
    orchestrator = BotOrchestrator(coordinator, response_generator, storage, rate_limiter, notification_sender)
    
    message = MockDiscordMessage("Hello", channel_name="general")
    
    # First bot should succeed
    result1 = await orchestrator.process_message("bot1", message, ["general"])
    assert result1 is True
    
    # Second bot should be rejected due to max_concurrent_responses = 1
    # (This would need the first bot to still be "active", which requires timing)
    # For this test, we'll verify the coordination logic separately
    await coordinator.mark_bot_responding("bot1", message.channel.id)
    result2 = await coordinator.should_handle_message("bot2", message, ["general"])
    assert result2 is False  # Should be rejected due to coordination


if __name__ == "__main__":
    pytest.main([__file__])