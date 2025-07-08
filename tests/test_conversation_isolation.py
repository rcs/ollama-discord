"""Tests for conversation state isolation between bots.

These tests ensure that each bot maintains its own isolated conversation history
and that there is no cross-bot data leakage.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from src.conversation_state import ConversationState, ConversationMessage
from src.adapters import FileMessageStorage
from src.domain_services import ResponseGenerator
from src.service_factory import create_bot_services
from src.config import Config, BotConfig, DiscordConfig, OllamaConfig, StorageConfig, MessageConfig, RateLimitConfig
from src.adapters import OllamaAI, MemoryRateLimiter, DiscordNotificationSender
from src.domain_services import MessageCoordinator


class TestConversationStateIsolation:
    """Test that conversation states are properly isolated between bots."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def bot_configs(self, temp_storage_path):
        """Create configurations for multiple bots."""
        configs = {}
        for bot_name in ['sage', 'spark', 'logic']:
            configs[bot_name] = Config(
                bot=BotConfig(name=bot_name, description=f"{bot_name.title()} bot"),
                discord=DiscordConfig(token=f"fake_token_{bot_name}", command_prefix="!"),
                ollama=OllamaConfig(base_url="http://127.0.0.1:11434", model="llama3", timeout=60),
                system_prompt=f"You are {bot_name.title()}, a helpful AI assistant.",
                storage=StorageConfig(path=temp_storage_path, max_history=1000),
                message=MessageConfig(max_length=1900, typing_indicator=True),
                rate_limit=RateLimitConfig(enabled=True, max_requests_per_minute=10)
            )
        return configs
    
    @pytest.fixture
    def conversation_states(self, temp_storage_path):
        """Create isolated conversation states for multiple bots."""
        states = {}
        for bot_name in ['sage', 'spark', 'logic']:
            states[bot_name] = ConversationState(
                bot_name=bot_name,
                storage_path=temp_storage_path,
                context_depth=10,
                max_history=100
            )
        return states
    
    def test_conversation_state_storage_paths_are_isolated(self, conversation_states, temp_storage_path):
        """Test that each bot has its own storage directory."""
        base_path = Path(temp_storage_path)
        
        for bot_name, conv_state in conversation_states.items():
            expected_path = base_path / bot_name
            assert conv_state.storage_path == expected_path
            
        # Verify all paths are different
        paths = [state.storage_path for state in conversation_states.values()]
        assert len(set(paths)) == len(paths), "All bot storage paths should be unique"
    
    @pytest.mark.asyncio
    async def test_conversation_messages_are_isolated(self, conversation_states):
        """Test that messages added to one bot don't appear in another bot's context."""
        channel_id = 12345
        user_id = 67890
        
        # Add message to sage bot
        sage_state = conversation_states['sage']
        await sage_state.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Hello sage!',
            metadata={'username': 'testuser'}
        )
        
        # Add different message to spark bot
        spark_state = conversation_states['spark']
        await spark_state.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Hello spark!',
            metadata={'username': 'testuser'}
        )
        
        # Get contexts for both bots
        sage_context = await sage_state.get_context(channel_id, user_id)
        spark_context = await spark_state.get_context(channel_id, user_id)
        
        # Verify isolation
        assert len(sage_context.messages) == 1
        assert len(spark_context.messages) == 1
        assert sage_context.messages[0].content == 'Hello sage!'
        assert spark_context.messages[0].content == 'Hello spark!'
        
        # Verify no cross-contamination
        assert 'spark' not in sage_context.messages[0].content
        assert 'sage' not in spark_context.messages[0].content
    
    @pytest.mark.asyncio
    async def test_bot_response_isolation(self, conversation_states):
        """Test that bot responses are stored only in the responding bot's context."""
        channel_id = 12345
        user_id = 67890
        
        # Add user message to all bots
        for bot_name, conv_state in conversation_states.items():
            await conv_state.add_message(
                channel_id=channel_id,
                user_id=user_id,
                role='user',
                content='What is your name?',
                metadata={'username': 'testuser'}
            )
        
        # Add bot responses only to specific bots
        sage_state = conversation_states['sage']
        await sage_state.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='I am Sage, your wise mentor.',
            bot_name='sage',
            metadata={'response_to_message_id': 123}
        )
        
        spark_state = conversation_states['spark']
        await spark_state.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='I am Spark, your creative companion.',
            bot_name='spark',
            metadata={'response_to_message_id': 123}
        )
        
        # Verify each bot only sees its own response
        sage_context = await sage_state.get_context(channel_id, user_id)
        spark_context = await spark_state.get_context(channel_id, user_id)
        logic_context = await conversation_states['logic'].get_context(channel_id, user_id)
        
        # Sage should see user message + sage response
        assert len(sage_context.messages) == 2
        assert sage_context.messages[1].content == 'I am Sage, your wise mentor.'
        assert sage_context.messages[1].bot_name == 'sage'
        
        # Spark should see user message + spark response
        assert len(spark_context.messages) == 2
        assert spark_context.messages[1].content == 'I am Spark, your creative companion.'
        assert spark_context.messages[1].bot_name == 'spark'
        
        # Logic should only see user message (no response)
        assert len(logic_context.messages) == 1
        assert logic_context.messages[0].role == 'user'
    
    def test_conversation_file_isolation(self, conversation_states, temp_storage_path):
        """Test that conversation files are stored in separate directories."""
        channel_id = 12345
        user_id = 67890
        
        # Get storage file paths for each bot using private method
        storage_files = {}
        for bot_name, conv_state in conversation_states.items():
            conversation_key = conv_state._get_conversation_key(channel_id, user_id)
            storage_files[bot_name] = conv_state._get_storage_file(conversation_key)
        
        # Verify all files are in different directories
        for bot_name, file_path in storage_files.items():
            expected_dir = Path(temp_storage_path) / bot_name
            assert file_path.parent == expected_dir
            
        # Verify all file paths are unique
        file_paths = list(storage_files.values())
        assert len(set(file_paths)) == len(file_paths), "All storage files should be unique"
    
    @pytest.mark.asyncio
    async def test_conversation_persistence_isolation(self, conversation_states, temp_storage_path):
        """Test that saved conversations don't interfere with each other."""
        import asyncio
        
        channel_id = 12345
        user_id = 67890
        
        # Add different messages to each bot and verify they're saved
        for i, (bot_name, conv_state) in enumerate(conversation_states.items()):
            await conv_state.add_message(
                channel_id=channel_id,
                user_id=user_id,
                role='user',
                content=f'Message for {bot_name} - {i}',
                metadata={'username': 'testuser'}
            )
            
            # Verify the message was added to this bot's context
            context = await conv_state.get_context(channel_id, user_id)
            assert len(context.messages) == 1
            assert context.messages[0].content == f'Message for {bot_name} - {i}'
        
        # Wait a bit for async save tasks to complete
        await asyncio.sleep(0.1)
        
        # Verify that each bot's storage directory exists and contains files
        for bot_name in ['sage', 'spark', 'logic']:
            bot_dir = Path(temp_storage_path) / bot_name
            assert bot_dir.exists(), f"Storage directory for {bot_name} should exist"
            
            # Check that conversation files exist
            conversation_files = list(bot_dir.glob("*.json"))
            assert len(conversation_files) > 0, f"Bot {bot_name} should have conversation files"


