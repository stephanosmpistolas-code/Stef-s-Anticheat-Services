"""
Cog: Scan
Εντολή /scan για λήψη του Scan.exe αρχείου από Google Drive.
Μόνο όσοι έχουν το role 1517363787726979092 μπορούν να τη χρησιμοποιήσουν.
"""

import discord
from discord import app_commands
from discord.ext import commands

ALLOWED_ROLE_ID = 1517363787726979092
SCAN_DOWNLOAD_URL = "https://drive.usercontent.google.com/download?id=1bxCi0evFUBPS2vgl9vJFh7X4GzyUuk9P&export=download&authuser=0"


class Scan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="scan",
        description="Κατέβασε το Scan.exe αρχείο για να σκανάρεις τον υπολογιστή σου.",
    )
    async def scan(self, interaction: discord.Interaction):
        # Έλεγχος αν ο χρήστης έχει το απαιτούμενο role
        if not any(role.id == ALLOWED_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "Δεν έχεις πρόσβαση σε αυτή την εντολή. Χρειάζεσαι το κατάλληλο role.",
                ephemeral=True,
            )
            return

        # Δημιουργία embed με το link
        embed = discord.Embed(
            title="Scan.exe - Κατέβασμα",
            description="Πάτησε το κουμπί παρακάτω ή το link για να κατεβάσεις το Scan.exe αρχείο.",
            color=0x3498DB,
        )
        embed.add_field(
            name="Εντολές",
            value="1. Κατέβασε το αρχείο\n2. Εκτέλεσε το ως Administrator\n3. Περίμενε τα αποτελέσματα",
            inline=False,
        )
        embed.set_footer(text="Stef's Anticheat Services")

        # Δημιουργία κουμπιού με link
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Κατέβασε Scan.exe",
                url=SCAN_DOWNLOAD_URL,
                style=discord.ButtonStyle.link,
                emoji="📥",
            )
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Scan(bot))
