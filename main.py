"""Main entry point for Ollama Discord Bot - Multi-bot mode only."""

import sys
import asyncio
from pathlib import Path
from typing import Optional

import click

from src.bot_manager import BotManager
from src.multi_bot_config import multi_bot_config_manager


@click.command()
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    help='Path to multi-bot configuration file (defaults to config/multi_bot.yaml)'
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
def main(config: Optional[Path], validate_config: bool, create_example: Optional[Path]):
    """Ollama Discord Bot - Multi-bot system with Ollama integration."""
    
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
    
    # Determine configuration file
    if not config:
        config = config_dir / "multi_bot.yaml"
        if not config.exists():
            click.echo("Multi-bot configuration not found: config/multi_bot.yaml")
            click.echo("Use --create-example config/multi_bot.yaml to create an example configuration.")
            sys.exit(1)
    
    # Validate configuration if requested
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


if __name__ == "__main__":
    main()