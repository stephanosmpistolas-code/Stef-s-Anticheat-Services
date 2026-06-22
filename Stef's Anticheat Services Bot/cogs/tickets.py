"""
Cog: Tickets
Σύστημα tickets υποστήριξης με κατηγορίες.

Ροή:
- Staff (μόνο Administrator) τρέχει /ticket-panel σε ένα κανάλι ->
  στέλνεται embed με το λογότυπο του server και κουμπί "Άνοιγμα Ticket".
- Χρήστης πατάει το κουμπί -> του εμφανίζεται (ephemeral) dropdown με τις
  κατηγορίες tickets (config.TICKET_CATEGORIES).
- Διαλέγει κατηγορία -> αν η κατηγορία απαιτεί συγκεκριμένο role και δεν το έχει,
  μπλοκάρεται με μήνυμα. Αλλιώς δημιουργείται ιδιωτικό text κανάλι ορατό μόνο
  σε αυτόν και στους staff roles (config.STAFF_ROLE_NAMES), μέσα στην κατηγορία
  TICKET_CATEGORY_NAME.
- Μέσα στο ticket υπάρχουν κουμπιά "Ανάληψη" (claim) και "Κλείσιμο" (close).
- Στο κλείσιμο δημιουργείται transcript (.txt) που στέλνεται στο κανάλι
  TICKET_LOG_CHANNEL_NAME, και το κανάλι του ticket διαγράφεται.

Τα ενεργά tickets αποθηκεύονται σε JSON αρχείο (config.TICKET_DATA_FILE).
"""

import io
import json
import os
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils_embeds import (
    info_embed,
    success_embed,
    warning_embed,
    add_user_field,
    add_moderator_field,
)
from utils_logging import send_log

DATA_FILE = config.TICKET_DATA_FILE


# ---------------------------------------------------------------------------
# Βοηθητικές συναρτήσεις
# ---------------------------------------------------------------------------

def _load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _slugify(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "user"


def is_staff(member: discord.Member) -> bool:
    return any(role.name in config.STAFF_ROLE_NAMES for role in member.roles)


def get_staff_roles(guild: discord.Guild) -> list[discord.Role]:
    return [role for role in guild.roles if role.name in config.STAFF_ROLE_NAMES]


def get_category(key: str) -> dict | None:
    return next((c for c in config.TICKET_CATEGORIES if c["key"] == key), None)


def _category_emoji(cat: dict) -> discord.PartialEmoji:
    return discord.PartialEmoji(
        name="ticket_emoji",
        id=cat["emoji_id"],
        animated=cat.get("emoji_animated", False),
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=cat["label"],
                description=cat["description"],
                emoji=_category_emoji(cat),
                value=cat["key"],
            )
            for cat in config.TICKET_CATEGORIES
        ]
        super().__init__(
            placeholder="Επίλεξε κατηγορία...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        await cog.create_ticket(interaction, self.values[0])


class TicketCategorySelectView(discord.ui.View):
    """Προσωρινό (όχι persistent) view - εμφανίζεται ephemeral μετά το κουμπί του panel."""

    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TicketCategorySelect())


class TicketPanelView(discord.ui.View):
    """Persistent view - το dropdown εμφανίζεται απευθείας στο panel."""

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


class TicketControlView(discord.ui.View):
    """Persistent view - κουμπιά μέσα σε ένα ήδη ανοιχτό ticket κανάλι."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ανάληψη",
        emoji="🙋",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_control:claim",
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        await cog.claim_ticket(interaction)

    @discord.ui.button(
        label="Κλείσιμο",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_control:close",
    )
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog: "Tickets" = interaction.client.get_cog("Tickets")
        await cog.request_close(interaction)


