import asyncio
import typing
from typing import Optional, Union, Literal
import re
import copy


import emojis
import numpy as np
import discord
from discord.ext import commands, tasks
from .utils.utils import invert_dict

ROW_ICONS = (
    "🇦",
    "🇧",
    "🇨",
    "🇩",
    "🇪",
    "🇫",
    "🇬",
    "🇭",
    "🇮",
    "🇯",
    "🇰",
    "🇱",
    "🇲",
    "🇳",
    "🇴",
    "🇵",
    "🇶",
)

COLUMN_ICONS = (
    "0️⃣",
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
    "🔟",
    "<:11:920679053688725596>",
    "<:12:920679079756300339>",
    "<:13:920679103332495430>",
    "<:14:920679132260618260>",
    "<:15:920679200854253578>",
    "<:16:920679238414266408>",
)

get_cursor = {
    "🟥": "🔴",
    "🟧": "🟠",
    "🟨": "🟡",
    "🟩": "🟢",
    "🟦": "🔵",
    "🟪": "🟣",
    "🟫": "🟤",
    "⬛": "⚫",
    "⬜": "⚪",
}

ABC = "ABCDEFGHIJKLMNOPQ"
NUM = (
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
)

conv = {
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3,
    "E": 4,
    "F": 5,
    "G": 6,
    "H": 7,
    "I": 8,
    "J": 9,
    "K": 10,
    "L": 11,
    "M": 12,
    "N": 13,
    "O": 14,
    "P": 15,
    "Q": 16,
}


def make_board(bg: str, height: int, width: int):
    board = np.full((height, width), bg, dtype="object")
    row_labels = ROW_ICONS[:height]
    col_labels = COLUMN_ICONS[:width]

    try:
        board[int(height / 2), int(width / 2)] = get_cursor[
            board[int(height / 2), int(width / 2)]
        ]
    except KeyError:
        pass
    return board, row_labels, col_labels


