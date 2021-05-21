import discord
from discord.ext import commands

from clippy import checks, utils


class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='embed')
    @checks.serverowner_or_permissions(manage_messages=True)
    async def _embed(self, ctx, title, content=None, colour=None,
                     icon_url=None, image_url=None, thumbnail_url=None,
                     plain_msg=''):
        """Build and post an embed in the current channel.

        Note: Always use quotes to contain multiple words within one argument.
        """
        await ctx.embed(title=title, description=content, colour=colour,
                        icon=icon_url, image=image_url,
                        thumbnail=thumbnail_url, plain_msg=plain_msg)

    @staticmethod
    async def get_channel_by_name_or_id(ctx, name):
        channel = None
        # If a channel mention is passed, it won't be recognized as an int but this get will succeed
        name = utils.sanitize_name(name)
        try:
            channel = discord.utils.get(ctx.guild.text_channels, id=int(name))
        except ValueError:
            pass
        if not channel:
            channel = discord.utils.get(ctx.guild.text_channels, name=name)
        if channel:
            guild_channel_list = []
            for textchannel in ctx.guild.text_channels:
                guild_channel_list.append(textchannel.id)
            diff = set([channel.id]) - set(guild_channel_list)
        else:
            diff = True
        if diff:
            return None
        return channel


def setup(bot):
    bot.add_cog(Utilities(bot))
