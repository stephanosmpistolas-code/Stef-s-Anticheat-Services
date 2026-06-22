"""
Status panel cog.
- /setstatus (slash, μόνο Administrator): αλλάζει την κατάσταση σε online/maintenance/offline
- !status (κανονική εντολή, ανοιχτή σε όλους): δείχνει το τρέχον status panel στο κανάλι που γράφτηκε
- Auto-post στο config.STATUS_CHANNEL_ID όταν ξεκινάει το bot (αν δεν υπάρχει ήδη μήνυμα)
- Auto-update κάθε config.STATUS_UPDATE_INTERVAL_SECONDS δευτερόλεπτα
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Literal
import asyncio
import json
import os

import config
import utils_embeds as ui

PANEL_STORAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "status_panel_data.json")


STATUS_MAP = {
    "online": (config.STATUS_LABEL_ONLINE, config.STATUS_COLOR_ONLINE),
    "maintenance": (config.STATUS_LABEL_MAINTENANCE, config.STATUS_COLOR_MAINTENANCE),
    "offline": (config.STATUS_LABEL_OFFLINE, config.STATUS_COLOR_OFFLINE),
}


class StatusPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.current_status: str = "online"
        # guild_id -> message_id του status panel (φορτώνεται από αρχείο, επιβιώνει σε restart)
        self.panel_messages: dict[int, int] = self._load_panel_data()
        # guild_id -> Lock, ώστε δύο ταυτόχρονες ενημερώσεις να μην δημιουργούν διπλά μηνύματα
        self.locks: dict[int, asyncio.Lock] = {}
        self.auto_update.start()

    def cog_unload(self):
        self.auto_update.cancel()

    @staticmethod
    def _load_panel_data() -> dict[int, int]:
        if not os.path.exists(PANEL_STORAGE_FILE):
            return {}
        try:
            with open(PANEL_STORAGE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _save_panel_data(self):
        try:
            with open(PANEL_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in self.panel_messages.items()}, f)
        except OSError:
            pass

    def build_status_embed(self, guild: discord.Guild) -> discord.Embed:
        label, color = STATUS_MAP[self.current_status]

        role = guild.get_role(config.STATUS_ACTIVE_ROLE_ID)
        if role is not None:
            active_members = role.members
            role_name = role.name
        else:
            active_members = []
            role_name = "Anti-Cheat"

        if active_members:
            mentions = "\n".join(f"🛡️ {m.mention}" for m in active_members)
            # Discord embed field όριο 1024 χαρακτήρων· κόβουμε αν χρειαστεί
            if len(mentions) > 1000:
                shown = active_members[:15]
                mentions = "\n".join(f"🛡️ {m.mention}" for m in shown)
                mentions += f"\n*... και {len(active_members) - 15} ακόμα*"
        else:
            mentions = "*Κανένα μέλος αυτή τη στιγμή*"

        embed = discord.Embed(
            title="📡 Κατάσταση Υπηρεσίας — Stef's Anticheat Services",
            description="Ζωντανή επισκόπηση της κατάστασης και του προσωπικού anti-cheat.",
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="⚙️ Κατάσταση", value=f"**{label}**", inline=False)
        embed.add_field(name="👥 Μέλη Server", value=f"**{guild.member_count}**", inline=True)
        embed.add_field(name="📶 Ping", value=f"**{round(self.bot.latency * 1000)} ms**", inline=True)
        embed.add_field(name="🕒 Τελευταία Ενημέρωση", value="Μόλις τώρα", inline=True)
        embed.add_field(
            name=f"🛡️ Active — {role_name} ({len(active_members)})",
            value=mentions,
            inline=False,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text="Stef's Anticheat Services Bot • Ενημερώνεται αυτόματα κάθε 30 δευτερόλεπτα")
        return embed

    async def get_status_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        channel = guild.get_channel(config.STATUS_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def post_or_update_panel(self, guild: discord.Guild):
        lock = self.locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            channel = await self.get_status_channel(guild)
            if channel is None:
                return

            embed = self.build_status_embed(guild)
            message_id = self.panel_messages.get(guild.id)

            if message_id is not None:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed)
                    return
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            # Δεν ξέρουμε το message_id (πρώτη φορά ή το bot μόλις επανεκκινήθηκε).
            # Ψάχνουμε στο πρόσφατο ιστορικό για υπάρχον status panel του bot και κάνουμε edit σε αυτό,
            # αν υπάρχουν πολλαπλά παλιά (π.χ. από πριν τη διόρθωση), κρατάμε το πιο πρόσφατο και
            # σβήνουμε μόνο τα υπόλοιπα παλιά αντίγραφα.
            found_message = None
            duplicates = []
            try:
                async for old_msg in channel.history(limit=20):
                    if old_msg.author.id == self.bot.user.id and old_msg.embeds:
                        if old_msg.embeds[0].title and "Κατάσταση Υπηρεσίας" in old_msg.embeds[0].title:
                            if found_message is None:
                                found_message = old_msg
                            else:
                                duplicates.append(old_msg)
            except (discord.Forbidden, discord.HTTPException):
                pass

            for dup in duplicates:
                try:
                    await dup.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            if found_message is not None:
                try:
                    await found_message.edit(embed=embed)
                    self.panel_messages[guild.id] = found_message.id
                    self._save_panel_data()
                    return
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass

            # Δεν υπάρχει κανένα προηγούμενο status panel στο κανάλι: στέλνουμε το πρώτο.
            try:
                message = await channel.send(embed=embed)
                self.panel_messages[guild.id] = message.id
                self._save_panel_data()
            except (discord.Forbidden, discord.HTTPException):
                pass

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.post_or_update_panel(guild)

    @tasks.loop(seconds=config.STATUS_UPDATE_INTERVAL_SECONDS)
    async def auto_update(self):
        for guild in self.bot.guilds:
            await self.post_or_update_panel(guild)

    @auto_update.before_loop
    async def before_auto_update(self):
        await self.bot.wait_until_ready()
        # Μικρή καθυστέρηση ώστε το on_ready να προλάβει να στείλει το αρχικό panel πρώτο
        await asyncio.sleep(5)

    # ---------- /setstatus (slash, μόνο Administrator) ----------
    @app_commands.command(name="setstatus", description="Αλλάζει την κατάσταση υπηρεσίας (Online/Maintenance/Offline)")
    @app_commands.describe(state="Η νέα κατάσταση")
    @app_commands.checks.has_permissions(administrator=True)
    async def setstatus(self, interaction: discord.Interaction, state: Literal["online", "maintenance", "offline"]):
        self.current_status = state
        await self.post_or_update_panel(interaction.guild)

        label, color = STATUS_MAP[state]
        embed = ui.success_embed("Κατάσταση Ενημερώθηκε", f"Η κατάσταση άλλαξε σε: {label}")
        ui.add_moderator_field(embed, interaction.user)
        await interaction.response.send_message(embed=embed)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            embed = ui.danger_embed("Δεν Επιτρέπεται", "Δεν έχεις τα απαραίτητα δικαιώματα για αυτή την εντολή.")
        else:
            embed = ui.danger_embed("Σφάλμα", f"Κάτι πήγε στραβά: {error}")

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    # ---------- !status (κανονική εντολή, ανοιχτή σε όλους) ----------
    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        embed = self.build_status_embed(ctx.guild)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatusPanel(bot))
