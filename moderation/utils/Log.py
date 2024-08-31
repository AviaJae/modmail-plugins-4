import discord


class Log:
    def __init__(self, guild: discord.Guild, db):
        self.guild: discord.Guild = guild
        self.db = db
        self.channel: discord.TextChannel = None

    async def _set_channel(self):
        config = await self.db.find_one({"_id": "config"})
        if config is None or config.get("channel") is None:
            return
        
        try:
            self.channel = await self.guild.fetch_channel(int(config["channel"]))
        except discord.NotFound:
            print(f"Channel {config['channel']} not found.")
            self.channel = None
        except discord.Forbidden:
            print(f"Bot does not have permission to access channel {config['channel']}.")
            self.channel = None
        except discord.HTTPException as e:
            print(f"Failed to fetch channel {config['channel']}: {e}")
            self.channel = None

    async def log(
        self, type: str, user: discord.User, mod: discord.User, *, reason: str
    ):
        if self.channel is None:
            return f"No Log Channel has been set up for {self.guild.name}"
        
        embed = discord.Embed()
        embed.set_author(name=f"{type} | {user.name}#{user.discriminator}")
        embed.add_field(
            name="User", value=f"<@{user.id}> `({user.name}#{user.discriminator})`"
        )
        embed.add_field(
            name="Moderator", value=f"<@{mod.id}> `({mod.name}#{mod.discriminator})`"
        )
        embed.add_field(name="Reason", value=reason)
        embed.timestamp = discord.utils.utcnow()

        try:
            await self.channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Bot does not have permission to send messages to channel {self.channel.id}.")
        except discord.HTTPException as e:
            print(f"Failed to send message to channel {self.channel.id}: {e}")
