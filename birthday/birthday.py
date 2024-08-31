import asyncio
import datetime
import discord
import logging
import pytz

from difflib import get_close_matches
from discord.ext import commands
from pytz import timezone

from core import checks
from core.models import PermissionLevel

logger = logging.getLogger("Modmail")


class BirthdayPlugin(commands.Cog):
    """
    A birthday plugin.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.plugin_db.get_partition(self)
        self.birthdays = dict()
        self.roles = dict()
        self.channels = dict()
        self.timezone = "America/Chicago"
        self.messages = dict()
        self.enabled = True
        self.booted = True
        self.bot.loop.create_task(self._set_db())

    async def _set_db(self):
        birthdays = await self.db.find_one({"_id": "birthdays"})
        config = await self.db.find_one({"_id": "config"})

        if birthdays is None:
            await self.db.find_one_and_update(
                {"_id": "birthdays"}, {"$set": {"birthdays": dict()}}, upsert=True
            )
            birthdays = await self.db.find_one({"_id": "birthdays"})

        if config is None:
            await self.db.find_one_and_update(
                {"_id": "config"},
                {
                    "$set": {
                        "roles": dict(),
                        "channels": dict(),
                        "enabled": True,
                        "timezone": "America/Chicago",
                        "messages": dict(),
                    }
                },
                upsert=True,
            )
            config = await self.db.find_one({"_id": "config"})

        self.birthdays = birthdays.get("birthdays", dict())
        self.roles = config.get("roles", dict())
        self.channels = config.get("channels", dict())
        self.enabled = config.get("enabled", True)
        self.timezone = config.get("timezone", "America/Chicago")
        self.messages = config.get("messages", dict())
        self.bot.loop.create_task(self._handle_birthdays())

    async def _update_birthdays(self):
        await self.db.find_one_and_update(
            {"_id": "birthdays"}, {"$set": {"birthdays": self.birthdays}}, upsert=True
        )

    async def _update_config(self):
        await self.db.find_one_and_update(
            {"_id": "config"},
            {
                "$set": {
                    "roles": self.roles,
                    "channels": self.channels,
                    "enabled": self.enabled,
                    "timezone": self.timezone,
                    "messages": self.messages,
                }
            },
            upsert=True,
        )

    async def _handle_birthdays(self):
        while True:
            if not self.enabled:
                return

            custom_timezone = timezone(self.timezone)
            now = datetime.datetime.now(custom_timezone)

            if self.booted:
                sleep_time = (
                    now.replace(hour=0, minute=15, second=0, microsecond=0) - now
                ).total_seconds()
                self.booted = False
                await asyncio.sleep(sleep_time)
                continue

            today = now.strftime("%d/%m/%Y").split("/")
            for user, obj in self.birthdays.items():
                if str(obj["month"]) != today[1] or str(obj["day"]) != today[0]:
                    continue
                guild = self.bot.get_guild(int(obj["guild"]))
                if guild is None:
                    continue
                member = guild.get_member(int(user))
                if member is None:
                    continue

                if self.roles[obj["guild"]]:
                    role = guild.get_role(int(self.roles[obj["guild"]]))
                    if role:
                        await member.add_roles(role, reason="Birthday Boi")

                if self.messages[obj["guild"]] and self.channels[obj["guild"]]:
                    channel = guild.get_channel(int(self.channels[obj["guild"]]))
                    if channel is None:
                        continue
                    age = int(today[2]) - obj["year"]
                    await channel.send(
                        self.messages[obj["guild"]]
                        .replace("{user.mention}", member.mention)
                        .replace("{user}", str(member))
                        .replace("{age}", str(age))
                    )

            # Calculate time until next midnight
            now = datetime.datetime.now(custom_timezone)
            next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            sleep_time = (next_midnight - now).total_seconds()
            await asyncio.sleep(sleep_time)

    @commands.group(invoke_without_command=True)
    async def birthday(self, ctx: commands.Context):
        """
        Birthday stuff.
        """
        await ctx.send_help(ctx.command)

    @birthday.command()
    async def set(self, ctx: commands.Context, date: str):
        """
        Set your birthdate.

        **Format:**
        DD/MM/YYYY

        **Example:**
        {p}birthday set 26/12/2002
        """
        try:
            birthday = date.split("/")
            if int(birthday[1]) > 12:  # Fix: Month should not be greater than 12
                await ctx.send(":x: | Invalid month provided.")
                return

            birthday_obj = {
                "day": int(birthday[0]),
                "month": int(birthday[1]),
                "year": int(birthday[2]),
                "guild": str(ctx.guild.id),
            }

            self.birthdays[str(ctx.author.id)] = birthday_obj
            await self._update_birthdays()
            await ctx.send(f"Done! Your birthday was set to {date}")
        except (KeyError, ValueError) as e:
            logger.error(f"Error setting birthday: {e}")
            await ctx.send("Please check the format of the date")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            await ctx.send(f":x: | An error occurred\n```{e}```")

    @birthday.command()
    async def clear(self, ctx: commands.Context):
        """
        Clear your birthday from the database.
        """
        self.birthdays.pop(str(ctx.author.id), None)  # Handle case if key doesn't exist
        await self._update_birthdays()
        await ctx.send("Done!")

    @birthday.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """
        Configure a channel for sending birthday announcements
        """
        self.channels[str(ctx.guild.id)] = str(channel.id)
        await self._update_config()
        await ctx.send("Done!")

    @birthday.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def role(self, ctx: commands.Context, role: discord.Role):
        """
        Configure a role which will be added to the birthday boizzzz
        """
        self.roles[str(ctx.guild.id)] = str(role.id)
        await self._update_config()
        await ctx.send("Done!")

    @birthday.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def message(self, ctx: commands.Context, *, msg: str):
        """
        Set a message to announce when wishing someone's birthday

        **Formatting:**
        • {user} - Name of the birthday boi
        • {user.mention} - Mention the birthday boi
        • {age} - Age of the birthday boiiii
        """
        self.messages[str(ctx.guild.id)] = msg
        await self._update_config()
        await ctx.send("Done!")

    @birthday.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def toggle(self, ctx: commands.Context):
        """
        Enable / Disable this plugin
        """
        self.enabled = not self.enabled
        await self._update_config()
        await ctx.send(f"{'Enabled' if self.enabled else 'Disabled'} the plugin :p")

    @birthday.command()
    @checks.has_permissions(PermissionLevel.ADMIN)
    async def timezone(self, ctx: commands.Context, timezone: str):
        """
        Set a timezone
        """
        if timezone not in pytz.all_timezones:
            matches = get_close_matches(timezone, pytz.all_timezones)
            if matches:
                embed = discord.Embed(color=0xEB3446)
                embed.description = f"Did you mean: \n`{'`, `'.join(matches)}`"
                await ctx.send(embed=embed)
            else:
                await ctx.send("Couldn't find the timezone.")
            return

        self.timezone = timezone
        await self._update_config()
        await ctx.send("Done!")


async def setup(bot):
    await bot.add_cog(BirthdayPlugin(bot))
