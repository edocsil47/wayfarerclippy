import asyncio
import datetime
import json
import pytz

import discord
from discord.ext import commands
import discord.permissions

from clippy import utils, checks
from clippy.exts.db.clippy_db import PermsTimerTable


class PermsTimerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timer_check_interval_minutes = 10
        self.upcoming_timers = {}
        self.role_option_list = [
            "All non-admins",
            "All roles below given role",
            "List of roles",
            "Single role"
        ]

    @commands.group(name='permstimer', aliases=['pt'], case_insensitive=True)
    @checks.serverowner_or_permissions(manage_messages=True)
    async def _permstimer(self, ctx):
        """Commands for Permission Timers"""
        if ctx.invoked_subcommand is None:
            raise commands.BadArgument()

    @_permstimer.command(aliases=['make', 'new'])
    async def _create(self, ctx):
        timer_name = await self._prompt_name(ctx)
        if not timer_name:
            return
        timer_time = await self._prompt_time(ctx)
        if not timer_time:
            return
        timer_roles = await self._prompt_roles(ctx)
        if not timer_roles:
            return
        timer_perms = await self._prompt_perms(ctx)
        if not timer_perms:
            return
        timer_config = {"roles_config": timer_roles, "perms_map": timer_perms}
        timer = PermsTimerTable.create(name=timer_name,
                                       time_utc=timer_time,
                                       finished=False,
                                       channel_id=ctx.channel.id,
                                       guild_id=ctx.guild.id,
                                       config=json.dumps(timer_config))
        now_seconds = (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()
        upcoming_seconds = now_seconds + ((self.timer_check_interval_minutes - 1) * 60)
        if timer_time < upcoming_seconds:
            if timer_name not in self.upcoming_timers:
                self.upcoming_timers[timer_name] = timer
                self.bot.event_loop.create_task(self.expiry_check(timer_name))

    async def _prompt_name(self, ctx):
        prompt = "Please provide a name for this timer"
        return await self._prompt_for_reply(ctx, prompt)

    async def _prompt_roles(self, ctx):
        prompt = "Which roles should this action be applied to?"
        role_set = await utils.ask_list(self.bot, prompt, ctx.channel, self.role_option_list,
                                        user_list=[ctx.message.author.id])
        if not role_set:
            return
        options_index = self.role_option_list.index(role_set)
        roles_config = {"options_index": options_index, "affected_roles": []}
        role_prompts = {1: "Provide the role below which this action will take affect",
                        2: "Provide a comma-separated list of role names or ids for which this action will take affect",
                        3: "Provide a role name or id for which this action will take affect"}
        if options_index == 0:
            return roles_config
        role_reply = await self._prompt_for_reply(ctx, role_prompts[options_index])
        affected_roles = []
        if options_index == 1:
            top_role = await self._try_get_role(ctx, role_reply)
            if not top_role:
                return None
            for role in ctx.guild.roles:
                if role < top_role:
                    affected_roles.append(role.id)
        elif options_index == 2:
            roles = role_reply.split(",")
            for role in roles:
                affected_role = await self._try_get_role(ctx, role)
                if not affected_role:
                    continue
                affected_roles.append(affected_role.id)

        elif options_index == 3:
            affected_role = await self._try_get_role(ctx, role_reply)
            if not affected_role:
                return None
            affected_roles.append(affected_role.id)
        roles_config["affected_roles"] = affected_roles
        return roles_config

    @staticmethod
    async def _try_get_role(ctx, role_str):
        converter = commands.RoleConverter()
        try:
            role = await converter.convert(ctx, role_str)
        except:
            role = None
        return role

    async def _prompt_time(self, ctx):
        prompt = "Please provide a datetime in the following format: 2020-01-01T12:00:00±0000"
        time_response = await self._prompt_for_reply(ctx, prompt)
        if not time_response:
            return None
        time_local = datetime.datetime.strptime(time_response, "%Y-%m-%dT%H:%M:%S%z")
        time_utc = time_local.astimezone(pytz.UTC)
        return (time_utc - pytz.utc.localize(datetime.datetime(1970, 1, 1))).total_seconds()

    async def _prompt_perms(self, ctx):
        perms_map = {'read_messages': None, 'send_messages': None}
        for perm in perms_map.keys():
            perms_map[perm] = await utils.ask_list(self.bot, f"True, False, or None for: {perm}?",
                                                   ctx.channel, ["True", "False", "None"],
                                                   user_list=[ctx.message.author.id])
        return perms_map

    async def _prompt_for_reply(self, ctx, prompt_text):
        while True:
            embed = discord.Embed(colour=discord.Colour.red(), description=prompt_text)
            query_msg = await ctx.channel.send(embed=embed)
            try:
                response = await self.bot.wait_for('message', timeout=20,
                                                   check=(lambda reply: reply.author == ctx.message.author))
            except asyncio.TimeoutError:
                await ctx.channel.send(embed=discord.Embed(colour=discord.Colour.light_grey(),
                                                           description="You took too long to reply."), delete_after=12)
                await query_msg.delete()
                return None
            if response.clean_content.lower() == "cancel":
                await query_msg.delete()
                await response.delete()
                return None
            return response.clean_content

    async def check_loop(self):
        while not self.bot.is_closed():
            now_seconds = (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()
            upcoming_seconds = now_seconds + ((self.timer_check_interval_minutes - 1) * 60)
            self.bot.logger.info("Checking for upcoming timers.")
            unfinished_timers = (PermsTimerTable.select(
                PermsTimerTable.permstimerid,
                PermsTimerTable.name,
                PermsTimerTable.time_utc,
                PermsTimerTable.finished,
                PermsTimerTable.channel_id,
                PermsTimerTable.guild_id,
                PermsTimerTable.config)
                                .where(PermsTimerTable.finished == 0))
            for t in unfinished_timers:
                if t.time_utc < upcoming_seconds:
                    if t.name not in self.upcoming_timers:
                        self.upcoming_timers[t.name] = t
                        self.bot.event_loop.create_task(self.expiry_check(t.name))
            await asyncio.sleep(self.timer_check_interval_minutes * 60)

    async def expiry_check(self, timer_name):
        timer = self.upcoming_timers[timer_name]
        while True:
            current = (datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds()
            if timer.time_utc < current - 1:
                await self._process_timer(timer)
                del self.upcoming_timers[timer_name]
                return self.set_timer_finished(timer)
            await asyncio.sleep((timer.time_utc - current)/2)

    async def _process_timer(self, timer):
        guild = self.bot.get_guild(timer.guild_id)
        if not guild:
            return self.bot.logger.warn(f"No guild found with id: {timer.guild_id}. Could not process timer commands.")
        channel = self.bot.get_channel(timer.channel_id)
        timer_config = json.loads(timer.config)
        affected_roles = timer_config["roles_config"]["affected_roles"]
        for role_id in affected_roles:
            role = guild.get_role(role_id)
            await channel.set_permissions(role,
                                          send_messages=self._get_perm_value_from_string(
                                              timer_config["perms_map"]["send_messages"]),
                                          read_messages=self._get_perm_value_from_string(
                                              timer_config["perms_map"]["read_messages"]))
            await channel.send(f"{role.name} can now view this channel")

    @staticmethod
    def _get_perm_value_from_string(value_str):
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False
        return None

    @staticmethod
    def set_timer_finished(timer):
        PermsTimerTable.update(finished=1).where(PermsTimerTable.permstimerid == timer.permstimerid).execute()


def setup(bot):
    bot.add_cog(PermsTimerCog(bot))
