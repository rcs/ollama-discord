"""Enhanced message processing with channel filtering and context management."""

import asyncio
import logging
import re
import random
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

import discord

from .conversation_state import ConversationState, ConversationContext


@dataclass
class MessageContext:
    """Context information for a message."""
    message: discord.Message
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


class MessageProcessor:
    """Processes messages with multi-bot coordination and context awareness."""
    
    def __init__(self, conversation_state: ConversationState, global_settings: Dict[str, Any]):
        self.conversation_state = conversation_state
        self.logger = logging.getLogger(__name__)
        
        # Validate inputs
        if conversation_state is None:
            raise ValueError("conversation_state cannot be None")
        
        if global_settings is None:
            self.logger.warning("global_settings is None, using defaults")
            global_settings = {}
        
        self.global_settings = global_settings
        self.logger.info(f"Initializing MessageProcessor with settings: {global_settings}")
        
        # Response coordination
        self.recent_responses: Dict[int, List[Tuple[str, datetime]]] = {}  # channel_id -> [(bot_name, timestamp)]
        self.active_responses: Dict[int, Set[str]] = {}  # channel_id -> {bot_names}
        
        # Configuration with safe defaults
        try:
            self.context_depth = global_settings.get('context_depth', 10)
            self.max_concurrent_responses = global_settings.get('max_concurrent_responses', 2)
            self.response_delay_range = self._parse_delay_range(global_settings.get('response_delay', '1-3'))
            self.cooldown_period = global_settings.get('cooldown_period', 30)  # seconds
            
            self.logger.info(f"MessageProcessor configured: context_depth={self.context_depth}, "
                           f"max_concurrent={self.max_concurrent_responses}, "
                           f"delay_range={self.response_delay_range}, "
                           f"cooldown={self.cooldown_period}")
        except Exception as e:
            self.logger.error(f"Error configuring MessageProcessor: {e}")
            # Set safe defaults
            self.context_depth = 10
            self.max_concurrent_responses = 2
            self.response_delay_range = (1.0, 3.0)
            self.cooldown_period = 30
            self.logger.info("Using fallback configuration for MessageProcessor")
        
    def _parse_delay_range(self, delay_str: str) -> Tuple[float, float]:
        """Parse delay range string like '1-3' or '2.5'."""
        if '-' in delay_str:
            min_delay, max_delay = map(float, delay_str.split('-'))
            return min_delay, max_delay
        else:
            delay = float(delay_str)
            return delay, delay
    
    async def should_bot_handle_message(self, bot_name: str, message: discord.Message, 
                                       channel_patterns: List[str]) -> bool:
        """Determine if a bot should handle a specific message."""
        self.logger.info(f"🔍 [{bot_name}] ANALYZING MESSAGE: '{message.content[:100]}...' in #{message.channel.name}")
        
        # Skip bot messages
        if message.author.bot:
            self.logger.info(f"❌ [{bot_name}] SKIPPED: Bot message from {message.author.display_name}")
            return False
        
        # Check channel filtering
        channel_match = self._matches_channel_patterns(message.channel, channel_patterns)
        if not channel_match:
            self.logger.info(f"❌ [{bot_name}] SKIPPED: Channel #{message.channel.name} not in patterns {channel_patterns}")
            return False
        else:
            self.logger.info(f"✅ [{bot_name}] CHANNEL MATCH: #{message.channel.name} matches patterns {channel_patterns}")
        
        # Check if message is a command (starts with prefix)
        if message.content.startswith('!'):
            self.logger.info(f"❌ [{bot_name}] SKIPPED: Command message (starts with !)")
            return False
        
        # Check for bot coordination (avoid multiple bots responding simultaneously)
        should_coordinate = await self._should_coordinate_response(bot_name, message)
        if should_coordinate:
            self.logger.info(f"❌ [{bot_name}] SKIPPED: Coordination - too many active responses")
            return False
        
        self.logger.info(f"🎯 [{bot_name}] WILL HANDLE: All checks passed!")
        return True
    
    def _matches_channel_patterns(self, channel: discord.TextChannel, patterns: List[str]) -> bool:
        """Check if channel matches any of the patterns."""
        if not patterns:
            return True  # No patterns means all channels
        
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
            return True  # Should coordinate (don't respond)
        
        # Check recent responses in the same channel
        recent_count = len(self.recent_responses.get(channel_id, []))
        if recent_count >= self.max_concurrent_responses:
            return True  # Should coordinate (don't respond)
        
        return False  # Can respond
    
    async def process_message(self, bot_name: str, message: discord.Message, 
                            context: ConversationContext, original_handler=None):
        """Process a message with enhanced context and coordination."""
        channel_id = None
        try:
            self.logger.debug(f"Processing message for {bot_name}: '{message.content[:50]}...'")
            
            # Mark bot as actively responding
            channel_id = message.channel.id
            if channel_id not in self.active_responses:
                self.active_responses[channel_id] = set()
            self.active_responses[channel_id].add(bot_name)
            
            # Safely extract thread ID
            thread_id = None
            try:
                if hasattr(message, 'thread') and message.thread:
                    thread_obj = getattr(message, 'thread')
                    if thread_obj and hasattr(thread_obj, 'id'):
                        thread_id = thread_obj.id
            except Exception as e:
                self.logger.warning(f"Could not extract thread_id: {e}")
            
            # Create message context
            message_context = MessageContext(
                message=message,
                channel_name=message.channel.name,
                channel_id=channel_id,
                user_id=message.author.id,
                user_name=message.author.display_name,
                content=message.content,
                timestamp=message.created_at,
                is_bot_message=message.author.bot,
                mentioned_bots=self._extract_mentioned_bots(message),
                thread_id=thread_id
            )
            
            self.logger.debug(f"Created message context for {bot_name} in #{message.channel.name}")
            
            # Determine response decision
            decision = await self._make_response_decision(bot_name, message_context, context)
            
            if decision.should_respond:
                self.logger.info(f"🚀 [{bot_name}] RESPONDING: {decision.reasoning}")
                
                # Add response delay for natural conversation flow
                if decision.delay_seconds > 0:
                    self.logger.info(f"⏳ [{bot_name}] WAITING {decision.delay_seconds:.1f}s before responding...")
                    await asyncio.sleep(decision.delay_seconds)
                
                # Store message in conversation state
                await self.conversation_state.add_message(
                    channel_id=channel_id,
                    user_id=message.author.id,
                    role='user',
                    content=message.content,
                    bot_name=None,
                    metadata={
                        'username': message.author.display_name,
                        'channel_name': message.channel.name,
                        'message_id': message.id
                    }
                )
                
                # Generate response using Ollama
                self.logger.info(f"🤖 [{bot_name}] GENERATING RESPONSE...")
                await self._generate_response(bot_name, message, context)
                
                # Record response
                await self._record_response(bot_name, channel_id)
                self.logger.info(f"✅ [{bot_name}] RESPONSE COMPLETE")
            
        except Exception as e:
            import traceback
            self.logger.error(f"Error processing message for {bot_name}: {e}")
            self.logger.error(f"Message content: '{getattr(message, 'content', 'N/A')}'")
            self.logger.error(f"Channel: {getattr(message.channel, 'name', 'N/A') if hasattr(message, 'channel') else 'N/A'}")
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
        finally:
            # Remove bot from active responses
            if channel_id and channel_id in self.active_responses:
                self.active_responses[channel_id].discard(bot_name)
                if not self.active_responses[channel_id]:
                    del self.active_responses[channel_id]
    
    def _extract_mentioned_bots(self, message: discord.Message) -> List[str]:
        """Extract mentioned bot names from message."""
        mentioned_bots = []
        
        # Check mentions
        for mention in message.mentions:
            if mention.bot:
                mentioned_bots.append(mention.display_name.lower())
        
        # Check content for bot name patterns
        content_lower = message.content.lower()
        common_bot_names = ['sage', 'spark', 'logic', 'assistant', 'bot']
        
        for bot_name in common_bot_names:
            if bot_name in content_lower:
                mentioned_bots.append(bot_name)
        
        return list(set(mentioned_bots))
    
    async def _make_response_decision(self, bot_name: str, message_context: MessageContext, 
                                    conversation_context: ConversationContext) -> ResponseDecision:
        """Make a decision about whether the bot should respond."""
        self.logger.info(f"🤔 [{bot_name}] MAKING RESPONSE DECISION for: '{message_context.content[:50]}...'")
        
        # Base response probability
        base_probability = 0.3
        
        # Factors that increase response probability
        factors = []
        
        # Bot mentioned
        if bot_name.lower() in message_context.mentioned_bots:
            factors.append(("mentioned", 0.6))
        
        # Question asked
        if '?' in message_context.content:
            factors.append(("question", 0.3))
        
        # Recent conversation activity
        if conversation_context.messages:
            recent_messages = [msg for msg in conversation_context.messages 
                             if msg.timestamp > datetime.now() - timedelta(minutes=5)]
            if len(recent_messages) > 2:
                factors.append(("active_conversation", 0.2))
        
        # Bot hasn't responded recently
        recent_bot_messages = [msg for msg in conversation_context.messages 
                             if msg.bot_name == bot_name and 
                             msg.timestamp > datetime.now() - timedelta(minutes=2)]
        if not recent_bot_messages:
            factors.append(("no_recent_response", 0.1))
        
        # Calculate final probability
        probability = base_probability
        reasoning_parts = [f"base: {base_probability}"]
        
        for factor_name, factor_value in factors:
            probability += factor_value
            reasoning_parts.append(f"{factor_name}: +{factor_value}")
        
        probability = min(probability, 1.0)
        
        # Random decision based on probability
        random_roll = random.random()
        should_respond = random_roll < probability
        
        # Calculate response delay
        delay = random.uniform(*self.response_delay_range) if should_respond else 0.0
        
        reasoning = f"Probability: {probability:.2f} ({', '.join(reasoning_parts)})"
        
        # Debug logging
        self.logger.info(f"🎲 [{bot_name}] DECISION: probability={probability:.2f}, random_roll={random_roll:.2f}, will_respond={should_respond}")
        self.logger.info(f"📋 [{bot_name}] FACTORS: {factors}")
        self.logger.info(f"🗨️ [{bot_name}] MENTIONED_BOTS: {message_context.mentioned_bots}")
        self.logger.info(f"⏱️ [{bot_name}] DELAY: {delay:.1f}s")
        
        return ResponseDecision(
            should_respond=should_respond,
            confidence=probability,
            reasoning=reasoning,
            delay_seconds=delay,
            priority=len(factors)
        )
    
    async def _generate_response(self, bot_name: str, message: discord.Message, 
                               context: ConversationContext):
        """Generate and send response using Ollama."""
        self.logger.info(f"🔗 [{bot_name}] Generating response for: '{message.content[:50]}...'")
        
        try:
            # Need to get the bot's configuration to make Ollama request
            # For now, make direct Ollama request with bot-specific system prompt
            import requests
            
            # Get bot-specific system prompt based on bot name
            system_prompts = {
                'sage': "You are Sage, a wise and thoughtful mentor who helps others think deeply about life's questions. Respond with wisdom, patience, and gentle guidance.",
                'spark': "You are Spark, a creative and innovative companion who loves brainstorming, creative projects, and inspiring new ideas. Respond with enthusiasm and creativity.",
                'logic': "You are Logic, an analytical and systematic thinker who excels at research, problem-solving, and data analysis. Respond with clarity and logical reasoning."
            }
            
            # Build conversation history from context
            messages = []
            if bot_name in system_prompts:
                messages.append({"role": "system", "content": system_prompts[bot_name]})
            
            # Add recent conversation context
            if context.messages:
                for msg in context.messages[-5:]:  # Last 5 messages for context
                    if msg.bot_name:
                        messages.append({"role": "assistant", "content": msg.content})
                    else:
                        messages.append({"role": "user", "content": msg.content})
            
            # Add current message
            messages.append({"role": "user", "content": message.content})
            
            # Make request to Ollama
            ollama_url = "http://127.0.0.1:11434/api/chat"
            payload = {
                "model": "llama3",  # Default model
                "messages": messages,
                "stream": False
            }
            
            self.logger.info(f"🤖 [{bot_name}] Making Ollama request...")
            response = requests.post(ollama_url, json=payload, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            response_text = response_data["message"]["content"]
            
            # Send the response
            await message.channel.send(response_text)
            self.logger.info(f"✅ [{bot_name}] Response sent successfully")
            
            # Store bot response in conversation state  
            await self.conversation_state.add_message(
                channel_id=message.channel.id,
                user_id=message.author.id,
                role='assistant',
                content=response_text,
                bot_name=bot_name,
                metadata={
                    'response_to_message_id': message.id
                }
            )
            
        except Exception as e:
            self.logger.error(f"❌ [{bot_name}] Failed to generate response: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Send error message
            try:
                await message.channel.send(f"❌ Sorry, I encountered an error while processing your message.")
            except Exception as send_error:
                self.logger.error(f"❌ [{bot_name}] Could not even send error message: {send_error}")
    
    async def _record_response(self, bot_name: str, channel_id: int):
        """Record that a bot has responded in a channel."""
        now = datetime.now()
        
        if channel_id not in self.recent_responses:
            self.recent_responses[channel_id] = []
        
        self.recent_responses[channel_id].append((bot_name, now))
        
        # Keep only recent responses
        self.recent_responses[channel_id] = [
            (bot, timestamp) for bot, timestamp in self.recent_responses[channel_id]
            if now - timestamp < timedelta(seconds=self.cooldown_period)
        ]
    
    async def get_channel_activity(self, channel_id: int) -> Dict[str, Any]:
        """Get activity information for a channel."""
        now = datetime.now()
        
        # Get recent responses
        recent_responses = self.recent_responses.get(channel_id, [])
        active_bots = self.active_responses.get(channel_id, set())
        
        return {
            'recent_responses': len(recent_responses),
            'active_bots': len(active_bots),
            'active_bot_names': list(active_bots),
            'last_response': recent_responses[-1][1] if recent_responses else None,
            'can_respond': len(active_bots) < self.max_concurrent_responses
        }
    
    async def reset_channel_state(self, channel_id: int):
        """Reset state for a specific channel."""
        if channel_id in self.recent_responses:
            del self.recent_responses[channel_id]
        if channel_id in self.active_responses:
            del self.active_responses[channel_id]
        
        self.logger.info(f"Reset state for channel {channel_id}")
    
    async def get_processor_stats(self) -> Dict[str, Any]:
        """Get statistics about message processing."""
        now = datetime.now()
        
        # Count active channels
        active_channels = len(self.active_responses)
        
        # Count recent responses across all channels
        total_recent_responses = sum(len(responses) for responses in self.recent_responses.values())
        
        # Count total active bots
        total_active_bots = sum(len(bots) for bots in self.active_responses.values())
        
        return {
            'active_channels': active_channels,
            'total_recent_responses': total_recent_responses,
            'total_active_bots': total_active_bots,
            'context_depth': self.context_depth,
            'max_concurrent_responses': self.max_concurrent_responses,
            'response_delay_range': self.response_delay_range,
            'cooldown_period': self.cooldown_period
        }