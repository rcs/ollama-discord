# Multi-Token Discord Bot Implementation Plan

## Project Status: 🚧 In Progress
**Started**: 2025-07-08  
**Target Completion**: TBD

## Overview
This plan addresses the duplicate response issue by implementing support for multiple Discord tokens, allowing each bot personality to have its own Discord application and connection.

## Current Issue
- All bot personalities (sage, spark, logic) share the same Discord token
- This creates multiple Discord clients with the same token
- Discord sends each message to all clients, causing duplicate responses

## Solution: Multiple Discord Tokens
Each bot personality will have its own Discord token, creating truly independent bots.

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
**Status**: 📋 Planned  

**Goals**:
- Design backward-compatible configuration schema
- Support both single shared token and per-bot tokens
- Allow environment variables and .env file usage

**Proposed Schema Options**:

Option A: Token in bot config
```yaml
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"  # Override token for this bot
```

Option B: Token mapping section
```yaml
discord_tokens:
  sage: "${DISCORD_TOKEN_SAGE}"
  spark: "${DISCORD_TOKEN_SPARK}"
  logic: "${DISCORD_TOKEN_LOGIC}"
  default: "${DISCORD_TOKEN}"  # Fallback

bots:
  - name: "sage"
    config_file: "sage.yaml"
```

**Tasks**:
- [ ] Evaluate configuration options
- [ ] Choose best approach
- [ ] Update configuration models
- [ ] Add validation for token configuration

### Phase 2: Environment Variable Support
**Status**: 📋 Planned  

**Goals**:
- Support multiple tokens via environment variables
- Support .env file with multiple tokens
- Maintain backward compatibility

**Tasks**:
- [ ] Update .env.example with multiple token examples
- [ ] Implement token resolution logic
- [ ] Add validation for missing tokens
- [ ] Test environment variable loading

### Phase 3: Bot Manager Refactoring
**Status**: 📋 Planned  

**Goals**:
- Update bot manager to use per-bot tokens
- Ensure each bot uses its configured token
- Add logging for token usage

**Tasks**:
- [ ] Update BotManager token handling
- [ ] Modify bot initialization to use specific tokens
- [ ] Add debug logging for token assignment
- [ ] Update error handling for invalid tokens

### Phase 4: Testing and Validation
**Status**: 📋 Planned  

**Goals**:
- Test multiple token configuration
- Verify no duplicate responses
- Ensure backward compatibility

**Tasks**:
- [ ] Create test configurations
- [ ] Test with multiple Discord applications
- [ ] Verify each bot connects independently
- [ ] Test error scenarios (missing tokens, invalid tokens)
- [ ] Update integration tests

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

## Configuration Best Practices Research

### Environment Variable Arrays
Common patterns for multiple values:
1. **Indexed naming**: `DISCORD_TOKEN_1`, `DISCORD_TOKEN_2`
2. **Named suffixes**: `DISCORD_TOKEN_SAGE`, `DISCORD_TOKEN_SPARK`
3. **JSON array**: `DISCORD_TOKENS='["token1", "token2"]'`
4. **Comma-separated**: `DISCORD_TOKENS="token1,token2,token3"`

### Recommendation
Use named suffixes for clarity and maintainability:
- `DISCORD_TOKEN_SAGE`
- `DISCORD_TOKEN_SPARK`
- `DISCORD_TOKEN_LOGIC`

This approach:
- Makes it clear which token belongs to which bot
- Allows easy addition/removal of bots
- Works well with .env files
- Is self-documenting

## Success Criteria
- [ ] Each bot personality can use a different Discord token
- [ ] No duplicate responses when using multiple tokens
- [ ] Backward compatible with single token configuration
- [ ] Clear documentation for setup and configuration
- [ ] Debug commands show which token each bot is using

## Notes
- Maintain backward compatibility for users with single token
- Provide clear migration guide
- Consider security implications of multiple tokens
- Update service files if needed