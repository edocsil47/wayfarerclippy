import asyncio
import json
import os
import random
import time
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands import BucketType
from peewee import fn

from clippy import utils
from clippy.exts.db.clippy_db import ThroneRoundTable, ThroneRound


class ThroneGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.throne_config = None
        self._load_throne_config()
        self.current_rounds = {}
        self._load_round()

    def _load_throne_config(self):
        try:
            with open(os.path.join('data', 'new_throne_config.json'), 'r') as fd:
                self.throne_config = json.load(fd)
        except FileNotFoundError:
            self.throne_config = {}

    def save_throne_config(self):
        with open(os.path.join('data', 'new_throne_config.json'), 'w') as fd:
            json.dump(self.throne_config, fd, indent=4)

    def _load_thing_list(self, guild_id):
        thing_list = []
        with open(os.path.join('data', 'thing_list.txt'), 'r') as fd:
            lines = fd.readlines()
            for line in lines:
                thing_list.append(line.strip())
        tid = 0
        for thing in thing_list:
            self.throne_config[str(guild_id)]["things"][str(tid)] = thing
            tid += 1

    def _ensure_default_config(self, guild):
        if str(guild.id) not in self.throne_config.keys():
            self.throne_config[str(guild.id)] = {
                "throne_role_id": None,
                "crown_wearer_id": None,
                "last_claim_time": 1614442990,
                "cooldown_seconds": 60,
                "game_channel_id": None,
                "scores": {},
                "things": {},
                "thing_assignments": {},
                "round_length": 1
            }

    @commands.command(hidden=True, aliases=['scd'])
    @commands.has_permissions(manage_roles=True)
    async def set_cooldown(self, ctx, seconds):
        self._ensure_default_config(ctx.guild)
        self.throne_config[str(ctx.guild.id)]["cooldown_seconds"] = seconds
        self.save_throne_config()
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, aliases=['sgc'])
    @commands.has_permissions(manage_roles=True)
    async def set_game_channel(self, ctx, channel_id):
        self._ensure_default_config(ctx.guild)
        self.throne_config[str(ctx.guild.id)]["game_channel_id"] = channel_id
        self.save_throne_config()
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, aliases=['str'])
    @commands.has_permissions(manage_roles=True)
    async def set_throne_role(self, ctx, role_id):
        role_id = utils.sanitize_name(role_id)
        try:
            role_id = int(role_id)
            role = discord.utils.get(ctx.guild.roles, id=role_id)
        except:
            role = discord.utils.get(ctx.guild.roles, name=role_id)
        if role is None:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(embed=discord.Embed(colour=discord.Colour.red(),
                                                      description=f"Unable to find role with name or id: **{role_id}**."),
                                  delete_after=10)
        self._ensure_default_config(ctx.guild)
        self.throne_config[str(ctx.guild.id)]["throne_role_id"] = role.id
        self.save_throne_config()
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, name="set_round_length", aliases=['srlen'])
    @commands.has_permissions(manage_roles=True)
    async def _set_round_length(self, ctx, round_length):
        """Set the length of a throne game round in hours."""
        self._ensure_default_config(ctx.guild)
        self.throne_config[str(ctx.guild.id)]["round_length"] = round_length
        self.save_throne_config()
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, name="set_seize_delay_minutes", aliases=['sdelay'])
    @commands.has_permissions(manage_roles=True)
    async def _set_seize_delay_minutes(self, ctx, delay_minutes):
        """Set the length time before Clippy seizes the throne in minutes."""
        self._ensure_default_config(ctx.guild)
        self.throne_config[str(ctx.guild.id)]["seize_delay_minutes"] = delay_minutes
        self.save_throne_config()
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, name="set_seize_odds", aliases=['sodds'])
    @commands.has_permissions(manage_roles=True)
    async def _set_seize_odds(self, ctx, seize_odds):
        self._ensure_default_config(ctx.guild)
        self.throne_config[str(ctx.guild.id)]["seize_odds"] = seize_odds
        self.save_throne_config()
        await ctx.message.add_reaction(self.bot.success_react)

    def _load_round(self):
        latest_round = (ThroneRoundTable.select(
            fn.MAX(ThroneRoundTable.round_number).alias('round_number'),
            ThroneRoundTable.start_time,
            ThroneRoundTable.end_time,
            ThroneRoundTable.active,
            ThroneRoundTable.guild_id
        )
                 .group_by(ThroneRoundTable.guild_id))
        found_round = latest_round.objects(ThroneRound)
        if len(found_round) < 1:
            return
        else:
            for i in range(len(found_round)):
                found = found_round[i]
                self.current_rounds[str(found.guild_id)] = found

    def start_loop(self):
        for guild_id in self.current_rounds:
            if self.current_rounds[str(guild_id)].active == True:
                self.bot.tasks.append(self.bot.event_loop.create_task(self.check_round_loop(guild_id)))

    async def _end_round(self, guild_id):
        guild = self.bot.get_guild(int(guild_id))
        round_number = self.current_rounds[str(guild_id)].round_number
        self.bot.logger.info(f"Ending Round {round_number} in guild {guild_id}")

        (ThroneRoundTable.update(active=False)
         .where((ThroneRoundTable.round_number == round_number)
                & (ThroneRoundTable.guild_id == guild_id))).execute()
        self.bot.logger.info("End Round: database updated")

        self.current_rounds[str(guild_id)].active = False
        self.current_rounds[str(guild_id)].end_time = time.time()

        self.throne_config[str(guild_id)]['thing_assignments'] = {}
        self.bot.logger.info(self.throne_config[str(guild_id)])
        scores = self.throne_config[str(guild_id)]["scores"][str(round_number)]
        self.bot.logger.info("End Round: assignments reset")

        self.bot.logger.info("End Round: before get channel")
        game_channel = self.bot.get_channel(self.throne_config[str(guild_id)]['game_channel_id'])
        if guild.id == 802333887258296403:
            await game_channel.send("LET'S SEE")
        self.bot.logger.info("End Round: after get channel")
        if len(scores.keys()) < 1:
            self.bot.logger.info("End Round: No scores found")
            return await game_channel.send("The round has ended!")

        self.bot.logger.info("End Round: Getting Last Throne holding Member")
        last_crown_holder_id = self.throne_config[str(guild_id)]["crown_wearer_id"]
        last_crown_holder = guild.get_member(last_crown_holder_id)
        await asyncio.sleep(1)

        await game_channel.send(f"The round has ended!")
        scores_msg = await self.get_top_scores(scores)

        self.bot.logger.info("End Round: Score tallying complete")
        await game_channel.send(f"The round has ended with {last_crown_holder.display_name} on the throne!"
                                       f"\n\nRound scoreboard:\n{scores_msg}")

        self.bot.logger.info("End Round: Getting throne role")
        try:
            throne_role_id = self.throne_config[str(guild_id)]["throne_role_id"]
            throne_role = guild.get_role(throne_role_id)
            await asyncio.sleep(1)
            self.bot.logger.info("End Round: Removing throne role")
            await last_crown_holder.remove_roles(throne_role)
            await asyncio.sleep(1)
        except Exception as e:
            self.bot.logger.warning(f"I FAILED TO GET THE ROLE BECAUSE I'M JUST A DUMB ROBOT: {e}")
        self.bot.logger.info("End Round: Crown role removed")

    async def get_top_scores(self, scores, score_count=5):
        sorted_scores = {k: v for k, v in sorted(scores.items(), key=lambda item: item[1], reverse=True)}
        scores_msg = ""
        count = 0
        self.bot.logger.info(f"End Round: Tallying scores\n{sorted_scores}")

        for mem_id, score in sorted_scores.items():
            try:
                member = self.bot.get_user(int(mem_id))
                await asyncio.sleep(.1)
                if member:
                    mem_str = member.display_name
                else:
                    mem_str = str(mem_id)
                scores_msg += f"{count + 1}. **{mem_str}** - {score} points\n"
                count += 1
                if count > score_count:
                    break
            except Exception as e:
                self.bot.logger.error(f"Failed to get guild or member with error: {e}")
                continue
        return scores_msg

    async def check_clippy_seize(self, guild_id, force=False):
        guild = self.bot.get_guild(int(guild_id))
        previous_crown_holder_id = self.throne_config[str(guild_id)]["crown_wearer_id"]
        game_channel = self.bot.get_channel(self.throne_config[str(guild_id)]['game_channel_id'])
        new_claim_time = self.throne_config[str(guild_id)]["last_claim_time"] = \
            datetime.utcnow().timestamp() - int(self.throne_config[str(guild_id)]["cooldown_seconds"])
        if previous_crown_holder_id == self.bot.user.id:
            person_thing = self._get_person_thing(guild.id, self.bot.user.id)
            self.throne_config[str(guild_id)]["last_claim_time"] = new_claim_time
            claim_msg = f'\nFind "{person_thing}" to claim the throne from **King Clippy**!'
            await game_channel.send("**King Clippy** grows tired of your petty squabbles and demands tribute!"
                                    f"\n{claim_msg}")
            if guild.id != 802333887258296403:
                await game_channel.edit(topic=claim_msg)
            return
        always_seize = self.throne_config[str(guild_id)].get("always_seize", False)
        seize_odds = float(self.throne_config[str(guild_id)].setdefault("seize_odds", .5))
        seize_roll = random.randint(1, 100) / 100
        self.bot.logger.info(f"Seize odds: {seize_odds}, seize roll: {seize_roll}, Seize: {seize_roll <= seize_odds}")
        if always_seize or force or seize_roll <= seize_odds:
            previous_crown_holder = guild.get_member(previous_crown_holder_id)
            self.throne_config[str(guild_id)]["crown_wearer_id"] = self.bot.user.id
            self.throne_config[str(guild_id)]["last_claim_time"] = new_claim_time
            throne_role_id = self.throne_config[str(guild_id)]["throne_role_id"]
            throne_role = guild.get_role(throne_role_id)
            await previous_crown_holder.remove_roles(throne_role)
            person_thing = self._get_person_thing(guild.id, self.bot.user.id)
            claim_msg = f'\nFind "{person_thing}" to claim the throne from **King Clippy**!'
            await game_channel.send("The Game of Thrones grows dormant, King Clippy takes this opportunity "
                                    f"to seize the throne from {previous_crown_holder.mention}!\n"
                                    f"All Hail King Clippy!!\n\n{claim_msg}")
            if guild.id != 802333887258296403:
                await game_channel.edit(topic=claim_msg)

    @commands.command(name='force_end')
    @commands.has_permissions(manage_roles=True)
    async def _force_end(self, ctx):
        tasks = self.bot.tasks
        for t in range(len(tasks)):
            task = tasks[t]
            if task._coro.cr_code.co_name == "check_round_loop":
                tasks.pop(t)
                task.cancel()
                break
        await self._end_round(ctx.guild.id)

    @commands.command(name='force_seize')
    @commands.has_permissions(manage_roles=True)
    async def _force_seize(self, ctx):
        await self.check_clippy_seize(ctx.guild.id, True)

    @commands.command(name='throne_leaderboard', aliases=['tlb', 'throne_board'])
    @commands.cooldown(rate=1, per=30, type=BucketType.channel)
    async def _throne_leaderboard(self, ctx):
        game_channel_id = self.throne_config[str(ctx.guild.id)]["game_channel_id"]
        if str(ctx.channel.id) != str(game_channel_id):
            return await ctx.message.delete()
        guild_id = ctx.guild.id
        round_number = self.current_rounds[str(guild_id)].round_number
        scores = self.throne_config[str(guild_id)]["scores"][str(round_number)]
        scores_msg = await self.get_top_scores(scores, 10)
        return await ctx.send(f"Leaderboard for current Throne Game:\n\n{scores_msg}")

    # def pretty_time_diff(self, time_diff):
    #     seconds = time_diff % 60
    #     time_diff /= 60
    #     minutes = time_diff % 60
    #     time_diff /= 60
    #     hours = time_diff % 60
    #     time_str = ""
    #     if hours >

    @commands.command(name='throne_round_start', aliases=['trs', 'new_throne_round', 'ntr'])
    @commands.has_permissions(manage_roles=True)
    async def _throne_round_start(self, ctx):
        round_number = 0
        if str(ctx.guild.id) in self.current_rounds:
            round_number = self.current_rounds[str(ctx.guild.id)].round_number
            if self.current_rounds[str(ctx.guild.id)].active == True:
                return await ctx.send("There is already an active round!")
        round_number += 1
        self._load_thing_list(ctx.guild.id)
        r_thing_id = random.randint(0, len(self.throne_config[str(ctx.guild.id)]["things"].keys()))
        self.throne_config[str(ctx.guild.id)]["thing_assignments"][str(self.bot.user.id)] = str(r_thing_id)
        first_thing = self.throne_config[str(ctx.guild.id)]["things"][str(r_thing_id)]
        self.throne_config[str(ctx.guild.id)]["crown_wearer_id"] = self.bot.user.id
        self.throne_config[str(ctx.guild.id)]["scores"][str(round_number)] = {}

        start_time = int(time.time())
        game_length = self.throne_config[str(ctx.guild.id)].setdefault('round_length', 1)
        end_time = start_time + (float(game_length) * 60 * 60)
        self.throne_config[str(ctx.guild.id)]["last_claim_time"] = \
            start_time - int(self.throne_config[str(ctx.guild.id)]["cooldown_seconds"])
        self.bot.logger.info(f"Starting new round at {start_time} until {end_time} ({end_time - start_time} "
                             f"total seconds). Round number {round_number}")

        self.current_rounds[str(ctx.guild.id)] = ThroneRoundTable.create(round_number=round_number,
                                                                    start_time=start_time,
                                                                    end_time=end_time,
                                                                    active=True,
                                                                    guild_id=ctx.guild.id)
        self.bot.tasks.append(self.bot.event_loop.create_task(self.check_round_loop(ctx.guild.id)))

        game_channel = self.bot.get_channel(self.throne_config[str(ctx.guild.id)]["game_channel_id"])
        claim_msg = f'Find "{first_thing}" to claim the throne from King Clippy'
        await ctx.guild.me.edit(nick="King Clippy")
        await game_channel.send(f"Starting new round! This round will run for {game_length} hours!")
        await game_channel.send(claim_msg)
        if ctx.guild.id != 802333887258296403:
            await game_channel.edit(topic=claim_msg)

    @commands.command(name="claim_throne", aliases=["claim", "claim_it"])
    @commands.cooldown(rate=1, per=20, type=BucketType.user)
    async def _claim_throne(self, ctx):
        if str(ctx.guild.id) not in self.current_rounds.keys():
            return await ctx.send("The Throne Game has not been configured on this server yet")
        if self.current_rounds[str(ctx.guild.id)].active == False:
            return await ctx.send("The Throne Game is not active right now.")
        self._ensure_default_config(ctx.guild)
        game_channel_id = self.throne_config[str(ctx.guild.id)]["game_channel_id"]
        if str(ctx.channel.id) != str(game_channel_id):
            return await ctx.message.delete()
        game_channel = self.bot.get_channel(self.throne_config[str(ctx.guild.id)]['game_channel_id'])
        previous_crown_holder_id = self.throne_config[str(ctx.guild.id)]["crown_wearer_id"]
        if previous_crown_holder_id == ctx.author.id:
            return await ctx.send(f"{ctx.author.mention} you already sit upon the throne!")
        previous_crown_holder = ctx.guild.get_member(previous_crown_holder_id)
        last_claim_time = self.throne_config[str(ctx.guild.id)]["last_claim_time"]
        message_end = "!"
        cooldown_seconds = float(self.throne_config[str(ctx.guild.id)]["cooldown_seconds"])
        if datetime.utcnow().timestamp() - last_claim_time > cooldown_seconds:
            self.throne_config[str(ctx.guild.id)]["crown_wearer_id"] = ctx.author.id
            self.throne_config[str(ctx.guild.id)]["last_claim_time"] = datetime.utcnow().timestamp()
            round_number = self.current_rounds[str(ctx.guild.id)].round_number
            if str(round_number) not in self.throne_config[str(ctx.guild.id)]["scores"]:
                self.throne_config[str(ctx.guild.id)]["scores"][str(round_number)] = {}
            if str(ctx.author.id) not in self.throne_config[str(ctx.guild.id)]["scores"][str(round_number)]:
                self.throne_config[str(ctx.guild.id)]["scores"][str(round_number)][str(ctx.author.id)] = 0
            self.throne_config[str(ctx.guild.id)]["scores"][str(round_number)][str(ctx.author.id)] += 1
            claimant_score = self.throne_config[str(ctx.guild.id)]["scores"][str(round_number)][str(ctx.author.id)]
            if previous_crown_holder:
                message_end = f" from {previous_crown_holder.mention}! "
            throne_role_id = self.throne_config[str(ctx.guild.id)]["throne_role_id"]
            throne_role = ctx.guild.get_role(throne_role_id)
            await ctx.author.add_roles(throne_role)
            try:
                await previous_crown_holder.remove_roles(throne_role)
            except Exception as e:
                self.bot.logger.warning(f"Failed to remove throne role: {e}")

            suffix = "th"
            if 10 < claimant_score < 20:
                suffix = "th"
            elif claimant_score % 10 == 1:
                suffix = "st"
            elif claimant_score % 10 == 2:
                suffix = "nd"
            elif claimant_score % 10 == 3:
                suffix = "rd"
            await game_channel.send(f"{ctx.author.mention} has claimed the throne{message_end}"
                                    f"All Hail {ctx.author.mention} the {claimant_score}{suffix}!")
            person_thing = self._get_person_thing(ctx.guild.id, ctx.author.id)
            claim_msg = f'\nFind "{person_thing}" to claim the throne from **{ctx.author.display_name}**!'
            await game_channel.send(claim_msg)
            if ctx.guild.id != 802333887258296403:
                await game_channel.edit(topic=claim_msg)
        else:
            if previous_crown_holder:
                message_end = f". Allow {previous_crown_holder.mention} their {round(cooldown_seconds / 60)} " \
                              f"minutes of fame!"
            await ctx.send(f"The throne can not yet be claimed{message_end}")
        self.save_throne_config()

    @commands.command(name="how_to_claim", aliases=['halp_claim', 'claim_halp'])
    async def _how_to_claim(self, ctx):
        crown_holder_id = self.throne_config[str(ctx.guild.id)]["crown_wearer_id"]
        crown_holder = ctx.guild.get_member(crown_holder_id)
        if str(crown_holder_id) in self.throne_config[str(ctx.guild.id)]["thing_assignments"]:
            thing_id = self.throne_config[str(ctx.guild.id)]["thing_assignments"][str(crown_holder_id)]
            thing = self.throne_config[str(ctx.guild.id)]["things"][str(thing_id)]
            await ctx.send(f'\nFind "{thing}" to claim the throne from **{crown_holder.display_name}**!')
        else:
            await ctx.send(f"\nNo one has told me how you can claim the throne from **{crown_holder.display_name}**!")

    def _get_person_thing(self, guild_id, member_id):
        roll_new = True
        if member_id != self.bot.user.id and \
                str(member_id) in self.throne_config[str(guild_id)]["thing_assignments"]:
            roll_new_threshold = self.throne_config[str(guild_id)].setdefault("roll_new_threshold", .4)
            dice_roll = random.random()
            self.bot.logger.info(f"_get_person_thing: {roll_new_threshold * 100}% chance. roll of {dice_roll}: {dice_roll > roll_new_threshold}")
            if dice_roll > roll_new_threshold:
                roll_new = False
        if roll_new:
            while True:
                r_thing_id = str(random.randint(0, len(self.throne_config[str(guild_id)]["things"].keys())-1))
                if r_thing_id not in self.throne_config[str(guild_id)]["thing_assignments"].values():
                    break
            self.throne_config[str(guild_id)]["thing_assignments"][str(member_id)] = r_thing_id
        thing_id = self.throne_config[str(guild_id)]["thing_assignments"][str(member_id)]
        return self.throne_config[str(guild_id)]["things"][str(thing_id)]

    async def check_round_loop(self, guild_id):
        while not self.bot.is_closed():
            round_end = self.current_rounds[str(guild_id)].end_time
            current_time = time.time()
            time_diff = round_end - current_time
            self.bot.logger.info(f"time diff: {time_diff}, abs < 60: {abs(time_diff) < 60}")
            if abs(time_diff) < 60 or time_diff < 0:
                await self._end_round(guild_id)
                break
            self.bot.logger.info(f"guild {guild_id}, equals: {str(guild_id) == str(802333887258296403)}")
            try:
                last_claim_time = float(self.throne_config[str(guild_id)]["last_claim_time"])
                seize_delay_minutes = float(self.throne_config[str(guild_id)].get("seize_delay_minutes", 60))
                time_since_last_claim = datetime.utcnow().timestamp() - last_claim_time
                if time_since_last_claim > seize_delay_minutes * 60:
                    await self.check_clippy_seize(guild_id)
                    new_sleep_time = (seize_delay_minutes * 60)
                else:
                    new_sleep_time = seize_delay_minutes * 60 - time_since_last_claim
                self.bot.logger.info(f"last claim: {last_claim_time}, delay minutes: {seize_delay_minutes}, "
                                     f"time since last: {time_since_last_claim}, new sleep time: {new_sleep_time}")
                sleep_time = min(time_diff / 2, new_sleep_time)
            except Exception as e:
                self.bot.logger.info(f"failed: {e}")
                sleep_time = time_diff / 2
            self.bot.logger.info(f"Throne Game loop check, sleeping for {sleep_time} seconds")
            await asyncio.sleep(sleep_time)
            continue
"""@game of thrones, clippy has taken advantage of the stagnation of the crown to unite the peasants and stage a coup. All hail King Clippy. Find X to restore your rightful claim to the throne"""


def setup(bot):
    bot.add_cog(ThroneGame(bot))
