from __future__ import annotations

from typing import TYPE_CHECKING

from tcod.console import Console
from tcod.map import compute_fov

import exceptions
from message_log import MessageLog
from render_functions import render_bar, render_names_at_mouse_location
from loader_functions.initialize_new_game import get_constants

if TYPE_CHECKING:
    from entity import Actor, Item
    from game_map import GameMap, GameWorld
    #from input_handlers import EventHandler

class Engine:
    game_map: GameMap
    game_world: GameWorld
    
    def __init__(self, player: Actor):
        self.message_log = MessageLog()
        self.mouse_location = (0, 0)
        self.player = player
        self.screen_reset = False
        self.enchant_now = False
        self.enchanting_item: Item = None
        self.last_keypress: str = "None"
        self.num_pressed: int = 0
        self.last_target = player
        self.last_level: int = 0
        self.current_turn: int = 0

    def handle_enemy_turns(self) -> None:
        for entity in set(self.game_map.actors) - {self.player}:
            if entity.ai:
                try:
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass # Ignore impossible action exceptions from AI.

    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius = 12,
        )
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible

    def render(self, console: Console) -> None:
        self.game_map.render(console)

        constants = get_constants()

        self.message_log.render(console = console, x = 25, y = constants['screen_height'] - constants['message_height'], width = 40, height = 5)

        render_bar(
            console = console,
            current_mana = self.player.battler.mana,
            maximum_mana = self.player.battler.max_mana,
            current_hp = self.player.battler.hp,
            maximum_hp = self.player.battler.max_hp,
            total_width = 20,
            dungeon_level = self.game_map.dungeon_level,
            xp = self.player.level.current_xp,
            xp_to_level = self.player.level.experience_to_next_level,
            player_level = self.player.level.current_level,
            player_gold = self.player.battler.gold,
            game_turn = self.current_turn
        )

        render_names_at_mouse_location(console = console, x = 25, y = constants['screen_height'] - constants['message_height'] - 1, engine = self)
