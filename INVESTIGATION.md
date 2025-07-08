# Service Startup Investigation

## Issue Description
The ollama-discord service is not starting properly. This document tracks the investigation and resolution.

## Investigation Timeline

### Initial Investigation - 2025-07-08

#### 1. Service Status Check
- [x] Check service status with systemctl - Service is running but failing
- [x] Review recent logs with journalctl - Multiple errors found
- [x] Check for any error messages or stack traces - Found several issues

#### 2. Log Analysis
```
Key errors found:
1. NameError: name 'Dict' is not defined in bot.py:119
2. NameError: name 'validator' is not defined in config.py:23
3. NameError: name 'validator' is not defined in multi_bot_config.py:20
4. Error: No such option: --multi-bot (repeated many times)
5. entr: cannot open 'src/message_processor.py': No such file or directory
```

#### 3. Findings
- Service files are using `--multi-bot` option which doesn't exist in main.py
- Missing imports for type hints (Dict should be imported from typing)
- Missing imports for Pydantic validators
- Development service references non-existent file `src/message_processor.py`
- The service is in a restart loop due to these errors

#### 4. Root Cause
- Code was left in a broken state with missing imports and incorrect service configuration
- Service files weren't updated when CLI options changed
- File references in development service weren't updated when files were removed/renamed 

## Resolution Plan
- [x] Identify the specific issue - Multiple issues found:
  - Service files using non-existent --multi-bot option
  - Path resolution bug in multi_bot_config.py doubling config paths
  - Missing imports (though these were already fixed in current code)
- [x] Implement fix:
  - Removed --multi-bot option from service files
  - Fixed path resolution bug in _validate_bot_configs method
- [x] Test the fix - Configuration validation now passes
- [x] Ensure service starts correctly - Service is running with all 3 bots
- [x] Document any configuration changes needed - No config changes needed

## Issues Fixed
1. **Service Command Error**: Removed `--multi-bot` option that doesn't exist
2. **Path Resolution Bug**: Fixed double path construction in multi_bot_config.py line 204
3. **Service Reinstallation**: Reinstalled service with corrected command

## Prevention Measures
- [x] Add better error handling - Already present in code
- [x] Improve logging for startup issues - Good logging already exists
- [ ] Add startup validation checks - Consider adding pre-flight checks
- [ ] Update documentation if needed - Update AGENTS.md with correct commands
- [ ] Add CI/CD tests for service startup
- [ ] Add validation test for multi-bot configuration loading
- [ ] Consider adding a --dry-run option to test configuration without starting bots

## Testing Checklist
- [x] Service starts successfully ✓
- [x] Bot connects to Discord ✓ (All 3 bots logged in)
- [ ] Bot responds to messages (needs manual testing)
- [x] No errors in logs during startup ✓
- [x] Configuration validation works ✓

## Final Status
The service is now running successfully with all 3 bots (sage, spark, logic) connected to Discord. The issue was caused by:
1. Outdated service files with incorrect CLI options
2. A path resolution bug that was doubling the config directory path

Both issues have been resolved and the service is operational.