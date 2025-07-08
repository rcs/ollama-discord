"""Discord bot with Ollama integration."""

import asyncio
import textwrap
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import discord
import requests

from .config import Config, setup_logging
from .domain_services import BotOrchestrator


def format_message_for_discord(content: str, max_length: int = 2000) -> List[str]:
    """
    Format a message for Discord, handling code blocks and long messages.
    
    Args:
        content: The message content to format
        max_length: Maximum length per Discord message (default 2000)
    
    Returns:
        List of formatted message chunks
    """
    if len(content) <= max_length:
        return [content]
    
    # Check if content contains code blocks
    if "```" in content:
        return _split_code_block_message(content, max_length)
    else:
        return _split_regular_message(content, max_length)


def _split_code_block_message(content: str, max_length: int) -> List[str]:
    """Split a message containing code blocks."""
    chunks = []
    current_chunk = ""
    in_code_block = False
    code_block_lang = ""
    
    lines = content.split('\n')
    
    for line in lines:
        # Check for code block markers
        if line.strip().startswith('```'):
            if not in_code_block:
                # Starting a code block
                code_block_lang = line.strip()[3:].strip()
                test_chunk = current_chunk + f"\n```{code_block_lang}\n"
                if len(test_chunk) > max_length:
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = f"```{code_block_lang}\n"
                    else:
                        current_chunk = test_chunk
                else:
                    current_chunk = test_chunk
                in_code_block = True
            else:
                # Ending a code block
                test_chunk = current_chunk + "\n```"
                if len(test_chunk) > max_length:
                    chunks.append(current_chunk)
                    current_chunk = "```"
                else:
                    current_chunk = test_chunk
                in_code_block = False
        else:
            test_chunk = current_chunk + line + "\n"
            if len(test_chunk) > max_length:
                if in_code_block:
                    # Close the code block and start a new chunk
                    chunks.append(current_chunk + "\n```")
                    current_chunk = f"```{code_block_lang}\n{line}\n"
                else:
                    chunks.append(current_chunk)
                    current_chunk = line + "\n"
            else:
                current_chunk = test_chunk
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def _split_regular_message(content: str, max_length: int) -> List[str]:
    """Split a regular message without code blocks."""
    chunks = []
    words = content.split()
    current_chunk = ""
    
    for word in words:
        test_chunk = current_chunk + " " + word if current_chunk else word
        if len(test_chunk) > max_length:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = word
            else:
                # Single word is too long, split it
                chunks.append(word[:max_length-3] + "...")
                current_chunk = ""
        else:
            current_chunk = test_chunk
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


class ConversationStorage:
    """Handles conversation history storage."""
    
    def __init__(self, config):
        self.config = config
        self.storage_path = Path(config.storage.path)
        if config.storage.enabled:
            self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def load_history(self, user_id: str, channel_id: str) -> List[Dict]:
        """Load conversation history for a user in a channel."""
        if not self.config.storage.enabled:
            return []
        
        history_file = self.storage_path / f"{channel_id}_{user_id}.json"
        if not history_file.exists():
            return []
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def save_history(self, user_id: str, channel_id: str, history: List[Dict]):
        """Save conversation history for a user in a channel."""
        if not self.config.storage.enabled:
            return
        
        # Limit history size
        if len(history) > self.config.storage.max_history:
            history = history[-self.config.storage.max_history:]
        
        history_file = self.storage_path / f"{channel_id}_{user_id}.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Failed to save conversation history: {e}")
    
    def add_message(self, user_id: str, channel_id: str, role: str, content: str):
        """Add a message to the conversation history."""
        if not self.config.storage.enabled:
            return
        
        history = self.load_history(user_id, channel_id)
        history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.save_history(user_id, channel_id, history)


class RateLimiter:
    """Simple rate limiter for bot requests."""
    
    def __init__(self, config):
        self.config = config
        self.requests: Dict[str, List[datetime]] = {}
    
    def can_request(self, user_id: str) -> bool:
        """Check if user can make a request."""
        if not self.config.rate_limit.enabled:
            return True
        
        now = datetime.now()
        user_requests = self.requests.get(user_id, [])
        
        # Remove requests older than 1 minute
        user_requests = [req_time for req_time in user_requests 
                        if (now - req_time).total_seconds() < 60]
        
        self.requests[user_id] = user_requests
        
        return len(user_requests) < self.config.rate_limit.max_requests_per_minute
    
    def record_request(self, user_id: str):
        """Record a request for rate limiting."""
        if not self.config.rate_limit.enabled:
            return
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        self.requests[user_id].append(datetime.now())


