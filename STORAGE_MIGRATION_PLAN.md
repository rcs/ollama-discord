# Storage Migration Plan: SQLite Database

## Overview
Migrate from file-based storage to SQLite database with bot-specific isolation, improved performance, and proper session management.

## Current Structure
```
data/
├── multi_bot_conversations/
│   ├── sage/
│   │   └── channelId_userId.json
│   ├── spark/
│   │   └── channelId_userId.json
│   └── shared_conversations.json
```

## Target Structure (SQLite)
```
data/
├── conversations.db (SQLite database)
└── backups/
    ├── conversations_2024-01-08.db
    └── conversations_2024-01-09.db
```

### Database Schema
```sql
-- Bot-specific conversation storage
CREATE TABLE conversations (
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
    metadata TEXT -- JSON for additional data
);

-- Sessions for conversation boundaries
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_name TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);

-- Indexes for performance
CREATE INDEX idx_conversations_bot_channel ON conversations(bot_name, channel_id);
CREATE INDEX idx_conversations_session ON conversations(session_id);
CREATE INDEX idx_sessions_bot_channel ON sessions(bot_name, channel_id);
CREATE INDEX idx_sessions_active ON sessions(is_active);
```

## Implementation Plan

### Phase 1: Core Changes to ConversationState

1. **Update storage path structure**
   - Remove bot_name subdirectory under shared path
   - Use `data/{bot_name}` as root for each bot
   - Add channel type separation (channels vs dms)

2. **Add channel name resolution**
   - Extract channel name from Discord message object
   - Sanitize channel names for filesystem safety
   - Handle DMs with username_userid format

3. **Implement session management**
   - Create new session files based on time gaps
   - Include session start time and duration in filename
   - Auto-close sessions after configurable timeout

### Phase 2: Update Storage Methods

1. **Modify `_get_storage_file()` method**
   ```python
   def _get_storage_file(self, channel_info: ChannelInfo, session_id: str) -> Path:
       if channel_info.is_dm:
           return self.storage_path / "dms" / channel_info.safe_name / f"{session_id}.json"
       else:
           return self.storage_path / "channels" / channel_info.safe_name / f"{session_id}.json"
   ```

2. **Add session tracking**
   ```python
   def _get_or_create_session(self, channel_info: ChannelInfo) -> Session:
       # Check for active session or create new one
       # Return session with ID like "2024-01-08_14-30-00_3600s"
   ```

3. **Update message storage to include channel info**
   ```python
   async def add_message(self, channel_info: ChannelInfo, user_id: int, 
                        role: str, content: str, **kwargs):
       session = self._get_or_create_session(channel_info)
       # Store message in session file
   ```

### Phase 3: Configuration Updates

1. **Remove shared storage paths**
   - Update `multi_bot_config.py` to remove global storage_path
   - Each bot gets its own root directory under `data/`

2. **Add session configuration**
   ```yaml
   storage:
     enabled: true
     type: "file"
     path: "./data/{bot_name}"  # Bot-specific root
     max_history: 100
     session_timeout: 3600  # 1 hour default
     session_gap: 300       # 5 minute gap starts new session
   ```

### Phase 4: Migration Process

1. **Create migration script**
   - Read existing conversation files
   - Extract channel information from Discord API if needed
   - Reorganize into new structure
   - Preserve conversation history

2. **Backward compatibility**
   - Keep old file reading capability during transition
   - Log warnings when old format detected
   - Provide migration command

### Phase 5: Testing

1. **Unit tests for new storage structure**
   - Test channel name sanitization
   - Test session creation and timeout
   - Test DM vs channel separation

2. **Integration tests**
   - Test multi-bot isolation
   - Test session continuity
   - Test storage cleanup

## Benefits

1. **Complete Bot Isolation**
   - Each bot has its own storage tree
   - No shared state between bots
   - Easy to split into separate processes

2. **Better Organization**
   - Human-readable directory structure
   - Easy to browse conversation history
   - Clear separation of channels and DMs

3. **Session Management**
   - Natural conversation boundaries
   - Efficient file sizes
   - Easy cleanup of old sessions

4. **Future Scalability**
   - Ready for process-per-bot architecture
   - Can easily move bot storage to different servers
   - Supports different storage backends per bot

## Timeline

- Week 1: Implement core ConversationState changes
- Week 2: Update all storage methods and add session management
- Week 3: Create migration script and test
- Week 4: Deploy and monitor

## Risks and Mitigations

1. **Risk**: Channel name changes
   - **Mitigation**: Store channel ID mapping in metadata

2. **Risk**: Large migration for existing data
   - **Mitigation**: Incremental migration, keep backward compatibility

3. **Risk**: Session file proliferation
   - **Mitigation**: Implement cleanup for old sessions

## Success Criteria

1. Each bot stores conversations in isolated directory structure
2. Channel names are human-readable in filesystem
3. Sessions are properly bounded by time gaps
4. No shared storage between bots
5. Easy to browse and understand conversation history