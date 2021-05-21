import math
import s2sphere

import discord
from discord.ext import commands


class S2Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='get_cell_id', aliases=['cell', 'cid'])
    async def _get_cell_id(self, ctx, size: int, lat: float, lng: float):
        """Displays the S2 cell id at the location provided
           Usage: `!cell <cell size> <latitude> <longitude>` Aliases: cell, cid, get_cell_id
           (don't include the < > when running the command)"""
        if ctx.channel.id not in [727982492035842070, 702292480028311592, 644310701183336507]:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
            return await ctx.send(embed=discord.Embed(
                colour=discord.Colour.red(),
                description=f"Please use the `!cell` commands in #clippys-corner"),
                delete_after=10)
        cell_id = s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees(float(lat), float(lng)))
        size_cell_id = cell_id.parent(size)
        cell_token = size_cell_id.to_token()
        return await ctx.send(f"Level {size} {size_cell_id}\nCell token: {cell_token}")

    @commands.command(name='haversine', aliases=['hav', 'distance', 'dis'])
    async def _haversine(self, ctx, lat1: float, lon1: float, lat2: float, lon2: float):
        """
        Do '!haversine lat1, lon1, lat2, lon2' to get the distance across the Earth's surface between 2 points.
        Also works with '!hav', '!distance', '!dis'
        """
        R = 6372800  # Earth radius in meters
        conv = 1609.34  # meters in a mile
        conv_metric = 1000

        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2

        await ctx.send(f"{2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a)) / conv_metric}km")


def setup(bot):
    bot.add_cog(S2Tools(bot))
