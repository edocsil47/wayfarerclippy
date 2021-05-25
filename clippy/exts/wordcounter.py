import json
import os
import random
import re

import discord
from discord.ext import commands

from clippy import utils


class WordCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counts = {}
        self.react_lists = {}
        self.get_word_counts()
        self.load_react_lists()

    def get_word_counts(self):
        try:
            with open(os.path.join('data', 'word_counts.json'), 'r') as fd:
                self.counts = json.load(fd)
        except FileNotFoundError:
            self.counts = {}

    def save_word_counts(self):
        with open(os.path.join('data', 'word_counts.json'), 'w') as fd:
            json.dump(self.counts, fd, indent=4)

    def load_react_lists(self):
        try:
            with open(os.path.join('data', 'react_lists.json'), 'r') as fd:
                self.react_lists = json.load(fd)
        except FileNotFoundError:
            self.react_lists = {}

    def save_react_lists(self):
        with open(os.path.join('data', 'react_lists.json'), 'w') as fd:
            json.dump(self.react_lists, fd, indent=4)

    @commands.command(name="add_react_list", aliases=['arl'])
    @commands.has_permissions(manage_roles=True)
    async def add_react_list(self, ctx, *, info):
        """
        Do '!add_react_list <name>, <emoji>, <channel_id>, <word1>[,<word2>, <word3>]'
        For example: `!add_react_list snivy, :snivy:, 103110311031103110, snivy`
        Use 'none' instead of a channel id to apply this react list to all channels.
        (don't include the <> or [] when running the command)
        Also works with '!arl'
        """
        info = re.split(r',\s+', info)
        if len(info) < 4:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(
                "Must provide at least a name for the list, a reaction emoji, channel, and a list of at least 1 listen word.",
                delete_after=10)
        name, emoji, channel_raw, words = info[0], info[1], info[2], info[3:]
        rl_name = f"{ctx.guild.id}_{name}"
        if rl_name in self.react_lists.keys():
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(
                f"A reaction list already exists for {name}. To add a word to its list, use the "
                f"`!add_word_to_react_list/!awrl` command",
                delete_after=20)
        utilities_cog = self.bot.cogs.get('Utilities')
        channel_id = "none"
        if channel_raw != "none":
            channel = await utilities_cog.get_channel_by_name_or_id(ctx, channel_raw)
            if not channel:
                await ctx.message.add_reaction(self.bot.failed_react)
                return await ctx.send(f"Could not find channel {channel_raw}", delete_after=10)
            channel_id = channel.id
        converter = commands.PartialEmojiConverter()
        badge_emoji = None
        try:
            badge_emoji = await converter.convert(ctx, info[1].strip())
            emoji = badge_emoji
            await ctx.message.add_reaction(emoji)
        except:
            pass
        try:
            await ctx.message.add_reaction(info[1].strip())
            badge_emoji = info[1].strip()
            emoji = badge_emoji
        except:
            pass
        if not badge_emoji:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("Could not find that emoji.", delete_after=10)

        self.react_lists[rl_name] = {
            "name": name,
            "emoji": emoji,
            "channel_id": channel_id,
            "guild_id": ctx.guild.id,
            "words": words
        }
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name="add_word_to_react_list", aliases=['awrl'])
    @commands.has_permissions(manage_roles=True)
    async def add_word_to_react_list(self, ctx, name, word):
        """
        Do '!add_word_to_react_list <name> <word>'
        For example: `!add_word_to_react_list snivy, serperior`
        (don't include the <> or [] when running the command)
        (don't use a comma in this command!)
        Also works with '!awrl'
        """
        rl_name = f"{ctx.guild.id}_{name}"
        if rl_name not in self.react_lists.keys():
            await ctx.send(f"No react list named {name} found.", delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        if word in self.react_lists[rl_name]["words"]:
            await ctx.send(f"{word} is already in the react list for {name}.", delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        self.react_lists[rl_name]["words"].append(word)
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name="remove_word_from_react_list", aliases=['rwrl'])
    @commands.has_permissions(manage_roles=True)
    async def remove_word_from_react_list(self, ctx, name, word):
        """
        Do '!remove_word_from_react_list <name> <word>'
        For example: `!remove_word_from_react_list snivy, serperior`
        (don't include the <> or [] when running the command)
        (don't use a comma in this command!)
        Also works with '!rwrl'
        """
        rl_name = f"{ctx.guild.id}_{name}"
        if rl_name not in self.react_lists.keys():
            await ctx.send(f"No react list named {name} found.", delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        if word not in self.react_lists[rl_name]["words"]:
            await ctx.send(f"{word} is not in the react list for {name}.", delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        self.react_lists[rl_name]["words"].remove(word)
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name='add_word_counter', aliases=['awc'])
    @commands.has_permissions(manage_roles=True)
    async def add_word_counter(self, ctx, *, info):
        """
        Do '!add_word_counter <word>, <channel_id>[,<channel_id2>, <channel_id3>]'
        For example: `!add_word_counter snivy, 103110311031103110`
        Exclude channel id to apply this word counter to all channels.
        (don't include the <> or [] when running the command)
        Also works with '!awc'
        """
        info = re.split(r',\s+', info)
        if len(info) < 1:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(
                "Must provide at least a word to count. optionally channel id(s).",
                delete_after=10)
        counted_word = info[0].lower()
        channel_ids = []
        utilities_cog = self.bot.cogs.get('Utilities')
        if len(info) > 1:
            channel_ids_raw = info[1:]
            for c_id in channel_ids_raw:

                channel = await utilities_cog.get_channel_by_name_or_id(ctx, c_id)
                if channel:
                    channel_ids.append(channel.id)
        rl_name = f"{ctx.guild.id}_{counted_word}"
        self.counts[rl_name] = {
            "counted_word": counted_word,
            "guild_id": ctx.guild.id,
            "channel_ids": channel_ids,
            "count": {}
        }
        await ctx.message.add_reaction(self.bot.success_react)
        success_msg = f"Word Counter for '**{counted_word}**' added."
        if len(channel_ids) > 0:
            success_msg += f" Active in {len(channel_ids)} channels."
        self.save_word_counts()
        return await ctx.send(success_msg, delete_after=10)

    @commands.command(name="list_word_counter", aliases=['lwc'])
    @commands.has_permissions(manage_roles=True)
    async def list_word_counter(self, ctx):
        output = "**Current word counters**\n"
        for key in self.counts.keys():
            if self.counts[key]["guild_id"] == ctx.guild.id:
                output += f"Name: {self.counts[key]['counted_word']}\n"
                if len(self.counts[key]["channel_ids"]) > 0:
                    channel_str = [str(cid) for cid in self.counts[key]['channel_ids']]
                    output += f"Active Channels: {', '.join(channel_str)}"
        await ctx.send(output)

    @commands.command(name="list_react_lists", aliases=['lrl'])
    @commands.has_permissions(manage_roles=True)
    async def list_react_lists(self, ctx):
        output_parts = []
        for key in self.react_lists.keys():
            if self.react_lists[key]["guild_id"] == ctx.guild.id:
                output = f"Name: {self.react_lists[key]['name']} - Emoji: {self.react_lists[key]['emoji']}\n"
                output += f"{', '.join(self.react_lists[key]['words'])}\n\n"
                if self.react_lists[key]["channel_id"] != "none":
                    output += f"Active in {self.react_lists[key]['channel_id']}"
                output_parts.append(output)
        await utils.send_message_in_chunks(output_parts, ctx)

    @commands.command(name='my_count', aliases=['my'])
    async def my_count(self, ctx, raw_word):
        """
        Do '!my_count word' with any word counted by the bot to see your personal count.
        Also works with '!my'
        """
        word = raw_word.lower().strip()
        singular = word
        if word[-1] == 's':
            singular = f"{ctx.guild.id}_{word[:-1]}"
        word = f"{ctx.guild.id}_{word}"

        if word in self.counts.keys():
            word = word
        elif singular in self.counts.keys():
            word = singular
        else:
            return await ctx.send(f'"{raw_word}" is not being counted right now.')
        add = False
        print(raw_word)
        if raw_word == "scores" or raw_word == "score":
            add = True
        user_counts = self.counts[word]["count"]
        if str(ctx.message.author.id) not in user_counts:
            return await ctx.send(f'You haven\'t said "{raw_word}" at all!')
        word_count = user_counts[str(ctx.message.author.id)]
        message = f'You\'ve said "{raw_word}" {word_count} times!'
        if add:
            message += "\n(haha whoops!!)"
        return await ctx.send(message)


    @commands.command(name='word_leaderboard', aliases=['wlb'])
    async def word_leaderboard(self, ctx, raw_word):
        """
        Do '!word_leaderboard word' with any word counted by the bot to see the top 10 sayers of that word.
        Also works with '!wlb'
        """
        word = raw_word.lower()
        singular = word
        if word[-1] == 's':
            singular = f"{ctx.guild.id}_{word[:-1]}"
        word = f"{ctx.guild.id}_{word}"

        if word in self.counts.keys():
            word = word
        elif singular in self.counts.keys():
            word = singular
        else:
            return await ctx.send(f"{raw_word} is not being counted right now.")
        user_counts = self.counts[word]["count"]
        sorted_user_counts = {k: v for k, v in
                              sorted(user_counts.items(), key=lambda item: item[1], reverse=True)}
        top_ten = list(sorted_user_counts.keys())[:10]
        description = ""
        count = 1
        for user_id in top_ten:
            word_count = sorted_user_counts[user_id]
            member = ctx.guild.get_member(int(user_id))
            if not member:
                continue
            description += f"{count}. **{member.display_name}** - {word_count}\n"
            count += 1
        lb_embed = discord.Embed(title=f'Top {count - 1} "{self.counts[word]["counted_word"]}" sayers',
                                 description=description)
        await ctx.send(embed=lb_embed)


    @commands.Cog.listener()
    async def on_message(self, message):
        check_str = message.clean_content.lower()
        # walsh
        if message.author.id == 188389841845616640:
            check_str = check_str.replace('\u200b', '')
        # bjmacke
        elif message.author.id == 309521938781569024:
            check_str = check_str.replace('ο', 'o')
        else:
            if random.randint(1, 10) < 3:
                check_str = check_str.replace('\u200b', '')
        #check_str = f"{message.guild.id}_{check_str}"
        if message.author != self.bot.user:
            for name in self.react_lists:
                this_react = self.react_lists[name]
                if this_react["guild_id"] == message.guild.id:
                    if this_react["channel_id"] == "none" or message.channel.id == this_react["channel_id"]:
                        for word in this_react["words"]:
                            if self._has_string(fr"\b{word}\b", check_str):
                                try:
                                    await message.add_reaction(this_react["emoji"])
                                except Exception as e:
                                    pass
            if not check_str.startswith("!"):
                for key in self.counts.keys():
                    if self.counts[key]["guild_id"] == message.guild.id:
                        word = self.counts[key]["counted_word"]
                        if self._has_string(fr"\b{word}(s)*\b", check_str):
                            if len(self.counts[key]["channel_ids"]) > 0:
                                if message.channel.id not in self.counts[key]["channel_ids"]:
                                    continue
                            author_id = str(message.author.id)
                            if author_id not in self.counts[key]["count"]:
                                self.counts[key]["count"][author_id] = 0
                            self.counts[key]["count"][author_id] += 1



    @staticmethod
    def _check_words(word_list, message):
        for word in word_list:
            if word in message:
                return True
        return False

    @staticmethod
    def _has_string(string, text):
        match = re.search(string, text)
        if match:
            return True
        else:
            return False


def setup(bot):
    bot.add_cog(WordCounter(bot))
