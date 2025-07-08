"""Tests for adapter implementations."""

import pytest
import tempfile
from unittest.mock import patch, Mock, AsyncMock
from pathlib import Path
import json
from datetime import datetime

from src.adapters import FileMessageStorage, OllamaAI, MemoryRateLimiter, DiscordNotificationSender
from src.conversation_state import ConversationState


class TestFileMessageStorage:
    """Test FileMessageStorage adapter."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            conv_state = ConversationState(
                storage_path=temp_dir,
                context_depth=10,
                max_history=100
            )
            yield FileMessageStorage(conv_state)
    
    @pytest.mark.asyncio
    async def test_add_message(self, temp_storage):
        """Test adding a message to storage."""
        message = await temp_storage.add_message(
            channel_id=12345,
            user_id=67890,
            role="user",
            content="Test message",
            metadata={"test": "data"}
        )
        
        assert message.role == "user"
        assert message.content == "Test message"
        assert message.metadata["test"] == "data"
        assert isinstance(message.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_get_context(self, temp_storage):
        """Test getting conversation context."""
        context = await temp_storage.get_context(12345, 67890)
        
        assert context.channel_id == 12345
        assert context.user_id == 67890
        assert isinstance(context.messages, list)
        assert isinstance(context.last_updated, datetime)
    
    @pytest.mark.asyncio
    async def test_message_persistence(self, temp_storage):
        """Test that messages are persisted across context retrievals."""
        # Add a message
        await temp_storage.add_message(
            channel_id=12345,
            user_id=67890,
            role="user",
            content="First message"
        )
        
        # Get context and verify message exists
        context = await temp_storage.get_context(12345, 67890)
        assert len(context.messages) == 1
        assert context.messages[0].content == "First message"


class TestOllamaAI:
    """Test OllamaAI adapter."""
    
    def test_initialization(self):
        """Test OllamaAI initialization."""
        ai = OllamaAI("http://localhost:11434", "llama3", timeout=30)
        assert ai.base_url == "http://localhost:11434"
        assert ai.model == "llama3"
        assert ai.timeout == 30
    
    @pytest.mark.asyncio
    @patch('src.adapters.requests.post')
    async def test_generate_response_success(self, mock_post):
        """Test successful response generation."""
        # Mock successful Ollama response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "message": {"content": "Generated response"}
        }
        mock_post.return_value = mock_response
        
        ai = OllamaAI("http://localhost:11434", "llama3")
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"}
        ]
        
        response = await ai.generate_response(messages)
        
        assert response == "Generated response"
        mock_post.assert_called_once()
        
        # Verify request parameters
        call_args = mock_post.call_args
        assert call_args[1]['json']['model'] == 'llama3'
        assert call_args[1]['json']['messages'] == messages
        assert call_args[1]['json']['stream'] is False
    
    @pytest.mark.asyncio
    @patch('src.adapters.requests.post')
    async def test_generate_response_with_custom_model(self, mock_post):
        """Test response generation with custom model."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "message": {"content": "Custom model response"}
        }
        mock_post.return_value = mock_response
        
        ai = OllamaAI("http://localhost:11434", "llama3")
        messages = [{"role": "user", "content": "Hello"}]
        
        response = await ai.generate_response(messages, model="custom-model")
        
        assert response == "Custom model response"
        
        # Verify custom model was used
        call_args = mock_post.call_args
        assert call_args[1]['json']['model'] == 'custom-model'
    
    @pytest.mark.asyncio
    @patch('src.adapters.requests.post')
    async def test_generate_response_http_error(self, mock_post):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP Error")
        mock_post.return_value = mock_response
        
        ai = OllamaAI("http://localhost:11434", "llama3")
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(Exception, match="HTTP Error"):
            await ai.generate_response(messages)


class TestMemoryRateLimiter:
    """Test MemoryRateLimiter adapter."""
    
    def test_initialization(self):
        """Test rate limiter initialization."""
        limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=5)
        assert limiter.enabled is True
        assert limiter.max_requests_per_minute == 5
        assert limiter.requests == {}
    
    def test_disabled_rate_limiter(self):
        """Test that disabled rate limiter allows all requests."""
        limiter = MemoryRateLimiter(enabled=False)
        
        # Should allow requests when disabled
        assert limiter.can_request("user1") is True
        
        # Recording should be no-op when disabled
        limiter.record_request("user1")
        assert limiter.requests == {}
    
    def test_rate_limiting_behavior(self):
        """Test rate limiting logic."""
        limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=2)
        
        # First request should be allowed
        assert limiter.can_request("user1") is True
        limiter.record_request("user1")
        
        # Second request should be allowed
        assert limiter.can_request("user1") is True
        limiter.record_request("user1")
        
        # Third request should be denied
        assert limiter.can_request("user1") is False
        
        # Different user should be allowed
        assert limiter.can_request("user2") is True
    
    def test_request_cleanup(self):
        """Test that old requests are cleaned up."""
        limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=1)
        
        # Add a request
        limiter.record_request("user1")
        assert "user1" in limiter.requests
        
        # Manually set old timestamp
        old_time = datetime.now().replace(year=2020)
        limiter.requests["user1"] = [old_time]
        
        # Should allow new request after cleanup
        assert limiter.can_request("user1") is True
        
        # Old request should be cleaned up
        assert len(limiter.requests["user1"]) == 0


class TestDiscordNotificationSender:
    """Test DiscordNotificationSender adapter."""
    
    def test_initialization(self):
        """Test notification sender initialization."""
        sender = DiscordNotificationSender(max_message_length=2000)
        assert sender.max_message_length == 2000
    
    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test basic message sending."""
        sender = DiscordNotificationSender()
        mock_channel = AsyncMock()
        
        await sender.send_message(mock_channel, "Test message")
        
        mock_channel.send.assert_called_once_with("Test message")
    
    @pytest.mark.asyncio
    @patch('src.adapters.format_message_for_discord')
    async def test_send_chunked_message(self, mock_format):
        """Test chunked message sending."""
        mock_format.return_value = ["Chunk 1", "Chunk 2"]
        
        sender = DiscordNotificationSender(max_message_length=1000)
        mock_channel = AsyncMock()
        
        await sender.send_chunked_message(mock_channel, "Long message")
        
        # Should format message and send all chunks
        mock_format.assert_called_once_with("Long message", 1000)
        assert mock_channel.send.call_count == 2
        mock_channel.send.assert_any_call("Chunk 1")
        mock_channel.send.assert_any_call("Chunk 2")
    
    @pytest.mark.asyncio
    async def test_send_chunked_message_single_chunk(self):
        """Test chunked message with single chunk."""
        sender = DiscordNotificationSender()
        mock_channel = AsyncMock()
        
        # Short message should not be chunked
        with patch('src.adapters.format_message_for_discord') as mock_format:
            mock_format.return_value = ["Short message"]
            
            await sender.send_chunked_message(mock_channel, "Short message")
            
            mock_channel.send.assert_called_once_with("Short message")


if __name__ == "__main__":
    pytest.main([__file__])