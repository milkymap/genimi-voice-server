

import click 
import asyncio 
from .settings.openai_settings import OpenAISettings

from .server.server import APIServer
from dotenv import load_dotenv

@click.command()
@click.option('--host', type=str, default='localhost')
@click.option('--port', type=int, default=8000)
def launch_server(host:str, port:int):
    openai_settings = OpenAISettings()  # read all env variables 
    async def _inner_loop():
        async with APIServer(host=host, port=port, openai_settings=openai_settings) as server:
            await server.listen() 
    asyncio.run(main=_inner_loop())


if __name__ == '__main__':
    load_dotenv()
    launch_server()