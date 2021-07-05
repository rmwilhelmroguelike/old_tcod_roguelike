import tcod

def get_constants():
    window_title = 'Generic d20 Roguelike'

    tileset = tcod.tileset.load_tilesheet(
        "NewDFtest.png", 16, 16, tcod.tileset.CHARMAP_CP437
    )

    test_list = list(range(10001,11920))
    
    tileset2 = tcod.tileset.load_tilesheet(
        "16x16.png", 32, 60, test_list
    )

    for i in range(10001,11920):
        tileset.set_tile(i, tileset2.get_tile(i))

    test3_list = list(range(12001, 12192))

    tileset3 = tcod.tileset.load_tilesheet(
        "wallstuff.png", 32, 10, test3_list
    )

    for i in range(12001, 12192):
        tileset.set_tile(i, tileset3.get_tile(i))
 
    screen_width = 80
    screen_height = 50

    map_width = 80
    map_height = 43

    bar_width = 20
    panel_height = 7
    panel_y = screen_height - panel_height

    message_x = bar_width + 2
    message_width = screen_width - bar_width - 2
    message_height = panel_height - 1

    room_max_size = 10
    room_min_size = 6
    max_rooms = 30

    max_monsters_per_room = 2
    max_items_per_room = 2
    
    constants = {
        'window_title': window_title,
        'tileset': tileset,
        'screen_width': screen_width,
        'screen_height': screen_height,
        'bar_width': bar_width,
        'panel_height': panel_height,
        'panel_y': panel_y,
        'message_x': message_x,
        'message_width': message_width,
        'message_height': message_height,
        'map_width': map_width,
        'map_height': map_height,
        'room_max_size': room_max_size,
        'room_min_size': room_min_size,
        'max_rooms': max_rooms,
    }

    return constants
