import typing
import os
import yarl
import asyncio
import aiohttp
import json
import datetime

import discord
import random
from discord.ext import commands, menus, tasks
import pandas as pd
import textwrap

from .utils.paginator import BotPages


GITHUB_API = 'https://api.github.com'


def is_in_botdev():
    async def predicate(ctx):
        if ctx.guild.id != 909105827850387478:
            raise commands.CheckFailure("You don't have permission to use this command.")
        return True

    return commands.check(predicate)


class Github:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.access_token = os.getenv("WgithubTOKEN")
        self._req_lock = asyncio.Lock()

    async def github_request(self, method, url, *, params=None, data=None, headers=None):
        hdrs = {
            'Accept': 'application/vnd.github.inertia-preview+json',
            'User-Agent': 'WitherredAway',
            'Authorization': 'token %s' % self.access_token,
        }

        req_url = yarl.URL(GITHUB_API) / url
        
        if headers is not None and isinstance(headers, dict):
            hdrs.update(headers)

        await self._req_lock.acquire()
        try:
            async with self.bot.session.request(method, req_url, params=params, json=data, headers=hdrs) as r:
                remaining = r.headers.get('X-Ratelimit-Remaining')
                js = await r.json()
                if r.status == 429 or remaining == '0':
                    # wait before we release the lock
                    delta = discord.utils._parse_ratelimit_header(r)
                    await asyncio.sleep(delta)
                    self._req_lock.release()
                    return await self.github_request(method, url, params=params, data=data, headers=headers)
                elif 300 > r.status >= 200:
                    return js
                else:
                    raise commands.CommandError(js['message'])
        finally:
            if self._req_lock.locked():
                self._req_lock.release()

    async def create_gist(
        self,
        content: str,
        *,
        description: str = None,
        filename: str = "output.txt",
        public: bool = True,
    ):
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        data = {"public": public, "files": {filename: {"content": content}}}
        params = {"scope": "gist"}

        if description:
            data["description"] = description

        js = await self.github_request("POST", "gists", data=data, headers=headers, params=params)
        return js["html_url"]

    async def edit_gist(
        self,
        gist_id: str,
        files: typing.Dict,
        *,
        description: str = None,
    ):
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        data = {"files": files}
        
        if description:
            data["description"] = description

        url = "gists/%s" % gist_id
        js = await self.github_request("PATCH", url, data=data, headers=headers)
        return js["html_url"]


class CreateGistModal(discord.ui.Modal):
    
    filename = discord.ui.TextInput(
        label="Filename",
        min_length=10,
        max_length=100,
        placeholder="output.txt",
        default="output.txt",
    )
    description = discord.ui.TextInput(
        label="Description", max_length=1000, placeholder="Description", default=None
    )
    content = discord.ui.TextInput(label="Content", style=discord.TextStyle.paragraph)

    def __init__(self, ctx):
        super().__init__(title="Create gist")
        self.ctx = ctx

    async def on_submit(self, interaction: discord.Interaction):
        github = Github(self.ctx.bot)
        gist_url = await github.create_gist(
            self.content.value,
            description=self.description.value,
            filename=self.filename.value,
            public=False
        )

        await interaction.response.send_message(gist_url)


class EditGistModal(discord.ui.Modal):

    gist_id = discord.ui.TextInput(
        label="Gist ID",
        min_length=10,
        max_length=100,
        placeholder="ID of the gist you want to edit",
    )
    filename = discord.ui.TextInput(
        label="Filename",
        min_length=10,
        max_length=100,
        placeholder="Name of the file that you want to edit",
        default="output.txt",
    )
    description = discord.ui.TextInput(
        label="Description", max_length=1000, placeholder="New description", default=None
    )
    content = discord.ui.TextInput(label="Content", placeholder="New content of the file", style=discord.TextStyle.paragraph)

    def __init__(self, ctx):
        super().__init__(title="Edit an already existing gist")
        self.ctx = ctx

    async def on_submit(self, interaction: discord.Interaction):
        github = Github(self.ctx.bot)
        gist_url = await github.edit_gist(
            self.gist_id.value,
            self.content.value,
            description=self.description.value,
            filename=self.filename.value,
        )

        await interaction.response.send_message(gist_url)


class GistView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, please create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Create gist", style=discord.ButtonStyle.green)
    async def _create_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        modal = CreateGistModal(self.ctx)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit a gist", style=discord.ButtonStyle.blurple)
    async def _edit_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        modal = EditGistModal(self.ctx)
        await interaction.response.send_modal(modal)


