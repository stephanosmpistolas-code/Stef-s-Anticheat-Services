"""
Κύριο αρχείο εκκίνησης του Discord moderation bot.
Λειτουργίες: anti-spam, anti-raid, moderation commands (warn/mute/kick/ban), logging.
"""

import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import config
from utils_logging import ensure_log_channel

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=commands.DefaultHelpCommand())


@bot.event
async def on_ready():
    print(f"Συνδέθηκε ως {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        try:
            await ensure_log_channel(guild)
        except discord.Forbidden:
            print(f"Δεν έχω δικαίωμα να δημιουργήσω κανάλι logs στο: {guild.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Συγχρονίστηκαν {len(synced)} slash commands (global).")
    except discord.HTTPException as e:
        print(f"Αποτυχία συγχρονισμού slash commands: {e}")

    # Άμεσος (instant) συγχρονισμός ανά server, ώστε οι εντολές να εμφανίζονται
    # αμέσως κατά το development, χωρίς να περιμένουμε το global propagation
    # (που μπορεί να πάρει έως 1 ώρα).
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            guild_synced = await bot.tree.sync(guild=guild)
            print(f"Άμεσος συγχρονισμός {len(guild_synced)} εντολών στο: {guild.name}")
        except discord.HTTPException as e:
            print(f"Αποτυχία άμεσου συγχρονισμού στο {guild.name}: {e}")
    print("Bot έτοιμο.")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    raise error


async def load_cogs():
    await bot.load_extension("cogs.anti_spam")
    await bot.load_extension("cogs.anti_raid")
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.welcome")
    await bot.load_extension("cogs.status_panel")
    await bot.load_extension("cogs.support_voice")
    await bot.load_extension("cogs.tickets")
    await bot.load_extension("cogs.scan")


async def main():
    if not TOKEN:
        raise RuntimeError(
            "Δεν βρέθηκε DISCORD_BOT_TOKEN. Δημιούργησε ένα αρχείο .env βασισμένο στο .env.example "
            "και βάλε το token του bot σου εκεί."
        )
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
