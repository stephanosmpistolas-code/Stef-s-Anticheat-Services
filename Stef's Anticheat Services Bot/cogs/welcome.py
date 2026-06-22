"""
Welcome cog.
- Στέλνει μήνυμα καλωσορίσματος σε συγκεκριμένο κανάλι (config.WELCOME_CHANNEL_ID)
  κάθε φορά που ένα νέο μέλος μπαίνει στο server.
- Δίνει αυτόματα ένα role σε κάθε νέο μέλος (auto-role).
- /setautorole (slash, μόνο Administrator): αλλάζει δυναμικά ποιο role δίνεται αυτόματα.
  Η ρύθμιση αποθηκεύεται σε αρχείο, ώστε να επιβιώνει σε restart του bot.
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import os

import config
import utils_embeds as ui

AUTOROLE_STORAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "autorole_data.json")


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # guild_id -> role_id, φορτώνεται από αρχείο. Αν δεν υπάρχει ρύθμιση για ένα guild,
        # χρησιμοποιείται το config.AUTO_ROLE_ID ως προεπιλογή.
        self.auto_roles: dict[int, int] = self._load_autorole_data()

    @staticmethod
    def _load_autorole_data() -> dict[int, int]:
        if not os.path.exists(AUTOROLE_STORAGE_FILE):
            return {}
        try:
            with open(AUTOROLE_STORAGE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _save_autorole_data(self):
        try:
            with open(AUTOROLE_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in self.auto_roles.items()}, f)
        except OSError:
            pass

    def get_auto_role_id(self, guild_id: int) -> int | None:
        if guild_id in self.auto_roles:
            return self.auto_roles[guild_id]
        return config.AUTO_ROLE_ID

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        # ---- Auto-role ----
        role_id = self.get_auto_role_id(member.guild.id)
        if role_id is not None:
            role = member.guild.get_role(role_id)
            if role is not None:
                try:
                    await member.add_roles(role, reason="Αυτόματη ανάθεση role σε νέο μέλος")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ---- Welcome message ----
        channel = member.guild.get_channel(config.WELCOME_CHANNEL_ID)
        if channel is None:
            return

        embed = ui.success_embed(
            "Καλώς Ήρθες",
            f"{member.mention}, καλώς ήρθες στο {member.guild.name}.",
        )
        embed.add_field(name="Μέλος Νούμερο", value=str(member.guild.member_count), inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Stef's Anticheat Services Bot")

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ---------- /setautorole (slash, μόνο Administrator) ----------
    @app_commands.command(name="setautorole", description="Ορίζει ποιο role δίνεται αυτόματα σε νέα μέλη")
    @app_commands.describe(role="Το role που θα δίνεται αυτόματα σε κάθε νέο μέλος")
    @app_commands.checks.has_permissions(administrator=True)
    async def setautorole(self, interaction: discord.Interaction, role: discord.Role):
        self.auto_roles[interaction.guild.id] = role.id
        self._save_autorole_data()

        embed = ui.success_embed(
            "Auto-Role Ενημερώθηκε",
            f"Κάθε νέο μέλος θα λαμβάνει αυτόματα το role {role.mention}.",
        )
        ui.add_moderator_field(embed, interaction.user)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removeautorole", description="Απενεργοποιεί το auto-role (κανένα role δεν θα δίνεται αυτόματα)")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeautorole(self, interaction: discord.Interaction):
        self.auto_roles[interaction.guild.id] = 0  # 0 = κανένα role
        self._save_autorole_data()

        embed = ui.success_embed(
            "Auto-Role Απενεργοποιήθηκε",
            "Δεν θα δίνεται κανένα role αυτόματα σε νέα μέλη πια.",
        )
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
