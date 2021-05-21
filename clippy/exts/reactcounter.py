import json
import os
import re

import discord
from discord.ext import commands


class ReactCounter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counts = {}
        self.get_react_counts()

    def get_react_counts(self):
        try:
            with open(os.path.join('data', 'react_counts.json'), 'r') as fd:
                self.counts = json.load(fd)
        except FileNotFoundError:
            self.counts = {}

    def save_react_counts(self):
        with open(os.path.join('data', 'react_counts.json'), 'w') as fd:
            json.dump(self.counts, fd, indent=4)

    @commands.command(name='add_react_counter', aliases=['arc'])
    @commands.has_permissions(manage_roles=True)
    async def add_react_counter(self, ctx, *, info):
        info = re.split(r',\s+', info)
        if len(info) < 4:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("Must provide at least an emoji, counter name, target user, counter message,  optionally channel id(s).",
                                  delete_after=10)
        converter = commands.PartialEmojiConverter()
        try:
            badge_emoji = await converter.convert(ctx, info[0].strip())
        except:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("Could not find that emoji.", delete_after=10)
        if str(badge_emoji.id) in self.counts.keys():
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("React counter already exists with that emoji.", delete_after=10)
        converter = commands.MemberConverter()
        try:
            member = await converter.convert(ctx, info[2])
        except:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(f"Could not find user {info[2]}.", delete_after=10)
        counter_name = info[1]
        channel_ids = []
        counter_message = info[3]
        if len(info) > 4:
            channel_ids_raw = info[4:]

            for c_id in channel_ids_raw:
                utilities_cog = self.bot.cogs.get('Utilities')
                channel = await utilities_cog.get_channel_by_name_or_id(ctx, c_id)
                if channel:
                    channel_ids.append(channel.id)
        self.counts[badge_emoji.id] = {
            "name": counter_name,
            "emoji_id": badge_emoji.id,
            "channel_ids": channel_ids,
            "user": member.id,
            "message": counter_message,
            "count": 0
        }
        await ctx.message.add_reaction(self.bot.success_react)
        success_msg = f"Counter '**{counter_name}**' added with emoji {badge_emoji}."
        if len(channel_ids) > 0:
            success_msg += f" Active in {len(channel_ids)} channels."
        self.save_react_counts()
        return await ctx.send(success_msg, delete_after=10)

    @commands.command(name='get_count', aliases=['grc'])
    async def get_count(self, ctx, emoji):
        converter = commands.PartialEmojiConverter()
        try:
            react_emoji = await converter.convert(ctx, emoji.strip())
        except:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("Could not find that emoji.", delete_after=10)
        if str(react_emoji.id) not in self.counts:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("No react counter found with that emoji.", delete_after=10)
        react_count = self.counts[str(react_emoji.id)]
        await ctx.send(f"I have counted {react_count['count']} {react_count['message']}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.errors.NotFound, AttributeError):
            return
        if not message.guild:
            return

        emoji_id = str(payload.emoji.id)

        if payload.user_id != message.author.id:
            if emoji_id in self.counts:
                if channel.id in self.counts[emoji_id]["channel_ids"] or len(self.counts[emoji_id]["channel_ids"]) < 1:
                    if message.author.id == self.counts[emoji_id]["user"]:
                        self.counts[emoji_id]["count"] += 1


def setup(bot):
    bot.add_cog(ReactCounter(bot))
