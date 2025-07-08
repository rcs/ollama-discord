"""Debug utilities for investigating bot behavior."""

import logging
import time
from typing import Dict, Any, Optional, Set
from datetime import datetime
from functools import wraps
import discord


class DebugManager:
    """Manages debug settings and instrumentation."""
    
    def __init__(self):
        self.message_tracking: Dict[str, Dict[str, Any]] = {}
        self.processed_messages: Set[str] = set()
        self.response_count: Dict[str, int] = {}
        self.start_time = time.time()
        self.debug_mode = True
        self.trace_mode = False
        
    def track_message_received(self, bot_name: str, message: discord.Message):
        """Track when a message is received by a bot."""
        msg_id = str(message.id)
        
        if msg_id not in self.message_tracking:
            self.message_tracking[msg_id] = {
                'received_by': [],
                'processed_by': [],
                'responded_by': [],
                'first_seen': datetime.now(),
                'author': str(message.author),
                'channel': str(message.channel),
                'content_preview': message.content[:50] if message.content else 'No content'
            }
        
        self.message_tracking[msg_id]['received_by'].append({
            'bot': bot_name,
            'time': datetime.now()
        })
        
        if self.debug_mode:
            logger = logging.getLogger(f"ollama-discord.{bot_name}")
            logger.debug(f"[MESSAGE_RECEIVED] ID: {msg_id}, Bot: {bot_name}, "
                        f"Author: {message.author}, Channel: {message.channel}")
    
    def track_message_processing(self, bot_name: str, message_id: str, will_process: bool, reason: str = ""):
        """Track message processing decision."""
        if message_id in self.message_tracking:
            self.message_tracking[message_id]['processed_by'].append({
                'bot': bot_name,
                'will_process': will_process,
                'reason': reason,
                'time': datetime.now()
            })
        
        if self.debug_mode:
            logger = logging.getLogger(f"ollama-discord.{bot_name}")
            logger.debug(f"[PROCESSING_DECISION] ID: {message_id}, Bot: {bot_name}, "
                        f"Will Process: {will_process}, Reason: {reason}")
    
    def track_response_sent(self, bot_name: str, message_id: str, response_length: int):
        """Track when a response is sent."""
        if message_id in self.message_tracking:
            self.message_tracking[message_id]['responded_by'].append({
                'bot': bot_name,
                'response_length': response_length,
                'time': datetime.now()
            })
        
        # Track response count per bot
        if bot_name not in self.response_count:
            self.response_count[bot_name] = 0
        self.response_count[bot_name] += 1
        
        if self.debug_mode:
            logger = logging.getLogger(f"ollama-discord.{bot_name}")
            logger.debug(f"[RESPONSE_SENT] ID: {message_id}, Bot: {bot_name}, "
                        f"Length: {response_length}")
    
    def get_message_stats(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific message."""
        return self.message_tracking.get(message_id)
    
    def get_duplicate_responses(self) -> Dict[str, Dict[str, Any]]:
        """Find messages that received multiple responses."""
        duplicates = {}
        for msg_id, data in self.message_tracking.items():
            if len(data['responded_by']) > 1:
                duplicates[msg_id] = data
        return duplicates
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        total_messages = len(self.message_tracking)
        messages_with_responses = sum(1 for data in self.message_tracking.values() 
                                    if data['responded_by'])
        duplicate_responses = len(self.get_duplicate_responses())
        
        return {
            'uptime_seconds': int(time.time() - self.start_time),
            'total_messages_seen': total_messages,
            'messages_with_responses': messages_with_responses,
            'duplicate_responses': duplicate_responses,
            'response_count_by_bot': self.response_count,
            'debug_mode': self.debug_mode,
            'trace_mode': self.trace_mode
        }
    
    def set_debug_mode(self, enabled: bool):
        """Enable or disable debug mode."""
        self.debug_mode = enabled
        
    def set_trace_mode(self, enabled: bool):
        """Enable or disable trace mode."""
        self.trace_mode = enabled


# Global debug manager instance
debug_manager = DebugManager()


def track_message_flow(func):
    """Decorator to track message flow through functions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if debug_manager.trace_mode:
            logger = logging.getLogger("ollama-discord.trace")
            logger.debug(f"[TRACE] Entering {func.__name__} with args: {args[:2]}")  # Limit args to avoid spam
        
        result = await func(*args, **kwargs)
        
        if debug_manager.trace_mode:
            logger.debug(f"[TRACE] Exiting {func.__name__}")
        
        return result
    return wrapper


def set_logger_level(logger_name: str, level: str):
    """Set logger level dynamically."""
    logger = logging.getLogger(logger_name)
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    if level.upper() in level_map:
        logger.setLevel(level_map[level.upper()])
        return True
    return False


def get_all_loggers() -> Dict[str, str]:
    """Get all logger names and their current levels."""
    loggers = {}
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and name.startswith('ollama-discord'):
            level_name = logging.getLevelName(logger.level) if hasattr(logger, 'level') else 'NOTSET'
            loggers[name] = level_name
    return loggers