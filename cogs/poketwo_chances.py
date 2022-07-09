import asyncio
import os
import typing
from typing import Counter, Union, Optional
from functools import cached_property
import json

import discord
from discord.ext import commands, tasks
import numpy as np
import pandas as pd
import gists

from cogs.utils.paste import paste_to_bin
from constants import NEW_LINE


class PoketwoChances(commands.Cog):
    """Commands related to the poketwo bot."""

    def __init__(self, bot):
        self.bot = bot

        self.pokemon_csv = (
            # "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"
            os.getenv("POKEMON_CSV")
        )

    display_emoji = "🔣"

    async def cog_load(self):
        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("WgithubTOKEN"))

    @cached_property
    def pk(self):
        pk = pd.read_csv(self.pokemon_csv)
        self.possible_abundance = round(
            (pk.loc[:, "abundance"][pk.loc[:, "catchable"] > 0]).sum(), 4
        )
        return pk

    async def update_chance_gist(
        self,
        df: pd.DataFrame,
        *,
        description: Optional[str] = "Spawn chances",
        gist_id: str,
        keep_cols: Optional[typing.List[str]] = None,
    ) -> gists.Gist:
        for idx in df.index:
            chance = round(df.at[idx, "abundance"] / self.possible_abundance * 100, 4)
            df.at[idx, "Chance"] = "1/" + str(round(1 / chance * 100))
            df.at[idx, "Chance percentage"] = str(chance) + "%"

        df.sort_values("abundance", ascending=False, inplace=True)
        if keep_cols is None:
            keep_cols = []
        drop_cols = ["abundance", "catchable"]
        df.drop(columns=drop_cols, inplace=True)

        rename_cols = {"name.en": "Pokemon", "id": "Dex"}
        if "enabled" in keep_cols:
            rename_cols["enabled"] = "Currently catchable"
        df.rename(columns=rename_cols, inplace=True)

        df_groupby = df.set_index("Pokemon").groupby("Chance percentage")
        df_groupby = [
            (float(chance[:-1]), pokemons)
            for chance, pokemons in df_groupby.groups.items()
        ]
        df_groupby.sort(key=lambda x: x[0], reverse=True)
        df_groupby = {
            f"{chance}% - 1/{round(1/chance*100)} [{len(pokemons)}]": sorted(pokemons)
            for chance, pokemons in df_groupby
        }

        df_grouped = pd.DataFrame.from_dict(df_groupby, orient="index")
        df_grouped = df_grouped.transpose()

        contents = """## Contents
- [Pokémon chances table](#file-pokemon_chances-csv)
- [Pokémon chances table, grouped by chance](#file-pokemon_chances_grouped-csv)"""

        files = [
            gists.File(name="contents.md", content=contents),
            gists.File(name="pokemon_chances.csv", content=df.to_csv(index=False)),
            gists.File(
                name="pokemon_chances_grouped.csv",
                content=df_grouped.to_csv(index=False),
            ),
        ]
        new_gist = gists.Gist.__new__(gists.Gist)
        new_gist.files = files
        new_gist.description = description

        gist = await self.gists_client.get_gist(gist_id)

        if gist == new_gist:
            return
        await gist.edit(files=files, description=description)

    async def format_msg(
        self,
        title: str,
        pokemon_dataframe: pd.DataFrame,
        *,
        gist_link: Optional[str] = None,
        list_pokemon: bool = True,
        keep_cols: Optional[typing.List[str]] = None,
    ) -> str:
        pkm_df = pokemon_dataframe
        total_abundance = round(pkm_df["abundance"][pkm_df["catchable"] > 0].sum())

        per_cent = round(total_abundance / self.possible_abundance * 100, 3)
        out_of = round(1 / per_cent * 100)
        total_chances = f"**Total chance**: {per_cent}% (1/{out_of})"

        extra = "\n"
        if list_pokemon is True:
            gist_id = gist_link.split("/")[-1]
            await self.update_chance_gist(
                pkm_df,
                description=f"Spawn chances of {title} pokémon. {total_chances}",
                gist_id=gist_id,
                keep_cols=keep_cols,
            )
            all_pokemon = f"> All pokémon: <{gist_link}>"
            extra = f" (Includes all catchable forms)\n{all_pokemon}\n**Total pokemon**: {len(pkm_df)}"

        result = f"__**{title}**__{extra}\n{total_chances}"
        return result

    @commands.group(
        aliases=("chances",),
        help="See the chances of pokémon or a rarity.",
        invoke_without_command=True,
    )
    async def chance(self, ctx):
        await ctx.send_help(ctx.command)

    @chance.command(name="all", help="See the chances of all pokémon in a nice table")
    async def all(self, ctx):
        pkm_df = self.pk.loc[self.pk["catchable"] > 0]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        ALL_GIST = "https://gist.github.com/1bc525b05f4cd52555a2a18c331e0cf9"

        async with ctx.channel.typing():
            result = await self.format_msg("All", pkm_df, gist_link=ALL_GIST)
        await ctx.send(result)

    @chance.command(
        name="rarity",
        help="See the chances of a rarity and the pokémon that belong to that rarity.",
    )
    async def _rarity(self, ctx, rarity):
        options_gists = {
            "Mythical": "https://gist.github.com/ba3f32d61cfdaf857c8541d168c21698",
            "Legendary": "https://gist.github.com/af25f3f398fbc0441fd0248a5ca3faad",
            "Ultra_beast": "https://gist.github.com/ba3f1b7063e939d8119286bbeb8e8080",
        }
        options = options_gists.keys()
        for option in options:
            if rarity.lower() in option.lower():
                rarity = option
                break
        else:
            return await ctx.send(
                f'Invalid rarity provided. Valid rarities: {", ".join(options)}.'
            )

        pkm_df = self.pk.loc[
            (self.pk["catchable"] > 0) & (self.pk[rarity.lower()] == 1)
        ]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        async with ctx.channel.typing():
            result = await self.format_msg(
                rarity, pkm_df, gist_link=options_gists.get(rarity)
            )
        await ctx.send(result)

    @chance.command(
        name="form",
        help="See the chances of a form and the individual pokémon. Options: Alolan, Galarian & Hisuian.",
    )
    async def _form(self, ctx, form):
        options_gists = {
            "Alolans": "https://gist.github.com/7c3cdaaa36c38d2fb2bd716652b09d00",
            "Galarians": "https://gist.github.com/4fb6735b2241506105af52626953618b",
            "Hisuians": "https://gist.github.com/4bcf5ef86577b14aa464a3376adb430e",
        }
        options = options_gists.keys()
        for option in options:
            if form.lower() in option.lower():
                form = option
                break
        else:
            return await ctx.send(
                f'Invalid form provided. Options: {", ".join(options)}'
            )

        pkm_df = self.pk.loc[
            (self.pk["catchable"] > 0)
            & (self.pk["slug"].str.endswith(form.lower()[:5]))
        ]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        async with ctx.channel.typing():
            result = await self.format_msg(
                form, pkm_df, gist_link=options_gists.get(form)
            )
        await ctx.send(result)

    @chance.command(
        name="region",
        aliases=("gen",),
        brief="See the chances of the pokémon from a region.",
        help="See the chances of the pokémon from a region. Options: Kanto/1, Johto/2, Hoenn/3, Sinnoh/4, Unova/5, Kalos/6, Alola/7, Galar/8, Hisui",
    )
    async def _region(self, ctx, region: Union[int, str]):
        options_gists = {
            "Kanto": "https://gist.github.com/2c48fc73eb1a9e94737634092e1c62e3",
            "Johto": "https://gist.github.com/4456e7da504e9ff5ddc653cd3bc4e76c",
            "Hoenn": "https://gist.github.com/ce4facd1f383676bb745cece67fbac50",
            "Sinnoh": "https://gist.github.com/e9a435742bea160eb588c8812e0730c4",
            "Unova": "https://gist.github.com/6af2072d0229c3f5582b32f20b65f2f5",
            "Kalos": "https://gist.github.com/849a6b64a35a505c7afb2eb276eda18d",
            "Alola": "https://gist.github.com/a55287b7bff61b90b3182bca602b062a",
            "Galar": "https://gist.github.com/f4d75c84e7ed4ce57273b6ef860a5a54",
            "Hisui": "https://gist.github.com/46bbc638f81687aa42709a83078aa1f8",
        }
        options = list(options_gists.keys())
        if isinstance(region, int):
            if region < 9:
                region = options[region - 1]
            else:
                return await ctx.send("Invalid generation provided. Options: 1-8")
        else:
            region = region.capitalize()

        pkm_df = self.pk.loc[
            (self.pk["catchable"] > 0) & (self.pk["region"] == region.lower())
        ]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid region provided. Options: {", ".join(options)}'
            )

        async with ctx.channel.typing():
            result = await self.format_msg(
                f"{region} region", pkm_df, gist_link=options_gists.get(region)
            )
        await ctx.send(result)

    @chance.command(
        name="pokemon",
        aliases=("poke", "pkm"),
        help="See the chances of a specific pokémon.",
    )
    async def _pokemon(self, ctx, *, pokemon: str):
        pokemon = pokemon.lower()

        pkm_df = self.pk.loc[
            (self.pk["catchable"] > 0)
            & (
                (self.pk["slug"].str.casefold() == pokemon)
                | (self.pk["name.en"].str.casefold() == pokemon)
            )
        ]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        if len(pkm_df) == 0:
            return await ctx.send("Invalid pokémon provided.")

        async with ctx.channel.typing():
            result = await self.format_msg(
                ", ".join([pkm_row["name.en"] for _, pkm_row in pkm_df.iterrows()]),
                pkm_df,
                list_pokemon=False,
            )
        await ctx.send(result)

    async def get_types_gist(self, type_1: str, type_2: str):
        TYPES_GISTS_LINK = (
            "https://gist.github.com/WitherredAway/286394d65db106061d8e76918dab9050"
        )

        types_gist = await self.gists_client.get_gist(TYPES_GISTS_LINK.split("/")[-1])
        file = types_gist.files[0]
        types_gists_json = json.loads(file.content)

        types_identifier = f"{type_1}-{type_2}"
        gist_link = types_gists_json.get(types_identifier, False)
        if gist_link is False:  # Check which identifier is correct
            gist_link = types_gists_json.get(f"{type_2}-{type_1}", None)

        if gist_link is None:
            gist_link = (
                await self.gists_client.create_gist(
                    files=[
                        gists.File(name="pokemon_chances.csv", content="."),
                        gists.File(name="pokemon_chances_grouped.csv", content="."),
                    ],
                    public=False,
                )
            ).url
            types_gists_json[types_identifier] = gist_link
            file.content = json.dumps(types_gists_json, indent=4)
            await types_gist.edit(files=[file])
        return gist_link

    @chance.command(
        name="type",
        aliases=("types", "ty", "t"),
        brief="See the chances of pokémon with certain type(s)",
        help="See the chances of pokémon with certain type(s). Types: Normal, Fire, Water, Grass, Flying, Fighting, Poison, Electric, Ground, Rock, Psychic, Ice, Bug, Ghost, Steel, Dragon, Dark and Fairy.",
    )
    async def _type(self, ctx, type_1: str, type_2: str = None):
        type_1 = type_1.capitalize()
        types = [type_1]
        if not type_2:
            msg = type_1
            pkm_df = self.pk.loc[
                (self.pk["type.0"] == type_1) | (self.pk["type.1"] == type_1)
            ]
        else:
            type_2 = type_2.capitalize()
            types.append(type_2)
            msg = " & ".join((type_1, type_2))
            pkm_df = self.pk.loc[
                ((self.pk["type.0"] == type_1) & (self.pk["type.1"] == type_2))
                | ((self.pk["type.0"] == type_2) & (self.pk["type.1"] == type_1))
            ]

        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid type(s) provided `{"` and `".join(types)}`.'
            )
        pkm_df = pkm_df.loc[pkm_df["catchable"] > 0]
        if len(pkm_df) == 0:
            return await ctx.send(
                f'No catchable pokémon found with type(s) `{"` and `".join(types)}`'
            )
        pkm_df.rename(columns={"type.0": "Type 1", "type.1": "Type 2"}, inplace=True)
        pkm_df = pkm_df.loc[
            :, ["id", "name.en", "Type 1", "Type 2", "catchable", "abundance"]
        ]

        async with ctx.channel.typing():
            result = await self.format_msg(
                f"{msg} Type(s)",
                pkm_df,
                gist_link=await self.get_types_gist(type_1, type_2),
            )
        await ctx.send(result)

    @chance.command(
        name="event", aliases=("ev",), help="Chances of pokemon of the current event"
    )
    async def event(self, ctx):
        pkm_df = self.pk.loc[(self.pk["event"] > 0) & (self.pk["catchable"] > 0)]
        if len(pkm_df) == 0:
            return await ctx.send("No currently catchable event pokemon")
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance", "enabled"]]
        pkm_df["enabled"] = pkm_df["enabled"] > 0

        EVENT_GIST = "https://gist.github.com/caf8fc84a8072cfcd1d07b2d18730d5e"

        async with ctx.channel.typing():
            result = await self.format_msg(
                "Event", pkm_df, keep_cols=["enabled"], gist_link=EVENT_GIST
            )
        await ctx.send(result)


async def setup(bot):
    await bot.add_cog(PoketwoChances(bot))
