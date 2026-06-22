"""
Cog: Subscription
Σύστημα διαχείρισης μηνιαίων subscriptions.

Λειτουργίες:
- /subscription add @user: Προσθέτει χρήστη σε subscription (30 ημέρες)
- Panel που ενημερώνεται κάθε 30 δευτερόλεπτα (χωρίς delete/resend)
- Background task που ελέγχει για λήξεις και στέλνει DM reminders
- Αυτόματη δυναμική διαχείρισης role
"""

import json
import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from utils_embeds import info_embed, success_embed

SUBSCRIPTION_DATA_FILE = "subscriptions_data.json"
CHANNEL_ID = 1518638616576917544
ROLE_ID = 1517639189150175402
UPDATE_INTERVAL_SECONDS = 30
SUBSCRIPTION_DAYS = 30


def _load_subscriptions() -> dict:
    """Φόρτωσε τα δεδομένα subscriptions από αρχείο."""
    if not os.path.exists(SUBSCRIPTION_DATA_FILE):
        return {}
    try:
        with open(SUBSCRIPTION_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_subscriptions(data: dict) -> None:
    """Αποθήκευσε τα δεδομένα subscriptions στο αρχείο."""
    with open(SUBSCRIPTION_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Subscription(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_message_id = None
        self.auto_update_panel.start()
        self.check_expirations.start()

    def cog_unload(self):
        self.auto_update_panel.cancel()
        self.check_expirations.cancel()

    @app_commands.command(
        name="subscription",
        description="Διαχείριση subscriptions",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def subscription(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str] = app_commands.Choice(
            name="add", value="add"
        ),
        user: discord.User = None,
    ):
        """Προσθήκη/Διαχείριση subscriptions."""
        if action.value == "add" and user:
            data = _load_subscriptions()
            expiry = (datetime.now(timezone.utc) + timedelta(days=SUBSCRIPTION_DAYS)).isoformat()

            data[str(user.id)] = {
                "user_id": user.id,
                "username": user.name,
                "purchased_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expiry,
                "notified": False,
            }
            _save_subscriptions(data)

            # Δώσε το role
            guild = interaction.guild
            role = guild.get_role(ROLE_ID)
            member = guild.get_member(user.id)
            if role and member:
                try:
                    await member.add_roles(role, reason=f"Subscription added by {interaction.user}")
                except discord.Forbidden:
                    pass

            embed = success_embed(
                "Subscription Added",
                f"{user.mention} θα έχει subscription για 30 ημέρες.\nΛήξη: {expiry}",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(seconds=UPDATE_INTERVAL_SECONDS)
    async def auto_update_panel(self):
        """Ενημερώνει το panel κάθε 30 δευτερόλεπτα χωρίς να το διαγράφει."""
        try:
            channel = self.bot.get_channel(CHANNEL_ID)
            if not channel:
                return

            data = _load_subscriptions()
            active_subs = [
                sub for sub in data.values()
                if datetime.fromisoformat(sub["expires_at"]) > datetime.now(timezone.utc)
            ]

            # Δημιουργία embed
            embed = info_embed(
                "Ενεργά Subscriptions",
                f"Σύνολο ενεργών: **{len(active_subs)}**",
            )

            if active_subs:
                sub_list = "\n".join(
                    [
                        f"• {sub['username']} - Λήξη: {sub['expires_at'][:10]}"
                        for sub in active_subs[:20]
                    ]
                )
                embed.add_field(name="Subscribers", value=sub_list or "Κανένας", inline=False)
            else:
                embed.add_field(name="Subscribers", value="Κανένας ενεργό subscription", inline=False)

            embed.set_footer(text=f"Ενημερώθηκε: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")

            # Αναζήτησε ή δημιουργήσε το panel message
            if not self.panel_message_id:
                # Πρώτη φορά, αναζήτησε τα τελευταία 100 messages
                async for msg in channel.history(limit=100):
                    if msg.author == self.bot.user and msg.embeds:
                        if "Ενεργά Subscriptions" in msg.embeds[0].title:
                            self.panel_message_id = msg.id
                            break

            if self.panel_message_id:
                try:
                    message = await channel.fetch_message(self.panel_message_id)
                    await message.edit(embed=embed)
                except discord.NotFound:
                    self.panel_message_id = None
                    msg = await channel.send(embed=embed)
                    self.panel_message_id = msg.id
            else:
                msg = await channel.send(embed=embed)
                self.panel_message_id = msg.id

        except Exception as e:
            print(f"Error in auto_update_panel: {e}")

    @tasks.loop(hours=1)
    async def check_expirations(self):
        """Ελέγχει για λήξεις και στέλνει DM reminders."""
        try:
            data = _load_subscriptions()
            now = datetime.now(timezone.utc)

            for user_id, sub in list(data.items()):
                expires = datetime.fromisoformat(sub["expires_at"])

                # Αν έχει λήξει και δεν έχουμε ειδοποιήσει, στείλε DM
                if expires <= now and not sub.get("notified"):
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        embed = discord.Embed(
                            title="Ενημέρωση Subscription",
                            description=(
                                f"Το subscription σου στο Stef's Anticheat Services έληξε.\n"
                                f"Ημερομηνία λήξης: {sub['expires_at'][:10]}\n\n"
                                f"Αν θες να ανανεώσεις, επικοινώνησε με το staff."
                            ),
                            color=0xE74C3C,
                        )
                        await user.send(embed=embed)
                        sub["notified"] = True
                    except (discord.Forbidden, discord.HTTPException):
                        pass

                    # Αφαίρεσε το role
                    guild_list = self.bot.guilds
                    for guild in guild_list:
                        member = guild.get_member(int(user_id))
                        role = guild.get_role(ROLE_ID)
                        if member and role:
                            try:
                                await member.remove_roles(role, reason="Subscription expired")
                            except discord.Forbidden:
                                pass

            _save_subscriptions(data)

        except Exception as e:
            print(f"Error in check_expirations: {e}")

    @auto_update_panel.before_loop
    async def before_auto_update(self):
        await self.bot.wait_until_ready()

    @check_expirations.before_loop
    async def before_check_expirations(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Subscription(bot))
