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
        self.access_token = os.getenv("githubTOKEN")
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
        content: str,
        *,
        description: str = None,
        filename: str = "output.txt",
    ):
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        data = {"files": {filename: {"content": content}}}
        
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
        self.UCP_FILENAME = "Unclaimed Pokemon.txt"

        self.update_unclaimed_pokemon.start()

    def cog_unload(self):
        self.update_unclaimed_pokemon.cancel()
    
    display_emoji = "🧪"

    @commands.check_any(commands.is_owner(), is_in_botdev())
    @commands.command()
    async def gist(self, ctx):
        view = GistView(ctx)
        await ctx.send(view=view)

    async def get_unclaimed(self):   
        pk = pd.read_csv('https://docs.google.com/spreadsheets/d/1-FBEjg5p6WxICTGLn0rvqwSdk30AmZqZgOOwsI2X1a4/export?gid=0&format=csv', index_col=0, header=6)
    
        msg = "\n".join(sorted(list(pk["Name"][pk["Person in Charge"].isna()])))  
        return msg
        
    # The task that updates the unclaimed pokemon gist
    @tasks.loop(minutes=5)
    async def update_unclaimed_pokemon(self):
        content = await self.get_unclaimed()
        amount = len(content.split("\n"))
        if hasattr(self, "amount"):
            if self.amount == amount:
                return
        else:
            self.amount = amount
            
        github = Github(self.bot)
        date = (datetime.datetime.utcnow()).strftime('%I:%M%p, %d/%m/%Y')
        
        gist_url = await github.edit_gist(
            self.UCP_GIST_ID,
            content,
            description="%s unclaimed pokemon as of %s GMT (Checks every 5 minutes, and updates only if there is a change)" % (amount, date),
            filename=self.UCP_FILENAME,
        )
        await self.bot.update_channel.send("Updated! %s (%s)" % (gist_url, amount))

    @update_unclaimed_pokemon.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Test(bot))
