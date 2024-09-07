import discord
from datetime import datetime
from discord.ext import commands

from core import checks
from core.models import PermissionLevel

class TagsPlugin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.db = bot.plugin_db.get_partition(self)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.REGULAR)
    async def tags(self, ctx: commands.Context):
        """
        Create, Edit & Manage Tags
        """
        await ctx.send_help(ctx.command)

    @tags.command()
    async def add(self, ctx: commands.Context, name: str, *, content: str):
        """
        Make a new tag
        """
        if await self.find_db(name=name) is not None:
            await ctx.send(f":x: | Tag with name `{name}` already exists!")
            return
        else:
            await self.db.insert_one(
                {
                    "name": name,
                    "content": content,
                    "createdAt": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                    "author": ctx.author.id,
                    "uses": 0,
                }
            )
            await ctx.send(f":white_check_mark: | Tag with name `{name}` has been successfully created!")

    @tags.command()
    async def edit(self, ctx: commands.Context, name: str, *, content: str):
        """
        Edit an existing tag

        Only the owner of the tag or a user with Manage Server permissions can use this command
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f":x: | Tag with name `{name}` doesn't exist")
        else:
            if ctx.author.id == tag["author"] or ctx.author.guild_permissions.manage_guild:
                await self.db.find_one_and_update(
                    {"name": name},
                    {"$set": {"content": content, "updatedAt": datetime.utcnow()}},
                )
                await ctx.send(f":white_check_mark: | Tag `{name}` is updated successfully!")
            else:
                await ctx.send("You don't have enough permissions to edit that tag.")

    @tags.command()
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a tag

        Only the owner of the tag or a user with Manage Server permissions can use this command
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f":x: | Tag `{name}` not found in the database.")
        else:
            if ctx.author.id == tag["author"] or ctx.author.guild_permissions.manage_guild:
                await self.db.delete_one({"name": name})
                await ctx.send(f":white_check_mark: | Tag `{name}` has been deleted successfully!")
            else:
                await ctx.send("You don't have enough permissions to delete that tag.")

    @tags.command()
    async def claim(self, ctx: commands.Context, name: str):
        """
        Claim a tag if the owner has left the server
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f":x: | Tag `{name}` not found.")
        else:
            member = ctx.guild.get_member(tag["author"])
            if member:
                await ctx.send(f":x: | The owner of the tag is still in the server: `{member}`")
            else:
                await self.db.find_one_and_update(
                    {"name": name},
                    {"$set": {"author": ctx.author.id, "updatedAt": datetime.utcnow()}},
                )
                await ctx.send(f":white_check_mark: | Tag `{name}` is now owned by `{ctx.author}`")

    @tags.command()
    async def info(self, ctx: commands.Context, name: str):
        """
        Get info on a tag
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f":x: | Tag `{name}` not found.")
        else:
            user: discord.User = await self.bot.fetch_user(tag["author"])
            embed = discord.Embed(
                title=f"{name}'s Info",
                color=discord.Color.green()
            )
            embed.add_field(name="Created By", value=f"{user}")
            embed.add_field(name="Created At", value=tag["createdAt"])
            embed.add_field(name="Last Modified At", value=tag["updatedAt"], inline=False)
            embed.add_field(name="Uses", value=tag["uses"], inline=False)
            await ctx.send(embed=embed)

    @commands.command()
    async def tag(self, ctx: commands.Context, name: str):
        """
        Use a tag
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f":x: | Tag {name} not found.")
        else:
            await ctx.send(tag["content"])
            await self.db.find_one_and_update(
                {"name": name}, {"$set": {"uses": tag["uses"] + 1}}
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.content.startswith(self.bot.command_prefix):
            return

        content = message.content[len(self.bot.command_prefix):].split(" ", 1)
        tag = await self.db.find_one({"name": content[0]})

        if tag:
            await message.channel.send(tag["content"])
            await self.db.find_one_and_update(
                {"name": content[0]}, {"$set": {"uses": tag["uses"] + 1}}
            )

    async def find_db(self, name: str):
        return await self.db.find_one({"name": name})


def setup(bot: commands.Bot):
    bot.add_cog(TagsPlugin(bot))
