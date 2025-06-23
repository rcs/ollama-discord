# Ollama Discord Bot

A Discord bot with Ollama integration supporting multiple configurations and AI-powered conversations.

## Features

- 🤖 Discord bot integration with Ollama AI models
- ⚙️ Multiple configuration support
- 🔒 Secure token management
- 🧪 Comprehensive testing suite
- 🔄 Automated CI/CD pipeline
- 📋 PR approval workflow

## Quick Start

### Prerequisites

- Python 3.10+
- Discord Bot Token
- Ollama server running locally or remotely

### Installation

1. Clone the repository:
```bash
git clone https://github.com/rcs/ollama-discord.git
cd ollama-discord
```

2. Install dependencies:
```bash
pip install -e .
```

3. Set up configuration:
```bash
cp config/example.yaml config/bot.yaml
# Edit config/bot.yaml with your settings
```

4. Run the bot:
```bash
python main.py
```

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

The bot supports multiple configuration files. See `config/example.yaml` for available options.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issues](https://github.com/rcs/ollama-discord/issues)
- 💬 [Discussions](https://github.com/rcs/ollama-discord/discussions) 