"""Service factory for dependency injection."""

from typing import Dict, Any
from .config import Config
from .conversation_state import ConversationState
from .domain_services import MessageCoordinator, ResponseGenerator, BotOrchestrator
from .adapters import FileMessageStorage, OllamaAI, MemoryRateLimiter, DiscordNotificationSender
from .multi_bot_config import MultiBotConfig


def create_services(config: Config, global_settings: Dict[str, Any] = None):
    """Create all services with proper dependency injection."""
    if global_settings is None:
        global_settings = {}
    
    # Create conversation state
    conversation_state = ConversationState(
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
    response_generator = ResponseGenerator(ai_model, storage)
    orchestrator = BotOrchestrator(
        coordinator, response_generator, storage, rate_limiter, notification_sender
    )
    
    return orchestrator, coordinator, response_generator


def create_multi_bot_services(multi_bot_config: MultiBotConfig):
    """Create services for multi-bot deployment."""
    # Get global settings from multi-bot config
    global_settings_dict = multi_bot_config.global_settings.model_dump()
    
    # Create shared conversation state
    context_depth = global_settings_dict.get('context_depth', 10)
    conversation_state = ConversationState(
        storage_path=global_settings_dict.get('storage_path', './data/multi_bot_conversations'),
        context_depth=context_depth,
        max_history=1000  # Default for multi-bot
    )
    
    # Create shared adapters
    storage = FileMessageStorage(conversation_state)
    
    # Use default Ollama settings for multi-bot (individual bots can override)
    ai_model = OllamaAI(
        base_url="http://127.0.0.1:11434",
        model="llama3",
        timeout=60
    )
    
    rate_limiter = MemoryRateLimiter(
        enabled=True,
        max_requests_per_minute=10
    )
    
    notification_sender = DiscordNotificationSender(max_message_length=1900)
    
    # Create domain services
    coordinator = MessageCoordinator(storage, rate_limiter, global_settings_dict)
    response_generator = ResponseGenerator(ai_model, storage)
    orchestrator = BotOrchestrator(
        coordinator, response_generator, storage, rate_limiter, notification_sender
    )
    
    return orchestrator, coordinator, response_generator, conversation_state