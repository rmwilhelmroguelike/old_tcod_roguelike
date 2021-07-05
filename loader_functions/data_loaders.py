import os

import shelve
import pickle
import copy

def save_game(engine, player, game_map, save_name: str = 'savegame'):
    with shelve.open(save_name, 'n') as data_file:
        data_file['engine'] = engine
        data_file['player'] = player
        data_file['game_map'] = game_map
        data_file.close()

def load_game():
    if not os.path.isfile('savegame.dat'):
        raise FileNotFoundError

    with shelve.open('savegame', 'r') as data_file:
        engine = data_file['engine']
        player = data_file['player']
        game_map = data_file['game_map']
        #engine.player = player
        #engine.player.parent = engine
        data_file.close()

    return engine#, player, game_map
"""
def save_game(player, entities, game_map, message_log):
    with shelve.open('savegame', 'n') as data_file:
        data_file['player'] = copy.deepcopy(player)
        data_file['entities'] = copy.deepcopy(entities)
        data_file['game_map'] = copy.deepcopy(game_map)
        data_file['message_log'] = copy.deepcopy(message_log)
        #data_file['event_handler'] = copy.deepcopy(event_handler)
        data_file.close()

def load_game():
    if not os.path.isfile('savegame.dat'):
        raise FileNotFoundError

    with shelve.open('savegame', 'r') as data_file:
        player = data_file['player']
        entities = data_file['entities']
        game_map = data_file['game_map']
        message_log = data_file['message_log']
        #event_handler = data_file['event_handler']
        data_file.close()

    return player, entities, game_map, message_log
"""
