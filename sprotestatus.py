import os
from dotenv import load_dotenv
from mcstatus import JavaServer

load_dotenv()
RCONAUTH = os.getenv('RCON_AUTH')
RCONIP = str(os.getenv('RCON_IP'))
RCONPORT = int(os.getenv('RCON_PORT'))
MCPORT = int(os.getenv('MC_PORT'))

server = JavaServer(RCONIP,MCPORT)
query = server.query()
print(f"The server has the following players online: {', '.join(query.players.names)}, {query.Players.__annotations__}, {query.map}")