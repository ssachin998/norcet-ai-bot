# NORCET AI Quiz Bot

A production-ready Telegram bot for **AIIMS NORCET** (Nursing Officer Recruitment Common Eligibility Test) preparation. Automatically posts AI-generated MCQ quiz polls with detailed explanations every day.

## Features

- **Automated Daily Sessions**: Posts 50 MCQ quiz polls at 7:00 AM and 7:00 PM IST
- **AI-Powered Questions**: Uses Google Gemini 2.5 Flash to generate NORCET-level questions
- **Anonymous Quiz Polls**: Each question is an interactive Telegram quiz poll
- **Detailed Explanations**: After each poll, sends rationale for ALL four options
- **NORCET Pearls**: High-yield clinical pearls with every question
- **Genuine References**: Only standard textbooks (Robbins, KDT, Apurba Sastry, Brunner, AIIMS Protocol, WHO, CDC)
- **Topic Rotation**: Reads topics from `topics.txt` and cycles through automatically
- **Duplicate Detection**: SHA-256 hashing prevents repeated questions
- **Progress Persistence**: Remembers topic progress across restarts (SQLite)
- **Admin Commands**: `/status`, `/nexttopic`, `/skip`, `/postnow`, `/help`, `/stats`, `/topics`, `/schedule`
- **Statistics**: Daily, weekly, and monthly reporting
- **Rate Limit Handling**: Respects Telegram API limits with automatic retry
- **Graceful Shutdown**: Clean handling of SIGINT/SIGTERM

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Telegram API | python-telegram-bot v22+ |
| AI Model | Google Gemini 2.5 Flash |
| Scheduling | APScheduler |
| Database | SQLite (WAL mode) |
| Config | python-dotenv |
| Deployment | Docker, Railway, Render |

## Project Structure

```
NORCET-AI-BOT/
├── bot.py              # Main entry point + admin command handlers
├── config.py           # Configuration management (env vars)
├── scheduler.py        # APScheduler for 7AM/7PM sessions
├── database.py         # SQLite schema, CRUD operations
├── gemini.py           # Google Gemini API client
├── telegram_poll.py    # Poll posting + explanation messages
├── topic_manager.py    # Topic rotation and progress tracking
├── duplicate_checker.py # Duplicate question detection
├── logger.py           # Structured logging (console + file)
├── utils.py            # Helper functions (HTML escape, retry, etc.)
├── topics.txt          # NORCET topic list
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker container configuration
├── railway.json        # Railway deployment config
├── .env.example        # Environment variable template
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Prerequisites

1. **Python 3.12+** installed
2. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
3. **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/apikey)
4. **Telegram Channel or Group** where polls will be posted

## Installation

### 1. Clone or Download the Project

```bash
git clone <your-repo-url> NORCET-AI-BOT
cd NORCET-AI-BOT
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
BOT_TOKEN=7123456789:AAH-your-bot-token
ADMIN_CHAT_IDS=123456789
QUIZ_CHAT_ID=@your_channel_username
CHANNEL_ID=@your_channel_username
GEMINI_API_KEY=AIza-your-gemini-key
```

### 5. Run the Bot

```bash
python bot.py
```

## Configuration Reference

### Getting a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token (format: `7123456789:AAH...`)

### Getting a Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with a Google account
3. Click **"Create API Key"**
4. Copy the key

### Finding Your Channel/Chat ID

1. Add your bot to the channel/group as an **administrator**
2. Post a message in the channel
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Find the `chat.id` field in the response
5. For public channels, use `@channelname` (with the @)
6. For private channels/groups, use the numeric ID (e.g., `-1001234567890`)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_TOKEN` | (required) | Telegram Bot token from BotFather |
| `ADMIN_CHAT_IDS` | (all users) | Comma-separated admin Telegram user IDs |
| `QUIZ_CHAT_ID` | (required) | Channel/group ID where polls are posted |
| `CHANNEL_ID` | (empty) | Channel ID for notifications |
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash-preview-04-17` | Gemini model to use |
| `TIMEZONE` | `Asia/Kolkata` | Scheduler timezone |
| `MORNING_HOUR` | `7` | Morning session hour |
| `MORNING_MINUTE` | `0` | Morning session minute |
| `EVENING_HOUR` | `19` | Evening session hour (24h format) |
| `EVENING_MINUTE` | `0` | Evening session minute |
| `QUESTIONS_PER_SESSION` | `50` | Questions per session |
| `POLL_OPEN_DURATION` | `120` | Poll open duration in seconds |
| `BATCH_SIZE` | `10` | Questions per Gemini API call |
| `GEMINI_TEMPERATURE` | `0.9` | Gemini generation temperature (0.0-1.0) |
| `GEMINI_MAX_RETRIES` | `3` | Max API retry attempts |
| `TELEGRAM_RATE_LIMIT` | `0.7` | Delay between Telegram messages (seconds) |
| `MAX_TELEGRAM_RETRIES` | `3` | Max Telegram API retry attempts |
| `DB_PATH` | `norcet_bot.db` | SQLite database file path |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FILE` | `norcet_bot.log` | Log file path |
| `DIFFICULTY_EASY` | `0.2` | Fraction of easy questions (20%) |
| `DIFFICULTY_MODERATE` | `0.6` | Fraction of moderate questions (60%) |
| `DIFFICULTY_HARD` | `0.2` | Fraction of hard questions (20%) |

