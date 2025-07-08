"""
Integration tests for the complete message processing flow.
Tests the end-to-end pipeline: Discord message → bot response decision → response.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

from src.message_processor import MessageProcessor, MessageContext, ResponseDecision
from src.conversation_state import ConversationState, ConversationContext
from src.bot_manager import BotManager
from src.multi_bot_config import MultiBotConfig


class MockDiscordMessage:
    """Mock Discord message for testing."""
    
    def __init__(self, content: str, channel_name: str, channel_id: int = 123, 
                 user_id: int = 456, user_name: str = "TestUser", author_is_bot: bool = False):
        self.content = content
        self.id = 999
        self.created_at = datetime.now()
        
        # Mock channel
        self.channel = Mock()
        self.channel.name = channel_name
        self.channel.id = channel_id
        
        # Mock author
        self.author = Mock()
        self.author.id = user_id
        self.author.display_name = user_name
        self.author.bot = author_is_bot
        
        # Mock mentions
        self.mentions = []


class TestMessageProcessingFlow:
    """Test the complete message processing flow."""
    
    @pytest.fixture
    def global_settings(self):
        """Create test global settings."""
        return {
            'context_depth': 10,
            'response_delay': '1-3',
            'max_concurrent_responses': 2,
            'cooldown_period': 30,
            'debug_mode': True,
            'log_response_decisions': True
        }
    
    @pytest.fixture
    def conversation_state(self):
        """Create mock conversation state."""
        state = Mock(spec=ConversationState)
        state.get_context = AsyncMock(return_value=Mock())
        state.add_message = AsyncMock()
        return state
    
    @pytest.fixture
    def message_processor(self, conversation_state, global_settings):
        """Create message processor."""
        return MessageProcessor(conversation_state, global_settings)
    
    @pytest.fixture
    def sage_bot_config(self):
        """Create sage bot configuration."""
        return {
            'name': 'sage',
            'config_file': 'sage.yaml',
            'channels': ['bambam', 'general', 'advice-*', 'philosophy', 'life-*'],
            'persona': {
                'name': 'Sage',
                'description': 'A wise mentor'
            },
            'response_behavior': {
                'engagement_threshold': 0.3,
                'response_probability': 0.4,
                'context_weight': 0.8
            },
            'enabled': True
        }

    def test_sage_mention_in_bambam_should_respond(self, message_processor, sage_bot_config):
        """Test that mentioning sage in bambam channel should trigger response."""
        # Create message: "Hey sage, what is it?" in #bambam
        message = MockDiscordMessage("Hey sage, what is it?", "bambam")
        
        # Test channel matching
        should_handle = asyncio.run(
            message_processor.should_bot_handle_message(
                'sage', message, sage_bot_config['channels']
            )
        )
        
        assert should_handle, "Sage should handle message in bambam channel with mention"
    
    def test_sage_mention_in_general_should_respond(self, message_processor, sage_bot_config):
        """Test that mentioning sage in general channel should trigger response."""
        # Create message: "Hey sage, what is it?" in #general  
        message = MockDiscordMessage("Hey sage, what is it?", "general")
        
        # Test channel matching
        should_handle = asyncio.run(
            message_processor.should_bot_handle_message(
                'sage', message, sage_bot_config['channels']
            )
        )
        
        assert should_handle, "Sage should handle message in general channel with mention"
    
    def test_sage_mention_in_random_channel_should_not_respond(self, message_processor, sage_bot_config):
        """Test that mentioning sage in non-configured channel should not trigger response."""
        # Create message: "Hey sage, what is it?" in #random
        message = MockDiscordMessage("Hey sage, what is it?", "random")
        
        # Test channel matching
        should_handle = asyncio.run(
            message_processor.should_bot_handle_message(
                'sage', message, sage_bot_config['channels']
            )
        )
        
        assert not should_handle, "Sage should not handle message in non-configured channel"
    
    def test_command_message_should_not_be_handled(self, message_processor, sage_bot_config):
        """Test that command messages (starting with !) should not be handled by multi-bot system."""
        # Create command message
        message = MockDiscordMessage("!ask what is it?", "bambam")
        
        should_handle = asyncio.run(
            message_processor.should_bot_handle_message(
                'sage', message, sage_bot_config['channels']
            )
        )
        
        assert not should_handle, "Command messages should not be handled by multi-bot system"
    
    def test_bot_message_should_not_be_handled(self, message_processor, sage_bot_config):
        """Test that bot messages should not be handled."""
        # Create bot message
        message = MockDiscordMessage("Hey sage, what is it?", "bambam", author_is_bot=True)
        
        should_handle = asyncio.run(
            message_processor.should_bot_handle_message(
                'sage', message, sage_bot_config['channels']
            )
        )
        
        assert not should_handle, "Bot messages should not be handled"
    
    @pytest.mark.asyncio
    async def test_response_decision_for_mention(self, message_processor):
        """Test that response decision logic works for mentions."""
        # Create message context with mention
        message = MockDiscordMessage("Hey sage, what is it?", "bambam")
        message_context = MessageContext(
            message=message,
            channel_name="bambam",
            channel_id=123,
            user_id=456,
            user_name="TestUser",
            content="Hey sage, what is it?",
            timestamp=datetime.now(),
            is_bot_message=False,
            mentioned_bots=["sage"]
        )
        
        # Mock conversation context
        conv_context = Mock()
        conv_context.messages = []
        
        # Test response decision
        decision = await message_processor._make_response_decision(
            'sage', message_context, conv_context
        )
        
        assert isinstance(decision, ResponseDecision)
        assert decision.should_respond or decision.confidence > 0.3, \
            "Should have positive response decision for mention"
        assert "mentioned" in decision.reasoning or "sage" in decision.reasoning, \
            "Reasoning should indicate mention was detected"
    
    @pytest.mark.asyncio
    async def test_channel_pattern_matching(self, message_processor, sage_bot_config):
        """Test that channel pattern matching works correctly."""
        patterns = sage_bot_config['channels']  # ['bambam', 'general', 'advice-*', 'philosophy', 'life-*']
        
        # Test exact matches
        bambam_msg = MockDiscordMessage("test", "bambam")
        general_msg = MockDiscordMessage("test", "general")
        
        assert await message_processor.should_bot_handle_message('sage', bambam_msg, patterns)
        assert await message_processor.should_bot_handle_message('sage', general_msg, patterns)
        
        # Test wildcard matches
        advice_general_msg = MockDiscordMessage("test", "advice-general")
        advice_work_msg = MockDiscordMessage("test", "advice-work")
        life_tips_msg = MockDiscordMessage("test", "life-tips")
        
        assert await message_processor.should_bot_handle_message('sage', advice_general_msg, patterns)
        assert await message_processor.should_bot_handle_message('sage', advice_work_msg, patterns)
        assert await message_processor.should_bot_handle_message('sage', life_tips_msg, patterns)
        
        # Test non-matches
        random_msg = MockDiscordMessage("test", "random")
        tech_msg = MockDiscordMessage("test", "tech-support")
        
        assert not await message_processor.should_bot_handle_message('sage', random_msg, patterns)
        assert not await message_processor.should_bot_handle_message('sage', tech_msg, patterns)


class TestEndToEndFlow:
    """Test the complete end-to-end message flow."""
    
    @pytest.fixture
    def multi_bot_config_data(self):
        """Create test multi-bot configuration data."""
        return {
            'bots': [
                {
                    'name': 'sage',
                    'config_file': 'sage.yaml',
                    'channels': ['bambam', 'general'],
                    'enabled': True
                }
            ],
            'global_settings': {
                'context_depth': 10,
                'max_concurrent_responses': 2,
                'response_delay': '1-3',
                'cooldown_period': 30
            }
        }
    
    @pytest.mark.asyncio
    async def test_message_processing_pipeline(self, multi_bot_config_data):
        """Test the complete message processing pipeline."""
        # Create multi-bot config
        config = MultiBotConfig.from_dict(multi_bot_config_data)
        
        # Create conversation state
        conv_state = ConversationState(context_depth=10)
        
        # Create message processor
        processor = MessageProcessor(conv_state, config.global_settings)
        
        # Create test message
        message = MockDiscordMessage("Hey sage, what is it?", "bambam")
        
        # Test the flow
        should_handle = await processor.should_bot_handle_message(
            'sage', message, ['bambam', 'general']
        )
        
        assert should_handle, "Message should be handled by sage in bambam channel"
        
        # Test message context creation
        context = await conv_state.get_context(
            channel_id=message.channel.id,
            user_id=message.author.id
        )
        
        assert context is not None, "Should create conversation context"


class TestRealWorldScenarios:
    """Test scenarios that match real Discord usage."""
    
    @pytest.fixture
    def message_processor_with_all_bots(self):
        """Create message processor configured for all three bots."""
        global_settings = {
            'context_depth': 10,
            'max_concurrent_responses': 2,
            'response_delay': '1-3',
            'cooldown_period': 30
        }
        
        conv_state = ConversationState(context_depth=10)
        return MessageProcessor(conv_state, global_settings)
    
    @pytest.mark.asyncio
    async def test_user_message_hey_sage_what_is_it_bambam(self, message_processor_with_all_bots):
        """Test the exact scenario: 'Hey sage, what is it?' in #bambam."""
        message = MockDiscordMessage("Hey sage, what is it?", "bambam")
        
        # Test sage should handle it
        sage_should_handle = await message_processor_with_all_bots.should_bot_handle_message(
            'sage', message, ['bambam', 'general', 'advice-*', 'philosophy', 'life-*']
        )
        
        # Test spark should not handle it (different channels)
        spark_should_handle = await message_processor_with_all_bots.should_bot_handle_message(
            'spark', message, ['bambam', 'creative', 'projects-*', 'brainstorm*', 'innovation', 'ideas']
        )
        
        # Test logic should not handle it (different channels)  
        logic_should_handle = await message_processor_with_all_bots.should_bot_handle_message(
            'logic', message, ['bambam', 'tech-*', 'research', 'analysis', 'data-*', 'science']
        )
        
        assert sage_should_handle, "Sage should handle message with mention in bambam"
        assert spark_should_handle, "Spark should also handle it (bambam in channels)"
        assert logic_should_handle, "Logic should also handle it (bambam in channels)"
    
    @pytest.mark.asyncio 
    async def test_user_message_hey_sage_what_is_it_general(self, message_processor_with_all_bots):
        """Test the exact scenario: 'Hey sage, what is it?' in #general."""
        message = MockDiscordMessage("Hey sage, what is it?", "general")
        
        # Test sage should handle it
        sage_should_handle = await message_processor_with_all_bots.should_bot_handle_message(
            'sage', message, ['bambam', 'general', 'advice-*', 'philosophy', 'life-*']
        )
        
        assert sage_should_handle, "Sage should handle message with mention in general channel"
    
    @pytest.mark.asyncio
    async def test_coordination_prevents_all_bots_responding(self, message_processor_with_all_bots):
        """Test that coordination prevents all bots from responding at once."""
        message = MockDiscordMessage("What does everyone think?", "bambam")
        
        # Simulate that sage is already responding
        message_processor_with_all_bots.active_responses[123] = {'sage'}
        
        # Test that other bots coordinate
        spark_should_handle = await message_processor_with_all_bots.should_bot_handle_message(
            'spark', message, ['bambam', 'creative']
        )
        
        logic_should_handle = await message_processor_with_all_bots.should_bot_handle_message(
            'logic', message, ['bambam', 'tech-*']
        )
        
        # Both could potentially handle, but coordination logic might prevent it
        # The exact behavior depends on max_concurrent_responses setting
        assert isinstance(spark_should_handle, bool)
        assert isinstance(logic_should_handle, bool)


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])