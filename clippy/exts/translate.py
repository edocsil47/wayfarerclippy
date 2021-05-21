import discord
import requests
from discord.ext import commands

from clippy import utils


class Translate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True, name='translate', aliases=['tr'])
    @commands.has_permissions(manage_roles=True)
    async def _translate(self, ctx, *, text):
        url = "https://systran-systran-platform-for-language-processing-v1.p.rapidapi.com/translation/text/translate"

        querystring = {"source":"auto","target":"en","input":"Cuantos%20votos%20positivos%20se%20necesitan%20para%20aprobar%20una%20solicitud%3F"}

        headers = {
            'x-rapidapi-host': "systran-systran-platform-for-language-processing-v1.p.rapidapi.com",
            'x-rapidapi-key': "6a86cee125mshfbb4bfc9dc9bae4p17d2e8jsn97012fc5213d"
        }

        response = requests.request("GET", url, headers=headers, params=querystring)

        print(response.text)
        return await ctx.send(response.text)
        # print(u'Detected source language: {}'.format(
        #     result['detectedSourceLanguage']))


def setup(bot):
    bot.add_cog(Translate(bot))
