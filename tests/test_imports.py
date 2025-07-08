"""Integration tests for module imports and dependencies.

These tests catch import-time errors that would cause the bot to crash on startup.
"""

import pytest
import sys
import importlib
from pathlib import Path


class TestModuleImports:
    """Test that all modules can be imported without errors."""
    
    def test_main_module_imports(self):
        """Test that main.py can import without errors."""
        # This will catch CLI and import issues
        import main
        assert hasattr(main, 'main')
    
    def test_core_module_imports(self):
        """Test that core modules can be imported without errors."""
        # This will catch Pydantic @validator issues immediately
        import src.config
        import src.multi_bot_config
        import src.bot_manager
        import src.service_factory
        import src.bot
        import src.conversation_state
        import src.domain_services
        import src.adapters
        import src.ports
    
    def test_pydantic_model_creation(self):
        """Test that Pydantic models can be created without syntax errors."""
        from src.config import Config, DiscordConfig, OllamaConfig
        from src.multi_bot_config import (
            ResponseBehaviorConfig, PersonaConfig, BotInstanceConfig, 
            GlobalSettings, MultiBotConfig
        )
        
        # Test basic model creation - this will fail if @validator syntax is wrong
        discord_config = DiscordConfig(token="test_token", command_prefix="!")
        ollama_config = OllamaConfig(model="test_model")
        
        # Test multi-bot config models
        response_config = ResponseBehaviorConfig()
        persona_config = PersonaConfig(name="test", description="test")
        bot_config = BotInstanceConfig(
            name="test", 
            config_file="test.yaml", 
            channels=["test"]
        )
        global_settings = GlobalSettings()
        multi_config = MultiBotConfig(bots=[bot_config], global_settings=global_settings)
        
        # Verify objects were created successfully
        assert discord_config.token == "test_token"
        assert response_config.engagement_threshold == 0.3  # default value
        assert multi_config.bots[0].name == "test"
    
    def test_pydantic_validation_works(self):
        """Test that Pydantic validation actually works."""
        from src.config import DiscordConfig
        from src.multi_bot_config import ResponseBehaviorConfig, GlobalSettings
        from pydantic import ValidationError
        
        # Test that validation catches invalid values
        with pytest.raises(ValidationError):
            DiscordConfig(token="", command_prefix="!")  # Empty token should fail
        
        with pytest.raises(ValidationError):
            ResponseBehaviorConfig(engagement_threshold=1.5)  # > 1.0 should fail
        
        with pytest.raises(ValidationError):
            GlobalSettings(context_depth=0)  # Below minimum should fail
    
    def test_all_dependencies_available(self):
        """Test that all required dependencies are available."""
        # Test Discord.py
        import discord
        assert hasattr(discord, 'Client')
        assert hasattr(discord, 'Message')
        
        # Test requests
        import requests
        assert hasattr(requests, 'get')
        
        # Test Pydantic V2
        import pydantic
        from pydantic import BaseModel, field_validator
        assert hasattr(pydantic, 'BaseModel')
        
        # Test YAML
        import yaml
        assert hasattr(yaml, 'safe_load')
        
        # Test Click
        import click
        assert hasattr(click, 'command')


class TestImportErrorScenarios:
    """Test specific import error scenarios that caused crashes."""
    
    def test_pydantic_v2_syntax(self):
        """Test that we're using correct Pydantic V2 syntax."""
        from pydantic import BaseModel, field_validator, ValidationError
        
        # Test that field_validator works (not @validator)
        class TestModel(BaseModel):
            value: float
            
            @field_validator('value')
            @classmethod
            def validate_value(cls, v):
                if v < 0 or v > 1:
                    raise ValueError('Value must be between 0 and 1')
                return v
        
        # Test it works
        valid_model = TestModel(value=0.5)
        assert valid_model.value == 0.5
        
        # Test validation fails appropriately
        with pytest.raises(ValidationError):
            TestModel(value=1.5)
    
    def test_no_legacy_pydantic_usage(self):
        """Test that we're not using legacy Pydantic V1 syntax."""
        import ast
        import src.config
        import src.multi_bot_config
        
        # Check source files for legacy @validator usage
        for module in [src.config, src.multi_bot_config]:
            source_file = Path(module.__file__)
            source_code = source_file.read_text()
            
            # Should not contain @validator decorator
            assert '@validator(' not in source_code, f"Found legacy @validator in {source_file}"
            
            # Should use @field_validator instead
            if 'validator' in source_code:
                assert '@field_validator(' in source_code, f"Found validator but not @field_validator in {source_file}"
    
    def test_cli_interface_exists(self):
        """Test that CLI interface is properly defined."""
        import main
        
        # Test that main function exists and is callable
        assert hasattr(main, 'main'), "main.py should have a main function"
        assert callable(main.main), "main function should be callable"
        
        # Test help works without crashing
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main.main, ['--help'])
        assert result.exit_code == 0
        assert 'Usage:' in result.output


class TestServiceDependencies:
    """Test that service dependencies are properly set up."""
    
    def test_service_factory_imports(self):
        """Test that service factory can create all services."""
        from src.service_factory import create_multi_bot_services
        from src.multi_bot_config import MultiBotConfig, BotInstanceConfig, GlobalSettings
        
        # Create minimal config
        bot_config = BotInstanceConfig(
            name="test", 
            config_file="test.yaml", 
            channels=["test"]
        )
        multi_config = MultiBotConfig(bots=[bot_config])
        
        # Test service creation doesn't crash
        services = create_multi_bot_services(multi_config)
        
        # Services are returned as a tuple: (orchestrator, coordinator, response_generator, conversation_state)
        assert len(services) == 4, f"Expected 4 services, got {len(services)}"
        
        # Verify service types
        orchestrator, coordinator, response_generator, conversation_state = services
        assert orchestrator is not None
        assert coordinator is not None  
        assert response_generator is not None
        assert conversation_state is not None
    
    def test_bot_manager_can_be_created(self):
        """Test that BotManager can be instantiated."""
        from src.bot_manager import BotManager
        
        # This should not crash on import or creation
        manager = BotManager("nonexistent.yaml")  # File doesn't need to exist for creation
        assert manager is not None
        assert hasattr(manager, 'initialize')
        assert hasattr(manager, 'start_all_bots')
        assert hasattr(manager, 'stop_all_bots')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])