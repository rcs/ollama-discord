# Ollama Discord Bot

A Discord bot with Ollama integration supporting multiple AI personalities with independent Discord connections.

## Features

- 🤖 **Multi-Bot Support**: Run multiple AI personalities (sage, spark, logic) simultaneously
- 🔑 **Independent Discord Tokens**: Each bot uses its own Discord application and token
- 🗄️ **Dual Storage Options**: Choose between file-based or SQLite storage
- ⚙️ **Flexible Configuration**: YAML-based configuration with environment variable support
- 🔒 **Secure Token Management**: Environment-based token configuration
- 🧪 **Comprehensive Testing**: 200+ tests with full coverage
- 🔄 **Bot Coordination**: Intelligent coordination prevents response conflicts
- 📋 **Session Management**: Automatic conversation session handling

## Quick Start

### Prerequisites

- Python 3.10+
- **Multiple Discord Bot Tokens** (one per bot personality)
- Ollama server running locally or remotely
- Discord server with appropriate bot permissions

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/rcs/ollama-discord.git
cd ollama-discord
```

2. **Set up virtual environment:**
```bash
source bin/activate  # Virtual environment is pre-configured
```

3. **Install dependencies:**
```bash
pip install -e .
```

4. **Create Discord Applications:**
   
   **⚠️ IMPORTANT:** Each bot personality requires its own Discord application and token.
   
   - Visit [Discord Developer Portal](https://discord.com/developers/applications)
   - Create 3 separate applications (sage, spark, logic)
   - Copy the bot tokens for each application
   - See [Discord Application Setup Guide](#discord-application-setup) below

5. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your Discord tokens:
```
```env
DISCORD_TOKEN_SAGE=your_sage_bot_token_here
DISCORD_TOKEN_SPARK=your_spark_bot_token_here  
DISCORD_TOKEN_LOGIC=your_logic_bot_token_here
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

6. **Configure multi-bot setup:**
```bash
# The multi_bot.yaml is already configured - just update channels if needed
nano config/multi_bot.yaml
```

7. **Start Ollama server:**
```bash
# Make sure Ollama is running
ollama serve
```

8. **Run the multi-bot system:**
```bash
python main.py
```

### Discord Application Setup

Each bot personality needs its own Discord application:

#### Creating Discord Applications

1. **Go to [Discord Developer Portal](https://discord.com/developers/applications)**
2. **Create three applications:**
   - `Sage Bot` - For philosophical discussions
   - `Spark Bot` - For creative ideation  
   - `Logic Bot` - For technical analysis

3. **For each application:**
   - Go to "Bot" section
   - Click "Add Bot"
   - Copy the bot token
   - Enable "Message Content Intent"
   - Set appropriate permissions

#### Bot Permissions

Each bot needs these permissions:
- ✅ Send Messages
- ✅ Read Message History
- ✅ Use Slash Commands (optional)
- ✅ Add Reactions (optional)

#### Inviting Bots to Server

Generate invite links for each bot with appropriate permissions:
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=2048&scope=bot
```

Replace `YOUR_BOT_CLIENT_ID` with each bot's client ID from the Developer Portal.

## Development

### Setting up the development environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .

# Lint code
flake8 .

# Type checking
mypy src/
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Commit your changes: `git commit -m 'feat: add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

See [docs/PR_WORKFLOW.md](docs/PR_WORKFLOW.md) for detailed contribution guidelines.

## Configuration

### Multi-Bot Configuration

The system uses `config/multi_bot.yaml` as the main configuration file:

```yaml
# Multi-bot configuration
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"
    channels: ["philosophy", "advice-*", "general"]
    
  - name: "spark"  
    config_file: "spark.yaml"
    discord_token: "${DISCORD_TOKEN_SPARK}"
    channels: ["creative", "brainstorm*", "ideas"]
    
  - name: "logic"
    config_file: "logic.yaml" 
    discord_token: "${DISCORD_TOKEN_LOGIC}"
    channels: ["tech-*", "research", "analysis"]

# Global settings
global_settings:
  storage_type: "file"  # or "sqlite"
  storage_path: "./data/multi_bot_conversations"
  context_depth: 10
  max_concurrent_responses: 2
```

### Storage Options

#### File Storage (Default)
```yaml
global_settings:
  storage_type: "file"
  storage_path: "./data/multi_bot_conversations"
```

#### SQLite Storage (Recommended)
```yaml
global_settings:
  storage_type: "sqlite"
  storage_path: "./data/conversations.db"
  session_timeout: 3600
```

#### Migrating to SQLite
```bash
# Preview migration
bin/python scripts/migrate_to_sqlite.py --dry-run

# Perform migration
bin/python scripts/migrate_to_sqlite.py

# Update config to use SQLite
# Change storage_type: "sqlite" in config/multi_bot.yaml
```

### Individual Bot Configuration

Each bot has its own configuration file (`sage.yaml`, `spark.yaml`, `logic.yaml`) defining:

- **System Prompt**: Bot personality and behavior
- **Ollama Settings**: Model, base URL, timeout
- **Message Settings**: Max length, typing indicators
- **Storage Settings**: Max history, path preferences

See `config/example.yaml` for all available options.

## Troubleshooting

### Common Issues

#### "No module named 'discord'" Error
```bash
# Make sure you're using the virtual environment
source bin/activate
pip install -e .
```

#### "Invalid Discord Token" Error
- ✅ Verify tokens are correct in `.env` file
- ✅ Check that token environment variables match config references
- ✅ Ensure each bot has a unique, valid Discord token
- ✅ Verify "Message Content Intent" is enabled for each bot

#### Bots Not Responding in Channels
- ✅ Check channel names in `config/multi_bot.yaml` match your Discord channels
- ✅ Verify bots have "Send Messages" permission in those channels
- ✅ Use `*` wildcards for channel patterns (e.g., `tech-*` matches `tech-support`)
- ✅ Check bot is online in Discord server

#### "Connection to Ollama failed"
```bash
# Start Ollama server
ollama serve

# Test connection
curl http://localhost:11434/api/tags

# Check Ollama model availability  
ollama list
```

#### Duplicate Responses
- ✅ **CRITICAL**: Each bot must have its own unique Discord token
- ✅ Do not share tokens between bot personalities
- ✅ If seeing duplicates, verify tokens are different

#### SQLite Migration Issues
```bash
# Check current data structure
ls -la data/multi_bot_conversations/

# Run migration with dry-run first
bin/python scripts/migrate_to_sqlite.py --dry-run

# Check migration output for errors
bin/python scripts/migrate_to_sqlite.py --data-dir ./data/old --db-path ./data/new.db
```

#### Service Auto-Start Issues
```bash
# Check service status
scripts/install-service.sh status

# View service logs
scripts/install-service.sh logs

# Restart service
scripts/install-service.sh uninstall
scripts/install-service.sh install
```

### Getting Help

- 📖 **Documentation**: See `CLAUDE.md` for detailed technical documentation
- 🔧 **Configuration Help**: Check `config/example.yaml` for all options
- 🐛 **Report Issues**: [GitHub Issues](https://github.com/rcs/ollama-discord/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/rcs/ollama-discord/discussions)

### Debug Commands

The bot includes built-in debug commands (see `docs/DEBUG_COMMANDS.md`):

```bash
# In Discord, use these commands (if enabled):
!debug status    # Show bot status
!debug config    # Show configuration
!debug tokens    # Show which tokens are being used (tokens redacted)
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issues](https://github.com/rcs/ollama-discord/issues)
- 💬 [Discussions](https://github.com/rcs/ollama-discord/discussions) 