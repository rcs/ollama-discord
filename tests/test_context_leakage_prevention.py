"""Tests to prevent context leakage between bots.

These tests specifically verify that information from one bot's conversation
cannot leak into another bot's context, ensuring complete isolation.
"""

import pytest
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from src.conversation_state import ConversationState
from src.adapters import FileMessageStorage
from src.domain_services import ResponseGenerator
from src.service_factory import create_bot_services
from src.config import Config, BotConfig, DiscordConfig, OllamaConfig, StorageConfig, MessageConfig, RateLimitConfig
from src.adapters import OllamaAI, MemoryRateLimiter, DiscordNotificationSender
from src.domain_services import MessageCoordinator


class TestContextLeakagePrevention:
    """Test that context information cannot leak between bots."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def isolated_conversation_states(self, temp_storage_path):
        """Create isolated conversation states for testing leakage."""
        states = {}
        for bot_name in ['bot_a', 'bot_b', 'bot_c']:
            states[bot_name] = ConversationState(
                bot_name=bot_name,
                storage_path=temp_storage_path,
                context_depth=10,
                max_history=100
            )
        return states
    
    @pytest.mark.asyncio
    async def test_message_content_isolation(self, isolated_conversation_states):
        """Test that message content from one bot doesn't appear in another's context."""
        channel_id = 12345
        user_id = 67890
        
        # Add sensitive information to bot_a
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='My password is secret123',
            metadata={'username': 'testuser'}
        )
        
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='I understand you shared sensitive information with me.',
            bot_name='bot_a',
            metadata={'response_to_message_id': 123}
        )
        
        # Add different information to bot_b
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='What is the weather like?',
            metadata={'username': 'testuser'}
        )
        
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='I can help you with weather information.',
            bot_name='bot_b',
            metadata={'response_to_message_id': 124}
        )
        
        # Verify bot_b cannot see bot_a's sensitive information
        bot_b_context = await isolated_conversation_states['bot_b'].get_context(channel_id, user_id)
        
        for message in bot_b_context.messages:
            assert 'password' not in message.content.lower()
            assert 'secret123' not in message.content
            assert 'sensitive information' not in message.content.lower()
        
        # Verify bot_a cannot see bot_b's information
        bot_a_context = await isolated_conversation_states['bot_a'].get_context(channel_id, user_id)
        
        for message in bot_a_context.messages:
            assert 'weather' not in message.content.lower()
        
        # Verify bot_c has no information from either bot
        bot_c_context = await isolated_conversation_states['bot_c'].get_context(channel_id, user_id)
        assert len(bot_c_context.messages) == 0
    
    @pytest.mark.asyncio
    async def test_metadata_isolation(self, isolated_conversation_states):
        """Test that message metadata doesn't leak between bots."""
        channel_id = 12345
        user_id = 67890
        
        # Add message with sensitive metadata to bot_a
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Hello',
            metadata={
                'username': 'testuser',
                'user_email': 'user@example.com',
                'session_token': 'abc123xyz',
                'ip_address': '192.168.1.100'
            }
        )
        
        # Add message with different metadata to bot_b
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Hi there',
            metadata={
                'username': 'testuser',
                'location': 'New York',
                'device': 'mobile'
            }
        )
        
        # Verify bot_b cannot see bot_a's sensitive metadata
        bot_b_context = await isolated_conversation_states['bot_b'].get_context(channel_id, user_id)
        
        for message in bot_b_context.messages:
            assert 'user_email' not in message.metadata
            assert 'session_token' not in message.metadata
            assert 'ip_address' not in message.metadata
            assert 'user@example.com' not in str(message.metadata)
            assert 'abc123xyz' not in str(message.metadata)
            assert '192.168.1.100' not in str(message.metadata)
        
        # Verify bot_a cannot see bot_b's metadata
        bot_a_context = await isolated_conversation_states['bot_a'].get_context(channel_id, user_id)
        
        for message in bot_a_context.messages:
            assert 'location' not in message.metadata
            assert 'device' not in message.metadata
            assert 'New York' not in str(message.metadata)
            assert 'mobile' not in str(message.metadata)
    
    @pytest.mark.asyncio
    async def test_bot_name_isolation(self, isolated_conversation_states):
        """Test that bot names in messages don't leak between contexts."""
        channel_id = 12345
        user_id = 67890
        
        # Add bot responses from different bots
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='Response from bot_a',
            bot_name='bot_a',
            metadata={'response_to_message_id': 123}
        )
        
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='Response from bot_b',
            bot_name='bot_b',
            metadata={'response_to_message_id': 124}
        )
        
        # Verify each bot only sees its own bot_name in messages
        bot_a_context = await isolated_conversation_states['bot_a'].get_context(channel_id, user_id)
        for message in bot_a_context.messages:
            if message.bot_name:
                assert message.bot_name == 'bot_a'
                assert message.bot_name != 'bot_b'
                assert message.bot_name != 'bot_c'
        
        bot_b_context = await isolated_conversation_states['bot_b'].get_context(channel_id, user_id)
        for message in bot_b_context.messages:
            if message.bot_name:
                assert message.bot_name == 'bot_b'
                assert message.bot_name != 'bot_a'
                assert message.bot_name != 'bot_c'
    
    @pytest.mark.asyncio
    async def test_conversation_participant_isolation(self, isolated_conversation_states):
        """Test that conversation participants don't leak between bots."""
        channel_id = 12345
        user_id = 67890
        
        # Add messages that would add participants to different bots
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='Bot A response',
            bot_name='bot_a',
            metadata={'response_to_message_id': 123}
        )
        
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='assistant',
            content='Bot B response',
            bot_name='bot_b',
            metadata={'response_to_message_id': 124}
        )
        
        # Verify participants are isolated
        bot_a_context = await isolated_conversation_states['bot_a'].get_context(channel_id, user_id)
        bot_b_context = await isolated_conversation_states['bot_b'].get_context(channel_id, user_id)
        bot_c_context = await isolated_conversation_states['bot_c'].get_context(channel_id, user_id)
        
        # Bot A should only have bot_a as participant
        assert 'bot_a' in bot_a_context.participants
        assert 'bot_b' not in bot_a_context.participants
        assert 'bot_c' not in bot_a_context.participants
        
        # Bot B should only have bot_b as participant
        assert 'bot_b' in bot_b_context.participants
        assert 'bot_a' not in bot_b_context.participants
        assert 'bot_c' not in bot_b_context.participants
        
        # Bot C should have no participants
        assert len(bot_c_context.participants) == 0
    
    @pytest.mark.asyncio
    async def test_file_storage_isolation(self, isolated_conversation_states, temp_storage_path):
        """Test that conversation files are completely isolated."""
        channel_id = 12345
        user_id = 67890
        
        # Add messages to different bots
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Secret message for bot A',
            metadata={'username': 'testuser'}
        )
        
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Different message for bot B',
            metadata={'username': 'testuser'}
        )
        
        # Wait for async saves to complete
        await asyncio.sleep(0.1)
        
        # Verify files are in separate directories
        bot_a_dir = Path(temp_storage_path) / 'bot_a'
        bot_b_dir = Path(temp_storage_path) / 'bot_b'
        bot_c_dir = Path(temp_storage_path) / 'bot_c'
        
        assert bot_a_dir.exists()
        assert bot_b_dir.exists()
        # bot_c_dir might not exist if no messages were added
        
        # Verify bot_a files don't contain bot_b information
        if bot_a_dir.exists():
            for file_path in bot_a_dir.glob('*.json'):
                content = file_path.read_text()
                assert 'Different message for bot B' not in content
                assert 'bot_b' not in content
        
        # Verify bot_b files don't contain bot_a information
        if bot_b_dir.exists():
            for file_path in bot_b_dir.glob('*.json'):
                content = file_path.read_text()
                assert 'Secret message for bot A' not in content
                assert 'bot_a' not in content
    
    @pytest.mark.asyncio
    async def test_cross_channel_isolation(self, isolated_conversation_states):
        """Test that conversations in different channels are isolated per bot."""
        user_id = 67890
        channel1_id = 11111
        channel2_id = 22222
        
        # Add messages to bot_a in different channels
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel1_id,
            user_id=user_id,
            role='user',
            content='Message in channel 1',
            metadata={'username': 'testuser'}
        )
        
        await isolated_conversation_states['bot_a'].add_message(
            channel_id=channel2_id,
            user_id=user_id,
            role='user',
            content='Message in channel 2',
            metadata={'username': 'testuser'}
        )
        
        # Add messages to bot_b in the same channels
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel1_id,
            user_id=user_id,
            role='user',
            content='Bot B in channel 1',
            metadata={'username': 'testuser'}
        )
        
        await isolated_conversation_states['bot_b'].add_message(
            channel_id=channel2_id,
            user_id=user_id,
            role='user',
            content='Bot B in channel 2',
            metadata={'username': 'testuser'}
        )
        
        # Verify bot_a contexts are isolated by channel and don't contain bot_b info
        bot_a_ch1_context = await isolated_conversation_states['bot_a'].get_context(channel1_id, user_id)
        bot_a_ch2_context = await isolated_conversation_states['bot_a'].get_context(channel2_id, user_id)
        
        # Bot A channel 1 should only have its own message
        assert len(bot_a_ch1_context.messages) == 1
        assert 'Message in channel 1' in bot_a_ch1_context.messages[0].content
        assert 'Bot B' not in bot_a_ch1_context.messages[0].content
        assert 'channel 2' not in bot_a_ch1_context.messages[0].content
        
        # Bot A channel 2 should only have its own message
        assert len(bot_a_ch2_context.messages) == 1
        assert 'Message in channel 2' in bot_a_ch2_context.messages[0].content
        assert 'Bot B' not in bot_a_ch2_context.messages[0].content
        assert 'channel 1' not in bot_a_ch2_context.messages[0].content
        
        # Verify bot_b contexts are isolated and don't contain bot_a info
        bot_b_ch1_context = await isolated_conversation_states['bot_b'].get_context(channel1_id, user_id)
        bot_b_ch2_context = await isolated_conversation_states['bot_b'].get_context(channel2_id, user_id)
        
        # Bot B channel 1 should only have its own message
        assert len(bot_b_ch1_context.messages) == 1
        assert 'Bot B in channel 1' in bot_b_ch1_context.messages[0].content
        assert 'Message in channel' not in bot_b_ch1_context.messages[0].content
        
        # Bot B channel 2 should only have its own message
        assert len(bot_b_ch2_context.messages) == 1
        assert 'Bot B in channel 2' in bot_b_ch2_context.messages[0].content
        assert 'Message in channel' not in bot_b_ch2_context.messages[0].content


