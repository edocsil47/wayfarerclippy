import asyncio
import json
import math
import os
import random
import re
from datetime import datetime

from clippy import utils

import discord
from discord.ext import commands


class Deleter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.category_ids = {}
        self.get_category_ids()
        #live
        self.notify_cid = 812048239868117033
        #debug
        #self.notify_cid = 767797600321011732
        self.odds_cid = 812048239868117033
        # live
        self.perms_source = 812106525467607090
        # debug
        #self.perms_source = 749410033556783164
        self.scores = {}
        self.get_scores()
        self.paused = False

    def get_category_ids(self):
        try:
            with open(os.path.join('data', 'deleter_category_ids.json'), 'r') as fd:
                self.category_ids = json.load(fd)
        except FileNotFoundError:
            self.category_ids = {}

    def save_category_ids(self):
        with open(os.path.join('data', 'deleter_category_ids.json'), 'w') as fd:
            json.dump(self.category_ids, fd, indent=4)

    def get_scores(self):
        try:
            with open(os.path.join('data', 'deleter_scores.json'), 'r') as fd:
                self.scores = json.load(fd)
        except FileNotFoundError:
            self.scores = {}

    def save_scores(self):
        with open(os.path.join('data', 'deleter_scores.json'), 'w') as fd:
            json.dump(self.scores, fd, indent=4)

    @commands.command(name='add_deleter', aliases=['ad'])
    async def _add_deleter(self, ctx, category_id: int, odds: int):
        category = ctx.guild.get_channel(category_id)
        if not category:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(f"No category with id {category_id} found in this server.", delete_after=15)
        key = f"{ctx.guild.id}_{category_id}"
        if key in self.category_ids:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(f"Deleter for category {category_id} already exists.", delete_after=15)
        self.category_ids[key] = {
            "id": category_id,
            "odds": odds
        }
        self.save_category_ids()
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name='change_odds', aliases=['co'])
    async def _change_odds(self, ctx, category_id: int, odds: int):
        key = f"{ctx.guild.id}_{category_id}"
        if key not in self.category_ids:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(f"No deleter found with category {category_id}.", delete_after=15)
        self.category_ids[key]["odds"] = odds
        self.save_category_ids()
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.paused:
            return
        if message.author.bot:
            return
        guild = message.guild
        if not guild:
            return
        if guild.id not in [802333887258296403, 671866672562307091]:
            return
        match = re.search(r'\D*(?P<digits>[0-9]+)\D*', message.clean_content)
        if match:
            if match.group('digits'):
                return await self.create_conke_channel(message, match.group('digits'))
        if len(self.category_ids.keys()) < 1:
            return
        category_dict = random.choice(list(self.category_ids.values()))
        category = guild.get_channel(category_dict["id"])
        if not category:
            return
        chance = random.randint(0, category_dict["odds"])
        # odds_channel = guild.get_channel(self.odds_cid)
        # if odds_channel:
        #     #await odds_channel.send(f'odds {category_dict["odds"]} - chance {chance}')
        #     print(f'odds {category_dict["odds"]} - chance {chance}')
        # else:
        #     print(f'odds {category_dict["odds"]} - chance {chance}')
        delete = chance == category_dict["odds"] - 1
        if delete:
            if len(category.channels) > 0:
                channel = random.choice(category.channels)
                if channel:
                    try:
                        await self._delete_channel(guild, channel, message)
                    except (discord.errors.Forbidden, discord.errors.NotFound):
                        pass
            else:
                try:
                    await self.notify(guild, category, None, None)
                    await category.delete()
                    del self.category_ids[f'{guild.id}_{category_dict["id"]}']
                    self.save_category_ids()
                    await self._count_score(message, "delete_category")
                    if len(self.category_ids.keys()) < 1:
                        await self._count_score(message, "game_over")
                        notify_channel = message.guild.get_channel(self.notify_cid)
                        if notify_channel:
                            await notify_channel.send(f'{message.author.mention} has "won" the game... for now.')
                except (discord.errors.Forbidden, discord.errors.NotFound):
                    pass

    async def _delete_channel(self, guild, channel, message):
        yoink = None
        async for old_message in channel.history(limit=1):
            if datetime.utcnow().timestamp() - old_message.created_at.timestamp() < 15:
                if old_message.author.id != message.author.id:
                    await self._count_score(message, "yoink")
                    await self._count_score(old_message, "been_yoinked")
                    yoink = old_message.author
        await self.notify(guild, channel, message, yoink)
        await channel.delete()
        await self._count_score(message, "delete_channel")

    async def _count_score(self, message, score_type):
        guild = message.guild
        author = message.author
        key = f"{guild.id}_{author.id}"
        if key not in self.scores:
            self.scores[key] = {
                "member_id": author.id
            }
        member_scores = self.scores[key]
        if score_type not in member_scores:
            member_scores[score_type] = 0
        member_scores[score_type] += 1
        self.save_scores()

    async def notify(self, guild, channel, message, yoink):
        send_message = f"{channel.name} just got deleted!"
        if message:
            same = message.channel.id == channel.id
            if same:
                if message.author:
                    send_message += f" And {message.author.mention} struck the killing blow!"
                    await self._count_score(message, "finisher")
            if yoink:
                send_message += f" And {message.author.mention} yoinked the delete from {yoink.mention}!"
        notify_channel = guild.get_channel(self.notify_cid)
        if not notify_channel:
            return
        await notify_channel.send(send_message)

    def del_keys(self, key_list):
        for key in key_list:
            if key in self.category_ids:
                del self.category_ids[key]

    async def create_conke_channel(self, message, digit_str):
        guild = message.guild
        channel_count = 1
        del_list = []
        for key, category_dict in self.category_ids.items():
            category = guild.get_channel(category_dict["id"])
            if category:
                channel_count += len(category.channels)
            else:
                del_list.append(key)
        self.del_keys(del_list)
        upper_bound = max(round(math.log(channel_count, 2)), 1)
        if random.randint(0, upper_bound) != (upper_bound - 1):
            return

        async def create_conke_category(category_ids, source_channel, guild, upper_bound):
            ow = source_channel.overwrites
            words = ["bepis", "conke", "bruh", "milkers", "bidoof", "boop", "shart"]
            word_1 = random.choice(words)
            word_2 = random.choice(words)
            word_3 = random.choice(words)
            new_category = await guild.create_category_channel(f"Lets {word_1} some more {word_2} off the {word_3}",
                                                               overwrites=ow)
            lower = max(1, round(upper_bound / 2))
            upper = max(2, round((upper_bound + 2) * 1.3))
            odds = random.randint(lower, upper)
            key = f"{guild.id}_{new_category.id}"
            category_ids[key] = {
                "id": new_category.id,
                "odds": odds
            }
            return new_category

        found_cat = None
        del_list = []
        for key, category_dict in self.category_ids.items():
            category = guild.get_channel(category_dict["id"])
            if category:
                if not self.category_ids[key].setdefault("locked", False):
                    if len(category.channels) + 4 < 50:
                        found_cat = category
                        break
            else:
                del_list.append(key)
        self.del_keys(del_list)

        if not found_cat:
            source_channel = guild.get_channel(self.perms_source)
            if not source_channel:
                return
            found_cat = await create_conke_category(self.category_ids, source_channel, guild, upper_bound)
            await self._count_score(message, "create_category")
            self.save_category_ids()

        lower_digit = str(int(digit_str) - 1)
        digit_str = digit_str[:69]
        lower_digit = lower_digit[:69]
        key = f"{guild.id}_{found_cat.id}"
        self.category_ids[key]["locked"] = True
        wasp_chance = 1 == random.randint(1, 10)
        if wasp_chance:
            new_channels = [
                await self._create_and_wait(message, f'{digit_str} cups of wasp on the wall', found_cat),
                await self._create_and_wait(message, f'{digit_str} cups of wasp', found_cat),
                await self._create_and_wait(message, f'{utils.waspcup_gen()}', found_cat),
                await self._create_and_wait(message, f'{lower_digit} cups of wasp on the wall', found_cat)]
            await self._count_score(message, "wasp")
        else:
            new_channels = [await self._create_and_wait(message, f'{digit_str} bottles of conke on the wall', found_cat),
                            await self._create_and_wait(message, f'{digit_str} bottles of conke', found_cat),
                            await self._create_and_wait(message, 'take one down pass it around', found_cat),
                            await self._create_and_wait(message, f'{lower_digit} bottles of conke on the wall', found_cat)]
        await self._count_score(message, "create_channel")

        send_chance = random.randint(1, 6)
        #print(f" {send_chance} send_chance")
        self.category_ids[key]["locked"] = False
        if send_chance == 4:
            send_channel = random.choice(new_channels)
            if send_channel:
                first_message = await send_channel.send("first")
                await self._count_score(message, "first")
                await self._listen_for_second(first_message)

    async def _listen_for_second(self, first_message):
        channel = first_message.channel

        def check(message):
            if message:
                if channel:
                    return (not message.author.bot) and message.channel.id == channel.id

        try:
            done, pending = await asyncio.wait([
                self.bot.wait_for('message', check=check)
            ], timeout=5,
                return_when=asyncio.FIRST_COMPLETED)
            for future in pending:
                future.cancel()
            try:
                stuff = done.pop().result()
                new_msg = stuff
                if new_msg.clean_content.lower() == "second":
                    await new_msg.add_reaction(self.bot.success_react)
                    return await self._count_score(new_msg, "second")
            except Exception as e:
                return print(f"failed second because: {e}")

        except asyncio.TimeoutError:
            return

    async def _create_and_wait(self, message, name, cat):
        try:
            new_channel = await message.guild.create_text_channel(name, category=cat)
            await asyncio.sleep(.5)
        except discord.errors.HTTPException as e:
            self.bot.logger.info(f"nuke after exception: '{e}'\nchannel count: {len(message.guild.channels)}")
            await self.nuke(message)
            new_channel = await message.guild.create_text_channel(name, category=cat)
        return new_channel

    async def nuke(self, message):
        found_cat = None
        del_list = []
        for key, category_dict in self.category_ids.items():
            category = message.guild.get_channel(category_dict["id"])
            if category:
                if len(category.channels) > 25:
                    found_cat = category
                    break
            else:
                del_list.append(key)
        self.del_keys(del_list)

        self.paused = True
        for channel in found_cat.channels:
            try:
                await channel.delete()
                await asyncio.sleep(.5)
            except:
                pass
        try:
            await found_cat.delete()
            del self.category_ids[f'{message.guild.id}_{found_cat.id}']
            await self._count_score(message, "nukes")
            notify_channel = message.guild.get_channel(self.notify_cid)
            if notify_channel:
                await notify_channel.send(f"{message.author.mention} nuked **{found_cat.name}**!!")
            if len(self.category_ids.keys()) < 1:
                await self._count_score(message, "game_over")
                await notify_channel.send(f'{message.author.mention} has "won" the game... for now.')
        except:
            pass

        self.paused = False

    @commands.command(name='my_scores', aliases=['my_score'])
    async def _my_scores(self, ctx):
        key = f"{ctx.guild.id}_{ctx.author.id}"
        if key not in self.scores:
            return await ctx.send("You've scored no points yet!")
        create_category = self.scores[key].setdefault("create_category", 0)
        create_channel = self.scores[key].setdefault("create_channel", 0)
        finisher = self.scores[key].setdefault("finisher", 0)
        delete_channel = self.scores[key].setdefault("delete_channel", 0)
        delete_category = self.scores[key].setdefault("delete_category", 0)
        first = self.scores[key].setdefault("first", 0)
        second = self.scores[key].setdefault("second", 0)
        game_over = self.scores[key].setdefault("game_over", 0)
        nukes = self.scores[key].setdefault("nukes", 0)
        yoink = self.scores[key].setdefault("yoink", 0)
        been_yoink = self.scores[key].setdefault("been_yoinked", 0)
        wasp = self.scores[key].setdefault("wasp", 0)
        if create_category + create_channel + finisher + delete_channel + delete_category + nukes + first == 0:
            return await ctx.send("You've scored no points yet!")
        message = f"Wow {ctx.author.mention}, look at all your Internet Points!\n"
        if create_category > 0:
            message += f"\nYou've created {create_category} categories!"
        if create_channel > 0:
            message += f"\nYou've created {create_channel} (x4) channels!"
        if delete_category > 0:
            message += f"\nYou've deleted {delete_category} categories!"
        if delete_channel > 0:
            message += f"\nYou've deleted {delete_channel} channels!"
        if yoink > 0:
            message += f"\nYou've yoinked {yoink} deletes!"
        if been_yoink > 0:
            message += f"\nYou've Ben Yoinked on {been_yoink} deletes!"
        if wasp > 0:
            message += f"\nYou've got {wasp} {utils.waspcup_gen()}!"
        second_message = "!"
        if second > 0:
            second_message = f" and you've seconded Clippy {second} times!"
        if first > 0:
            message += f"\nYou've received {first} Clippy firsts{second_message}"
        if finisher > 0:
            message += f"\nAnd you've struck the killing blow {finisher} times!"
        if nukes > 0:
            message += f"\nAnd you've dropped {nukes} nukes!"
        if game_over > 0:
            message += f'\nAnd you\'ve "won" {game_over} times. Was it really a victory though?'
        return await ctx.send(message)


def setup(bot):
    bot.add_cog(Deleter(bot))
