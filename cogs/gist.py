import typing
from typing import Optional, TypeVar, Union
import asyncio
import os
import copy
import gists
import re

import discord
from discord.ext import commands, menus, tasks
import validators

from .utils.paginator import BotPages
from constants import CODE_BLOCK_FMT


def new_file_name(*, default: Optional[str] = "", required: Optional[bool] = False):
    return discord.ui.TextInput(
        label="Create a new file",
        placeholder="New file's name e.g. output.txt",
        default=default,
        style=discord.TextStyle.short,
        custom_id="new_file_name",
        required=required,
    )


def new_file_content(*, default: Optional[str] = "", required: Optional[bool] = False):
    return discord.ui.TextInput(
        label="Content",
        placeholder="New file's content",
        default=default,
        style=discord.TextStyle.paragraph,
        custom_id="new_file_content",
        required=required,
    )


class CreateGistModal(discord.ui.Modal):
    """Interactive modal to create gists."""

    description = discord.ui.TextInput(
        label="Description of gist",
        placeholder="Description of the gist.",
        required=False,
    )
    filename = new_file_name(default="output.txt", required=True)
    content = new_file_content(required=True)

    def __init__(self, view: discord.ui.View):
        super().__init__(title="Create a new gist")
        self.view = view
        self.client = self.view.client

    async def on_submit(self, interaction: discord.Interaction):
        description = self.description.value
        self.view.description = description
        description += self.view.AUTHOR_WATERMARK
        filename = self.filename.value
        content = self.content.value

        files = gists.File(name=filename, content=content)

        gist = await self.client.create_gist(
            files=[files], description=description, public=True
        )
        await self.view.update_page(interaction, gist)


class EditGistModal(discord.ui.Modal):
    """The modal for executing various functions on a gist"""

    def __init__(self, view: discord.ui.View):
        super().__init__(title="Edit gist (only shows the first 2 files)")
        self.view = view
        self.client = self.view.client
        self.gist = self.view.gist
        self.file = self.view.source.file
        self._fill_items()

    def _fill_items(self):
        self.add_item(
            discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.paragraph,
                placeholder="Description of the gist.",
                default=self.view.description,
                custom_id="gist_description",
                required=False,
            )
        )

        filename = self.file.name
        content = self.file.content
        self.add_item(
            discord.ui.TextInput(
                label="Filename",
                placeholder=filename,
                style=discord.TextStyle.short,
                default=filename,
                custom_id=f"old_file_name",
                required=True,
            )
        )
        files_amt = len(self.gist.files)
        self.add_item(
            discord.ui.TextInput(
                label=f"{filename}'s content",
                placeholder=f"Edit content of file {filename}. {'Cannot delete last file' if files_amt == 1 else 'Leave empty to delete file'}.",
                style=discord.TextStyle.paragraph,
                default=content,
                custom_id=f"old_file_content",
                required=files_amt
                == 1,  # Makes it so that you can't delete the last file
            )
        )

        self.add_item(new_file_name())

        self.add_item(new_file_content())

    def children_dict(self) -> typing.Dict[str, discord.ui.TextInput]:
        ch_dict = {child.custom_id: child for child in self.children}
        return ch_dict

    async def on_submit(self, interaction: discord.Interaction):
        children = self.children_dict()
        file_objs = self.gist.files

        description = children["gist_description"].value
        self.view.description = description
        description += self.view.AUTHOR_WATERMARK

        old_file_name = children["old_file_name"].default
        old_file_new_name = children["old_file_name"].value
        old_file_content = children["old_file_content"].value
        file_objs.append(
            gists.File(
                name=old_file_name, content=old_file_content, new_name=old_file_new_name
            )
        )

        new_file_name = children["new_file_name"].value
        new_file_content = children["new_file_content"].value
        if all((new_file_name != "", new_file_content != "")):
            file_objs.append(gists.File(name=new_file_name, content=new_file_content))

        await self.gist.edit(
            files=file_objs,
            description=description,
        )
        await self.view.update_page(interaction)


