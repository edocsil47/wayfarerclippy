import asyncio
import datetime
import sys

import discord

from clippy.bot import ClippyBot

from clippy.exts.db.clippy_db import *
ClippyDB.start('data/clippy.db')

Clippy = ClippyBot()
logger = Clippy.logger

guild_dict = Clippy.guild_dict
config = Clippy.config

event_loop = asyncio.get_event_loop()
Clippy.event_loop = event_loop


async def guild_cleanup(loop=True):
    while not Clippy.is_closed():
        logger.info('Server_Cleanup ------ BEGIN ------')
        guilddict_srvtemp = guild_dict
        dict_guild_list = []
        bot_guild_list = []
        dict_guild_delete = []
        guild_id = None
        for guildid in guilddict_srvtemp.keys():
            dict_guild_list.append(guildid)
        for guild in Clippy.guilds:
            bot_guild_list.append(guild.id)
            guild_id = guild.id
        guild_diff = set(dict_guild_list) - set(bot_guild_list)
        for s in guild_diff:
            dict_guild_delete.append(s)
        for s in dict_guild_delete:
            try:
                del guild_dict[s]
                logger.info(('Server_Cleanup - Cleared ' + str(s)) +
                            ' from save data')
            except KeyError:
                pass
        logger.info('Server_Cleanup - SAVING CHANGES')
        try:
            admin_commands_cog = Clippy.cogs.get('AdminCommands')
            if not admin_commands_cog:
                return None
            await admin_commands_cog.save(guild_id)
        except Exception as err:
            logger.info('Server_Cleanup - SAVING FAILED' + str(err))
        logger.info('Server_Cleanup ------ END ------')
        await asyncio.sleep(7200)
        continue


async def _print(owner, message):
    if 'launcher' in sys.argv[1:]:
        if 'debug' not in sys.argv[1:]:
            await owner.send(message)
    print(message)
    logger.info(message)


async def maint_start(bot):
    bot.tasks = []
    try:
        comments_scrape_cog = bot.get_cog("CommentScrapeCog")
        perms_timer_cog = bot.get_cog("PermsTimerCog")
        bot.tasks.append(event_loop.create_task(comments_scrape_cog.check_loop()))
        bot.tasks.append(event_loop.create_task(perms_timer_cog.check_loop()))
        throne_game_cog = bot.get_cog("ThroneGame")
        throne_game_cog.start_loop()
        logger.info('Maintenance Tasks Started')
    except KeyboardInterrupt:
        [task.cancel() for task in bot.tasks]

"""
Events
"""
@Clippy.event
async def on_ready():
    Clippy.owner = discord.utils.get(
        Clippy.get_all_members(), id=config['master'])
    if Clippy.initial_start:
        await _print(Clippy.owner, 'Starting up...')
    Clippy.uptime = datetime.datetime.now()
    owners = []
    guilds = len(Clippy.guilds)
    users = 0
    for guild in Clippy.guilds:
        users += guild.member_count
        try:
            if guild.id not in guild_dict:
                guild_dict[guild.id] = {'configure_dict': {}}
            else:
                guild_dict[guild.id].setdefault('configure_dict', {})
        except KeyError:
            guild_dict[guild.id] = {'configure_dict': {}}
        owners.append(guild.owner)
    if Clippy.initial_start:
        await _print(Clippy.owner, "{server_count} servers connected.\n{member_count} members found."
                     .format(server_count=guilds, member_count=users))
        Clippy.initial_start = False
        await maint_start(Clippy)
    else:
        logger.warn("bot failed to resume")


try:
    event_loop.run_until_complete(Clippy.start(config['bot_token']))
except discord.LoginFailure:
    logger.critical('Invalid token')
    event_loop.run_until_complete(Clippy.logout())
    Clippy._shutdown_mode = 0
except KeyboardInterrupt:
    logger.info('Keyboard interrupt detected. Quitting...')
    event_loop.run_until_complete(Clippy.logout())
    Clippy._shutdown_mode = 0
except Exception as e:
    logger.critical('Fatal exception', exc_info=e)
    event_loop.run_until_complete(Clippy.logout())
finally:
    pass
try:
    sys.exit(Clippy._shutdown_mode)
except AttributeError:
    sys.exit(0)
