import pytest
from src.bot import Bot
from src.config import Config


class TestBot:
    """Test cases for the Bot class."""
    
    def test_bot_initialization(self):
        """Test that bot can be initialized with config."""
        config = Config()
        bot = Bot(config)
        assert bot is not None
        assert bot.config == config
    
    def test_bot_config_validation(self):
        """Test that bot validates config properly."""
        config = Config()
        # This should not raise an exception
        bot = Bot(config)
        assert bot is not None


class TestConfig:
    """Test cases for the Config class."""
    
    def test_config_creation(self):
        """Test that config can be created."""
        config = Config()
        assert config is not None
    
    def test_config_defaults(self):
        """Test that config has expected default values."""
        config = Config()
        # Add assertions for expected default values
        assert hasattr(config, 'discord_token')
        assert hasattr(config, 'ollama_url') 