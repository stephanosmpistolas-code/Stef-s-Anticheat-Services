"""
Cog: Scan
Εντολή /scan για λήψη του Scan.exe αρχείου.
Μόνο όσοι έχουν το role 1517363787726979092 μπορούν να τη χρησιμοποιήσουν.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands

ALLOWED_ROLE_ID = 1517363787726979092

# Δοκίμασε πολλές πιθανές διαδρομές
POSSIBLE_PATHS = [
    "Scan.exe.exe",
    "./Scan.exe.exe",
    "/app/Scan.exe.exe",
    os.path.join(os.getcwd(), "Scan.exe.exe"),
]


def find_scan_file():
    """Βρες το αρχείο Scan.exe.exe σε κάποια από τις πιθανές διαδρομές."""
    for path in POSSIBLE_PATHS:
        if os.path.exists(path):
            return path
    return None


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

        # Βρες το αρχείο
        scan_path = find_scan_file()
        if not scan_path:
            await interaction.response.send_message(
                "Το αρχείο Scan.exe δεν βρέθηκε. Ενημέρωσε το staff.",
                ephemeral=True,
            )
            return

        # Αποστολή του αρχείου
        try:
            file = discord.File(scan_path, filename="Scan.exe.exe")
            await interaction.response.send_message(
                "Ορίστε το Scan.exe αρχείο. Μπορείς να το κατεβάσεις και να το τρέξεις.",
                file=file,
                ephemeral=True,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(
                f"Αποτυχία αποστολής αρχείου: {e}",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Scan(bot))
