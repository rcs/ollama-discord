import pytest
from unittest.mock import Mock
from src.bot import DiscordBot
from src.config import Config, BotConfig, DiscordConfig, OllamaConfig


class TestDiscordBot:
    """Test cases for the DiscordBot class."""
    
    def test_bot_initialization(self):
        """Test that bot can be initialized with config."""
        config = Config(
            bot=BotConfig(name="test-bot"),
            discord=DiscordConfig(token="test-token"),
            ollama=OllamaConfig()
        )
        bot = DiscordBot(config)
        assert bot is not None
        assert bot.config == config


class TestConfig:
    """Test cases for the Config class."""
    
    def test_config_creation(self):
        """Test that config can be created with required fields."""
        config = Config(
            bot=BotConfig(name="test-bot"),
            discord=DiscordConfig(token="test-token"),
            ollama=OllamaConfig()
        )
        assert config is not None
        assert config.bot.name == "test-bot"
        assert config.discord.token == "test-token" 