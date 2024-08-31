import asyncio
import os
import lavalink
import discord
import re
import math
from discord.ext import commands

url_rx = re.compile(r"https?:\/\/(?:www\.)?.+")

class MusicPlugin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.lavalink = {"host": "", "password": "", "port": 2333}
        asyncio.create_task(self.update())

    async def update(self):
        self.lavalink["host"] = os.getenv("ll_host")
        self.lavalink["port"] = int(os.getenv("ll_port", 2333))
        self.lavalink["password"] = os.getenv("ll_password")
        
        if not hasattr(self.bot, "lavalink"):
            self.bot.lavalink = lavalink.Client(self.bot.user.id)
            self.bot.lavalink.add_node(
                self.lavalink["host"],
                self.lavalink["port"],
                self.lavalink["password"],
                os.getenv("ll_region", "eu"),
                "default-node",
            )
            self.bot.add_listener(
                self.bot.lavalink.voice_update_handler, "on_socket_response"
            )

    @commands.command()
    async def join(self, ctx: commands.Context):
        """ Joins the voice channel of the user. """
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You need to be in a voice channel.")

        channel = ctx.author.voice.channel
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_connected:
            player.store("channel", ctx.channel.id)
            await player.connect(channel.id)
            await ctx.send("Joined the voice channel!")

    @commands.command(aliases=["p"])
    async def play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player:
            player = self.bot.lavalink.players.create(ctx.guild.id, endpoint=str(ctx.guild.region))

        query = query.strip("<>")

        if not url_rx.match(query):
            query = f"ytsearch:{query}"

        results = await player.node.get_tracks(query)

        if not results or not results["tracks"]:
            return await ctx.send("Nothing found!")

        embed = discord.Embed(color=discord.Color.blurple())

        if results["loadType"] == "PLAYLIST_LOADED":
            tracks = results["tracks"]
            for track in tracks:
                player.add(requester=ctx.author.id, track=track)
            embed.title = "Playlist Enqueued!"
            embed.description = f'{results["playlistInfo"]["name"]} - {len(tracks)} tracks'
        else:
            track = results["tracks"][0]
            embed.title = "Track Enqueued"
            embed.description = f'[{track["info"]["title"]}]({track["info"]["uri"]})'
            player.add(requester=ctx.author.id, track=track)

        await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()

    @commands.command()
    async def seek(self, ctx, seconds: int):
        """ Seeks to a given position in a track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing.")

        track_time = player.position + (seconds * 1000)
        await player.seek(track_time)

        await ctx.send(f"Moved track to **{lavalink.utils.format_time(track_time)}**")

    @commands.command(aliases=["forceskip"])
    async def skip(self, ctx):
        """ Skips the current track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing.")

        await player.skip()
        await ctx.send("⏭ | Skipped.")

    @commands.command()
    async def stop(self, ctx):
        """ Stops the player and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing.")

        player.queue.clear()
        await player.stop()
        await ctx.send("⏹ | Stopped.")

    @commands.command(aliases=["np", "n", "playing"])
    async def now(self, ctx):
        """ Shows some stats about the currently playing song. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.current:
            return await ctx.send("Nothing playing.")

        position = lavalink.utils.format_time(player.position)
        duration = "🔴 LIVE" if player.current.stream else lavalink.utils.format_time(player.current.duration)
        song = f"**[{player.current.title}]({player.current.uri})**\n({position}/{duration})"

        embed = discord.Embed(
            color=discord.Color.blurple(), title="Now Playing", description=song
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=["q"])
    async def queue(self, ctx, page: int = 1):
        """ Shows the player's queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Nothing queued.")

        items_per_page = 10
        pages = math.ceil(len(player.queue) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue_list = ""
        for index, track in enumerate(player.queue[start:end], start=start):
            queue_list += f"`{index + 1}.` [**{track.title}**]({track.uri})\n"

        embed = discord.Embed(
            color=discord.Color.blurple(),
            description=f"**{len(player.queue)} tracks**\n\n{queue_list}",
        )
        embed.set_footer(text=f"Viewing page {page}/{pages}")
        await ctx.send(embed=embed)

    @commands.command()
    async def pause(self, ctx):
        """ Pauses/Resumes the current track. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Not playing.")

        if player.paused:
            await player.set_pause(False)
            await ctx.send("⏯ | Resumed")
        else:
            await player.set_pause(True)
            await ctx.send("⏯ | Paused")

    @commands.command(aliases=["vol"])
    async def volume(self, ctx, volume: int = None):
        """ Changes the player's volume (0-1000). """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if volume is None:
            return await ctx.send(f"🔈 | {player.volume}%")

        if volume < 0 or volume > 1000:
            return await ctx.send("Volume must be between 0 and 1000.")

        await player.set_volume(volume)
        await ctx.send(f"🔈 | Set to {volume}%")

    @commands.command()
    async def shuffle(self, ctx):
        """ Shuffles the player's queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)
        if not player.is_playing:
            return await ctx.send("Nothing playing.")

        player.shuffle = not player.shuffle
        await ctx.send("🔀 | Shuffle " + ("enabled" if player.shuffle else "disabled"))

    @commands.command(aliases=["loop"])
    async def repeat(self, ctx):
        """ Repeats the current song until the command is invoked again. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send("Nothing playing.")

        player.repeat = not player.repeat
        await ctx.send("🔁 | Repeat " + ("enabled" if player.repeat else "disabled"))

    @commands.command()
    async def remove(self, ctx, index: int):
        """ Removes an item from the player's queue with the given index. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.queue:
            return await ctx.send("Nothing queued.")

        if index < 1 or index > len(player.queue):
            return await ctx.send(f"Index has to be between 1 and {len(player.queue)}")

        removed = player.queue.pop(index - 1)  # Account for 0-index.

        await ctx.send(f"Removed **{removed.title}** from the queue.")

    @commands.command()
    async def find(self, ctx, *, query):
        """ Lists the first 10 search results from a given query. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not query.startswith("ytsearch:") and not query.startswith("scsearch:"):
            query = "ytsearch:" + query

        results = await player.node.get_tracks(query)

        if not results or not results["tracks"]:
            return await ctx.send("Nothing found.")

        tracks = results["tracks"][:10]  # First 10 results

        o = ""
        for index, track in enumerate(tracks, start=1):
            track_title = track["info"]["title"]
            track_uri = track["info"]["uri"]
            o += f"`{index}.` [{track_title}]({track_uri})\n"

        embed = discord.Embed(color=discord.Color.blurple(), description=o)
        await ctx.send(embed=embed)

    @commands.command(aliases=["dc"])
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.players.get(ctx.guild.id)

        if not player.is_connected:
            return await ctx.send("Not connected.")

        if not ctx.author.voice or (
            player.is_connected
            and ctx.author.voice.channel.id != int(player.channel_id)
        ):
            return await ctx.send("You're not in my voicechannel!")

        player.queue.clear()
        await player.stop()
        await player.disconnect()
        await ctx.send("*⃣ | Disconnected.")

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voice channel. """
        player = self.bot.lavalink.players.get(ctx.guild.id) or self.bot.lavalink.players.create(ctx.guild.id, endpoint=str(ctx.guild.region))

        should_connect = ctx.command.name in ("play", "join")  # Commands that require joining voice

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError("You need to be in a voice channel.")

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError("Not connected.")

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                raise commands.CommandInvokeError("I need the `CONNECT` and `SPEAK` permissions.")

            await player.connect(ctx.author.voice.channel.id)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError("You need to be in my voice channel.")

async def setup(bot):
    bot.add_cog(MusicPlugin(bot))
