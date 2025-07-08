# AGENTS.md

## Git Workflow Requirements
- **ALWAYS create a feature branch** at the start of any work: `git checkout -b <type>/<description>`
- **ALWAYS create a PR** at the end of any work: `gh pr create --title "..." --body "..."`
- **NEVER commit directly to main branch**
- Branch types: `feature/`, `fix/`, `docs/`, `refactor/`, `test/`
- See `docs/PR_WORKFLOW.md` for detailed workflow

## Build/Test Commands
- **Run all tests**: `bin/python -m pytest tests/ -v`
- **Run single test file**: `bin/python -m pytest tests/test_bot.py -v`
- **Run specific test**: `bin/python -m pytest tests/test_bot.py::TestDiscordBot::test_on_message_with_orchestrator -v`
- **Test with coverage**: `bin/python -m pytest tests/ --cov=src --cov-report=html`
- **Lint with ruff**: `bin/python -m ruff check src/ tests/`
- **Format with black**: `bin/python -m black src/ tests/`
- **Type check**: `bin/python -m mypy src/`
- **Security scan**: `bin/python -m bandit -r src/`

## Code Style Guidelines
- **Python version**: 3.10+, use virtual environment `bin/python` (NOT system python)
- **Line length**: 88 characters (black/ruff configured)
- **Imports**: Standard library first, third-party, then local imports with blank lines between groups
- **Type hints**: Required for all function definitions (`disallow_untyped_defs = true`)
- **Docstrings**: Use triple quotes with Args/Returns sections for public functions
- **Error handling**: Use specific exception types, avoid bare `except:`
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
- **Async**: Use `AsyncMock` for testing async functions, mark tests with `@pytest.mark.asyncio`
- **Configuration**: Use Pydantic models with field validation for all config classes