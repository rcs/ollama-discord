# Multi-Bot Conversational System - PLAN.md

## Project Overview
Transform the single-bot Discord system into a scalable multi-bot conversational platform where multiple AI personas can interact naturally in whitelisted channels, using trailing message context for intelligent responses.

## Core Features
- **Multi-bot orchestration**: Run N bots simultaneously with shared conversation state
- **Channel whitelisting**: Bots respond only in specified channels
- **Context-aware responses**: Use trailing message history for intelligent replies
- **Natural conversation flow**: Bots participate organically without explicit commands
- **Persona-driven interactions**: Each bot has distinct personality and response patterns

## Success Criteria

### Primary Success Metrics
1. **Multi-bot deployment**: Successfully run 3+ bots simultaneously
2. **Channel filtering**: Bots respond only in whitelisted channels
3. **Context awareness**: Responses incorporate last 5-10 messages from channel
4. **Natural flow**: Bots engage without requiring explicit commands/mentions
5. **Conversation continuity**: Maintain context across multi-bot interactions

### Secondary Success Metrics
1. **Persona differentiation**: Each bot demonstrates distinct personality
2. **Response quality**: Contextually appropriate and engaging responses
3. **Scalability**: Easy to add new bot personas via configuration

## Architecture Design

### 1. Multi-Bot Process Manager
- **File**: `src/bot_manager.py`
- **Purpose**: Orchestrate multiple bot instances with shared state
- **Key features**:
  - Asyncio-based concurrent bot execution
  - Shared conversation state management
  - Bot lifecycle management (start/stop/restart)
  - Configuration hot-reloading

### 2. Enhanced Message Processing
- **File**: `src/message_processor.py`
- **Purpose**: Intelligent message routing and context management
- **Key features**:
  - Channel whitelist filtering
  - Message context collection (trailing N messages)
  - Bot response eligibility determination
  - Message threading and conversation tracking

### 3. Shared Conversation State
- **File**: `src/conversation_state.py`
- **Purpose**: Centralized conversation history and context
- **Key features**:
  - Multi-bot conversation history
  - Context-aware message storage
  - Bot interaction tracking
  - Conversation topic/thread management

### 4. Configuration Extensions
- **Files**: Configuration schema updates
- **Purpose**: Support multi-bot deployment and channel management
- **Key features**:
  - Channel whitelist configuration
  - Bot persona definitions
  - Response behavior settings
  - Multi-bot coordination rules

## Implementation Plan

### Phase 0: Setup & Planning
1. **Create feature branch** - `feature/multi-bot-conversation-system`
2. **Create PLAN.md** - This comprehensive planning document
3. **Setup PR workflow** - Follow proper development process

### Phase 1: Core Infrastructure (Week 1)
1. **Bot Manager Architecture** - Multi-bot process coordination
2. **Configuration Schema** - Extend for multi-bot support
3. **Message Processing** - Enhanced context-aware processing
4. **Shared State System** - Centralized conversation management
5. **First PR checkpoint** - Core infrastructure complete

### Phase 2: Bot Personas & Channel Management (Week 2)
1. **Three Bot Personas** - Create distinct personality configurations
2. **Channel Whitelisting** - Implement channel filtering system
3. **Context Collection** - Trailing message context system
4. **Response Logic** - Natural conversation participation rules
5. **CLI Enhancement** - Multi-bot deployment commands

### Phase 3: Integration & Testing (Week 3)
1. **Integration Testing** - Multi-bot conversation scenarios
2. **Persona Testing** - Personality differentiation validation
3. **Channel Testing** - Whitelist filtering accuracy
4. **Documentation** - Usage guides and examples
5. **Final PR** - Complete multi-bot system implementation

## PR Workflow Integration

### Development Process
1. **Feature Branch**: `feature/multi-bot-conversation-system`
2. **Commit Strategy**: Atomic commits with clear messages
3. **Testing**: Run tests before each commit
4. **Code Review**: Submit PR for review before merging
5. **Documentation**: Update README and docs with changes

### PR Checkpoints
- **Checkpoint 1**: Core infrastructure (bot manager, state, processor)
- **Checkpoint 2**: Configuration and persona system
- **Checkpoint 3**: Complete system with tests and documentation

## Bot Personas

### Persona 1: "Sage" - The Wise Mentor
- **Personality**: Thoughtful, philosophical, asks probing questions
- **Response style**: Reflective, uses metaphors, encourages deeper thinking
- **Triggers**: Complex topics, philosophical discussions, problem-solving
- **Channel focus**: General discussion, advice channels

### Persona 2: "Spark" - The Creative Catalyst
- **Personality**: Energetic, imaginative, generates creative ideas
- **Response style**: Enthusiastic, uses analogies, suggests alternatives
- **Triggers**: Creative challenges, brainstorming, artistic discussions
- **Channel focus**: Creative channels, project planning, ideation