class TestResponseGeneratorLeakagePrevention:
    """Test that ResponseGenerator doesn't leak context between bots."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_ai_model(self):
        """Create a mock AI model that captures the messages sent to it."""
        ai_model = AsyncMock()
        ai_model.generate_response = AsyncMock(return_value="Test response")
        return ai_model
    
    @pytest.fixture
    def isolated_response_generators(self, temp_storage_path, mock_ai_model):
        """Create isolated response generators for testing."""
        generators = {}
        
        for bot_name in ['secure_bot', 'public_bot']:
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
                system_prompt=f"You are {bot_name}, a specialized assistant.",
                bot_name=bot_name
            )
        
        return generators
    
    @pytest.mark.asyncio
    async def test_system_prompt_isolation(self, isolated_response_generators, mock_ai_model):
        """Test that system prompts don't leak between response generators."""
        channel_id = 12345
        user_id = 67890
        
        # Generate responses with different bots
        await isolated_response_generators['secure_bot'].generate_response(
            'secure_bot', 'Hello', channel_id, user_id
        )
        
        await isolated_response_generators['public_bot'].generate_response(
            'public_bot', 'Hello', channel_id, user_id
        )
        
        # Verify each call used the correct isolated system prompt
        assert mock_ai_model.generate_response.call_count == 2
        
        calls = mock_ai_model.generate_response.call_args_list
        
        # Check secure_bot call
        secure_messages = calls[0][0][0]
        secure_system = next(msg for msg in secure_messages if msg.get('role') == 'system')
        assert 'secure_bot' in secure_system['content']
        assert 'public_bot' not in secure_system['content']
        
        # Check public_bot call
        public_messages = calls[1][0][0]
        public_system = next(msg for msg in public_messages if msg.get('role') == 'system')
        assert 'public_bot' in public_system['content']
        assert 'secure_bot' not in public_system['content']
    
    @pytest.mark.asyncio
    async def test_conversation_history_isolation(self, isolated_response_generators, mock_ai_model):
        """Test that conversation history doesn't leak between response generators."""
        channel_id = 12345
        user_id = 67890
        
        # Add sensitive conversation to secure_bot
        await isolated_response_generators['secure_bot'].storage.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='My credit card number is 1234-5678-9012-3456',
            metadata={'username': 'testuser'}
        )
        
        # Add public conversation to public_bot
        await isolated_response_generators['public_bot'].storage.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='What is the weather today?',
            metadata={'username': 'testuser'}
        )
        
        # Clear mock history
        mock_ai_model.generate_response.reset_mock()
        
        # Generate new responses
        await isolated_response_generators['secure_bot'].generate_response(
            'secure_bot', 'Can you help me?', channel_id, user_id
        )
        
        await isolated_response_generators['public_bot'].generate_response(
            'public_bot', 'Tell me more', channel_id, user_id
        )
        
        # Verify secure information doesn't leak to public bot
        calls = mock_ai_model.generate_response.call_args_list
        
        # Check secure_bot call - should see credit card info
        secure_messages = calls[0][0][0]
        secure_content = ' '.join(msg.get('content', '') for msg in secure_messages)
        assert '1234-5678-9012-3456' in secure_content
        assert 'weather' not in secure_content
        
        # Check public_bot call - should NOT see credit card info
        public_messages = calls[1][0][0]
        public_content = ' '.join(msg.get('content', '') for msg in public_messages)
        assert '1234-5678-9012-3456' not in public_content
        assert 'weather' in public_content
    
    @pytest.mark.asyncio
    async def test_storage_isolation_in_generators(self, isolated_response_generators):
        """Test that storage is completely isolated between response generators."""
        channel_id = 12345
        user_id = 67890
        
        # Add messages to both generators
        await isolated_response_generators['secure_bot'].storage.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Confidential information',
            metadata={'classification': 'secret'}
        )
        
        await isolated_response_generators['public_bot'].storage.add_message(
            channel_id=channel_id,
            user_id=user_id,
            role='user',
            content='Public information',
            metadata={'classification': 'public'}
        )
        
        # Verify each generator only sees its own storage
        secure_context = await isolated_response_generators['secure_bot'].storage.get_context(channel_id, user_id)
        public_context = await isolated_response_generators['public_bot'].storage.get_context(channel_id, user_id)
        
        # Secure bot should only see confidential info
        assert len(secure_context.messages) == 1
        assert 'Confidential information' in secure_context.messages[0].content
        assert 'Public information' not in secure_context.messages[0].content
        assert secure_context.messages[0].metadata['classification'] == 'secret'
        
        # Public bot should only see public info
        assert len(public_context.messages) == 1
        assert 'Public information' in public_context.messages[0].content
        assert 'Confidential information' not in public_context.messages[0].content
        assert public_context.messages[0].metadata['classification'] == 'public'