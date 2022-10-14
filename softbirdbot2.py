import os
import json
import logging
import discord
import sqlite3 as sl
from aiomcrcon import Client
from contextlib import closing
from discord.ext import commands
from mcstatus import JavaServer
from dotenv import load_dotenv

# config
with open("config.json") as cfgfile:
    CFG = json.load(cfgfile)

BOTLOGFILE=CFG["botlog"]
CONFIGDB=CFG["configdb"]



logging.basicConfig(filename=BOTLOGFILE, 
    encoding='utf-8', 
    level=logging.INFO, 
    format='%(asctime)s %(message)s',
    datefmt='[%a %d-%m-%y %H:%M:%S]'
    )

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

####################
# Database helpers #
####################

TABLENAME = "CONFIG"

async def db_insert(data: list, dbname: str):
    """ Insert a list of data into a full database row for new server signups.

        Parameters
        ----------
        data : list
            List of input items.
        db: sl.Connection
            Target database connection.

        Raises
        ------
        sl.IntegrityError
            If entry already exists. 
    """
    # TODO: error handler decorator
    sqlstring = f'INSERT INTO {TABLENAME} (guildid, adminroleid, rconip, rconport, rconpw, mcip, mcport, guildname) values(?, ?, ?, ?, ?, ?, ?, ?)'
    try:
        with closing(sl.connect(dbname)) as db:
            with db:
                db.executemany(sqlstring, (data,))
                db.commit()
    except sl.IntegrityError as e:
        logging.warning(f"{e}")
        print("IntegrityError; skipped insert")

async def db_getfieldnames(dbname: str):
    sqlstring = f'SELECT * FROM {TABLENAME}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                cursor.execute(sqlstring)
                records = [x[0] for x in cursor.description]
    return records

async def db_rowquery(guild_id: int, dbname: str):
    """ Query all entries in a specified database row.

        Parameters
        ----------
        guild_id : int
            identifier for the row to pull from
        db: sl.Connection
            Target database connection.

        Returns
        -------
        list
            List of matching entries in the full row.
    """
    sqlstring = f'SELECT * FROM {TABLENAME} WHERE guildid={guild_id}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                cursor.execute(sqlstring)
                records = list([x for x in cursor][0])
    fields = await db_getfieldnames(dbname)
    resultdict = dict(zip(fields, records))
    return resultdict

async def db_query(field: str, entry: str, operator: str, value, dbname: str):
    """ Query a specified database entry with comparison operators.

        Parameters
        ----------
        field: str
            Name of the field of which you want the entry. 
        entry: str
            Target field to compare with value.
        operator: str
            Operator to use, e.g. =, !=, <=, >=.
        value: Any
            Value to compare entry to.
        db: sl.Connection
            Target database connection.

        Returns
        -------
        list
            List of matching entry values.
    """
    # TODO: error handler decorator
    sqlstring = f'SELECT {field} FROM {TABLENAME} WHERE {entry} {operator} {value}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                data = cursor.execute(sqlstring)
                return [i[0] for i in data]

async def db_squery(field: str, dbname: str):
    """ Query all entries in a specified database column.

        Parameters
        ----------
        field : str
            Name of the field to return.
        db: sl.Connection
            Target database connection.

        Returns
        -------
        list
            List of matching entries in the full column.
    """
    sqlstring = f'SELECT {field} FROM {TABLENAME}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                data = cursor.execute(sqlstring)
                return ([x[0] for x in data])

async def db_queryguildentry(field: str, guild_id: int, dbname: str):
    sqlstring = f'SELECT {field} FROM {TABLENAME} WHERE guildid={guild_id}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                data = cursor.execute(sqlstring)
                return [i[0] for i in data]

async def db_update(field: str, newval, guild_id: int, dbname: str):
    """ Update a specific entry in a column and row matched by the specified field and guildid.

        Parameters
        ----------
        field: str
            Name of the target field.
        newval: Any
            New value to write to target entry.
        guild_id: int
            ID of the guild to update the value for.
        db: sl.Connection
            Target database connection.
    """
    sqlstring = f'UPDATE {TABLENAME} SET {field}=? WHERE guildid==?'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                cursor.execute(sqlstring, (newval, guild_id,))
                db.commit()

#####################
# Bot configuration #
#####################

async def get_guild_config(guild_id: str, dbname: str):
    result = await db_rowquery(guild_id, dbname)
    return result

async def check_guild_exists(guild_id: str, dbname:str):
    result = await db_squery("guildid", dbname)
    if guild_id in result:
        return True
    else:
        return False

