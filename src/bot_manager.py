"""Multi-bot orchestration manager for Discord bots."""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from pathlib import Path
import json
from dataclasses import dataclass, asdict
from datetime import datetime

from .bot import DiscordBot
from .config import load_config, BotConfig
from .conversation_state import ConversationState
from .message_processor import MessageProcessor


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


@dataclass
class MultiBotConfig:
    """Configuration for multi-bot deployment."""
    bots: List[Dict[str, any]]
    global_settings: Dict[str, any]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MultiBotConfig':
        return cls(
            bots=data.get('bots', []),
            global_settings=data.get('global_settings', {})
        )


class BotManager:
    """Manages multiple Discord bot instances with shared conversation state."""
    
    def __init__(self, config_file: str):
        self.config_file = Path(config_file)
        self.bot_instances: Dict[str, BotInstance] = {}
        self.conversation_state: Optional[ConversationState] = None
        self.message_processor: Optional[MessageProcessor] = None
        self.multi_bot_config: Optional[MultiBotConfig] = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._tasks: Set[asyncio.Task] = set()
        
    async def initialize(self):
        """Initialize the bot manager with configuration."""
        self.logger.info(f"Loading multi-bot configuration from {self.config_file}")
        
        try:
            # Load multi-bot configuration
            config_data = self._load_config_file(self.config_file)
            self.logger.info(f"Loaded config data keys: {list(config_data.keys())}")
            self.logger.debug(f"Config data: {config_data}")
            
            self.multi_bot_config = MultiBotConfig.from_dict(config_data)
            self.logger.info(f"Created MultiBotConfig with {len(self.multi_bot_config.bots)} bots")
            
            # Check global_settings and convert to dict
            global_settings = getattr(self.multi_bot_config, 'global_settings', None)
            if global_settings is None:
                self.logger.warning("multi_bot_config.global_settings is None!")
                global_settings_dict = {}
            else:
                # Convert Pydantic model to dict for compatibility
                if hasattr(global_settings, 'model_dump'):
                    global_settings_dict = global_settings.model_dump()
                elif hasattr(global_settings, 'dict'):
                    global_settings_dict = global_settings.dict()
                else:
                    global_settings_dict = global_settings
                self.logger.info(f"Global settings: {global_settings_dict}")
            
            # Initialize shared conversation state
            context_depth = global_settings_dict.get('context_depth', 10)
            self.conversation_state = ConversationState(context_depth=context_depth)
            self.logger.info(f"Initialized ConversationState with context_depth={context_depth}")
            
            # Initialize message processor
            self.message_processor = MessageProcessor(
                conversation_state=self.conversation_state,
                global_settings=global_settings_dict
            )
            self.logger.info("Initialized MessageProcessor successfully")
            
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
        
        # Validate bots list
        if not hasattr(self.multi_bot_config, 'bots') or not self.multi_bot_config.bots:
            raise ValueError("No bots configured in multi_bot.yaml")
        
        # Validate global_settings
        if not hasattr(self.multi_bot_config, 'global_settings'):
            self.logger.warning("No global_settings found, using defaults")
            self.multi_bot_config.global_settings = {}
        
        global_settings = self.multi_bot_config.global_settings
        # Convert to dict if it's a Pydantic model
        if hasattr(global_settings, 'model_dump'):
            global_settings_dict = global_settings.model_dump()
        elif hasattr(global_settings, 'dict'):
            global_settings_dict = global_settings.dict()
        else:
            global_settings_dict = global_settings
        
        # Validate required global settings with defaults
        defaults = {
            'context_depth': 10,
            'max_concurrent_responses': 2,
            'response_delay': '1-3',
            'cooldown_period': 30
        }
        
        for key, default_value in defaults.items():
            if key not in global_settings_dict:
                self.logger.info(f"Setting default value for {key}: {default_value}")
                global_settings_dict[key] = default_value
        
        # Validate individual bot configurations
        for i, bot_config in enumerate(self.multi_bot_config.bots):
            # Convert Pydantic model to dict if needed
            if hasattr(bot_config, 'model_dump'):
                bot_dict = bot_config.model_dump()
            elif hasattr(bot_config, 'dict'):
                bot_dict = bot_config.dict()
            else:
                bot_dict = bot_config
            
            if not isinstance(bot_dict, dict):
                raise ValueError(f"Bot configuration {i} is not a dictionary")
            
            required_fields = ['name', 'config_file', 'channels']
            for field in required_fields:
                if field not in bot_dict:
                    raise ValueError(f"Bot configuration {i} missing required field: {field}")
            
            # Validate channels list
            if not isinstance(bot_dict['channels'], list) or not bot_dict['channels']:
                raise ValueError(f"Bot {bot_dict['name']} must have at least one channel")
        
        self.logger.info("Configuration validation completed successfully")
    
    def _load_config_file(self, config_file: Path) -> Dict:
        """Load configuration file (YAML or JSON)."""
        import yaml
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        with open(config_file, 'r') as f:
            if config_file.suffix.lower() in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif config_file.suffix.lower() == '.json':
                return json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {config_file.suffix}")
    
    async def _load_bot_configurations(self):
        """Load individual bot configurations."""
        for bot_config in self.multi_bot_config.bots:
            # Convert Pydantic model to dict if needed
            if hasattr(bot_config, 'model_dump'):
                bot_dict = bot_config.model_dump()
            elif hasattr(bot_config, 'dict'):
                bot_dict = bot_config.dict()
            else:
                bot_dict = bot_config
            
            bot_name = bot_dict.get('name')
            config_file = bot_dict.get('config_file')
            channels = bot_dict.get('channels', [])
            
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
            
            # Create enhanced message handler
            async def enhanced_message_handler(message):
                """Enhanced message processing with multi-bot coordination."""
                try:
                    # Use the bot's own logger which has DEBUG level configured
                    bot_logger = logging.getLogger(f"bot.{bot_instance.name}")
                    bot_logger.setLevel(logging.DEBUG)
                    
                    # Also ensure we can see the output by using INFO level
                    bot_logger.info(f"🔍 [{bot_instance.name}] RECEIVED MESSAGE: '{message.content[:50]}...' in #{message.channel.name}")
                    
                    # Check if this bot should handle this message
                    should_handle = await self.message_processor.should_bot_handle_message(
                        bot_instance.name, message, bot_instance.channels
                    )
                    
                    bot_logger.info(f"🤔 [{bot_instance.name}] HANDLE DECISION: {should_handle}")
                    
                    if should_handle:
                        # Get conversation context
                        context = await self.conversation_state.get_context(
                            channel_id=message.channel.id,
                            user_id=message.author.id
                        )
                        
                        # Process message with context
                        await self.message_processor.process_message(
                            bot_instance.name, message, context, None  # No fallback needed here
                        )
                        
                        # Update bot activity
                        bot_instance.last_activity = datetime.now()
                        return True  # Message was handled
                    else:
                        bot_logger.info(f"📞 [{bot_instance.name}] NOT HANDLING - will try default handler")
                        return False  # Let default handler try
                        
                except Exception as e:
                    import traceback
                    bot_logger.error(f"[{bot_instance.name}] Error in enhanced message handler: {e}")
                    bot_logger.error(f"[{bot_instance.name}] Full traceback: {traceback.format_exc()}")
                    return False  # Let default handler try
            
            # Create Discord bot with enhanced message processing
            bot = DiscordBot(bot_instance.config, custom_message_handler=enhanced_message_handler)
            
            # Make sure we can use the bot's logger in the enhanced handler
            async def enhanced_message_handler_with_bot_logger(message):
                """Enhanced message processing with multi-bot coordination using bot's logger."""
                try:
                    # Use the actual bot's logger which is properly configured
                    bot.logger.info(f"🔍 [{bot_instance.name}] RECEIVED MESSAGE: '{message.content[:50]}...' in #{message.channel.name}")
                    
                    # Check if this bot should handle this message
                    should_handle = await self.message_processor.should_bot_handle_message(
                        bot_instance.name, message, bot_instance.channels
                    )
                    
                    bot.logger.info(f"🤔 [{bot_instance.name}] HANDLE DECISION: {should_handle}")
                    
                    if should_handle:
                        # Get conversation context
                        context = await self.conversation_state.get_context(
                            channel_id=message.channel.id,
                            user_id=message.author.id
                        )
                        
                        # Process message with context
                        await self.message_processor.process_message(
                            bot_instance.name, message, context, None  # No fallback needed here
                        )
                        
                        # Update bot activity
                        bot_instance.last_activity = datetime.now()
                        return True  # Message was handled
                    else:
                        bot.logger.info(f"📞 [{bot_instance.name}] NOT HANDLING - will try default handler")
                        return False  # Let default handler try
                        
                except Exception as e:
                    import traceback
                    bot.logger.error(f"[{bot_instance.name}] Error in enhanced message handler: {e}")
                    bot.logger.error(f"[{bot_instance.name}] Full traceback: {traceback.format_exc()}")
                    return False  # Let default handler try
            
            # Replace the handler with the one that uses bot's logger
            bot.custom_message_handler = enhanced_message_handler_with_bot_logger
            
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