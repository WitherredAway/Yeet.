import asyncio

import discord
from discord.ext import commands


class RepeatView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bot = self.ctx.bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        await self.message.edit(view=None)

    @discord.ui.button(label="Run again", style=discord.ButtonStyle.blurple)
    async def repeat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.ctx.bot.process_commands(self.ctx.message)


class Developer(commands.Cog):
    """Developer only category."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hidden = True

    display_emoji: discord.PartialEmoji = "⚒️"

    @commands.command(
        name="togglecommand",
        aliases=("tc",),
        description="Enable or disable a command.",
    )
    @commands.is_owner()
    async def toggle(self, ctx: commands.Context, *, command: str):
        command = self.bot.get_command(command)

        if command is None:
            return await ctx.send(f":x: Command `{command}` not found.")

        elif command == ctx.command:
            return await ctx.send(f":x: This command cannot be disabled.")

        else:
            command.enabled = not command.enabled
            await ctx.send(
                f'{"↪️ Enabled" if command.enabled else "↩️ Disabled"} command `{command.qualified_name}`.'
            )

    # Cog related commands group
    @commands.is_owner()
    @commands.group(
        name="cog",
        aliases=("c",),
        invoke_without_command=True,
        case_insensitive=True,
        help="Commands related to cogs, dev only command.",
    )
    async def cog(self, ctx: commands.Context):
        await ctx.send_help(ctx.command)

    # Cog load command for loading cogs
    @commands.is_owner()
    @cog.command(
        name="load",
        aliases=("l",),
        brief="Load a cog",
        help="Loads a cog with the name, dev only command.",
    )
    async def _load(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.load_extension(f"cogs.{cog}")
        except commands.ExtensionNotFound:
            message = f":x: Cog `{cog}` not found."
        except commands.ExtensionAlreadyLoaded:
            message = f"Cog `{cog}` is already loaded."
        else:
            message = f":inbox_tray: Loaded cog `{cog}`"

        view = RepeatView(ctx)
        view.message = await ctx.send(message, view=view)

    # Cog unload command for unloading cogs
    @commands.is_owner()
    @cog.command(
        name="unload",
        aliases=("u",),
        brief="Unloads a cog",
        help="Unloads a cog with the name, dev only command.",
    )
    async def _unload(self, ctx: commands.Context, cog: str):
        if cog.lower() == "admin":
            message = ":x: Cannot unload this cog"
        else:
            try:
                await self.bot.unload_extension(f"cogs.{cog}")
            except commands.ExtensionNotLoaded:
                message = f":x: Cog `{cog}` not found."
            except Exception as e:
                raise e
            else:
                message = f":outbox_tray: Unloaded cog `{cog}`"

        view = RepeatView(ctx)
        view.message = await ctx.send(message, view=view)

    # Cog reload command for reloading cogs
    @commands.is_owner()
    @cog.command(
        name="reload",
        aliases=("r",),
        brief="Reloads a cog",
        help="Reloads a cog with the name, dev only command.",
    )
    async def _reload(self, ctx: commands.Context, cog):
        if cog == "all":
            cogs = []
            for cog_ext in list(self.bot.extensions):
                await self.bot.reload_extension(cog_ext)
                cog_name = cog_ext[5:] if cog_ext.startswith("cogs.") else cog_ext
                cogs.append(f"\n🔁 Reloaded cog `{cog_name}`")
            message = ", ".join(cogs)
        else:
            try:
                await self.bot.reload_extension(f"cogs.{cog}")
            except commands.ExtensionNotLoaded:
                message = f":x: Cog `{cog}` not found."
            else:
                message = f":repeat: Reloaded cog `{cog}`"

        view = RepeatView(ctx)
        view.message = await ctx.send(message, view=view)

    # cog all
    @commands.is_owner()
    @cog.command(
        name="all",
        aliases=["a"],
        hidden=True,
        brief="All cogs",
        help="Lists all cogs, dev only command.",
    )
    async def _all(self, ctx):
        extlist = self.bot.Embed(title="Cogs", description="List of all enabled cogs")

        for ext in self.bot.extensions:
            extn = (
                ext.split(".")[1].capitalize()
                if ext.startswith("cogs")
                else ext.capitalize()
            )
            extlist.add_field(name=extn, value=str(ext), inline=False)
        await ctx.send(embed=extlist)


async def setup(bot: commands.Bot):
    await bot.add_cog(Developer(bot))
