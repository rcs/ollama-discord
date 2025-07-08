"""Port interfaces for the ollama-discord bot system."""

from typing import Protocol, List, Dict, Any, Optional
from .conversation_state import ConversationMessage, ConversationContext


class MessageStorage(Protocol):
    """Port for storing and retrieving conversation messages."""
    
    async def add_message(self, channel_id: int, user_id: int, role: str, content: str, 
                         bot_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """Add a message to storage."""
        ...
    
    async def get_context(self, channel_id: int, user_id: int) -> ConversationContext:
        """Get conversation context for a channel/user combination."""
        ...


class AIModel(Protocol):
    """Port for AI model interactions."""
    
    async def generate_response(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        """Generate a response from the AI model."""
        ...


class RateLimiter(Protocol):
    """Port for rate limiting functionality."""
    
    def can_request(self, user_id: str) -> bool:
        """Check if user can make a request."""
        ...
    
    def record_request(self, user_id: str) -> None:
        """Record a request for rate limiting."""
        ...


class NotificationSender(Protocol):
    """Port for sending notifications/messages."""
    
    async def send_message(self, channel, content: str) -> None:
        """Send a message to a channel."""
        ...
    
    async def send_chunked_message(self, channel, content: str) -> None:
        """Send a message, chunking if necessary."""
        ...