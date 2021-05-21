import copy
import json
import os
import pickle
import random
import sys

from clippy.logs import init_loggers
from clippy.errors import custom_error_handling

import discord
from discord.ext import commands

default_exts = ['admincommands',
                'commentscrape',
                'deleter',
                'moneymoney',
                #'oldthronegame',
                'permstimer',
                'profile',
                'reactcounter',
                's2tools',
                'thronegame',
                'translate',
                'usercommands',
                'utilities',
                'wordcounter']


def _prefix_callable(bot, msg):
    user_id = bot.user.id
    base = [f'<@!{user_id}> ', f'<@{user_id}> ']
    if msg.guild is None:
        base.append('!')
    else:
        try:
            prefix = bot.guild_dict[msg.guild.id]['configure_dict']['settings']['prefix']
        except (KeyError, AttributeError):
            prefix = None
        if not prefix:
            prefix = bot.config['default_prefix']
        base.extend(prefix)
    return base


class ClippyBot(commands.AutoShardedBot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        #intents.presences = True
        super().__init__(command_prefix=_prefix_callable,
                         case_insensitive=True,
                         activity=discord.Game(name="Wayfarer"),
                         intents=intents)

        self.logger = init_loggers()
        custom_error_handling(self, self.logger)
        self.guild_dict = {'configure_dict': {}}
        self._load_data()
        self._load_config()
        self.success_react = '✅'
        self.failed_react = '❌'
        self.thumbsup_react = '👍'
        self.empty_str = '\u200b'
        self.check_delay_minutes = 5
        self.initial_start = True
        self.last_random = -1
        self.last_rainbow_random = -1
        self.privacy_statement = "Hi! I see you're interested to know what data I collect about you. I'm a bot that " \
                                 "monitors channels on this server for my name. I don't store any messages, I just " \
                                 "watch for fun words like 'oof' and 'bruh' and count who says them. " \
                                 "I also have certain commands that let you store data " \
                                 "about yourself on the server. These commands are for your Wayfarer profile. I " \
                                 "only store your username and the basic details you send me. No other data about " \
                                 "your use of the server is stored by me, and I don't sell your data to any third " \
                                 "parties. If you want to know what I know about you, use the !profile command! " \
                                 "If you don't like me storing your data, just message **tehstone** " \
                                 "and he'll remove it for you!"""

        for ext in default_exts:
            try:
                self.load_extension(f"clippy.exts.{ext}")
            except Exception as e:
                print(f'**Error when loading extension {ext}:**\n{type(e).__name__}: {e}')
            else:
                if 'debug' in sys.argv[1:]:
                    print(f'Loaded {ext} extension.')

    class RenameUnpickler(pickle.Unpickler):
        def find_class(self, module, name):
            return super().find_class(module, name)

    def _load_data(self):
        try:
            with open(os.path.join('data', 'serverdict'), 'rb') as fd:
                self.guild_dict = self.RenameUnpickler(fd).load()
            self.logger.info('Serverdict Loaded Successfully')
        except OSError:
            self.logger.info('Serverdict Not Found - Looking for Backup')
            try:
                with open(os.path.join('data', 'serverdict_backup'), 'rb') as fd:
                    self.guild_dict = self.RenameUnpickler(fd).load()
                self.logger.info('Serverdict Backup Loaded Successfully')
            except OSError:
                self.logger.info('Serverdict Backup Not Found - Creating New Serverdict')
                self.guild_dict = {}
                with open(os.path.join('data', 'serverdict'), 'wb') as fd:
                    pickle.dump(self.guild_dict, fd, -1)
                self.logger.info('Serverdict Created')

    def _load_config(self):
        # Load configuration
        with open('config.json', 'r') as fd:
            self.config = json.load(fd)

    async def on_message(self, message):
        if message.type == discord.MessageType.pins_add and message.author == self.user:
            return await message.delete()
        # try:
        #     prefix = self.guild_dict[message.guild.id]['configure_dict']['settings']['prefix']
        # except (KeyError, AttributeError):
        #     prefix = self.config['default_prefix']
        prefix = "&"
        if not message.author.bot:
            if self.user.mentioned_in(message) and not message.mention_everyone \
                    and not message.clean_content.startswith(prefix):
                if message.clean_content.startswith('?catch'):
                    return await message.channel.send("You can't train me! You don't have enough badges!")
                if self._check_thumb(message.clean_content):
                    await self._send_with_image(message.channel, 'ThumbMaskot.png',
                                                "I'm sorry, Clippy is out right now. How can Thumby help?")
                if self._check_words(["play", "game"], message.clean_content.lower()):
                    embed = discord.Embed(colour=discord.Colour.green(),
                                          title="Would you like to play a game?",
                                          url="https://www.decisionproblem.com/paperclips/")
                    await message.channel.send(embed=embed)
                elif self._check_words(["gdpr", "privacy"], message.clean_content.lower()):
                    text = self.privacy_statement
                    embed = discord.Embed(colour=discord.Colour.dark_blue(),
                                          title="Privacy Statement",
                                          description=text)
                    await message.channel.send(embed=embed)
                elif self._check_words(['pronoun'], message.clean_content.lower()):
                    await self._send_with_image(message.channel, 'microsoft-clippy-orange.png',
                                                "Thanks for asking! I prefer clip/clips")
                elif self._check_words(["gym"],
                                       message.clean_content.lower()):
                    await self._send_with_image(message.channel, 'microsoft-clippy-orange.png',
                                                "Have you tried restarting?")
                elif self._check_words(['fortress', 'greenhouse', 'inn', 'hpwu', 'wizard'],
                                       message.clean_content.lower()):
                    await self._send_with_image(message.channel, 'wizard-clippy-orange.png', "¯\_(ツ)_/¯")
                elif self._check_words(['lunar', 'moon'],
                                       message.clean_content.lower()):
                    await self._send_with_image(message.channel, 'space-clip.png', "I am unable to confirm or deny "
                                                                                   "the existence of a Lunar Intel map.")
                elif self._check_words(["ama"], message.clean_content.lower()):
                    await self._send_with_image(message.channel, 'microsoft-clippy-orange.png',
                                                "AMAs are not the answer!")
                else:
                    rainbow_roll = 14 == random.randint(1, 22)
                    if rainbow_roll:
                        await self._send_with_image(message.channel, 'rainbow_clippy_small.png',
                                                    self._get_random_message(True))
                    else:
                        if self._check_words(["french", "france", "spicy", "sexy"], message.clean_content.lower()):
                            chance = random.randint(1, 5)
                        else:
                            chance = random.randint(1, 16)
                        self.logger.info(f"random number: {chance}")
                        if chance == 2:
                            await self._send_with_image(message.channel, 'french_clip.png',
                                                        "Paint me like one of your French clips!", )
                        else:
                            await self._send_with_image(message.channel, 'microsoft-clippy-orange.png',
                                                        self._get_random_message(False))
            await self.process_commands(message)

    @staticmethod
    async def _send_with_image(channel, filename, msg):
        with open(os.path.join('data', filename), 'rb') as imgfile:
            await channel.send(content=msg,
                               file=discord.File(imgfile, filename='microsoft-clippy-orange.png'))

    def _get_random_message(self, rainbow):
        rainbow_options = [
            "Reviewing is magic",
            "Welcome to Clippy-Con",
            "I could clear the queue in 10 seconds flat",
            "Do you like my new hairstyle?",
            "Nominations will now be 20% cooler",
            "We should work with Nyan Cat so we can call them Nyantic",
        ]
        options = [
            "Hi there, it looks like you're trying to review a Wayspot!",
            "Take care not to clog up your area with too many Wayspots!",
            "I'll ask for help from my good friend, Remy",
            "There are no current updates to your problem at this time, thank you for your patience",
            "Let me circle back with an answer for you next week.",
            "Not all Wayspots will appear in game.",
            "Have you tried turning Wayfarer off and on again?",
            "Avoid cool downs by reviewing More Accurately™",
            "Please ensure that you complete reviewing each nomination that is assigned to you.",
            "I take zero responsibility for your cool downs",
            "Some wayspots are more equal than others",
            "Check your Junk/Spam folders to see if you have received an email notification regarding your nominations",
            "We have reviewed your message and have taken action",
            "Actually, it was me, Clippy 😅",
            "This should now be fixed, thank you.",
            "I am thankful to everyone for having a healthy discussion on this thread",
            f"Your report has been processed and action has been taken on {random.randint(10,100)} "
            "Wayspots in response to your report",

        ]

        if rainbow:
            m_index = random.randint(0, len(rainbow_options) - 1)
            while m_index == self.last_rainbow_random:
                m_index = random.randint(0, len(rainbow_options) - 1)
            self.last_rainbow_random = m_index
            return rainbow_options[m_index]
        else:
            m_index = random.randint(0, len(options) - 1)
            while m_index == self.last_random:
                m_index = random.randint(0, len(options) - 1)
            self.last_random = m_index
            return options[m_index]

    @staticmethod
    def _check_thumb(message):
        thumbs = ["ThumbsDownLight", "ThumbLight", "ThumbDark", "ThumbsDownDark", "Thumbing"]
        for word in thumbs:
            if word in message:
                return True
        return False

    @staticmethod
    def _check_words(word_list, message):
        for word in word_list:
            if word in message:
                return True
        return False

    async def process_commands(self, message):
        """Processes commands that are registered with the bot and it's groups.

        Without this being run in the main `on_message` event, commands will
        not be processed.
        """
        if message.author.bot:
            return
        if message.content.startswith('!'):
            try:
                if message.content[1] == " ":
                    message.content = message.content[0] + message.content[2:]
                content_array = message.content.split(' ')
                content_array[0] = content_array[0].lower()
            except IndexError:
                pass

        ctx = await self.get_context(message)
        if not ctx.command:
            return
        await self.invoke(ctx)

    def get_guild_prefixes(self, guild, *, local_inject=_prefix_callable):
        proxy_msg = discord.Object(id=None)
        proxy_msg.guild = guild
        return local_inject(self, proxy_msg)

    async def on_member_join(self, member):
        guild = member.guild
        if guild.id != 639640865249165343:
            return
        self.guild_dict[guild.id]['configure_dict'] \
            .setdefault('invite_tracking', {'enabled': True, 'destination': 644254949454381066, 'invite_counts': {}})
        t_guild_dict = copy.deepcopy(self.guild_dict)
        invite_dict = t_guild_dict[guild.id]['configure_dict']['invite_tracking']['invite_counts']
        all_invites = await guild.invites()
        messages = []
        invite_codes = []
        for inv in all_invites:
            if inv.code in invite_dict:
                count = invite_dict.get(inv.code, inv.uses)
                if inv.uses > count:
                    messages.append(f"Using invite code: {inv.code} for: {inv.channel} created by: {inv.inviter}")
                    invite_codes.append(inv.code)
            elif inv.uses == 1:
                messages.append(f"Using new invite code: {inv.code} for: {inv.channel} created by: {inv.inviter}")
                invite_codes.append(inv.code)
            invite_dict[inv.code] = inv.uses
        notify = '\n'.join(messages)

        destination = t_guild_dict[guild.id]['configure_dict']['invite_tracking'].get('destination', None)
        if destination and len(messages) > 0:
            try:
                await self.get_channel(destination).send(notify)
            except AttributeError:
                pass

        self.guild_dict[guild.id]['configure_dict']['invite_tracking']['invite_counts'] = invite_dict

    async def on_member_remove(self, member):
        guild = member.guild
        if guild.id != 639640865249165343:
            return
        destination = self.guild_dict[guild.id]['configure_dict']['invite_tracking'].get('destination', None)
        if destination:
            role_names = []
            for role in member.roles:
                if role.name != "@everyone":
                    role_names.append(role.name)

            message = f"{member.name}#{member.discriminator} left. Last joined: {member.joined_at}. ID: {member.id}" \
                      f" Roles: {', '.join([r for r in role_names])}"
            try:
                await self.get_channel(destination).send(message)
            except AttributeError:
                pass

    async def on_guild_join(self, guild):
        owner = guild.owner
        self.guild_dict[guild.id] = {
            'configure_dict': {},
        }
        await owner.send("Welcome.")

    async def on_guild_remove(self, guild):
        try:
            if guild.id in self.guild_dict:
                try:
                    del self.guild_dict[guild.id]
                except KeyError:
                    pass
        except KeyError:
            pass

    async def on_member_update(self, before, after):

        pass

    async def on_message_delete(self, message):
        pass