class TestFileMessageStorageIsolation:
    """Test that FileMessageStorage properly isolates data between bots."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def storage_instances(self, temp_storage_path):
        """Create isolated storage instances for multiple bots."""
        storages = {}
        for bot_name in ['sage', 'spark', 'logic']:
            conv_state = ConversationState(
                bot_name=bot_name,
                storage_path=temp_storage_path,
                context_depth=10,
                max_history=100
            )
            storages[bot_name] = FileMessageStorage(conv_state)
        return storages
    
    @pytest.mark.asyncio
    async def test_add_message_isolation(self, storage_instances):
        """Test that messages added to one storage don't appear in others."""
        channel_id = 12345
        user_id = 67890
        
        # Add different messages to each storage
        for bot_name, storage in storage_instances.items():
            await storage.add_message(
                channel_id=channel_id,
                user_id=user_id,
                role='user',
                content=f'Hello {bot_name}!',
                metadata={'username': 'testuser'}
            )
        
        # Verify each storage only contains its own message
        for bot_name, storage in storage_instances.items():
            context = await storage.get_context(channel_id, user_id)
            assert len(context.messages) == 1
            assert context.messages[0].content == f'Hello {bot_name}!'
    
    @pytest.mark.asyncio
    async def test_get_context_isolation(self, storage_instances):
        """Test that get_context returns isolated data for each bot."""
        channel_id = 12345
        user_id = 67890
        
        # Add messages and responses to each bot
        for bot_name, storage in storage_instances.items():
            # User message
            await storage.add_message(
                channel_id=channel_id,
                user_id=user_id,
                role='user',
                content='What can you do?',
                metadata={'username': 'testuser'}
            )
            
            # Bot response
            await storage.add_message(
                channel_id=channel_id,
                user_id=user_id,
                role='assistant',
                content=f'I am {bot_name}, I can help you with {bot_name}-specific tasks.',
                bot_name=bot_name,
                metadata={'response_to_message_id': 123}
            )
        
        # Verify each storage returns only its own conversation
        for bot_name, storage in storage_instances.items():
            context = await storage.get_context(channel_id, user_id)
            assert len(context.messages) == 2
            
            # Check user message
            assert context.messages[0].role == 'user'
            assert context.messages[0].content == 'What can you do?'
            
            # Check bot response
            assert context.messages[1].role == 'assistant'
            assert context.messages[1].bot_name == bot_name
            assert bot_name in context.messages[1].content
            
            # Verify no other bot names appear in the content
            other_bots = [name for name in ['sage', 'spark', 'logic'] if name != bot_name]
            for other_bot in other_bots:
                assert other_bot not in context.messages[1].content


