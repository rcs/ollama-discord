import pytest
from unittest.mock import Mock, AsyncMock
from src.bot import DiscordBot, format_message_for_discord
from src.config import Config, BotConfig, DiscordConfig, OllamaConfig, StorageConfig, MessageConfig, RateLimitConfig, LoggingConfig
from src.domain_services import BotOrchestrator


class TestDiscordBot:
    """Test cases for the DiscordBot class."""
    
    def create_test_config(self):
        """Helper to create a test config."""
        return Config(
            bot=BotConfig(name="test-bot"),
            discord=DiscordConfig(token="test-token"),
            ollama=OllamaConfig(),
            storage=StorageConfig(path="./test_data"),
            message=MessageConfig(),
            rate_limit=RateLimitConfig(),
            logging=LoggingConfig()
        )
    
    def test_bot_initialization_requires_orchestrator(self):
        """Test that bot requires orchestrator in new architecture."""
        config = self.create_test_config()
        mock_orchestrator = Mock(spec=BotOrchestrator)
        
        bot = DiscordBot(config, orchestrator=mock_orchestrator)
        assert bot is not None
        assert bot.config == config
        assert bot.orchestrator == mock_orchestrator
    
    def test_bot_initialization_with_orchestrator(self):
        """Test that bot can be initialized with orchestrator."""
        config = self.create_test_config()
        mock_orchestrator = Mock(spec=BotOrchestrator)
        channel_patterns = ["general", "test-*"]
        
        bot = DiscordBot(config, orchestrator=mock_orchestrator, channel_patterns=channel_patterns)
        assert bot is not None
        assert bot.config == config
        assert bot.orchestrator == mock_orchestrator
        assert bot.channel_patterns == channel_patterns
    
    def test_bot_config_validation(self):
        """Test that bot validates config properly."""
        config = self.create_test_config()
        mock_orchestrator = Mock(spec=BotOrchestrator)
        # This should not raise an exception
        bot = DiscordBot(config, orchestrator=mock_orchestrator)
        assert bot is not None
    
    @pytest.mark.asyncio
    async def test_on_message_with_orchestrator(self):
        """Test message handling with orchestrator."""
        config = self.create_test_config()
        mock_orchestrator = AsyncMock(spec=BotOrchestrator)
        mock_orchestrator.process_message.return_value = True
        
        bot = DiscordBot(config, orchestrator=mock_orchestrator, channel_patterns=["general"])
        
        # Mock Discord message
        mock_message = Mock()
        mock_message.content = "Hello bot"
        
        # Call on_message
        await bot.on_message(mock_message)
        
        # Verify orchestrator was called
        mock_orchestrator.process_message.assert_called_once_with(
            "test-bot", mock_message, ["general"]
        )
    
    @pytest.mark.asyncio
    async def test_on_message_direct_orchestrator_call(self):
        """Test message handling goes directly to orchestrator."""
        config = self.create_test_config()
        mock_orchestrator = AsyncMock(spec=BotOrchestrator)
        
        bot = DiscordBot(config, orchestrator=mock_orchestrator, channel_patterns=["general"])
        
        # Mock Discord message
        mock_message = Mock()
        mock_message.content = "Hello bot"
        
        # Call on_message
        await bot.on_message(mock_message)
        
        # Verify orchestrator was called directly
        mock_orchestrator.process_message.assert_called_once_with(
            "test-bot", mock_message, ["general"]
        )


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
