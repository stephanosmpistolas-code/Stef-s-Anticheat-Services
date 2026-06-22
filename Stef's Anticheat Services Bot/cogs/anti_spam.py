"""
Anti-spam cog.
Εντοπίζει: flood μηνυμάτων (πολλά μηνύματα σε σύντομο διάστημα) και mass mentions.
Όταν εντοπιστεί spam: διαγραφή μηνυμάτων, προσωρινό mute, log στο κανάλι logs.
"""

import discord
from discord.ext import commands
from collections import defaultdict, deque
import time

import config
import utils_embeds as ui
from utils_logging import send_log
from utils_moderation import apply_timeout, get_or_create_mute_role


class AntiSpam(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # user_id -> deque των timestamps των τελευταίων μηνυμάτων
        self.message_times: dict[int, deque] = defaultdict(deque)

    def is_staff(self, member: discord.Member) -> bool:
        return any(role.name in config.STAFF_ROLE_NAMES for role in member.roles)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        member = message.author
        if isinstance(member, discord.Member) and self.is_staff(member):
            return

        now = time.time()
        times = self.message_times[member.id]
        times.append(now)

        # κρατάμε μόνο τα μηνύματα μέσα στο time window
        while times and now - times[0] > config.SPAM_TIME_WINDOW:
            times.popleft()

        # --- Έλεγχος flood ---
        if len(times) >= config.SPAM_MESSAGE_LIMIT:
            times.clear()
            await self.handle_spam(message, reason="Flood μηνυμάτων")
            return

        # --- Έλεγχος mass mentions ---
        if len(message.mentions) >= config.MASS_MENTION_LIMIT:
            await self.handle_spam(message, reason="Μαζικά mentions σε ένα μήνυμα")
            return

    async def handle_spam(self, message: discord.Message, reason: str):
        member = message.author
        guild = message.guild

        # Διαγραφή πρόσφατων μηνυμάτων του χρήστη στο κανάλι (καθαρισμός flood)
        try:
            def check(m):
                return m.author.id == member.id

            await message.channel.purge(limit=15, check=check)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # Timeout στο μέλος
        applied = await apply_timeout(member, config.SPAM_MUTE_DURATION, reason)

        # Ενημέρωση στο κανάλι
        notice = ui.warning_embed(
            "Εντοπίστηκε Spam",
            f"{member.mention} τέθηκε σε προσωρινή σίγαση λόγω: {reason}.",
        )
        try:
            await message.channel.send(embed=notice, delete_after=10)
        except discord.HTTPException:
            pass

        # Log
        log_embed = ui.warning_embed("Anti-Spam Ενέργεια")
        ui.add_user_field(log_embed, member)
        ui.add_reason_field(log_embed, reason)
        log_embed.add_field(
            name="Ενέργεια",
            value=(
                f"Timeout {config.SPAM_MUTE_DURATION} δευτερολέπτων"
                if applied
                else "Αποτυχία timeout (έλεγξε δικαιώματα bot)"
            ),
            inline=False,
        )
        log_embed.add_field(name="Κανάλι", value=message.channel.mention, inline=False)
        await send_log(guild, log_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiSpam(bot))
