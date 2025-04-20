import discord
from discord.ext import commands

from core import checks
from core.models import PermissionLevel

class AutoRolePlugin(commands.Cog):
    """Auto assign 'unverified' role on join and remove it if member gets verified."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        config = await self.db.find_one({"_id": "config"})
        if not config or "unverified_role" not in config or "verified_role" not in config:
            return

        unverified_role = member.guild.get_role(config["unverified_role"])
        verified_role = member.guild.get_role(config["verified_role"])

        if not verified_role or not unverified_role:
            return

        if verified_role not in member.roles and unverified_role not in member.roles:
            try:
                await member.add_roles(unverified_role, reason="Auto-assigned unverified role on join")
            except discord.Forbidden:
                print(f"Missing permissions to add role to {member}")
            except Exception as e:
                print(f"Error assigning unverified role: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return  # no role change

        config = await self.db.find_one({"_id": "config"})
        if not config or "unverified_role" not in config or "verified_role" not in config:
            return

        unverified_role = after.guild.get_role(config["unverified_role"])
        verified_role = after.guild.get_role(config["verified_role"])

        if not verified_role or not unverified_role:
            return

        # If verified was added, remove unverified
        if verified_role in after.roles and unverified_role in after.roles:
            try:
                await after.remove_roles(unverified_role, reason="Member verified, removed unverified role")
            except discord.Forbidden:
                print(f"Missing permissions to remove role from {after}")
            except Exception as e:
                print(f"Error removing unverified role: {e}")

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def autorole(self, ctx):
        """Configure autorole roles."""
        await ctx.send_help(ctx.command)

    @autorole.command(name="set")
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def set_roles(self, ctx, unverified: discord.Role, verified: discord.Role):
        """Set the unverified and verified roles."""
        await self.db.find_one_and_update(
            {"_id": "config"},
            {"$set": {
                "unverified_role": unverified.id,
                "verified_role": verified.id
            }},
            upsert=True
        )
        await ctx.send(f"✅ Autorole system configured.\nUnverified: `{unverified.name}`\nVerified: `{verified.name}`")

async def setup(bot):
    await bot.add_cog(AutoRolePlugin(bot))
