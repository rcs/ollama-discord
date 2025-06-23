"""Main entry point for Ollama Discord Bot."""

import sys
import asyncio
from pathlib import Path
from typing import Optional

import click

from src.config import load_config
from src.bot import DiscordBot


@click.command()
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    help='Path to configuration file'
)
@click.option(
    '--list-configs', '-l',
    is_flag=True,
    help='List available configuration files'
)
def main(config: Optional[Path], list_configs: bool):
    """Ollama Discord Bot - Run Discord bots with Ollama integration."""
    
    config_dir = Path("config")
    
    if list_configs:
        """List available configuration files."""
        if not config_dir.exists():
            click.echo("No config directory found.")
            return
        
        config_files = list(config_dir.glob("*.yaml"))
        if not config_files:
            click.echo("No configuration files found in config/")
            return
        
        click.echo("Available configuration files:")
        for config_file in sorted(config_files):
            if config_file.name != "example.yaml":
                click.echo(f"  {config_file.name}")
        return
    
    if not config:
        # Try to find a configuration file
        config_files = list(config_dir.glob("*.yaml"))
        config_files = [f for f in config_files if f.name != "example.yaml"]
        
        if not config_files:
            click.echo("No configuration files found. Use --list-configs to see available configs.")
            click.echo("Copy config/example.yaml to create your own configuration.")
            sys.exit(1)
        
        if len(config_files) == 1:
            config = config_files[0]
            click.echo(f"Using configuration: {config.name}")
        else:
            click.echo("Multiple configuration files found. Please specify one with --config:")
            for config_file in sorted(config_files):
                click.echo(f"  {config_file.name}")
            sys.exit(1)
    
    try:
        # Load configuration
        bot_config = load_config(str(config))
        click.echo(f"Loaded configuration for bot: {bot_config.bot.name}")
        
        # Create and run bot
        bot = DiscordBot(bot_config)
        bot.run()
        
    except FileNotFoundError as e:
        click.echo(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to start bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()