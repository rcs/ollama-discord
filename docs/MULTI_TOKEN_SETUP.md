# Multi-Token Discord Bot Setup Guide

## Overview
This guide explains how to set up multiple Discord bot tokens to run truly independent bot personalities, eliminating duplicate response issues.

## Why Multiple Tokens?

### The Problem
When multiple bot personalities share a single Discord token:
- Each personality creates its own Discord client connection
- Discord sends every message to all connections
- Users see duplicate/triplicate responses

### The Solution
Give each bot personality its own Discord application and token:
- Each bot connects independently
- Discord sends messages only to the intended bot
- No duplicate responses

## Setup Process

### Step 1: Create Multiple Discord Applications

1. **Go to Discord Developer Portal**
   - Visit https://discord.com/developers/applications
   - Log in with your Discord account

2. **Create Applications for Each Bot**
   
   For each bot personality (sage, spark, logic):
   
   a. Click "New Application"
   b. Name it appropriately (e.g., "Sage Bot", "Spark Bot", "Logic Bot")
   c. Go to the "Bot" section
   d. Click "Add Bot"
   e. Copy the bot token (you'll need this later)
   f. Configure bot settings:
      - Public Bot: OFF (recommended)
      - Requires OAuth2 Code Grant: OFF
      - Message Content Intent: ON (required)

3. **Set Bot Permissions**
   
   For each bot, in the OAuth2 > URL Generator section:
   - Scopes: Select "bot"
   - Bot Permissions:
     - Send Messages
     - Read Message History
     - Add Reactions (optional)
     - Use Slash Commands (optional)
   - Copy the generated URL

4. **Invite Bots to Your Server**
   - Use each bot's OAuth2 URL
   - Select your Discord server
   - Authorize the bot

### Step 2: Configure Environment Variables

#### Option A: Using .env File (Recommended)

1. **Update your .env file:**
```bash
# Individual bot tokens
DISCORD_TOKEN_SAGE=your_sage_bot_token_here
DISCORD_TOKEN_SPARK=your_spark_bot_token_here
DISCORD_TOKEN_LOGIC=your_logic_bot_token_here

# Optional: Default token for backward compatibility
DISCORD_TOKEN=your_default_token_here

# Ollama configuration (shared by all bots)
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

2. **Security Note:** Never commit .env files to version control!

#### Option B: System Environment Variables

```bash
# Linux/Mac
export DISCORD_TOKEN_SAGE="your_sage_bot_token_here"
export DISCORD_TOKEN_SPARK="your_spark_bot_token_here"
export DISCORD_TOKEN_LOGIC="your_logic_bot_token_here"

# Windows
set DISCORD_TOKEN_SAGE=your_sage_bot_token_here
set DISCORD_TOKEN_SPARK=your_spark_bot_token_here
set DISCORD_TOKEN_LOGIC=your_logic_bot_token_here
```

### Step 3: Update Configuration Files

#### Multi-Bot Configuration (`config/multi_bot.yaml`)

```yaml
# Bot-specific token mapping
discord_tokens:
  sage: "${DISCORD_TOKEN_SAGE}"
  spark: "${DISCORD_TOKEN_SPARK}"
  logic: "${DISCORD_TOKEN_LOGIC}"
  default: "${DISCORD_TOKEN}"  # Fallback for bots without specific tokens

# Bot configurations
bots:
  - name: "sage"
    config_file: "sage.yaml"
    channels: 
      - "philosophy"
      - "advice-*"
    # Token will be resolved from discord_tokens mapping
    
  - name: "spark"
    config_file: "spark.yaml"
    channels:
      - "creative"
      - "brainstorm*"
    
  - name: "logic"
    config_file: "logic.yaml"
    channels:
      - "tech-*"
      - "research"
```

#### Individual Bot Configurations

No changes needed! Individual bot configs (`sage.yaml`, etc.) will automatically use the token from the multi-bot configuration.

### Step 4: Verify Configuration

1. **Check token loading:**
```bash
# This will validate that all tokens are properly configured
bin/python main.py --validate-config -c config/multi_bot.yaml
```

2. **Start the bot system:**
```bash
bin/python main.py -c config/multi_bot.yaml
```

3. **Check logs for successful connections:**
```
2025-07-08 10:21:07,087 - [SAGE] INFO - Bot 'sage' logged in as Sage Bot#1234
2025-07-08 10:21:07,147 - [SPARK] INFO - Bot 'spark' logged in as Spark Bot#5678
2025-07-08 10:21:17,338 - [LOGIC] INFO - Bot 'logic' logged in as Logic Bot#9012
```

Note: Each bot should now show a different bot name/discriminator.

## Configuration Schema Options

### Option 1: Token Mapping (Recommended)
```yaml
discord_tokens:
  sage: "${DISCORD_TOKEN_SAGE}"
  spark: "${DISCORD_TOKEN_SPARK}"
  logic: "${DISCORD_TOKEN_LOGIC}"
  default: "${DISCORD_TOKEN}"
```

**Pros:**
- Clean separation of tokens from bot config
- Easy to see all tokens in one place
- Supports default fallback

### Option 2: Inline Tokens
```yaml
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"
```

**Pros:**
- Token directly associated with bot
- No separate mapping section needed

### Option 3: Mixed Approach
```yaml
# Default token for most bots
discord_token_default: "${DISCORD_TOKEN}"

bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"  # Override
    
  - name: "helper"
    config_file: "helper.yaml"
    # Uses default token
```

**Pros:**
- Flexible for mixed environments
- Backward compatible

## Troubleshooting

### Issue: "Invalid Token" Error
- Verify token is copied correctly (no extra spaces)
- Ensure bot was added to the application
- Check environment variable is set correctly

### Issue: Bot Not Responding
- Verify bot has correct permissions in Discord
- Check channel patterns match your server's channels
- Use `!debug stats` to see if messages are being received

### Issue: Still Seeing Duplicates
- Ensure each bot has a unique token
- Check logs to verify different bot names
- Use `!debug duplicates` to investigate

### Viewing Current Configuration
Use debug commands to verify token usage:
```
!debug stats
!debug loggers
```

## Security Best Practices

1. **Never share or commit tokens**
   - Use .env files (git ignored)
   - Use environment variables
   - Rotate tokens if exposed

2. **Limit bot permissions**
   - Only grant necessary permissions
   - Use role-based access in Discord

3. **Monitor bot activity**
   - Check logs regularly
   - Set up alerts for errors
   - Monitor for unexpected behavior

## Migration Guide

### From Single Token to Multiple Tokens

1. **Keep existing bot running** (optional)
2. **Create new Discord applications**
3. **Update .env with new tokens**
4. **Test with one bot first**
5. **Gradually migrate all bots**
6. **Remove old shared token**

### Rollback Plan
If issues occur:
1. Keep original token as `DISCORD_TOKEN`
2. Remove bot-specific tokens from config
3. Restart service

## Benefits of Multiple Tokens

1. **No duplicate responses** - Each bot truly independent
2. **Better organization** - Separate apps for each personality
3. **Improved debugging** - Clear which bot is responding
4. **Scalability** - Easy to add/remove bots
5. **Security** - Compromise of one token doesn't affect others