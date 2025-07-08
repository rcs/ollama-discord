# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord bot system with Ollama integration that supports multiple bot configurations. Each bot can have different models, prompts, storage settings, and Discord configurations. The system supports conversation history, rate limiting, and flexible configuration management.

## Architecture

- **Modular design**: Code organized in `src/` package with separate concerns
- **Configuration-driven**: YAML-based configuration with Pydantic validation
- **Multiple bot support**: Each bot runs with its own configuration
- **Conversation storage**: Optional persistent conversation history per user/channel
- **Rate limiting**: Configurable request rate limiting per user

## Key Components

- `src/bot.py`: Main `DiscordBot` class with conversation storage and rate limiting
- `src/config.py`: Configuration management with Pydantic models and validation
- `main.py`: CLI entry point for running bots with config selection
- `config/`: Directory containing YAML configuration files

## Development Setup

1. **Activate virtual environment**:
   ```bash
   source bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

3. **Create configuration**:
   ```bash
   cp config/example.yaml config/mybot.yaml
   # Edit config/mybot.yaml with your settings
   ```

4. **Run a bot**:
   ```bash
   python main.py --config config/mybot.yaml
   # Or auto-select if only one config exists:
   python main.py
   ```

## Development Commands

- **List available configs**: `python main.py --list-configs`
- **Install in development mode**: `pip install -e .`
- **Run specific bot**: `python main.py -c config/bot1.yaml`
- **Install dev dependencies**: `pip install -e ".[dev]"`

## Configuration Structure

Each bot configuration (`config/*.yaml`) includes:

- **bot**: Name and description
- **discord**: Token and command prefix  
- **ollama**: Model, base URL, timeout settings
- **system_prompt**: Custom system prompt for the bot
- **storage**: Conversation history settings (path, max history)
- **message**: Message handling (max length, typing indicator)
- **rate_limit**: Request rate limiting configuration
- **logging**: Logging level and format

Environment variables can be used in configs with `${VAR_NAME}` syntax.

### Environment File (.env)

The bot automatically loads environment variables from a `.env` file in the project root if it exists:

```bash
# Copy the example and customize
cp .env.example .env
# Edit .env with your actual values
```

**Key environment variables:**
- `DISCORD_TOKEN`: Your Discord bot token (required)
- `OLLAMA_BASE_URL`: Ollama server URL (optional, defaults in config)
- `OLLAMA_MODEL`: Default model name (optional, defaults in config)

**Example .env:**
```
DISCORD_TOKEN=your_discord_bot_token_here
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

All configuration files use `${DISCORD_TOKEN}` to read the token from environment variables or the .env file.

## Dependencies

- `discord.py>=2.3.0`: Discord API wrapper
- `requests>=2.31.0`: HTTP library for Ollama API calls
- `pydantic>=2.0.0`: Configuration validation
- `pyyaml>=6.0.0`: YAML configuration parsing
- `click>=8.0.0`: CLI interface

## External Requirements

- Ollama must be running locally (default: port 11434)
- Discord bot tokens configured in YAML files or environment variables
- Proper Discord bot permissions (read messages, send messages)

## Auto-Start Service

To run the bot automatically when you log in, use the systemd user service:

### Installation

#### Production Mode (Default)
```bash
# Install service (creates user service that starts on login)
scripts/install-service.sh install

# Check service status
scripts/install-service.sh status

# View logs
scripts/install-service.sh logs

# Follow logs in real-time
scripts/install-service.sh follow

# Uninstall service
scripts/install-service.sh uninstall
```

#### Development Mode (Auto-Restart on File Changes)
```bash
# Install development service with auto-restart
scripts/install-service.sh install --dev

# The bot will automatically restart when you modify:
# - Any .py files in src/
# - main.py
# - Any .yaml files in config/
```

**Development mode requirements:**
- Ubuntu/Debian: `sudo apt install entr`
- macOS: `brew install entr`
- Arch Linux: `sudo pacman -S entr`

### Log Monitoring

Use the dedicated log tailing script for easy log monitoring:

```bash
# Show recent logs (last 50 lines)
scripts/tail-logs.sh

# Follow logs in real-time
scripts/tail-logs.sh --follow

# Show last 100 lines
scripts/tail-logs.sh -n 100

# Follow logs starting with last 20 lines
scripts/tail-logs.sh -f -n 20

# Show service information only
scripts/tail-logs.sh --info
```

**Quick shortcuts:**
```bash
scripts/install-service.sh logs    # Show recent logs (via service script)
scripts/install-service.sh follow  # Follow logs (via service script)
scripts/tail-logs.sh -f            # Follow logs (dedicated script)
```

### Manual Service Management
```bash
# Start service manually
systemctl --user start ollama-discord.service

# Stop service
systemctl --user stop ollama-discord.service

# Check status
systemctl --user status ollama-discord.service

# View logs
journalctl --user -u ollama-discord.service

# Follow logs
journalctl --user -u ollama-discord.service -f
```

### Troubleshooting
- **Service fails to start**: Check logs with `scripts/install-service.sh logs`
- **Bot token issues**: Ensure `DISCORD_TOKEN` is set in `.env` file or environment
- **Missing .env file**: Copy `.env.example` to `.env` and add your Discord token
- **Ollama connection**: Verify Ollama is running on port 11434
- **Permission issues**: Service runs as your user, no sudo required
- **Development mode fails**: Ensure `entr` is installed (see installation commands above)
- **Auto-restart not working**: Check that files are being watched with `find src/ main.py config/ -name "*.py" -o -name "*.yaml"`

## File Structure

```
ollama-discord/
├── main.py                   # CLI entry point
├── pyproject.toml            # Dependencies and project metadata
├── ollama-discord.service    # Systemd user service file (production)
├── ollama-discord-dev.service # Systemd user service file (development with auto-restart)
├── scripts/
│   ├── install-service.sh    # Service installation script
│   ├── tail-logs.sh          # Log monitoring script
│   └── setup_branch_protection.py  # Existing script
├── bin/                     # Virtual environment executables (gitignored)
├── src/
│   ├── __init__.py
│   ├── bot.py               # DiscordBot class with full functionality
│   └── config.py            # Configuration models and loading
├── config/
│   ├── example.yaml         # Template configuration
│   └── *.yaml              # Individual bot configurations
└── data/                   # Created automatically for conversation storage
```

## Development Guidelines

### File Operations
⚠️ **IMPORTANT**: Always check file existence before writing to any file you haven't created in the current session:

```python
# Good: Check existence first
if Path("file.txt").exists():
    # Read first, then edit
    content = Path("file.txt").read_text()
    # Make changes...

# Bad: Writing without checking
Path("file.txt").write_text("new content")  # May overwrite existing file
```

Use `Read` tool before `Edit` or `Write` tools for any file that might already exist.