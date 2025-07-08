"""Discord bot with Ollama integration - Multi-bot architecture only."""

from typing import List, Optional

import discord

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


class DiscordBot:
    """Discord bot with Ollama integration - Multi-bot architecture only."""
    
    def __init__(self, config: Config, orchestrator: BotOrchestrator, 
                 channel_patterns: Optional[List[str]] = None):
        self.config = config
        self.logger = setup_logging(config.logging, config.bot.name)
        self.orchestrator = orchestrator
        self.channel_patterns = channel_patterns or []
        
        # Setup Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        
        # Register event handlers
        self.client.event(self.on_ready)
        self.client.event(self.on_message)
        
        self.logger.info(f"Bot '{config.bot.name}' initialized")
    
    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        self.logger.info(f"Bot '{self.config.bot.name}' logged in as {self.client.user}")
    
    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming Discord messages."""
        # Use orchestrator for message processing
        await self.orchestrator.process_message(
            self.config.bot.name, message, self.channel_patterns
        )
    
    
    def run(self) -> None:
        """Start the Discord bot."""
        self.logger.info(f"Starting bot '{self.config.bot.name}'...")
        self.client.run(self.config.discord.token)