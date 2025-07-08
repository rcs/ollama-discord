# Logging Configuration Guide

## Overview
The ollama-discord bot system provides comprehensive logging capabilities for monitoring, debugging, and troubleshooting. This guide covers logging configuration, best practices, and runtime management.

## Configuration Structure

### Basic Configuration
Logging is configured in the YAML configuration files at two levels:

1. **Individual Bot Configuration** (`config/sage.yaml`, etc.)
```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

2. **Multi-Bot Configuration** (`config/multi_bot.yaml`)
```yaml
logging:
  level: "DEBUG"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/multi_bot.log"
  max_file_size: "10MB"
  backup_count: 5
```

### Configuration Options

#### `level`
Sets the minimum logging level. Messages below this level are ignored.

**Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Hierarchy:**
- `DEBUG`: Most verbose, shows all messages
- `INFO`: Normal operational messages
- `WARNING`: Warning messages that don't prevent operation
- `ERROR`: Error messages for failures
- `CRITICAL`: Critical failures that may cause shutdown

#### `format`
Python logging format string that controls log message appearance.

**Common format variables:**
- `%(asctime)s`: Timestamp
- `%(name)s`: Logger name (e.g., "ollama-discord.sage")
- `%(levelname)s`: Log level (DEBUG, INFO, etc.)
- `%(message)s`: The actual log message
- `%(filename)s`: Source filename
- `%(lineno)d`: Line number
- `%(funcName)s`: Function name

**Example formats:**
```yaml
# Simple format
format: "%(levelname)s - %(message)s"

# Detailed format
format: "%(asctime)s - [%(name)s] %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

# Production format
format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

#### `file` (Optional)
Path to log file. If not specified, logs only go to console.

```yaml
file: "./logs/multi_bot.log"
```

#### `max_file_size` (Optional)
Maximum size of log file before rotation. Supports units: KB, MB, GB.

```yaml
max_file_size: "10MB"
```

#### `backup_count` (Optional)
Number of rotated log files to keep.

```yaml
backup_count: 5  # Keeps multi_bot.log, multi_bot.log.1, ..., multi_bot.log.5
```

## Logger Hierarchy

The bot system uses a hierarchical logger structure:

```
ollama-discord              # Root logger for the bot system
├── ollama-discord.sage     # Logger for sage bot
├── ollama-discord.spark    # Logger for spark bot
├── ollama-discord.logic    # Logger for logic bot
├── ollama-discord.trace    # Logger for trace-level debugging
└── __main__                # Logger for bot manager
```

Each bot gets its own logger with the bot name, making it easy to filter logs.

## Runtime Log Level Management

### Using Debug Commands
Change log levels without restarting:

```
# Set all bot loggers to DEBUG
!debug level DEBUG

# Set specific bot to INFO
!debug level INFO ollama-discord.spark

# Check current levels
!debug loggers
```

### Programmatic Control
```python
import logging

# Get logger
logger = logging.getLogger("ollama-discord.sage")

# Change level
logger.setLevel(logging.DEBUG)

# Check level
current_level = logger.getEffectiveLevel()
```

## Log Message Examples

### Startup Logs
```
2025-07-08 10:21:04,088 - [SAGE] INFO - Bot 'sage' initialized
2025-07-08 10:21:07,087 - [SAGE] INFO - Bot 'sage' logged in as Play Voices#9273
```

### Message Processing Logs
```
2025-07-08 10:21:15,123 - [SAGE] DEBUG - [MESSAGE_RECEIVED] ID: 123456, Bot: sage, Author: User#1234, Channel: general
2025-07-08 10:21:15,125 - [SAGE] DEBUG - [PROCESSING_DECISION] ID: 123456, Bot: sage, Will Process: True, Reason: Matches channel pattern
2025-07-08 10:21:16,789 - [SAGE] DEBUG - [RESPONSE_SENT] ID: 123456, Bot: sage, Length: 256
2025-07-08 10:21:16,790 - [SAGE] INFO - ✅ [sage] Message processed successfully
```

### Error Logs
```
2025-07-08 10:21:20,456 - [SPARK] ERROR - ❌ [spark] Error processing message: Connection timeout
2025-07-08 10:21:20,457 - [SPARK] ERROR - Full traceback: 
Traceback (most recent call last):
  File "domain_services.py", line 301, in process_message
    ...
```

## Best Practices

### 1. Development vs Production Logging

**Development:**
```yaml
logging:
  level: "DEBUG"
  format: "%(asctime)s - [%(name)s] %(levelname)s - %(message)s"
```

**Production:**
```yaml
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/bot.log"
  max_file_size: "50MB"
  backup_count: 10
```

### 2. Log Levels by Environment

- **Local Development**: DEBUG - See everything
- **Testing/Staging**: INFO - Normal operation plus useful info
- **Production**: WARNING - Only problems and errors
- **Troubleshooting**: Temporarily set to DEBUG

### 3. Structured Logging

Use consistent prefixes for easy filtering:
```python
logger.debug(f"[MESSAGE_RECEIVED] ID: {msg_id}, Channel: {channel}")
logger.debug(f"[PROCESSING_DECISION] Bot: {bot}, Decision: {decision}")
logger.debug(f"[RESPONSE_SENT] ID: {msg_id}, Length: {length}")
```

### 4. Performance Considerations

- DEBUG logging can impact performance
- Trace mode significantly impacts performance
- Use INFO or WARNING in production
- Enable DEBUG only when troubleshooting

### 5. Sensitive Information

Never log:
- Discord tokens
- User personal information
- Full message content (use previews)
- API keys or secrets

Example of safe logging:
```python
# Bad
logger.debug(f"Token: {token}")

# Good
logger.debug(f"Token: {token[:8]}...{token[-4:]}")
```

## Troubleshooting

### Common Issues

#### 1. Logs Not Appearing
- Check log level isn't too high
- Verify logger name is correct
- Ensure file permissions for log directory

#### 2. Log Files Growing Too Large
- Set appropriate `max_file_size`
- Increase `backup_count` if needed
- Consider log aggregation service

#### 3. Performance Impact
- Reduce log level (INFO or WARNING)
- Disable trace mode
- Remove expensive log statements

### Debug Workflow

1. **Enable debug logging**
   ```
   !debug level DEBUG
   ```

2. **Enable trace mode if needed**
   ```
   !debug trace on
   ```

3. **Reproduce the issue**

4. **Check logs**
   ```bash
   tail -f logs/multi_bot.log | grep ERROR
   ```

5. **Analyze with debug commands**
   ```
   !debug stats
   !debug duplicates
   ```

6. **Reset logging when done**
   ```
   !debug level INFO
   !debug trace off
   ```

## Log Analysis Tools

### Viewing Logs
```bash
# Follow logs in real-time
tail -f logs/multi_bot.log

# Search for errors
grep ERROR logs/multi_bot.log

# Filter by bot
grep "\[SAGE\]" logs/multi_bot.log

# Count log levels
grep -c "ERROR" logs/multi_bot.log
```

### Log Rotation
The system automatically rotates logs when they reach `max_file_size`. Rotated files are named:
- `multi_bot.log` (current)
- `multi_bot.log.1` (most recent)
- `multi_bot.log.2`
- ...
- `multi_bot.log.5` (oldest, if backup_count=5)

### External Tools
Consider using:
- **ELK Stack**: Elasticsearch, Logstash, Kibana
- **Grafana Loki**: For log aggregation
- **Datadog/New Relic**: For production monitoring