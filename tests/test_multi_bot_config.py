"""Unit tests for MultiBotConfig."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from src.multi_bot_config import (
    ResponseBehaviorConfig, PersonaConfig, BotInstanceConfig, 
    GlobalSettings, MultiBotConfig, MultiBotConfigManager
)


class TestResponseBehaviorConfig:
    """Test ResponseBehaviorConfig."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = ResponseBehaviorConfig()
        
        assert config.engagement_threshold == 0.3
        assert config.response_probability == 0.4
        assert config.context_weight == 0.8
        assert config.max_response_length == 500
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = ResponseBehaviorConfig(
            engagement_threshold=0.5,
            response_probability=0.6,
            context_weight=0.9,
            max_response_length=1000
        )
        
        assert config.engagement_threshold == 0.5
        assert config.response_probability == 0.6
        assert config.context_weight == 0.9
        assert config.max_response_length == 1000
    
    def test_validation_probability_range(self):
        """Test validation of probability values."""
        with pytest.raises(ValueError):
            ResponseBehaviorConfig(engagement_threshold=1.5)
        
        with pytest.raises(ValueError):
            ResponseBehaviorConfig(response_probability=-0.1)
        
        with pytest.raises(ValueError):
            ResponseBehaviorConfig(context_weight=2.0)


class TestPersonaConfig:
    """Test PersonaConfig."""
    
    def test_basic_persona(self):
        """Test basic persona configuration."""
        persona = PersonaConfig(
            name="TestBot",
            description="A test bot"
        )
        
        assert persona.name == "TestBot"
        assert persona.description == "A test bot"
        assert persona.personality_traits == []
        assert persona.response_style is None
        assert persona.preferred_topics == []
        assert persona.engagement_triggers == []
    
    def test_full_persona(self):
        """Test full persona configuration."""
        persona = PersonaConfig(
            name="Sage",
            description="Wise mentor",
            personality_traits=["thoughtful", "patient"],
            response_style="contemplative",
            preferred_topics=["philosophy", "wisdom"],
            engagement_triggers=["questions", "dilemmas"]
        )
        
        assert persona.name == "Sage"
        assert len(persona.personality_traits) == 2
        assert persona.response_style == "contemplative"
        assert len(persona.preferred_topics) == 2
        assert len(persona.engagement_triggers) == 2


class TestBotInstanceConfig:
    """Test BotInstanceConfig."""
    
    def test_basic_bot_config(self):
        """Test basic bot configuration."""
        config = BotInstanceConfig(
            name="test-bot",
            config_file="test.yaml",
            channels=["general"]
        )
        
        assert config.name == "test-bot"
        assert config.config_file == "test.yaml"
        assert config.channels == ["general"]
        assert config.enabled is True
        assert config.priority == 0
    
    def test_validation_config_file_extension(self):
        """Test validation of config file extension."""
        with pytest.raises(ValueError, match="Config file must be a YAML file"):
            BotInstanceConfig(
                name="test",
                config_file="test.json",
                channels=["test"]
            )
    
    def test_validation_empty_channels(self):
        """Test validation of empty channels list."""
        with pytest.raises(ValueError, match="At least one channel must be specified"):
            BotInstanceConfig(
                name="test",
                config_file="test.yaml",
                channels=[]
            )
    
    def test_full_bot_config(self):
        """Test full bot configuration."""
        persona = PersonaConfig(name="TestBot")
        behavior = ResponseBehaviorConfig(engagement_threshold=0.5)
        
        config = BotInstanceConfig(
            name="test-bot",
            config_file="test.yaml",
            channels=["general", "test-*"],
            persona=persona,
            response_behavior=behavior,
            enabled=False,
            priority=5
        )
        
        assert config.persona == persona
        assert config.response_behavior == behavior
        assert config.enabled is False
        assert config.priority == 5


