#!/usr/bin/env python3
"""
Migration script to convert file-based conversation storage to SQLite.

This script reads existing file-based conversation data and imports it into
a SQLite database for improved performance and concurrent access.

Usage:
    python scripts/migrate_to_sqlite.py [options]

Options:
    --data-dir PATH     Path to existing file-based data directory
    --db-path PATH      Path to SQLite database file
    --dry-run          Show what would be migrated without actually doing it
    --help             Show this help message
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sqlite_storage import SQLiteMessageStorage


async def migrate_file_to_sqlite(data_dir: Path, db_path: Path, dry_run: bool = False) -> None:
    """Migrate file-based conversation data to SQLite."""
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return
    
    print(f"🔍 Scanning data directory: {data_dir}")
    
    # Find all bot directories
    bot_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    
    if not bot_dirs:
        print("❌ No bot directories found in data directory")
        return
    
    print(f"📁 Found {len(bot_dirs)} bot directories: {[d.name for d in bot_dirs]}")
    
    total_files = 0
    total_messages = 0
    
    if dry_run:
        print("🔥 DRY RUN - No changes will be made")
    
    # Process each bot directory
    for bot_dir in bot_dirs:
        bot_name = bot_dir.name
        print(f"\n🤖 Processing bot: {bot_name}")
        
        # Create SQLite storage for this bot
        if not dry_run:
            storage = SQLiteMessageStorage(
                bot_name=bot_name,
                db_path=str(db_path),
                session_timeout=3600
            )
            await storage._initialize_db()
        
        # Find all conversation files
        json_files = list(bot_dir.glob("**/*.json"))
        
        if not json_files:
            print(f"  📄 No conversation files found for {bot_name}")
            continue
        
        print(f"  📄 Found {len(json_files)} conversation files")
        total_files += len(json_files)
        
        # Process each conversation file
        for file_path in json_files:
            try:
                # Parse filename to extract channel and user info
                filename = file_path.stem
                if "_" in filename:
                    parts = filename.split("_")
                    if len(parts) >= 2:
                        channel_id = parts[0]
                        user_id = parts[1]
                    else:
                        print(f"  ⚠️  Skipping file with unexpected format: {filename}")
                        continue
                else:
                    print(f"  ⚠️  Skipping file with unexpected format: {filename}")
                    continue
                
                # Read conversation data
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract messages
                messages = data.get('messages', [])
                if not messages:
                    print(f"  📄 {filename}: No messages found")
                    continue
                
                print(f"  📄 {filename}: {len(messages)} messages")
                total_messages += len(messages)
                
                if dry_run:
                    continue
                
                # Import messages into SQLite
                for msg_data in messages:
                    try:
                        # Parse timestamp
                        timestamp_str = msg_data.get('timestamp', '')
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except:
                            timestamp = datetime.now()
                        
                        # Add message to SQLite
                        await storage.add_message(
                            channel_id=int(channel_id),
                            user_id=int(user_id),
                            role=msg_data.get('role', 'user'),
                            content=msg_data.get('content', ''),
                            bot_name=msg_data.get('bot_name', bot_name),
                            metadata=msg_data.get('metadata', {})
                        )
                        
                    except Exception as e:
                        print(f"  ❌ Error importing message: {e}")
                        continue
                
            except Exception as e:
                print(f"  ❌ Error processing file {file_path}: {e}")
                continue
    
    print(f"\n✅ Migration summary:")
    print(f"   📁 Bot directories: {len(bot_dirs)}")
    print(f"   📄 Conversation files: {total_files}")
    print(f"   💬 Total messages: {total_messages}")
    
    if dry_run:
        print(f"   🔥 DRY RUN - No changes were made")
        print(f"   💾 SQLite database would be created at: {db_path}")
    else:
        print(f"   💾 SQLite database created at: {db_path}")
        print(f"   🎉 Migration completed successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate file-based conversation storage to SQLite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/multi_bot_conversations"),
        help="Path to existing file-based data directory (default: data/multi_bot_conversations)"
    )
    
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/conversations.db"),
        help="Path to SQLite database file (default: data/conversations.db)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually doing it"
    )
    
    args = parser.parse_args()
    
    print("🚀 SQLite Migration Tool")
    print("=" * 50)
    print(f"📁 Data directory: {args.data_dir}")
    print(f"💾 SQLite database: {args.db_path}")
    print(f"🔥 Dry run: {'Yes' if args.dry_run else 'No'}")
    print("=" * 50)
    
    # Ensure database directory exists
    if not args.dry_run:
        args.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Run migration
    asyncio.run(migrate_file_to_sqlite(args.data_dir, args.db_path, args.dry_run))


if __name__ == "__main__":
    main()