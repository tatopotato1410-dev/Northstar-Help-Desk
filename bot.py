import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import re

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = 1536214555196395631
TICKET_CATEGORY_ID = 1543403330867560519
COACHING_CHANNEL_ID = 1543408314476535958


STAFF_ROLES = {
    "Admin",
    "The Steward",
    "Executive",
    "Council"
}


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================================================
# SERVICE TYPES
# =========================================================

SERVICES = {
    "member_support": {
        "label": "Member Support",
        "emoji": "👥",
        "description": "Get help with a problem or question"
    },

    "submit_request": {
        "label": "Submit a Request",
        "emoji": "📋",
        "description": "Submit a request to Northstar staff"
    },

    "report_issue": {
        "label": "Report an Issue",
        "emoji": "📝",
        "description": "Report a problem that needs staff attention"
    },

    "give_feedback": {
        "label": "Give Feedback",
        "emoji": "💡",
        "description": "Send feedback or a suggestion"
    },

    "other": {
        "label": "Other",
        "emoji": "❓",
        "description": "Something that doesn't fit the other categories"
    }
}


# =========================================================
# CLOSE TICKET BUTTON
# =========================================================

class CloseTicketButton(discord.ui.Button):

    def __init__(self):

        super().__init__(
            label="Close Ticket",
            emoji="🔒",
            style=discord.ButtonStyle.danger,
            custom_id="northstar_close_ticket"
        )

    async def callback(self, interaction: discord.Interaction):

        user = interaction.user

        is_staff = any(
            role.name in STAFF_ROLES
            for role in user.roles
        )

        if not is_staff:

            await interaction.response.send_message(
                "❌ Only Northstar staff can close tickets.",
                ephemeral=True
            )

            return

        channel = interaction.channel

        await interaction.response.send_message(
            "🔒 Ticket closed. Deleting channel...",
            ephemeral=True
        )

        await channel.delete(
            reason=f"Ticket closed by {user}"
        )


class CloseTicketView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(CloseTicketButton())


# =========================================================
# SERVICE DESK DROPDOWN
# =========================================================

class ServiceDeskSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for service_id, service in SERVICES.items():

            options.append(
                discord.SelectOption(
                    label=service["label"],
                    description=service["description"],
                    emoji=service["emoji"],
                    value=service_id
                )
            )

        super().__init__(
            placeholder="Select a service...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="northstar_service_desk"
        )

    async def callback(self, interaction: discord.Interaction):

        selected = self.values[0]
        service = SERVICES[selected]

        guild = interaction.guild
        user = interaction.user

        if guild is None:

            await interaction.response.send_message(
                "❌ Something went wrong: server not found.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # FIND TICKET CATEGORY
        # -------------------------------------------------

        category = guild.get_channel(TICKET_CATEGORY_ID)

        if category is None:

            await interaction.response.send_message(
                "❌ I couldn't find the Support Tickets category.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # PREVENT DUPLICATE TICKET OF SAME TYPE
        # -------------------------------------------------

        ticket_topic = (
            f"ticket-owner:{user.id}:service-{selected}"
        )

        for channel in category.text_channels:

            if channel.topic == ticket_topic:

                await interaction.response.send_message(
                    f"❌ You already have an open "
                    f"**{service['label']}** ticket: {channel.mention}",
                    ephemeral=True
                )

                return

        # -------------------------------------------------
        # CREATE SAFE USERNAME
        # -------------------------------------------------

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]",
            "",
            user.name
        ).lower()

        if not safe_name:
            safe_name = str(user.id)

        # -------------------------------------------------
        # CREATE TICKET NAME
        # -------------------------------------------------

        channel_name = (
            f"🎫・{selected.replace('_', '-')}-{safe_name}"
        )

        # -------------------------------------------------
        # CREATE CHANNEL
        # -------------------------------------------------

        try:

            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=ticket_topic
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to create ticket channels.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            print(f"Failed to create ticket: {e}")

            await interaction.response.send_message(
                "❌ Discord failed to create the ticket.",
                ephemeral=True
            )

            return

        # -------------------------------------------------
        # TICKET EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title=f"{service['emoji']} {service['label']}",
            description=(
                f"Welcome {user.mention}!\n\n"
                f"**Service:** {service['label']}\n\n"
                "Please explain what you need help with below.\n\n"
                "Everyone in Northstar can see and respond to this ticket.\n\n"
                "📝 **Please provide as much detail as possible.**"
            )
        )

        embed.set_footer(
            text="Northstar Service Desk"
        )

        # -------------------------------------------------
        # SEND TICKET MESSAGE
        # -------------------------------------------------

        await channel.send(
            embed=embed,
            view=CloseTicketView()
        )

        # -------------------------------------------------
        # CONFIRMATION
        # -------------------------------------------------

        await interaction.response.send_message(
            f"✅ Your **{service['label']}** ticket has been created: "
            f"{channel.mention}",
            ephemeral=True
        )


# =========================================================
# SERVICE DESK VIEW
# =========================================================

class ServiceDeskView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(ServiceDeskSelect())


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    # Register persistent components
    bot.add_view(ServiceDeskView())
    bot.add_view(CloseTicketView())

    guild = discord.Object(id=GUILD_ID)

    bot.tree.copy_global_to(guild=guild)

    try:

        synced = await bot.tree.sync(guild=guild)

        print(
            f"Synced {len(synced)} command(s) to Northstar"
        )

    except Exception as e:

        print(
            f"Failed to sync commands: {e}"
        )


# =========================================================
# SETUP COMMAND
# =========================================================

@bot.tree.command(
    name="setup",
    description="Set up the Northstar Service Desk"
)
async def setup(interaction: discord.Interaction):

    coaching_text = (
        "🧑‍🏫 **Looking for coaching?**\n"
        f"Speak to one of our Coaches in "
        f"<#{COACHING_CHANNEL_ID}>."
    )

    embed = discord.Embed(
        title="🛎️ Northstar Service Desk",
        description=(
            "Need assistance? Select an option below and we'll get you "
            "to the right place.\n\n"

            "👥 **Member Support**\n"
            "General questions, problems or assistance.\n\n"

            "📋 **Submit a Request**\n"
            "Request something from Northstar staff.\n\n"

            "📝 **Report an Issue**\n"
            "Report a problem that needs staff attention.\n\n"

            "💡 **Give Feedback**\n"
            "Suggestions and feedback for Northstar.\n\n"

            "❓ **Other**\n"
            "Anything that doesn't fit the other categories.\n\n"

            f"{coaching_text}"
        )
    )

    embed.set_footer(
        text="Northstar Service Desk • Select a service below"
    )

    await interaction.channel.send(
        embed=embed,
        view=ServiceDeskView()
    )

    await interaction.response.send_message(
        "✅ Service Desk panel created.",
        ephemeral=True
    )


# =========================================================
# START BOT
# =========================================================

bot.run(TOKEN)