import asyncio
from discord.ext import commands
from core import checks
from core.models import PermissionLevel

class StaffStats(commands.Cog):
    """
    A plugin which saves staff IDs in the database for frontend stuff.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        # Use asyncio.create_task instead of bot.loop.create_task
        asyncio.create_task(self._update_stats())

    async def _update_stats(self):
        while True:
            # Fetch the category channel using the ID from config
            category = self.bot.get_channel(
                int(self.bot.config.get("main_category_id"))
            )

            staff_members = list()

            # Loop through guild members
            for member in self.bot.modmail_guild.members:
                # Ensure member has permission to read messages in the category
                if category and member.permissions_in(category).read_messages:
                    if not member.bot:
                        staff_members.append(str(member.id))

            # Update the database with the list of staff members
            await self.db.find_one_and_update(
                {"_id": "list"}, {"$set": {"staff": staff_members}}, upsert=True
            )

            # Sleep for 24 hours (86400 seconds)
            await asyncio.sleep(86400)

    @commands.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def syncstaff(self, ctx):
        """
        Manually sync the staff list
        """
        category = self.bot.get_channel(int(self.bot.config.get("main_category_id")))

        staff_members = list()

        for member in self.bot.modmail_guild.members:
            if category and member.permissions_in(category).read_messages:
                if not member.bot:
                    staff_members.append(str(member.id))

        # Update the database with the list of staff members
        await self.db.find_one_and_update(
            {"_id": "list"}, {"$set": {"staff": staff_members}}, upsert=True
        )

        await ctx.send("Staff members synced successfully.")
        return

# The setup function is now async in discord.py v2.x
async def setup(bot):
    await bot.add_cog(StaffStats(bot))
