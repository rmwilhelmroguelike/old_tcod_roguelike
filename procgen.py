from __future__ import annotations

import random
from typing import Iterator, List, Tuple, TYPE_CHECKING

import tcod
import copy
import random

from loader_functions.random_utils import from_dungeon_level, random_choice_from_dict
from loader_functions.random_utils import random_choice_from_cr, random_monster_choice
import entity_factories
from game_map import GameMap
import tile_types
from entity import Entity, Stairs
from render_order import RenderOrder
from components.equipment import Equipment

if TYPE_CHECKING:
    from engine import Engine

class RectangularRoom:
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)

        return center_x, center_y

    @property
    def inner(self) -> Tuple[slice, slice]:
        """Return the inner area of this room as a 2D array index."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: RectangularRoom) -> bool:
        """Return True if this room overlaps with another RectangularRoom."""
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )    

def place_entities(room: RectangularRoom, dungeon: GameMap) -> None:
    maximum_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]], dungeon.dungeon_level)
    maximum_items = from_dungeon_level([[1, 1], [2, 4]], dungeon.dungeon_level)

    number_of_monsters = random.randint(0, maximum_monsters)
    number_of_items = random.randint(0, maximum_items)

    for i in range(number_of_monsters):
        x = random.randint(room.x1 + 1, room.x2 - 1)
        y = random.randint(room.y1 + 1, room.y2 - 1)

        if not any(entity.x == x and entity.y == y for entity in dungeon.entities):
            monster_choice = random_monster_choice(dungeon.dungeon_level)
            
            if monster_choice == 'orc':
                new_orc = copy.deepcopy(entity_factories.orc)
                orc_falchion = random_choice_from_dict({entity_factories.falchion_plus_one: 10,
                                                       entity_factories.falchion_masterwork: 20,
                                                       entity_factories.falchion: 70})
                new_orc.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = orc_falchion, body = entity_factories.studded_leather))
            elif monster_choice == 'human skeleton':
                hskel_scimitar = random_choice_from_dict({entity_factories.scimitar_plus_one: 10,
                                                         entity_factories.scimitar_masterwork: 20,
                                                         entity_factories.scimitar: 70})
                hskel_hshield = random_choice_from_dict({entity_factories.heavy_shield_plus_one: 5,
                                                        entity_factories.heavy_shield_masterwork: 15,
                                                        entity_factories.heavy_shield: 80})
                new_hskel = copy.deepcopy(entity_factories.human_skeleton)
                new_hskel.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = hskel_scimitar, off_hand = hskel_hshield))
            elif monster_choice == 'goblin':
                new_goblin = copy.deepcopy(entity_factories.goblin)
                goblin_morn = random_choice_from_dict({entity_factories.morningstar_plus_one: 5,
                                                      entity_factories.morningstar_masterwork: 10,
                                                      entity_factories.morningstar: 85})
                new_goblin.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = goblin_morn, body = entity_factories.leather_armor, off_hand = entity_factories.light_shield))
            elif monster_choice == 'ogre':
                new_ogre = copy.deepcopy(entity_factories.ogre)
                ogre_club = random_choice_from_dict({entity_factories.greatclub_plus_one: 20,
                                                      entity_factories.greatclub_masterwork: 30,
                                                      entity_factories.greatclub: 50})
                new_ogre.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = ogre_club, body = entity_factories.hide_armor, ranged = entity_factories.javelin))
            elif monster_choice == 'troll':
                new_troll = copy.deepcopy(entity_factories.troll)
                new_troll.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(neck = entity_factories.amulet_of_na_plus_one))
            elif monster_choice == 'hill giant':
                new_hill_giant = copy.deepcopy(entity_factories.hill_giant)
                hgiant_club = random_choice_from_dict({entity_factories.greatclub_plus_one: 35,
                                    entity_factories.greatclub_masterwork: 45,
                                    entity_factories.greatclub: 20})
                new_hill_giant.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = hgiant_club, body = entity_factories.hide_armor))
            elif monster_choice == 'ettin':
                new_ettin = copy.deepcopy(entity_factories.ettin)
                ettin_morn = random_choice_from_dict({entity_factories.morningstar_plus_one: 20,
                                                      entity_factories.morningstar_masterwork: 30,
                                                      entity_factories.morningstar: 50})
                new_ettin.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = ettin_morn, ranged = entity_factories.javelin))
            elif monster_choice == 'frost giant':
                new_frost_giant = copy.deepcopy(entity_factories.frost_giant)
                frgiant_axe = random_choice_from_dict({entity_factories.greataxe_plus_two: 20,
                                                      entity_factories.greataxe_plus_one: 30,
                                                      entity_factories.greataxe_masterwork: 30,
                                                      entity_factories.greataxe: 20})
                frgiant_cshirt = random_choice_from_dict({entity_factories.chain_shirt_plus_one: 30,
                                                          entity_factories.chain_shirt_masterwork: 30,
                                                          entity_factories.chain_shirt: 40})
                new_frost_giant.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = frgiant_axe, body = frgiant_cshirt))
            elif monster_choice == 'fire giant':
                new_fire_giant = copy.deepcopy(entity_factories.fire_giant)
                figiant_sword = random_choice_from_dict({entity_factories.greatsword_plus_two: 30,
                                                         entity_factories.greatsword_plus_one: 40,
                                                         entity_factories.greatsword_masterwork: 30})
                new_fire_giant.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment(main_hand = figiant_sword, body = entity_factories.half_plate))
            elif monster_choice == 'manticore':
                new_manticore = copy.deepcopy(entity_factories.manticore)
                new_manticore.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment())
            elif monster_choice == 'young red dragon':
                new_young_red_dragon = copy.deepcopy(entity_factories.red_dragon_young)
                new_young_red_dragon.spawn_w_items(dungeon, x, y, inventory = [], equipment = Equipment())
            elif monster_choice == 'bison':
                entity_factories.bison.spawn(dungeon, x, y)
            elif monster_choice == 'boar':
                new_boar = copy.deepcopy(entity_factories.boar)
                new_boar.spawn(dungeon, x, y)
            elif monster_choice == 'camel':
                entity_factories.camel.spawn(dungeon, x, y)
            elif monster_choice == 'crocodile':
                entity_factories.crocodile.spawn(dungeon, x, y)
            elif monster_choice == 'hawk':
                entity_factories.hawk.spawn(dungeon, x, y)
            elif monster_choice == 'hyena':
                entity_factories.hyena.spawn(dungeon, x, y)
            elif monster_choice == 'snake':
                entity_factories.snake.spawn(dungeon, x, y)
            elif monster_choice == 'wolf':
                entity_factories.wolf.spawn(dungeon, x, y)
            else:
                print('missing monster: ' + monster_choice)

def tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int]
) -> Iterator[Tuple[int, int]]:
    """Return an L-shaped tunnel between these two points."""
    x1, y1 = start
    x2, y2 = end
    if random.random() < 0.5: # 50% chance
        # Move horizontally, then vertically.
        corner_x, corner_y = x2, y1
    else:
        # Move vertically, then horizontally.
        corner_x, corner_y = x1, y2

    # Generate the coordinates for this tunnel.
    for x, y in tcod.los.bresenham((x1, y1), (corner_x, corner_y)).tolist():
        yield x, y
    for x, y in tcod.los.bresenham((corner_x, corner_y), (x2, y2)).tolist():
        yield x, y

def place_holder(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
    dungeon_level: int,
) -> GameMap:
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, dungeon_level, entities = [player])

    rooms: List[RectangularRoom] = []

    new_room = RectangularRoom(5, 5, 2, 2)
    dungeon.tiles[new_room.inner] = tile_types.floor
    rooms.append(new_room)
    player.place(6, 6, dungeon)

    return dungeon

def graphics_test(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
    dungeon_level: int,
) -> GameMap:
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, dungeon_level, entities = [player])

    rooms: List[RectangularRoom] = []

    center_of_last_room_x = None
    center_of_last_room_y = None

    new_room = RectangularRoom(2, 2, 30, 30)
    dungeon.tiles[new_room.inner] = tile_types.floor
    rooms.append(new_room)
    player.place(6, 7, dungeon)

    entity_factories.wolf.spawn(dungeon, 4, 3)
    entity_factories.snake.spawn(dungeon, 5, 3)
    entity_factories.orc.spawn(dungeon, 6, 3)
    entity_factories.goblin.spawn(dungeon, 7, 3)
    entity_factories.boar.spawn(dungeon, 8, 3)
    entity_factories.troll.spawn_w_items(dungeon, 9, 3, inventory = [entity_factories.greatsword], equipment = Equipment(neck = entity_factories.amulet_of_na_plus_one))
    entity_factories.bison.spawn(dungeon, 4, 4)
    entity_factories.camel.spawn(dungeon, 5, 4)
    entity_factories.crocodile.spawn(dungeon, 6, 4)
    entity_factories.hawk.spawn(dungeon, 7, 4)
    entity_factories.cure_light_wounds_potion.spawn(dungeon, 8, 4)
    entity_factories.fireball_scroll.spawn(dungeon, 9, 4)
    entity_factories.confusion_scroll.spawn(dungeon, 4, 5)
    entity_factories.lightning_scroll.spawn(dungeon, 5, 5)
    entity_factories.long_sword.spawn(dungeon, 6, 5)
    entity_factories.heavy_shield.spawn(dungeon, 7, 5)
    entity_factories.dwarven_waraxe.spawn(dungeon, 8, 5)
    entity_factories.light_shield.spawn(dungeon, 9, 5)
    entity_factories.falchion.spawn(dungeon, 4, 6)
    entity_factories.morningstar.spawn(dungeon, 5, 6)
    entity_factories.full_plate.spawn(dungeon, 6, 6)
    entity_factories.studded_leather.spawn(dungeon, 7, 6)
    entity_factories.leather_armor.spawn(dungeon, 8, 6)
    entity_factories.splint_mail.spawn(dungeon, 9, 6)
    entity_factories.stairs.spawn(dungeon, 4, 7)
    entity_factories.up_stairs.spawn(dungeon, 5, 7)
    entity_factories.composite_long_bow.spawn(dungeon, 7, 7)
    entity_factories.breastplate.spawn(dungeon, 8, 7)
    entity_factories.greatsword.spawn(dungeon, 9, 7)
    entity_factories.ogre.spawn(dungeon, 9, 8)
    entity_factories.greatclub.spawn(dungeon, 9, 9)
    entity_factories.javelin.spawn(dungeon, 10, 3)
    entity_factories.human_skeleton.spawn_w_items(dungeon, 10, 4, inventory = [], equipment = Equipment(main_hand = entity_factories.scimitar, off_hand = entity_factories.heavy_shield))
    entity_factories.hill_giant.spawn_w_items(dungeon, 10, 5, inventory = [], equipment = Equipment(main_hand = entity_factories.greatclub, body = entity_factories.hide_armor))
    entity_factories.red_dragon_young.spawn_w_items(dungeon, 10, 6, inventory = [], equipment = Equipment())

    return dungeon
    


    
def generate_dungeon(
    max_rooms: int,
    room_min_size: int,
    room_max_size: int,
    map_width: int,
    map_height: int,
    engine: Engine,
    dungeon_level: int,
    stairs: int,
) -> GameMap:
    """Generate a new dungeon map."""
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, dungeon_level, entities = [player], stairs = stairs)

    rooms: List[RectangularRoom] = []

    center_of_last_room_x = None
    center_of_last_room_y = None

    for r in range(max_rooms):
        room_width = random.randint(room_min_size, room_max_size)
        room_height = random.randint(room_min_size, room_max_size)

        x = random.randint(0, dungeon.width - room_width - 1)
        y = random.randint(0, dungeon.height - room_height - 1)

        # "RectangularRoom" class makes rectangles easier to work with
        new_room = RectangularRoom(x, y, room_width, room_height)

        # Run through the other rooms and see if they intersect with this one.
        if any(new_room.intersects(other_room) for other_room in rooms):
            continue # This room vdfm intersects, so go to the next attempt.
        # If there are no intersections then the room is valid.

        center_of_last_room_x = int(x + room_width / 2)
        center_of_last_room_y = int(y + room_height / 2)
        
        # Dig out this rooms inner area.
        dungeon.tiles[new_room.inner] = tile_types.floor

        if len(rooms) == 0:
            # The first room, where the player starts.
            player.place(*new_room.center, dungeon)
            if dungeon.dungeon_level > 0:
                if dungeon.stairs == 1: #went down stairs to get here
                    entity_factories.up_stairs.spawn(dungeon, player.x, player.y)
                else: #went up stairs to get here
                    entity_factories.stairs.spawn(dungeon, player.x, player.y)
        else: # All rooms after the first.
            # Dig out a tunnel between this room and the previous one.
            for x, y in tunnel_between(rooms[-1].center, new_room.center):
                dungeon.tiles[x, y] = tile_types.floor

        place_entities(new_room, dungeon)

        # Finally, append the new room to the list.
        rooms.append(new_room)

    floor = dungeon.dungeon_level + 1
    if dungeon.stairs == 1: #went down stairs to get here
        entity_factories.stairs.spawn(dungeon, center_of_last_room_x, center_of_last_room_y)
    else: #went up stairs to get here
        entity_factories.up_stairs.spawn(dungeon, center_of_last_room_x, center_of_last_room_y)
        
    return dungeon

def generate_town(
    engine: Engine,
    max_rooms: int = 0,
    room_min_size: int = 0,
    room_max_size: int = 0,
    map_width: int = 0,
    map_height: int = 0,
    dungeon_level: int = 0,
) -> GameMap:
    """Generate a new dungeon map."""
    player = engine.player
    dungeon = GameMap(engine, map_width, map_height, dungeon_level, entities = [player])

    rooms: List[RectangularRoom] = []

    main_room = RectangularRoom(10, 10, 20, 20)

    dungeon.tiles[main_room.inner] = tile_types.floor
    player.place(*main_room.center, dungeon)
    entity_factories.stairs.spawn(dungeon, 20, 20)

    entity_factories.armor_shop.spawn(dungeon, 15, 15)
    entity_factories.weapon_shop.spawn(dungeon, 15, 20)
    entity_factories.potion_shop.spawn(dungeon, 20, 15)
    entity_factories.jewelry_shop.spawn(dungeon, 15, 25)
    entity_factories.clothing_shop.spawn(dungeon, 20, 25)
    entity_factories.bow_shop.spawn(dungeon, 25, 25)
    entity_factories.enchanter.spawn(dungeon, 25, 20)
    entity_factories.misc_shop.spawn(dungeon, 25, 15)

    return dungeon
