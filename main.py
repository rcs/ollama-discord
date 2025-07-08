"""Main entry point for Ollama Discord Bot."""

import sys
import asyncio
from pathlib import Path
from typing import Optional

import click

from src.config import load_config
from src.bot import DiscordBot
from src.bot_manager import BotManager
from src.multi_bot_config import multi_bot_config_manager


@click.command()
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    help='Path to configuration file (single bot or multi-bot)'
)
@click.option(
    '--multi-bot', '-m',
    is_flag=True,
    help='Run in multi-bot mode (automatically detects multi_bot.yaml)'
)
@click.option(
    '--list-configs', '-l',
    is_flag=True,
    help='List available configuration files'
)
@click.option(
    '--validate-config', '-v',
    is_flag=True,
    help='Validate configuration without starting bots'
)
@click.option(
    '--create-example',
    type=click.Path(path_type=Path),
    help='Create example multi-bot configuration file'
)
def main(config: Optional[Path], multi_bot: bool, list_configs: bool, 
         validate_config: bool, create_example: Optional[Path]):
    """Ollama Discord Bot - Run Discord bots with Ollama integration."""
    
    config_dir = Path("config")
    
    # Handle create example command
    if create_example:
        try:
            multi_bot_config_manager.create_example_config(str(create_example))
            click.echo(f"Created example multi-bot configuration: {create_example}")
            return
        except Exception as e:
            click.echo(f"Failed to create example configuration: {e}")
            sys.exit(1)
    
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
        click.echo("\nSingle bot configurations:")
        for config_file in sorted(config_files):
            if config_file.name not in ["example.yaml", "multi_bot.yaml"]:
                click.echo(f"  {config_file.name}")
        
        if (config_dir / "multi_bot.yaml").exists():
            click.echo("\nMulti-bot configurations:")
            click.echo("  multi_bot.yaml")
        
        return
    
    # Determine configuration mode
    if multi_bot or (config and config.name == "multi_bot.yaml"):
        # Multi-bot mode
        if not config:
            config = config_dir / "multi_bot.yaml"
            if not config.exists():
                click.echo("Multi-bot configuration not found: config/multi_bot.yaml")
                click.echo("Use --create-example to create an example configuration.")
                sys.exit(1)
        
        if validate_config:
            try:
                multi_config = multi_bot_config_manager.load_multi_bot_config(str(config))
                summary = multi_bot_config_manager.get_config_summary(multi_config)
                click.echo("✅ Multi-bot configuration is valid!")
                click.echo(f"Total bots: {summary['total_bots']}")
                click.echo(f"Enabled bots: {summary['enabled_bots']}")
                click.echo(f"Bot names: {', '.join(summary['bot_names'])}")
                if summary['potential_conflicts']:
                    click.echo("⚠️  Potential channel conflicts:")
                    for channel, bots in summary['potential_conflicts'].items():
                        click.echo(f"  {channel}: {', '.join(bots)}")
                return
            except Exception as e:
                click.echo(f"❌ Configuration validation failed: {e}")
                sys.exit(1)
        
        # Run multi-bot system
        try:
            click.echo(f"Starting multi-bot system with configuration: {config.name}")
            manager = BotManager(str(config))
            asyncio.run(manager.run())
        except KeyboardInterrupt:
            click.echo("\nShutting down multi-bot system...")
        except Exception as e:
            click.echo(f"Failed to start multi-bot system: {e}")
            sys.exit(1)
    
    else:
        # Single bot mode
        if not config:
            # Try to find a configuration file
            config_files = list(config_dir.glob("*.yaml"))
            config_files = [f for f in config_files if f.name not in ["example.yaml", "multi_bot.yaml"]]
            
            if not config_files:
                click.echo("No single-bot configuration files found. Use --list-configs to see available configs.")
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
        
        if validate_config:
            try:
                bot_config = load_config(str(config))
                click.echo("✅ Single-bot configuration is valid!")
                click.echo(f"Bot name: {bot_config.bot.name}")
                return
            except Exception as e:
                click.echo(f"❌ Configuration validation failed: {e}")
                sys.exit(1)
        
        # Run single bot
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