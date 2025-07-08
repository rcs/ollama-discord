"""Tests for SQLite storage adapter."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from src.sqlite_storage import SQLiteMessageStorage
from src.conversation_state import ConversationMessage, ConversationContext


class TestSQLiteMessageStorage:
    """Test SQLite message storage functionality."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def sqlite_storage(self, temp_db_path):
        """Create SQLite storage instance."""
        return SQLiteMessageStorage(
            bot_name="test_bot",
            db_path=temp_db_path,
            session_timeout=3600
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, sqlite_storage):
        """Test SQLite storage initialization."""
        # Initialize DB
        await sqlite_storage._initialize_db()
        
        # Check that the database was created
        assert Path(sqlite_storage.db_path).exists()
        
        # Check that tables exist by trying to add a message
        message = await sqlite_storage.add_message(
            channel_id=123,
            user_id=456,
            role="user",
            content="Hello world!"
        )
        
        assert message.role == "user"
        assert message.content == "Hello world!"
        assert message.bot_name == "test_bot"
    
    @pytest.mark.asyncio
    async def test_add_message(self, sqlite_storage):
        """Test adding messages to SQLite storage."""
        # Add a user message
        user_message = await sqlite_storage.add_message(
            channel_id=123,
            user_id=456,
            role="user",
            content="Hello bot!"
        )
        
        # Add a bot response
        bot_message = await sqlite_storage.add_message(
            channel_id=123,
            user_id=456,
            role="assistant",
            content="Hello user!"
        )
        
        # Verify messages
        assert user_message.role == "user"
        assert user_message.content == "Hello bot!"
        assert bot_message.role == "assistant"
        assert bot_message.content == "Hello user!"
        
        # Both messages should be in the same session
        context = await sqlite_storage.get_context(123, 456)
        assert len(context.messages) == 2
        assert context.messages[0].content == "Hello bot!"
        assert context.messages[1].content == "Hello user!"
    
    @pytest.mark.asyncio
    async def test_get_context(self, sqlite_storage):
        """Test getting conversation context."""
        # Add multiple messages
        await sqlite_storage.add_message(123, 456, "user", "Message 1")
        await sqlite_storage.add_message(123, 456, "assistant", "Response 1")
        await sqlite_storage.add_message(123, 456, "user", "Message 2")
        await sqlite_storage.add_message(123, 456, "assistant", "Response 2")
        
        # Get context
        context = await sqlite_storage.get_context(123, 456)
        
        # Should have all messages in chronological order
        assert len(context.messages) == 4
        assert context.messages[0].content == "Message 1"
        assert context.messages[1].content == "Response 1"
        assert context.messages[2].content == "Message 2"
        assert context.messages[3].content == "Response 2"
        
        # Context should have correct channel and user
        assert context.channel_id == 123
        assert context.user_id == 456
    
    @pytest.mark.asyncio
    async def test_bot_isolation(self, temp_db_path):
        """Test that different bots have isolated storage."""
        # Create two storage instances for different bots
        bot1_storage = SQLiteMessageStorage("bot1", temp_db_path)
        bot2_storage = SQLiteMessageStorage("bot2", temp_db_path)
        
        # Add messages to each bot
        await bot1_storage.add_message(123, 456, "user", "Message for bot1")
        await bot2_storage.add_message(123, 456, "user", "Message for bot2")
        
        # Get context for each bot
        bot1_context = await bot1_storage.get_context(123, 456)
        bot2_context = await bot2_storage.get_context(123, 456)
        
        # Each bot should only see its own messages
        assert len(bot1_context.messages) == 1
        assert len(bot2_context.messages) == 1
        assert bot1_context.messages[0].content == "Message for bot1"
        assert bot2_context.messages[0].content == "Message for bot2"
    
    @pytest.mark.asyncio
    async def test_session_management(self, sqlite_storage):
        """Test session creation and management."""
        # Add messages - should create a session
        await sqlite_storage.add_message(123, 456, "user", "Message 1")
        await sqlite_storage.add_message(123, 456, "assistant", "Response 1")
        
        # Get session ID from first message
        session_id1 = await sqlite_storage._get_or_create_session(123, 456)
        
        # Add another message - should use same session
        await sqlite_storage.add_message(123, 456, "user", "Message 2")
        session_id2 = await sqlite_storage._get_or_create_session(123, 456)
        
        # Should be same session
        assert session_id1 == session_id2
    
    @pytest.mark.asyncio
    async def test_metadata_storage(self, sqlite_storage):
        """Test storing and retrieving message metadata."""
        metadata = {
            "user_display_name": "TestUser",
            "message_type": "command",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # Add message with metadata
        message = await sqlite_storage.add_message(
            channel_id=123,
            user_id=456,
            role="user",
            content="Test message",
            metadata=metadata
        )
        
        # Verify metadata was stored
        assert message.metadata == metadata
        
        # Verify metadata is retrieved correctly
        context = await sqlite_storage.get_context(123, 456)
        assert len(context.messages) == 1
        assert context.messages[0].metadata == metadata
    
    @pytest.mark.asyncio
    async def test_cleanup_old_sessions(self, sqlite_storage):
        """Test cleaning up old sessions."""
        # Add some messages
        await sqlite_storage.add_message(123, 456, "user", "Message 1")
        await sqlite_storage.add_message(123, 456, "assistant", "Response 1")
        
        # Verify messages exist
        context = await sqlite_storage.get_context(123, 456)
        assert len(context.messages) == 2
        
        # Clean up old sessions (using 0 days to clean everything)
        await sqlite_storage.cleanup_old_sessions(days_old=0)
        
        # Verify messages are gone
        context = await sqlite_storage.get_context(123, 456)
        assert len(context.messages) == 0
    
    @pytest.mark.asyncio
    async def test_different_channels(self, sqlite_storage):
        """Test that different channels have isolated contexts."""
        # Add messages to different channels
        await sqlite_storage.add_message(123, 456, "user", "Message in channel 123")
        await sqlite_storage.add_message(789, 456, "user", "Message in channel 789")
        
        # Get context for each channel
        context_123 = await sqlite_storage.get_context(123, 456)
        context_789 = await sqlite_storage.get_context(789, 456)
        
        # Each channel should have its own message
        assert len(context_123.messages) == 1
        assert len(context_789.messages) == 1
        assert context_123.messages[0].content == "Message in channel 123"
        assert context_789.messages[0].content == "Message in channel 789"
    
    @pytest.mark.asyncio
    async def test_different_users(self, sqlite_storage):
        """Test that different users have isolated contexts."""
        # Add messages from different users in same channel
        await sqlite_storage.add_message(123, 456, "user", "Message from user 456")
        await sqlite_storage.add_message(123, 789, "user", "Message from user 789")
        
        # Get context for each user
        context_456 = await sqlite_storage.get_context(123, 456)
        context_789 = await sqlite_storage.get_context(123, 789)
        
        # Each user should have their own message
        assert len(context_456.messages) == 1
        assert len(context_789.messages) == 1
        assert context_456.messages[0].content == "Message from user 456"
        assert context_789.messages[0].content == "Message from user 789"