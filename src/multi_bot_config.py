"""Multi-bot configuration management."""

import os
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path
from pydantic import BaseModel, Field, validator
import logging

from .config import Config, load_config


class ResponseBehaviorConfig(BaseModel):
    """Configuration for bot response behavior."""
    engagement_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    response_probability: float = Field(default=0.4, ge=0.0, le=1.0)
    context_weight: float = Field(default=0.8, ge=0.0, le=1.0)
    max_response_length: int = Field(default=500, gt=0)
    
    @validator('engagement_threshold', 'response_probability', 'context_weight')
    def validate_probability(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Probability values must be between 0.0 and 1.0")
        return v


class PersonaConfig(BaseModel):
    """Configuration for bot persona."""
    name: str
    description: Optional[str] = None
    personality_traits: List[str] = Field(default_factory=list)
    response_style: Optional[str] = None
    preferred_topics: List[str] = Field(default_factory=list)
    engagement_triggers: List[str] = Field(default_factory=list)


class BotInstanceConfig(BaseModel):
    """Configuration for a single bot instance in multi-bot deployment."""
    name: str
    config_file: str
    channels: List[str] = Field(default_factory=list)
    persona: Optional[PersonaConfig] = None
    response_behavior: ResponseBehaviorConfig = ResponseBehaviorConfig()
    enabled: bool = True
    priority: int = 0
    
    @validator('config_file')
    def validate_config_file(cls, v):
        if not v.endswith(('.yaml', '.yml')):
            raise ValueError("Config file must be a YAML file")
        return v
    
    @validator('channels')
    def validate_channels(cls, v):
        if not v:
            raise ValueError("At least one channel must be specified")
        return v


class GlobalSettings(BaseModel):
    """Global settings for multi-bot deployment."""
    context_depth: int = Field(default=10, ge=1, le=50)
    response_delay: str = Field(default="1-3")
    max_concurrent_responses: int = Field(default=2, ge=1, le=10)
    cooldown_period: int = Field(default=30, ge=5, le=300)
    conversation_timeout: int = Field(default=3600, ge=60)  # seconds
    storage_path: str = Field(default="./data/multi_bot_conversations")
    enable_cross_bot_context: bool = True
    enable_bot_mentions: bool = True
    debug_mode: bool = False
    
    @validator('response_delay')
    def validate_response_delay(cls, v):
        if '-' in v:
            try:
                min_delay, max_delay = map(float, v.split('-'))
                if min_delay < 0 or max_delay < min_delay:
                    raise ValueError("Invalid delay range")
            except ValueError:
                raise ValueError("Response delay must be in format 'min-max' or a single number")
        else:
            try:
                delay = float(v)
                if delay < 0:
                    raise ValueError("Response delay must be positive")
            except ValueError:
                raise ValueError("Response delay must be a valid number")
        return v


class MultiBotConfig(BaseModel):
    """Main configuration model for multi-bot deployment."""
    bots: List[BotInstanceConfig]
    global_settings: GlobalSettings = GlobalSettings()
    logging: Optional[Dict[str, Any]] = None
    
    @validator('bots')
    def validate_bots(cls, v):
        if not v:
            raise ValueError("At least one bot must be configured")
        
        # Check for duplicate bot names
        bot_names = [bot.name for bot in v]
        if len(bot_names) != len(set(bot_names)):
            raise ValueError("Bot names must be unique")
        
        return v
    
    def get_bot_config(self, bot_name: str) -> Optional[BotInstanceConfig]:
        """Get configuration for a specific bot."""
        for bot in self.bots:
            if bot.name == bot_name:
                return bot
        return None
    
    def get_enabled_bots(self) -> List[BotInstanceConfig]:
        """Get all enabled bot configurations."""
        return [bot for bot in self.bots if bot.enabled]
    
    def get_bots_for_channel(self, channel_name: str) -> List[BotInstanceConfig]:
        """Get all bots configured for a specific channel."""
        matching_bots = []
        
        for bot in self.get_enabled_bots():
            if self._channel_matches_patterns(channel_name, bot.channels):
                matching_bots.append(bot)
        
        # Sort by priority (higher priority first)
        matching_bots.sort(key=lambda b: b.priority, reverse=True)
        
        return matching_bots
    
    def _channel_matches_patterns(self, channel_name: str, patterns: List[str]) -> bool:
        """Check if channel name matches any of the patterns."""
        import re
        
        channel_name_lower = channel_name.lower()
        
        for pattern in patterns:
            pattern_lower = pattern.lower()
            
            # Exact match
            if pattern_lower == channel_name_lower:
                return True
            
            # Wildcard pattern
            if '*' in pattern_lower:
                regex_pattern = pattern_lower.replace('*', '.*')
                if re.match(f'^{regex_pattern}$', channel_name_lower):
                    return True
            
            # Prefix match (pattern ending with -)
            if pattern_lower.endswith('-') and channel_name_lower.startswith(pattern_lower[:-1]):
                return True
        
        return False


class MultiBotConfigManager:
    """Manager for loading and validating multi-bot configurations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def load_multi_bot_config(self, config_path: str) -> MultiBotConfig:
        """Load multi-bot configuration from YAML file."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Multi-bot configuration file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
        
        # Expand environment variables
        expanded_config = self._expand_env_vars(raw_config)
        
        # Validate configuration
        multi_bot_config = MultiBotConfig(**expanded_config)
        
        # Validate individual bot configurations
        self._validate_bot_configs(multi_bot_config, config_file.parent)
        
        return multi_bot_config
    
    def _expand_env_vars(self, data: Any) -> Any:
        """Recursively expand environment variables in configuration data."""
        if isinstance(data, dict):
            return {key: self._expand_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]
        elif isinstance(data, str):
            return os.path.expandvars(data)
        return data
    
    def _validate_bot_configs(self, multi_bot_config: MultiBotConfig, base_path: Path):
        """Validate that all referenced bot configuration files exist and are valid."""
        for bot_config in multi_bot_config.bots:
            config_file = base_path / bot_config.config_file
            
            if not config_file.is_absolute():
                config_file = base_path / config_file
            
            if not config_file.exists():
                raise FileNotFoundError(f"Bot configuration file not found: {config_file}")
            
            # Try to load and validate the individual bot config
            try:
                individual_config = load_config(str(config_file))
                self.logger.info(f"Validated configuration for bot: {bot_config.name}")
            except Exception as e:
                raise ValueError(f"Invalid configuration for bot {bot_config.name}: {e}")
    
    def create_example_config(self, output_path: str):
        """Create an example multi-bot configuration file."""
        example_config = {
            'bots': [
                {
                    'name': 'sage',
                    'config_file': 'config/sage.yaml',
                    'channels': ['general', 'advice-*'],
                    'persona': {
                        'name': 'Sage',
                        'description': 'A wise mentor who helps others think deeply',
                        'personality_traits': ['thoughtful', 'philosophical', 'patient'],
                        'response_style': 'reflective',
                        'preferred_topics': ['philosophy', 'problem-solving', 'life-advice'],
                        'engagement_triggers': ['questions', 'dilemmas', 'complex-topics']
                    },
                    'response_behavior': {
                        'engagement_threshold': 0.3,
                        'response_probability': 0.4,
                        'context_weight': 0.8
                    },
                    'enabled': True,
                    'priority': 1
                },
                {
                    'name': 'spark',
                    'config_file': 'config/spark.yaml',
                    'channels': ['creative', 'projects-*'],
                    'persona': {
                        'name': 'Spark',
                        'description': 'A creative catalyst who generates ideas',
                        'personality_traits': ['energetic', 'imaginative', 'enthusiastic'],
                        'response_style': 'creative',
                        'preferred_topics': ['creativity', 'brainstorming', 'innovation'],
                        'engagement_triggers': ['creative-challenges', 'ideation', 'inspiration']
                    },
                    'response_behavior': {
                        'engagement_threshold': 0.4,
                        'response_probability': 0.5,
                        'context_weight': 0.6
                    },
                    'enabled': True,
                    'priority': 2
                },
                {
                    'name': 'logic',
                    'config_file': 'config/logic.yaml',
                    'channels': ['tech-*', 'research'],
                    'persona': {
                        'name': 'Logic',
                        'description': 'An analytical thinker focused on facts and data',
                        'personality_traits': ['precise', 'methodical', 'analytical'],
                        'response_style': 'structured',
                        'preferred_topics': ['technology', 'research', 'analysis'],
                        'engagement_triggers': ['technical-questions', 'data-analysis', 'facts']
                    },
                    'response_behavior': {
                        'engagement_threshold': 0.2,
                        'response_probability': 0.3,
                        'context_weight': 0.9
                    },
                    'enabled': True,
                    'priority': 3
                }
            ],
            'global_settings': {
                'context_depth': 10,
                'response_delay': '1-3',
                'max_concurrent_responses': 2,
                'cooldown_period': 30,
                'conversation_timeout': 3600,
                'storage_path': './data/multi_bot_conversations',
                'enable_cross_bot_context': True,
                'enable_bot_mentions': True,
                'debug_mode': False
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(example_config, f, default_flow_style=False, indent=2)
        
        self.logger.info(f"Created example multi-bot configuration at: {output_path}")
    
    def validate_channel_assignments(self, multi_bot_config: MultiBotConfig) -> Dict[str, List[str]]:
        """Validate channel assignments and return potential conflicts."""
        channel_assignments = {}
        conflicts = {}
        
        for bot in multi_bot_config.bots:
            for channel_pattern in bot.channels:
                if channel_pattern not in channel_assignments:
                    channel_assignments[channel_pattern] = []
                channel_assignments[channel_pattern].append(bot.name)
        
        # Find conflicts (channels assigned to multiple bots)
        for channel_pattern, bot_names in channel_assignments.items():
            if len(bot_names) > 1:
                conflicts[channel_pattern] = bot_names
        
        return conflicts
    
    def get_config_summary(self, multi_bot_config: MultiBotConfig) -> Dict[str, Any]:
        """Get a summary of the multi-bot configuration."""
        enabled_bots = multi_bot_config.get_enabled_bots()
        
        channel_coverage = {}
        for bot in enabled_bots:
            for channel in bot.channels:
                if channel not in channel_coverage:
                    channel_coverage[channel] = []
                channel_coverage[channel].append(bot.name)
        
        return {
            'total_bots': len(multi_bot_config.bots),
            'enabled_bots': len(enabled_bots),
            'bot_names': [bot.name for bot in enabled_bots],
            'channel_patterns': list(channel_coverage.keys()),
            'channel_coverage': channel_coverage,
            'global_settings': multi_bot_config.global_settings.model_dump(),
            'potential_conflicts': self.validate_channel_assignments(multi_bot_config)
        }


# Global instance
multi_bot_config_manager = MultiBotConfigManager()