"""
Moderation cog (slash commands).
Εντολές: /warn, /warnings, /mute, /unmute, /kick, /ban, /unban, /unlock, /dmall.
Όλες απαιτούν τα αντίστοιχα δικαιώματα (kick_members / ban_members / moderate_members / administrator).
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from collections import defaultdict

import config
import utils_embeds as ui
from utils_logging import send_log
from utils_moderation import apply_timeout, remove_timeout


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> user_id -> list of reasons
        self.warnings: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))

    # ---------- WARN ----------
    @app_commands.command(name="warn", description="Προειδοποίηση μέλους")
    @app_commands.describe(member="Το μέλος που θα προειδοποιηθεί", reason="Ο λόγος της προειδοποίησης")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        guild_warnings = self.warnings[interaction.guild.id]
        guild_warnings[member.id].append(reason)
        count = len(guild_warnings[member.id])

        embed = ui.warning_embed("Μέλος Προειδοποιήθηκε")
        ui.add_user_field(embed, member)
        ui.add_moderator_field(embed, interaction.user)
        ui.add_reason_field(embed, reason)
        embed.add_field(name="Σύνολο Προειδοποιήσεων", value=str(count), inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

        if count >= config.MAX_WARNINGS_BEFORE_MUTE:
            applied = await apply_timeout(
                member, config.SPAM_MUTE_DURATION, f"Αυτόματο mute μετά από {count} προειδοποιήσεις"
            )
            auto_embed = ui.danger_embed(
                "Αυτόματο Mute",
                f"{member.mention} έλαβε αυτόματο timeout λόγω συσσωρευμένων προειδοποιήσεων."
                if applied
                else "Αποτυχία αυτόματου timeout (έλεγξε δικαιώματα bot).",
            )
            await interaction.followup.send(embed=auto_embed)
            await send_log(interaction.guild, auto_embed)

    @app_commands.command(name="warnings", description="Λίστα προειδοποιήσεων ενός μέλους")
    @app_commands.describe(member="Το μέλος που θες να δεις τις προειδοποιήσεις του")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def list_warnings(self, interaction: discord.Interaction, member: discord.Member):
        reasons = self.warnings[interaction.guild.id].get(member.id, [])
        if not reasons:
            embed = ui.info_embed("Προειδοποιήσεις", f"{member.mention} δεν έχει καμία προειδοποίηση.")
        else:
            text = "\n".join(f"{i+1}. {r}" for i, r in enumerate(reasons))
            embed = ui.info_embed(f"Προειδοποιήσεις για {member.display_name}", text)
        await interaction.response.send_message(embed=embed)

    # ---------- MUTE / UNMUTE ----------
    @app_commands.command(name="mute", description="Προσωρινή σίγαση μέλους")
    @app_commands.describe(member="Το μέλος", seconds="Διάρκεια σε δευτερόλεπτα", reason="Ο λόγος")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, member: discord.Member, seconds: int = 600, reason: str = "Δεν δόθηκε λόγος"):
        applied = await apply_timeout(member, seconds, reason)
        if applied:
            embed = ui.warning_embed("Μέλος Σιγάστηκε")
            ui.add_user_field(embed, member)
            ui.add_moderator_field(embed, interaction.user)
            ui.add_reason_field(embed, reason)
            embed.add_field(name="Διάρκεια", value=f"{seconds} δευτερόλεπτα", inline=False)
        else:
            embed = ui.danger_embed("Αποτυχία", "Δεν ήταν δυνατή η σίγαση του μέλους. Έλεγξε τα δικαιώματα του bot.")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

    @app_commands.command(name="unmute", description="Άρση σίγασης μέλους")
    @app_commands.describe(member="Το μέλος")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, member: discord.Member):
        applied = await remove_timeout(member, f"Άρση σίγασης από {interaction.user}")
        if applied:
            embed = ui.success_embed("Μέλος Αποσιγάστηκε")
            ui.add_user_field(embed, member)
            ui.add_moderator_field(embed, interaction.user)
        else:
            embed = ui.danger_embed("Αποτυχία", "Δεν ήταν δυνατή η άρση σίγασης. Έλεγξε τα δικαιώματα του bot.")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

    # ---------- KICK ----------
    @app_commands.command(name="kick", description="Αποβολή μέλους από το server")
    @app_commands.describe(member="Το μέλος", reason="Ο λόγος")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        try:
            await member.kick(reason=f"{reason} | Από: {interaction.user}")
            embed = ui.danger_embed("Μέλος Αποβλήθηκε (Kick)")
            ui.add_user_field(embed, member)
            ui.add_moderator_field(embed, interaction.user)
            ui.add_reason_field(embed, reason)
        except (discord.Forbidden, discord.HTTPException):
            embed = ui.danger_embed("Αποτυχία", "Δεν ήταν δυνατή η αποβολή του μέλους. Έλεγξε τα δικαιώματα του bot.")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

    # ---------- BAN ----------
    @app_commands.command(name="ban", description="Αποκλεισμός μέλους από το server")
    @app_commands.describe(member="Το μέλος", reason="Ο λόγος")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Δεν δόθηκε λόγος"):
        try:
            await member.ban(reason=f"{reason} | Από: {interaction.user}", delete_message_days=0)
            embed = ui.danger_embed("Μέλος Αποκλείστηκε (Ban)")
            ui.add_user_field(embed, member)
            ui.add_moderator_field(embed, interaction.user)
            ui.add_reason_field(embed, reason)
        except (discord.Forbidden, discord.HTTPException):
            embed = ui.danger_embed("Αποτυχία", "Δεν ήταν δυνατό το ban του μέλους. Έλεγξε τα δικαιώματα του bot.")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

    @app_commands.command(name="unban", description="Άρση αποκλεισμού χρήστη με βάση το ID του")
    @app_commands.describe(user_id="Το Discord ID του χρήστη", reason="Ο λόγος")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "Δεν δόθηκε λόγος"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=f"{reason} | Από: {interaction.user}")
            embed = ui.success_embed("Μέλος Ξεμπλοκαρίστηκε (Unban)")
            ui.add_user_field(embed, user)
            ui.add_moderator_field(embed, interaction.user)
            ui.add_reason_field(embed, reason)
        except (ValueError, discord.NotFound, discord.Forbidden, discord.HTTPException):
            embed = ui.danger_embed("Αποτυχία", "Δεν ήταν δυνατό το unban. Έλεγξε το ID χρήστη και τα δικαιώματα του bot.")
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

    # ---------- DM ALL (μήνυμα σε όλα τα μέλη) ----------
    @app_commands.command(name="dmall", description="Στέλνει μήνυμα μέσω DM σε όλα τα μέλη του server")
    @app_commands.describe(message="Το μήνυμα που θα σταλεί")
    @app_commands.checks.has_permissions(administrator=True)
    async def dmall(self, interaction: discord.Interaction, message: str):
        guild = interaction.guild

        confirm_embed = ui.info_embed(
            "Αποστολή Μηνύματος σε Όλα τα Μέλη",
            f"Ξεκινάει αποστολή σε {guild.member_count} μέλη. Αυτό μπορεί να πάρει αρκετή ώρα.",
        )
        await interaction.response.send_message(embed=confirm_embed)

        sent = 0
        failed = 0

        for member in guild.members:
            if member.bot:
                continue
            try:
                dm_embed = ui.info_embed(f"Μήνυμα από {guild.name}", message)
                dm_embed.set_footer(text="Stef's Anticheat Services Bot")
                await member.send(embed=dm_embed)
                sent += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1
            await asyncio.sleep(1.2)

        result_embed = ui.success_embed(
            "Ολοκληρώθηκε η Αποστολή",
            f"Επιτυχημένες αποστολές: {sent}\nΑποτυχημένες (κλειστά DMs ή άλλο σφάλμα): {failed}",
        )
        ui.add_moderator_field(result_embed, interaction.user)
        result_embed.add_field(name="Μήνυμα", value=message, inline=False)
        await interaction.edit_original_response(embed=result_embed)
        await send_log(guild, result_embed)

    # ---------- UNLOCK (άρση anti-raid lockdown) ----------
    @app_commands.command(name="unlock", description="Άρση anti-raid lockdown στο server")
    @app_commands.checks.has_permissions(administrator=True)
    async def unlock(self, interaction: discord.Interaction):
        raid_cog = self.bot.get_cog("AntiRaid")
        if raid_cog is None:
            await interaction.response.send_message(embed=ui.danger_embed("Σφάλμα", "Το anti-raid module δεν είναι διαθέσιμο."))
            return

        unlocked = await raid_cog.deactivate_raid_mode(interaction.guild)
        embed = ui.success_embed(
            "Άρση Lockdown",
            f"Ξεκλειδώθηκαν {unlocked} κανάλια. Το server επέστρεψε σε κανονική λειτουργία.",
        )
        ui.add_moderator_field(embed, interaction.user)
        await interaction.response.send_message(embed=embed)
        await send_log(interaction.guild, embed)

    # ---------- Error handling ----------
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            embed = ui.danger_embed("Δεν Επιτρέπεται", "Δεν έχεις τα απαραίτητα δικαιώματα για αυτή την εντολή.")
        else:
            embed = ui.danger_embed("Σφάλμα", f"Κάτι πήγε στραβά: {error}")

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