### Persona 3: "Logic" - The Analytical Thinker
- **Personality**: Precise, methodical, focuses on facts and data
- **Response style**: Structured, evidence-based, systematic analysis
- **Triggers**: Technical discussions, data analysis, logical problems
- **Channel focus**: Technical channels, research, fact-checking

## Testing Strategy

### Unit Tests
- **File**: `tests/test_bot_manager.py`
  - Bot lifecycle management
  - Configuration loading and validation
  - Message routing logic

- **File**: `tests/test_message_processor.py`
  - Channel filtering accuracy
  - Context collection correctness
  - Response eligibility determination

- **File**: `tests/test_conversation_state.py`
  - Multi-bot conversation history
  - Context persistence and retrieval
  - State synchronization

### Integration Tests
- **File**: `tests/test_multi_bot_integration.py`
  - Multi-bot conversation scenarios
  - Channel whitelist enforcement
  - Context-aware response generation
  - Persona differentiation validation

### End-to-End Tests
- **File**: `tests/test_e2e_conversations.py`
  - Full conversation flow testing
  - Real Discord integration testing
  - Configuration hot-reload testing

## Configuration Structure

### Multi-Bot Configuration
```yaml
# config/multi_bot.yaml
bots:
  - name: "sage"
    config_file: "config/sage.yaml"
    channels: ["general", "advice-*"]
    
  - name: "spark"  
    config_file: "config/spark.yaml"
    channels: ["creative", "projects-*"]
    
  - name: "logic"
    config_file: "config/logic.yaml"
    channels: ["tech-*", "research"]

global_settings:
  context_depth: 10
  response_delay: 1-3  # seconds
  max_concurrent_responses: 2
```

### Individual Bot Configuration
```yaml
# config/sage.yaml
bot:
  name: "sage"
  persona: "wise-mentor"
  
discord:
  token: "${DISCORD_TOKEN_SAGE}"
  
system_prompt: |
  You are Sage, a wise mentor who helps others think deeply...
  
response_behavior:
  engagement_threshold: 0.3
  response_probability: 0.4
  context_weight: 0.8
```

## File Structure Changes

```
ollama-discord/
├── PLAN.md                     # This planning document
├── src/
│   ├── bot_manager.py          # Multi-bot orchestration
│   ├── message_processor.py    # Enhanced message processing
│   ├── conversation_state.py   # Shared conversation state
│   └── multi_bot_config.py     # Multi-bot configuration
├── config/
│   ├── multi_bot.yaml          # Multi-bot deployment config
│   ├── sage.yaml               # Sage persona config
│   ├── spark.yaml              # Spark persona config
│   └── logic.yaml              # Logic persona config
├── tests/
│   ├── test_bot_manager.py
│   ├── test_message_processor.py
│   ├── test_conversation_state.py
│   ├── test_multi_bot_integration.py
│   └── test_e2e_conversations.py
└── docs/
    ├── MULTI_BOT_SETUP.md
    ├── PERSONA_GUIDE.md
    └── TESTING_GUIDE.md
```

## Dependencies & Requirements

### New Dependencies
- `asyncio` - Concurrent bot execution (built-in)
- `pytest-asyncio` - Async testing support
- `pytest-mock` - Mocking for unit tests
- `fakeredis` - Optional: Redis-compatible testing

### System Requirements
- Multiple Discord bot tokens (3+ for initial personas)
- Sufficient system resources for concurrent bots
- Discord server with appropriate channel structure
- Ollama running with multiple model support

## Risk Mitigation

### Technical Risks
1. **Rate limiting**: Implement bot coordination to avoid Discord API limits
2. **Memory usage**: Optimize shared state management for scalability
3. **Message conflicts**: Prevent simultaneous bot responses to same message
4. **Context overflow**: Implement context size limits and cleanup

### Operational Risks
1. **Bot token management**: Secure storage and rotation procedures
2. **Channel permissions**: Validate bot permissions in target channels
3. **Configuration errors**: Comprehensive validation and error handling
4. **Service reliability**: Implement health checks and restart mechanisms

## Success Validation

### Functional Tests
- [ ] Deploy 3 bots simultaneously
- [ ] Verify channel whitelist filtering
- [ ] Confirm context-aware responses
- [ ] Validate persona differentiation
- [ ] Test natural conversation flow

### User Experience Tests
- [ ] Natural conversation feel
- [ ] Distinct bot personalities
- [ ] Appropriate response timing
- [ ] Relevant context usage
- [ ] Engaging multi-bot interactions

This plan provides a comprehensive roadmap for implementing a scalable multi-bot conversational system with clear success criteria, testing strategy, and implementation phases.