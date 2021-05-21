import json
import os

import discord
from discord.ext import commands


class MoneyMoney(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pokemon = {}
        self._load_pokemon()
        self.scores = {}
        self._load_scores()

    def _load_pokemon(self):
        with open(os.path.join('data', 'pokemon_id_map.json'), 'r') as fd:
            self.pokemon = json.load(fd)

    def _load_scores(self):
        try:
            with open(os.path.join('data', 'money_scores.json'), 'r') as fd:
                self.scores = json.load(fd)
        except FileNotFoundError:
            self.scores = {}

    def save_scores(self):
        with open(os.path.join('data', 'money_scores.json'), 'w') as fd:
            json.dump(self.scores, fd, indent=4)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author != self.bot.user:
            check_str = message.clean_content.lower()
            if not check_str.startswith('$'):
                return
            dollar_signs = check_str.count('$')
            multiplier = 1 + (dollar_signs-1)/10
            split_content = check_str.split()
            pokemon = ' '.join(split_content[1:]).strip()
            mega, shiny, clippy, boobs = False, False, False, False
            if 'mega ' in pokemon:
                mega = True
                pokemon = pokemon.replace('mega ', '')
            if 'mega-' in pokemon:
                mega = True
                pokemon = pokemon.replace('mega-', '')
            if 'shiny ' in pokemon:
                shiny = True
                pokemon = pokemon.replace('shiny ', '')
            if 'clippy' in pokemon:
                clippy = True
            if 'boobs' in pokemon:
                boobs = True
            key = f"{message.guild.id}_{message.author.id}"
            if key not in self.scores.keys():
                self.scores[key] = {
                    "member_id": message.author.id,
                    "money": 0
                }
            if clippy:
                money = 0 - self.scores[key]["money"]
                self.scores[key]["money"] += money
            elif boobs:
                self.scores[key]["money"] = 80085
            elif pokemon in self.pokemon.keys():
                money = self.pokemon[pokemon]
                if mega:
                    money *= 2
                if shiny:
                    multiplier = 0 - multiplier
                money = round(money * multiplier)
                self.scores[key]["money"] += money
            self.save_scores()
            await message.add_reaction('💲')

    @commands.command(name="my_money", aliases=["$$$"])
    async def _my_money(self, ctx):
        key = f"{ctx.guild.id}_{ctx.author.id}"
        if key not in self.scores.keys():
            self.scores[key] = {
                "member_id": ctx.author.id,
                "money": 0
            }
            self.save_scores()
            return await ctx.send("You have no money!")
        money = self.scores[key]["money"]
        return await ctx.send(f"You have ${money}!!")


def setup(bot):
    bot.add_cog(MoneyMoney(bot))
