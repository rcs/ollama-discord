"""Integration tests for context isolation between bots.

These tests verify that in realistic multi-bot scenarios, each bot maintains
its own isolated conversation context and doesn't see other bots' interactions.
"""

import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from src.service_factory import create_bot_services
from src.config import Config, BotConfig, DiscordConfig, OllamaConfig, StorageConfig, MessageConfig, RateLimitConfig
from src.adapters import OllamaAI, MemoryRateLimiter, DiscordNotificationSender
from src.domain_services import MessageCoordinator
from src.conversation_state import ConversationState


class MockDiscordMessage:
    """Mock Discord message for testing."""
    
    def __init__(self, content: str, author_id: int = 12345, channel_id: int = 67890, 
                 channel_name: str = "general", author_name: str = "testuser", message_id: int = None):
        self.content = content
        self.id = message_id or hash(content) % 1000000
        self.channel = AsyncMock()
        self.channel.id = channel_id
        self.channel.name = channel_name
        self.channel.send = AsyncMock(return_value=None)
        self.author = Mock()
        self.author.id = author_id
        self.author.display_name = author_name
        self.author.bot = False


class TestMultiBotContextIsolation:
    """Test context isolation in multi-bot scenarios."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_ai_model(self):
        """Create a mock AI model that returns bot-specific responses."""
        ai_model = AsyncMock()
        
        def generate_response(messages):
            # Extract bot name from system prompt to generate bot-specific responses
            system_msg = next((msg for msg in messages if msg.get('role') == 'system'), {})
            system_content = system_msg.get('content', '').lower()
            
            if 'sage' in system_content:
                return "Sage's wise response"
            elif 'spark' in system_content:
                return "Spark's creative response"
            elif 'logic' in system_content:
                return "Logic's analytical response"
            else:
                return "Generic response"
        
        ai_model.generate_response.side_effect = generate_response
        return ai_model
    
    @pytest.fixture
    def bot_services(self, temp_storage_path, mock_ai_model):
        """Create isolated services for multiple bots."""
        services = {}
        
        # Create shared services
        rate_limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=10)
        notification_sender = DiscordNotificationSender(max_message_length=1900)
        
        # Create shared coordinator
        global_settings = {
            'storage_path': temp_storage_path,
            'context_depth': 10,
            'max_concurrent_responses': 2,
            'response_delay': '1-3',
            'cooldown_period': 30
        }
        
        temp_conversation_state = ConversationState(
            bot_name="coordinator",
            storage_path=temp_storage_path,
            context_depth=10,
            max_history=1000
        )
        from src.adapters import FileMessageStorage
        temp_storage = FileMessageStorage(temp_conversation_state)
        coordinator = MessageCoordinator(temp_storage, rate_limiter, global_settings)
        
        # Create bot-specific services
        for bot_name in ['sage', 'spark', 'logic']:
            bot_config = Config(
                bot=BotConfig(name=bot_name, description=f"{bot_name.title()} bot"),
                discord=DiscordConfig(token=f"fake_token_{bot_name}", command_prefix="!"),
                ollama=OllamaConfig(base_url="http://127.0.0.1:11434", model="llama3", timeout=60),
                system_prompt=f"You are {bot_name.title()}, a {bot_name}-specific AI assistant.",
                storage=StorageConfig(path=temp_storage_path, max_history=1000),
                message=MessageConfig(max_length=1900, typing_indicator=True),
                rate_limit=RateLimitConfig(enabled=True, max_requests_per_minute=10)
            )
            
            services[bot_name] = create_bot_services(
                bot_name=bot_name,
                bot_config=bot_config,
                shared_coordinator=coordinator,
                shared_ai_model=mock_ai_model,
                shared_rate_limiter=rate_limiter,
                shared_notification_sender=notification_sender,
                global_settings=global_settings
            )
        
        return services
    
    @pytest.mark.asyncio
    async def test_simultaneous_message_processing_isolation(self, bot_services):
        """Test that bots processing the same message maintain isolated contexts."""
        message = MockDiscordMessage("Hello everyone!")
        channel_patterns = ["general"]
        
        # Process the same message with all bots sequentially to avoid coordination conflicts
        results = []
        for bot_name, services in bot_services.items():
            result = await services.orchestrator.process_message(bot_name, message, channel_patterns)
            results.append((bot_name, result))
        
        # At least some bots should have processed the message successfully
        successful_bots = [bot_name for bot_name, result in results if result is True]
        assert len(successful_bots) >= 2, f"At least 2 bots should process successfully, got: {successful_bots}"
        
        # Verify each successful bot has its own isolated conversation context
        channel_id = message.channel.id
        user_id = message.author.id
        
        for bot_name in successful_bots:
            services = bot_services[bot_name]
            context = await services.storage.get_context(channel_id, user_id)
            
            # Each bot should have the user message and its own response
            assert len(context.messages) == 2, f"Bot {bot_name} should have user message + bot response"
            
            # Check user message
            user_msg = context.messages[0]
            assert user_msg.role == 'user'
            assert user_msg.content == "Hello everyone!"
            
            # Check bot response
            bot_msg = context.messages[1]
            assert bot_msg.role == 'assistant'
            assert bot_msg.bot_name == bot_name
            assert bot_name.title() in bot_msg.content, f"Bot {bot_name} response should contain its name"
    
    @pytest.mark.asyncio
    async def test_sequential_conversation_isolation(self, bot_services):
        """Test that sequential conversations with different bots remain isolated."""
        channel_id = 67890
        user_id = 12345
        
        # User talks to sage
        sage_message = MockDiscordMessage("What is wisdom?", channel_id=channel_id, author_id=user_id)
        sage_result = await bot_services['sage'].orchestrator.process_message('sage', sage_message, ["general"])
        
        # User talks to spark
        spark_message = MockDiscordMessage("Give me a creative idea", channel_id=channel_id, author_id=user_id)
        spark_result = await bot_services['spark'].orchestrator.process_message('spark', spark_message, ["general"])
        
        # Verify processing succeeded
        assert sage_result is True, "Sage should have processed the message successfully"
        assert spark_result is True, "Spark should have processed the message successfully"
        
        # Verify each bot only sees its own conversation
        sage_context = await bot_services['sage'].storage.get_context(channel_id, user_id)
        spark_context = await bot_services['spark'].storage.get_context(channel_id, user_id)
        logic_context = await bot_services['logic'].storage.get_context(channel_id, user_id)
        
        # Sage should only see wisdom conversation
        assert len(sage_context.messages) == 2
        assert "wisdom" in sage_context.messages[0].content
        assert "Sage" in sage_context.messages[1].content
        assert "creative" not in sage_context.messages[0].content
        assert "problem" not in sage_context.messages[0].content
        
        # Spark should only see creative conversation
        assert len(spark_context.messages) == 2
        assert "creative" in spark_context.messages[0].content
        assert "Spark" in spark_context.messages[1].content
        assert "wisdom" not in spark_context.messages[0].content
        assert "problem" not in spark_context.messages[0].content
        
        # Logic should have no messages (didn't talk to logic)
        assert len(logic_context.messages) == 0
    
    @pytest.mark.asyncio
    async def test_multi_user_context_isolation(self, bot_services):
        """Test that different users' conversations are isolated per bot."""
        user1_id = 11111
        user2_id = 22222
        channel_id = 67890
        
        # User 1 talks to sage
        user1_message = MockDiscordMessage("Hello sage, I'm user 1", 
                                         channel_id=channel_id, author_id=user1_id)
        await bot_services['sage'].orchestrator.process_message('sage', user1_message, ["general"])
        
        # User 2 talks to sage
        user2_message = MockDiscordMessage("Hello sage, I'm user 2", 
                                         channel_id=channel_id, author_id=user2_id)
        await bot_services['sage'].orchestrator.process_message('sage', user2_message, ["general"])
        
        # User 1 talks to spark
        user1_spark_message = MockDiscordMessage("Hello spark, I'm user 1", 
                                                channel_id=channel_id, author_id=user1_id)
        await bot_services['spark'].orchestrator.process_message('spark', user1_spark_message, ["general"])
        
        # Verify contexts are isolated by user and bot
        sage_user1_context = await bot_services['sage'].storage.get_context(channel_id, user1_id)
        sage_user2_context = await bot_services['sage'].storage.get_context(channel_id, user2_id)
        spark_user1_context = await bot_services['spark'].storage.get_context(channel_id, user1_id)
        spark_user2_context = await bot_services['spark'].storage.get_context(channel_id, user2_id)
        
        # Sage-User1: should only see user1's message to sage
        assert len(sage_user1_context.messages) == 2
        assert "user 1" in sage_user1_context.messages[0].content
        assert "sage" in sage_user1_context.messages[0].content.lower()
        
        # Sage-User2: should only see user2's message to sage
        assert len(sage_user2_context.messages) == 2
        assert "user 2" in sage_user2_context.messages[0].content
        assert "sage" in sage_user2_context.messages[0].content.lower()
        
        # Spark-User1: should only see user1's message to spark
        assert len(spark_user1_context.messages) == 2
        assert "user 1" in spark_user1_context.messages[0].content
        assert "spark" in spark_user1_context.messages[0].content.lower()
        
        # Spark-User2: should have no messages (user2 didn't talk to spark)
        assert len(spark_user2_context.messages) == 0
    
    @pytest.mark.asyncio
    async def test_conversation_history_building_isolation(self, bot_services):
        """Test that conversation history builds correctly in isolation."""
        channel_id = 67890
        user_id = 12345
        
        # Build a conversation with sage
        messages_to_sage = [
            "What is wisdom?",
            "Can you elaborate on that?",
            "Give me an example"
        ]
        
        for msg_content in messages_to_sage:
            message = MockDiscordMessage(msg_content, channel_id=channel_id, author_id=user_id)
            await bot_services['sage'].orchestrator.process_message('sage', message, ["general"])
        
        # Build a different conversation with spark
        messages_to_spark = [
            "I need creative ideas",
            "Something more innovative"
        ]
        
        for msg_content in messages_to_spark:
            message = MockDiscordMessage(msg_content, channel_id=channel_id, author_id=user_id)
            await bot_services['spark'].orchestrator.process_message('spark', message, ["general"])
        
        # Verify conversation histories are isolated
        sage_context = await bot_services['sage'].storage.get_context(channel_id, user_id)
        spark_context = await bot_services['spark'].storage.get_context(channel_id, user_id)
        logic_context = await bot_services['logic'].storage.get_context(channel_id, user_id)
        
        # Sage should have 6 messages (3 user + 3 bot responses)
        assert len(sage_context.messages) == 6
        user_messages = [msg for msg in sage_context.messages if msg.role == 'user']
        bot_messages = [msg for msg in sage_context.messages if msg.role == 'assistant']
        assert len(user_messages) == 3
        assert len(bot_messages) == 3
        assert all("wisdom" in msg.content or "elaborate" in msg.content or "example" in msg.content 
                  for msg in user_messages)
        assert all(msg.bot_name == 'sage' for msg in bot_messages)
        
        # Spark should have 4 messages (2 user + 2 bot responses)
        assert len(spark_context.messages) == 4
        user_messages = [msg for msg in spark_context.messages if msg.role == 'user']
        bot_messages = [msg for msg in spark_context.messages if msg.role == 'assistant']
        assert len(user_messages) == 2
        assert len(bot_messages) == 2
        assert all("creative" in msg.content or "innovative" in msg.content 
                  for msg in user_messages)
        assert all(msg.bot_name == 'spark' for msg in bot_messages)
        
        # Logic should have no messages
        assert len(logic_context.messages) == 0
    
    @pytest.mark.asyncio
    async def test_ai_model_context_isolation(self, bot_services, mock_ai_model):
        """Test that AI model receives isolated context for each bot."""
        channel_id = 67890
        user_id = 12345
        
        # Add some history to sage
        sage_message1 = MockDiscordMessage("Previous sage question", channel_id=channel_id, author_id=user_id)
        await bot_services['sage'].orchestrator.process_message('sage', sage_message1, ["general"])
        
        # Add different history to spark
        spark_message1 = MockDiscordMessage("Previous spark question", channel_id=channel_id, author_id=user_id)
        await bot_services['spark'].orchestrator.process_message('spark', spark_message1, ["general"])
        
        # Clear mock call history
        mock_ai_model.generate_response.reset_mock()
        
        # Send new messages to both bots
        sage_message2 = MockDiscordMessage("New sage question", channel_id=channel_id, author_id=user_id)
        await bot_services['sage'].orchestrator.process_message('sage', sage_message2, ["general"])
        
        spark_message2 = MockDiscordMessage("New spark question", channel_id=channel_id, author_id=user_id)
        await bot_services['spark'].orchestrator.process_message('spark', spark_message2, ["general"])
        
        # Verify AI model was called twice with different contexts
        assert mock_ai_model.generate_response.call_count == 2
        
        calls = mock_ai_model.generate_response.call_args_list
        
        # Check sage call
        sage_messages = calls[0][0][0]  # First call, first argument
        sage_system = next(msg for msg in sage_messages if msg.get('role') == 'system')
        assert 'Sage' in sage_system['content']
        
        # Sage should see its own conversation history
        sage_user_messages = [msg for msg in sage_messages if msg.get('role') == 'user']
        assert any('Previous sage question' in msg['content'] for msg in sage_user_messages)
        assert not any('Previous spark question' in msg['content'] for msg in sage_user_messages)
        
        # Check spark call
        spark_messages = calls[1][0][0]  # Second call, first argument
        spark_system = next(msg for msg in spark_messages if msg.get('role') == 'system')
        assert 'Spark' in spark_system['content']
        
        # Spark should see its own conversation history
        spark_user_messages = [msg for msg in spark_messages if msg.get('role') == 'user']
        assert any('Previous spark question' in msg['content'] for msg in spark_user_messages)
        assert not any('Previous sage question' in msg['content'] for msg in spark_user_messages)