class TestGlobalSettings:
    """Test GlobalSettings."""
    
    def test_default_settings(self):
        """Test default global settings."""
        settings = GlobalSettings()
        
        assert settings.context_depth == 10
        assert settings.response_delay == "1-3"
        assert settings.max_concurrent_responses == 2
        assert settings.cooldown_period == 30
        assert settings.conversation_timeout == 3600
        assert settings.storage_path == "./data/multi_bot_conversations"
        assert settings.enable_cross_bot_context is True
        assert settings.enable_bot_mentions is True
        assert settings.debug_mode is False
    
    def test_validation_response_delay_range(self):
        """Test validation of response delay range."""
        # Valid range
        settings = GlobalSettings(response_delay="1.5-2.5")
        assert settings.response_delay == "1.5-2.5"
        
        # Valid single value
        settings = GlobalSettings(response_delay="2.0")
        assert settings.response_delay == "2.0"
        
        # Invalid range
        with pytest.raises(ValueError):
            GlobalSettings(response_delay="3-1")  # max < min
        
        # Invalid format
        with pytest.raises(ValueError):
            GlobalSettings(response_delay="invalid")
    
    def test_validation_ranges(self):
        """Test validation of numeric ranges."""
        with pytest.raises(ValueError):
            GlobalSettings(context_depth=0)  # Below minimum
        
        with pytest.raises(ValueError):
            GlobalSettings(context_depth=100)  # Above maximum
        
        with pytest.raises(ValueError):
            GlobalSettings(max_concurrent_responses=0)  # Below minimum


class TestMultiBotConfig:
    """Test MultiBotConfig."""
    
    def test_basic_multibot_config(self):
        """Test basic multi-bot configuration."""
        bot_config = BotInstanceConfig(
            name="test-bot",
            config_file="test.yaml",
            channels=["test"]
        )
        
        config = MultiBotConfig(
            bots=[bot_config],
            global_settings=GlobalSettings()
        )
        
        assert len(config.bots) == 1
        assert config.bots[0] == bot_config
        assert isinstance(config.global_settings, GlobalSettings)
    
    def test_validation_empty_bots(self):
        """Test validation of empty bots list."""
        with pytest.raises(ValueError, match="At least one bot must be configured"):
            MultiBotConfig(bots=[])
    
    def test_validation_duplicate_bot_names(self):
        """Test validation of duplicate bot names."""
        bot1 = BotInstanceConfig(name="test", config_file="test1.yaml", channels=["ch1"])
        bot2 = BotInstanceConfig(name="test", config_file="test2.yaml", channels=["ch2"])
        
        with pytest.raises(ValueError, match="Bot names must be unique"):
            MultiBotConfig(bots=[bot1, bot2])
    
    def test_get_bot_config(self):
        """Test getting specific bot configuration."""
        bot1 = BotInstanceConfig(name="bot1", config_file="bot1.yaml", channels=["ch1"])
        bot2 = BotInstanceConfig(name="bot2", config_file="bot2.yaml", channels=["ch2"])
        
        config = MultiBotConfig(bots=[bot1, bot2])
        
        assert config.get_bot_config("bot1") == bot1
        assert config.get_bot_config("bot2") == bot2
        assert config.get_bot_config("nonexistent") is None
    
    def test_get_enabled_bots(self):
        """Test getting enabled bots."""
        bot1 = BotInstanceConfig(name="bot1", config_file="bot1.yaml", channels=["ch1"], enabled=True)
        bot2 = BotInstanceConfig(name="bot2", config_file="bot2.yaml", channels=["ch2"], enabled=False)
        bot3 = BotInstanceConfig(name="bot3", config_file="bot3.yaml", channels=["ch3"], enabled=True)
        
        config = MultiBotConfig(bots=[bot1, bot2, bot3])
        enabled = config.get_enabled_bots()
        
        assert len(enabled) == 2
        assert bot1 in enabled
        assert bot3 in enabled
        assert bot2 not in enabled
    
    def test_get_bots_for_channel(self):
        """Test getting bots for specific channel."""
        bot1 = BotInstanceConfig(name="bot1", config_file="bot1.yaml", channels=["general"], priority=1)
        bot2 = BotInstanceConfig(name="bot2", config_file="bot2.yaml", channels=["tech-*"], priority=2)
        bot3 = BotInstanceConfig(name="bot3", config_file="bot3.yaml", channels=["general"], priority=3)
        
        config = MultiBotConfig(bots=[bot1, bot2, bot3])
        
        # Test exact match
        general_bots = config.get_bots_for_channel("general")
        assert len(general_bots) == 2
        assert general_bots[0].priority == 3  # Higher priority first
        assert general_bots[1].priority == 1
        
        # Test wildcard match
        tech_bots = config.get_bots_for_channel("tech-support")
        assert len(tech_bots) == 1
        assert tech_bots[0].name == "bot2"
    
    def test_channel_matches_patterns_exact(self):
        """Test exact channel pattern matching."""
        # Create a minimal valid config to test the method
        dummy_bot = BotInstanceConfig(name="test", config_file="test.yaml", channels=["test"])
        config = MultiBotConfig(bots=[dummy_bot])
        
        assert config._channel_matches_patterns("general", ["general", "test"])
        assert not config._channel_matches_patterns("general", ["test", "other"])
    
    def test_channel_matches_patterns_wildcard(self):
        """Test wildcard channel pattern matching."""
        # Create a minimal valid config to test the method
        dummy_bot = BotInstanceConfig(name="test", config_file="test.yaml", channels=["test"])
        config = MultiBotConfig(bots=[dummy_bot])
        
        assert config._channel_matches_patterns("tech-support", ["tech-*"])
        assert config._channel_matches_patterns("projects-alpha", ["projects-*"])
        assert not config._channel_matches_patterns("general", ["tech-*"])
    
    def test_channel_matches_patterns_prefix(self):
        """Test prefix channel pattern matching."""
        # Create a minimal valid config to test the method
        dummy_bot = BotInstanceConfig(name="test", config_file="test.yaml", channels=["test"])
        config = MultiBotConfig(bots=[dummy_bot])
        
        assert config._channel_matches_patterns("tech-support", ["tech-"])
        assert config._channel_matches_patterns("tech-general", ["tech-"])
        assert not config._channel_matches_patterns("support-tech", ["tech-"])


