# Debug Commands Documentation

## Overview
The ollama-discord bot system includes built-in debug commands for runtime monitoring and troubleshooting. These commands allow you to inspect bot behavior, change logging levels, and diagnose issues without restarting the service.

## Available Commands

### Basic Commands

#### `!debug help`
Shows all available debug commands and their usage.

**Example:**
```
User: !debug help
Bot: **Debug Commands:**
• !debug help - Show this help
• !debug stats - Show message processing statistics
• !debug duplicates - Show duplicate responses
• !debug level <LEVEL> [logger] - Set log level (DEBUG/INFO/WARNING/ERROR)
• !debug loggers - Show all loggers and their levels
• !debug trace on/off - Enable/disable trace logging
• !debug debug on/off - Enable/disable debug logging
• !debug message <id> - Show info for specific message
```

#### `!debug stats`
Displays current message processing statistics including uptime, message counts, and response metrics.

**Example:**
```
User: !debug stats
Bot: **Debug Statistics:**
• Uptime: 3600s
• Total messages seen: 150
• Messages with responses: 45
• Duplicate responses: 12
• Response count by bot: {'sage': 20, 'spark': 15, 'logic': 10}
• Debug mode: True
• Trace mode: False
```

### Duplicate Response Detection

#### `!debug duplicates`
Shows messages that received responses from multiple bots, helping identify duplicate response issues.

**Example:**
```
User: !debug duplicates
Bot: **Duplicate Responses Detected:**

Message ID: 123456789
• Content: What is the meaning of life?
• Received by: ['sage', 'spark', 'logic']
• Responded by: ['sage', 'spark']

Message ID: 123456790
• Content: Tell me a joke
• Received by: ['sage', 'spark', 'logic']
• Responded by: ['spark', 'logic']
```

### Logging Control

#### `!debug level <LEVEL> [logger]`
Changes the logging level for a specific logger or the current bot's logger.

**Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL

**Examples:**
```
# Set current bot's logger to DEBUG
User: !debug level DEBUG
Bot: Set ollama-discord.sage to DEBUG

# Set specific logger to INFO
User: !debug level INFO ollama-discord.spark
Bot: Set ollama-discord.spark to INFO
```

#### `!debug loggers`
Shows all active loggers and their current levels.

**Example:**
```
User: !debug loggers
Bot: **Active Loggers:**
• ollama-discord.sage: DEBUG
• ollama-discord.spark: INFO
• ollama-discord.logic: INFO
• ollama-discord.trace: WARNING
```

### Advanced Debugging

#### `!debug trace on/off`
Enables or disables trace-level logging for detailed function call tracking.

**Example:**
```
User: !debug trace on
Bot: Trace mode: enabled
```

**Note:** Trace mode generates very verbose logs and should only be used for detailed debugging.

#### `!debug debug on/off`
Enables or disables debug mode for message tracking and statistics collection.

**Example:**
```
User: !debug debug off
Bot: Debug mode: disabled
```

#### `!debug message <id>`
Shows detailed information about a specific message ID, including which bots received and processed it.

**Example:**
```
User: !debug message 123456789
Bot: **Message 123456789:**
• Author: JohnDoe#1234
• Channel: general
• Content: What is the meaning of life?
• Received by: ['sage', 'spark', 'logic']
• Processed by: [('sage', True), ('spark', True), ('logic', False)]
• Responded by: ['sage', 'spark']
```

## Security Considerations

### Authorization
Currently, debug commands are available to all users in development mode. For production deployment:

1. **Restrict to specific users**: Configure authorized user IDs in the bot configuration
2. **Restrict to specific roles**: Only allow users with admin/moderator roles
3. **Restrict to specific channels**: Only allow debug commands in designated channels

### Recommended Production Setup
```python
# In debug_commands.py
authorized_users = [
    "123456789012345678",  # Admin user ID
    "234567890123456789"   # Developer user ID
]

# Or check roles
if not any(role.name in ['Admin', 'Bot Developer'] for role in message.author.roles):
    return "Unauthorized to use debug commands"
```

## Use Cases

### Diagnosing Duplicate Responses
1. User reports seeing multiple responses
2. Use `!debug duplicates` to see affected messages
3. Use `!debug message <id>` for specific message details
4. Check which bots are responding

### Performance Troubleshooting
1. Use `!debug stats` to see message processing rates
2. Enable trace mode with `!debug trace on` for detailed flow
3. Check specific logger levels with `!debug loggers`
4. Adjust logging levels as needed

### Real-time Debugging
1. Set logger to DEBUG: `!debug level DEBUG`
2. Monitor logs while reproducing issue
3. Use `!debug message <id>` to inspect specific messages
4. Disable debug mode when done: `!debug debug off`

## Implementation Details

### Message Tracking
The debug system tracks:
- When each message is received by each bot
- Processing decisions (will process/won't process)
- Response generation and sending
- Timing information for performance analysis

### Memory Management
- Message tracking is kept in memory
- Old messages are periodically cleaned up
- Statistics are reset on bot restart

### Performance Impact
- Debug mode: Minimal impact, adds tracking metadata
- Trace mode: Significant impact, logs all function calls
- Recommended to disable both in production unless troubleshooting