class TestBotServiceIsolation:
    """Test that bot services are properly isolated."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_ai_model(self):
        """Create a mock AI model."""
        ai_model = AsyncMock()
        ai_model.generate_response = AsyncMock(return_value="Test response")
        return ai_model
    
    def test_bot_services_have_isolated_storage_paths(self, temp_storage_path, mock_ai_model):
        """Test that each bot service has its own storage path."""
        services = {}
        
        # Create shared services
        rate_limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=10)
        notification_sender = DiscordNotificationSender(max_message_length=1900)
        
        temp_conversation_state = ConversationState(
            bot_name="coordinator",
            storage_path=temp_storage_path,
            context_depth=10,
            max_history=1000
        )
        from src.adapters import FileMessageStorage
        temp_storage = FileMessageStorage(temp_conversation_state)
        coordinator = MessageCoordinator(temp_storage, rate_limiter, {})
        
        # Create bot services
        for bot_name in ['sage', 'spark', 'logic']:
            bot_config = Config(
                bot=BotConfig(name=bot_name, description=f"{bot_name.title()} bot"),
                discord=DiscordConfig(token=f"fake_token_{bot_name}", command_prefix="!"),
                ollama=OllamaConfig(base_url="http://127.0.0.1:11434", model="llama3", timeout=60),
                system_prompt=f"You are {bot_name.title()}.",
                storage=StorageConfig(path=temp_storage_path, max_history=1000),
                message=MessageConfig(max_length=1900, typing_indicator=True),
                rate_limit=RateLimitConfig(enabled=True, max_requests_per_minute=10)
            )
            
            services[bot_name] = create_bot_services(
                bot_name=bot_name,
                bot_config=bot_config,
                shared_coordinator=coordinator,
                shared_ai_model=mock_ai_model,
                shared_rate_limiter=rate_limiter,
                shared_notification_sender=notification_sender,
                global_settings={'storage_path': temp_storage_path}
            )
        
        # Verify each service has isolated storage
        storage_paths = set()
        for bot_name, service in services.items():
            storage_path = service.conversation_state.storage_path
            storage_paths.add(storage_path)
            
            # Each bot should have its own subdirectory
            expected_path = Path(temp_storage_path) / bot_name
            assert storage_path == expected_path
        
        # All storage paths should be unique
        assert len(storage_paths) == len(services)
    
    def test_bot_services_have_isolated_system_prompts(self, temp_storage_path, mock_ai_model):
        """Test that each bot service has its own system prompt."""
        services = {}
        
        # Create shared services
        rate_limiter = MemoryRateLimiter(enabled=True, max_requests_per_minute=10)
        notification_sender = DiscordNotificationSender(max_message_length=1900)
        
        temp_conversation_state = ConversationState(
            bot_name="coordinator",
            storage_path=temp_storage_path,
            context_depth=10,
            max_history=1000
        )
        from src.adapters import FileMessageStorage
        temp_storage = FileMessageStorage(temp_conversation_state)
        coordinator = MessageCoordinator(temp_storage, rate_limiter, {})
        
        # Create bot services with different prompts
        prompts = {
            'sage': 'You are Sage, a wise mentor.',
            'spark': 'You are Spark, a creative companion.',
            'logic': 'You are Logic, an analytical thinker.'
        }
        
        for bot_name, prompt in prompts.items():
            bot_config = Config(
                bot=BotConfig(name=bot_name, description=f"{bot_name.title()} bot"),
                discord=DiscordConfig(token=f"fake_token_{bot_name}", command_prefix="!"),
                ollama=OllamaConfig(base_url="http://127.0.0.1:11434", model="llama3", timeout=60),
                system_prompt=prompt,
                storage=StorageConfig(path=temp_storage_path, max_history=1000),
                message=MessageConfig(max_length=1900, typing_indicator=True),
                rate_limit=RateLimitConfig(enabled=True, max_requests_per_minute=10)
            )
            
            services[bot_name] = create_bot_services(
                bot_name=bot_name,
                bot_config=bot_config,
                shared_coordinator=coordinator,
                shared_ai_model=mock_ai_model,
                shared_rate_limiter=rate_limiter,
                shared_notification_sender=notification_sender,
                global_settings={'storage_path': temp_storage_path}
            )
        
        # Verify each service has its own system prompt
        for bot_name, service in services.items():
            expected_prompt = prompts[bot_name]
            actual_prompt = service.response_generator.system_prompt
            assert actual_prompt == expected_prompt
            
            # Verify prompts are unique
            for other_bot, other_service in services.items():
                if other_bot != bot_name:
                    assert service.response_generator.system_prompt != other_service.response_generator.system_prompt