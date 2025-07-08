# Duplicate Response Investigation Plan

## Issue Description
Users are seeing two responses for each message sent in Discord. This suggests either:
1. Multiple bot instances are responding to the same message
2. A single bot is processing messages twice
3. The bot is sending responses twice

## Investigation Strategy

### Phase 1: Enhanced Instrumentation
1. **Add Message Tracking**
   - Log message IDs when received
   - Track which bot instance processes each message
   - Log when responses are sent
   - Identify if same message ID appears multiple times

2. **Add Dynamic Logging**
   - Implement runtime log level control
   - Add debug commands to change log levels without restart
   - Create focused logging for message flow

3. **Add Processing Metrics**
   - Count messages received per bot
   - Count responses sent per bot
   - Track processing time per message
   - Monitor bot coordination

### Phase 2: Potential Causes to Investigate

1. **Multiple Bot Instances**
   - Are all 3 bots (sage, spark, logic) using the same Discord token?
   - Is each bot creating its own Discord client?
   - Check if multiple processes are running

2. **Message Processing Logic**
   - Is the orchestrator calling multiple bots?
   - Is the coordination logic working correctly?
   - Are channel patterns causing overlap?

3. **Discord Client Issues**
   - Is the on_message handler being called multiple times?
   - Are there multiple event registrations?
   - Is the bot responding to its own messages?

4. **Service Configuration**
   - Is the service starting multiple instances?
   - Is the development mode (with entr) causing issues?

### Phase 3: Debug Information to Collect

1. **Message Flow Logging**
   ```
   [RECEIVED] Message ID: xxx, Author: xxx, Channel: xxx, Bot: xxx
   [PROCESSING] Message ID: xxx, Bot: xxx, Should Handle: xxx
   [RESPONDING] Message ID: xxx, Bot: xxx, Response Length: xxx
   [SENT] Message ID: xxx, Bot: xxx
   ```

2. **Bot State Logging**
   ```
   [BOT_STATE] Active Bots: [sage, spark, logic]
   [BOT_STATE] Bot: sage, Channels: [...], Connected: True
   ```

3. **Coordination Logging**
   ```
   [COORDINATION] Message ID: xxx, Bots Considering: [...]
   [COORDINATION] Message ID: xxx, Bot Selected: xxx
   ```

## Implementation Plan

### Step 1: Create Debug Utilities
- Add a debug module with logging utilities
- Implement message tracking decorator
- Create runtime log level manager

### Step 2: Instrument Key Points
- Bot initialization
- Message reception
- Message processing decision
- Response generation
- Response sending

### Step 3: Add Debug Commands
- `!debug level <LEVEL>` - Change log level
- `!debug stats` - Show message processing stats
- `!debug bots` - Show active bot states
- `!debug trace <on/off>` - Enable detailed tracing

### Step 4: Test and Analyze
- Send test messages
- Collect debug logs
- Identify where duplication occurs
- Implement fix based on findings

## Success Criteria
- Can identify exactly where duplicate responses originate
- Can change log levels without restarting service
- Have clear visibility into message processing flow
- Can prevent duplicate responses

## Root Cause Analysis

### Issue Identified
The duplicate responses are caused by the multi-bot architecture where:
1. All 3 bots (sage, spark, logic) use the same Discord token
2. Each bot creates its own Discord client instance
3. Discord sends each message to all 3 client instances
4. Each bot processes the message independently

### Evidence
From the logs:
```
2025-07-08 10:33:13,219 - [LOGIC] INFO - Bot 'logic' logged in as Play Voices#9273
2025-07-08 10:33:13,352 - [SAGE] INFO - Bot 'sage' logged in as Play Voices#9273
2025-07-08 10:33:13,XXX - [SPARK] INFO - Bot 'spark' logged in as Play Voices#9273
```

All bots are logging in as the same Discord user (Play Voices#9273), creating 3 separate websocket connections to Discord.

### Architecture Mismatch
The current architecture assumes:
- Multiple bot personalities sharing infrastructure
- Each bot has its own Discord client
- Bots coordinate through the orchestrator

But Discord's model is:
- One bot token = one bot user = one connection
- Multiple connections with same token = duplicate messages

## Solution Options

### Option 1: Single Discord Client (Recommended)
Refactor to use a single Discord client shared by all bot personalities:
- One connection to Discord
- Message routing to different personalities based on channels/patterns
- Maintains multi-personality feature without duplicate messages

### Option 2: Multiple Bot Tokens
Use different Discord bot tokens for each personality:
- Requires creating 3 separate Discord applications
- Each bot truly independent
- More complex setup but cleaner separation

### Option 3: Message Deduplication
Keep current architecture but add deduplication:
- Track message IDs across all bots
- Only allow one bot to respond per message
- Works but is a band-aid solution

## Debug Features Added
1. **Message Tracking**: Tracks all messages received, processed, and responded to
2. **Debug Commands**: Runtime control of logging and debugging
   - `!debug stats` - Show processing statistics
   - `!debug duplicates` - Show duplicate responses
   - `!debug level <LEVEL>` - Change log level
3. **Dynamic Logging**: Can change log levels without restart
4. **Instrumentation**: Added tracking at key points in message flow