# Startup Validation Plan

## Purpose
Prevent broken code from being committed by ensuring the service can start successfully before any changes are merged.

## Pre-Commit Checklist

### 1. Configuration Validation
- [ ] Run `bin/python main.py --validate-config -c config/multi_bot.yaml`
- [ ] Ensure all bot configuration files exist and are valid
- [ ] Check for any path resolution issues

### 2. Import Validation
- [ ] Run `bin/python -m py_compile src/*.py` to check for syntax errors
- [ ] Run `bin/python -c "import src.bot_manager; import src.multi_bot_config"`
- [ ] Ensure all imports are properly defined (no NameError on import)

### 3. Service File Validation
- [ ] Verify service files match current CLI options
- [ ] Check that all file paths in service files exist
- [ ] Ensure virtual environment paths are correct

### 4. Basic Startup Test
```bash
# Test basic startup without Discord connection
bin/python main.py --validate-config -c config/multi_bot.yaml

# Test imports
bin/python -c "from src.bot_manager import BotManager; print('Imports OK')"
```

## Automated Testing Recommendations

### 1. Add Pre-Commit Hook
Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
echo "Running pre-commit validation..."

# Check Python syntax
find src/ -name "*.py" -exec python -m py_compile {} \;

# Validate configuration
bin/python main.py --validate-config -c config/multi_bot.yaml

# Check imports
bin/python -c "import src.bot_manager; import src.multi_bot_config" || exit 1

echo "Pre-commit validation passed!"
```

### 2. Add GitHub Actions Workflow
Create `.github/workflows/startup-validation.yml`:
```yaml
name: Startup Validation

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .
    - name: Validate configuration
      run: |
        python main.py --validate-config -c config/multi_bot.yaml
    - name: Check imports
      run: |
        python -c "import src.bot_manager; import src.multi_bot_config"
```

### 3. Add Unit Tests
Create `tests/test_startup.py`:
```python
import pytest
from pathlib import Path
from src.multi_bot_config import multi_bot_config_manager
from src.config import load_config

def test_multi_bot_config_loads():
    """Test that multi-bot configuration loads without errors."""
    config_path = Path("config/multi_bot.yaml")
    if config_path.exists():
        config = multi_bot_config_manager.load_multi_bot_config(str(config_path))
        assert len(config.bots) > 0

def test_individual_bot_configs():
    """Test that individual bot configs load properly."""
    for config_file in Path("config").glob("*.yaml"):
        if config_file.name != "multi_bot.yaml":
            config = load_config(str(config_file))
            assert config.bot.name is not None
```

## Service Update Procedure

When updating service-related code:

1. **Before Making Changes**:
   - Document current working state
   - Note all CLI options and their usage

2. **After Making Changes**:
   - Update service files if CLI options change
   - Test with: `bin/python main.py --help`
   - Validate configuration still works
   - Reinstall service if needed: `scripts/install-service.sh install --dev`

3. **Before Committing**:
   - Run full validation checklist
   - Test service startup
   - Ensure no import errors

## Emergency Recovery

If service fails to start:

1. Check logs: `scripts/tail-logs.sh -n 100`
2. Validate configuration: `bin/python main.py --validate-config`
3. Test imports manually: `bin/python -c "import src.bot_manager"`
4. Check service file: `cat ~/.config/systemd/user/ollama-discord.service`
5. Reinstall if needed: `scripts/install-service.sh install --dev`

## Key Areas to Monitor

1. **CLI Changes**: Any changes to main.py arguments
2. **Import Changes**: New dependencies or moved modules
3. **Path Changes**: File relocations or renames
4. **Config Schema**: Changes to configuration structure
5. **Service Dependencies**: Changes to startup requirements