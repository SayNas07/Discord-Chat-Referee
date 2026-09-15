import asyncio
import json
import os
import re

import discord
from discord import app_commands
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SYSTEM_PROMPT = """You are a deadpan, pompous courtroom judge.
You rule on the given dispute using ONLY the chat transcript provided.
Never invent facts, speakers, or quotes that are not in the transcript.
If the evidence is genuinely absent, say so in the ruling, set guilty_party to "Nobody", and use low confidence.

Return ONLY valid JSON, with no markdown fences and no extra text. Keys:
- ruling: string, one-sentence verdict
- guilty_party: string, a username, or "Nobody" if inconclusive
- evidence: array of up to 3 objects with keys quote, author, timestamp (quotes must appear verbatim in the transcript)
- confidence: integer 0-100
- sentence: string, a joke punishment
"""

intents = discord.Intents.default()
intents.message_content = True


class RefereeBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = RefereeBot()
tree = bot.tree
gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _format_message(message: discord.Message) -> str:
    stamp = message.created_at.strftime("%d/%m %H:%M")
    name = message.author.display_name
    return f"[{stamp}] {name}: {message.content}"


def _confidence_colour(confidence: int) -> discord.Colour:
    if confidence >= 70:
        return discord.Colour.green()
    if confidence >= 40:
        return discord.Colour.gold()
    return discord.Colour.red()


def _evidence_field(evidence) -> str:
    if not isinstance(evidence, list) or not evidence:
        return "No exhibits entered into the record."

    lines = []
    for item in evidence[:3]:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        author = str(item.get("author", "Unknown")).strip()
        timestamp = str(item.get("timestamp", "unknown time")).strip()
        if not quote:
            continue
        lines.append(f"> {quote}\n— {author}, {timestamp}")

    return "\n\n".join(lines) if lines else "No exhibits entered into the record."


def _build_embed(verdict: dict) -> discord.Embed:
    try:
        confidence = int(verdict.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0
    confidence = max(0, min(100, confidence))

    embed = discord.Embed(
        title="⚖️ THE COURT HAS RULED",
        description=str(verdict.get("ruling", "The bench declines to comment.")),
        colour=_confidence_colour(confidence),
    )
    embed.add_field(
        name="Defendant",
        value=str(verdict.get("guilty_party", "Nobody")),
        inline=False,
    )
    embed.add_field(name="Evidence", value=_evidence_field(verdict.get("evidence")), inline=False)
    embed.add_field(name="Confidence", value=f"{confidence}%", inline=False)
    embed.add_field(
        name="Sentence",
        value=str(verdict.get("sentence", "Court adjourned.")),
        inline=False,
    )
    return embed


def _ask_gemini(transcript: str, dispute: str) -> str:
    prompt = (
        f"DISPUTE:\n{dispute}\n\n"
        f"TRANSCRIPT (oldest first):\n{transcript}\n"
    )
    response = gemini.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    print(f"RAW RESPONSE: {response.text!r}")
    return response.text or ""


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} ({bot.user.id})")


@tree.command(name="referee", description="Settle a dispute from recent chat like a courtroom judge.")
@app_commands.describe(
    dispute="The question being settled",
    limit="How many recent messages to consider (default 300, max 500)",
)
async def referee(
    interaction: discord.Interaction,
    dispute: str,
    limit: app_commands.Range[int, 1, 5000] = 300,
) -> None:
    await interaction.response.defer()

    channel = interaction.channel
    if channel is None or not hasattr(channel, "history"):
        await interaction.followup.send("This court has no jurisdiction here.")
        return

    collected: list[discord.Message] = []
    async for message in channel.history(limit=limit):
        if message.author.bot or not message.content:
            continue
        collected.append(message)

    collected.reverse()
    transcript = "\n".join(_format_message(m) for m in collected)
    if not transcript:
        transcript = "(No human messages were found in the requested window.)"

    print(f"TRANSCRIPT: {len(collected)} messages, {len(transcript)} chars")

    verdict = None
    try:
        for attempt in range(2):
            raw = await asyncio.to_thread(_ask_gemini, transcript, dispute)
            try:
                verdict = json.loads(_strip_json_fences(raw))
                if not isinstance(verdict, dict):
                    raise json.JSONDecodeError("expected object", raw, 0)
                break
            except json.JSONDecodeError:
                if attempt == 0:
                    continue
                await interaction.followup.send("The court is in recess.")
                return
    except Exception as e:
        import traceback
        print(f"REFEREE ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        await interaction.followup.send("The court is in recess.")
        return

    await interaction.followup.send(embed=_build_embed(verdict))


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set")
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set")
    bot.run(token)
