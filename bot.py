import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import re

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN was not found in the .env file.")

GUILD_ID = 1536214555196395631
TICKET_CATEGORY_ID = 1543403330867560519
COACHING_CHANNEL_ID = 1543408314476535958

HIGH_COMMAND_ROLE_NAME = "High Command"
SUPPORT_TEAM_ROLE_NAME = "Support Team"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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


def is_ticket_staff(member):
    return any(
        role.name in {HIGH_COMMAND_ROLE_NAME, SUPPORT_TEAM_ROLE_NAME}
        for role in member.roles
    )


class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Close Ticket",
            emoji="🔒",
            style=discord.ButtonStyle.danger,
            custom_id="northstar_close_ticket"
        )

    async def callback(self, interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Something went wrong.",
                ephemeral=True
            )
            return

        if not is_ticket_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Only **High Command** or **Support Team** can close tickets.",
                ephemeral=True
            )
            return

        channel = interaction.channel

        await interaction.response.send_message(
            "🔒 Ticket closed. Deleting channel...",
            ephemeral=True
        )

        try:
            await channel.delete(
                reason=f"Ticket closed by {interaction.user}"
            )
        except discord.Forbidden:
            print("ERROR: I do not have permission to delete the ticket.")
        except discord.HTTPException as error:
            print(f"ERROR deleting ticket: {error}")


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicketButton())


class ServiceDeskSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=service["label"],
                description=service["description"],
                emoji=service["emoji"],
                value=service_id
            )
            for service_id, service in SERVICES.items()
        ]

        super().__init__(
            placeholder="Select a service...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="northstar_service_desk"
        )

    async def callback(self, interaction):
        guild = interaction.guild
        user = interaction.user
        selected = self.values[0]
        service = SERVICES[selected]

        if guild is None:
            await interaction.response.send_message(
                "❌ Something went wrong: server not found.",
                ephemeral=True
            )
            return

        category = guild.get_channel(TICKET_CATEGORY_ID)

        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ I couldn't find the Support Tickets category.",
                ephemeral=True
            )
            return

        high_command = discord.utils.get(
            guild.roles,
            name=HIGH_COMMAND_ROLE_NAME
        )

        support_team = discord.utils.get(
            guild.roles,
            name=SUPPORT_TEAM_ROLE_NAME
        )

        if high_command is None:
            await interaction.response.send_message(
                "❌ I couldn't find the **High Command** role.",
                ephemeral=True
            )
            return

        if support_team is None:
            await interaction.response.send_message(
                "❌ I couldn't find the **Support Team** role.",
                ephemeral=True
            )
            return

        ticket_topic = f"ticket-owner:{user.id}:service-{selected}"

        for existing_channel in category.text_channels:
            if existing_channel.topic == ticket_topic:
                await interaction.response.send_message(
                    f"❌ You already have an open **{service['label']}** "
                    f"ticket: {existing_channel.mention}",
                    ephemeral=True
                )
                return

        safe_name = re.sub(
            r"[^a-zA-Z0-9_-]",
            "",
            user.name
        ).lower()

        if not safe_name:
            safe_name = str(user.id)

        channel_name = f"ticket-{selected}-{safe_name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            high_command: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            ),
            support_team: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )
        }

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=ticket_topic,
                overwrites=overwrites
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create ticket channels.",
                ephemeral=True
            )
            return
        except discord.HTTPException as error:
            print(f"ERROR creating ticket: {error}")
            await interaction.response.send_message(
                "❌ Discord failed to create the ticket.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{service['emoji']} {service['label']}",
            description=(
                f"Welcome {user.mention}!\n\n"
                f"**Service:** {service['label']}\n\n"
                "Please explain what you need help with below.\n\n"
                "🔒 **Private Ticket**\n"
                "Only you, High Command, and Support Team can see this ticket.\n\n"
                "📝 **Please provide as much detail as possible.**"
            ),
            colour=discord.Colour.blue()
        )

        embed.set_footer(text="Northstar Service Desk")

        try:
            await channel.send(
                content=f"{high_command.mention} {support_team.mention}",
                embed=embed,
                view=CloseTicketView(),
                allowed_mentions=discord.AllowedMentions(roles=True)
            )
        except discord.HTTPException as error:
            print(f"ERROR sending ticket message: {error}")

        await interaction.response.send_message(
            f"✅ Your **{service['label']}** ticket has been created: "
            f"{channel.mention}",
            ephemeral=True
        )


class ServiceDeskView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ServiceDeskSelect())


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    bot.add_view(ServiceDeskView())
    bot.add_view(CloseTicketView())

    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)

    try:
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to Northstar")
    except Exception as error:
        print(f"Failed to sync commands: {error}")


@bot.tree.command(
    name="setup",
    description="Set up the Northstar Service Desk"
)
async def setup(interaction):
    coaching_text = (
        "🧑‍🏫 **Looking for coaching?**\n"
        f"Speak to one of our Coaches in <#{COACHING_CHANNEL_ID}>."
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


bot.run(TOKEN)
