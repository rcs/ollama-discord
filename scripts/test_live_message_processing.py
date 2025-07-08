#!/usr/bin/env python3
"""
Debug script to test live message processing without Discord.
Simulates the exact message processing flow that should happen in Discord.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.message_processor import MessageProcessor, MessageContext
from src.conversation_state import ConversationState
from src.multi_bot_config import multi_bot_config_manager


class MockDiscordMessage:
    """Mock Discord message that matches the real Discord.py interface."""
    
    def __init__(self, content: str, channel_name: str, channel_id: int = 123, 
                 user_id: int = 456, user_name: str = "TestUser"):
        self.content = content
        self.id = 999
        self.created_at = datetime.now()
        
        # Mock channel
        class MockChannel:
            def __init__(self, name, id):
                self.name = name
                self.id = id
        
        self.channel = MockChannel(channel_name, channel_id)
        
        # Mock author
        class MockAuthor:
            def __init__(self, id, display_name):
                self.id = id
                self.display_name = display_name
                self.bot = False
        
        self.author = MockAuthor(user_id, user_name)
        self.mentions = []


async def test_message_processing():
    """Test the complete message processing pipeline."""
    print("🧪 Testing Live Message Processing Pipeline")
    print("=" * 50)
    
    # Load actual multi-bot configuration
    config_path = Path(__file__).parent.parent / "config" / "multi_bot.yaml"
    print(f"📁 Loading config from: {config_path}")
    
    try:
        multi_bot_config = multi_bot_config_manager.load_multi_bot_config(str(config_path))
        print(f"✅ Loaded config with {len(multi_bot_config.bots)} bots")
        print(f"🔧 Global settings: {multi_bot_config.global_settings}")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Initialize conversation state and message processor
    # Convert global_settings to dict for compatibility
    if hasattr(multi_bot_config.global_settings, 'model_dump'):
        global_settings_dict = multi_bot_config.global_settings.model_dump()
    elif hasattr(multi_bot_config.global_settings, 'dict'):
        global_settings_dict = multi_bot_config.global_settings.dict()
    else:
        global_settings_dict = multi_bot_config.global_settings
    
    conv_state = ConversationState(
        context_depth=global_settings_dict.get('context_depth', 10)
    )
    
    message_processor = MessageProcessor(
        conversation_state=conv_state,
        global_settings=global_settings_dict
    )
    
    print(f"✅ Initialized MessageProcessor")
    
    # Test scenarios
    test_scenarios = [
        {
            "message": "Hey sage, what is it?",
            "channel": "bambam", 
            "description": "Sage mention in bambam (should respond)"
        },
        {
            "message": "Hey sage, what is it?",
            "channel": "general",
            "description": "Sage mention in general (should respond)"
        },
        {
            "message": "What does everyone think?",
            "channel": "bambam",
            "description": "General question in bambam (may respond)"
        },
        {
            "message": "!ask what is it?",
            "channel": "bambam",
            "description": "Command message (should NOT respond)"
        },
        {
            "message": "Hey sage, what is it?",
            "channel": "random",
            "description": "Sage mention in non-configured channel (should NOT respond)"
        }
    ]
    
    # Test each bot against each scenario
    for bot_config in multi_bot_config.bots:
        # Convert Pydantic model to dict
        if hasattr(bot_config, 'model_dump'):
            bot_dict = bot_config.model_dump()
        elif hasattr(bot_config, 'dict'):
            bot_dict = bot_config.dict()
        else:
            bot_dict = bot_config
            
        bot_name = bot_dict['name']
        bot_channels = bot_dict['channels']
        
        print(f"\n🤖 Testing {bot_name.upper()} (channels: {bot_channels})")
        print("-" * 40)
        
        for scenario in test_scenarios:
            message = MockDiscordMessage(
                content=scenario["message"],
                channel_name=scenario["channel"]
            )
            
            try:
                # Test if bot should handle message
                should_handle = await message_processor.should_bot_handle_message(
                    bot_name, message, bot_channels
                )
                
                # Create message context for decision testing
                message_context = MessageContext(
                    message=message,
                    channel_name=scenario["channel"],
                    channel_id=123,
                    user_id=456,
                    user_name="TestUser",
                    content=scenario["message"],
                    timestamp=datetime.now(),
                    is_bot_message=False,
                    mentioned_bots=_extract_mentioned_bots(scenario["message"]),
                    thread_id=None
                )
                
                # Get conversation context
                conv_context = await conv_state.get_context(
                    channel_id=123,
                    user_id=456
                )
                
                # Test response decision
                if should_handle:
                    decision = await message_processor._make_response_decision(
                        bot_name, message_context, conv_context
                    )
                    
                    status = "🟢 WOULD RESPOND" if decision.should_respond else "🟡 MIGHT RESPOND"
                    confidence = f"(confidence: {decision.confidence:.2f})"
                    reasoning = f"Reason: {decision.reasoning}"
                else:
                    status = "🔴 NO RESPONSE"
                    confidence = ""
                    reasoning = "Channel/message filtering"
                
                print(f"  📨 '{scenario['message'][:30]}...' in #{scenario['channel']}")
                print(f"     {status} {confidence}")
                print(f"     {reasoning}")
                print()
                
            except Exception as e:
                print(f"  ❌ Error testing scenario: {e}")
                import traceback
                print(f"     {traceback.format_exc()}")
    
    print("\n🔍 Analysis:")
    print("=" * 50)
    print("If tests show 'WOULD RESPOND' but Discord doesn't respond, check:")
    print("1. Are all three bots connected? (check service logs)")
    print("2. Is Ollama running and accessible?")
    print("3. Are there errors in the bot logs?")
    print("4. Is the enhanced on_message handler working?")
    print("\n💡 Next steps:")
    print("- Check service logs: ./scripts/install-service.sh logs")
    print("- Test Ollama: curl http://127.0.0.1:11434/api/tags")
    print("- Enable debug logging to see live message processing")


def _extract_mentioned_bots(content: str) -> list:
    """Extract mentioned bot names from message content."""
    mentioned_bots = []
    content_lower = content.lower()
    common_bot_names = ['sage', 'spark', 'logic', 'assistant', 'bot']
    
    for bot_name in common_bot_names:
        if bot_name in content_lower:
            mentioned_bots.append(bot_name)
    
    return mentioned_bots


async def test_channel_patterns():
    """Test channel pattern matching specifically."""
    print("\n🎯 Testing Channel Pattern Matching")
    print("=" * 50)
    
    # Load config to get actual channel patterns
    config_path = Path(__file__).parent.parent / "config" / "multi_bot.yaml"
    multi_bot_config = multi_bot_config_manager.load_multi_bot_config(str(config_path))
    
    message_processor = MessageProcessor(
        conversation_state=ConversationState(context_depth=10),
        global_settings=multi_bot_config.global_settings
    )
    
    for bot_config in multi_bot_config.bots:
        bot_name = bot_config['name']
        patterns = bot_config['channels']
        
        print(f"\n🤖 {bot_name.upper()} patterns: {patterns}")
        
        test_channels = ['bambam', 'general', 'advice-general', 'tech-support', 'random']
        
        for channel in test_channels:
            matches = message_processor._matches_channel_patterns(
                type('MockChannel', (), {'name': channel})(), patterns
            )
            status = "✅ MATCH" if matches else "❌ NO MATCH"
            print(f"  #{channel}: {status}")


if __name__ == "__main__":
    print("🚀 Starting Live Message Processing Test")
    print("This will test the same logic used by the Discord bots")
    print()
    
    try:
        asyncio.run(test_message_processing())
        asyncio.run(test_channel_patterns())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()