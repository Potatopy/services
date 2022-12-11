from nextcord.ext import commands
import nextcord
import asyncio
import aiosqlite
import time as pyTime
import random
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")


class AddUser(nextcord.ui.Modal):
    def __init__(self, channel):
        super().__init__(
            "Add a user to the ticket",
            timeout=300
        )
        self.channel = channel
        self.user = nextcord.ui.TextInput(
            label="User ID",
            min_length=2,
            max_length=30,
            required=True,
            placeholder="User ID (Must be INT)"
        )
        self.add_item(self.user)

    async def callback(self, interaction: nextcord.Interaction):
        user = interaction.guild.get_member(int(self.user.value))
        if user is None:
            return await interaction.send(f"Invalid user ID! Make sure the user is in the server.", ephemeral=True)
        overwrite = nextcord.PermissionOverwrite()
        overwrite.read_messages = True
        await self.channel.set_permissions(user, overwrite=overwrite)
        await interaction.send(f"Added {user.mention} to the ticket!")


class RemoveUser(nextcord.ui.Modal):
    def __init__(self, channel):
        super().__init__(
            "Remove a user from the ticket",
            timeout=300
        )
        self.channel = channel
        self.user = nextcord.ui.TextInput(
            label="User ID",
            min_length=2,
            max_length=30,
            required=True,
            placeholder="User ID (Must be INT)"
        )
        self.add_item(self.user)

    async def callback(self, interaction: nextcord.Interaction):
        user = interaction.guild.get_member(int(self.user.value))
        if user is None:
            return await interaction.send(f"Invalid user ID! Make sure the user is in the server.", ephemeral=True)
        overwrite = nextcord.PermissionOverwrite()
        overwrite.read_messages = False
        await self.channel.set_permissions(user, overwrite=overwrite)
        await interaction.send(f"Removed {user.mention} from the ticket!")


