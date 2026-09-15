# Chat Referee

A Discord bot that settles arguments by reading the channel history and issuing a courtroom ruling with receipts.

Someone claims they never agreed to pay for the Uber. Run `/referee who said they'd pay for the uber` and the court delivers a verdict, quotes the evidence with timestamps, assigns a confidence score, and hands down a sentence.

## Usage

```
/referee dispute:<the question> [limit:<messages>]
```

| Argument | Required | Default | Notes |
|---|---|---|---|
| `dispute` | yes | — | The question being settled |
| `limit` | no | 300 | How many recent messages to review (1–500) |

The bot reads the channel it was invoked in. It skips bot messages and empty content, then sends the transcript to the model with the dispute.

Rulings are delivered in English. Evidence is quoted verbatim in whatever language it was written in.

## Privacy

Message history is fetched from the Discord API at query time and held in memory for the duration of the request. Nothing is written to disk and nothing is stored between invocations.

The transcript is sent to Google's Gemini API to produce the ruling. Don't run this in a channel where that matters.

## Stack

- `discord.py` — slash command, history fetch, embed rendering
- `google-genai` — verdict generation via `gemini-3.6-flash`
- Whole transcript goes into context. No embeddings, no vector store, no retrieval step: 300 messages is roughly 3k tokens against a million-token window.

## Setup

**1. Create the Discord application**

At [discord.com/developers](https://discord.com/developers/applications): New Application, then the Bot tab.

- Enable **Message Content Intent** under Privileged Gateway Intents. Without it, `channel.history()` returns empty strings.
- Reset Token and save it. It's shown once.

**2. Invite the bot**

OAuth2 → URL Generator. Scopes `bot` and `applications.commands`. Permissions:

- Send Messages
- Embed Links
- Read Message History

Permissions integer `83968`. Nothing else is needed, and asking for more is a bad look on a bot that reads private conversations.

**3. Get a Gemini API key**

[aistudio.google.com/apikey](https://aistudio.google.com/apikey). The free tier is rate limited per minute, which is fine for a single server.

**4. Run it**

```bash
python -m venv .venv
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```
DISCORD_TOKEN=your_token_here
GEMINI_API_KEY=your_key_here
```

```bash
python bot.py
```

Slash commands can take a few minutes to appear the first time they sync. That's Discord, not a bug.

## Deployment

Runs as a worker process, not a web service. There's no HTTP server here and a platform expecting an open port will mark it unhealthy.

On Railway: deploy from the GitHub repo, then set `DISCORD_TOKEN` and `GEMINI_API_KEY` in the Variables tab. `.env` stays out of the repo.

`runtime.txt` pins Python 3.12, since 3.14 images aren't widely available yet.

## Known limitations

**Quotes aren't verified.** The system prompt instructs the model not to fabricate evidence, and it largely complies, but nothing structurally prevents it. For a bot whose entire premise is receipts, "largely" is the wrong standard. A substring check of each returned quote against the transcript would make fabrication impossible rather than merely discouraged.

**Recall degrades before context does.** Raising `limit` past a few hundred messages doesn't reliably improve rulings. The model has to find three relevant quotes in a much larger haystack, and precision drops well before the window fills. If large rulings come back mushy, that's the argument for adding retrieval.

**Wrong rulings are public.** One bad verdict in a busy server is visible to everyone in it. The format is deliberately absurd so that being wrong reads as part of the joke.