class TicketCloseConfirmView(discord.ui.View):
    """Προσωρινό view επιβεβαίωσης (όχι persistent, λήγει μετά από λίγο)."""

    def __init__(self, cog: "Tickets"):
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.button(label="Επιβεβαίωση Κλεισίματος", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Κλείνει το ticket...", view=self)
        await self.cog.close_ticket(interaction)

    @discord.ui.button(label="Άκυρο", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Η ενέργεια ακυρώθηκε.", view=self)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Καταχώρηση persistent views ώστε τα κουμπιά να δουλεύουν και μετά από restart
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())

    # -------------------- /ticket-panel --------------------

    @app_commands.command(
        name="ticket-panel",
        description="Στέλνει το πάνελ ανοίγματος ticket σε αυτό το κανάλι.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = info_embed(config.TICKET_PANEL_TITLE, config.TICKET_PANEL_DESCRIPTION)

        file = None
        if os.path.exists(config.TICKET_PANEL_LOGO_PATH):
            file = discord.File(config.TICKET_PANEL_LOGO_PATH, filename=config.TICKET_PANEL_LOGO_FILENAME)
            # Βάλε την εικόνα σαν "image" (μεγάλη, πάνω) αντί για thumbnail
            embed.set_image(url=f"attachment://{config.TICKET_PANEL_LOGO_FILENAME}")

        if file is not None:
            await interaction.channel.send(embed=embed, view=TicketPanelView(), file=file)
        else:
            await interaction.channel.send(embed=embed, view=TicketPanelView())

        await interaction.followup.send("Το πάνελ tickets στάλθηκε.", ephemeral=True)

    @ticket_panel.error
    async def ticket_panel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "Μόνο ο Administrator μπορεί να χρησιμοποιήσει αυτή την εντολή.", ephemeral=True
            )
        else:
            raise error

    # -------------------- Δημιουργία ticket --------------------

    async def create_ticket(self, interaction: discord.Interaction, category_key: str):
        category = get_category(category_key)
        if category is None:
            await interaction.response.send_message("Άγνωστη κατηγορία ticket.", ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user

        # Έλεγχος αν η κατηγορία απαιτεί Administrator
        if category.get("require_admin"):
            if not member.guild_permissions.administrator:
                await interaction.response.send_message(
                    f"Μόνο Administrators μπορούν να ανοίξουν '{category['label']}'.",
                    ephemeral=True,
                )
                return

        # Έλεγχος role-restricted κατηγορίας (π.χ. Support, Scan)
        required_role_id = category.get("required_role_id")
        if required_role_id is not None and not any(role.id == required_role_id for role in member.roles):
            role_obj = guild.get_role(required_role_id)
            role_text = role_obj.mention if role_obj else "τον απαιτούμενο ρόλο"
            await interaction.response.send_message(
                f"Δεν έχεις {role_text} για να ανοίξεις κατηγορία '{category['label']}'.",
                ephemeral=True,
            )
            return

        data = _load_data()

        # Έλεγχος αν ο χρήστης έχει ήδη ανοιχτό ticket σε αυτό το server
        for channel_id, info in list(data.items()):
            if info["guild_id"] == guild.id and info["user_id"] == member.id:
                channel = guild.get_channel(int(channel_id))
                if channel is not None:
                    await interaction.response.send_message(
                        f"Έχεις ήδη ανοιχτό ticket: {channel.mention}", ephemeral=True
                    )
                    return
                # ορφανή εγγραφή (το κανάλι διαγράφηκε χειροκίνητα) -> την αφαιρούμε
                del data[channel_id]
                _save_data(data)

        await interaction.response.defer(ephemeral=True)

        ticket_category = discord.utils.get(guild.categories, name=config.TICKET_CATEGORY_NAME)
        if ticket_category is None:
            try:
                ticket_category = await guild.create_category(
                    config.TICKET_CATEGORY_NAME,
                    reason="Αυτόματη δημιουργία κατηγορίας tickets",
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "Δεν έχω δικαίωμα να δημιουργήσω κατηγορία καναλιών. Ενημέρωσε το staff.",
                    ephemeral=True,
                )
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
            member: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True, attach_files=True
            ),
        }
        for role in get_staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

        channel_name = f"{category['channel_prefix']}-{_slugify(member.name)}"
        try:
            channel = await guild.create_text_channel(
                channel_name,
                category=ticket_category,
                overwrites=overwrites,
                reason=f"Ticket ({category['label']}) για {member} ({member.id})",
                topic=f"Ticket | {category['label']} | Χρήστης: {member.id} | Δεν έχει αναληφθεί",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Δεν έχω δικαίωμα να δημιουργήσω κανάλι. Ενημέρωσε το staff.", ephemeral=True
            )
            return

        data[str(channel.id)] = {
            "guild_id": guild.id,
            "user_id": member.id,
            "category": category_key,
            "claimed_by": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_data(data)

        welcome = info_embed(
            f"Νέο Ticket - {category['label']}",
            category["welcome_description"].format(mention=member.mention),
        )
        add_user_field(welcome, member)

        staff_mentions = " ".join(role.mention for role in get_staff_roles(guild))
        await channel.send(
            content=f"{member.mention} {staff_mentions}".strip(),
            embed=welcome,
            view=TicketControlView(),
        )

        await interaction.followup.send(f"Το ticket σου δημιουργήθηκε: {channel.mention}", ephemeral=True)

        log_embed = success_embed("Άνοιξε νέο ticket")
        add_user_field(log_embed, member)
        log_embed.add_field(name="Κατηγορία", value=category["label"], inline=False)
        log_embed.add_field(name="Κανάλι", value=channel.mention, inline=False)
        await send_log(guild, log_embed)

    # -------------------- Ανάληψη ticket --------------------

    async def claim_ticket(self, interaction: discord.Interaction):
        member = interaction.user
        if not is_staff(member):
            await interaction.response.send_message(
                "Μόνο το staff μπορεί να αναλάβει ticket.", ephemeral=True
            )
            return

        data = _load_data()
        info = data.get(str(interaction.channel.id))
        if info is None:
            await interaction.response.send_message(
                "Αυτό το κανάλι δεν είναι ενεργό ticket.", ephemeral=True
            )
            return

        if info.get("claimed_by"):
            claimer = interaction.guild.get_member(info["claimed_by"])
            await interaction.response.send_message(
                f"Το ticket έχει ήδη αναλάβει ο/η {claimer.mention if claimer else 'άγνωστο μέλος'}.",
                ephemeral=True,
            )
            return

        info["claimed_by"] = member.id
        data[str(interaction.channel.id)] = info
        _save_data(data)

        category = get_category(info.get("category"))
        category_label = category["label"] if category else "Ticket"
        try:
            await interaction.channel.edit(topic=f"Ticket | {category_label} | Ανέλαβε: {member.id}")
        except (discord.Forbidden, discord.HTTPException):
            pass

        embed = success_embed("Το ticket αναλήφθηκε")
        add_moderator_field(embed, member)
        await interaction.response.send_message(embed=embed)

        log_embed = info_embed("Ανάληψη ticket")
        add_moderator_field(log_embed, member)
        log_embed.add_field(name="Κανάλι", value=interaction.channel.mention, inline=False)
        await send_log(interaction.guild, log_embed)

    # -------------------- Αίτημα κλεισίματος --------------------

    async def request_close(self, interaction: discord.Interaction):
        data = _load_data()
        info = data.get(str(interaction.channel.id))
        if info is None:
            await interaction.response.send_message(
                "Αυτό το κανάλι δεν είναι ενεργό ticket.", ephemeral=True
            )
            return

        member = interaction.user
        if not (is_staff(member) or member.id == info["user_id"]):
            await interaction.response.send_message(
                "Δεν έχεις δικαίωμα να κλείσεις αυτό το ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Σίγουρα θες να κλείσεις αυτό το ticket; Θα δημιουργηθεί transcript και το κανάλι θα διαγραφεί.",
            view=TicketCloseConfirmView(self),
            ephemeral=True,
        )

    # -------------------- Κλείσιμο ticket --------------------

    async def close_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        guild = interaction.guild
        data = _load_data()
        info = data.get(str(channel.id))
        if info is None:
            await interaction.followup.send("Αυτό το ticket έχει ήδη κλείσει.", ephemeral=True)
            return

        closer = interaction.user
        category = get_category(info.get("category"))
        category_label = category["label"] if category else "Ticket"

        if config.TICKET_TRANSCRIPT_ON_CLOSE:
            transcript = await self._build_transcript(channel)
            log_channel = await self._ensure_ticket_log_channel(guild)
            if log_channel is not None:
                opener = guild.get_member(info["user_id"])
                if opener is None:
                    try:
                        opener = await self.bot.fetch_user(info["user_id"])
                    except discord.HTTPException:
                        opener = None

                summary = success_embed("Ticket έκλεισε")
                if opener is not None:
                    add_user_field(summary, opener)
                add_moderator_field(summary, closer)
                summary.add_field(name="Κατηγορία", value=category_label, inline=False)

                file = discord.File(transcript, filename=f"{channel.name}.txt")
                try:
                    await log_channel.send(embed=summary, file=file)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        del data[str(channel.id)]
        _save_data(data)

        log_embed = warning_embed("Κλείσιμο ticket")
        add_moderator_field(log_embed, closer)
        log_embed.add_field(name="Κανάλι", value=channel.name, inline=False)
        await send_log(guild, log_embed)

        await channel.delete(reason=f"Ticket έκλεισε από {closer}")

    async def _build_transcript(self, channel: discord.TextChannel) -> io.BytesIO:
        buffer = io.StringIO()
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = message.content or "[χωρίς κείμενο]"
            buffer.write(f"[{timestamp}] {message.author} ({message.author.id}): {content}\n")
            for attachment in message.attachments:
                buffer.write(f"    [attachment] {attachment.url}\n")
        return io.BytesIO(buffer.getvalue().encode("utf-8"))

    async def _ensure_ticket_log_channel(self, guild: discord.Guild):
        channel = discord.utils.get(guild.text_channels, name=config.TICKET_LOG_CHANNEL_NAME)
        if channel is not None:
            return channel

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        for role in get_staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        try:
            return await guild.create_text_channel(
                config.TICKET_LOG_CHANNEL_NAME,
                overwrites=overwrites,
                reason="Αυτόματη δημιουργία καναλιού ticket logs",
            )
        except discord.Forbidden:
            return None


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
