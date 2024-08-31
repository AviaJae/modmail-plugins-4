import discord
import typing
import re
from discord.ext import commands

from core import checks
from core.models import PermissionLevel


class AnnouncementPlugin(commands.Cog):
    """
    Easily create plain text or embedded announcements.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.group(aliases=["a"], invoke_without_command=True)
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.REGULAR)
    async def announcement(self, ctx: commands.Context):
        """
        Make Announcements Easily.
        """
        await ctx.send_help(ctx.command)

    @announcement.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def start(
        self,
        ctx: commands.Context,
        role: typing.Optional[typing.Union[discord.Role, str]] = None,
    ):
        """
        Start an interactive session to create an announcement.
        Add the role in the command if you want to enable mentions.

        **Example:**
        __Announcement with role mention:__
        {prefix}announcement start everyone

        __Announcement without role mention__
        {prefix}announcement start
        """

        def check(msg: discord.Message):
            return ctx.author == msg.author and ctx.channel == msg.channel

        def title_check(msg: discord.Message):
            return (
                ctx.author == msg.author
                and ctx.channel == msg.channel
                and len(msg.content) < 256
            )

        def description_check(msg: discord.Message):
            return (
                ctx.author == msg.author
                and ctx.channel == msg.channel
                and len(msg.content) < 2048
            )

        def footer_check(msg: discord.Message):
            return (
                ctx.author == msg.author
                and ctx.channel == msg.channel
                and len(msg.content) < 2048
            )

        def cancel_check(msg: discord.Message):
            return msg.content.lower() in ["cancel", f"{ctx.prefix}cancel"]

        if isinstance(role, discord.Role):
            role_mention = f"<@&{role.id}>"
            await role.edit(mentionable=True)
        elif isinstance(role, str):
            if role.lower() in ["here", "@here"]:
                role_mention = "@here"
            elif role.lower() in ["everyone", "@everyone"]:
                role_mention = "@everyone"
            else:
                role_mention = ""
        else:
            role_mention = ""

        await ctx.send("Starting an interactive process to create an announcement.")

        await ctx.send(
            embed=await self.generate_embed("Do you want it to be an embed? `[y/n]`")
        )

        embed_res: discord.Message = await self.bot.wait_for("message", check=check)
        if cancel_check(embed_res):
            await ctx.send("Cancelled!")
            return

        if embed_res.content.lower() == "n":
            await ctx.send(
                embed=await self.generate_embed(
                    "Okay, let's do a no-embed announcement."
                    "\nWhat's the announcement?"
                )
            )
            announcement = await self.bot.wait_for("message", check=check)
            if cancel_check(announcement):
                await ctx.send("Cancelled!")
                return

            await ctx.send(
                embed=await self.generate_embed(
                    "To which channel should I send the announcement?"
                )
            )
            channel_msg = await self.bot.wait_for("message", check=check)
            if cancel_check(channel_msg):
                await ctx.send("Cancelled!")
                return

            if not channel_msg.channel_mentions:
                await ctx.send("Cancelled as no channel was provided.")
                return

            channel = channel_msg.channel_mentions[0]
            await channel.send(f"{role_mention}\n{announcement.content}")

        elif embed_res.content.lower() == "y":
            embed = discord.Embed()

            await ctx.send(
                embed=await self.generate_embed(
                    "Should the embed have a title? `[y/n]`"
                )
            )
            t_res = await self.bot.wait_for("message", check=check)
            if cancel_check(t_res):
                await ctx.send("Cancelled!")
                return

            if t_res.content.lower() == "y":
                await ctx.send(
                    embed=await self.generate_embed(
                        "What should the title of the embed be?"
                        "\n**Must not exceed 256 characters**"
                    )
                )
                title_msg = await self.bot.wait_for("message", check=title_check)
                embed.title = title_msg.content

            await ctx.send(
                embed=await self.generate_embed(
                    "Should the embed have a description? `[y/n]`"
                )
            )
            d_res = await self.bot.wait_for("message", check=check)
            if cancel_check(d_res):
                await ctx.send("Cancelled!")
                return

            if d_res.content.lower() == "y":
                await ctx.send(
                    embed=await self.generate_embed(
                        "What do you want as the description for the embed?"
                        "\n**Must not exceed 2048 characters**"
                    )
                )
                description_msg = await self.bot.wait_for(
                    "message", check=description_check
                )
                embed.description = description_msg.content

            await ctx.send(
                embed=await self.generate_embed(
                    "Should the embed have a thumbnail? `[y/n]`"
                )
            )
            th_res = await self.bot.wait_for("message", check=check)
            if cancel_check(th_res):
                await ctx.send("Cancelled!")
                return

            if th_res.content.lower() == "y":
                await ctx.send(
                    embed=await self.generate_embed(
                        "What's the thumbnail of the embed? Enter a valid URL."
                    )
                )
                thumbnail_msg = await self.bot.wait_for("message", check=check)
                embed.set_thumbnail(url=thumbnail_msg.content)

            await ctx.send(
                embed=await self.generate_embed("Should the embed have an image? `[y/n]`")
            )
            i_res = await self.bot.wait_for("message", check=check)
            if cancel_check(i_res):
                await ctx.send("Cancelled!")
                return

            if i_res.content.lower() == "y":
                await ctx.send(
                    embed=await self.generate_embed(
                        "What's the image of the embed? Enter a valid URL."
                    )
                )
                image_msg = await self.bot.wait_for("message", check=check)
                embed.set_image(url=image_msg.content)

            await ctx.send(
                embed=await self.generate_embed("Will the embed have a footer? `[y/n]`")
            )
            f_res = await self.bot.wait_for("message", check=check)
            if cancel_check(f_res):
                await ctx.send("Cancelled!")
                return

            if f_res.content.lower() == "y":
                await ctx.send(
                    embed=await self.generate_embed(
                        "What do you want the footer of the embed to be?"
                        "\n**Must not exceed 2048 characters**"
                    )
                )
                footer_msg = await self.bot.wait_for("message", check=footer_check)
                embed.set_footer(text=footer_msg.content)

            await ctx.send(
                embed=await self.generate_embed("Do you want it to have a color? `[y/n]`")
            )
            c_res = await self.bot.wait_for("message", check=check)
            if cancel_check(c_res):
                await ctx.send("Cancelled!")
                return

            if c_res.content.lower() == "y":
                await ctx.send(
                    embed=await self.generate_embed(
                        "What color should the embed have? Please provide a valid hex color."
                    )
                )
                color_msg = await self.bot.wait_for("message", check=check)
                if cancel_check(color_msg):
                    await ctx.send("Cancelled!")
                    return

                match = re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color_msg.content)
                if match:
                    embed.color = discord.Color(int(color_msg.content[1:], 16))
                else:
                    await ctx.send(
                        "Failed! Not a valid hex color, get yours from "
                        "https://www.google.com/search?q=color+picker"
                    )
                    return

            await ctx.send(
                embed=await self.generate_embed(
                    "In which channel should I send the announcement?"
                )
            )
            channel_msg = await self.bot.wait_for("message", check=check)
            if cancel_check(channel_msg):
                await ctx.send("Cancelled!")
                return

            if not channel_msg.channel_mentions:
                await ctx.send("Cancelled as no channel was provided.")
                return

            schan = channel_msg.channel_mentions[0]
            await ctx.send(
                "Here is how the embed looks like: Send it? `[y/n]`", embed=embed
            )
            s_res = await self.bot.wait_for("message", check=check)
            if cancel_check(s_res) or s_res.content.lower() == "n":
                await ctx.send("Cancelled!")
                return

            await schan.send(f"{role_mention}", embed=embed)

        if isinstance(role, discord.Role):
            await role.edit(mentionable=False)

    @announcement.command(aliases=["native", "n", "q"])
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def quick(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        role: typing.Optional[typing.Union[discord.Role, str]],
        *,
        msg: str,
    ):
        """
        An old way of making announcements.

        **Usage:**
        {prefix}announcement quick #channel <OPTIONAL role> message
        """
        if isinstance(role, discord.Role):
            await role.edit(mentionable=True)
            role_mention = f"<@&{role.id}>"
        elif isinstance(role, str):
            if role.lower() in ["here", "@here"]:
                role_mention = "@here"
            elif role.lower() in ["everyone", "@everyone"]:
                role_mention = "@everyone"
            else:
                msg = f"{role} {msg}"
                role_mention = ""
        else:
            role_mention = ""

        await channel.send(f"{role_mention}\n{msg}")
        await ctx.send("Done!")

        if isinstance(role, discord.Role):
            await role.edit(mentionable=False)

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.bot.session.post(
            "https://counter.modmail-plugins.piyush.codes/api/instances/announcement",
            json={"id": self.bot.user.id},
        ):
            print("Posted to Plugin API")

    @staticmethod
    async def generate_embed(description: str):
        embed = discord.Embed(color=discord.Color.blurple(), description=description)
        return embed


def setup(bot):
    await bot.add_cog(AnnouncementPlugin(bot))
