"""Small Components V2 layouts used by Clipy."""
from __future__ import annotations

import discord
from services.search import ClipResult

ACCENT = discord.Colour.from_rgb(55, 145, 220)


def duration_text(seconds: int | None) -> str:
    if seconds is None:
        return "length n/a"
    minutes, seconds = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


class ClipResultsView(discord.ui.LayoutView):
    def __init__(self, query: str, results: list[ClipResult], requester_id: int):
        super().__init__(timeout=180)
        self.query, self.results, self.requester_id, self.page = query, results, requester_id, 0
        self.render()

    def render(self):
        self.clear_items()
        box = discord.ui.Container(
            discord.ui.TextDisplay(f"## Results for {discord.utils.escape_markdown(self.query)}"),
            discord.ui.Separator(),
            accent_colour=ACCENT,
        )
        start = self.page * 3
        for i, result in enumerate(self.results[start:start + 3], start=start + 1):
            title = discord.utils.escape_markdown(result.title[:160])
            channel = discord.utils.escape_markdown(result.channel[:70])
            box.add_item(discord.ui.Separator())
            box.add_item(discord.ui.TextDisplay(
                f"**{i}. [{title}]({result.url})**\n"
                f"{channel} · {duration_text(result.duration)}"
            ))
        pages = max(1, (len(self.results) + 2) // 3)
        if pages > 1:
            row = discord.ui.ActionRow()
            prev = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, disabled=self.page == 0)
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, disabled=self.page >= pages - 1)
            counter = discord.ui.Button(label=f"{self.page + 1}/{pages}", style=discord.ButtonStyle.secondary, disabled=True)

            async def move(interaction: discord.Interaction, delta: int):
                if interaction.user.id != self.requester_id:
                    await interaction.response.send_message("These buttons belong to the person who ran the search.", ephemeral=True)
                    return
                self.page = max(0, min(pages - 1, self.page + delta))
                self.render()
                await interaction.response.edit_message(view=self)

            async def go_prev(interaction: discord.Interaction):
                await move(interaction, -1)

            async def go_next(interaction: discord.Interaction):
                await move(interaction, 1)

            prev.callback = go_prev
            next_button.callback = go_next
            row.add_item(prev)
            row.add_item(counter)
            row.add_item(next_button)
            box.add_item(row)
        self.add_item(box)

    async def on_timeout(self):
        self.stop()


def status_view(title: str, message: str, *, ephemeral_colour: bool = False) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=120)
    view.add_item(discord.ui.Container(
        discord.ui.TextDisplay(f"## {title}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(message),
        accent_colour=ACCENT if not ephemeral_colour else discord.Colour.orange(),
    ))
    return view
