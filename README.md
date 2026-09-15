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