class GistView(BotPages):
    def __init__(
        self,
        source: menus.PageSource,
        ctx: commands.Context,
        client: gists.Client,
        compact: bool,
    ):
        self.source = source
        self.ctx = ctx
        self.client = client
        self.compact = compact

        self.gist = self.source.gist
        self.description = self.source.description
        self._super()
        self.embed = self.source.embed

        self.AUTHOR_WATERMARK = f" - {self.ctx.author.id}"

        # if source.is_paginating():
        # self.add_view(source.entries)

    def _super(self):
        super().__init__(self.source, ctx=self.ctx, compact=self.compact)

    async def update_page(self, interaction, gist=None):
        if gist:
            self.gist = gist
            self.source.gist = gist

        current_page = self.current_page
        self.source.reload()
        # This resets self.current_page to the beginning
        self._super()
        try:
            await self.show_page(interaction, current_page)
        except IndexError:
            await self.show_page(interaction, self.current_page)

    def fill_items(self) -> None:
        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            self.add_item(self.go_to_first_page)  # type: ignore
            self.go_to_first_page.label = f"1 ⏮"
            self.add_item(self.go_to_previous_page)  # type: ignore
            self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            self.add_item(self.go_to_last_page)  # type: ignore
            self.go_to_last_page.label = f"⏭ {max_pages}"
            if not self.compact:
                self.add_item(self.numbered_page)  # type: ignore
            if not use_last_and_first:
                self.go_to_first_page.disabled = True
                self.go_to_last_page.disabled = True
                self.numbered_page.disabled = True
        self.add_item(self._create_gist)
        self.add_item(self._edit_gist)
        self.add_item(self._delete_gist)
        self._update_buttons()

    # TODO
    def add_view(self, entries: typing.List) -> None:
        self.clear_items()
        # self.add_item(GistSelectMenu)
        self.fill_items()

    async def show_page(
        self, interaction: discord.Interaction, page_number: int
    ) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        self._update_buttons()
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        if self.compact:
            max_pages = self.source.get_max_pages()
            self.go_to_last_page.disabled = (
                max_pages is None or (page_number + 1) >= max_pages
            )
            self.go_to_next_page.disabled = (
                max_pages is not None and (page_number + 1) >= max_pages
            )
            self.go_to_previous_page.disabled = page_number == 0
            return

        self.go_to_previous_page.label = f"{page_number} ᐊ"
        self.go_to_current_page.label = str(page_number + 1)
        self.go_to_next_page.label = f"ᐅ {page_number + 2}"

        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        # self.go_to_first_page.disabled = False

        max_pages = self.source.get_max_pages()
        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = "ᐅ"
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = "ᐊ"

    def _update_buttons(self):
        if self.gist:
            belongs = self.source.belongs
            if belongs:
                self._create_gist.disabled = True
                self._edit_gist.disabled = False
                self._delete_gist.disabled = False
            else:
                self._create_gist.disabled = False
                self._edit_gist.disabled = True
                self._delete_gist.disabled = True

            return
        self._create_gist.disabled = False
        self._edit_gist.disabled = True
        self._delete_gist.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id in (
            self.ctx.bot.owner_id,
            self.ctx.author.id,
        ):
            return True
        await interaction.response.send_message(
            "This instance does not belong to you!", ephemeral=True
        )
        return False

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None)

    @discord.ui.button(label="Create new gist", style=discord.ButtonStyle.green, row=1)
    async def _create_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        modal = CreateGistModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit file", style=discord.ButtonStyle.blurple, row=1)
    async def _edit_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        modal = EditGistModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete gist", style=discord.ButtonStyle.danger, row=1)
    async def _delete_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        await self.gist.delete()
        embed = self.embed
        embed.title += " [DELETED]"
        embed.color = 0xFF0000

        self.gist = None

        await self.update_page(interaction)


