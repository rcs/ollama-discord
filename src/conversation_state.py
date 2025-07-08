"""Shared conversation state management for multi-bot system."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
import threading


@dataclass
class ConversationMessage:
    """Represents a single message in a conversation."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime
    bot_name: Optional[str] = None  # Which bot sent this message (if assistant)
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'bot_name': self.bot_name,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        """Create from dictionary."""
        return cls(
            role=data['role'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            bot_name=data.get('bot_name'),
            metadata=data.get('metadata', {})
        )


@dataclass
class ConversationContext:
    """Context for a conversation including message history."""
    channel_id: int
    user_id: int
    messages: List[ConversationMessage]
    last_updated: datetime
    topic: Optional[str] = None
    participants: List[str] = None  # Bot names that have participated
    
    def __post_init__(self):
        if self.participants is None:
            self.participants = []
    
    def get_recent_messages(self, limit: int = 10) -> List[ConversationMessage]:
        """Get the most recent messages."""
        return self.messages[-limit:] if self.messages else []
    
    def get_messages_since(self, since: datetime) -> List[ConversationMessage]:
        """Get messages since a specific timestamp."""
        return [msg for msg in self.messages if msg.timestamp > since]
    
    def get_bot_messages(self, bot_name: str) -> List[ConversationMessage]:
        """Get messages from a specific bot."""
        return [msg for msg in self.messages if msg.bot_name == bot_name]
    
    def add_participant(self, bot_name: str):
        """Add a bot to the participants list."""
        if bot_name not in self.participants:
            self.participants.append(bot_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'channel_id': self.channel_id,
            'user_id': self.user_id,
            'messages': [msg.to_dict() for msg in self.messages],
            'last_updated': self.last_updated.isoformat(),
            'topic': self.topic,
            'participants': self.participants
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Create from dictionary."""
        return cls(
            channel_id=data['channel_id'],
            user_id=data['user_id'],
            messages=[ConversationMessage.from_dict(msg) for msg in data['messages']],
            last_updated=datetime.fromisoformat(data['last_updated']),
            topic=data.get('topic'),
            participants=data.get('participants', [])
        )


class ConversationState:
    """Manages shared conversation state across multiple bots."""
    
    def __init__(self, storage_path: str = "./data/multi_bot_conversations", 
                 context_depth: int = 10, max_history: int = 1000):
        self.storage_path = Path(storage_path)
        self.context_depth = context_depth
        self.max_history = max_history
        self.logger = logging.getLogger(__name__)
        
        # In-memory cache for active conversations
        self._conversations: Dict[str, ConversationContext] = {}
        self._cache_lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'messages_processed': 0,
            'conversations_active': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Initialize storage
        self._initialize_storage()
    
    def _initialize_storage(self):
        """Initialize storage directory."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Initialized conversation storage at {self.storage_path}")
    
    def _get_conversation_key(self, channel_id: int, user_id: int) -> str:
        """Get unique key for a conversation."""
        return f"{channel_id}_{user_id}"
    
    def _get_storage_file(self, conversation_key: str) -> Path:
        """Get storage file path for a conversation."""
        return self.storage_path / f"{conversation_key}.json"
    
    async def get_context(self, channel_id: int, user_id: int) -> ConversationContext:
        """Get conversation context for a channel/user combination."""
        conversation_key = self._get_conversation_key(channel_id, user_id)
        
        with self._cache_lock:
            # Check cache first
            if conversation_key in self._conversations:
                self._stats['cache_hits'] += 1
                return self._conversations[conversation_key]
            
            self._stats['cache_misses'] += 1
            
            # Load from storage
            context = await self._load_conversation(conversation_key, channel_id, user_id)
            
            # Cache the conversation
            self._conversations[conversation_key] = context
            
            return context
    
    async def _load_conversation(self, conversation_key: str, channel_id: int, user_id: int) -> ConversationContext:
        """Load conversation from storage."""
        storage_file = self._get_storage_file(conversation_key)
        
        if storage_file.exists():
            try:
                with open(storage_file, 'r') as f:
                    data = json.load(f)
                    return ConversationContext.from_dict(data)
            except Exception as e:
                self.logger.error(f"Failed to load conversation {conversation_key}: {e}")
        
        # Create new conversation context
        return ConversationContext(
            channel_id=channel_id,
            user_id=user_id,
            messages=[],
            last_updated=datetime.now()
        )
    
    async def add_message(self, channel_id: int, user_id: int, role: str, content: str,
                         bot_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """Add a message to the conversation."""
        conversation_key = self._get_conversation_key(channel_id, user_id)
        
        # Create message
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            bot_name=bot_name,
            metadata=metadata or {}
        )
        
        # Get conversation context
        context = await self.get_context(channel_id, user_id)
        
        with self._cache_lock:
            # Add message to context
            context.messages.append(message)
            context.last_updated = datetime.now()
            
            # Add bot to participants if applicable
            if bot_name:
                context.add_participant(bot_name)
            
            # Trim history if needed
            if len(context.messages) > self.max_history:
                context.messages = context.messages[-self.max_history:]
            
            # Update cache
            self._conversations[conversation_key] = context
            
            # Update statistics
            self._stats['messages_processed'] += 1
        
        # Save to storage (async)
        asyncio.create_task(self._save_conversation(conversation_key, context))
        
        return message
    
    async def _save_conversation(self, conversation_key: str, context: ConversationContext):
        """Save conversation to storage."""
        storage_file = self._get_storage_file(conversation_key)
        
        try:
            # Create a copy to avoid race conditions
            data = context.to_dict()
            
            # Write to temporary file first
            temp_file = storage_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.replace(storage_file)
            
        except Exception as e:
            self.logger.error(f"Failed to save conversation {conversation_key}: {e}")
    
    async def get_channel_conversations(self, channel_id: int, limit: int = 10) -> List[ConversationContext]:
        """Get all conversations in a channel."""
        conversations = []
        
        with self._cache_lock:
            # Check cache first
            for key, context in self._conversations.items():
                if context.channel_id == channel_id:
                    conversations.append(context)
        
        # Load from storage if needed
        if len(conversations) < limit:
            for storage_file in self.storage_path.glob(f"{channel_id}_*.json"):
                if len(conversations) >= limit:
                    break
                
                try:
                    conversation_key = storage_file.stem
                    if conversation_key not in self._conversations:
                        with open(storage_file, 'r') as f:
                            data = json.load(f)
                            context = ConversationContext.from_dict(data)
                            conversations.append(context)
                except Exception as e:
                    self.logger.error(f"Failed to load conversation from {storage_file}: {e}")
        
        # Sort by last updated
        conversations.sort(key=lambda c: c.last_updated, reverse=True)
        
        return conversations[:limit]
    
    async def get_bot_activity(self, bot_name: str, since: Optional[datetime] = None) -> Dict[str, Any]:
        """Get activity statistics for a specific bot."""
        if since is None:
            since = datetime.now() - timedelta(hours=24)
        
        total_messages = 0
        active_conversations = 0
        channels = set()
        
        with self._cache_lock:
            for context in self._conversations.values():
                bot_messages = [msg for msg in context.messages 
                              if msg.bot_name == bot_name and msg.timestamp > since]
                
                if bot_messages:
                    total_messages += len(bot_messages)
                    active_conversations += 1
                    channels.add(context.channel_id)
        
        return {
            'bot_name': bot_name,
            'total_messages': total_messages,
            'active_conversations': active_conversations,
            'unique_channels': len(channels),
            'since': since.isoformat()
        }
    
    async def cleanup_old_conversations(self, older_than: timedelta = timedelta(days=30)):
        """Clean up old conversations."""
        cutoff_time = datetime.now() - older_than
        cleaned_count = 0
        
        # Clean up cache
        with self._cache_lock:
            keys_to_remove = []
            for key, context in self._conversations.items():
                if context.last_updated < cutoff_time:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._conversations[key]
                cleaned_count += 1
        
        # Clean up storage files
        for storage_file in self.storage_path.glob("*.json"):
            try:
                # Check file modification time
                if storage_file.stat().st_mtime < cutoff_time.timestamp():
                    storage_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                self.logger.error(f"Failed to clean up {storage_file}: {e}")
        
        self.logger.info(f"Cleaned up {cleaned_count} old conversations")
        return cleaned_count
    
    async def get_conversation_summary(self, channel_id: int, user_id: int) -> Dict[str, Any]:
        """Get summary of a conversation."""
        context = await self.get_context(channel_id, user_id)
        
        # Count messages by type
        user_messages = len([msg for msg in context.messages if msg.role == 'user'])
        bot_messages = len([msg for msg in context.messages if msg.role == 'assistant'])
        
        # Get bot participation
        bot_participation = {}
        for bot_name in context.participants:
            bot_participation[bot_name] = len([msg for msg in context.messages if msg.bot_name == bot_name])
        
        # Get recent activity
        recent_activity = len(context.get_messages_since(datetime.now() - timedelta(hours=1)))
        
        return {
            'channel_id': channel_id,
            'user_id': user_id,
            'total_messages': len(context.messages),
            'user_messages': user_messages,
            'bot_messages': bot_messages,
            'participants': context.participants,
            'bot_participation': bot_participation,
            'recent_activity': recent_activity,
            'last_updated': context.last_updated.isoformat(),
            'topic': context.topic
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation state statistics."""
        with self._cache_lock:
            self._stats['conversations_active'] = len(self._conversations)
            return self._stats.copy()
    
    async def reset_conversation(self, channel_id: int, user_id: int):
        """Reset a specific conversation."""
        conversation_key = self._get_conversation_key(channel_id, user_id)
        
        with self._cache_lock:
            if conversation_key in self._conversations:
                del self._conversations[conversation_key]
        
        # Remove storage file
        storage_file = self._get_storage_file(conversation_key)
        if storage_file.exists():
            storage_file.unlink()
        
        self.logger.info(f"Reset conversation {conversation_key}")
    
    async def export_conversation(self, channel_id: int, user_id: int, format: str = 'json') -> str:
        """Export a conversation in specified format."""
        context = await self.get_context(channel_id, user_id)
        
        if format == 'json':
            return json.dumps(context.to_dict(), indent=2, ensure_ascii=False)
        elif format == 'txt':
            lines = []
            for message in context.messages:
                timestamp = message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                if message.role == 'user':
                    lines.append(f"[{timestamp}] User: {message.content}")
                elif message.role == 'assistant' and message.bot_name:
                    lines.append(f"[{timestamp}] {message.bot_name}: {message.content}")
                else:
                    lines.append(f"[{timestamp}] {message.role}: {message.content}")
            return '\n'.join(lines)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    async def shutdown(self):
        """Shutdown the conversation state manager."""
        self.logger.info("Shutting down conversation state manager")
        
        # Save all cached conversations
        save_tasks = []
        with self._cache_lock:
            for key, context in self._conversations.items():
                save_tasks.append(self._save_conversation(key, context))
        
        # Wait for all saves to complete
        if save_tasks:
            await asyncio.gather(*save_tasks, return_exceptions=True)
        
        # Clear cache
        with self._cache_lock:
            self._conversations.clear()
        
        self.logger.info("Conversation state manager shutdown complete")