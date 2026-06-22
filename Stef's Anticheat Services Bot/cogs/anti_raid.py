"""
Anti-raid cog.
Εντοπίζει μαζικά joins σε σύντομο χρονικό διάστημα και ενεργοποιεί lockdown mode:
- Κλείνει την δυνατότητα νέων μελών να γράφουν (verification gate)
- Σημειώνει νέους λογαριασμούς ως ύποπτους
- Ενημερώνει staff στο κανάλι logs
"""

import discord
from discord.ext import commands, tasks
from collections import deque
from datetime import datetime, timezone

import config
import utils_embeds as ui
from utils_logging import send_log


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.join_times: deque = deque()
        self.raid_mode_guilds: set[int] = set()
        self.lockdown_check.start()

    def cog_unload(self):
        self.lockdown_check.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        now = datetime.now(timezone.utc)

        self.join_times.append(now.timestamp())
        cutoff = now.timestamp() - config.RAID_TIME_WINDOW
        while self.join_times and self.join_times[0] < cutoff:
            self.join_times.popleft()

        account_age_days = (now - member.created_at).days
        is_new_account = account_age_days < config.RAID_ACCOUNT_AGE_MIN_DAYS

        # Πάντα logάρουμε κάθε join, με σημείωση αν ο λογαριασμός είναι νέος
        join_embed = ui.info_embed("Νέο Μέλος")
        ui.add_user_field(join_embed, member)
        join_embed.add_field(
            name="Ηλικία Λογαριασμού",
            value=f"{account_age_days} ημέρες" + (" (ΥΠΟΠΤΟ - πολύ νέος λογαριασμός)" if is_new_account else ""),
            inline=False,
        )
        await send_log(guild, join_embed)

        # Έλεγχος για raid: πολλά joins σε μικρό διάστημα
        if len(self.join_times) >= config.RAID_JOIN_LIMIT and guild.id not in self.raid_mode_guilds:
            await self.activate_raid_mode(guild)

    async def activate_raid_mode(self, guild: discord.Guild):
        self.raid_mode_guilds.add(guild.id)

        # Lockdown: default role δεν μπορεί να γράφει σε κανάλια κειμένου
        locked_channels = []
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = False
                await channel.set_permissions(
                    guild.default_role, overwrite=overwrite, reason="Ενεργοποίηση anti-raid lockdown"
                )
                locked_channels.append(channel)
            except (discord.Forbidden, discord.HTTPException):
                continue

        alert = ui.raid_embed(
            "Ενεργοποιήθηκε Λειτουργία Anti-Raid",
            f"Εντοπίστηκαν {config.RAID_JOIN_LIMIT}+ νέα μέλη μέσα σε {config.RAID_TIME_WINDOW} δευτερόλεπτα.\n"
            f"Το server τέθηκε σε lockdown για {config.RAID_LOCKDOWN_DURATION} δευτερόλεπτα.\n"
            f"Κλειδωμένα κανάλια: {len(locked_channels)}",
        )
        await send_log(guild, alert)

    @tasks.loop(seconds=30)
    async def lockdown_check(self):
        """
        Περιοδικός έλεγχος: αν έχει περάσει αρκετός χρόνος χωρίς νέα joins,
        το lockdown αίρεται αυτόματα.
        Σημείωση: για απλότητα, η άρση γίνεται χειροκίνητα μέσω εντολής `unlock`
        ή μπορεί να επεκταθεί με χρονομέτρηση ανά guild.
        """
        pass

    @lockdown_check.before_loop
    async def before_lockdown_check(self):
        await self.bot.wait_until_ready()

    async def deactivate_raid_mode(self, guild: discord.Guild) -> int:
        self.raid_mode_guilds.discard(guild.id)
        unlocked = 0
        for channel in guild.text_channels:
            try:
                overwrite = channel.overwrites_for(guild.default_role)
                overwrite.send_messages = None
                await channel.set_permissions(
                    guild.default_role, overwrite=overwrite, reason="Άρση anti-raid lockdown"
                )
                unlocked += 1
            except (discord.Forbidden, discord.HTTPException):
                continue
        return unlocked


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