class GistPageSource(menus.ListPageSource):
    def __init__(self, gist: gists.Gist, *, ctx: commands.Context, per_page: int = 1):
        self.gist = gist
        self.ctx = ctx
        self.per_page = per_page

        self.bot = self.ctx.bot
        self.embed = self.bot.Embed()
        self.description = None
        self.reload()

    def reload(self):
        self.update_attrs()
        super().__init__(self.entries, per_page=self.per_page)

    def update_attrs(self):
        if self.gist is not None:
            self.entries = self.gist.files
            self.belongs = self.validate_author()
        else:
            self.entries = [None]

    def is_paginating(self) -> bool:
        return len(self.entries) > self.per_page and self.gist is not None

    async def format_page(self, menu, file: Union[gists.File, None]) -> discord.Embed:
        self.file = file
        embed = self.embed
        embed.clear_fields()
        gist = self.gist
        if not gist:
            embed.title = "Gist not found/provided."
            self.description = None
            return embed

        embed.title = gist.id
        embed.url = gist.url
        embed.description = self.description
        updated_at = f'{discord.utils.format_dt(gist.updated_at)}, {discord.utils.format_dt(gist.updated_at, style="R")}'
        created_at = f'{discord.utils.format_dt(gist.created_at)}, {discord.utils.format_dt(gist.created_at, style="R")}'
        embed.add_field(
            name="Updates",
            value=(
                f"**Last updated at**: {updated_at}\n" f"**Created at**: {created_at}"
            ),
        )

        if file is not None:
            content = (
                f"{file.content[:1010]}..."
                if len(file.content) > 1024
                else file.content
            )
            if not file.name.endswith(".md"):
                content = CODE_BLOCK_FMT % content
            embed.add_field(
                name=file.name,
                value=content,
            )

        maximum = self.get_max_pages()
        if maximum > 0:
            text = f"File {menu.current_page + 1}/{maximum}"
            self.embed.set_footer(text=text)

        return self.embed

    def validate_author(self):
        # Pattern to group the author id and the description content from the description
        pattern = re.compile(r"(.*) - (\d+)")

        desc = self.gist.description
        finds = pattern.search(desc)

        if finds is None:
            self.description = self.gist.description
            return False
        author_id, self.description = int(finds.group(2)), finds.group(1)

        if author_id == self.ctx.author.id:
            return True
        return False


class Gist(commands.Cog):
    """Commands for testing."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "📋"

    @commands.command(
        name="gist",
        brief="GitHub Gists utilities",
        help=(
            "Create a new gist or pass in the link/ID of a gist initially created through this command"
            " to Edit or Delete the list with the help of Modals and Buttons"
        ),
        description=(
            "Gists are a way to share text, code, etc with others and acts like a paste service.\n"
            "This command is intended to assist you in making such by using discord as a User Interface.\n\n"
            "When using this command please keep the Github Gists' [ToS](https://docs.github.com/en/github/site-policy/github-terms-of-service), [Privacy Policy](https://docs.github.com/en/github/site-policy/github-privacy-statement) and [Security documents](https://github.com/security) in mind. Any violation of these is not my responsibility."
        ),
    )
    async def gist(self, ctx, gist_url_or_id: Optional[str] = None):
        client = self.bot.gists_client
        gist = None

        if gist_url_or_id is not None:
            if validators.url(str(gist_url_or_id)):
                gist_url_or_id = gist_url_or_id.split("/")[
                    -2 if gist_url_or_id.endswith("/") else -1
                ]
            try:
                gist = await client.get_gist(gist_url_or_id)
            except gists.NotFound:
                gist = None

        formatter = GistPageSource(gist, ctx=ctx, per_page=1)
        menu = GistView(formatter, ctx=ctx, client=client, compact=True)
        await menu.start()
        # view.response = await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Gist(bot))
