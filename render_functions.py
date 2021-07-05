from __future__ import annotations

from typing import TYPE_CHECKING

import colors

if TYPE_CHECKING:
    from tcod import Console
    from engine import Engine
    from game_map import GameMap

def get_names_at_location(x: int, y: int, game_map: GameMap) -> str:
    if not game_map.in_bounds(x, y) or not game_map.visible[x, y]:
        return ""

    names = ", ".join(
        entity.name for entity in game_map.entities if entity.x == x and entity.y == y
    )

    return names.capitalize()

def render_bar(
    console: Console, current_mana: int, maximum_mana: int, current_hp: int, maximum_hp: int, total_width: int, dungeon_level: int,
    xp: int, xp_to_level: int, player_level, player_gold, game_turn,
) -> None:

    if maximum_mana > 0:
        console.draw_rect(x = 0, y = 44, width = 20, height = 1, ch = 1, bg = colors.bar_empty)

        mana_bar_width = int(float(current_mana) / maximum_mana * total_width)

        if mana_bar_width > 0:
            console.draw_rect(
                x = 0, y = 44, width = mana_bar_width, height = 1, ch = 1, bg = colors.bar_filled
            )

        console.print(
            x = 1, y = 44, string = f"MANA: {current_mana}/{maximum_mana}", fg = colors.bar_text
        )

    console.draw_rect(x = 0, y = 45, width = 20, height = 1, ch = 1, bg = colors.bar_empty)

    hp_bar_width = int(float(current_hp) / maximum_hp * total_width)

    if hp_bar_width > 0:
        console.draw_rect(
            x = 0, y = 45, width = hp_bar_width, height = 1, ch = 1, bg = colors.bar_filled
        )

    console.print(
        x = 1, y = 45, string = f"HP: {current_hp}/{maximum_hp}", fg = colors.bar_text
    )
    console.print(
        x = 1, y = 46, string = f"Dungeon: {dungeon_level}, Player: {player_level}", fg = colors.white
    )
    console.print(
        x = 1, y = 47, string = f"Current xp: {xp}/{xp_to_level}", fg = colors.white
    )
    console.print(
        x = 1, y = 48, string = f"Turn: {game_turn}", fg = colors.white
    )
    console.print(
        x = 1, y = 49, string = f"Player Gold: ${player_gold}", fg = colors.white
    )

def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = engine.mouse_location

    names_at_mouse_location = get_names_at_location(
        x = mouse_x, y = mouse_y, game_map = engine.game_map
    )

    console.print(x = x, y = y, string = names_at_mouse_location)
