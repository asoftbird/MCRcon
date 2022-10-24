from math import trunc
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

# init
with open("config.json") as cfgfile:
    CFG = json.load(cfgfile)

BOTLOGFILE=CFG["botlog"]
CONFIGDB=CFG["configdb"]

logging.basicConfig( 
    encoding='utf-8', 
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='[%a %d-%m-%y %H:%M:%S]',
    handlers=[
        logging.FileHandler(BOTLOGFILE),
        logging.StreamHandler()
    ]
    )

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#TODO: figure out what intents are necessary
intents = discord.Intents(messages=True, guilds=True, members=True)
intents.message_content = True
intents.members = True

#TODO: configurable prefix per-server
bot = commands.Bot(command_prefix=';;', intents=intents)

####################
# Database helpers #
####################
# TODO: split off to db utils module
# TODO: make sure users can't perform SQL injects
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
    sqlstring = f'INSERT INTO {TABLENAME} (guildid, adminroleid, guildname, rconip, rconport, rconpw, mcip, mcport) values(?, ?, ?, ?, ?, ?, ?, ?)'
    try:
        with closing(sl.connect(dbname)) as db:
            with db:
                db.executemany(sqlstring, (data,))
                db.commit()
    except sl.IntegrityError as e:
        logging.warning(f"IntegrityError; skipped insert: {e}")

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

async def convert_time(timeTicks: int):
    time = (timeTicks/1000)+6 % 24
    hours = trunc(time)
    minutes = str(trunc((time - hours)*60)).zfill(2)
    hours = str(hours).zfill(2)
    return hours, minutes

#####################
# Utility functions #
#####################
# TODO: split off to util module
# TODO: documentation
async def get_guild_config(guild_id: str, dbname: str):
    result = await db_rowquery(guild_id, dbname)
    return result

async def check_guild_exists(guild_id: str, dbname:str):
    result = await db_squery("guildid", dbname)
    if guild_id in result:
        return True
    else:
        return False

async def register_guild(guild_id: str, dbname: str):
    if await check_guild_exists(str(guild_id), dbname) == False:
        data = [guild_id, "", "", "", "", "", "", ""]
        await db_insert(data, dbname)
        return True
    else:
        return False

async def set_guild_config(guild_id: str, fieldname: str, newvalue, dbname: str):
    if await check_guild_exists(str(guild_id), dbname) == True:
        await db_update(fieldname, newvalue, guild_id, dbname)
        return True
    else:
        return False

async def get_user_object(guild: discord.Guild, username):
    if username.isnumeric(): 
        # ID given
        user = guild.get_member(int(username))
        return user
    elif username.isalpha():
        # name given
        user = guild.get_member_named(username)
        return user
    else:
        user = guild.get_member_named(username)
        if user is not None:
            return user
        else:
            return None

async def rcon_command(command, guild_id: str):
    guildcfg = await get_guild_config(guild_id, CONFIGDB)
    RCONclient = Client(guildcfg['rconip'], int(guildcfg['rconport']), guildcfg['rconpw'])
    await RCONclient.connect()
    RCONresponse = await RCONclient.send_cmd(command)
    await RCONclient.close()
    return RCONresponse

async def check_user_command_permissions(author, guild_id: str, level: str):
    # TODO: add multiple / configurable permission levels for commands
    if level == "admin":
        # this command is admin only, check roles
        guildcfg = await get_guild_config(guild_id, CONFIGDB)
        roleids = [str(x.id) for x in author.roles]
        if guildcfg['adminroleid'] in roleids:
            return True
    elif level == "everyone":
        # everyone can use this, bypass check
        return True
    else:
        return False

#events
@bot.event
async def on_ready():
    logging.info(f"bot ready!")

@bot.event
async def on_command(ctx):
    logging.info(f"User {ctx.author.name} ({ctx.author.id}) from guild {ctx.guild.name} ({ctx.guild.id}) used command \"{ctx.message.content}\"")

@bot.event
async def on_command_completion(ctx):
    logging.info(f"Command \"{ctx.message.content}\" by {ctx.author.name} ({ctx.author.id}) in {ctx.guild.name} ({ctx.guild.id}) completed.")

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

# TODO: start using cogs to separate out command modules

# Server management
## Send command to server
@bot.command(aliases=['command'])
async def cmd(ctx, *args):
    if await check_user_command_permissions(ctx.author, ctx.guild.id, "admin") == True:
        arguments = ' '.join(args)
        response = await rcon_command(arguments, ctx.guild.id)
        await ctx.send(f'Sent command: "{arguments}" to server.')
        await ctx.send(f'Server response: {response[0]}')
    else:
        await ctx.send('Insufficient permissions.')

## Whitelisting! 
@bot.command(aliases=['wl'])
async def whitelist(ctx, operation, *args):
    if await check_user_command_permissions(ctx.author, ctx.guild.id, "admin") == True:
        argument = ' '.join(args)

        if operation == "multiadd" or operation == "add":
            if len(args) < 11:
                for i in args:
                    response = await rcon_command(f"whitelist add {i}", ctx.guild.id)
                    await ctx.send(f'{response[0]}')
            else:
                raise commands.TooManyArguments

        elif operation == "multidel" or operation == "del" or operation == "remove":
            if len(args) < 11:
                for i in args:
                    response = await rcon_command(f"whitelist remove {i}", ctx.guild.id)
                    await ctx.send(f'{response[0]}')
            else:
                raise commands.TooManyArguments

        elif operation == "reload":
            arguments = "whitelist reload"

        elif operation == "list":
            arguments = "whitelist list"

        else:
            raise commands.MissingRequiredArgument
        response = await rcon_command(arguments, ctx.guild.id)
        await ctx.send(f'Sent command: "{arguments}" to server.')
        await ctx.send(f'Server response: {response[0]}')
    else:
        await ctx.send('Insufficient permissions.')

