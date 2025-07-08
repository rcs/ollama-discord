"""Multi-bot orchestration manager for Discord bots."""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from .bot import DiscordBot
from .config import load_config, BotConfig
from .conversation_state import ConversationState
from .service_factory import create_multi_bot_services
from .multi_bot_config import MultiBotConfig, multi_bot_config_manager


@dataclass
class BotInstance:
    """Represents a bot instance with its configuration and state."""
    name: str
    config: BotConfig
    bot: Optional[DiscordBot] = None
    channels: List[str] = None
    is_running: bool = False
    last_activity: Optional[datetime] = None
    
    def __post_init__(self):
        if self.channels is None:
            self.channels = []




class BotManager:
    """Manages multiple Discord bot instances with shared conversation state."""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.bot_instances: Dict[str, BotInstance] = {}
        self.conversation_state: Optional[ConversationState] = None
        self.multi_bot_config: MultiBotConfig
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        
    async def initialize(self):
        """Initialize the bot manager with configuration."""
        self.logger.info(f"Loading multi-bot configuration from {self.config_file}")
        
        try:
            # Load multi-bot configuration using proper Pydantic model
            self.multi_bot_config = multi_bot_config_manager.load_multi_bot_config(str(self.config_file))
            self.logger.info(f"Loaded MultiBotConfig with {len(self.multi_bot_config.bots)} bots")
            
            # Get global settings as dict for services
            global_settings_dict = self.multi_bot_config.global_settings.model_dump()
            self.logger.info(f"Global settings: {global_settings_dict}")
            
            # Create services using factory
            self.orchestrator, self.coordinator, self.response_generator, self.conversation_state = create_multi_bot_services(
                self.multi_bot_config
            )
            self.logger.info("Initialized services using service factory")
            
            
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
        
        # Validate configuration
        self._validate_configuration()
        
        # Load bot configurations
        await self._load_bot_configurations()
        
        self.logger.info(f"Initialized bot manager with {len(self.bot_instances)} bots")
    
    def _validate_configuration(self):
        """Validate the multi-bot configuration."""
        self.logger.info("Validating multi-bot configuration...")
        
        # Validate bots list - Pydantic already validates this during loading
        if not self.multi_bot_config.bots:
            raise ValueError("No bots configured in multi_bot.yaml")
        
        # Validate individual bot configurations
        for i, bot_config in enumerate(self.multi_bot_config.bots):
            # Bot config is already a proper Pydantic model, access fields directly
            required_fields = ['name', 'config_file', 'channels']
            
            if not bot_config.name:
                raise ValueError(f"Bot configuration {i} missing required field: name")
            if not bot_config.config_file:
                raise ValueError(f"Bot configuration {i} missing required field: config_file")
            if not bot_config.channels:
                raise ValueError(f"Bot {bot_config.name} must have at least one channel")
        
        self.logger.info("Configuration validation completed successfully")
    
    
    async def _load_bot_configurations(self):
        """Load individual bot configurations."""
        for bot_config in self.multi_bot_config.bots:
            # Bot config is already a proper Pydantic model, access fields directly
            bot_name = bot_config.name
            config_file = bot_config.config_file
            channels = bot_config.channels
            
            if not bot_name or not config_file:
                self.logger.warning(f"Skipping invalid bot configuration: {bot_config}")
                continue
            
            try:
                # Load bot configuration
                config_path = Path(config_file)
                if not config_path.is_absolute():
                    config_path = self.config_file.parent / config_path
                
                bot_config_obj = load_config(str(config_path))
                
                # Create bot instance
                bot_instance = BotInstance(
                    name=bot_name,
                    config=bot_config_obj,
                    channels=channels
                )
                
                self.bot_instances[bot_name] = bot_instance
                self.logger.info(f"Loaded configuration for bot: {bot_name}")
                
            except Exception as e:
                self.logger.error(f"Failed to load configuration for bot {bot_name}: {e}")
    
    async def start_all_bots(self):
        """Start all configured bots."""
        if self._running:
            self.logger.warning("Bot manager is already running")
            return
        
        self._running = True
        self.logger.info("Starting all bots...")
        
        # Start each bot in parallel
        start_tasks = []
        for bot_name, bot_instance in self.bot_instances.items():
            task = asyncio.create_task(self._start_bot(bot_instance))
            start_tasks.append(task)
            self._tasks.add(task)
        
        # Wait for all bots to start
        await asyncio.gather(*start_tasks, return_exceptions=True)
        
        self.logger.info(f"Started {len(self.bot_instances)} bots")
    
    async def _start_bot(self, bot_instance: BotInstance):
        """Start a single bot instance."""
        try:
            self.logger.info(f"Starting bot: {bot_instance.name}")
            
            # Create Discord bot with orchestrator
            bot = DiscordBot(
                config=bot_instance.config,
                orchestrator=self.orchestrator,
                channel_patterns=bot_instance.channels
            )
            
            # Store bot instance
            bot_instance.bot = bot
            bot_instance.is_running = True
            
            # Start the bot (this will block until the bot stops)
            await bot.client.start(bot_instance.config.discord.token)
            
        except Exception as e:
            self.logger.error(f"Failed to start bot {bot_instance.name}: {e}")
            bot_instance.is_running = False
            raise
    
    async def stop_all_bots(self):
        """Stop all running bots."""
        if not self._running:
            return
        
        self._running = False
        self.logger.info("Stopping all bots...")
        
        # Stop each bot
        stop_tasks = []
        for bot_name, bot_instance in self.bot_instances.items():
            if bot_instance.is_running and bot_instance.bot:
                task = asyncio.create_task(self._stop_bot(bot_instance))
                stop_tasks.append(task)
        
        # Wait for all bots to stop
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Cancel remaining tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        self._tasks.clear()
        self.logger.info("All bots stopped")
    
    async def _stop_bot(self, bot_instance: BotInstance):
        """Stop a single bot instance."""
        try:
            self.logger.info(f"Stopping bot: {bot_instance.name}")
            
            if bot_instance.bot:
                await bot_instance.bot.client.close()
            
            bot_instance.is_running = False
            bot_instance.bot = None
            
        except Exception as e:
            self.logger.error(f"Failed to stop bot {bot_instance.name}: {e}")
    
    async def restart_bot(self, bot_name: str):
        """Restart a specific bot."""
        if bot_name not in self.bot_instances:
            raise ValueError(f"Bot not found: {bot_name}")
        
        bot_instance = self.bot_instances[bot_name]
        
        # Stop the bot
        await self._stop_bot(bot_instance)
        
        # Start the bot
        await self._start_bot(bot_instance)
    
    def get_bot_status(self) -> Dict[str, Dict]:
        """Get status of all bots."""
        status = {}
        for bot_name, bot_instance in self.bot_instances.items():
            status[bot_name] = {
                'is_running': bot_instance.is_running,
                'last_activity': bot_instance.last_activity.isoformat() if bot_instance.last_activity else None,
                'channels': bot_instance.channels,
                'config_name': bot_instance.config.bot.name
            }
        return status
    
    async def reload_configuration(self):
        """Reload configuration and restart bots if needed."""
        self.logger.info("Reloading configuration...")
        
        # Stop all bots
        await self.stop_all_bots()
        
        # Reload configuration
        await self.initialize()
        
        # Start all bots
        await self.start_all_bots()
        
        self.logger.info("Configuration reloaded and bots restarted")
    
    async def run(self):
        """Run the bot manager (blocks until stopped)."""
        try:
            await self.initialize()
            await self.start_all_bots()
            
            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.error(f"Bot manager error: {e}")
        finally:
            await self.stop_all_bots()