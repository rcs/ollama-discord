"""Unit tests for ConversationState."""

import pytest
import tempfile
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.conversation_state import (
    ConversationState, ConversationMessage, ConversationContext
)


@pytest.fixture
def temp_storage_path():
    """Create a temporary storage path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def conversation_state(temp_storage_path):
    """Create a ConversationState instance."""
    return ConversationState(
        storage_path=temp_storage_path,
        context_depth=5,
        max_history=100
    )


class TestConversationMessage:
    """Test ConversationMessage dataclass."""
    
    def test_message_creation(self):
        """Test creating a ConversationMessage."""
        timestamp = datetime.now()
        message = ConversationMessage(
            role="user",
            content="Hello",
            timestamp=timestamp,
            bot_name=None,
            metadata={"test": "value"}
        )
        
        assert message.role == "user"
        assert message.content == "Hello"
        assert message.timestamp == timestamp
        assert message.bot_name is None
        assert message.metadata["test"] == "value"
    
    def test_message_default_metadata(self):
        """Test ConversationMessage with default metadata."""
        message = ConversationMessage(
            role="user",
            content="Hello",
            timestamp=datetime.now()
        )
        
        assert message.metadata == {}
    


class TestConversationContext:
    """Test ConversationContext dataclass."""
    
    def test_context_creation(self):
        """Test creating a ConversationContext."""
        timestamp = datetime.now()
        messages = [
            ConversationMessage("user", "Hello", timestamp),
            ConversationMessage("assistant", "Hi", timestamp, "bot1")
        ]
        
        context = ConversationContext(
            channel_id=123,
            user_id=456,
            messages=messages,
            last_updated=timestamp,
            topic="greeting",
            participants=["bot1"]
        )
        
        assert context.channel_id == 123
        assert context.user_id == 456
        assert len(context.messages) == 2
        assert context.topic == "greeting"
        assert context.participants == ["bot1"]
    
    def test_context_default_participants(self):
        """Test ConversationContext with default participants."""
        context = ConversationContext(
            channel_id=123,
            user_id=456,
            messages=[],
            last_updated=datetime.now()
        )
        
        assert context.participants == []
    
    def test_get_recent_messages(self):
        """Test getting recent messages."""
        messages = [
            ConversationMessage("user", f"Message {i}", datetime.now())
            for i in range(10)
        ]
        
        context = ConversationContext(
            channel_id=123,
            user_id=456,
            messages=messages,
            last_updated=datetime.now()
        )
        
        recent = context.get_recent_messages(5)
        assert len(recent) == 5
        assert recent[-1].content == "Message 9"  # Most recent
    
    def test_get_messages_since(self):
        """Test getting messages since timestamp."""
        now = datetime.now()
        old_time = now - timedelta(hours=1)
        
        messages = [
            ConversationMessage("user", "Old message", old_time),
            ConversationMessage("user", "New message", now)
        ]
        
        context = ConversationContext(
            channel_id=123,
            user_id=456,
            messages=messages,
            last_updated=now
        )
        
        recent = context.get_messages_since(now - timedelta(minutes=30))
        assert len(recent) == 1
        assert recent[0].content == "New message"
    
    def test_get_bot_messages(self):
        """Test getting messages from specific bot."""
        messages = [
            ConversationMessage("user", "User message", datetime.now()),
            ConversationMessage("assistant", "Bot1 message", datetime.now(), "bot1"),
            ConversationMessage("assistant", "Bot2 message", datetime.now(), "bot2")
        ]
        
        context = ConversationContext(
            channel_id=123,
            user_id=456,
            messages=messages,
            last_updated=datetime.now()
        )
        
        bot1_messages = context.get_bot_messages("bot1")
        assert len(bot1_messages) == 1
        assert bot1_messages[0].content == "Bot1 message"
    
    def test_add_participant(self):
        """Test adding participants."""
        context = ConversationContext(
            channel_id=123,
            user_id=456,
            messages=[],
            last_updated=datetime.now()
        )
        
        context.add_participant("bot1")
        assert "bot1" in context.participants
        
        # Adding same participant again should not duplicate
        context.add_participant("bot1")
        assert context.participants.count("bot1") == 1
    


class TestConversationState:
    """Test ConversationState class."""
    
    def test_initialization(self, conversation_state, temp_storage_path):
        """Test ConversationState initialization."""
        assert conversation_state.storage_path == Path(temp_storage_path)
        assert conversation_state.context_depth == 5
        assert conversation_state.max_history == 100
        assert len(conversation_state._conversations) == 0
    
    def test_get_conversation_key(self, conversation_state):
        """Test getting conversation key."""
        key = conversation_state._get_conversation_key(123, 456)
        assert key == "123_456"
    
    def test_get_storage_file(self, conversation_state):
        """Test getting storage file path."""
        file_path = conversation_state._get_storage_file("123_456")
        assert file_path.name == "123_456.json"
        assert file_path.parent == conversation_state.storage_path
    
    @pytest.mark.asyncio
    async def test_get_context_new_conversation(self, conversation_state):
        """Test getting context for new conversation."""
        context = await conversation_state.get_context(123, 456)
        
        assert context.channel_id == 123
        assert context.user_id == 456
        assert len(context.messages) == 0
        assert context.participants == []
    
    @pytest.mark.asyncio
    async def test_get_context_cached(self, conversation_state):
        """Test getting cached context."""
        # First call creates and caches
        context1 = await conversation_state.get_context(123, 456)
        
        # Second call should return cached version
        context2 = await conversation_state.get_context(123, 456)
        
        assert context1 is context2
        assert conversation_state._stats['cache_hits'] >= 1
    
    @pytest.mark.asyncio
    async def test_add_message(self, conversation_state):
        """Test adding a message."""
        message = await conversation_state.add_message(
            channel_id=123,
            user_id=456,
            role="user",
            content="Hello world",
            metadata={"source": "test"}
        )
        
        assert message.role == "user"
        assert message.content == "Hello world"
        assert message.metadata["source"] == "test"
        
        # Verify message was added to context
        context = await conversation_state.get_context(123, 456)
        assert len(context.messages) == 1
        assert context.messages[0] == message
    
    @pytest.mark.asyncio
    async def test_add_bot_message(self, conversation_state):
        """Test adding a bot message."""
        await conversation_state.add_message(
            channel_id=123,
            user_id=456,
            role="assistant",
            content="Hi there",
            bot_name="test-bot"
        )
        
        context = await conversation_state.get_context(123, 456)
        assert "test-bot" in context.participants
        assert context.messages[0].bot_name == "test-bot"
    
    @pytest.mark.asyncio
    async def test_message_history_limit(self, conversation_state):
        """Test that message history is limited."""
        # Add messages beyond the limit
        for i in range(150):  # max_history is 100
            await conversation_state.add_message(
                channel_id=123,
                user_id=456,
                role="user",
                content=f"Message {i}"
            )
        
        context = await conversation_state.get_context(123, 456)
        assert len(context.messages) == 100  # Should be limited to max_history
        assert context.messages[-1].content == "Message 149"  # Most recent preserved
    
    @pytest.mark.asyncio
    async def test_save_and_load_conversation(self, conversation_state, temp_storage_path):
        """Test saving and loading conversation from storage."""
        # Add a message to create conversation
        await conversation_state.add_message(
            channel_id=123,
            user_id=456,
            role="user",
            content="Test message"
        )
        
        # Wait for async save to complete
        await asyncio.sleep(0.1)
        
        # Verify file was created
        storage_file = Path(temp_storage_path) / "123_456.json"
        assert storage_file.exists()
        
        # Clear cache and reload
        conversation_state._conversations.clear()
        
        context = await conversation_state.get_context(123, 456)
        assert len(context.messages) == 1
        assert context.messages[0].content == "Test message"
    
    @pytest.mark.asyncio
    async def test_get_channel_conversations(self, conversation_state):
        """Test getting all conversations in a channel."""
        # Create multiple conversations in same channel
        await conversation_state.add_message(123, 456, "user", "Message 1")
        await conversation_state.add_message(123, 789, "user", "Message 2")
        await conversation_state.add_message(456, 123, "user", "Message 3")  # Different channel
        
        conversations = await conversation_state.get_channel_conversations(123)
        
        assert len(conversations) == 2
        channel_ids = [conv.channel_id for conv in conversations]
        assert all(cid == 123 for cid in channel_ids)
    
    @pytest.mark.asyncio
    async def test_get_bot_activity(self, conversation_state):
        """Test getting bot activity statistics."""
        # Add messages from different bots
        await conversation_state.add_message(123, 456, "assistant", "Bot1 message", "bot1")
        await conversation_state.add_message(123, 456, "assistant", "Bot2 message", "bot2")
        await conversation_state.add_message(123, 456, "assistant", "Bot1 again", "bot1")
        
        activity = await conversation_state.get_bot_activity("bot1")
        
        assert activity["bot_name"] == "bot1"
        assert activity["total_messages"] == 2
        assert activity["active_conversations"] == 1
        assert activity["unique_channels"] == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_old_conversations(self, conversation_state):
        """Test cleaning up old conversations."""
        # Add a conversation
        await conversation_state.add_message(123, 456, "user", "Old message")
        
        # Simulate old conversation by modifying timestamp
        context = await conversation_state.get_context(123, 456)
        context.last_updated = datetime.now() - timedelta(days=31)
        
        # Run cleanup
        cleaned = await conversation_state.cleanup_old_conversations(timedelta(days=30))
        
        assert cleaned >= 1
        assert len(conversation_state._conversations) == 0  # Should be removed from cache
    
    @pytest.mark.asyncio
    async def test_get_conversation_summary(self, conversation_state):
        """Test getting conversation summary."""
        # Add various messages
        await conversation_state.add_message(123, 456, "user", "User message 1")
        await conversation_state.add_message(123, 456, "assistant", "Bot response", "bot1")
        await conversation_state.add_message(123, 456, "user", "User message 2")
        
        summary = await conversation_state.get_conversation_summary(123, 456)
        
        assert summary["channel_id"] == 123
        assert summary["user_id"] == 456
        assert summary["total_messages"] == 3
        assert summary["user_messages"] == 2
        assert summary["bot_messages"] == 1
        assert summary["participants"] == ["bot1"]
        assert summary["bot_participation"]["bot1"] == 1
    
    @pytest.mark.asyncio
    async def test_reset_conversation(self, conversation_state, temp_storage_path):
        """Test resetting a conversation."""
        # Create conversation
        await conversation_state.add_message(123, 456, "user", "Test message")
        
        # Wait for save
        await asyncio.sleep(0.1)
        
        # Verify file exists
        storage_file = Path(temp_storage_path) / "123_456.json"
        assert storage_file.exists()
        
        # Reset conversation
        await conversation_state.reset_conversation(123, 456)
        
        # Verify removed from cache and storage
        assert "123_456" not in conversation_state._conversations
        assert not storage_file.exists()
    
    @pytest.mark.asyncio
    
    @pytest.mark.asyncio
    async def test_export_conversation_txt(self, conversation_state):
        """Test exporting conversation as text."""
        await conversation_state.add_message(123, 456, "user", "Hello")
        await conversation_state.add_message(123, 456, "assistant", "Hi", "bot1")
        
        export_data = await conversation_state.export_conversation(123, 456, "txt")
        
        assert "User: Hello" in export_data
        assert "bot1: Hi" in export_data
    
    @pytest.mark.asyncio
    async def test_export_conversation_invalid_format(self, conversation_state):
        """Test exporting conversation with invalid format."""
        with pytest.raises(ValueError, match="Unsupported export format"):
            await conversation_state.export_conversation(123, 456, "invalid")
    
    def test_get_stats(self, conversation_state):
        """Test getting conversation state statistics."""
        stats = conversation_state.get_stats()
        
        assert "messages_processed" in stats
        assert "conversations_active" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
    
    @pytest.mark.asyncio
    async def test_shutdown(self, conversation_state):
        """Test shutting down conversation state."""
        # Add a conversation
        await conversation_state.add_message(123, 456, "user", "Test")
        
        # Shutdown
        await conversation_state.shutdown()
        
        # Verify cache is cleared
        assert len(conversation_state._conversations) == 0


if __name__ == "__main__":
    pytest.main([__file__])