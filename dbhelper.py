from contextlib import closing
import sqlite3 as sl
import logging
import json

# config
with open("config.json") as cfgfile:
    CFG = json.load(cfgfile)

LOGFILE=CFG["dblog"]
CONFIGDB=CFG["configdb"]

logging.basicConfig(filename=LOGFILE, 
    encoding='utf-8', 
    level=logging.INFO, 
    format='%(asctime)s %(message)s',
    datefmt='[%a %d-%m-%y %H:%M:%S]'
    )

dbcon = sl.connect(CONFIGDB)
TABLENAME = "CONFIG"
# with dbcon:
#     dbcon.execute("""
#         CREATE TABLE CONFIG (
#             guildid TEXT PRIMARY KEY,
#             adminroleid TEXT,
#             guildname TEXT,
#             rconip TEXT,
#             rconport TEXT,
#             rconpw TEXT,
#             mcip TEXT,
#             mcport TEXT
#         );
#     """)

# FTS 398915618868428811 / 862719092104757249
# TT 783401696277168138 / 983868264570576906

FTS_data = [
    "398915618868428811",
    "8627190921047572491",
    "file transfer",
    "127.0.0.1",
    "1234",
    "FTSpw",
    "127.0.0.2",
    "5678"
]

TT_data = [
    "783401696277168138",
    "983868264570576906",
    "tufties",
    "192.168.0.1",
    "69420",
    "TTpw",
    "192.168.0.2",
    "25565"
]


def db_insert(data1: list, db: sl.Connection):
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
    print("db_insert fired")
    sqlstring = f'INSERT INTO {TABLENAME} (guildid, adminroleid, guildname, rconip, rconport, rconpw, mcip, mcport) values(?, ?, ?, ?, ?, ?, ?, ?)'
    data = data1 #list(zip(data1, data2))
    print(data)
    try:
        with db:
            db.executemany(sqlstring, (data,))
            db.commit()
    except sl.IntegrityError as e:
        logging.warning(f"{e}")
        print("IntegrityError; skipped insert")

def db_query(field: str, entry: str, operator: str, value, db: sl.Connection):
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
    print("db_query fired")
    cursor = db.cursor()
    sqlstring = f'SELECT {field} FROM {TABLENAME} WHERE {entry} {operator} {value}'
    with db:
        data = cursor.execute(sqlstring)
        return [i[0] for i in data]

def db_squery(field: str, db: sl.Connection):
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
    # TODO: error handler decorator
    print("db_squery fired")
    cursor = db.cursor()
    sqlstring = f'SELECT {field} FROM {TABLENAME}'
    with db:
        data = cursor.execute(sqlstring)
        return [i[0] for i in data]

def db_getfieldnames(dbname: str):
    print("db_getfieldnames fired")
    sqlstring = f'SELECT * FROM {TABLENAME}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                cursor.execute(sqlstring)
                records = [x[0] for x in cursor.description]
    return records

def db_rowquery(guild_id: int, dbname: str):
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
    print("db_rowquery fired")
    sqlstring = f'SELECT * FROM {TABLENAME} WHERE guildid={guild_id}'
    with closing(sl.connect(dbname)) as db:
        with db:
            with closing(db.cursor()) as cursor:
                cursor.execute(sqlstring)
                records = list([x for x in cursor][0])
                print(records)
    fields = db_getfieldnames(db)
    print(fields)
    resultdict = dict(zip(fields, records))
    print(resultdict)

    return resultdict

def db_update(field: str, newval, guild_id: int, db: sl.Connection):
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
    print("db_update fired")
    cursor = db.cursor()
    sqlstring = f'UPDATE {TABLENAME} SET {field}=? WHERE guildid==?'
    with db:
        cursor.execute(sqlstring, (newval,guild_id,))
        db.commit()

# guildid, adminroleid, rconip, rconport, rconpw, mcip, mcport, guildname
db_insert(TT_data, dbcon)
# print(db_update('guildname', 'FTS', 398915618868428811, dbcon))

# print(f"admin role IDs: {db_squery('adminroleid', dbcon)}")
# print(f"admin role ID for TT: {db_query('adminroleid', 'guildid', '==', '783401696277168138', dbcon)}")