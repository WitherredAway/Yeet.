import re
import os

import pandas as pd
import discord
from discord.ext import commands


class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.hidden = True
        self.pk = pd.read_csv(os.getenv("POKEMON_CSV"))
        self.pk = self.pk.loc[self.pk["catchable"] > 0]
        self.pattern = re.compile("The pokémon is (.+)\.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != 716390085896962058:
            return
        content = message.content
        hint = self.pattern.search(content)
        if hint is None:
            return
        hint = hint.group(1).replace("\\", "").replace("_", ".")
        hint = f'{hint}$'
        pkms = self.pk[self.pk["name.en"].str.match(hint)].sort_values("abundance", ascending=False)
        pkm = pkms.iloc[0]
        
        _types = ("Steel", "Fighting")
        _types_not = ("Psychic", "Ice", "Rock")
        _regions = ()
        _regions_not = ("Alola", "Galar", "Hoenn", "Johto", "Unova")
        r_types = ("Dark", "Ice", "Fire")
        r_regions = ("Alola", "Hoenn", "Johto")
        
        embed = self.bot.Embed()
        embed.color = 0x00FF00
        
        name = pkm["name.en"]
        type_0, type_1 = pkm['type.0'], pkm['type.1']
        region = pkm['region'].capitalize()
        msg = "<@267550284979503104>"
        
        embed.add_field(name=name, value=f'{type_0}\n{type_1 if isinstance(type_1, str) else ""}\n\n{region}')
        if (
            type_0 in r_types
            or type_1 in r_types
            or region in r_regions
        ) and not (
            type_0 in _types
            or type_1 in _types
            or region in _regions
        ):
            msg = "<@850079219681722398>"
            embed.color = 0x606080
        elif (
            type_0 in _types_not
            or type_1 in _types_not
            or region in _regions_not
        ):
            msg = ""
            embed.color = 0xFF0000

        await message.channel.send(msg, embed=embed)


async def setup(bot):
    await bot.add_cog(Test(bot))
        