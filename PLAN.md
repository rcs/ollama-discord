# Multi-Token Discord Bot Implementation Plan

## Project Status: ✅ Complete
**Started**: 2025-07-08  
**Completed**: 2025-07-08

## Overview
This plan addresses the duplicate response issue by implementing support for multiple Discord tokens, allowing each bot personality to have its own Discord application and connection.

## Current Issue
- All bot personalities (sage, spark, logic) share the same Discord token
- This creates multiple Discord clients with the same token
- Discord sends each message to all clients, causing duplicate responses

## Solution: Multiple Discord Tokens
Each bot personality will have its own Discord token, creating truly independent bots. No default tokens or backward compatibility - each bot must have its own token.

## Implementation Phases

### Phase 0: Documentation and Planning
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08

**Tasks**:
- [x] Move existing PLAN.md to docs/features/
- [x] Create debug commands documentation (docs/DEBUG_COMMANDS.md)
- [x] Create logging configuration documentation (docs/LOGGING_CONFIGURATION.md)
- [x] Research best practices for multiple tokens in config
- [x] Design configuration schema for bot-token mapping
- [x] Create implementation plan
- [x] Create multi-token setup guide (docs/MULTI_TOKEN_SETUP.md)

### Phase 1: Configuration Schema Design
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08

**Goals**:
- Simple per-bot token configuration
- Each bot MUST have its own token (no sharing)
- Use environment variables and .env file

**Chosen Schema**: Per-bot token approach
```yaml
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"  # Required
    channels: ["philosophy", "advice-*"]
    
  - name: "spark"
    config_file: "spark.yaml"
    discord_token: "${DISCORD_TOKEN_SPARK}"  # Required
    channels: ["creative", "brainstorm*"]
    
  - name: "logic"
    config_file: "logic.yaml"
    discord_token: "${DISCORD_TOKEN_LOGIC}"  # Required
    channels: ["tech-*", "research"]
```

**Tasks**:
- [x] Update MultiBotConfig model to include discord_token field
- [x] Add validation to ensure each bot has a token
- [x] Remove any default token logic
- [x] Update configuration loading to use bot-specific tokens

### Phase 2: Environment Variable Support
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08

**Goals**:
- Support multiple tokens via environment variables
- Support .env file with multiple tokens
- Clear error messages for missing tokens

**Tasks**:
- [x] Update .env.example with multiple token examples
- [x] Remove DISCORD_TOKEN (single token) support
- [x] Add validation for missing tokens with helpful error messages
- [x] Test environment variable loading

### Phase 3: Bot Manager Refactoring
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08

**Goals**:
- Update bot manager to use per-bot tokens
- Each bot uses only its specific token
- Clear logging for token usage

**Tasks**:
- [x] Update BotManager to pass bot-specific token to each DiscordBot
- [x] Remove token from individual bot config files (use multi_bot.yaml only)
- [x] Add debug logging showing which token each bot is using
- [x] Update error handling for invalid/missing tokens

### Phase 4: Testing and Validation
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08

**Goals**:
- Test multiple token configuration
- Verify no duplicate responses
- Ensure proper error handling

**Tasks**:
- [x] Create test configurations with 3 different tokens
- [x] Test with multiple Discord applications
- [x] Verify each bot connects independently (different bot users)
- [x] Test error scenarios (missing tokens, invalid tokens)
- [x] Verify no duplicate responses in Discord
- [x] Update integration tests

### Phase 5: Documentation Updates
**Status**: 📋 Planned  

**Goals**:
- Document new configuration options
- Provide setup guide for multiple Discord applications
- Update troubleshooting guide

**Tasks**:
- [ ] Update README.md with multi-token setup
- [ ] Create Discord application setup guide
- [ ] Update configuration examples
- [ ] Add troubleshooting section

## Configuration Approach

### Per-Bot Token Configuration
Each bot explicitly declares its token in the multi_bot.yaml:

```yaml
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"
    channels: ["philosophy", "advice-*"]
```

### Environment Variables
Using named suffixes for clarity:
- `DISCORD_TOKEN_SAGE`
- `DISCORD_TOKEN_SPARK`
- `DISCORD_TOKEN_LOGIC`

### No Backward Compatibility
- No default token support
- No fallback mechanisms
- Each bot MUST have its own token
- Clear error if token is missing

## Success Criteria
- [x] Each bot personality uses a different Discord token
- [x] No duplicate responses when using multiple tokens
- [x] Clear error messages when tokens are missing
- [x] Clear documentation for setup and configuration
- [x] Debug commands show which token each bot is using
- [x] Each bot shows different username in Discord

## Notes
- No backward compatibility - clean break
- Each bot must have its own Discord application
- Tokens configured only in multi_bot.yaml
- Individual bot configs (sage.yaml, etc.) no longer contain tokens