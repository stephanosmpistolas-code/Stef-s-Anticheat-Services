"""
Βοηθητικές συναρτήσεις για logging.
Όλες οι ενέργειες του bot (spam detection, raid detection, moderation commands)
καταγράφονται σε ένα κανάλι λογιστικής (ορίζεται στο config.LOG_CHANNEL_NAME).
"""

import discord
import config


def get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=config.LOG_CHANNEL_NAME)


async def send_log(guild: discord.Guild, embed: discord.Embed):
    channel = get_log_channel(guild)
    if channel is None:
        return
    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def ensure_log_channel(guild: discord.Guild) -> discord.TextChannel:
    """
    Δημιουργεί το κανάλι logs αν δεν υπάρχει ήδη, με δικαιώματα ορατά μόνο σε staff roles.
    """
    existing = get_log_channel(guild)
    if existing is not None:
        return existing

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }

    for role in guild.roles:
        if role.name in config.STAFF_ROLE_NAMES:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

    channel = await guild.create_text_channel(
        config.LOG_CHANNEL_NAME,
        overwrites=overwrites,
        reason="Αυτόματη δημιουργία καναλιού logs από το anti-cheat bot",
    )
    return channel
