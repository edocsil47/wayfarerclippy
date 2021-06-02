import asyncio
import os
import json

import discord
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from datetime import date

from discord.ext import commands

from clippy import checks, utils


class CommentScrapeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users = self._load_file(os.path.join('data', "nia_users.json"))
        self.post_info = self._load_file(os.path.join('data', "post_info.json"))
        if not self.users or not self.post_info:
            return
        self.post_ids = [p["discussionID"] for p in self.post_info]
        self.characterLimit = 280
        self.profileIconURL = "https://us.v-cdn.net/6032079/uploads/userpics/801/pQAD25QEXJZ5H.png"
        self.status_tiers = [8,48] # max hours for "active" status, max hours before "offline" status
        self.status_indicators = ["🟢", "🟡", "🔴"] # emoji for online status; active, away, offline
        self.wayforum_ep = "https://community.wayfarer.nianticlabs.com/api/v2" # API endpoint

    def _load_file(self, filename):
        if not os.path.exists(filename):
            self.bot.logger.warn(f'{filename} not found')
            return None
        with open(filename, 'r') as json_data:
            return json.load(json_data)

    @commands.command(hidden=True, aliases=['scoc'])
    @commands.has_permissions(manage_roles=True)
    async def set_comment_output_channel(self, ctx, item):
        output_channel = await self.channel_helper(ctx, item)
        if output_channel is None:
            self.bot.help_logger.info(f"User: {ctx.author.name}, channel: {ctx.channel}, error: Channel not found: {item}.")
            await ctx.channel.send(f'Channel not found: {item}. Could not set comment output channel', delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        self.bot.guild_dict[ctx.guild.id]['configure_dict'].setdefault('comment_output_channel', output_channel.id)
        await ctx.channel.send(f'{output_channel.mention} set as comment output channel.', delete_after=10)
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, aliases=['spoc'])
    @commands.has_permissions(manage_roles=True)
    async def set_post_output_channel(self, ctx, item):
        output_channel = await self.channel_helper(ctx, item)
        if output_channel is None:
            self.bot.help_logger.info(f"User: {ctx.author.name}, channel: {ctx.channel}, error: Channel not found: {item}.")
            await ctx.channel.send(f'Channel not found: {item}. Could not set post output channel', delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        self.bot.guild_dict[ctx.guild.id]['configure_dict'].setdefault('post_output_channel', output_channel.id)
        await ctx.channel.send(f'{output_channel.mention} set as post output channel.', delete_after=10)
        return await ctx.message.add_reaction(self.bot.success_react)

    async def channel_helper(self, ctx, item):
        utilities_cog = self.bot.cogs.get('Utilities')
        if not utilities_cog:
            await ctx.channel.send('Utilities module not found, command failed.', delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        qbl_channel = await utilities_cog.get_channel_by_name_or_id(ctx, item)
        if qbl_channel is None:
            await ctx.channel.send('No channel found by that name or id, please try again.', delete_after=10)
            return await ctx.message.add_reaction(self.bot.failed_react)
        return qbl_channel

    @commands.command(hidden=True, name='add_comment_react_channel', aliases=['acrc'])
    @commands.has_permissions(manage_roles=True)
    async def _add_snax_channel(self, ctx, channel_id):
        output_channel = await self.channel_helper(ctx, channel_id)
        if output_channel is None:
            return await ctx.message.add_reaction(self.bot.failed_react)
        snax_channels = self.bot.config.setdefault('comment_react_channels', [])
        if output_channel.id not in snax_channels:
            snax_channels.append(output_channel.id)
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, name='rem_comment_react_channel', aliases=['rcrc'])
    @commands.has_permissions(manage_roles=True)
    async def _rem_snax_channel(self, ctx, channel_id):
        output_channel = await self.channel_helper(ctx, channel_id)
        if output_channel is None:
            return await ctx.message.add_reaction(self.bot.failed_react)
        snax_channels = self.bot.config.setdefault('comment_react_channels', [])
        if output_channel.id in snax_channels:
            snax_channels.remove(output_channel.id)
        return await ctx.message.add_reaction(self.bot.success_react)

    @commands.command(hidden=True, aliases=['ttt'])
    @commands.has_permissions(manage_roles=True)
    async def test_test(self, ctx):
        await self.check_for_updates(ctx.guild.id)

    @commands.command(hidden=True, name='get_comment_reactions', aliases=['gcr'])
    @checks.allow_react_check_commands()
    async def _get_comment_reactions(self, ctx, comment_id):
        return await self._check_reaction_command_perms(ctx, comment_id, "comment")

    @commands.command(hidden=True, name='get_discussion_reactions', aliases=['gdr'])
    @checks.allow_react_check_commands()
    async def _get_discussion_reactions(self, ctx, comment_id: int):
        return await self._check_reaction_command_perms(ctx, comment_id, "discussion")

    async def _check_reaction_command_perms(self, ctx, comment_id, command_type):
        allowed_roles = [639828284703506448, 702291832041767025]
        allowed = False
        for role in ctx.message.author.roles:
            if role.id in allowed_roles:
                allowed = True
        if not allowed:
            self.bot.logger.info(f"{ctx.message.author.name} used command _get_{command_type}_reactions "
                                 f"in channel {ctx.channel.name}")
            try:
                return await ctx.message.delete()
            except discord.Forbidden:
                self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
                return
        return await self._get_reactions(ctx, comment_id, command_type)

    @checks.serverowner_or_permissions(manage_messages=True)
    @commands.command(hidden=True, name='score_counts', aliases=['sc'])
    async def _score_counts(self, ctx, limit=15, post_id=6822):
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            self.bot.logger.warn(f"Did not have permission to delete message in {ctx.channel.name}.")
        async with ctx.typing():
            limit = min(limit, 25)
            page = 1
            all_reactions = {}
            comment_list = []
            all_comments = {}
            while True:
                url = f"https://community.wayfarer.nianticlabs.com/api/v2/comments?discussionID={post_id}&limit=100&page={page}"
                response = requests.get(url)
                if response.status_code != 200:
                    error_response = await ctx.send(f"Failed to look up comments for post {post_id}")
                    return await self._cleanup(ctx.message, error_response)
                comments = response.json()
                if len(comments) == 0:
                    break
                comment_list += comments
                page += 1
            for comment in comment_list:
                if comment["score"]:
                    all_comments[comment["commentID"]] = comment
                    all_reactions[comment["commentID"]] = comment["score"]
            sort_orders = sorted(all_reactions.items(), key=lambda x: x[1], reverse=True)
            # likes_only = {}
            # for i in sort_orders[:30]:
            #     c_reactions = await self._get_reactions(ctx, i[0], "comment", False)
            #     if c_reactions:
            #         if "Like" in c_reactions:
            #             likes_only[i[0]] = len(c_reactions["Like"])
            #
            # sorted_likes = sorted(likes_only.items(), key=lambda x: x[1], reverse=True)

            response_embed = discord.Embed(colour=discord.Colour.from_rgb(252, 71, 19))
            rank = 1
            for i in sort_orders[:limit]:
                com = all_comments[i[0]]
                raw = com['body']
                clean_text = BeautifulSoup(raw, 'html.parser').get_text()
                response_embed.add_field(name=f"**{rank}**. Score: {i[1]}",
                                         value=f"\n [{clean_text[:100]}](https://community.wayfarer.nianticlabs.com/discussion/comment/{i[0]}/#Comment_{i[0]})")
                rank += 1
            if len(response_embed.fields) == 0:
                response_embed.description = "This post has no comments with reactions."
            else:
                response_embed.title = f"Here are the top {limit} comments by score in post {post_id}"
                response_embed.url = f"https://community.wayfarer.nianticlabs.com/discussion/{post_id}"
            await ctx.send(embed=response_embed)

    async def _get_reactions(self, ctx, comment_id, command_type_singular, send=True):
        try:
            comment_id = int(comment_id)
        except ValueError:
            comment_id = int(comment_id.strip('<>').split("_")[-1])
        command_type = command_type_singular + "s"
        page = 1
        # 12343 error403
        full_reactions = {}
        while True:
            response = requests.get("https://community.wayfarer.nianticlabs.com/api/v2/"
                                    f"{command_type}/{comment_id}/reactions?limit=100&page={page}")
            if response.status_code != 200:
                error_response = await ctx.send(f"No {command_type_singular} found with id: {comment_id}")
                return await self._cleanup(ctx.message, error_response)
            reactions = response.json()
            if len(reactions) == 0:
                if page == 1:
                    if send:
                        error_response = await ctx.send(f"{command_type_singular} {comment_id} has no reactions")
                        return await self._cleanup(ctx.message, error_response)
                    else:
                        return
                if not send:
                    return full_reactions
                return

            if send:
                response_embed = await self._create_reactions_embed(reactions, command_type_singular, comment_id)
                await ctx.send(embed=response_embed)
            else:
                full_reactions = self._tally_reactions(reactions, full_reactions)
            page += 1

    @staticmethod
    def _tally_reactions(reactions, message_reactions):
        for react in reactions:
            react_type = react["reactionType"]["name"]
            if react_type not in message_reactions:
                message_reactions[react_type] = []
            message_reactions[react_type].append(react["user"]["name"])
        return message_reactions

    @staticmethod
    async def _create_reactions_embed(reactions, command_type_singular, comment_id):
        message_reactions = {}
        for react in reactions:
            react_type = react["reactionType"]["name"]
            if react_type not in message_reactions:
                message_reactions[react_type] = []
            message_reactions[react_type].append(react["user"]["name"])
        response_embed = discord.Embed(colour=discord.Colour.from_rgb(252, 71, 19))
        if command_type_singular == "discussion":
            title_url = f"https://community.wayfarer.nianticlabs.com/discussion/{comment_id}/"
        if command_type_singular == "comment":
            title_url = f"https://community.wayfarer.nianticlabs.com/discussion/comment/{comment_id}/" \
                        f"#Comment_{comment_id}"
        response_embed.url = title_url
        response_embed.title = f"Reactions for {command_type_singular.capitalize()} *{comment_id}*"
        message_text = ""
        for react_type in message_reactions:
            message_text += f"**{react_type}** ({len(message_reactions[react_type])}): " \
                            f"{', '.join(message_reactions[react_type])}\n"
        response_embed.description = message_text
        return response_embed

    @staticmethod
    async def _cleanup(message, error_response):
        await asyncio.sleep(10)
        try:
            await message.delete()
            await error_response.delete()
        except:
            pass

    async def comment_scrape(self, guild_id):
        task_page = "https://community.wayfarer.nianticlabs.com/profile/comments/NianticCasey-ING"
        page = requests.get(task_page)
        soup = BeautifulSoup(page.content, 'html.parser')
        new_comments = 0

        comments = soup.findAll('li', attrs={'class': 'Item'})

        for comment in comments:
            comment_id = comment.attrs['id'].split('_')[1]
            if comment_id in self.comment_ids:
                break
            raw_message = comment.find('div', attrs={'class': 'Message'})
            message_text = raw_message.contents[0]

            link_el = comment.find('span', attrs={'class': 'MItem'})
            post_title = link_el.find('a').contents[0]

            output_channel_id = self.bot.guild_dict[guild_id]['configure_dict'].get('comment_output_channel', 0)
            output_channel = None
            if output_channel_id != 0:
                output_channel = self.bot.get_channel(output_channel_id)
            if output_channel:
                message_embed = self.format_comment_message(comment_id, post_title, message_text)
                await output_channel.send(embed=message_embed)
            else:
                self.bot.logger.warn("No post output channel found.")
            self.comment_ids.append(comment_id)
            new_comments += 1

        with open(os.path.join('data', 'comment_id_history'), 'w') as file:
            for cid in self.comment_ids:
                file.write("%i\n" % int(cid))

        return new_comments

    async def post_scrape(self, guild_id):
        task_page = "https://community.wayfarer.nianticlabs.com/profile/discussions/NianticCasey-ING"
        page = requests.get(task_page)
        soup = BeautifulSoup(page.content, 'html.parser')
        new_posts = 0

        posts = soup.findAll('li', attrs={'class': 'ItemDiscussion'})

        for post in posts:
            post_id = post.attrs['id'].split('_')[1]
            if post_id in self.post_ids:
                break
            title_div = post.find('div', attrs={'class': 'Title'})
            title_a = title_div.find('a')
            meta_div = post.find('div', attrs={'class': 'Meta'})
            post_title = title_a.contents[0]
            post_url = title_a.attrs['href']

            category_span = meta_div.find('span', attrs={'class': 'Category'})
            category_a = category_span.find('a')
            category_name = category_a.contents[0]

            output_channel_id = self.bot.guild_dict[guild_id]['configure_dict'].get('comment_output_channel', 0)
            output_channel = None
            if output_channel_id != 0:
                output_channel = self.bot.get_channel(output_channel_id)
            if output_channel:
                message_embed = self.format_post_message(post_title, post_url, category_name)
                await output_channel.send(embed=message_embed)
            else:
                self.bot.logger.warn("No post output channel found.")
            self.post_ids.append(post_id)
            new_posts += 1

        with open(os.path.join('data', 'post_id_history'), 'w') as file:
            for cid in self.post_ids:
                file.write("%i\n" % int(cid))

        return new_posts

    async def check_for_updates(self):
        messages = {"comments": [], "discussions": []}

        await self._check_for_user_changes()
        for user_id, user in self.users.items():
            comments_page, discussions_page = user["last_comments_page"], user["last_discussions_page"]
            latest_comment, latest_discussion = user["latest_comment"], user["latest_discussion"]
            last_page = []

            try:
                while True:
                    url = f"https://community.wayfarer.nianticlabs.com/api/v2/discussions?insertUserID={user_id}" \
                          f"&limit=100&page={discussions_page}"
                    async with self.bot.session.get(url=url) as response:
                        await response
                    if response.json() == last_page or response.json() == []:
                        break
                    last_page = response.json()
                    discussions = response.json()
                    if len(discussions) > 2:
                        discussions.reverse()
                    for discussion in discussions:
                        if int(discussion["discussionID"]) not in self.post_ids:
                            self.post_ids.append(discussion["discussionID"])
                            self.post_info.append(self._compact_discussion(discussion))
                        if int(discussion["discussionID"]) > latest_discussion:
                            latest_discussion = discussion["discussionID"]
                            messages["discussions"].append(self._format_discussion(discussion, user["name"]))
                    discussions_page += 1
                user["latest_discussion"] = latest_discussion
                user["last_discussions_page"] = max(discussions_page - 1, 1)
            except Exception as e:
                self.bot.logger.warn(f"Failed to update discussions for user {user['name']}\nFull error: {e}")

            last_page = []
            try:
                while True:
                    url = "https://community.wayfarer.nianticlabs.com/api/v2/comments?insertUserID=" + str(
                            user_id) + "&limit=100&page=" + str(comments_page)
                    async with self.bot.session.get(url=url) as response:
                        await response
                    if response.json() == last_page or response.json() == []:
                        break
                    last_page = response.json()
                    comments = response.json()
                    if len(comments) > 0:
                        for comment in comments:
                            if comment["commentID"] > latest_comment:
                                latest_comment = comment["commentID"]
                                if int(comment["discussionID"]) not in self.post_ids:
                                    parent_post = self._get_post_by_id(comment["discussionID"])
                                    self.post_ids.append(parent_post["discussionID"])
                                    self.post_info.append(parent_post)
                                else:
                                    parent_post = self._get_discussion_from_list(self.post_info, comment["discussionID"])
                                if int(parent_post["categoryID"]) not in user["exclude_categories"]:
                                    messages["comments"]\
                                        .append(self._format_comment(comment, parent_post, user["name"]))
                        comments_page += 1
                    else:
                        break
                    comments_page = max(comments_page, 1)
                    user["latest_comment"] = latest_comment
                    user["last_comments_page"] = comments_page - 1
            except Exception as e:
                self.bot.logger.warn(f"Failed to update comments for user {user['name']}\nFull error: {e}")

        with open(os.path.join('data', 'post_info.json'), 'w') as fd:
            json.dump(self.post_info, fd, indent=4)

        with open(os.path.join('data', 'nia_users.json'), 'w') as fd:
            json.dump(self.users, fd, indent=4)

        return messages

    async def _check_for_user_changes(self):
        role_ids = [16, 32, 33]
        for role in role_ids:
            users = requests.get(
                f"https://community.wayfarer.nianticlabs.com/api/v2/users?roleID={role}&limit=100").json()
            for user in users:
                if str(user["userID"]) not in self.users.keys():
                    self.users[str(user["userID"])] = {
                        "userID": user["userID"],
                        "name": user["name"],
                        "exclude_categories": [],
                        "last_comments_page": 1,
                        "last_discussions_page": 1,
                        "latest_comment": 0,
                        "latest_discussion": 0
                    }
                else:
                    self.users[str(user["userID"])]["name"] = user["name"]

    @staticmethod
    def _get_discussion_from_list(posts, post_id):
        for p in posts:
            if p["discussionID"] == post_id:
                return p

    def _get_post_by_id(self, post_id):
        full_post = requests.get("https://community.wayfarer.nianticlabs.com/api/v2/discussions/" + str(post_id)).json()
        return self._compact_discussion(full_post)

    @staticmethod
    def _compact_discussion(full_post):
        return {"discussionID": full_post["discussionID"],
                "name": full_post["name"],
                "body": full_post["body"],
                "categoryID": full_post["categoryID"],
                "dateUpdated": full_post["dateUpdated"],
                "insertUserID": full_post["insertUserID"],
                "url": full_post["url"]
                }

    def _format_comment(self, comment, parent, username):
        thread_title = parent["name"]
        clean_text = BeautifulSoup(comment['body'], 'html.parser').get_text()
        if len(clean_text) > self.characterLimit:
            clean_text = clean_text[:self.characterLimit] + "..."

        m_embed = discord.Embed(colour=discord.Colour.from_rgb(252, 71, 19))
        m_embed.title = f"New comment by {username} in:\n {thread_title}"
        m_embed.description = clean_text
        m_embed.url = comment['url']
        m_embed.set_footer(text=f"Posted at {comment['dateInserted']}")
        m_embed.set_thumbnail(url=self.profileIconURL)

        return m_embed

    def _format_discussion(self, discussion, username):
        thread_title = discussion["name"]
        clean_text = BeautifulSoup(discussion['body'], 'html.parser').get_text()
        if len(clean_text) > self.characterLimit:
            clean_text = clean_text[:self.characterLimit] + "..."

        m_embed = discord.Embed(colour=discord.Colour.from_rgb(0, 184, 236))
        m_embed.title = f"New discussion post by {username}: {thread_title}"
        m_embed.description = clean_text
        m_embed.url = discussion['url']
        m_embed.set_footer(text=f"Posted at {discussion['dateInserted']}")
        m_embed.set_thumbnail(url=self.profileIconURL)
        return m_embed

    async def check_loop(self):
        while not self.bot.is_closed():
            self.bot.logger.info("Checking for new comments and posts.")
            messages = await self.check_for_updates()
            self.bot.logger.info(f"Found {len(messages['comments'])} new comments "
                                 f"and {len(messages['discussions'])} new posts.")

            for guildid in self.bot.guild_dict.keys():
                output_channel_id = self.bot.guild_dict[guildid]['configure_dict'].get('comment_output_channel', 0)
                output_channel = None
                if output_channel_id != 0:
                    output_channel = self.bot.get_channel(output_channel_id)
                if output_channel:
                    for m in messages["discussions"]:
                        await output_channel.send(embed=m)
                    for m in messages["comments"]:
                        await output_channel.send(embed=m)

            await asyncio.sleep(self.bot.check_delay_minutes * 60)

    def handle_forum_username(self, user):
        """ Allows forum functions to use smart IDs if desired,
        e.g. !profile 9
          or !profile NianticCasey-ING
          or !profile NianticCasey
        can all be used. The latter case (alias) will be cached to avoid making
        excess requests to the API.
        """
        if user.isdigit() and len(user) < 7: # *probably* won't have any players with numerical usernames under 6 characters join the forums without a game suffix right?
            return user
        if user.upper().endswith("-PGO"):
            return f"$name:{user}"
        if user.upper().endswith("-ING"):
            return f"$name:{user}"
        read_only_flag = False
        try:
            with open('ID_alias_list.json') as json_file:
                ID_alias_list = json.load(json_file)
        except FileNotFoundError:
            ID_alias_list = {}
        except:
            read_only_flag = True
        if user in ID_alias_list:
            return ID_alias_list[user]

        # if user is not easily parsable or currently in the alias list, will make
        # API calls to search for the currect game suffix. Worst case is three API
        # calls being made for an invalid username. Successful calls will not have
        # to be made again
        response = requests.get(f"{self.wayforum_ep}/users/$name:{user}-PGO")
        if response.status_code != 404:
            if not read_only_flag:
                ID_alias_list[user] = response.json()["userID"]
                with open('ID_alias_list.json', 'w') as outfile:
                    json.dump(ID_alias_list, outfile)
            return response.json()["userID"]

        response = requests.get(f"{self.wayforum_ep}/users/$name:{user}-ING")
        if response.status_code != 404:
            if not read_only_flag:
                ID_alias_list[user] = response.json()["userID"]
                with open('ID_alias_list.json', 'w') as outfile:
                    json.dump(ID_alias_list, outfile)
            return response.json()["userID"]

        response = requests.get(f"{self.wayforum_ep}/users/$name:{user}")
        if response.status_code != 404:
            if not read_only_flag:
                ID_alias_list[user] = response.json()["userID"]
                with open('ID_alias_list.json', 'w') as outfile:
                    json.dump(ID_alias_list, outfile)
            return response.json()["userID"]

        return f"$name:{user}"

    def get_online_tier(self, elapsed):
        """ Returns appropriate online status tier from time offline in seconds"""
        if elapsed < self.status_tiers[0]*3600:
            return 0
        elif elapsed < self.status_tiers[1]*3600:
            return 1
        else:
            return 2

    @staticmethod
    def forum_paginated_request(url):
        """ Returns all pages for forum API calls that can have pagination"""
        i = 1
        pages = []
        last_page = []
        while True:
            response = requests.get(f"{url}&page={i}")
            # break loop if pages are not iterating or if page is blank
            if response.json() == last_page or response.json() == []:
                return pages
            pages += response.json()
            last_page = response.json()
            i += 1

    @commands.command(hidden=True, name="get_online", aliases=["ol","online"])
    async def get_online(self, ctx, user):
        """ Returns the last time a user was active on the forum"""
        response_profile = requests.get(f"{self.wayforum_ep}/users/{self.handle_forum_username(user)}")
        profile = response_profile.json()
        try:
            date_last_active = profile["dateLastActive"]
        except:
            error_response = await ctx.send(f"Sorry, I wasn't able to find a forum user named **{user}**")
            return await self._cleanup(ctx.message, error_response)
        elapsed = datetime.now().timestamp() - datetime.fromisoformat(date_last_active).timestamp()
        await ctx.send(f"{self.status_indicators[self.get_online_tier(elapsed)]} {profile['name']} was last online **{int(elapsed/3600)} hours ago** (at {date_last_active})")

    @commands.command(hidden=True, name="get_niantic_roles", aliases=["nia"])
    async def get_niantic_roles(self, ctx):
        """ Returns a list of all forum staff with their online status"""
        response_nia = self.forum_paginated_request(f"{self.wayforum_ep}/users?roleID=$name:Niantic")
        response_mod = self.forum_paginated_request(f"{self.wayforum_ep}/users?roleID=$name:Moderator")
        response_admin = self.forum_paginated_request(f"{self.wayforum_ep}/users?roleID=$name:Administrator")
        people = response_nia + response_mod + response_admin

        # categorize users by online status
        green = []; yellow = []; red = []
        for p in people:
            elapsed = datetime.now().timestamp() - datetime.fromisoformat(p["dateLastActive"]).timestamp()
            if self.get_online_tier(elapsed) == 0:
                green += [p["name"]]
            elif self.get_online_tier(elapsed) == 1:
                yellow += [p["name"]]
            else:
                red += [p["name"]]

        # create text for embed
        embed_content = ""
        if green:
            green = list(set(green))
            green.sort()
            embed_content += f"{self.status_indicators[0]} **Online in the past {self.status_tiers[0]} hours:**\n\
                               {', '.join(green)}\n\n"
        if yellow:
            yellow = list(set(yellow))
            yellow.sort()
            embed_content += f"{self.status_indicators[1]} **Online in the past {self.status_tiers[1]} hours:**\n\
                               {', '.join(yellow)}\n\n"
        if red:
            red = list(set(red))
            red.sort()
            embed_content += f"{self.status_indicators[2]} **Not online for more than {self.status_tiers[1]} hours:**\n\
                               {', '.join(red)}\n"

        embed = discord.Embed(
            title = "Niantic users on the Wayforum:",
            description = embed_content,
            color = 16533267
        )
        await ctx.send(embed=embed)

    @commands.command(hidden=True, name="get_forum_profile", aliases=["fpf"])
    async def get_forum_profile(self, ctx, user):
        """ Returns information from a forum user's profile"""
        response_profile = requests.get(f"{self.wayforum_ep}/users/{self.handle_forum_username(user)}")
        profile = response_profile.json()
        try:
            date_last_active = profile["dateLastActive"]
        except:
            error_response = await ctx.send(f"Sorry, I wasn't able to find a forum user named **{user}**")
            return await self._cleanup(ctx.message, error_response)
        elapsed = datetime.now().timestamp() - datetime.fromisoformat(date_last_active).timestamp()
        roles = [r["name"] for r in profile["roles"]]
        embed = discord.Embed(
            title = profile["name"],
            description = f"User ID: {profile['userID']}\n\
                            Roles: {', '.join(roles)}\n\
                            Join Date: {profile['dateInserted']}\n\
                            Comments: {profile['countComments']}\n\
                            Discussions: {profile['countDiscussions']}",
            url = profile["url"],
            color = 16533267
        )
        embed.set_footer(text = f"{self.status_indicators[self.get_online_tier(elapsed)]} Last online: {int(elapsed/3600)} hours ago (at {date_last_active})")
        embed.set_thumbnail(url = profile["photoUrl"])
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(CommentScrapeCog(bot))

