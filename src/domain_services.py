"""Pure domain logic for the ollama-discord bot system."""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

import discord

from .ports import MessageStorage, AIModel, RateLimiter, NotificationSender
from .conversation_state import ConversationContext
from .debug_utils import debug_manager
from .debug_commands import debug_handler


@dataclass
class MessageContext:
    """Context information for a message."""
    channel_name: str
    channel_id: int
    user_id: int
    user_name: str
    content: str
    timestamp: datetime
    is_bot_message: bool
    mentioned_bots: List[str]
    thread_id: Optional[int] = None


@dataclass
class ResponseDecision:
    """Decision about whether and how a bot should respond."""
    should_respond: bool
    confidence: float
    reasoning: str
    delay_seconds: float = 0.0
    priority: int = 0


class MessageCoordinator:
    """Coordinates message handling across multiple bots."""
    
    def __init__(self, storage: MessageStorage, rate_limiter: RateLimiter, global_settings: Dict[str, Any]):
        self.storage = storage
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(__name__)
        
        # Response coordination
        self.recent_responses: Dict[int, List[Tuple[str, datetime]]] = {}
        self.active_responses: Dict[int, Set[str]] = {}
        
        # Configuration with safe defaults
        self.max_concurrent_responses = global_settings.get('max_concurrent_responses', 2)
        self.response_delay_range = self._parse_delay_range(global_settings.get('response_delay', '1-3'))
        self.cooldown_period = global_settings.get('cooldown_period', 30)
        
    def _parse_delay_range(self, delay_str: str) -> Tuple[float, float]:
        """Parse delay range string like '1-3' or '2.5'."""
        if '-' in delay_str:
            min_delay, max_delay = map(float, delay_str.split('-'))
            return min_delay, max_delay
        else:
            delay = float(delay_str)
            return delay, delay
    
    async def should_handle_message(self, bot_name: str, message: discord.Message, 
                                   channel_patterns: List[str]) -> bool:
        """Determine if a bot should handle a specific message."""
        bot_logger = logging.getLogger(f"bot.{bot_name}")
        bot_logger.info(f"🔍 [{bot_name}] ANALYZING MESSAGE: '{message.content[:100]}...' in #{message.channel.name}")
        
        # Skip bot messages
        if message.author.bot:
            bot_logger.info(f"❌ [{bot_name}] SKIPPED: Bot message from {message.author.display_name}")
            return False
        
        # Check channel filtering
        channel_match = self._matches_channel_patterns(message.channel, channel_patterns)
        if not channel_match:
            bot_logger.info(f"❌ [{bot_name}] SKIPPED: Channel #{message.channel.name} not in patterns {channel_patterns}")
            return False
        else:
            bot_logger.info(f"✅ [{bot_name}] CHANNEL MATCH: #{message.channel.name} matches patterns {channel_patterns}")
        
        # Check if message is a command (starts with prefix)
        if message.content.startswith('!'):
            bot_logger.info(f"❌ [{bot_name}] SKIPPED: Command message (starts with !)")
            return False
        
        # Check rate limiting
        if not self.rate_limiter.can_request(str(message.author.id)):
            bot_logger.info(f"❌ [{bot_name}] SKIPPED: Rate limited")
            return False
        
        # Check for bot coordination (avoid multiple bots responding simultaneously)
        should_coordinate = await self._should_coordinate_response(bot_name, message)
        if should_coordinate:
            bot_logger.info(f"❌ [{bot_name}] SKIPPED: Coordination - too many active responses")
            return False
        
        bot_logger.info(f"🎯 [{bot_name}] WILL HANDLE: All checks passed!")
        return True
    
    def _matches_channel_patterns(self, channel: discord.TextChannel, patterns: List[str]) -> bool:
        """Check if channel matches any of the patterns."""
        if not patterns:
            return True
        
        channel_name = channel.name.lower()
        
        for pattern in patterns:
            pattern = pattern.lower()
            
            # Exact match
            if pattern == channel_name:
                return True
            
            # Wildcard pattern
            if '*' in pattern:
                regex_pattern = pattern.replace('*', '.*')
                if re.match(f'^{regex_pattern}$', channel_name):
                    return True
            
            # Prefix match (pattern ending with -)
            if pattern.endswith('-') and channel_name.startswith(pattern[:-1]):
                return True
        
        return False
    
    async def _should_coordinate_response(self, bot_name: str, message: discord.Message) -> bool:
        """Check if bot should coordinate response to avoid conflicts."""
        channel_id = message.channel.id
        now = datetime.now()
        
        # Clean up old responses
        if channel_id in self.recent_responses:
            self.recent_responses[channel_id] = [
                (bot, timestamp) for bot, timestamp in self.recent_responses[channel_id]
                if now - timestamp < timedelta(seconds=self.cooldown_period)
            ]
        
        # Check if too many bots are currently responding
        active_count = len(self.active_responses.get(channel_id, set()))
        if active_count >= self.max_concurrent_responses:
            return True
        
        # Check recent responses in the same channel
        recent_count = len(self.recent_responses.get(channel_id, []))
        if recent_count >= self.max_concurrent_responses:
            return True
        
        return False
    
    async def mark_bot_responding(self, bot_name: str, channel_id: int):
        """Mark bot as actively responding."""
        if channel_id not in self.active_responses:
            self.active_responses[channel_id] = set()
        self.active_responses[channel_id].add(bot_name)
    
    async def mark_response_complete(self, bot_name: str, channel_id: int):
        """Mark response as complete."""
        if channel_id in self.active_responses:
            self.active_responses[channel_id].discard(bot_name)
            if not self.active_responses[channel_id]:
                del self.active_responses[channel_id]
        
        # Record response timing
        now = datetime.now()
        if channel_id not in self.recent_responses:
            self.recent_responses[channel_id] = []
        self.recent_responses[channel_id].append((bot_name, now))