class TestResponseGeneratorIsolation:
    """Test that ResponseGenerator uses isolated system prompts and storage."""
    
    @pytest.fixture
    def mock_ai_model(self):
        """Create a mock AI model."""
        ai_model = AsyncMock()
        ai_model.generate_response = AsyncMock(return_value="Test response")
        return ai_model
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def response_generators(self, mock_ai_model, temp_storage_path):
        """Create isolated response generators for multiple bots."""
        generators = {}
        for bot_name in ['sage', 'spark', 'logic']:
            # Create isolated storage
            conv_state = ConversationState(
                bot_name=bot_name,
                storage_path=temp_storage_path,
                context_depth=10,
                max_history=100
            )
            storage = FileMessageStorage(conv_state)
            
            # Create response generator with bot-specific prompt
            generators[bot_name] = ResponseGenerator(
                ai_model=mock_ai_model,
                storage=storage,
                system_prompt=f"You are {bot_name.title()}, a {bot_name}-specific AI assistant.",
                bot_name=bot_name
            )
        return generators
    
    @pytest.mark.asyncio
    async def test_system_prompt_isolation(self, response_generators, mock_ai_model):
        """Test that each bot uses its own system prompt."""
        channel_id = 12345
        user_id = 67890
        message = "Hello!"
        
        # Generate responses for each bot
        for bot_name, generator in response_generators.items():
            await generator.generate_response(bot_name, message, channel_id, user_id)
        
        # Verify each call used the correct system prompt
        assert mock_ai_model.generate_response.call_count == 3
        
        calls = mock_ai_model.generate_response.call_args_list
        for i, (bot_name, generator) in enumerate(response_generators.items()):
            messages = calls[i][0][0]  # First argument of the call
            
            # Find system message
            system_messages = [msg for msg in messages if msg.get('role') == 'system']
            assert len(system_messages) == 1
            
            system_content = system_messages[0]['content']
            assert bot_name.title() in system_content
            assert f"{bot_name}-specific" in system_content
    
    @pytest.mark.asyncio
    async def test_storage_isolation_in_response_generation(self, response_generators):
        """Test that response generation uses isolated storage for each bot."""
        channel_id = 12345
        user_id = 67890
        
        # Add different conversation history to each bot
        for bot_name, generator in response_generators.items():
            await generator.storage.add_message(
                channel_id=channel_id,
                user_id=user_id,
                role='user',
                content=f'Previous message to {bot_name}',
                metadata={'username': 'testuser'}
            )
        
        # Generate responses
        for bot_name, generator in response_generators.items():
            await generator.generate_response(bot_name, "New message", channel_id, user_id)
        
        # Verify each bot only sees its own conversation history
        for bot_name, generator in response_generators.items():
            context = await generator.storage.get_context(channel_id, user_id)
            
            # Should have: previous message + new message (response generation adds the new message)
            user_messages = [msg for msg in context.messages if msg.role == 'user']
            assert len(user_messages) >= 1
            
            # Check that the previous message is bot-specific
            previous_msg = next(msg for msg in user_messages if 'Previous message' in msg.content)
            assert f'to {bot_name}' in previous_msg.content