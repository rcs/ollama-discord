"""Debug commands for runtime bot control."""

import discord
from typing import Optional
from .debug_utils import debug_manager, set_logger_level, get_all_loggers


class DebugCommandHandler:
    """Handles debug commands for the bot system."""
    
    def __init__(self, authorized_users: Optional[list] = None):
        self.authorized_users = authorized_users or []
    
    async def handle_debug_command(self, message: discord.Message, bot_name: str) -> Optional[str]:
        """Handle debug commands if authorized."""
        # Check if message is a debug command
        if not message.content.startswith('!debug'):
            return None
        
        # Check authorization (you can customize this)
        # For now, allow anyone to use debug commands in development
        # In production, check self.authorized_users
        
        parts = message.content.split()
        if len(parts) < 2:
            return self._get_help_text()
        
        command = parts[1].lower()
        
        if command == 'help':
            return self._get_help_text()
        
        elif command == 'stats':
            return self._get_stats()
        
        elif command == 'duplicates':
            return self._get_duplicates()
        
        elif command == 'level' and len(parts) >= 3:
            level = parts[2].upper()
            logger_name = parts[3] if len(parts) > 3 else f"ollama-discord.{bot_name}"
            return self._set_log_level(logger_name, level)
        
        elif command == 'loggers':
            return self._get_loggers()
        
        elif command == 'trace' and len(parts) >= 3:
            enabled = parts[2].lower() == 'on'
            debug_manager.set_trace_mode(enabled)
            return f"Trace mode: {'enabled' if enabled else 'disabled'}"
        
        elif command == 'debug' and len(parts) >= 3:
            enabled = parts[2].lower() == 'on'
            debug_manager.set_debug_mode(enabled)
            return f"Debug mode: {'enabled' if enabled else 'disabled'}"
        
        elif command == 'message' and len(parts) >= 3:
            msg_id = parts[2]
            return self._get_message_info(msg_id)
        
        else:
            return "Unknown command. Use `!debug help` for available commands."
    
    def _get_help_text(self) -> str:
        """Get help text for debug commands."""
        return """**Debug Commands:**
• `!debug help` - Show this help
• `!debug stats` - Show message processing statistics
• `!debug duplicates` - Show duplicate responses
• `!debug level <LEVEL> [logger]` - Set log level (DEBUG/INFO/WARNING/ERROR)
• `!debug loggers` - Show all loggers and their levels
• `!debug trace on/off` - Enable/disable trace logging
• `!debug debug on/off` - Enable/disable debug logging
• `!debug message <id>` - Show info for specific message"""
    
    def _get_stats(self) -> str:
        """Get current statistics."""
        stats = debug_manager.get_summary_stats()
        return f"""**Debug Statistics:**
• Uptime: {stats['uptime_seconds']}s
• Total messages seen: {stats['total_messages_seen']}
• Messages with responses: {stats['messages_with_responses']}
• Duplicate responses: {stats['duplicate_responses']}
• Response count by bot: {stats['response_count_by_bot']}
• Debug mode: {stats['debug_mode']}
• Trace mode: {stats['trace_mode']}"""
    
    def _get_duplicates(self) -> str:
        """Get information about duplicate responses."""
        duplicates = debug_manager.get_duplicate_responses()
        if not duplicates:
            return "No duplicate responses detected."
        
        lines = ["**Duplicate Responses Detected:**"]
        for msg_id, data in list(duplicates.items())[:5]:  # Limit to 5
            lines.append(f"\nMessage ID: {msg_id}")
            lines.append(f"• Content: {data['content_preview']}")
            lines.append(f"• Received by: {[r['bot'] for r in data['received_by']]}")
            lines.append(f"• Responded by: {[r['bot'] for r in data['responded_by']]}")
        
        if len(duplicates) > 5:
            lines.append(f"\n... and {len(duplicates) - 5} more")
        
        return '\n'.join(lines)
    
    def _set_log_level(self, logger_name: str, level: str) -> str:
        """Set logger level."""
        if set_logger_level(logger_name, level):
            return f"Set {logger_name} to {level}"
        else:
            return f"Invalid level: {level}. Use DEBUG/INFO/WARNING/ERROR"
    
    def _get_loggers(self) -> str:
        """Get all loggers and their levels."""
        loggers = get_all_loggers()
        if not loggers:
            return "No ollama-discord loggers found."
        
        lines = ["**Active Loggers:**"]
        for name, level in loggers.items():
            lines.append(f"• {name}: {level}")
        
        return '\n'.join(lines)
    
    def _get_message_info(self, msg_id: str) -> str:
        """Get information about a specific message."""
        info = debug_manager.get_message_stats(msg_id)
        if not info:
            return f"No information found for message {msg_id}"
        
        lines = [f"**Message {msg_id}:**"]
        lines.append(f"• Author: {info['author']}")
        lines.append(f"• Channel: {info['channel']}")
        lines.append(f"• Content: {info['content_preview']}")
        lines.append(f"• Received by: {[r['bot'] for r in info['received_by']]}")
        lines.append(f"• Processed by: {[(r['bot'], r['will_process']) for r in info['processed_by']]}")
        lines.append(f"• Responded by: {[r['bot'] for r in info['responded_by']]}")
        
        return '\n'.join(lines)


# Global debug command handler
debug_handler = DebugCommandHandler()