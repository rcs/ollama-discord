import pytest
from src.bot import DiscordBot, Config, format_message_for_discord


class TestBot:
    """Test cases for the Bot class."""
    
    def test_bot_initialization(self):
        """Test that bot can be initialized with config."""
        config = Config()
        bot = DiscordBot(config)
        assert bot is not None
        assert bot.config == config
    
    def test_bot_config_validation(self):
        """Test that bot validates config properly."""
        config = Config()
        # This should not raise an exception
        bot = DiscordBot(config)
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


class TestMessageFormatting:
    """Test cases for message formatting utilities."""
    
    def test_format_short_message(self):
        """Test formatting of short messages."""
        message = "Hello, world!"
        chunks = format_message_for_discord(message, max_length=2000)
        assert len(chunks) == 1
        assert chunks[0] == message
    
    def test_format_long_message(self):
        """Test formatting of long messages."""
        # Create a message longer than max_length
        long_message = "word " * 1000  # ~5000 characters
        chunks = format_message_for_discord(long_message, max_length=100)
        assert len(chunks) > 1
        assert all(len(chunk) <= 100 for chunk in chunks)
    
    def test_format_code_block_message(self):
        """Test formatting of messages with code blocks."""
        code_message = """Here's some code:

```python
def hello_world():
    print("Hello, world!")
    return "success"
```

This is the end."""
        
        chunks = format_message_for_discord(code_message, max_length=50)
        assert len(chunks) > 1
        
        # Check that code blocks are properly preserved
        all_content = "".join(chunks)
        assert "```python" in all_content
        assert "```" in all_content
    
    def test_format_single_long_word(self):
        """Test formatting when a single word is longer than max_length."""
        long_word = "a" * 100
        chunks = format_message_for_discord(long_word, max_length=50)
        assert len(chunks) == 1
        assert chunks[0] == long_word[:47] + "..."
    
    def test_format_empty_message(self):
        """Test formatting of empty message."""
        chunks = format_message_for_discord("", max_length=100)
        assert len(chunks) == 1
        assert chunks[0] == "" 