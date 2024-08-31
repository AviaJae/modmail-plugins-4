import discord
import asyncio
from datetime import datetime
from discord.ext import commands

from core import checks
from core.models import PermissionLevel


class ReportUser(commands.Cog):
    """
    Report a user to the AirAsia Moderation Team.
    """

    def __init__(self, bot):
        self.bot: discord.Client = bot
        self.db = bot.plugin_db.get_partition(self)
        self.blacklist = []
        self.channel = None
        self.message = "Thanks for reporting, the AirAsia Moderation Team will look into it soon."
        self.current_case = 1
        asyncio.create_task(self._set_config())

    async def _set_config(self):
        config = await self.db.find_one({"_id": "config"})
        if config is None:
            return
        self.blacklist = config.get("blacklist", [])
        self.channel = config.get("channel", None)
        self.current_case = config.get("case", 1)
        self.message = config.get(
            "message", "Thanks for reporting, the AirAsia Moderation Team will look into it soon."
        )

    async def update(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "blacklist": self.blacklist,
                    "channel": self.channel,
                    "message": self.message,
                    "case": self.current_case,
                }
            },
            upsert=True,
        )

    @commands.group(invoke_without_command=True)
    async def ru(self, ctx: commands.Context):
        """
        Report User Staff Commands
        """
        await ctx.send_help(ctx.command)

    @ru.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def blacklist(self, ctx, member: discord.Member):
        """
        Blacklist or unblacklist a user
        """
        if member.id not in self.blacklist:
            self.blacklist.append(member.id)
            action = "Blacklisted"
        else:
            self.blacklist.remove(member.id)
            action = "Blacklist Removed"
        await self.update()

        await ctx.send(f"{action}!")

    @ru.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Set a reports channel
        """
        self.channel = str(channel.id)
        await self.update()
        await ctx.send("Channel for reports is set.")

    @ru.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def message(self, ctx, *, msg: str):
        """
        Customize the message that will be sent to users who report someone.
        """
        self.message = msg
        await self.update()
        await ctx.send("Custom message set!")

    @commands.command()
    async def report(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """
        Report a user
        """
        if ctx.author.id in self.blacklist:
            await ctx.message.delete()
            return

        if self.channel is None:
            await ctx.message.delete()
            await ctx.author.send("Reports channel for the guild has not been set.")
            return

        channel: discord.TextChannel = self.bot.get_channel(int(self.channel))
        if not channel:
            await ctx.message.delete()
            await ctx.author.send("The reports channel is invalid.")
            return

        embed = discord.Embed(
            color=discord.Colour.red(), timestamp=datetime.utcnow()
        )
        embed.set_author(
            name=f"{ctx.author.name}#{ctx.author.discriminator}",
            icon_url=ctx.author.avatar.url,
        )
        embed.title = "User Report"
        embed.add_field(
            name="Against",
            value=f"{member.name}#{member.discriminator}",
            inline=False,
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Case {self.current_case}")

        try:
            m: discord.Message = await channel.send(embed=embed)
            await ctx.author.send(self.message)
            await m.add_reaction("✅")
            await self.db.insert_one(
                {
                    "case": self.current_case,
                    "author": str(ctx.author.id),
                    "against": str(member.id),
                    "reason": reason,
                    "resolved": False,
                }
            )
            self.current_case += 1
            await self.update()
        except Exception as e:
            await ctx.author.send(f"An error occurred while reporting: {e}")

        await ctx.message.delete()

    @ru.command()
    @checks.has_permissions(PermissionLevel.MOD)
    async def info(self, ctx: commands.Context, casen: int):
        """
        Get information about a specific case
        """
        case = await self.db.find_one({"case": casen})

        if case is None:
            await ctx.send(f"Case `#{casen}` doesn't exist.")
            return

        user1: discord.User = await self.bot.fetch_user(int(case["author"]))
        user2: discord.User = await self.bot.fetch_user(int(case["against"]))

        embed = discord.Embed(color=discord.Colour.red())
        embed.add_field(
            name="Reported by", value=f"{user1.name}#{user1.discriminator}", inline=False
        )
        embed.add_field(
            name="Against", value=f"{user2.name}#{user2.discriminator}", inline=False
        )
        embed.add_field(name="Reason", value=case["reason"], inline=False)
        embed.add_field(name="Status", value=case["resolved"], inline=False)
        embed.title = "Report Log"

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        if str(payload.channel_id) != str(self.channel) or str(payload.emoji.name) != "✅":
            return

        channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
        msg: discord.Message = await channel.fetch_message(payload.message_id)

        if not msg.embeds or not msg.embeds[0].footer.text:
            return

        case_number_str = msg.embeds[0].footer.text.replace("Case ", "")
        if not case_number_str.isdigit():
            return

        case_number = int(case_number_str)
        case = await self.db.find_one({"case": case_number})

        if case is None or case.get("resolved", False):
            await channel.send(f"Case `#{case_number}` is already resolved.")
            return

        def check(message: discord.Message):
            return (
                payload.user_id == message.author.id
                and payload.channel_id == message.channel.id
            )

        await channel.send("Enter your response which will be sent to the reporter:")
        report_response = await self.bot.wait_for("message", check=check)
        user1 = await self.bot.fetch_user(int(case["author"]))
        await user1.send(f"**Response from AirAsia Moderation Team:**\n{report_response.content}")
        await channel.send("DM sent.")
        await self.db.find_one_and_update(
            {"case": case_number}, {"$set": {"resolved": True}}
        )


async def setup(bot):
    await bot.add_cog(ReportUser(bot))
