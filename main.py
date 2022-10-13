from aiomcrcon import Client
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
RCONAUTH = os.getenv('RCON_AUTH')
RCONIP = str(os.getenv('RCON_IP'))
RCONPORT = int(os.getenv('RCON_PORT'))


async def main():
    password = RCONAUTH
    command = input("Command? ")

    RCONclient = Client(RCONIP, RCONPORT, password)
    await RCONclient.connect()

    RCONresponse = await RCONclient.send_cmd(command)
    print(RCONresponse)

    await RCONclient.close()


if __name__ == "__main__":
    asyncio.run(main())