# Server info
## Get player list from server
@bot.command()
async def status(ctx):
    guildcfg = await get_guild_config(ctx.guild.id, CONFIGDB)
    server = JavaServer(guildcfg['mcip'], int(guildcfg['mcport']))
    query = server.query()
    if await check_user_command_permissions(ctx.author, ctx.guild.id, "everyone") == True:
        #TODO: add configuration options based on MC version / config file 
        if guildcfg['guildname'] != 'gtnhserver': 
            # FIXME: quick hack to ensure it runs on private server
            tps = await rcon_command("forge tps overworld", ctx.guild.id)
            day = await rcon_command("time query day", ctx.guild.id)
            time = await rcon_command("time query daytime", ctx.guild.id)
            tps = tps[0][46:-1]
            day = day[0][12:-1]
            time = time[0][12:-1]
            time = int(time)
            time_hours, time_minutes = await convert_time(time)
            if time >= 23000 or time < 1000:
                timeWord = f"{time_hours}:{time_minutes} (sunrise)"
            elif time >= 1000 and time < 6000:
                timeWord = f"{time_hours}:{time_minutes} (morning)"
            elif time >= 6000 and time < 12000:
                timeWord = f"{time_hours}:{time_minutes} (afternoon)"
            elif time >= 12000 and time < 13000:
                timeWord = f"{time_hours}:{time_minutes} (sunset)"
            elif time >= 13000 and time < 18000:
                timeWord = f"{time_hours}:{time_minutes} (night)"
            elif time >= 18000 and time < 23000:
                timeWord = f"{time_hours}:{time_minutes} (late night)"

            await ctx.send(f"Players: {', '.join(query.players.names)} ({query.players.online}/{query.players.max})\nTPS: {tps}\nTime: day {day}, {timeWord}")
        else:
            await ctx.send(f"Players: {', '.join(query.players.names)} ({query.players.online}/{query.players.max})")
    else:
        await ctx.send('Insufficient permissions.')

# bot config
# TODO: make server admins able to use these command
## Get full current guild db info
@bot.command(aliases=['guildinfo'])
@commands.check_any(commands.is_owner())
async def ginf(ctx):
    guildcfg = await get_guild_config(str(ctx.guild.id), CONFIGDB)
    await ctx.send(guildcfg)

## Check if entry for current guild exists
@bot.command(aliases=['guildregistry'])
@commands.check_any(commands.is_owner())
async def greg(ctx):
    if await check_guild_exists(str(ctx.guild.id), CONFIGDB) == True:
        await ctx.send(f"Guild {ctx.guild.name} ({ctx.guild.id}) is registered!")
    else:
        await ctx.send(f"Guild {ctx.guild.name} ({ctx.guild.id}) is not registered!")

## Register guild
@bot.command(aliases=['guildregistryadd'])
@commands.check_any(commands.is_owner())
async def gregadd(ctx):
    if await register_guild(ctx.guild.id, CONFIGDB) == True:
        logging.info(f"Added entry for guild {ctx.guild.name} ({ctx.guild.id})!")
        await ctx.send(f"Added entry for guild {ctx.guild.name} ({ctx.guild.id})!")
    else:
        await ctx.send(f"Registry failed: {ctx.guild.name} .already registered.")

## Change an entry for current guild
@bot.command(aliases=['guildset'])
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
@bot.command(aliases=['guildget'])
@commands.check_any(commands.is_owner())
async def gget(ctx, fieldname):
    fieldnamelist = await db_getfieldnames(CONFIGDB)
    if fieldname in fieldnamelist:
        result = await get_guild_config(ctx.guild.id, CONFIGDB)
        fieldvalue = result[fieldname]
        await ctx.send(f"Checked config: {fieldname} is set to {fieldvalue}.")
    else:
       await ctx.send(f"Field not found!") 

## Request info on a user (provides username, nickname ID, list of roles + role IDs)
@bot.command(aliases=['userinfo'])
@commands.check_any(commands.is_owner())
async def uinf(ctx, *args):
    if await check_user_command_permissions(ctx.author, ctx.guild.id, "admin") == True:
        guild = ctx.guild
        username = ' '.join(args)
        user_object = await get_user_object(guild, username)
        if user_object is not None:
            rolenames = [str(x.name) for x in user_object.roles]
            roleIDs = [str(x.id) for x in user_object.roles]
            roles = dict(zip(rolenames, roleIDs))
            roles.pop("@everyone")
            await ctx.send(f"User: {user_object}, ID: {user_object.id}, name: {user_object.name}")
            await ctx.send(f"Roles: {roles}")
        else:
            await ctx.send(f"User not found!") 
    else:
        await ctx.send('Insufficient permissions.')

bot.run(TOKEN)