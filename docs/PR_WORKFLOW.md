# Pull Request Workflow Guide

## Overview
This repository uses a PR-based development workflow with automated CI/CD checks and required approvals.

## Branch Protection Rules Setup

To set up branch protection rules (do this once):

1. Go to your GitHub repository: https://github.com/rcs/ollama-discord
2. Navigate to **Settings** → **Branches**
3. Click **Add rule** for the `master` branch
4. Configure the following settings:
   - ✅ **Require a pull request before merging**
   - ✅ **Require approvals** (set to 1 or more)
   - ✅ **Dismiss stale PR approvals when new commits are pushed**
   - ✅ **Require status checks to pass before merging**
   - ✅ **Require branches to be up to date before merging**
   - ✅ **Include administrators**
   - ✅ **Restrict pushes that create files that are larger than 100 MB**

## Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes
- Write your code
- Add tests for new functionality
- Update documentation as needed

### 3. Run Local Checks
Before pushing, run these commands locally:
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Format code
black .

# Lint code
flake8 .

# Type checking
mypy src/

# Run tests
pytest

# Security checks
bandit -r src/
```

### 4. Commit and Push
```bash
git add .
git commit -m "feat: add your feature description"
git push -u origin feature/your-feature-name
```

### 5. Create a Pull Request
- Go to your GitHub repository
- Click **Compare & pull request** for your branch
- Fill out the PR template
- Request reviews from team members

### 6. CI/CD Checks
The following checks will run automatically:
- ✅ **Linting** (flake8)
- ✅ **Code formatting** (black)
- ✅ **Type checking** (mypy)
- ✅ **Unit tests** (pytest with coverage)
- ✅ **Security scanning** (bandit)

### 7. Code Review
- Address any review comments
- Make additional commits if needed
- All checks must pass before merging

### 8. Merge
Once approved and all checks pass:
- Click **Merge pull request**
- Delete the feature branch (automatic with our settings)

## Commit Message Convention

Use conventional commit messages:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for adding tests
- `chore:` for maintenance tasks

## Code Quality Standards

### Python Code Style
- Follow PEP 8 with 88 character line length
- Use type hints
- Write docstrings for functions and classes
- Keep functions small and focused

### Testing
- Aim for >80% code coverage
- Write unit tests for new functionality
- Include integration tests for complex features

### Security
- No hardcoded secrets in code
- Use environment variables for sensitive data
- Run security scans regularly

## Troubleshooting

### Common Issues

1. **CI fails on formatting**
   ```bash
   black .  # Fix formatting
   git add . && git commit -m "style: fix formatting"
   ```

2. **CI fails on linting**
   ```bash
   flake8 .  # Check issues
   # Fix the issues manually
   ```

3. **CI fails on type checking**
   ```bash
   mypy src/  # Check type issues
   # Add type hints where needed
   ```

4. **Tests failing locally**
   ```bash
   pip install -e ".[dev]"  # Ensure dev dependencies
   pytest -v  # Run with verbose output
   ```

## Getting Help

- Check the [GitHub Issues](https://github.com/rcs/ollama-discord/issues) for known problems
- Review the CI logs for detailed error messages
- Ask for help in PR reviews or team discussions 