class DiscordBot:
    """Discord bot with Ollama integration and configuration support."""
    
    def __init__(self, config: Config, orchestrator: Optional[BotOrchestrator] = None, 
                 custom_message_handler=None, channel_patterns: Optional[List[str]] = None):
        self.config = config
        self.logger = setup_logging(config.logging, config.bot.name)
        self.orchestrator = orchestrator
        self.custom_message_handler = custom_message_handler
        self.channel_patterns = channel_patterns or []
        
        # Legacy components for backwards compatibility
        if not orchestrator:
            self.storage = ConversationStorage(config)
            self.rate_limiter = RateLimiter(config)
        
        # Setup Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        
        # Register event handlers
        self.client.event(self.on_ready)
        self.client.event(self.on_message)
        
        self.logger.info(f"Bot '{config.bot.name}' initialized")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f"Bot '{self.config.bot.name}' logged in as {self.client.user}")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming Discord messages."""
        # If there's a custom message handler, use it first
        if self.custom_message_handler:
            # Let the custom handler decide what to do
            handled = await self.custom_message_handler(message)
            if handled:
                return
        
        # Use orchestrator if available (new architecture)
        if self.orchestrator:
            await self.orchestrator.process_message(
                self.config.bot.name, message, self.channel_patterns
            )
            return
        
        # Legacy behavior for backwards compatibility
        # Default behavior: Ignore bot messages and messages not starting with command prefix
        if message.author.bot or not message.content.startswith(self.config.discord.command_prefix):
            return
        
        # Extract prompt
        prompt = message.content[len(self.config.discord.command_prefix):].strip()
        if not prompt:
            await message.channel.send("Please provide a message after the command.")
            return
        
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        
        # Check rate limiting
        if not self.rate_limiter.can_request(user_id):
            await message.channel.send("You're sending requests too quickly. Please wait a moment.")
            return
        
        # Record the request
        self.rate_limiter.record_request(user_id)
        
        # Show typing indicator
        if self.config.message.typing_indicator:
            await message.channel.typing()
        
        try:
            # Get conversation history
            history = self.storage.load_history(user_id, channel_id)
            
            # Add user message to history
            self.storage.add_message(user_id, channel_id, "user", prompt)
            
            # Generate response
            response = await asyncio.to_thread(self.ollama_chat, prompt, history)
            
            # Add bot response to history
            self.storage.add_message(user_id, channel_id, "assistant", response)
            
            # Send response, chunking if necessary
            await self.send_chunked_message(message.channel, response)
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            await message.channel.send("Sorry, I encountered an error processing your request.")
    
    def ollama_chat(self, prompt: str, history: List[Dict] = None) -> str:
        """Send request to Ollama API."""
        messages = []
        
        # Add system prompt
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        
        # Add conversation history (excluding timestamps and keeping only recent messages)
        if history:
            for msg in history[-10:]:  # Keep last 10 messages for context
                if msg["role"] in ["user", "assistant"]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
        
        # Add current user message
        messages.append({"role": "user", "content": prompt})
        
        # Make request to Ollama
        ollama_url = f"{self.config.ollama.base_url}/api/chat"
        payload = {
            "model": self.config.ollama.model,
            "messages": messages,
            "stream": False
        }
        
        response = requests.post(
            ollama_url,
            json=payload,
            timeout=self.config.ollama.timeout
        )
        response.raise_for_status()
        
        return response.json()["message"]["content"]
    
    async def send_chunked_message(self, channel, content: str):
        """Send message, chunking if necessary to fit Discord's character limit."""
        max_length = self.config.message.max_length
        
        # Use the new formatting utility
        chunks = format_message_for_discord(content, max_length)
        
        for chunk in chunks:
            await channel.send(chunk)
    
    def run(self):
        """Start the Discord bot."""
        self.logger.info(f"Starting bot '{self.config.bot.name}'...")
        self.client.run(self.config.discord.token)