## Admin Commands

All commands are restricted to admin users (configured via `ADMIN_CHAT_IDS`).

| Command | Description |
|---------|-------------|
| `/start` | Start the bot, see welcome message |
| `/help` | Show all available commands |
| `/status` | View bot status, current topic, statistics |
| `/nexttopic` | Complete current topic, advance to next |
| `/skip` | Skip current topic without marking complete |
| `/postnow` | Post a quiz session immediately |
| `/stats today` | View today's question statistics |
| `/stats week` | View this week's statistics |
| `/stats month` | View this month's statistics |
| `/topics` | List all topics with completion status |
| `/schedule` | View upcoming scheduled sessions |

## Database Schema

The bot uses SQLite with WAL (Write-Ahead Logging) mode for reliability.

### Tables

- **questions**: All posted quiz questions with full metadata
- **topic_progress**: Current position in topics list
- **post_history**: Log of every quiz session
- **duplicates**: Hash-based duplicate detection index
- **daily_stats**: Per-day statistics aggregation

## Deployment

### Docker

```bash
# Build the image
docker build -t norcet-bot .

# Run the container
docker run -d \
  --name norcet-bot \
  --env-file .env \
  -v norcet-data:/app/data \
  norcet-bot

# View logs
docker logs -f norcet-bot

# Stop
docker stop norcet-bot
```

### Railway

1. Create a new project on [Railway.app](https://railway.app)
2. Connect your GitHub repository (or use `railway init`)
3. Add environment variables in Railway dashboard
4. Railway auto-detects Python and deploys using `railway.json`
5. Add a persistent volume for `/app/data` to persist the SQLite database

### Render

1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python bot.py`
5. Add environment variables in the Render dashboard
6. Use a free Redis instance or persistent disk for the database

### Important for Cloud Deployment

- The SQLite database file must be on a **persistent volume** or it will be lost on restart
- Set `DB_PATH` to a directory that persists (e.g., `/app/data/norcet_bot.db` on Railway)
- Ensure the bot token and API key are set as **environment variables**, not in the code

## Question Quality

Questions are generated by Google Gemini 2.5 Flash with a carefully designed prompt that ensures:

- **NORCET-style questions** resembling AIIMS previous year papers
- **Clinical application** testing, not just factual recall
- **Difficulty distribution**: 20% Easy, 60% Moderate, 20% Hard
- **Detailed rationales** for every option (2-4 sentences each)
- **Genuine textbook references** from standard nursing/medical books
- **No fabricated references** — only verified sources
- **No duplicates** — SHA-256 hashing prevents repetition

## Troubleshooting

### Bot doesn't start

- Verify `BOT_TOKEN` is correct
- Check that `GEMINI_API_KEY` is valid
- Ensure `QUIZ_CHAT_ID` is properly formatted

### Questions not posting

- Verify the bot is an **admin** in the target channel/group
- Check the log file (`norcet_bot.log`) for errors
- Ensure the Gemini API key has quota remaining

### Duplicate questions appearing

- The duplicate checker uses SHA-256 hashing
- Clear the duplicates table if needed: delete from the database manually
- The bot filters duplicates at both generation time and post time

### Rate limit errors

- Telegram limits: ~20 messages/minute per group, ~30 messages/second globally
- The bot includes automatic rate limiting (`TELEGRAM_RATE_LIMIT`)
- Failed messages are retried automatically up to `MAX_TELEGRAM_RETRIES`

## License

This project is for educational purposes. Use responsibly.

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for the Telegram Bot framework
- [Google Gemini API](https://ai.google.dev/) for AI question generation
- [APScheduler](https://apscheduler.readthedocs.io/) for scheduling
- All NORCET aspirants preparing for AIIMS nursing entrance examinations