class ResponseGenerator:
    """Generates responses using AI models."""
    
    def __init__(self, ai_model: AIModel, storage: MessageStorage):
        self.ai_model = ai_model
        self.storage = storage
        self.logger = logging.getLogger(__name__)
        
        # Bot-specific system prompts
        self.system_prompts = {
            'sage': "You are Sage, a wise and thoughtful mentor who helps others think deeply about life's questions. Respond with wisdom, patience, and gentle guidance.",
            'spark': "You are Spark, a creative and innovative companion who loves brainstorming, creative projects, and inspiring new ideas. Respond with enthusiasm and creativity.",
            'logic': "You are Logic, an analytical and systematic thinker who excels at research, problem-solving, and data analysis. Respond with clarity and logical reasoning."
        }
    
    async def generate_response(self, bot_name: str, message_content: str, 
                               channel_id: int, user_id: int) -> str:
        """Generate a response for the given message."""
        self.logger.info(f"🤖 [{bot_name}] Generating response for: '{message_content[:50]}...'")
        
        try:
            # Get conversation context
            context = await self.storage.get_context(channel_id, user_id)
            
            # Build message history
            messages = self._build_message_history(bot_name, context, message_content)
            
            # Generate response
            response = await self.ai_model.generate_response(messages)
            
            self.logger.info(f"✅ [{bot_name}] Response generated successfully")
            return response
            
        except Exception as e:
            self.logger.error(f"❌ [{bot_name}] Failed to generate response: {e}")
            raise  # Re-raise the exception so orchestrator can handle it
    
    def _build_message_history(self, bot_name: str, context: ConversationContext, 
                              current_message: str) -> List[Dict[str, str]]:
        """Build message history for AI model."""
        messages = []
        
        # Add system prompt
        if bot_name in self.system_prompts:
            messages.append({"role": "system", "content": self.system_prompts[bot_name]})
        
        # Add recent conversation context
        if context.messages:
            for msg in context.messages[-5:]:  # Last 5 messages for context
                if msg.bot_name:
                    messages.append({"role": "assistant", "content": msg.content})
                else:
                    messages.append({"role": "user", "content": msg.content})
        
        # Add current message
        messages.append({"role": "user", "content": current_message})
        
        return messages


class BotOrchestrator:
    """Orchestrates the complete bot message processing flow."""
    
    def __init__(self, coordinator: MessageCoordinator, response_generator: ResponseGenerator, 
                 storage: MessageStorage, rate_limiter: RateLimiter, notification_sender: NotificationSender):
        self.coordinator = coordinator
        self.response_generator = response_generator
        self.storage = storage
        self.rate_limiter = rate_limiter
        self.notification_sender = notification_sender
        self.logger = logging.getLogger(__name__)
    
    async def process_message(self, bot_name: str, message: discord.Message, 
                            channel_patterns: List[str]) -> bool:
        """Process a message and determine if bot should respond."""
        channel_id = message.channel.id
        message_id = str(message.id)
        
        try:
            # Check for debug commands first
            debug_response = await debug_handler.handle_debug_command(message, bot_name)
            if debug_response:
                await self.notification_sender.send_message(message.channel, debug_response)
                return True
            
            # Check if bot should handle this message
            should_handle = await self.coordinator.should_handle_message(bot_name, message, channel_patterns)
            
            # Track processing decision
            debug_manager.track_message_processing(
                bot_name, message_id, should_handle, 
                f"Channel patterns: {channel_patterns}"
            )
            
            if not should_handle:
                return False
            
            # Mark bot as responding
            await self.coordinator.mark_bot_responding(bot_name, channel_id)
            
            # Record the request for rate limiting
            self.rate_limiter.record_request(str(message.author.id))
            
            # Store user message
            await self.storage.add_message(
                channel_id=channel_id,
                user_id=message.author.id,
                role='user',
                content=message.content,
                metadata={
                    'username': message.author.display_name,
                    'channel_name': message.channel.name,
                    'message_id': message.id
                }
            )
            
            # Generate response
            response_text = await self.response_generator.generate_response(
                bot_name, message.content, channel_id, message.author.id
            )
            
            # Send response
            await self.notification_sender.send_chunked_message(message.channel, response_text)
            
            # Track response sent
            debug_manager.track_response_sent(bot_name, message_id, len(response_text))
            
            # Store bot response
            await self.storage.add_message(
                channel_id=channel_id,
                user_id=message.author.id,
                role='assistant',
                content=response_text,
                bot_name=bot_name,
                metadata={
                    'response_to_message_id': message.id
                }
            )
            
            self.logger.info(f"✅ [{bot_name}] Message processed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [{bot_name}] Error processing message: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Send error message to user
            try:
                await self.notification_sender.send_message(
                    message.channel, 
                    "❌ Sorry, I encountered an error while processing your message."
                )
            except Exception as send_error:
                self.logger.error(f"❌ [{bot_name}] Could not even send error message: {send_error}")
            
            return False
        finally:
            # Always mark response as complete
            await self.coordinator.mark_response_complete(bot_name, channel_id)