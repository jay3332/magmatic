# pre-release test script to ensure everything works properly
# this is to be removed after 0.1.0

import discord
import magmatic
from discord.ext import commands


class TestBot(commands.Bot):
    async def setup_hook(self) -> None:
        self.node = await magmatic.start_node(bot=bot, password='youshallnotpass')

    async def on_ready(self) -> None:
        print(f'Logged in as {self.user}')


bot = TestBot(command_prefix='magmatic:', intents=discord.Intents.default())


@bot.command()
async def join(ctx: commands.Context) -> None:
    await ctx.author.voice.channel.connect(cls=magmatic.Player)  # type: ignore
    await ctx.send(f'joined: {ctx.voice_client}')


@bot.command()
async def leave(ctx: commands.Context) -> None:
    await ctx.voice_client.disconnect()  # type: ignore
    await ctx.send('disconnected')


bot.run('TOKEN')
