# Discord Application Setup Guide

This guide walks you through creating multiple Discord applications for the ollama-discord multi-bot system.

## Overview

The ollama-discord bot system requires **separate Discord applications** for each bot personality to prevent duplicate responses and ensure proper isolation.

### Required Applications

You need to create **3 Discord applications**:

1. **Sage Bot** - Philosophical discussions and wisdom
2. **Spark Bot** - Creative ideation and innovation  
3. **Logic Bot** - Technical analysis and research

## Step-by-Step Setup

### Step 1: Access Discord Developer Portal

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Log in with your Discord account
3. You should see the "Applications" dashboard

### Step 2: Create First Application (Sage Bot)

1. **Click "New Application"**
2. **Name**: `Sage Bot` (or your preferred name)
3. **Description**: `AI assistant for philosophical discussions and wisdom sharing`
4. **Click "Create"**

#### Configure Bot Settings

1. **Go to "Bot" section** in the left sidebar
2. **Click "Add Bot"** 
3. **Confirm** by clicking "Yes, do it!"

#### Bot Configuration

1. **Username**: Set to `Sage` or your preferred name
2. **Avatar**: Upload an appropriate image (optional)
3. **Public Bot**: ✅ Enabled (recommended)
4. **Require OAuth2 Code Grant**: ❌ Disabled
5. **Message Content Intent**: ✅ **REQUIRED** - Enable this!
6. **Server Members Intent**: ❌ Not needed
7. **Presence Intent**: ❌ Not needed

#### Copy Bot Token

1. **Under "Token" section**, click "Copy"
2. **Save this token** - you'll need it for `DISCORD_TOKEN_SAGE`
3. **⚠️ Keep this token secret!** Never share it publicly

### Step 3: Create Second Application (Spark Bot)

Repeat Step 2 with these changes:

1. **Name**: `Spark Bot`
2. **Description**: `AI assistant for creative ideation and innovation`
3. **Username**: Set to `Spark`
4. **Avatar**: Upload a creative/energetic image (optional)
5. **Copy the token** for `DISCORD_TOKEN_SPARK`

### Step 4: Create Third Application (Logic Bot)

Repeat Step 2 with these changes:

1. **Name**: `Logic Bot`
2. **Description**: `AI assistant for technical analysis and research`
3. **Username**: Set to `Logic`
4. **Avatar**: Upload a technical/analytical image (optional)
5. **Copy the token** for `DISCORD_TOKEN_LOGIC`

## Bot Permissions Setup

Each bot needs specific permissions in your Discord server.

### Required Permissions

For each bot application:

1. **Go to "OAuth2" > "URL Generator"**
2. **Scopes**: Select `bot`
3. **Bot Permissions**: Select these permissions:
   - ✅ **Send Messages** (Required)
   - ✅ **Read Message History** (Required)
   - ✅ **Use Slash Commands** (Optional)
   - ✅ **Add Reactions** (Optional)
   - ✅ **Embed Links** (Recommended)
   - ✅ **Attach Files** (Optional)

### Generate Invite Links

1. **Copy the generated URL** at the bottom
2. **Repeat for each bot** (Sage, Spark, Logic)
3. **Save these URLs** - you'll use them to invite bots to your server

Example invite URL format:
```
https://discord.com/api/oauth2/authorize?client_id=123456789012345678&permissions=2112&scope=bot
```

## Inviting Bots to Your Server

### Invite Each Bot

1. **Open the invite URL** for Sage Bot
2. **Select your Discord server**
3. **Review permissions** and click "Authorize"
4. **Complete captcha** if prompted
5. **Repeat for Spark and Logic bots**

### Verify Bots in Server

After inviting all bots, you should see:

- 🟢 **Sage** (offline until you start the bot)
- 🟢 **Spark** (offline until you start the bot)  
- 🟢 **Logic** (offline until you start the bot)

## Channel Configuration

### Set Up Channels

Create or designate channels for each bot personality:

```yaml
# Example channel assignments
bots:
  - name: "sage"
    channels: ["philosophy", "advice", "wisdom", "general"]
    
  - name: "spark"  
    channels: ["creative", "brainstorm", "ideas", "innovation"]
    
  - name: "logic"
    channels: ["tech-support", "research", "analysis", "data"]
```

### Channel Patterns

You can use wildcard patterns for flexible channel matching:

