import json
import re

import discord
from discord.ext import commands
from discord.ext.commands import CommandError, BadArgument
from peewee import JOIN

from clippy import utils
from clippy.exts.db.clippy_db import ProfileTable, ClippyDB, ContestTable, StatsTable, StatsProfileInstance


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.listen_channels = [727982492035842070, 728735968248463421, 767797600321011732]
        self.info_types = ["reviews", "agreements", "accepted", "rejected", "duplicate", "other", "upgrades_redeemed"]
        self.bot_channel_id = 727982492035842070

    @commands.command(name='update_old')
    async def _update_old(self, ctx, *, info):
        """Updates the stats on your review profile (the hard way)

           Usage: `!update <reviews> <agreements> <accepted> <rejected> <duplicate> <other>`
           Must include all 6 required counts for this to work.
           (don't include the < > when running the command)"""
        if ctx.channel.type != discord.ChannelType.private and ctx.channel.id not in self.listen_channels:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
        f_msg = f"Must include all 6 of these required values:\n**{'**, **'.join(self.info_types)}**."
        info = re.split(r',*\s+', info)
        __, __ = ProfileTable.get_or_create(user_id=ctx.author.id)
        if len(info) == 6:
            for i in info:
                if not i.isdigit():
                    f_msg = f"Please provide only integer values. {i} is not a valid integer."
                    return await utils.fail_out(ctx, self.bot.failed_react, f_msg, 10)
            ClippyDB._db.execute_sql("insert into StatsTable "
                                     "(user_id, date_submitted, reviews, agreements, accepted, rejected, duplicate, "
                                     "other) values "
                                     f"({ctx.author.id}, {round(ctx.message.created_at.timestamp())}, "
                                     f"{info[0]}, {info[1]}, {info[2]}, {info[3]}, {info[4]}, {info[5]}) ")
            await ctx.message.add_reaction(self.bot.success_react)
            return await ctx.invoke(self.bot.get_command('profile'))
        else:
            return await utils.fail_out(ctx, self.bot.failed_react, f_msg, 10)

    @commands.command(name='update')
    async def _update(self, ctx, *, info):
        """
        Updates the Wayfarer stats on your !profile.
        In order to use this command, please install the Wayfarer+ browser plugin
        Then navigate to the Profile page in Wayfarer, click "Copy rating stats to clipboard"
        and paste in that data after the !update command.
        """
        user_id = None
        if ctx.author:
            user_id = ctx.author.id
        if not user_id:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("Something went wrong, please contact mod for help.", delete_after=20)
        try:
            data = json.loads(info)
            profile, __ = ProfileTable.get_or_create(user_id=user_id)
            ClippyDB._db.execute_sql("insert into StatsTable "
                                     "(user_id, date_submitted, reviews, agreements, accepted, rejected, duplicate, "
                                     "other, upgrades_available, upgrades_redeemed, current_progress, extended_type, "
                                     "rating) values "
                                     f"({user_id}, {round(ctx.message.created_at.timestamp())}, "
                                     f"{data['total_nominations']}, {data['total_agreements']}, "
                                     f"{data['accepted']}, {data['rejected']}, {data['duplicates']},"
                                     f"{data['other']}, {data['upgrades_available']},  {data['upgrades_redeemed']},"
                                     f"{data['current_progress']}, \"{data['extended_type']}\", "
                                     f"\"{data['current_rating']}\")")
            if data['extended_type'] == "facts":
                if not profile.badge_count or profile.badge_count == 0:
                    await ctx.send("Your stats update has a counting type of '**Facts Only**' but you have not "
                                   "set a badge count on your profile. It's recommended that you do "
                                   "`!set_badge_count` with the count shown on your Ingress or Pokemon Go "
                                   "badge to make sure your profile is correct.")
            else:
                if int(data['other']) < 0:
                    await ctx.send("Your '**Other Agreements**' count is negative. This typically means that you "
                                   "need to change the Wayfarer+ '**Extended stat**' setting to '**Facts Only**'.")
            print(profile.badge_count)
            await ctx.message.add_reaction(self.bot.success_react)
            return await ctx.invoke(self.bot.get_command('profile'))
        except Exception as e:
            await ctx.message.add_reaction(self.bot.failed_react)
            return await ctx.send("In order to use this command, please install the Wayfarer+ browser plugin\n"
                                  "Then navigate to the Profile page in Wayfarer, click "
                                  "'Copy rating stats to clipboard' "
                                  "and paste in that data after the !update command.")

    @commands.command(name='set_badge_count', aliases=['setbc'])
    async def _set_badge_count(self, ctx, count):
        """
        Do '!set_badge_count number' with the number shown on your Ingress or Pokemon Go Wayfarer review badge
        to set the total number of earned agreements. This is only needed if you use the "Facts Only" setting in
        Wayfarer+. Also works with '!setbc'
        """
        __, __ = ProfileTable.get_or_create(user_id=ctx.author.id)
        ClippyDB._db.execute_sql("update ProfileTable set "
                                 f"badge_count={count} "
                                 f"where user_id = {ctx.author.id}")
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name='friendcode', aliases=['fc'])
    async def _friendcode(self, ctx, *, text=''):
        user = ctx.message.author
        new_code = "NULL"
        if len(text) != 0:
            new_code = text.replace(' ', '')
            if not new_code.isdigit() or len(new_code) != 12:
                f_msg = 'Must include exactly 12 digits representing a Friend Code. Or nothing to clear your code.'
                return await utils.fail_out(ctx, self.bot.failed_react, f_msg, 15)
        __, __ = ProfileTable.get_or_create(user_id=user.id)
        ClippyDB._db.execute_sql(f"update ProfileTable set friendcode={new_code} "
                                 f"where user_id = {user.id}")
        await ctx.message.add_reaction(self.bot.success_react)
        return await ctx.invoke(self.bot.get_command('profile'))
        pass

    @commands.command(name='profile')
    async def _profile(self, ctx, user: discord.Member = None):
        """Displays a user's profile. Don't include a name to view your own.
           Usage: `!profile [user]`
           (don't include the [ ] when running the command. Use just the command to view your own profile."""
        if user and user == self.bot.user:

            profile_embed = discord.Embed(colour=discord.Colour.from_rgb(252, 71, 19))
            help_channel = ctx.guild.get_channel(self.bot_channel_id)
            help_channel_txt = "#clippys-corner"
            if help_channel:
                help_channel_txt = help_channel.mention
            profile_embed.description = ("Hi, I'm Clippy! To learn about the things I can do, head over to "
                                         f"{help_channel_txt} and use the `!help` command.")
        else:
            if not user:
                user = ctx.message.author
            __, __ = ProfileTable.get_or_create(user_id=user.id)
            results = (ProfileTable.select(
                ProfileTable.user_id,
                ProfileTable.badge_count,
                ProfileTable.friendcode,
                ProfileTable.first_saturdays,
                ProfileTable.review_contests,
                StatsTable.date_submitted,
                StatsTable.reviews,
                StatsTable.agreements,
                StatsTable.accepted,
                StatsTable.rejected,
                StatsTable.duplicate,
                StatsTable.other,
                StatsTable.upgrades_available,
                StatsTable.upgrades_redeemed,
                StatsTable.current_progress,
                StatsTable.extended_type,
                StatsTable.rating
            )
                          .join(StatsTable, join_type=JOIN.LEFT_OUTER, on=(ProfileTable.user_id == StatsTable.user_id))
                          .where(ProfileTable.user_id == user.id)
                          .order_by(StatsTable.date_submitted.desc())
                          .limit(1)
                          )
            stats_profile = results.objects(StatsProfileInstance)
            stats_profile = stats_profile[0]

            profile_color = discord.Colour.from_rgb(255, 162, 48)
            if stats_profile.reviews:
                if stats_profile.rating:
                    if stats_profile.rating.lower() == "great":
                        profile_color = discord.Colour.from_rgb(43, 214, 46)
                    elif stats_profile.rating.lower() == "good":
                        profile_color = discord.Colour.from_rgb(255, 255, 48)
                    elif stats_profile.rating.lower() == "poor":
                        profile_color = discord.Colour.from_rgb(252, 71, 19)

                progress_str = ""
                if stats_profile.current_progress:
                    progress_str = f" (Progress **{stats_profile.current_progress}%**)"

                agreements = stats_profile.agreements
                other = stats_profile.other
                if stats_profile.badge_count and stats_profile.extended_type:
                    if stats_profile.extended_type == "facts":
                        other = stats_profile.badge_count - stats_profile.agreements
                        agreements = stats_profile.badge_count

                if stats_profile.reviews < 1:
                    percent = 0
                else:
                    percent = round((agreements / stats_profile.reviews) * 100, 1)

                upgrade_str = ""
                if stats_profile.upgrades_redeemed:
                    upgrade_str = f"\nUpgrades Redeemed: ** {stats_profile.upgrades_redeemed} ** {progress_str}"

                profile_msg = f"Total reviews: **{stats_profile.reviews}**\nApprox. Agreements: **{agreements}** (**{percent}%**)\n " \
                              f"**{stats_profile.accepted}** Accepted, **{stats_profile.rejected}** Rejected, " \
                              f"**{stats_profile.duplicate}** Duplicated\nOther Agreements: **{other}**" \
                              f"{upgrade_str}"
            else:
                profile_msg = ("To fill in your review stats, please install the Wayfarer+ browser plugin.\n "
                               "Then navigate to the Profile page in Wayfarer, click "
                               "'Copy rating stats to clipboard' "
                               "and paste in that data after the !update command.")

            profile_embed = discord.Embed(colour=profile_color)

            if stats_profile.review_contests:
                if stats_profile.review_contests > 0:
                    profile_msg += f"\nServer Review Contests: {stats_profile.review_contests}"
            profile_embed.add_field(name="Wayfarer",
                                    value=profile_msg,
                                    inline=False)

            if stats_profile.friendcode:
                profile_embed.add_field(name="Pokemon Go",
                                        value=f'\nFriend Code: {stats_profile.friendcode}',
                                        inline=False)

            if stats_profile.first_saturdays:
                if stats_profile.first_saturdays > 0:
                    profile_embed.add_field(name="Ingress",
                                            value=f'\nFirst Saturdays: {stats_profile.first_saturdays}',
                                            inline=False)
            contest_wins = (ContestTable.select(
                ContestTable.user_id,
                ContestTable.contest_name,
                ContestTable.win_title)
                            .where(ContestTable.user_id == user.id)
                            )
            if len(contest_wins) > 0:
                contest_text = ""
                for w in contest_wins:
                    contest_text += f"**{w.contest_name}**\n{w.win_title}\n\n"
                profile_embed.add_field(name="🏆 Contests 🏆",
                                        value=contest_text,
                                        inline=False)

        profile_embed.set_thumbnail(url=user.avatar_url)
        return await ctx.send(embed=profile_embed)

    @commands.command(name='contest_winner', aliases=['cw'])
    @commands.has_permissions(manage_roles=True)
    async def contest_winner(self, ctx, *, info):
        info = re.split(r',\s+', info)
        if len(info) != 3:
            return await ctx.send("Must provide a winner, contest name, and title won")
        winner, contest_name, win_title = info[0].strip(), info[1].strip(), info[2].strip()

        converter = commands.MemberConverter()
        try:
            member = await converter.convert(ctx, winner)
        except (CommandError, BadArgument):
            return await ctx.send(f"Could not find a member of the server matching {winner}")
        winner_id = member.id

        __, __ = ProfileTable.get_or_create(user_id=winner_id)
        ContestTable.create(user_id=winner_id, contest_name=contest_name, win_title=win_title)
        await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name='set_ifs', aliases=['sifs'])
    @commands.has_permissions(manage_roles=True)
    async def set_ifs(self, ctx, *, info):
        info = re.split(r',\s+', info)
        if len(info) != 2:
            return await ctx.message.add_reaction(self.bot.failed_react)
        winner, count = info[0].strip(), info[1].strip()

        converter = commands.MemberConverter()
        try:
            member = await converter.convert(ctx, winner)
        except (CommandError, BadArgument):
            return await ctx.send(f"Could not find a member of the server matching {winner}")

        __, __ = ProfileTable.get_or_create(user_id=member.id)
        updated = ProfileTable.update(first_saturdays=count).where(ProfileTable.user_id == member.id).execute()
        if updated == 1:
            await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(name='set_review_contests', aliases=['src'])
    @commands.has_permissions(manage_roles=True)
    async def set_review_contests(self, ctx, *, info):
        info = re.split(r',\s+', info)
        if len(info) != 2:
            return await ctx.message.add_reaction(self.bot.failed_react)
        winner, count = info[0].strip(), info[1].strip()

        converter = commands.MemberConverter()
        try:
            member = await converter.convert(ctx, winner)
        except (CommandError, BadArgument):
            return await ctx.send(f"Could not find a member of the server matching {winner}")

        __, __ = ProfileTable.get_or_create(user_id=member.id)
        updated = ProfileTable.update(review_contests=count).where(ProfileTable.user_id == member.id).execute()
        if updated == 1:
            await ctx.message.add_reaction(self.bot.success_react)


def setup(bot):
    bot.add_cog(Profile(bot))
