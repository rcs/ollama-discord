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
```bash
# Install service (creates user service that starts on login)
bin/install-service.sh install

# Check service status
bin/install-service.sh status

# View logs
bin/install-service.sh logs

# Follow logs in real-time
bin/install-service.sh follow

# Uninstall service
bin/install-service.sh uninstall
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
- **Service fails to start**: Check logs with `bin/install-service.sh logs`
- **Bot token issues**: Ensure `DISCORD_TOKEN_BOT1` environment variable is set
- **Ollama connection**: Verify Ollama is running on port 11434
- **Permission issues**: Service runs as your user, no sudo required

## File Structure

```
ollama-discord/
├── main.py                   # CLI entry point
├── pyproject.toml            # Dependencies and project metadata
├── ollama-discord.service    # Systemd user service file
├── bin/
│   ├── install-service.sh    # Service installation script
│   └── python               # Virtual environment Python executable
├── src/
│   ├── __init__.py
│   ├── bot.py               # DiscordBot class with full functionality
│   └── config.py            # Configuration models and loading
├── config/
│   ├── example.yaml         # Template configuration
│   └── *.yaml              # Individual bot configurations
└── data/                   # Created automatically for conversation storage
```