class Test(commands.Cog):
    """Commands for testing."""

    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

        self.UCP_GIST_ID = "2206767186c249f17b07ad9a299f068c"
        self.unc_filename = "Unclaimed Pokemon.md"
        self.unr_filename = "Unreviewed Pokemon.md"
        self.ml_filename = "Claimed missing link.md"
        
        self.unc = True
        self.unr = True
        self.ml = True
        
        self.url = 'https://docs.google.com/spreadsheets/d/1-FBEjg5p6WxICTGLn0rvqwSdk30AmZqZgOOwsI2X1a4/export?gid=0&format=csv'
        
        self.update_pokemon.start()

    def cog_unload(self):
        self.update_pokemon.cancel()
    
    display_emoji = "🧪"

    @commands.check_any(commands.is_owner(), is_in_botdev())
    @commands.command()
    async def gist(self, ctx):
        view = GistView(ctx)
        await ctx.send(view=view)

    def validate_unclaimed(self):
        pk = self.pk
        unc_list = sorted(list(pk["Name"][pk["Person in Charge"].isna()]))
        
        unc_amount = len(unc_list)
        if hasattr(self, "unc_amount"):
            if self.unc_amount == unc_amount:
                self.unc = False
                return False
            else:
                self.unc_amount = unc_amount
        else:
            self.unc_amount = unc_amount

        return unc_list, unc_amount

    def format_unreviewed(self, df, user, pkm_indexes):
        pkm_list = []
        for idx, pkm_idx in enumerate(pkm_indexes):
            pokename = df.loc[pkm_idx, "Name"]
            comment = df.loc[pkm_idx, "Comment"] if str(df.loc[pkm_idx, "Comment"]) != "nan" else None
            link = df.loc[pkm_idx, "Complete Imgur Link"]
            location = f'{self.url[:-24]}/edit#gid=0&range=E{pkm_idx+7}'

            comment_text = f'''(Marked for review)
        - Comment: {comment}
            '''
            text = f'''
    1. `{pokename}` {comment_text if comment else ""}
        - [Sheet location]({location})
        - [Imgur]({link})
            '''
            pkm_list.append(text)
        format_list = "\n".join(pkm_list)
        return_text = f"""- **{user}** [{len(pkm_list)}]
{format_list}"""
        return return_text

    async def get_unreviewed(self, df, df_grouped):
        df_list = []
        for _id, pkm_idx in df_grouped.groups.items():
            user = await self.bot.fetch_user(int(_id))
            msg = self.format_unreviewed(df, user, pkm_idx)
            
            df_list.append(msg)

        return df_list

    async def validate_unreviewed(self):
        pk = self.pk
        df = pk.loc[(~pk["Person's ID"].isna()) & (~pk["Complete Imgur Link"].isna()) & (pk["Approval Status"] != "Approved")]

        df_grouped = df.groupby("Person's ID")

        unr_amount = len([pkm_id for pkm_idx in df_grouped.groups.values() for pkm_id in pkm_idx])

        if hasattr(self, "unr_amount"):
            if self.unr_amount == unr_amount:
                self.unr = False
                return False
            else:
                unr_list = await self.get_unreviewed(df, df_grouped)
                self.unr_amount = unr_amount
        else:
            unr_list = await self.get_unreviewed(df, df_grouped)
            self.unr_amount = unr_amount

        return unr_list, unr_amount

    async def get_missing_link(self, df, df_grouped):
        df_list = []
        mention_list = []
        for _id, pkm_idx in df_grouped.groups.items():
            pkm_list = df.loc[pkm_idx, "Name"]
            formatted_list = list(map(lambda x: f'`{x}`', pkm_list))
            msg = f'- **{await self.bot.fetch_user(int(_id))}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            df_list.append(msg)
            mention_msg = f'- **{(await self.bot.fetch_user(int(_id))).mention}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            mention_list.append(mention_msg)

        return df_list, mention_list

    async def validate_missing_link(self):
        pk = self.pk
        df = pk.loc[(~pk["Person's ID"].isna()) & (pk["Complete Imgur Link"].isna())]

        df_grouped = df.groupby("Person's ID")

        ml_amount = len([pkm_id for pkm_idx in df_grouped.groups.values() for pkm_id in pkm_idx])

        if hasattr(self, "ml_amount"):
            if self.ml_amount == ml_amount:
                self.ml = False
                return False
            else:
                ml_list, ml_list_mention = await self.get_missing_link(df, df_grouped)
                self.ml_amount = ml_amount
        else:
            ml_list, ml_list_mention = await self.get_missing_link(df, df_grouped)
            self.ml_amount = ml_amount
            
        return ml_list, ml_list_mention, ml_amount
        
    # The task that updates the unclaimed pokemon gist
    @tasks.loop(minutes=5)
    async def update_pokemon(self):
        self.pk = pd.read_csv(self.url , index_col=0, header=6, dtype={"Person's ID": object})
        date = (datetime.datetime.utcnow()).strftime('%I:%M%p, %d/%m/%Y')
        updated = []
        
        unc_list, unc_amount = self.validate_unclaimed()
        
        unr_list, unr_amount = await self.validate_unreviewed()

        ml_list, ml_list_mention, ml_amount = await self.validate_missing_link()

        files = {}
        if self.unc:
            updated.append(f"`Unclaimed pokemon` **({unc_amount})**")
            unc_content = "## Count: %s\n## Pokemon: \n%s" % (unc_amount, "\n".join(unc_list) if unc_list else "None")
            files[self.unc_filename] = {
                'filename': self.unc_filename,
                'content': unc_content
            }
        if self.unr:
            updated.append(f"`Unreviewed pokemon` **({unr_amount})**")
            unr_content = "## Count: %s\n## Users: \n%s" % (unr_amount, "\n".join(unr_list) if unr_list else "None")
            files[self.unr_filename] = {
                'filename': self.unr_filename,
                'content': unr_content
            }
        if self.ml:
            updated.append(f"`Missing link pokemon` **({ml_amount})**")
            ml_content = "## Count: %s\n## Users: \n%s\n\n\n## Copy & paste to ping:\n```\n%s\n```" % (ml_amount, "\n".join(ml_list) if ml_list else "None", "\n".join(ml_list_mention) if ml_list else "None")
            files[self.ml_filename] = {
                'filename': self.ml_filename,
                'content': ml_content
            }
        if not (self.unc or self.unr or self.ml):
            return
            
        github = Github(self.bot)

        description = f"{self.ml_amount} claimed pokemon with missing links, {self.unc_amount} unclaimed pokemon and {self.unr_amount} unreviewed pokemon - As of {date} GMT (Checks every 5 minutes, and updates only if there is a change)"
        gist_url = await github.edit_gist(
            self.UCP_GIST_ID,
            files,
            description=description,
        )
        update_msg = "Updated %s! (%s)" % (" and ".join(updated), gist_url)
        await self.bot.update_channel.send(update_msg)

    @update_pokemon.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Test(bot))