async def set_guild_config(guild_id: str, fieldname: str, newvalue, dbname: str):
    if await check_guild_exists(str(guild_id), CONFIGDB) == True:
        await db_update(fieldname, newvalue, guild_id, dbname)
        return True
    else:
        return False



####################
# MC Server access #
####################

async def rcon_command(command, guild_id: str):
    guildcfg = await get_guild_config(guild_id, CONFIGDB)
    RCONclient = Client(guildcfg['rconip'], guildcfg['rconport'], guildcfg['rconpw'])
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
@commands.check_any(commands.is_owner()) #commands.has_role(ADMINROLE)
async def cmd(ctx, *args):
    guildcfg = await get_guild_config(ctx.guild.id, CONFIGDB)
    author_roles = ctx.author.roles
    if guildcfg['adminroleid'] in author_roles:
        arguments = ' '.join(args)
        response = await rcon_command(arguments, ctx.guild.id)
        await ctx.send(f'Sent command: "{arguments}" to server.')
        await ctx.send(f'Server response: {response}')
    else:
        await ctx.send(f'Insufficient permissions.')

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
                response = await rcon_command(f"whitelist add {i}", ctx.guild.id)
                await ctx.send(f'{response}')
        else:
            raise commands.TooManyArguments
    elif operation == "multidel":
        if len(args) < 11:
            for i in args:
                response = await rcon_command(f"whitelist remove {i}", ctx.guild.id)
                await ctx.send(f'{response}')
        else:
            raise commands.TooManyArguments
    else:
        raise commands.MissingRequiredArgument
    response = await rcon_command(arguments, ctx.guild.id)
    await ctx.send(f'Sent command: "{arguments}" to server.')
    await ctx.send(f'Server response: {response}')

# Server info
## Get player list from server
@bot.command()
@commands.check_any(commands.is_owner(), commands.has_role(ADMINROLE))
async def status(ctx):
    guildcfg = await get_guild_config(ctx.guild.id, CONFIGDB)
    server = JavaServer(guildcfg['mcip'],guildcfg['mcport'])
    query = server.query()
    tps = await rcon_command("forge tps overworld", ctx.guild.id)
    day = await rcon_command("time query day", ctx.guild.id)
    time = await rcon_command("time query daytime", ctx.guild.id)
    tps = tps[0][46:-1]
    day = day[0][12:-1]
    time = time[0][12:-1]
    await ctx.send(f"Players: {', '.join(query.players.names)} ({query.players.online}/{query.players.max})\nTPS: {tps}\nTime: day {day}, {time}s")



# bot config
## Get full current guild db info
@bot.command()
@commands.check_any(commands.is_owner())
async def ginf(ctx):
    guildcfg = await get_guild_config(str(ctx.guild.id), CONFIGDB)
    await ctx.send(guildcfg)

## Check if entry for current guild exists
@bot.command()
@commands.check_any(commands.is_owner())
async def greg(ctx):
    print("greg")
    if await check_guild_exists(str(ctx.guild.id), CONFIGDB) == True:
        await ctx.send(f"Guild {ctx.guild.name} ({ctx.guild.id}) is registered!")
    else:
        await ctx.send(f"Guild {ctx.guild.name} ({ctx.guild.id}) is not registered!")

## Change an entry for current guild
@bot.command()
@commands.check_any(commands.is_owner())
async def gset(ctx, fieldname, value):
    fieldnamelist = await db_getfieldnames(CONFIGDB)
    if fieldname in fieldnamelist:
        if fieldname != 'guildid':
            result = await set_guild_config(ctx.guild.id, fieldname, value, CONFIGDB)
            if result == True:
                logging.info(f"Updated config for {ctx.guild.id}: {fieldname} set to {value}.")
                await ctx.send(f"Updated config: {fieldname} set to {value}.")
            else:
                await ctx.send(f"Entry or guild not found!")
        else:
            await ctx.send(f"Cannot change guildid!")

## Get the value of a single entry for current guild
@bot.command()
@commands.check_any(commands.is_owner())
async def gget(ctx, fieldname):
    fieldnamelist = await db_getfieldnames(CONFIGDB)
    if fieldname in fieldnamelist:
        result = await get_guild_config(ctx.guild.id, CONFIGDB)
        fieldvalue = result[fieldname]
        await ctx.send(f"Checked config: {fieldname} is set to {fieldvalue}.")
    else:
       await ctx.send(f"Field not found!") 


bot.run(TOKEN)