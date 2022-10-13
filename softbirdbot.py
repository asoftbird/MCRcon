import os
import discord
from aiomcrcon import Client
from discord.ext import commands
from mcstatus import JavaServer
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
RCONAUTH = os.getenv('RCON_AUTH')
RCONIP = str(os.getenv('RCON_IP'))
RCONPORT = int(os.getenv('RCON_PORT'))
MCPORT = int(os.getenv('MC_PORT'))
ADMINROLE = int(os.getenv('ADMINROLE_ID'))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=';;', intents=intents)

async def rcon_command(command):
    RCONclient = Client(RCONIP, RCONPORT, RCONAUTH)
    await RCONclient.connect()
    RCONresponse = await RCONclient.send_cmd(command)
    await RCONclient.close()
    return RCONresponse

#events
@bot.event
async def on_ready():
    print(f'bot ready!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.NotOwner):
        await ctx.send("Error: Only the bot owner can use this command!")
    elif isinstance(error, discord.ext.commands.errors.MissingRole):
        await ctx.send("Error: You are missing the required role.")
    elif isinstance(error, discord.ext.commands.errors.MissingRequiredArgument): 
        await ctx.send("Error: Command mistyped or missing required argument.")
    elif isinstance(error, discord.ext.commands.errors.TooManyArguments): 
        await ctx.send("Error: Too many arguments.")

############
# Commands #
############

# Server management
## Send command to server
@bot.command()
@commands.check_any(commands.is_owner(), commands.has_role(ADMINROLE))
async def cmd(ctx, *args):
    arguments = ' '.join(args)
    response = await rcon_command(arguments)
    await ctx.send(f'Sent command: "{arguments}" to server.')
    await ctx.send(f'Server response: {response}')

## Whitelisting! 
@bot.command(aliases=['wl'])
@commands.check_any(commands.is_owner(), commands.has_role(ADMINROLE))
async def whitelist(ctx, operation, *args):
    argument = ' '.join(args)
    if operation == "add":
        arguments = "whitelist add " + argument
    elif operation == "del" or operation == "remove":
        arguments = "whitelist remove " + argument
    elif operation == "list":
        arguments = "whitelist list"
    elif operation == "reload":
        arguments = "whitelist reload"
    elif operation == "multiadd":
        if len(args) < 11:
            for i in args:
                response = await rcon_command(f"whitelist add {i}")
                await ctx.send(f'{response}')
        else:
            raise commands.TooManyArguments
    elif operation == "multidel":
        if len(args) < 11:
            for i in args:
                response = await rcon_command(f"whitelist remove {i}")
                await ctx.send(f'{response}')
        else:
            raise commands.TooManyArguments
    else:
        raise commands.MissingRequiredArgument
    response = await rcon_command(arguments)
    await ctx.send(f'Sent command: "{arguments}" to server.')
    await ctx.send(f'Server response: {response}')

# Server info
## Get player list from server
@bot.command()
@commands.check_any(commands.is_owner(), commands.has_role(ADMINROLE))
async def status(ctx):
    server = JavaServer(RCONIP,MCPORT)
    query = server.query()
    tps = await rcon_command("forge tps overworld")
    day = await rcon_command("time query day")
    time = await rcon_command("time query daytime")
    tps = tps[0][46:-1]
    day = day[0][12:-1]
    time = time[0][12:-1]
    await ctx.send(f"Players: {', '.join(query.players.names)} ({query.players.online}/{query.players.max})\nTPS: {tps}\nTime: day {day}, {time}s")


bot.run(TOKEN)