"""Adapter implementations for external dependencies."""

import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

from .ports import MessageStorage, AIModel, RateLimiter, NotificationSender
from .conversation_state import ConversationState, ConversationMessage, ConversationContext
from .bot import format_message_for_discord
from .sqlite_storage import SQLiteMessageStorage


class FileMessageStorage(MessageStorage):
    """File-based message storage adapter."""
    
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
    
    async def add_message(self, channel_id: int, user_id: int, role: str, content: str, 
                         bot_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """Add a message to storage."""
        return await self.conversation_state.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role=role,
            content=content,
            bot_name=bot_name,
            metadata=metadata
        )
    
    async def get_context(self, channel_id: int, user_id: int) -> ConversationContext:
        """Get conversation context for a channel/user combination."""
        return await self.conversation_state.get_context(channel_id, user_id)


class OllamaAI(AIModel):
    """Ollama AI model adapter."""
    
    def __init__(self, base_url: str, model: str, timeout: int = 60):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
    
    async def generate_response(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        """Generate a response from Ollama."""
        import asyncio
        
        # Use provided model or default
        model_name = model or self.model
        
        # Make request to Ollama
        ollama_url = f"{self.base_url}/api/chat"
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False
        }
        
        # Run blocking request in thread pool
        def make_request():
            response = requests.post(ollama_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()["message"]["content"]
        
        return await asyncio.to_thread(make_request)


class MemoryRateLimiter(RateLimiter):
    """In-memory rate limiter adapter."""
    
    def __init__(self, enabled: bool = True, max_requests_per_minute: int = 10):
        self.enabled = enabled
        self.max_requests_per_minute = max_requests_per_minute
        self.requests: Dict[str, List[datetime]] = {}
    
    def can_request(self, user_id: str) -> bool:
        """Check if user can make a request."""
        if not self.enabled:
            return True
        
        now = datetime.now()
        user_requests = self.requests.get(user_id, [])
        
        # Remove requests older than 1 minute
        user_requests = [req_time for req_time in user_requests 
                        if (now - req_time).total_seconds() < 60]
        
        self.requests[user_id] = user_requests
        
        return len(user_requests) < self.max_requests_per_minute
    
    def record_request(self, user_id: str) -> None:
        """Record a request for rate limiting."""
        if not self.enabled:
            return
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        self.requests[user_id].append(datetime.now())


class DiscordNotificationSender(NotificationSender):
    """Discord notification sender adapter."""
    
    def __init__(self, max_message_length: int = 1900):
        self.max_message_length = max_message_length
    
    async def send_message(self, channel, content: str) -> None:
        """Send a message to a Discord channel."""
        await channel.send(content)
    
    async def send_chunked_message(self, channel, content: str) -> None:
        """Send a message, chunking if necessary to fit Discord's character limit."""
        chunks = format_message_for_discord(content, self.max_message_length)
        
        for chunk in chunks:
            await channel.send(chunk)