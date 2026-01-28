import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
import threading
import os
import asyncio
import io
import datetime

# ----------------- CONFIGURATION -----------------
TOKEN = os.getenv("DISCORD_TOKEN") # Ne mets pas ton token ici en clair !
COLOR = 0x7110ff
TICKET_CATEGORY_ID = 1465103469785514067      # ID de la catégorie Tickets
LOG_CHANNEL_ID = 1461729802343026924  # ID du salon des logs

# ----------------- KEEP ALIVE (WEB SERVER) -----------------
app = Flask('')
@app.route('/')
def home(): return "Void Assistant is running!"

def run(): app.run(host="0.0.0.0", port=8080)
def keep_alive(): threading.Thread(target=run).start()

# ----------------- TICKET LOGIC -----------------
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ **Generating transcript and closing ticket...**")
        
        channel = interaction.channel
        logs_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        
        transcript = f"--- VOID MARKET TRANSCRIPT: {channel.name} ---\n"
        transcript += f"Closed by: {interaction.user} ({interaction.user.id})\n"
        transcript += f"Date: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
        transcript += "-"*40 + "\n\n"

        async for message in channel.history(limit=None, oldest_first=True):
            time = message.created_at.strftime('%H:%M:%S')
            content = message.content if message.content else "[File/Image]"
            transcript += f"[{time}] {message.author}: {content}\n"

        file = discord.File(io.BytesIO(transcript.encode()), filename=f"log-{channel.name}.txt")

        if logs_channel:
            log_embed = discord.Embed(
                title="🔒 Ticket Archived",
                description=f"Ticket `{channel.name}` has been closed.",
                color=COLOR,
                timestamp=discord.utils.utcnow()
            )
            log_embed.set_footer(text="Void Market Logs")
            await logs_channel.send(embed=log_embed, file=file)

        await asyncio.sleep(2)
        await channel.delete()

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Purchase", description="Open a ticket to buy a product", emoji="🛒"),
            discord.SelectOption(label="Support", description="General assistance and questions", emoji="💬"),
            discord.SelectOption(label="Replacement", description="Request a product replacement", emoji="⚙️"),
        ]
        super().__init__(placeholder="Select a ticket category...", min_values=1, max_values=1, options=options, custom_id="void_select")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"{self.values[0].lower()}-{user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"✅ Your ticket has been created: {channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title=f"{self.values[0]} Ticket",
            description="Please wait until the owner can help you. **Response time may vary due to many factors, so please be patient.**",
            color=COLOR
        )
        if guild.icon: embed.set_thumbnail(url=guild.icon.url)

        if self.values[0] == "Replacement":
            embed.add_field(
                name="🔧 Replacement Requirements",
                value="Please provide the following information:\n• **Video** accessing the account.\n• **Invoice ID and Order ID**.\n• **Full proof** of payment.\n• **Email** used for payment.",
                inline=False
            )
        elif self.values[0] == "Purchase":
            embed.description = "Please tell us which product you would like to buy and your preferred payment method."

        embed.set_footer(text="Void Market • Fast & Reliable")
        await channel.send(content=f"{user.mention} | @everyone", embed=embed, view=CloseTicketView())

class TicketMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ----------------- BOT SETUP -----------------

class VoidAssistant(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketMenuView())
        self.add_view(CloseTicketView())

    async def on_ready(self):
        # Configuration du statut "Ne pas déranger" et de l'activité Playing
        await self.change_presence(
            status=discord.Status.do_not_disturb, 
            activity=discord.Game(name="✨Managing tickets..")
        )
        print(f"✅ {self.user} is online")
        await self.tree.sync()

bot = VoidAssistant()

@bot.tree.command(name="setup_tickets", description="Post the ticket menu")
@app_commands.default_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Void Market Assistant",
        description="If you need help, click on the option corresponding to the type of ticket you want to open. **Response time may vary to many factors, so please be patient.**",
        color=COLOR
    )
    if interaction.guild.icon: embed.set_thumbnail(url=interaction.guild.icon.url)
    await interaction.channel.send(embed=embed, view=TicketMenuView())
    await interaction.response.send_message("✅ Menu posted.", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
