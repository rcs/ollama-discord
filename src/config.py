"""Configuration management for Ollama Discord Bot."""

import os
import yaml
from typing import Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
import logging
from dotenv import load_dotenv


class BotConfig(BaseModel):
    """Bot identification configuration."""
    name: str
    description: Optional[str] = None


class DiscordConfig(BaseModel):
    """Discord-specific configuration."""
    token: str
    command_prefix: str = "!ask"
    
    @field_validator('token')
    @classmethod
    def validate_token(cls, v):
        if not v or v.startswith("YOUR_"):
            raise ValueError("Discord token must be set and not be a placeholder")
        return v


class OllamaConfig(BaseModel):
    """Ollama API configuration."""
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3"
    timeout: int = 60


class StorageConfig(BaseModel):
    """Storage configuration for conversation history."""
    enabled: bool = True
    type: str = "file"
    path: str = "./data/{bot_name}"
    max_history: int = 50


class MessageConfig(BaseModel):
    """Message handling configuration."""
    max_length: int = 1900
    typing_indicator: bool = True


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    enabled: bool = False
    max_requests_per_minute: int = 10


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config(BaseModel):
    """Main configuration model."""
    bot: BotConfig
    discord: DiscordConfig
    ollama: OllamaConfig
    system_prompt: str = "You are a helpful AI assistant."
    storage: StorageConfig = StorageConfig()
    message: MessageConfig = MessageConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    logging: LoggingConfig = LoggingConfig()


def expand_env_vars(data: Any) -> Any:
    """Recursively expand environment variables in configuration data."""
    if isinstance(data, dict):
        return {key: expand_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [expand_env_vars(item) for item in data]
    elif isinstance(data, str):
        return os.path.expandvars(data)
    return data


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file with environment variable expansion."""
    # Load .env file if it exists (looks for .env in current working directory)
    env_file = Path('.env')
    if env_file.exists():
        load_dotenv(env_file)
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    
    # Expand environment variables
    expanded_config = expand_env_vars(raw_config)
    
    # Replace {bot_name} placeholder in storage path
    if 'storage' in expanded_config and 'path' in expanded_config['storage']:
        bot_name = expanded_config.get('bot', {}).get('name', 'default')
        expanded_config['storage']['path'] = expanded_config['storage']['path'].format(
            bot_name=bot_name
        )
    
    return Config(**expanded_config)


def setup_logging(config: LoggingConfig, bot_name: str) -> logging.Logger:
    """Setup logging with the specified configuration."""
    logger = logging.getLogger(f"ollama-discord.{bot_name}")
    
    # Map string levels to logging constants
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    log_level = level_map.get(config.level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger