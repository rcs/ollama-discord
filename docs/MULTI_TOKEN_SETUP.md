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
# Individual bot tokens (required - no default/shared tokens)
DISCORD_TOKEN_SAGE=your_sage_bot_token_here
DISCORD_TOKEN_SPARK=your_spark_bot_token_here
DISCORD_TOKEN_LOGIC=your_logic_bot_token_here

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
# Bot configurations with individual tokens
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"  # Required - each bot needs its own token
    channels: 
      - "philosophy"
      - "advice-*"
    
  - name: "spark"
    config_file: "spark.yaml"
    discord_token: "${DISCORD_TOKEN_SPARK}"  # Required - each bot needs its own token
    channels:
      - "creative"
      - "brainstorm*"
    
  - name: "logic"
    config_file: "logic.yaml"
    discord_token: "${DISCORD_TOKEN_LOGIC}"  # Required - each bot needs its own token
    channels:
      - "tech-*"
      - "research"
```

#### Individual Bot Configurations

Remove the token from individual bot configs (`sage.yaml`, etc.). The token is now only specified in `multi_bot.yaml`.

Before:
```yaml
# In sage.yaml
discord:
  token: "${DISCORD_TOKEN}"  # Remove this
  command_prefix: "!sage"
```

After:
```yaml
# In sage.yaml
discord:
  command_prefix: "!sage"  # Token removed, specified in multi_bot.yaml
```

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

## Configuration Schema

### Simple Per-Bot Tokens
Each bot must have its own token specified directly in the multi_bot.yaml:

```yaml
bots:
  - name: "sage"
    config_file: "sage.yaml"
    discord_token: "${DISCORD_TOKEN_SAGE}"  # Required
    channels: ["philosophy", "advice-*"]
    
  - name: "spark"
    config_file: "spark.yaml"
    discord_token: "${DISCORD_TOKEN_SPARK}"  # Required
    channels: ["creative", "brainstorm*"]
    
  - name: "logic"
    config_file: "logic.yaml"
    discord_token: "${DISCORD_TOKEN_LOGIC}"  # Required
    channels: ["tech-*", "research"]
```

**Benefits:**
- Simple and direct - token with bot configuration
- No indirection or lookups
- Clear which token belongs to which bot
- Easy to add/remove bots
- No backward compatibility complexity

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
- Check logs to verify different bot names (should see different #discriminators)
- Use `!debug duplicates` to investigate
- Verify you're not running the old single-token configuration

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

1. **Create new Discord applications** for each bot personality
2. **Update .env with new tokens**:
   ```bash
   DISCORD_TOKEN_SAGE=new_sage_token
   DISCORD_TOKEN_SPARK=new_spark_token
   DISCORD_TOKEN_LOGIC=new_logic_token
   ```
3. **Update multi_bot.yaml** to include discord_token for each bot
4. **Remove token from individual bot configs** (sage.yaml, etc.)
5. **Restart the service**
6. **Verify each bot shows different username** in logs

### No Rollback Support
This is a breaking change - there's no backward compatibility with single token configuration. Make sure you have all tokens ready before updating.

## Benefits of Multiple Tokens

1. **No duplicate responses** - Each bot truly independent
2. **Better organization** - Separate apps for each personality
3. **Improved debugging** - Clear which bot is responding
4. **Scalability** - Easy to add/remove bots
5. **Security** - Compromise of one token doesn't affect others