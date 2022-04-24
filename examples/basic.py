from typing import Annotated, Union  # If you're using 3.8 import Annotated from typing_extensions, not typing.

import discord
import magmatic
from discord.ext import commands


class MusicBot(commands.Bot):
    """A simple music bot that can play music from YouTube."""

    # This event triggers whenever a node successfully connects to Lavalink.
    # Note that this can be triggered more than just once.
    async def on_magmatic_node_ready(self, node: magmatic.Node) -> None:
        print(f'Node {node.identifier} has connected to Lavalink!')

    # It is recommended to set up your nodes here (or in cog_load inside a Cog).
    async def setup_hook(self) -> None:
        self.node = await magmatic.start_node(
            bot=self,
            host='127.0.0.1',  # The host domain of your Lavalink node. 127.0.0.1 is localhost.
            port=2333,  # The port your Lavalink node is listening on. Default port is 2333.
            password='youshallnotpass',  # The password configured in application.yml
        )

    async def close(self) -> None:
        await self.node.destroy()  # This also disconnects all players from their voice channels, so it doesn't look like our bot is "hanging" in the voice channel.
        await super().close()


bot = MusicBot(command_prefix='$', intents=discord.Intents(
    voice_states=True,  # Magmatic (and consequently Lavalink) requires this intent for it to function properly
    message_content=True,  # Obviously required if you're using ext.commands (if on API v9 this may not be necessary)
))


@bot.command(aliases=['connect'])
async def join(ctx):
    """Joins a voice channel."""
    channel = ctx.author.voice.channel
    if not channel:
        return await ctx.send('You are not in a voice channel.')

    # There are many ways to connect magmatic to a voice channel.
    # A very common way is by using the `cls` kwarg in `Connectable.connect`, which is what we'll do here:
    await channel.connect(cls=magmatic.Player)
    # There are type-checking defects to this though. Some type-checkers will complain that magmatic.Player is
    # not compatible with the `cls` kwarg (even though it is).
    #
    # For better type-checking support with the trade-off being a more non-standard way of connecting,
    # Player.connect (if an instance of Player already exists) or Node.connect_player can be used instead.

    await ctx.send(f'Successfully joined {channel.mention}.')


@bot.command(aliases=['disconnect'])
async def leave(ctx):
    """Disconnects from the voice channel."""
    if ctx.voice_client is None:
        return await ctx.send('Not connected.')

    await ctx.voice_client.destroy()  # Use disconnect if you want to keep the state of the Player. Here it really isn't necessary.


# We use typing.Annotated to give discord.py the YoutubeTrack converter but let the type-checker know that
# track is still an instance of a normal Track (or Playlist).
@bot.command()
async def play(ctx, *, track: Annotated[Union[magmatic.Track, magmatic.Playlist], magmatic.YoutubeTrack]):
    """Plays the track given from your search query."""
    if ctx.voice_client is None:
        await ctx.invoke(join)

    if isinstance(track, magmatic.Playlist):
        await ctx.voice_client.play(track.selected_track or track.first)
        return

    await ctx.voice_client.play(track)


bot.run('TOKEN')
