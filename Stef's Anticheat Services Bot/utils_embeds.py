"""
Βοηθητικές συναρτήσεις για δημιουργία embeds.
Όλα τα embeds είναι καθαρά, χωρίς emoji, με σαφή τίτλο και χρώμα ανάλογα τη σοβαρότητα.
"""

import discord
from datetime import datetime, timezone
import config


def base_embed(title: str, description: str = "", color: int = config.COLOR_INFO) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    return embed


def info_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, config.COLOR_INFO)


def success_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, config.COLOR_SUCCESS)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, config.COLOR_WARNING)


def danger_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, config.COLOR_DANGER)


def raid_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, config.COLOR_RAID)


def add_user_field(embed: discord.Embed, user: discord.abc.User, label: str = "Χρήστης") -> discord.Embed:
    embed.add_field(name=label, value=f"{user.mention} ({user.id})", inline=False)
    return embed


def add_moderator_field(embed: discord.Embed, moderator: discord.abc.User) -> discord.Embed:
    embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.id})", inline=False)
    return embed


def add_reason_field(embed: discord.Embed, reason: str) -> discord.Embed:
    embed.add_field(name="Λόγος", value=reason or "Δεν δόθηκε λόγος", inline=False)
    return embed
