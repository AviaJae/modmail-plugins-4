import discord
from discord.ext import commands

from core import checks
from core.models import PermissionLevel

class AutoRolePlugin(commands.Cog):
    """Assign 'unverified' role to new members and manage verification."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await self.db.find_one({"_id": "config"})
        if not config or "role_id" not in config:
            return  # Role not set

        role = member.guild.get_role(config["role_id"])
        if role:
            try:
                await member.add_roles(role, reason="Assigned autorole on join")
            except discord.Forbidden:
                print(f"Missing permissions to add role to {member}")
            except Exception as e:
                print(f"Error assigning autorole: {e}")

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def autorole(self, ctx):
        """Configure autorole settings."""
        await ctx.send_help(ctx.command)

    @autorole.command(name="set")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def setrole(self, ctx, role: discord.Role):
        """Set the role to give to new members (e.g., unverified)."""
        await self.db.find_one_and_update(
            {"_id": "config"}, {"$set": {"role_id": role.id}}, upsert=True
        )
        await ctx.send(f"✅ Autorole set to `{role.name}`.")

    @commands.command()
    @checks.has_permissions(PermissionLevel.MODERATOR)
    async def verify(self, ctx, member: discord.Member):
        """Verify a user by removing the unverified role."""
        config = await self.db.find_one({"_id": "config"})
        if not config or "role_id" not in config:
            return await ctx.send("❌ Autorole not configured.")

        role = member.guild.get_role(config["role_id"])
        if not role:
            return await ctx.send("❌ The configured role no longer exists.")

        if role in member.roles:
            try:
                await member.remove_roles(role, reason="User verified")
                await ctx.send(f"✅ {member.mention} has been verified.")
            except discord.Forbidden:
                await ctx.send("⚠ I don't have permission to remove that role.")
        else:
            await ctx.send(f"{member.mention} doesn't have the unverified role.")

async def setup(bot):
    await bot.add_cog(AutoRolePlugin(bot))
