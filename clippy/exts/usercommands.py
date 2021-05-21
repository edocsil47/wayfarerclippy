import asyncio
import random
import re
import time
from datetime import datetime, timezone

import discord
import os
import qrcode
from discord.ext import commands
from discord.ext.commands import BadArgument, CommandError
from spongemock import spongemock

from clippy import utils
from clippy.exts.db.clippy_db import ProfileTable


class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cutoff_time = "15:00"
        self.sync_time = "17:50"

    @commands.command(name='get_cutoff_sync_times', aliases=['time', 'cutoff', 'sync'])
    async def get_cutoff_sync_times(self, ctx):
        """Displays the time remaining until the next daily cut-off and sync
           Usage: `!cutoff` Aliases: cutoff, time, sync"""
        current_date = datetime.utcfromtimestamp(time.time())
        cutoff_time = datetime.strptime(self.cutoff_time, '%H:%M')
        cutoff_date = datetime.utcfromtimestamp(time.time())\
            .replace(hour=cutoff_time.hour, minute=cutoff_time.minute, second=0, microsecond=0)
        sync_time = datetime.strptime(self.sync_time, '%H:%M')
        sync_date = datetime.utcfromtimestamp(time.time())\
            .replace(hour=sync_time.hour, minute=sync_time.minute, second=0, microsecond=0)
        if cutoff_date < current_date:
            cutoff_date = cutoff_date.replace(day=cutoff_date.day+1)
        if sync_date < current_date:
            sync_date = sync_date.replace(day=sync_date.day+1)
        time_until_cutoff = self._format_time_diff(cutoff_date, current_date)
        time_until_sync = self._format_time_diff(sync_date, current_date)
        return await ctx.send("Times are approximate and occasionally are delayed.\n"
                              f"Time until next Pokemon Go sync: {time_until_sync}\n"
                              f"Time until next vote/sync cutoff: {time_until_cutoff}\n"
                              f"(cutoff time seems to have moved a lot closer to sync time so the time listed "
                              f"above may be incorrect)\n\n")

    @staticmethod
    def _format_time_diff(future_time, current_time):
        time_diff = future_time - current_time
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours < 2:
            if hours == 1:
                hour_string = f"{hours} hour "
            else:
                hour_string = ""
        else:
            hour_string = f"{hours} hours "
        if seconds > 30:
            minutes += 1
        if minutes == 1:
            minute_string = f"{minutes:02} minute"
        else:
            minute_string = f"{minutes:02} minutes"
        return f"**{hour_string}{minute_string}**"

    @commands.command(name='privacy_statement', aliases=['gdpr', 'privacy'])
    async def _privacy_statement(self, ctx):
        """
        Do '!privacy_statement' to read information about what info Clippy stores and how it's used.
        Also works with '!gdpr' and '!privacy'
        """
        text = self.bot.privacy_statement
        embed = discord.Embed(colour=discord.Colour.dark_blue(),
                              title="Privacy Statement",
                              description=text)
        return await ctx.message.channel.send(embed=embed)

    @commands.command(name='spongebob', aliases=['sb', 'mock', 'bob'])
    async def _spongebob(self, ctx, *, text):
        """
        Do '!spongebob text' with any text to bobify the text
        Also works with '!sb' and '!mock'
        """
        return await self._send_by_webhook(ctx, spongemock.mock(text))

    async def _send_by_webhook(self, ctx, message):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
        webhooks = await ctx.channel.webhooks()
        if len(webhooks) < 1:
            webhook = await ctx.channel.create_webhook(name="Clippy")
        else:
            webhook = webhooks[0]
        message = discord.utils.escape_mentions(message)
        # message = message.replace('@here', f'@{self.bot.empty_str}here')
        # message = message.replace('@everyone', f'@{self.bot.empty_str}everyone')
        # message = message.replace('@&', f'@{self.bot.empty_str}&')
        self.bot.logger.info(f"{ctx.author.name} sent '{message}' as '{ctx.author.display_name}'")
        await webhook.send(content=message, username=ctx.author.display_name,
                           avatar_url=ctx.author.avatar_url)

    @commands.command(name='waspcup', aliases=['wasp', 'wc'])
    async def _waspcup(self, ctx):
        message = f"{utils.waspcup_gen()}\n{utils.waspcup_gen()}"
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
        webhooks = await ctx.channel.webhooks()
        if len(webhooks) < 1:
            webhook = await ctx.channel.create_webhook(name="Clippy")
        else:
            webhook = webhooks[0]
        await webhook.send(content=message, username="Clippy",
                           avatar_url="https://cdn.discordapp.com/attachments/809841343282020382/824071032306270248/Wasp_Cup_Clippy.png")

    @commands.command(name='copy_connect_four', aliases=['cc4'])
    async def _copy_connect_four(self, ctx, message_id):
        target_message = await ctx.channel.fetch_message(message_id)
        await ctx.message.delete()
        if not target_message:
            return
        raw_message = target_message.clean_content.replace('⚪', ':white_circle:')
        raw_message = raw_message.replace('🟡', ':yellow_circle:')
        raw_message = raw_message.replace('🔴', ':red_circle:')
        raw_message = f"```{raw_message}```"
        raw_sent = await ctx.send(raw_message)
        await asyncio.sleep(15)
        await raw_sent.delete()

    @commands.command(name='qrcode', aliases=['qr', 'qrc'])
    async def _qrcode(self, ctx, *, text):
        """
        Do '!qrcode' followed by your 12 digit Pokemon Go friend code to generate a QR code that others can scan
        to send you a friend request. Also works with '!qr' and '!qrc'
        """
        friend_code = None
        converter = commands.MemberConverter()
        user = ctx.author
        try:
            member = await converter.convert(ctx, text)
        except (CommandError, BadArgument):
            member = None
        if member:
            user_stats, __ = ProfileTable.get_or_create(user_id=member.id)
            if user_stats.friendcode:
                friend_code = user_stats.friendcode
                user = member
        else:
            friend_code = text.replace(' ', '')
            if not friend_code.isdigit() or len(friend_code) != 12:
                f_msg = 'Must include exactly 12 digits representing a Friend Code.'
                return await utils.fail_out(ctx, self.bot.failed_react, f_msg, 15)
        if friend_code:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(friend_code)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            filename = f'qrcode_{friend_code}.png'
            img.save(os.path.join('data', filename))
            msg_content = f"{user.display_name}'s Friend Code:"
            with open(os.path.join('data', filename), 'rb') as imgfile:
                await ctx.channel.send(content=msg_content,
                                       file=discord.File(imgfile, filename=filename))
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
        else:
            f_msg = "Could not find the person you're looking for or they haven't set their code."
            return await utils.fail_out(ctx, self.bot.failed_react, f_msg, 15)

    @commands.command(name='ñ', aliases=['l', 'n'])
    async def _ñify(self, ctx, *, text):
        """
        Do '!ñ text' with any text to replace all occurrences of letter l with ñ. Don't ask why.
        Also works with '!l' and '!n'
        """
        text = text.replace('l', 'ñ')
        text = text.replace('L', 'Ñ')
        return await self._send_by_webhook(ctx, text)

    @commands.command(name='🔥')
    async def _flame(self, ctx):
        """Try it and see"""
        await ctx.message.channel.send("Ohhhh burn!")

    @commands.command(name='🥂')
    async def _cheers(self, ctx):
        """Try it and see"""
        await ctx.message.channel.send("Cheers!")

    @commands.command(name='set_nick', aliases=['sn'])
    @commands.has_permissions(manage_roles=True)
    async def _set_nick(self, ctx, *, info):
        info = re.split(r',\s+', info)
        if len(info) < 2:
            await ctx.message.add_reaction(self.bot.failed_react)
            return
        member_str = info[0].strip()
        converter = commands.MemberConverter()
        try:
            member = await converter.convert(ctx, member_str)
        except:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send(f'Could not find user "{member_str}".', delete_after=10)
        new_nick = ''.join(info[1:])
        try:
            await member.edit(nick=new_nick)
            return await ctx.message.add_reaction(self.bot.success_react)
        except discord.errors.Forbidden:
            return await ctx.send(f'{member.mention} must change their nick to "{new_nick}" ASAP!')


def setup(bot):
    bot.add_cog(UserCommands(bot))
