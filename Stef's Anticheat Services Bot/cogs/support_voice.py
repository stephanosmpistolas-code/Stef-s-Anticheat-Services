"""
Support Voice cog.
- Όταν ένα μέλος μπει στο voice κανάλι αναμονής (config.SUPPORT_WAITING_CHANNEL_ID),
  μετά από config.SUPPORT_MOVE_DELAY_SECONDS δευτερόλεπτα το bot:
    1. Δημιουργεί ένα νέο voice κανάλι "Support (Username)" στην ίδια κατηγορία
    2. Μετακινεί το μέλος μέσα σε αυτό
- Όταν το μέλος φύγει από το προσωπικό του support κανάλι (και αδειάσει), το κανάλι διαγράφεται.
"""

import discord
from discord.ext import commands
import asyncio

import config


class SupportVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # channel_id -> member_id, για να ξέρουμε ποια κανάλια είναι "δικά μας" support rooms
        self.support_channels: dict[int, int] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        # ---- Μέλος μπήκε στο κανάλι αναμονής ----
        if after.channel is not None and after.channel.id == config.SUPPORT_WAITING_CHANNEL_ID:
            asyncio.create_task(self._create_and_move(member, after.channel))

        # ---- Έλεγχος αν κάποιο support κανάλι άδειασε ----
        if before.channel is not None and before.channel.id in self.support_channels:
            await self._cleanup_if_empty(before.channel)

    async def _create_and_move(self, member: discord.Member, waiting_channel: discord.VoiceChannel):
        await asyncio.sleep(config.SUPPORT_MOVE_DELAY_SECONDS)

        # Επιβεβαίωση ότι το μέλος είναι ακόμα στο κανάλι αναμονής μετά την καθυστέρηση
        current_voice = member.voice
        if current_voice is None or current_voice.channel is None:
            return
        if current_voice.channel.id != config.SUPPORT_WAITING_CHANNEL_ID:
            return

        guild = member.guild
        category = waiting_channel.category

        support_role = guild.get_role(config.SUPPORT_NOTIFY_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True, move_members=True),
        }
        if support_role is not None:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)

        try:
            new_channel = await guild.create_voice_channel(
                name=f"Support ({member.display_name})",
                category=category,
                overwrites=overwrites,
                reason=f"Αυτόματο support κανάλι για {member}",
            )
        except (discord.Forbidden, discord.HTTPException):
            return

        self.support_channels[new_channel.id] = member.id

        try:
            await member.move_to(new_channel, reason="Αυτόματη μετακίνηση σε προσωπικό support κανάλι")
        except (discord.Forbidden, discord.HTTPException):
            # Αν η μετακίνηση αποτύχει (π.χ. το μέλος έφυγε από voice), καθάρισε το κανάλι
            try:
                await new_channel.delete(reason="Αποτυχία μετακίνησης μέλους")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
            self.support_channels.pop(new_channel.id, None)
            return

        await self._send_notification(guild, member, new_channel)

    async def _send_notification(self, guild: discord.Guild, member: discord.Member, voice_channel: discord.VoiceChannel):
        notify_channel = guild.get_channel(config.SUPPORT_NOTIFY_CHANNEL_ID)
        if notify_channel is None:
            return

        role = guild.get_role(config.SUPPORT_NOTIFY_ROLE_ID)
        role_mention = role.mention if role is not None else ""

        content = f"{role_mention} Κάποιος Περιμένει Για Support!"

        embed = discord.Embed(
            title="Νέο Αίτημα Support",
            description=f"{member.mention} χρειάζεται βοήθεια.",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Κανάλι", value=voice_channel.mention, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Stef's Anticheat Services Bot")

        try:
            await notify_channel.send(content=content, embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _cleanup_if_empty(self, channel: discord.VoiceChannel):
        # Παίρνουμε φρέσκια αναφορά του καναλιού για ακριβή λίστα μελών
        guild = channel.guild
        fresh_channel = guild.get_channel(channel.id)
        if fresh_channel is None:
            self.support_channels.pop(channel.id, None)
            return

        if len(fresh_channel.members) == 0:
            try:
                await fresh_channel.delete(reason="Το support κανάλι άδειασε")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
            self.support_channels.pop(channel.id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(SupportVoice(bot))