class CreateTicket(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label="Create Ticket", style=nextcord.ButtonStyle.blurple, custom_id="create_ticket:blurple")
    async def create_ticket(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        msg = await interaction.response.send_message("Ticket is being made for you! :wink:", ephemeral=True)

        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT role FROM roles WHERE guild=?", (interaction.guild.id,))
            role = await cursor.fetchone()
            if role:
                overwrites = {
                    interaction.guild.default_role: nextcord.PermissionOverwrite(read_messages=False),
                    interaction.guild.me: nextcord.PermissionOverwrite(read_messages=True),
                    interaction.guild.get_role(role[0]): nextcord.PermissionOverwrite(read_messages=True),
                    interaction.user: nextcord.PermissionOverwrite(read_messages=True)
                }
            else:
                overwrites = {
                    interaction.guild.default_role: nextcord.PermissionOverwrite(read_messages=False),
                    interaction.guild.me: nextcord.PermissionOverwrite(read_messages=True),
                }

        channel = await interaction.guild.create_text_channel(f"{interaction.user.name}-ticket", overwrites=overwrites)
        await msg.edit(f"Channel created! {channel.mention}")
        embed = nextcord.Embed(title=f"Ticket Created!",
                               description=f"Ticket created by {interaction.user.mention}! Click any of the buttons below to add/remove users or delete the ticket and receive the transcript!",
                               color=nextcord.Color.blurple())
        await channel.send(embed=embed, view=TicketSettings())


class TicketSettings(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label="Add User", style=nextcord.ButtonStyle.green, custom_id="ticket_settings:green")
    async def add_user(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_modal(AddUser(interaction.channel))

    @nextcord.ui.button(label="Remove User", style=nextcord.ButtonStyle.gray, custom_id="ticket_settings:gray")
    async def remove_user(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await interaction.response.send_modal(RemoveUser(interaction.channel))

    @nextcord.ui.button(label="Close Ticket", style=nextcord.ButtonStyle.red, custom_id="ticket_settings:red")
    async def close_ticket(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        messages = await interaction.channel.history(limit=None, oldest_first=True).flatten()
        contents = [message.content for message in messages]
        final = ""
        for msg in contents:
            msg = msg + "\n"
            final = final + msg
        with open('transcript.txt', 'w') as f:
            f.write(final)
        await interaction.response.send_message("Ticket is being closed! :wink:", ephemeral=True)
        await interaction.channel.delete()
        await interaction.user.send(f"Ticket closed successfully! Here is the transcript:",
                                    file=nextcord.File('transcript.txt'))
        os.remove('transcript.txt')

class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistent_views_added = False

    async def on_ready(self):
        if not self.persistent_views_added:
            self.add_view(CreateTicket(self))
            self.add_view(TicketSettings())
            self.persistent_views_added = True
            print("Persistent views added.")
            self.db = await aiosqlite.connect("tickets.db")
            self.give = await aiosqlite.connect("giveaway.db")
            async with self.db.cursor() as cursor:
                await cursor.execute("CREATE TABLE IF NOT EXISTS roles (role INT, guild INT)")
            print("Tickets are ready!")

        print(f"{self.user} is ready!")
        print(f"Bot is ready || Logged in as {self.user}")


bot = Bot(command_prefix=',', intents=nextcord.Intents.all())
bot.remove_command('help')

@bot.command(name='setup_tickets', description='Setup the ticket system')
@commands.has_permissions(manage_guild=True)
async def setup_tickets(ctx: commands.Context):
    embed = nextcord.Embed(title="Support / Services",
                           description="Click on the `Create Ticket!` Button to create a ticket. And our staff will respond within 24 - 48 hrs.",
                           color=nextcord.Color.blurple())
    await ctx.send(embed=embed, view=CreateTicket(bot))

@bot.command(name='setup_role', description='Setup the role for the ticket system')
@commands.has_permissions(manage_guild=True)
async def setup_role(ctx: commands.Context, role: nextcord.Role):
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT role FROM roles WHERE guild=?", (ctx.guild.id,))
        role2 = await cursor.fetchone()
        if role2:
            await cursor.execute("UPDATE roles SET role=? WHERE guild=?", (role.id, ctx.guild.id))
            await ctx.send(f"Updated mod role to {role.mention}")
        else:
            await cursor.execute("INSERT INTO roles VALUES (?, ?)", (role.id, ctx.guild.id))
            await ctx.send(f"Set mod role to {role.mention}")
    await bot.db.commit()

@bot.command(name='kick', description='Kick a user from the guild')
@commands.has_permissions(kick_members=True)
async def kick(ctx: commands.Context, member: nextcord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"get out of here {member}")


@bot.command(name='ban', description='Ban a user from the guild')
@commands.has_permissions(ban_members=True)
async def ban(ctx: commands.Context, member: nextcord.Member, *, reason=None):
    await member.ban(reason=reason)
    await ctx.send(f"smoking that {member} pack lmao")


@bot.command(name='unban', description='Unban a user from the guild')
@commands.has_permissions(ban_members=True)
async def unban(ctx: commands.Context, member: nextcord.User, *, reason=None):
    await ctx.guild.unban(member, reason=reason)
    await ctx.send(f"{member} got a second chance")


@bot.command(name='clear', description='clear messages from the channel')
@commands.has_permissions(manage_messages=True)
async def clear(ctx: commands.Context, amount: int):
    await ctx.channel.purge(limit=amount)
    await ctx.send(f"cleared {amount} messages")


@bot.command(name='store', description='mute a user')
@commands.has_permissions(manage_guild=True)
async def store(ctx: commands.Context):
    await ctx.send(embed=nextcord.Embed(title="My Store!", description="https://h3lpeds-store.sellix.io/",
                                       color=nextcord.Color.purple()))


@bot.command()
@commands.has_permissions(manage_guild=True)
async def cashapp(ctx: commands.Context):
    embed = nextcord.Embed(
        title="Cashapp",
        description="Cashapp: https://cash.app/$h3lped",
        color=nextcord.Color.purple()
    )

    embed.set_image(url="https://media.discordapp.net/attachments/1043646377319739422/1045147863417639002/IMG_5219.png")

    await ctx.send(embed=embed)

def convert(time):
    pos = ["s", "m", "h", "d"]
    time_dict = {"s": 1, "m": 60, "h": 3600, "d": 3600*24}
    unit = time[-1]

    if unit not in pos:
        return -1
    try:
        val = int(time[:-1])
    except:
        return -2

    return val * time_dict[unit]

@bot.command()
@commands.has_permissions(manage_guild=True)
async def gstart(ctx):
    await ctx.send("answer the questions within 15 seconds to start the giveaway")

    questions = ["Which channel should it be hosted in?", 
    "What should be the duration of the giveaway? (s|m|h|d)", 
    "What is the prize of the giveaway?"]
    
    answers = []

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    for i in questions:
        await ctx.send(i)

        try:
            msg = await bot.wait_for("message", timeout=15.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("You didn't answer in time, please be quicker next time!")
            return
        else:
            answers.append(msg.content)

    try:
        c_id = int(answers[0][2:-1])
    except:
        await ctx.send(f"You didn't mention a channel properly. Do it like this {channel.mention} next time.")
        return

    time = convert(answers[1])
    if time == -1:
        await ctx.send(f"You didn't answer the time with a proper unit. Use (s|m|h|d) next time!")
        return
    elif time == -2:
        await ctx.send(f"The time must be an integer. Please enter an integer next time")
        return
    
    prize = answers[2]

    channel = bot.get_channel(c_id)
    
    await ctx.send(f"The Giveaway will be in {channel.mention} and will last {answers[1]}")

    embed = nextcord.Embed(title="Giveaway!", description=f"{prize}", color=nextcord.Color.purple())

    embed.add_field(name="Hosted by:", value=ctx.author.mention)

    embed.set_footer(text=f"Ends {answers[1]} from now!")

    my_msg = await channel.send(embed=embed)

    await my_msg.add_reaction("🎉")

    await asyncio.sleep(time)

    new_msg = await channel.fetch_message(my_msg.id)

    users = await new_msg.reactions[0].users().flatten()
    users.pop(users.index(bot.user))

    winner = random.choice(users)

    await channel.send(f"Congratulations! {winner.mention} won {prize}!")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def greroll(ctx, channel: nextcord.TextChannel, id_: int):
    try:
        new_msg = await channel.fetch_message(id_)
    except:
        await ctx.send("The id was entered incorrectly.")
        return

    users = await new_msg.reactions[0].users().flatten()
    users.pop(users.index(bot.user))

    winner = random.choice(users)

    await channel.send(f"The new winner is {winner.mention}!")

@bot.command()
@commands.has_permissions(manage_guild=True)
async def gend(ctx, channel: nextcord.TextChannel, id_: int):
    try:
        new_msg = await channel.fetch_message(id_)
    except:
        await ctx.send("The id was entered incorrectly.")
        return

    users = await new_msg.reactions[0].users().flatten()
    users.pop(users.index(bot.user))

    winner = random.choice(users)

    await channel.send(f"The giveaway has ended and the winner is {winner.mention}!")

@bot.command()
async def help(ctx):
    embed = nextcord.Embed(
        title="Help",
        description="My prefix is `,`",
        color=nextcord.Color.purple()
    )
    for command in bot.walk_commands():
        description = command.description
        if not description or description is None or description == "":
            description = 'No description'
        embed.add_field(name=f',{command.name}{command.signature if command.signature is not None else ""}', value=description)
    await ctx.send(embed=embed)

@bot.command()
async def crypto(ctx):
    em = nextcord.Embed(
        title="Crypto Wallets",
        description="My crypto wallets (if the crypto is not listed, tell me and i will see id i can accept it)",
    )
    em.add_field(name="Bitcoin", value="bc1qpk407aahx69frvaxzq2wmp968utj654767kn0h")
    em.add_field(name="Ethereum", value="0x82A99144149373f96710Dd24be9e6C233264D616")
    em.add_field(name="Litecoin", value="LNJ91UYHxBj6ciBuMPWfsk3BUqePPWMtQz")
    await ctx.send(embed=em)

bot.run(TOKEN)
