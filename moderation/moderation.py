import datetime
import logging

import discord
import typing
from discord.ext import commands

from core import checks
from core.models import PermissionLevel

logger = logging.getLogger("Modmail")

class ModerationPlugin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        logger.debug("ModerationPlugin initialized")

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def moderation(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    @moderation.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await self.db.find_one_and_update(
            {"_id": "config"}, {"$set": {"channel": channel.id}}, upsert=True
        )
        await ctx.send("Log channel updated successfully!")

    async def get_log_channel(self, ctx):
        config = await self.db.find_one({"_id": "config"})
        if not config:
            await ctx.send("There's no configured log channel.")
            return None
        channel = ctx.guild.get_channel(int(config["channel"]))
        if not channel:
            await ctx.send("Configured log channel is invalid.")
            return None
        return channel

    @commands.command(aliases=["banhammer"])
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def ban(self, ctx: commands.Context, members: commands.Greedy[discord.Member], days: typing.Optional[int] = 0, *, reason: str = None):
        if not members:
            return await ctx.send("You need to mention at least one member to ban.")
        channel = await self.get_log_channel(ctx)
        if not channel:
            return
        for member in members:
            try:
                await member.ban(delete_message_days=days, reason=reason)
                embed = discord.Embed(color=discord.Color.red(), title=f"🔨 {member} was banned!", timestamp=datetime.datetime.utcnow())
                embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
                await ctx.send(f"🚫 | {member} has been banned!")
                await channel.send(embed=embed)
            except discord.Forbidden:
                await ctx.send("I don't have permission to ban members.")
            except Exception as e:
                logger.error(f"Error banning user: {e}")
                await ctx.send("An error occurred while banning the user.")

    @commands.command(aliases=["getout"])
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None):
        if not members:
            return await ctx.send("You need to mention at least one member to kick.")
        channel = await self.get_log_channel(ctx)
        if not channel:
            return
        for member in members:
            try:
                await member.kick(reason=reason)
                embed = discord.Embed(color=discord.Color.red(), title=f"🦶 {member} was kicked!", timestamp=datetime.datetime.utcnow())
                embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
                await ctx.send(f"🦶 | {member} has been kicked!")
                await channel.send(embed=embed)
            except discord.Forbidden:
                await ctx.send("I don't have permission to kick members.")
            except Exception as e:
                logger.error(f"Error kicking user: {e}")
                await ctx.send("An error occurred while kicking the user.")

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        if member.bot:
            return await ctx.send("Bots cannot be warned.")
        channel = await self.get_log_channel(ctx)
        if not channel:
            return
        warns_config = await self.db.find_one({"_id": "warns"}) or {}
        user_warns = warns_config.get(str(member.id), [])
        user_warns.append({"reason": reason, "mod": ctx.author.id})
        await self.db.find_one_and_update({"_id": "warns"}, {"$set": {str(member.id): user_warns}}, upsert=True)
        await ctx.send(f"Successfully warned **{member}**\n`{reason}`")
        await channel.send(embed=await self.generate_warn_embed(str(member.id), str(ctx.author.id), len(user_warns), reason))

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def unwarn(self, ctx, member: discord.Member, index: int):
        warns_config = await self.db.find_one({"_id": "warns"}) or {}
        warns = warns_config.get(str(member.id), [])
        if not warns:
            return await ctx.send(f"{member} has no warnings.")
        if index < 1 or index > len(warns):
            return await ctx.send(f"Invalid warning index. {member} has {len(warns)} warnings.")
        removed = warns.pop(index - 1)
        await self.db.find_one_and_update({"_id": "warns"}, {"$set": {str(member.id): warns}}, upsert=True)
        await ctx.send(f"Removed warning {index} from **{member}**: `{removed['reason']}`")

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def pardon(self, ctx, member: discord.Member, *, reason: str):
        if member.bot:
            return await ctx.send("Bots cannot be pardoned.")
        channel = await self.get_log_channel(ctx)
        if not channel:
            return
        warns_config = await self.db.find_one({"_id": "warns"}) or {}
        if str(member.id) not in warns_config:
            return await ctx.send(f"{member} doesn't have any warnings.")
        await self.db.find_one_and_update({"_id": "warns"}, {"$set": {str(member.id): []}})
        await ctx.send(f"Successfully pardoned **{member}**\n`{reason}`")
        embed = discord.Embed(color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
        embed.set_author(name=f"Pardon | {member}", icon_url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member}")
        embed.add_field(name="Moderator", value=f"<@{ctx.author.id}> - `{ctx.author}`")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Total Warnings", value="0")
        await channel.send(embed=embed)

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def timeout(self, ctx, member: discord.Member, duration: str, *, reason: str = None):
        if not member.guild_permissions.moderate_members:
            try:
                seconds = self.convert_to_seconds(duration)
                until = discord.utils.utcnow() + datetime.timedelta(seconds=seconds)
                await member.timeout(until, reason=reason)
                await ctx.send(f"🕒 | Timed out **{member}** for `{duration}`")
                channel = await self.get_log_channel(ctx)
                if channel:
                    embed = discord.Embed(color=discord.Color.orange(), title=f"🕒 Timeout | {member}", timestamp=datetime.datetime.utcnow())
                    embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                    embed.add_field(name="Duration", value=duration, inline=False)
                    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
                    await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Timeout error: {e}")
                await ctx.send("An error occurred while timing out the user.")

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def untimeout(self, ctx, member: discord.Member):
        try:
            await member.timeout(None)
            await ctx.send(f"⏱️ | Timeout removed from **{member}**")
            channel = await self.get_log_channel(ctx)
            if channel:
                embed = discord.Embed(color=discord.Color.green(), title=f"⏱️ Untimeout | {member}", timestamp=datetime.datetime.utcnow())
                embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Untimeout error: {e}")
            await ctx.send("An error occurred while removing the timeout.")

    def convert_to_seconds(self, duration: str) -> int:
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        try:
            return int(duration[:-1]) * units[duration[-1].lower()]
        except (ValueError, KeyError):
            raise commands.BadArgument("Invalid duration format. Use `10m`, `1h`, `2d`, etc.")

    async def generate_warn_embed(self, member_id, mod_id, warning_count, reason):
        member = await self.bot.fetch_user(int(member_id))
        mod = await self.bot.fetch_user(int(mod_id))
        embed = discord.Embed(color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
        embed.set_author(name=f"Warn | {member}", icon_url=member.display_avatar.url)
        embed.add_field(name="User", value=f"{member}")
        embed.add_field(name="Moderator", value=f"<@{mod_id}> - ({mod})")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Total Warnings", value=str(warning_count))
        return embed

async def setup(bot):
    bot.add_cog(ModerationPlugin(bot))
    logger.debug("ModerationPlugin setup complete")
