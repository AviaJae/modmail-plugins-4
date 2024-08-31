import datetime
import logging

import discord
import typing
from discord.ext import commands

from core import checks
from core.models import PermissionLevel

logger = logging.getLogger("Modmail")

class ModerationPlugin(commands.Cog):
    """
    Moderate your server using modmail.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        logger.debug("ModerationPlugin initialized")

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def moderation(self, ctx: commands.Context):
        """
        Settings and stuff.
        """
        await ctx.send_help(ctx.command)

    @moderation.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Set the log channel for moderation actions.
        """
        await self.db.find_one_and_update(
            {"_id": "config"}, {"$set": {"channel": channel.id}}, upsert=True
        )
        await ctx.send("Log channel updated successfully!")

    @commands.command(aliases=["banhammer"])
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def ban(
        self,
        ctx: commands.Context,
        members: commands.Greedy[discord.Member],
        days: typing.Optional[int] = 0,
        *,
        reason: str = None,
    ):
        """Ban one or more users.
        Usage:
        {prefix}ban @member 10 Advertising their own products
        {prefix}ban @member1 @member2 @member3 Spamming
        """
        config = await self.db.find_one({"_id": "config"})

        if not config:
            return await ctx.send("There's no configured log channel.")
        
        channel = ctx.guild.get_channel(int(config["channel"]))

        if not channel:
            return await ctx.send("Configured log channel is invalid.")

        for member in members:
            try:
                await member.ban(
                    delete_message_days=days, reason=reason
                )

                embed = discord.Embed(
                    color=discord.Color.red(),
                    title=f"{member} was banned!",
                    timestamp=datetime.datetime.utcnow(),
                )

                embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)

                await ctx.send(f"🚫 | {member} has been banned!")
                await channel.send(embed=embed)

            except discord.Forbidden:
                await ctx.send("I don't have permission to ban members.")
            except Exception as e:
                logger.error(f"Error banning user: {e}")
                await ctx.send("An error occurred while banning the user.")

    @commands.command(aliases=["getout"])
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def kick(
        self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None
    ):
        """Kick one or more users.
        Usage:
        {prefix}kick @member Being rude
        {prefix}kick @member1 @member2 @member3 Advertising
        """
        config = await self.db.find_one({"_id": "config"})

        if not config:
            return await ctx.send("There's no configured log channel.")
        
        channel = ctx.guild.get_channel(int(config["channel"]))

        if not channel:
            return await ctx.send("Configured log channel is invalid.")

        for member in members:
            try:
                await member.kick(reason=reason)
                
                embed = discord.Embed(
                    color=discord.Color.red(),
                    title=f"{member} was kicked!",
                    timestamp=datetime.datetime.utcnow(),
                )

                embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)

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
        """Warn a member.
        Usage:
        {prefix}warn @member Spoilers
        """
        if member.bot:
            return await ctx.send("Bots cannot be warned.")

        channel_config = await self.db.find_one({"_id": "config"})

        if not channel_config:
            return await ctx.send("There's no configured log channel.")
        
        channel = ctx.guild.get_channel(int(channel_config["channel"]))

        if not channel:
            return await ctx.send("Configured log channel is invalid.")

        warns_config = await self.db.find_one({"_id": "warns"}) or {}

        user_warns = warns_config.get(str(member.id), [])
        user_warns.append({"reason": reason, "mod": ctx.author.id})

        await self.db.find_one_and_update(
            {"_id": "warns"}, {"$set": {str(member.id): user_warns}}, upsert=True
        )

        await ctx.send(f"Successfully warned **{member}**\n`{reason}`")

        await channel.send(
            embed=await self.generate_warn_embed(
                str(member.id), str(ctx.author.id), len(user_warns), reason
            )
        )

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def pardon(self, ctx, member: discord.Member, *, reason: str):
        """Remove all warnings of a member.
        Usage:
        {prefix}pardon @member Nice guy
        """
        if member.bot:
            return await ctx.send("Bots cannot be pardoned.")

        channel_config = await self.db.find_one({"_id": "config"})

        if not channel_config:
            return await ctx.send("There's no configured log channel.")
        
        channel = ctx.guild.get_channel(int(channel_config["channel"]))

        if not channel:
            return await ctx.send("Configured log channel is invalid.")

        warns_config = await self.db.find_one({"_id": "warns"}) or {}

        if str(member.id) not in warns_config:
            return await ctx.send(f"{member} doesn't have any warnings.")

        await self.db.find_one_and_update(
            {"_id": "warns"}, {"$set": {str(member.id): []}}
        )

        await ctx.send(f"Successfully pardoned **{member}**\n`{reason}`")

        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(
            name=f"Pardon | {member}",
            icon_url=member.avatar_url,
        )
        embed.add_field(name="User", value=f"{member}")
        embed.add_field(name="Moderator", value=f"<@{ctx.author.id}> - `{ctx.author}`")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Total Warnings", value="0")

        await channel.send(embed=embed)

    async def generate_warn_embed(self, member_id, mod_id, warning_count, reason):
        member = await self.bot.fetch_user(int(member_id))
        mod = await self.bot.fetch_user(int(mod_id))

        embed = discord.Embed(color=discord.Color.red())
        embed.set_author(
            name=f"Warn | {member}",
            icon_url=member.avatar_url,
        )
        embed.add_field(name="User", value=f"{member}")
        embed.add_field(name="Moderator", value=f"<@{mod_id}> - ({mod})")
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Total Warnings", value=str(warning_count))

        return embed

def setup(bot):
    bot.add_cog(ModerationPlugin(bot))
    logger.debug("ModerationPlugin setup complete")
