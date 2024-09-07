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
        Create, Edit, & Manage Tags
        """
        await ctx.send_help(ctx.command)

    @tags.command()
    async def add(self, ctx: commands.Context, name: str, *, content: str):
        """
        Create a new tag
        """
        if await self.find_db(name=name) is not None:
            await ctx.send(f"❌ | A tag with the name `{name}` already exists.")
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
            await ctx.send(f"✅ | Tag `{name}` has been successfully created!")

    @tags.command()
    async def edit(self, ctx: commands.Context, name: str, *, content: str):
        """
        Edit an existing tag

        Only the owner of the tag or a user with Manage Server permissions can use this command.
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f"❌ | The tag `{name}` does not exist.")
        else:
            if ctx.author.id == tag["author"] or ctx.author.guild_permissions.manage_guild:
                await self.db.find_one_and_update(
                    {"name": name},
                    {"$set": {"content": content, "updatedAt": datetime.utcnow()}},
                )
                await ctx.send(f"✅ | Tag `{name}` has been successfully updated.")
            else:
                await ctx.send("❌ | You do not have permission to edit this tag.")

    @tags.command()
    async def delete(self, ctx: commands.Context, name: str):
        """
        Delete a tag

        Only the owner of the tag or a user with Manage Server permissions can use this command.
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f"❌ | The tag `{name}` does not exist.")
        else:
            if ctx.author.id == tag["author"] or ctx.author.guild_permissions.manage_guild:
                await self.db.delete_one({"name": name})
                await ctx.send(f"✅ | Tag `{name}` has been successfully deleted.")
            else:
                await ctx.send("❌ | You do not have permission to delete this tag.")

    @tags.command()
    async def claim(self, ctx: commands.Context, name: str):
        """
        Claim ownership of a tag if the original owner has left the server
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f"❌ | The tag `{name}` does not exist.")
        else:
            member = ctx.guild.get_member(tag["author"])
            if member:
                await ctx.send(f"❌ | The owner of this tag, `{member}`, is still in the server.")
            else:
                await self.db.find_one_and_update(
                    {"name": name},
                    {"$set": {"author": ctx.author.id, "updatedAt": datetime.utcnow()}},
                )
                await ctx.send(f"✅ | You have claimed ownership of the tag `{name}`.")

    @tags.command()
    async def info(self, ctx: commands.Context, name: str):
        """
        Get detailed information about a tag
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f"❌ | The tag `{name}` does not exist.")
        else:
            user: discord.User = await self.bot.fetch_user(tag["author"])
            embed = discord.Embed(
                title=f"Information about `{name}`",
                color=discord.Color.green()
            )
            embed.add_field(name="Created By", value=f"{user}")
            embed.add_field(name="Created At", value=tag["createdAt"])
            embed.add_field(name="Last Modified", value=tag["updatedAt"], inline=False)
            embed.add_field(name="Uses", value=tag["uses"], inline=False)
            await ctx.send(embed=embed)

    @tags.command()
    async def list(self, ctx: commands.Context):
        """
        List all available tags
        """
        tags_cursor = self.db.find({})
        tags = await tags_cursor.to_list(length=100)

        if not tags:
            await ctx.send("❌ | No tags are available.")
        else:
            tag_list = ", ".join([tag["name"] for tag in tags])
            await ctx.send(f"📋 | Available tags: {tag_list}")

    @commands.command()
    async def tag(self, ctx: commands.Context, name: str):
        """
        Use a tag by name
        """
        tag = await self.find_db(name=name)
        if tag is None:
            await ctx.send(f"❌ | The tag `{name}` does not exist.")
        else:
            await ctx.send(tag["content"])
            await self.db.find_one_and_update(
                {"name": name}, {"$set": {"uses": tag["uses"] + 1}}
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content.startswith(self.bot.command_prefix):
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


async def setup(bot: commands.Bot):
    await bot.add_cog(TagsPlugin(bot))
