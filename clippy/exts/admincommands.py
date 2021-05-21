import errno
import io
import json
import os
import pickle
import sys
import textwrap
import tempfile
import traceback

from contextlib import redirect_stdout

import discord
from discord.ext import commands

from clippy import checks, utils


class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.failed_react = '❌'
        self.success_react = '✅'

    async def cog_command_error(self, ctx, error):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            ctx.resolved = True
            return await ctx.send_help(ctx.command)

    @commands.command(hidden=True, name="eval")
    @checks.is_dev_or_owner()
    async def _eval(self, ctx, *, body: str):
        """Evaluates a code"""
        env = {
            'bot': ctx.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            'guild_dict': ctx.bot.guild_dict
        }

        def cleanup_code(content):
            """Automatically removes code blocks from the code."""
            # remove ```py\n```
            if content.startswith('```') and content.endswith('```'):
                return '\n'.join(content.split('\n')[1:-1])
            # remove `foo`
            return content.strip('` \n')

        env.update(globals())
        body = cleanup_code(body)
        stdout = io.StringIO()
        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'
        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')
        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass
            if ret is None:
                if value:
                    paginator = commands.Paginator(prefix='```py')
                    for line in textwrap.wrap(value, 80):
                        paginator.add_line(line.rstrip().replace('`', '\u200b`'))
                    for p in paginator.pages:
                        await ctx.send(p)
            else:
                ctx.bot._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

    @commands.command(name='save')
    @checks.is_owner()
    async def save_command(self, ctx):
        """Usage: `!save`
        Save persistent state to file, path is relative to current directory."""
        try:
            await self.save(ctx.guild.id)
            self.bot.logger.info('CONFIG SAVED')
            await ctx.message.add_reaction('✅')
        except Exception as err:
            await self._print(self.bot.owner, 'Error occurred while trying to save!')
            await self._print(self.bot.owner, err)

    async def save(self, guildid):
        try:
            with open('config.json', 'w') as fd:
                json.dump(self.bot.config, fd, indent=4)
        except Exception as e:
            self.bot.logger.error(f"Failed to save config. Error: {str(e)}")
        try:
            with tempfile.NamedTemporaryFile('wb', dir=os.path.dirname(os.path.join('data', 'serverdict')),
                                             delete=False) as tf:
                pickle.dump(self.bot.guild_dict, tf, 4)
                tempname = tf.name
            try:
                os.remove(os.path.join('data', 'serverdict_backup'))
            except OSError:
                pass
            try:
                os.rename(os.path.join('data', 'serverdict'), os.path.join('data', 'serverdict_backup'))
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
            os.rename(tempname, os.path.join('data', 'serverdict'))
        except Exception as e:
            self.bot.logger.error(f"Failed to save serverdict. Error: {str(e)}")
        try:
            rc_cog = self.bot.cogs.get('ReactCounter')
            rc_cog.save_react_counts()
        except:
            self.bot.logger.warning("Failed to save ReactCounter")
        try:
            wc_cog = self.bot.cogs.get('WordCounter')
            wc_cog.save_word_counts()
            wc_cog.save_react_lists()
        except:
            self.bot.logger.warning("Failed to save WordCounter")
        try:
            del_cog = self.bot.cogs.get('Deleter')
            del_cog.save_category_ids()
            del_cog.save_scores()
        except:
            self.bot.logger.warning("Failed to save Deleter")
        try:
            money_cog = self.bot.cogs.get('MoneyMoney')
            money_cog.save_scores()
        except:
            self.bot.logger.warning("Failed to save MoneyMoney")
        try:
            throne_cog = self.bot.cogs.get('ThroneGame')
            throne_cog.save_throne_config()
        except:
            self.bot.logger.warning("Failed to save ThroneGame")


    async def _print(self, owner, message):
        if 'launcher' in sys.argv[1:]:
            if 'debug' not in sys.argv[1:]:
                await owner.send(message)
        print(message)
        self.bot.logger.info(message)

    @commands.command()
    @checks.is_owner()
    async def abuse(self, ctx, *, message_to_send):
        guild = self.bot.get_guild(802333887258296403)
        source_channel = guild.get_channel(812106525467607090)
        ow = source_channel.overwrites
        category = await guild.create_category_channel(f"Derpy category", overwrites=ow)
        print(f"{category.name}")
        new_channel = await guild.create_text_channel("3-mar-þooþs-xiiv", category=category)
        print(f"{new_channel.name}")
        if not new_channel:
            return
        await new_channel.send(message_to_send)
        # me = ctx.guild.get_member(371387628093833216)
        # await channel_to_send.set_permissions(me, read_messages=True,
        #                                       send_messages=True)
        # await channel_to_send.send(message_to_send)

    @commands.command()
    @checks.is_owner()
    async def restart(self, ctx):
        """Usage: `!restart`
        Calls the save function and restarts Clippy."""
        try:
            await self.save(ctx.guild.id)
        except Exception as err:
            await self._print(self.bot.owner, 'Error occurred while trying to save!')
            await self._print(self.bot.owner, err)
        await ctx.channel.send('Restarting...')
        self.bot._shutdown_mode = 26
        await self.bot.logout()

    @commands.command()
    @checks.is_owner()
    async def exit(self, ctx):
        """Usage: `!exit`
        Calls the save function and shuts down the bot.
        **Note**: If running bot through docker, Clippy will likely restart."""
        try:
            await self.save(ctx.guild.id)
        except Exception as err:
            await self._print(self.bot.owner, 'Error occurred while trying to save!')
            await self._print(self.bot.owner, err)
        await ctx.channel.send('Shutting down...')
        self.bot._shutdown_mode = 0
        await self.bot.logout()

    @commands.command(name='load')
    @checks.is_owner()
    async def _load(self, ctx, *extensions):
        for ext in extensions:
            try:
                self.bot.load_extension(f"clippy.exts.{ext}")
            except Exception as e:
                error_title = '**Error when loading extension'
                await ctx.send(f'{error_title} {ext}:**\n'
                               f'{type(e).__name__}: {e}')
            else:
                await ctx.send('**Extension {ext} Loaded.**\n'.format(ext=ext))

    @commands.command(name='reload', aliases=['rl'])
    @checks.is_owner()
    async def _reload(self, ctx, *extensions):
        for ext in extensions:
            try:
                self.bot.reload_extension(f"clippy.exts.{ext}")
            except Exception as e:
                error_title = '**Error when reloading extension'
                await ctx.send(f'{error_title} {ext}:**\n'
                               f'{type(e).__name__}: {e}')
            else:
                await ctx.send('**Extension {ext} Reloaded.**\n'.format(ext=ext))

    @commands.command(name='unload')
    @checks.is_owner()
    async def _unload(self, ctx, *extensions):
        exts = [ex for ex in extensions if f"clippy.exts.{ex}" in self.bot.extensions]
        for ex in exts:
            self.bot.unload_extension(f"clippy.exts.{ex}")
        s = 's' if len(exts) > 1 else ''
        await ctx.send("**Extension{plural} {est} unloaded.**\n".format(plural=s, est=', '.join(exts)))


    def can_manage(self, user):
        if checks.is_user_dev_or_owner(self.bot.config, user.id):
            return True
        for role in user.roles:
            if role.permissions.manage_messages:
                return True
        return False

    @checks.serverowner_or_permissions(manage_messages=True)
    @commands.command(hidden=True, name='most_voted_comments', aliases=['mvc'])
    async def _most_voted_comments(self, ctx, channel_id: int, oldest_id: int):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
        channel = ctx.guild.get_channel(channel_id)
        thumb = self.bot.get_emoji(664648365644054538)
        if not channel:
            return
        messages = await channel.history(limit=123).flatten()
        message_votes = {}
        voted_messages = {}
        for message in messages:
            if message.id < oldest_id:
                break
            voted_messages[message.id] = message
            for r in message.reactions:
                if r.emoji == thumb:
                    message_votes[message.id] = r.count
                    continue
        votes_leads = sorted(message_votes.items(), key=lambda x: x[1], reverse=True)
        places = ["1st", "2nd", "3rd"]
        response = ""
        for i in range(3):
            winner = voted_messages[votes_leads[i][0]]
            response += f"{places[i]} place: {winner.author.display_name} with {votes_leads[i][1]} points\n"
        await ctx.send(response)

    @checks.serverowner_or_permissions(manage_guild=True)
    @commands.command(hidden=True, name='clippy_say', aliases=['csay'])
    async def _clippy_say(self, ctx, *, text):
        self.bot.logger.info(f"{ctx.author.name} used `clippy_say` to say: '{text}'")
        await ctx.message.delete()
        await ctx.channel.send(text)

    @checks.serverowner_or_permissions(manage_guild=True)
    @commands.command(hidden=True, name='upsidedown', aliases=['ud'])
    async def _upsidedown(self, ctx, *, text):
        await ctx.channel.send(utils.make_upsidedown(text))

    @checks.serverowner_or_permissions(manage_guild=True)
    @commands.command(hidden=True, name='readaudit', aliases=['ra'])
    async def _readaudit(self, ctx):
        async for entry in ctx.guild.audit_logs(limit=100):
            print(entry)


def setup(bot):
    bot.add_cog(AdminCommands(bot))
