#!/usr/bin/env python3
#import copy
import traceback

import tcod
import tcod.event

from typing import Iterable, Iterator
import colors
#from engine import Engine
import entity_factories
import exceptions
import input_handlers
from loader_functions.initialize_new_game import get_constants # get_game_variables
from loader_functions.player_init import get_player
#from loader_functions.data_loaders import load_game
from input_handlers import MainGameEventHandler, TownPortalEventHandler
#from procgen import generate_dungeon, graphics_test, generate_town, place_holder
import setup_game

def main() -> None:

    handler: input_handlers.BaseEventHandler = setup_game.MainMenu()
    constants = get_constants()
        
    while True:
        with tcod.context.new_terminal(
            constants['screen_width'],
            constants['screen_height'],
            tileset = constants['tileset'],
            title = constants['window_title'],
            vsync = True,
        ) as context:
            root_console = tcod.Console(constants['screen_width'], constants['screen_height'], order = "F")
            while True:
                root_console.clear()
                handler.on_render(console = root_console)
                context.present(root_console)
                try:
                    for event in tcod.event.wait():
                        context.convert_event(event)   
                        handler = handler.handle_events(event)
                except Exception: # Handle exceptions in game
                    traceback.print_exc() # Print error to stderr.
                    # The print the error to the message log.
                    if isinstance(handler, input_handlers.EventHandler):
                        handler.engine.message_log.add_message(
                            traceback.format_exc(), colors.error
                        )

if __name__ == "__main__":
    main()
