"""
Βοηθητικές συναρτήσεις για moderation: δημιουργία/εύρεση mute role, εφαρμογή timeout.
"""

import discord
from datetime import timedelta
import config


async def get_or_create_mute_role(guild: discord.Guild) -> discord.Role:
    role = discord.utils.get(guild.roles, name=config.MUTE_ROLE_NAME)
    if role is not None:
        return role

    role = await guild.create_role(
        name=config.MUTE_ROLE_NAME,
        reason="Αυτόματη δημιουργία mute role από το anti-cheat bot",
        permissions=discord.Permissions(send_messages=False, speak=False, add_reactions=False),
    )

    # Ρύθμιση overwrites ώστε ο muted role να μην μπορεί να γράφει σε κανάλια
    for channel in guild.channels:
        try:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
                await channel.set_permissions(
                    role,
                    send_messages=False,
                    speak=False,
                    add_reactions=False,
                )
        except (discord.Forbidden, discord.HTTPException):
            continue

    return role


async def apply_timeout(member: discord.Member, seconds: int, reason: str) -> bool:
    """
    Εφαρμόζει Discord native timeout (mute) στο μέλος.
    Επιστρέφει True αν πέτυχε, False αν απέτυχε (π.χ. λόγω δικαιωμάτων).
    """
    try:
        await member.timeout(timedelta(seconds=seconds), reason=reason)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


async def remove_timeout(member: discord.Member, reason: str) -> bool:
    try:
        await member.timeout(None, reason=reason)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False
