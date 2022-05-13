from __future__ import annotations

from typing import Optional
import random
import string

import discord
from discord.ext import commands
from english_words import english_words_alpha_set

from ..utils import *


class BoggleButton(discord.ui.Button['BoggleView']):

    def __init__(self, label: str, style: discord.ButtonStyle, *, row: int, col: int) -> None:
        super().__init__(
            style=style,
            label=label,
            row=row,
        )

        self.col = col

    def __repr__(self) -> str:
        return self.label

    async def callback(self, interaction: discord.Interaction) -> None:
        game = self.view.game

        if interaction.user != game.player:
            return await interaction.response.send_message('This is not your game!', ephemeral=True)
        else:
            if self.style == game.button_style:
                if game.indices:
                    beside_current = game.beside_current(*game.indices[-1])
                else:
                    beside_current = [(self.row, self.col)]

                if (self.row, self.col) in beside_current:
                    game.current_word += self.label
                    game.indices.append((self.row, self.col))

                    self.style = game.selected_style
                else:
                    return await interaction.response.defer()

            elif (self.row, self.col) == game.indices[-1]:
                self.style = game.button_style
                game.current_word = game.current_word[:-1]
                game.indices.pop(-1)
            else:
                return await interaction.response.defer()
            
            embed = game.get_embed()
            await interaction.response.edit_message(view=self.view, embed=embed)

class BoggleView(BaseView):

    def __init__(self, game: Boggle, *, timeout: float) -> None:
        super().__init__(timeout=timeout)

        self.game = game

        for i, row in enumerate(self.game.board):
            for j, letter in enumerate(row):
                button = BoggleButton(
                    label=letter, 
                    style=self.game.button_style,
                    row=i, 
                    col=j,
                )
                self.add_item(button)

    @property
    def nested_children(self) -> list[list[BoggleButton]]:
        return chunk(self.children[2:], count=4)

    @discord.ui.button(label='Enter', style=discord.ButtonStyle.blurple, row=4)
    async def enter_button(self, interaction: discord.Interaction, _) -> None:
        game = self.game

        if not game.current_word:
            return await interaction.response.send_message('You have no current guesses!', ephemeral=True)

        if len(game.current_word) < 3:
            return await interaction.response.send_message('Word must be of at least 3 letters in length!', ephemeral=True)

        if game.current_word.lower() in english_words_alpha_set:
            game.correct_guesses.append(game.current_word)
        else:
            game.wrong_guesses.append(game.current_word)

        game.current_word = ''
        game.indices = []
        game.reset()

        embed = game.get_embed()
        return await interaction.response.edit_message(view=self, embed=embed)

    @discord.ui.button(label='Stop', style=discord.ButtonStyle.red, row=4)
    async def stop_button(self, interaction: discord.Interaction, _) -> None:
        self.disable_all()

        await interaction.response.edit_message(view=self)
        return self.stop()

class Boggle:
    
    def __init__(self) -> None:
        self.board = [random.choices(string.ascii_uppercase, k=4) for _ in range(4)]

        self.button_style: discord.ButtonStyle = discord.ButtonStyle.gray
        self.selected_style: discord.ButtonStyle = discord.ButtonStyle.green

        self.correct_guesses: list[str] = []
        self.wrong_guesses: list[str] = []

        self.current_word: str = ''
        self.indices: list[tuple[int, int]] = []

        self.embed_color: Optional[DiscordColor] = None

    def reset(self) -> None:
        for button in self.view.children[2:]:
            if isinstance(button, discord.ui.Button):
                button.style = self.button_style

    def get_embed(self) -> discord.Embed:
        correct_guesses = '\n- '.join(self.correct_guesses)
        wrong_guesses = '\n- '.join(self.wrong_guesses)

        embed = discord.Embed(title='Boggle!', color=self.embed_color)
        embed.description = f'```yml\nCurrent-word: {self.current_word}\n```'
        embed.add_field(
            name='Correct Guesses',
            value=f'```yml\n- {correct_guesses}\n```',
        )
        embed.add_field(
            name='Wrong Guesses',
            value=f'```yml\n- {wrong_guesses}\n```',
        )
        return embed

    def beside_current(self, row: int, col: int) -> list[tuple[int, int]]:
        
        indexes = (
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
            (row + 1, col + 1),
            (row - 1, col - 1),
            (row + 1, col - 1),
            (row - 1, col + 1),
        )

        components = self.view.nested_children[:]
        return [
            (i, j) for (i, j) in indexes if i in range(4) and j in range(4) and 
            components[i][j].style != self.selected_style
        ]

    async def start(
        self, 
        ctx: commands.Context,
        *,
        embed_color: DiscordColor = DEFAULT_COLOR,
        button_style: discord.ButtonStyle = discord.ButtonStyle.gray,
        selected_style: discord.ButtonStyle = discord.ButtonStyle.green,
        timeout: Optional[float] = None,
    ) -> bool:

        self.embed_color = embed_color

        self.button_style = button_style
        self.selected_style = selected_style
        self.player = ctx.author

        self.view = BoggleView(self, timeout=timeout)
        self.message = await ctx.send(view=self.view, embed=self.get_embed())

        return await self.view.wait()