class TestMultiBotConfigManager:
    """Test MultiBotConfigManager."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # Create valid bot config
            bot_config = {
                'bot': {'name': 'test-bot'},
                'discord': {'token': 'test-token'},
                'ollama': {'model': 'test-model'},
                'system_prompt': 'Test prompt'
            }
            
            bot_config_file = config_dir / "test_bot.yaml"
            with open(bot_config_file, 'w') as f:
                yaml.dump(bot_config, f)
            
            # Create multi-bot config
            multi_config = {
                'bots': [
                    {
                        'name': 'test-bot',
                        'config_file': str(bot_config_file),
                        'channels': ['test-channel']
                    }
                ],
                'global_settings': {
                    'context_depth': 5
                }
            }
            
            multi_config_file = config_dir / "multi_bot.yaml"
            with open(multi_config_file, 'w') as f:
                yaml.dump(multi_config, f)
            
            yield config_dir, multi_config_file, bot_config_file
    
    def test_manager_creation(self):
        """Test creating MultiBotConfigManager."""
        manager = MultiBotConfigManager()
        assert hasattr(manager, 'logger')
    
    @patch('src.multi_bot_config.load_config')
    def test_load_multi_bot_config(self, mock_load_config, temp_config_dir):
        """Test loading multi-bot configuration."""
        config_dir, multi_config_file, bot_config_file = temp_config_dir
        
        # Mock the individual bot config loading
        mock_bot_config = Mock()
        mock_load_config.return_value = mock_bot_config
        
        manager = MultiBotConfigManager()
        config = manager.load_multi_bot_config(str(multi_config_file))
        
        assert isinstance(config, MultiBotConfig)
        assert len(config.bots) == 1
        assert config.bots[0].name == 'test-bot'
    
    def test_load_multi_bot_config_not_found(self):
        """Test loading non-existent config file."""
        manager = MultiBotConfigManager()
        
        with pytest.raises(FileNotFoundError):
            manager.load_multi_bot_config("nonexistent.yaml")
    
    def test_expand_env_vars_dict(self):
        """Test expanding environment variables in dictionary."""
        manager = MultiBotConfigManager()
        
        with patch.dict('os.environ', {'TEST_VAR': 'test_value'}):
            data = {'key': '${TEST_VAR}', 'nested': {'key2': '${TEST_VAR}_suffix'}}
            result = manager._expand_env_vars(data)
            
            assert result['key'] == 'test_value'
            assert result['nested']['key2'] == 'test_value_suffix'
    
    def test_expand_env_vars_list(self):
        """Test expanding environment variables in list."""
        manager = MultiBotConfigManager()
        
        with patch.dict('os.environ', {'TEST_VAR': 'test_value'}):
            data = ['${TEST_VAR}', 'static', '${TEST_VAR}_suffix']
            result = manager._expand_env_vars(data)
            
            assert result == ['test_value', 'static', 'test_value_suffix']
    
    def test_expand_env_vars_string(self):
        """Test expanding environment variables in string."""
        manager = MultiBotConfigManager()
        
        with patch.dict('os.environ', {'TEST_VAR': 'test_value'}):
            result = manager._expand_env_vars('${TEST_VAR}')
            assert result == 'test_value'
    
    def test_expand_env_vars_other_types(self):
        """Test expanding environment variables with other types."""
        manager = MultiBotConfigManager()
        
        assert manager._expand_env_vars(123) == 123
        assert manager._expand_env_vars(True) is True
        assert manager._expand_env_vars(None) is None
    
    def test_create_example_config(self):
        """Test creating example configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "example.yaml"
            
            manager = MultiBotConfigManager()
            manager.create_example_config(str(output_file))
            
            assert output_file.exists()
            
            # Verify content is valid YAML
            with open(output_file) as f:
                data = yaml.safe_load(f)
            
            assert 'bots' in data
            assert 'global_settings' in data
            assert len(data['bots']) == 3  # Sage, Spark, Logic
    
    def test_validate_channel_assignments_no_conflicts(self):
        """Test channel assignment validation without conflicts."""
        bot1 = BotInstanceConfig(name="bot1", config_file="bot1.yaml", channels=["general"])
        bot2 = BotInstanceConfig(name="bot2", config_file="bot2.yaml", channels=["tech"])
        
        config = MultiBotConfig(bots=[bot1, bot2])
        manager = MultiBotConfigManager()
        
        conflicts = manager.validate_channel_assignments(config)
        assert len(conflicts) == 0
    
    def test_validate_channel_assignments_with_conflicts(self):
        """Test channel assignment validation with conflicts."""
        bot1 = BotInstanceConfig(name="bot1", config_file="bot1.yaml", channels=["general"])
        bot2 = BotInstanceConfig(name="bot2", config_file="bot2.yaml", channels=["general"])
        
        config = MultiBotConfig(bots=[bot1, bot2])
        manager = MultiBotConfigManager()
        
        conflicts = manager.validate_channel_assignments(config)
        assert "general" in conflicts
        assert set(conflicts["general"]) == {"bot1", "bot2"}
    
    def test_get_config_summary(self):
        """Test getting configuration summary."""
        bot1 = BotInstanceConfig(name="bot1", config_file="bot1.yaml", channels=["general"], enabled=True)
        bot2 = BotInstanceConfig(name="bot2", config_file="bot2.yaml", channels=["tech"], enabled=False)
        
        config = MultiBotConfig(bots=[bot1, bot2])
        manager = MultiBotConfigManager()
        
        summary = manager.get_config_summary(config)
        
        assert summary['total_bots'] == 2
        assert summary['enabled_bots'] == 1
        assert summary['bot_names'] == ['bot1']
        assert 'general' in summary['channel_patterns']
        assert summary['channel_coverage']['general'] == ['bot1']


if __name__ == "__main__":
    pytest.main([__file__])