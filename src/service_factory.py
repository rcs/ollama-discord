"""Service factory for dependency injection."""

from dataclasses import dataclass
from typing import Dict, Any
from .config import Config
from .conversation_state import ConversationState
from .domain_services import MessageCoordinator, ResponseGenerator, BotOrchestrator
from .adapters import FileMessageStorage, OllamaAI, MemoryRateLimiter, DiscordNotificationSender, SQLiteMessageStorage
from .multi_bot_config import MultiBotConfig


@dataclass
class BotServices:
    """Container for bot-specific services."""
    orchestrator: BotOrchestrator
    response_generator: ResponseGenerator
    storage: FileMessageStorage
    conversation_state: ConversationState


def create_services(config: Config, global_settings: Dict[str, Any] = None):
    """Create all services with proper dependency injection."""
    if global_settings is None:
        global_settings = {}
    
    # Create conversation state
    conversation_state = ConversationState(
        bot_name=config.bot.name,
        storage_path=config.storage.path,
        context_depth=global_settings.get('context_depth', 10),
        max_history=config.storage.max_history
    )
    
    # Create adapters
    storage = FileMessageStorage(conversation_state)
    
    ai_model = OllamaAI(
        base_url=config.ollama.base_url,
        model=config.ollama.model,
        timeout=config.ollama.timeout
    )
    
    rate_limiter = MemoryRateLimiter(
        enabled=config.rate_limit.enabled,
        max_requests_per_minute=config.rate_limit.max_requests_per_minute
    )
    
    notification_sender = DiscordNotificationSender(
        max_message_length=config.message.max_length
    )
    
    # Create domain services
    coordinator = MessageCoordinator(storage, rate_limiter, global_settings)
    response_generator = ResponseGenerator(
        ai_model=ai_model, 
        storage=storage, 
        system_prompt=config.system_prompt,
        bot_name=config.bot.name
    )
    orchestrator = BotOrchestrator(
        coordinator, response_generator, storage, rate_limiter, notification_sender
    )
    
    return orchestrator, coordinator, response_generator





def create_bot_services(bot_name: str, bot_config: Config, 
                       shared_coordinator: MessageCoordinator,
                       shared_ai_model: OllamaAI,
                       shared_rate_limiter: MemoryRateLimiter,
                       shared_notification_sender: DiscordNotificationSender,
                       global_settings: Dict[str, Any]) -> BotServices:
    """Create isolated services for a specific bot."""
    
    # Bot-specific conversation state
    conversation_state = ConversationState(
        bot_name=bot_name,
        storage_path=global_settings.get('storage_path', './data/multi_bot_conversations'),
        context_depth=global_settings.get('context_depth', 10),
        max_history=bot_config.storage.max_history
    )
    
    # Bot-specific storage - choose between file and SQLite
    storage_type = global_settings.get('storage_type', 'file')
    if storage_type == 'sqlite':
        storage = SQLiteMessageStorage(
            bot_name=bot_name,
            db_path=global_settings.get('storage_path', './data/conversations.db'),
            session_timeout=global_settings.get('session_timeout', 3600)
        )
    else:
        storage = FileMessageStorage(conversation_state)
    
    # Bot-specific response generator with its own prompt
    response_generator = ResponseGenerator(
        ai_model=shared_ai_model,
        storage=storage,
        system_prompt=bot_config.system_prompt,
        bot_name=bot_name
    )
    
    # Bot-specific orchestrator
    orchestrator = BotOrchestrator(
        coordinator=shared_coordinator,
        response_generator=response_generator,
        storage=storage,
        rate_limiter=shared_rate_limiter,
        notification_sender=shared_notification_sender,
        bot_name=bot_name
    )
    
    return BotServices(
        orchestrator=orchestrator,
        response_generator=response_generator,
        storage=storage,
        conversation_state=conversation_state
    )


def create_multi_bot_services(multi_bot_config):
    """
    Compatibility function for tests - creates services for the first bot in the config.
    
    This function is deprecated and only exists for backward compatibility with tests.
    New code should use create_bot_services() directly.
    """
    if not multi_bot_config.bots:
        raise ValueError("No bots configured")
    
    # Use the first bot for compatibility
    first_bot = multi_bot_config.bots[0]
    
    # Create a minimal config for the first bot
    from .config import Config, BotConfig, DiscordConfig, OllamaConfig, StorageConfig, MessageConfig, RateLimitConfig
    
    bot_config = Config(
        bot=BotConfig(name=first_bot.name, description="Test bot"),
        discord=DiscordConfig(token=first_bot.discord_token, command_prefix="!"),
        ollama=OllamaConfig(base_url="http://127.0.0.1:11434", model="llama3", timeout=60),
        system_prompt="You are a helpful AI assistant.",
        storage=StorageConfig(path="./data/test_conversations", max_history=1000),
        message=MessageConfig(max_length=1900, typing_indicator=True),
        rate_limit=RateLimitConfig(enabled=True, max_requests_per_minute=10)
    )
    
    # Create shared services
    global_settings_dict = multi_bot_config.global_settings.model_dump()
    
    ai_model = OllamaAI(
        base_url="http://127.0.0.1:11434",
        model="llama3",
        timeout=60
    )
    
    rate_limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=10)
    notification_sender = DiscordNotificationSender(max_message_length=1900)
    
    # Create conversation state for coordinator
    temp_conversation_state = ConversationState(
        bot_name="coordinator",
        storage_path=global_settings_dict.get('storage_path', './data/multi_bot_conversations'),
        context_depth=global_settings_dict.get('context_depth', 10),
        max_history=1000
    )
    temp_storage = FileMessageStorage(temp_conversation_state)
    coordinator = MessageCoordinator(temp_storage, rate_limiter, global_settings_dict)
    
    # Create bot services
    bot_services = create_bot_services(
        bot_name=first_bot.name,
        bot_config=bot_config,
        shared_coordinator=coordinator,
        shared_ai_model=ai_model,
        shared_rate_limiter=rate_limiter,
        shared_notification_sender=notification_sender,
        global_settings=global_settings_dict
    )
    
    # Return in the format expected by tests
    return (
        bot_services.orchestrator,
        coordinator,
        bot_services.response_generator,
        bot_services.conversation_state
    )