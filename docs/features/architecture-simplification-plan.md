# Multi-Token Discord Bot Implementation Plan

## Current Project: Multiple Discord Tokens Support
**Status**: 🚧 In Progress  
**Started**: 2025-07-08  

## Previous Project: Architecture Simplification
**Status**: ✅ Complete  
**Completed**: 2025-07-08

### Current Phase: Phase 0 - Planning
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08  

## Overview

This project aims to simplify the ollama-discord bot architecture by removing the dual single/multi-bot modes, improving type safety, and focusing tests on business logic rather than basic functionality.

## Current Issues Identified
1. **Dual architecture complexity**: Single bot vs multi-bot modes with conditional logic throughout
2. **Type inconsistencies**: Mix of Pydantic models and plain dicts with manual coercion
3. **Legacy compatibility layers**: DiscordBot has both old and new code paths
4. **Test focus**: Tests verify basic functionality rather than business logic
5. **Attribute checking**: Code uses hasattr() and getattr() instead of proper typing

## Implementation Phases

### Phase 1: Remove Single Bot Mode
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08  

**Goals**:
- Remove single bot CLI options and logic from `main.py`
- Remove legacy mode from `DiscordBot` class
- Remove `ConversationStorage` and `RateLimiter` classes (replaced by ports/adapters)
- Update service scripts to only support multi-bot configs

**Tasks**:
- [x] Update main.py CLI to only support multi-bot mode
- [x] Remove legacy storage and rate limiting from DiscordBot
- [x] Update service installation scripts
- [x] Convert existing single bot configs to multi-bot format
- [x] Update tests and ensure they pass
- [ ] Commit changes

### Phase 2: Improve Type Safety
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08  

**Goals**:
- Make all configs use proper Pydantic models consistently
- Remove all `hasattr()`, `getattr()`, and manual dict conversion
- Add proper type hints throughout (enable mypy strict mode)
- Use dependency injection properly with typed interfaces

**Tasks**:
- [x] Review and fix type inconsistencies in config handling
- [x] Remove hasattr/getattr usage in favor of proper typing
- [x] Enable mypy strict mode and fix all issues
- [x] Update dependency injection to use typed interfaces
- [x] Update tests and ensure they pass
- [ ] Commit changes

### Phase 3: Refactor DiscordBot Class
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08  

**Goals**:
- Remove legacy storage/rate limiting code
- Remove conditional orchestrator logic
- Make orchestrator required (not optional)
- Simplify message handling flow

**Tasks**:
- [x] Clean up DiscordBot constructor and remove optional orchestrator
- [x] Remove legacy message handling paths
- [x] Simplify on_message flow
- [x] Remove unused custom_message_handler complexity
- [x] Remove unused send_chunked_message method (handled by adapters)
- [x] Add proper type hints to all methods
- [x] Update tests and ensure they pass
- [ ] Commit changes

### Phase 4: Improve Test Quality
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08  

**Goals**:
- Focus tests on domain logic (coordination, response generation)
- Remove basic config/initialization tests
- Add comprehensive business flow tests
- Test error scenarios and edge cases

**Tasks**:
- [x] Review existing tests and identify business logic vs basic tests
- [x] Remove/consolidate basic functionality tests
- [x] Add comprehensive domain logic tests (channel pattern matching, coordination)
- [x] Add error scenario and edge case tests (command detection, rate limiting)
- [x] Ensure all tests pass
- [x] Commit changes

### Phase 5: Final Cleanup
**Status**: ✅ Complete  
**Started**: 2025-07-08  
**Completed**: 2025-07-08  
**Goals**:
- Remove unused code and clarify architecture
- Update documentation to reflect simplified architecture
- Fix deprecation warnings

**Tasks**:
- [x] Remove unused imports and classes
- [x] Remove dead code (message_processor.py and enhanced_message_handler)
- [x] Update CLAUDE.md documentation to reflect new architecture
- [x] Fix Pydantic deprecation warnings (migrate to V2 field_validator)
- [x] Final test run and commit

## Expected Benefits
- **Simpler architecture**: One way to run bots, clear code paths
- **Better type safety**: Catch errors at development time
- **Easier maintenance**: Less conditional logic and edge cases
- **Better tests**: Focus on actual business requirements
- **Cleaner code**: Remove legacy compatibility layers

## Notes
- Each phase includes updating tests and ensuring they pass
- Each phase ends with a commit
- PLAN.md is updated throughout the process