class Draw(commands.Cog):
    """Category with commands to bring out your inner artist."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🖌️"

    @commands.bot_has_permissions(external_emojis=True)
    @commands.group(
        name="draw",
        aliases=("drawing", "paint", "painting"),
        case_insensitive=True,
        brief="Make pixel art on discord!",
        help="wip",
        description="Command which you can use to make pixel art using buttons and dropdown menus.",
        invoke_without_command=True,
    )
    async def draw(
        self,
        ctx,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"] = "⬜",
    ):
        bg = background
        if height < 5 or height > 17:
            return await ctx.send("Height must be atleast 5 and atmost 17")

        if width < 5 or width > 17:
            return await ctx.send("Width must be atleast 5 and atmost 17")

        board, row_list, col_list = make_board(bg, height, width)
        view = DrawButtons(bg, board, row_list, col_list, ctx=ctx)

        response = await ctx.send(embed=view.embed, view=view)
        view.response = response
        await view.wait()

    @draw.command(
        name="copy",
        brief="Copy a drawing.",
        help="Copy a drawing from an embed by replying to with message ID and channel.",
        description="Allows you to copy a drawing that was done with the `draw` command.",
    )
    async def copy(
        self,
        ctx,
        message: Union[int, discord.Message] = None,
        message_channel: Union[int, discord.TextChannel] = None,
    ):
        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        elif message is not None:
            if message_channel is None:
                message_channel = ctx.channel
            else:
                message_channel = await ctx.bot.fetch_channel(
                    message_channel
                    if type(message_channel) == int
                    else message_channel.id
                )
            try:
                message = await message_channel.fetch_message(
                    message if type(message) == int else message.id
                )
            except:
                return await ctx.send(
                    "Please provide a valid message ID or reply to a message!"
                )

        if all(
            (
                message.embeds,
                "drawing board" in message.embeds[0].title,
                message.author == ctx.bot.user,
            )
        ):
            name = message.embeds[0].fields[0].name
            value = message.embeds[0].fields[0].value
            board = []
            for line in value.split("\n"):
                board.append(line[3:].split("\u200b"))
            board = np.array(board, dtype="object")
            bg = name[0]
        else:
            return await ctx.send(
                "Invalid message, make sure it's a draw embed and a message from the bot."
            )

        row_list = ROW_ICONS[: len(board)]
        col_list = COLUMN_ICONS[: len(board[0])]
        try:
            board[int(len(row_list) / 2), int(len(col_list) / 2)] = get_cursor[
                board[int(len(row_list) / 2), int(len(col_list) / 2)]
            ]
        except KeyError:
            pass
        options = discord.ui.View.from_message(message, timeout=0).children[0].options
        view = DrawButtons(
            bg, board, row_list, col_list, ctx=ctx, selectmenu_options=options
        )
        view.clear_cursors()
        view.draw_cursor()

        response = await ctx.send(embed=view.embed, view=view)
        view.response = response
        await view.wait()


class AddedEmoji:
    def __init__(
        self,
        *,
        status: str,
        emoji: discord.PartialEmoji,
        name: Optional[str] = None,
        sent_emoji: Optional[str] = None,
    ):
        self.status = status
        self.emoji = emoji
        self.original_name = emoji.name
        self.name = name or emoji.name
        self.emoji.name = self.name
        self.sent_emoji = sent_emoji

    def __str__(self):
        return str(self.emoji)

    @property
    def id(self):
        return self.emoji.id

    @id.setter
    def id(self, value: int):
        self.emoji.id = value

    @classmethod
    def from_option(
        cls,
        option: discord.SelectOption,
        *,
        status: Optional[str] = "",
        sent_emoji: str,
    ):
        return cls(status=status, emoji=option.emoji, sent_emoji=sent_emoji)


class DrawSelectMenu(discord.ui.Select):
    def __init__(self, *, options: Optional[typing.List[discord.SelectOption]] = None):
        options = (
            options
            if options
            else [
                discord.SelectOption(label="Red", emoji="🟥", value="🔴"),
                discord.SelectOption(label="Orange", emoji="🟧", value="🟠"),
                discord.SelectOption(label="Yellow", emoji="🟨", value="🟡"),
                discord.SelectOption(label="Green", emoji="🟩", value="🟢"),
                discord.SelectOption(label="Blue", emoji="🟦", value="🔵"),
                discord.SelectOption(label="Purple", emoji="🟪", value="🟣"),
                discord.SelectOption(label="Brown", emoji="🟫", value="🟤"),
                discord.SelectOption(label="Black", emoji="⬛", value="⚫"),
                discord.SelectOption(label="White", emoji="⬜", value="⚪"),
                discord.SelectOption(
                    label="Add Emoji",
                    emoji="<:emojismiley:920902406336815104>",
                    value="emoji",
                ),
            ]
        )
        super().__init__(
            placeholder="🎨 Palette",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.ctx = self.view.ctx
        select = self
        if select.values[0] == "emoji":
            resp = await interaction.followup.send(
                content="Please send a message containing the emojis you want to add to your palette. E.g. `😎 I like turtles 🐢`"
            )

            def check(m):
                return m.author == interaction.user

            try:
                msg = await self.ctx.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await interaction.followup.edit_message(
                    resp.id, content="Timed out."
                )

            unicode_emojis = list(emojis.get(msg.content))
            custom_emojis = list(re.findall(r"<a?:[a-zA-Z0-9_]+:\d+>", msg.content))
            emoji_ids = list(
                map(lambda n: f"{n}:{n}", re.findall(r"(?<![\:\d])(\d+)", msg.content))
            )

            sent_emojis = unicode_emojis + custom_emojis + emoji_ids
            added_emojis = {}
            for num, sent_emoji in enumerate(sent_emojis):
                emoji_check = discord.PartialEmoji.from_str(sent_emoji)
                emoji = copy.copy(emoji_check)

                emoji_identifier = emoji.id if emoji.id else emoji.name
                existing_emojis = [
                    (em.id if em.id else em.name)
                    for em in [opt.emoji for opt in select.options]
                ]
                if emoji_identifier in existing_emojis:
                    # This list comprehension mess checks if the emoji
                    # you're trying to add already exists in the options
                    # of the select menu. It uses the emoji's ID if it's
                    # a custom emoji, otherwise it uses the name which is
                    # the unicode emoji to see if it already exists in an option

                    added_emojis[emoji_identifier] = AddedEmoji(
                        status="Already exists", emoji=emoji, sent_emoji=sent_emoji
                    )
                    continue

                added_emojis[emoji_identifier] = AddedEmoji(
                    status="Added",
                    emoji=emoji,
                    name="_" if emoji.is_custom_emoji() else emoji.name,
                    sent_emoji=sent_emoji,
                )

            replaced_emojis = {}
            for added_emoji in added_emojis.values():
                if added_emoji.status != "Added":
                    continue

                if len(select.options) == 25:
                    replaced_option = select.options.pop(10)
                    replaced_emoji = replaced_option.emoji
                    replaced_emoji.name = replaced_option.label
                    replaced_emojis[
                        replaced_emoji.id if replaced_emoji.id else replaced_emoji.name
                    ] = AddedEmoji.from_option(
                        replaced_option,
                        status=f"Replaced (by {added_emoji}) because limit reached",
                        sent_emoji=replaced_emoji,
                    )
                    added_emoji.status = f"Added (replaced {replaced_emoji})"

                option = discord.SelectOption(
                    label=added_emoji.original_name,
                    emoji=added_emoji.emoji,
                    value=str(added_emoji.emoji),
                )
                select.append_option(option)

            added_emojis.update(replaced_emojis)

            if len(select.options[10:]) > 0:
                self.view.cursor = select.options[-1].value
                self.placeholder = select.options[-1].label

            response = [
                f"%s - {added_emoji.status}"
                % (
                    f"{added_emoji.emoji} ({added_emoji.id})"
                    if added_emoji.sent_emoji in emoji_ids
                    else added_emoji.emoji
                )
                for added_emoji in added_emojis.values()
            ]

            try:
                await interaction.edit_original_message(view=self.view)
            except discord.HTTPException as error:
                await interaction.followup.send(content=error)
                raise error
            await msg.delete()
            await interaction.followup.edit_message(
                resp.id, content="\n".join(response) if len(response) else "Aborted"
            )
        else:
            self.view.cursor = select.values[0]
            self.placeholder = self.view.cursor


class DrawButtons(discord.ui.View):
    def __init__(
        self,
        bg,
        board,
        row_list,
        col_list,
        *,
        ctx: commands.Context,
        selectmenu_options: Optional[typing.List[discord.SelectOption]] = None,
    ):
        super().__init__(timeout=600)
        children = self.children.copy()
        self.clear_items()
        self.add_item(DrawSelectMenu(options=selectmenu_options))
        for item in children:
            self.add_item(item)

        self.bg = bg
        self.initial_board = board
        self.board = self.initial_board.copy()
        self.row_list = row_list
        self.col_list = col_list
        self.cursor_row = int(len(row_list) / 2)
        self.cursor_col = int(len(col_list) / 2)
        self.ctx = ctx
        self.response = None
        self.cells = [(self.cursor_row, self.cursor_col)]
        self.cursor = self.board[self.cursor_row, self.cursor_col]
        self.cursor_row_max = row_list.index(row_list[-1])
        self.cursor_col_max = col_list.index(col_list[-1])
        self.initial_cell = (None, None)
        self.initial_row = self.initial_cell[0]
        self.initial_col = self.initial_cell[1]
        self.final_cell = (None, None)
        self.final_row = self.final_cell[0]
        self.final_col = self.final_cell[1]
        self.inv_get_cursor = invert_dict(get_cursor)

        self.auto = False
        self.fill = False

    @property
    def embed(self):
        embed = discord.Embed(title=f"{self.ctx.author}'s drawing board.")
        u200b = "\u200b"
        embed.add_field(
            name=f'{self.bg}  {"".join(self.col_list)}{u200b}',
            value="\n".join(
                [
                    f"{self.row_list[idx]}  {u200b.join(cell)}"
                    for idx, cell in enumerate(self.board)
                ]
            ),
        )
        embed.set_footer(
            text=(
                f"The board looks wack? Try decreasing its size! Do {self.ctx.clean_prefix}help draw for more info."
                if all((len(self.row_list) >= 10, len(self.col_list) >= 10))
                else f"You can customize this board! Do {self.ctx.clean_prefix}help draw for more info."
            )
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        selectmenu = self.children[0]
        selectmenu.disabled = True

        self.clear_items()
        self.add_item(selectmenu)
        self.add_item(
            discord.ui.Button(
                label=f"This interaction has timed out. Use {self.ctx.prefix}{self.ctx.command} for a new one.",
                style=discord.ButtonStyle.gray,
                disabled=True,
            )
        )
        self.clear_cursors()
        embed = self.embed
        await self.response.edit(embed=embed, view=self)
        self.stop()

    def cursor_conv(self, row_key):
        row = conv[row_key] - self.cursor_row
        return row

    def un_cursor(self, value):
        return self.inv_get_cursor.get(value, value)

    def draw_cursor(self, row: Optional[int] = None, col: Optional[int] = None):
        try:
            self.board[
                row if row else self.cursor_row, col if col else self.cursor_col
            ] = get_cursor[self.board[row if row else self.cursor_row, col if col else self.cursor_col]]
        except KeyError:
            pass

    def clear_cursors(self):
        for cell_tuple in self.cells:
            try:
                self.board[cell_tuple] = self.un_cursor(self.board[cell_tuple])
            except KeyError:
                continue
        self.cells = [(self.cursor_row, self.cursor_col)]

    async def move_cursor(
        self, interaction: discord.Interaction, row_move: int = 0, col_move: int = 0
    ):
        if self.fill is not True:
            self.board[self.cursor_row, self.cursor_col] = self.un_cursor(
                self.board[self.cursor_row, self.cursor_col]
            )
        self.cursor_row += (
            row_move if self.cursor_row + row_move <= self.cursor_row_max else 0
        )
        self.cursor_col += (
            col_move if self.cursor_col + col_move <= self.cursor_col_max else 0
        )
        if self.fill is not True:
            self.cells = [(self.cursor_row, self.cursor_col)]
        elif self.fill is True:
            self.final_cell = (self.cursor_row, self.cursor_col)
            self.final_row = self.final_cell[0]
            self.final_col = self.final_cell[1]

            self.clear_cursors()
            self.cells = [
                (row, col)
                for col in range(
                    min(self.initial_col, self.final_col),
                    max(self.initial_col, self.final_col) + 1,
                )
                for row in range(
                    min(self.initial_row, self.final_row),
                    max(self.initial_row, self.final_row) + 1,
                )
            ]

        if self.auto is True:
            await self.edit_draw(interaction, self.cursor)

        for cell_tuple in self.cells:
            self.draw_cursor(*cell_tuple)
        embed = self.embed
        if self.auto is not True:
            await interaction.edit_original_message(embed=embed)

    async def edit_draw(self, interaction, draw=None, corner=None):
        if all(cell == draw for cell in self.cells):
            return
        if draw is None:
            draw = self.board[self.cursor_row][self.cursor_col]
        if corner is None:
            corner = self.cursor
        for cell_tuple in self.cells:
            self.board[cell_tuple[0], cell_tuple[1]] = draw
        embed = self.embed
        await interaction.edit_original_message(embed=embed, view=self)

    # ------ buttons ------

    @discord.ui.button(
        emoji="<:stop:921864670145552444>", style=discord.ButtonStyle.danger
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.clear_cursors()
        embed = self.embed
        await interaction.edit_original_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(
        emoji="<:clear:922414780193579009>", style=discord.ButtonStyle.danger
    )
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.auto = False
        self.auto_colour.style = discord.ButtonStyle.gray
        self.fill = False
        self.fill_bucket.style = discord.ButtonStyle.grey
        self.cursor_row = int(len(self.row_list) / 2)
        self.cursor_col = int(len(self.col_list) / 2)
        self.board, _, _ = make_board(self.bg, len(self.col_list), len(self.row_list))
        self.clear_cursors()
        self.draw_cursor()
        embed = self.embed
        await interaction.edit_original_message(embed=embed, view=self)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder1(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder2(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:fill:930832869692149790>", style=discord.ButtonStyle.gray
    )
    async def fill_bucket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if self.fill == False:
            self.fill = True
            self.initial_cell = (self.cursor_row, self.cursor_col)
            self.initial_row = self.initial_cell[0]
            self.initial_col = self.initial_cell[1]
            self.fill_bucket.style = discord.ButtonStyle.green
        elif self.fill == True:
            self.fill = False
            self.clear_cursors()
            self.draw_cursor()
            self.fill_bucket.style = discord.ButtonStyle.grey
        await self.edit_draw(interaction)
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder3(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:up_left:920896021700161547>", style=discord.ButtonStyle.blurple
    )
    async def up_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = -1
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:up:920895538696704053>", style=discord.ButtonStyle.blurple
    )
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = -1
        col_move = 0
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:up_right:920895852128657480>", style=discord.ButtonStyle.blurple
    )
    async def up_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = -1
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder5(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:erase:927526530052132894>", style=discord.ButtonStyle.gray
    )
    async def erase(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.edit_draw(interaction, get_cursor[self.bg])

    @discord.ui.button(
        emoji="<:left:920895993145327628>", style=discord.ButtonStyle.blurple
    )
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 0
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:auto_cursor:921352341427470347>", style=discord.ButtonStyle.gray
    )
    async def auto_colour(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if self.auto == False:
            self.auto = True
            self.auto_colour.style = discord.ButtonStyle.green
        elif self.auto == True:
            self.auto = False
            self.auto_colour.style = discord.ButtonStyle.grey
        await interaction.edit_original_message(view=self)

    @discord.ui.button(
        emoji="<:right:920895888229036102>", style=discord.ButtonStyle.blurple
    )
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 0
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder6(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:middle:920897054060998676>", style=discord.ButtonStyle.green
    )
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.edit_draw(interaction, self.cursor)

    @discord.ui.button(
        emoji="<:down_left:920895965987242025>", style=discord.ButtonStyle.blurple
    )
    async def down_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = 1
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:down:920895939030429696>", style=discord.ButtonStyle.blurple
    )
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 1
        col_move = 0
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:down_right:920895913608765551>", style=discord.ButtonStyle.blurple
    )
    async def down_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = 1
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:ABCD:920896121285537832>", style=discord.ButtonStyle.blurple
    )
    async def set_cursor(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        res = await self.ctx.send(
            'Please type the cell you want to move the cursor to. e.g. "A1", "a8", "A10", etc.'
        )

        def check(m):
            return m.author == interaction.user

        try:
            msg = await self.ctx.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            return await self.ctx.send("Timed out.")
        cell = msg.content.upper()
        if len(cell) != 2 and len(cell) != 3:
            return await self.ctx.send("Min and max length of cell must be 2 and 3")

        row_key = cell[0]
        col_key = cell[1:]
        if (
            row_key not in ABC[: self.cursor_row_max + 1]
            or col_key not in NUM[: self.cursor_col_max + 1]
        ):
            return await self.ctx.send(f"Invalid cell provided.")
        row_move = self.cursor_conv(row_key)
        col_move = int(col_key) - self.cursor_col
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)
        await res.delete()
        await asyncio.sleep(0.5)
        await msg.delete()


async def setup(bot):
    await bot.add_cog(Draw(bot))
