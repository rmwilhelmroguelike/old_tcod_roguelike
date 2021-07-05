#!/usr/bin/env python3
import copy
import traceback

import tcod

import colors
from engine import Engine
import entity_factories
from loader_functions.initialize_new_game import get_constants # get_game_variables
from loader_functions.data_loaders import load_game
from procgen import generate_dungeon

def main() -> None:
    constants = get_constants()

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
            engine.event_handler.on_render(console=root_console)
            context.present(root_console)

            try:
                for event in tcod.event.wait():
                    context.convert_event(event)
                    engine.event_handler.handle_events(event)
            except Exception:  # Handle exceptions in game.
                traceback.print_exc()  # Print error to stderr.
                # Then print the error to the message log.
                engine.message_log.add_message(traceback.format_exc(), color.error)



if __name__ == "__main__":
    main()