- `advice-*` matches `advice-general`, `advice-career`, etc.
- `tech-*` matches `tech-support`, `tech-discussion`, etc.
- `*brainstorm*` matches `brainstorm`, `team-brainstorm`, etc.

## Environment Configuration

### Create .env File

Create a `.env` file in your project root:

```env
# Discord Bot Tokens (replace with your actual tokens)
DISCORD_TOKEN_SAGE=YOUR_SAGE_BOT_TOKEN_HERE
DISCORD_TOKEN_SPARK=YOUR_SPARK_BOT_TOKEN_HERE
DISCORD_TOKEN_LOGIC=YOUR_LOGIC_BOT_TOKEN_HERE

# Ollama Configuration
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3
```

### Security Best Practices

1. **Never commit tokens to git**
   - Add `.env` to your `.gitignore`
   - Use environment variables in production

2. **Use unique tokens**
   - Each bot must have its own token
   - Never share tokens between bots

3. **Regenerate compromised tokens**
   - If a token is accidentally exposed, regenerate it immediately
   - Update your `.env` file with the new token

## Testing Your Setup

### Start the Bot System

```bash
# Ensure environment is activated
source bin/activate

# Start the multi-bot system
python main.py
```

### Verify Bots Are Online

In Discord, you should see all three bots come online:
- 🟢 **Sage** (online)
- 🟢 **Spark** (online)
- 🟢 **Logic** (online)

### Test Bot Responses

Send test messages in appropriate channels:

```
# In #philosophy channel
Hello Sage, what do you think about the meaning of life?

# In #creative channel  
Hey Spark, I need ideas for a new project!

# In #tech-support channel
Logic, can you help me debug this code?
```

Each bot should respond only in their designated channels.

## Troubleshooting

### Bot Not Responding

1. **Check token validity**
   ```bash
   # Verify tokens in .env file
   cat .env | grep DISCORD_TOKEN
   ```

2. **Check bot permissions**
   - Ensure bot has "Send Messages" permission
   - Verify bot can see the channel you're testing in

3. **Check channel configuration**
   - Verify channel names in `config/multi_bot.yaml`
   - Test with exact channel names first, then wildcards

### Multiple Bots Responding

This indicates **shared tokens** (critical issue):

1. **Verify unique tokens**
   ```bash
   # All three should be different
   echo $DISCORD_TOKEN_SAGE
   echo $DISCORD_TOKEN_SPARK  
   echo $DISCORD_TOKEN_LOGIC
   ```

2. **Check for copy-paste errors**
   - Ensure you copied the correct token for each bot
   - Regenerate tokens if necessary

### Bot Appears Offline

1. **Check bot status in Discord**
   - Bot should show as online when system is running

2. **Check application status**
   - Verify bot is enabled in Discord Developer Portal
   - Check "Message Content Intent" is enabled

3. **Check console output**
   ```bash
   # Look for connection errors
   python main.py
   ```

## Advanced Configuration

### Custom Bot Personalities

You can customize each bot's behavior by editing their individual config files:

- `config/sage.yaml` - Philosophical assistant
- `config/spark.yaml` - Creative catalyst  
- `config/logic.yaml` - Technical analyst

### Rate Limiting

Configure response coordination to prevent conflicts:

```yaml
global_settings:
  max_concurrent_responses: 2
  cooldown_period: 30  # seconds between responses
  response_delay: "1-3"  # random delay range
```

### Channel Overlap

Bots can share channels but will coordinate responses:

```yaml
bots:
  - name: "sage"
    channels: ["general", "philosophy"]  # Shares 'general'
    
  - name: "spark"
    channels: ["general", "creative"]    # Shares 'general'
```

The coordination system ensures only one bot responds per message in shared channels.

## Support

If you encounter issues:

1. **Check the main README.md** for additional troubleshooting
2. **Review logs** for error messages
3. **Create an issue** on GitHub with:
   - Bot configuration (redact tokens!)
   - Error messages
   - Steps to reproduce

## Next Steps

After completing this setup:

1. **✅ All bots are online and responding**
2. **✅ Each bot has unique Discord applications**  
3. **✅ Channel assignments are working**
4. **🚀 Your multi-bot system is ready!**

Consider exploring:
- **SQLite storage** for better performance
- **Custom system prompts** for each bot
- **Auto-start service** for production deployment