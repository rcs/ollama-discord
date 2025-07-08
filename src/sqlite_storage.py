"""SQLite-based storage adapter for conversation messages."""

import aiosqlite
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from .ports import MessageStorage
from .conversation_state import ConversationMessage, ConversationContext


class SQLiteMessageStorage(MessageStorage):
    """SQLite-based message storage adapter."""
    
    def __init__(self, bot_name: str, db_path: str = "data/conversations.db", 
                 session_timeout: int = 3600):
        self.bot_name = bot_name
        self.db_path = Path(db_path)
        self.session_timeout = session_timeout
        self._initialized = False
        
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def _initialize_db(self) -> None:
        """Initialize the database schema."""
        if self._initialized:
            return
            
        async with aiosqlite.connect(self.db_path) as db:
            # Create conversations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    channel_name TEXT NOT NULL,
                    channel_type TEXT NOT NULL CHECK (channel_type IN ('channel', 'dm')),
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Create sessions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_bot_channel 
                ON conversations(bot_name, channel_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_session 
                ON conversations(session_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_bot_channel 
                ON sessions(bot_name, channel_id)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_active 
                ON sessions(is_active)
            """)
            
            await db.commit()
        
        self._initialized = True
    
    async def _get_or_create_session(self, channel_id: int, user_id: int) -> str:
        """Get active session or create new one."""
        await self._initialize_db()
        
        channel_str = str(channel_id)
        cutoff_time = datetime.now() - timedelta(seconds=self.session_timeout)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Look for active session
            async with db.execute("""
                SELECT session_id FROM sessions 
                WHERE bot_name = ? AND channel_id = ? AND is_active = 1 
                AND last_activity > ?
            """, (self.bot_name, channel_str, cutoff_time)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    session_id = row[0]
                    # Update last activity
                    await db.execute("""
                        UPDATE sessions 
                        SET last_activity = CURRENT_TIMESTAMP 
                        WHERE session_id = ?
                    """, (session_id,))
                    await db.commit()
                    return session_id
            
            # Create new session
            session_id = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO sessions (bot_name, channel_id, session_id, started_at, last_activity)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (self.bot_name, channel_str, session_id))
            
            # Close old sessions
            await db.execute("""
                UPDATE sessions 
                SET is_active = 0 
                WHERE bot_name = ? AND channel_id = ? AND session_id != ?
            """, (self.bot_name, channel_str, session_id))
            
            await db.commit()
            return session_id
    
    async def add_message(self, channel_id: int, user_id: int, role: str, content: str, 
                         bot_name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """Add a message to storage."""
        await self._initialize_db()
        
        session_id = await self._get_or_create_session(channel_id, user_id)
        message_id = str(uuid.uuid4())
        
        # Use bot_name parameter or default to instance bot_name
        effective_bot_name = bot_name or self.bot_name
        
        async with aiosqlite.connect(self.db_path) as db:
            # Insert message
            await db.execute("""
                INSERT INTO conversations 
                (bot_name, channel_id, channel_name, channel_type, user_id, username, 
                 session_id, message_id, role, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                effective_bot_name,
                str(channel_id),
                f"channel_{channel_id}",  # TODO: Get actual channel name
                "channel",  # TODO: Detect DM vs channel
                str(user_id),
                f"user_{user_id}",  # TODO: Get actual username
                session_id,
                message_id,
                role,
                content,
                json.dumps(metadata) if metadata else None
            ))
            
            # Update session message count
            await db.execute("""
                UPDATE sessions 
                SET message_count = message_count + 1, last_activity = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))
            
            await db.commit()
        
        return ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            bot_name=effective_bot_name,
            metadata=metadata or {}
        )
    
    async def get_context(self, channel_id: int, user_id: int) -> ConversationContext:
        """Get conversation context for a channel/user combination."""
        await self._initialize_db()
        
        channel_str = str(channel_id)
        user_str = str(user_id)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Get recent messages for this bot/channel/user
            async with db.execute("""
                SELECT role, content, timestamp, metadata
                FROM conversations 
                WHERE bot_name = ? AND channel_id = ? AND user_id = ?
                ORDER BY timestamp ASC 
                LIMIT 50
            """, (self.bot_name, channel_str, user_str)) as cursor:
                
                rows = await cursor.fetchall()
                
                messages = []
                for row in rows:
                    role, content, timestamp_str, metadata_str = row
                    
                    # Parse timestamp
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        timestamp = datetime.now()
                    
                    # Parse metadata
                    metadata = {}
                    if metadata_str:
                        try:
                            metadata = json.loads(metadata_str)
                        except:
                            pass
                    
                    messages.append(ConversationMessage(
                        role=role,
                        content=content,
                        timestamp=timestamp,
                        bot_name=self.bot_name,
                        metadata=metadata
                    ))
                
                # Messages are already in chronological order
                
                return ConversationContext(
                    channel_id=channel_id,
                    user_id=user_id,
                    messages=messages,
                    last_updated=datetime.now()
                )
    
    async def cleanup_old_sessions(self, days_old: int = 7) -> None:
        """Clean up old inactive sessions."""
        await self._initialize_db()
        
        if days_old == 0:
            # Special case: clean everything
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM conversations WHERE bot_name = ?", (self.bot_name,))
                await db.execute("DELETE FROM sessions WHERE bot_name = ?", (self.bot_name,))
                await db.commit()
        else:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Delete old conversations
                await db.execute("""
                    DELETE FROM conversations 
                    WHERE timestamp < ? AND bot_name = ?
                """, (cutoff_date, self.bot_name))
                
                # Delete old sessions
                await db.execute("""
                    DELETE FROM sessions 
                    WHERE last_activity < ? AND bot_name = ?
                """, (cutoff_date, self.bot_name))
                
                await db.commit()