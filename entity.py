from __future__ import annotations

import tcod
import copy
import math
from typing import Optional, Tuple, Type, TypeVar, TYPE_CHECKING, Union

from render_order import RenderOrder
from components.inventory import Inventory, Bag_Inventory
from loader_functions.random_utils import random_choice_from_cr, get_inv
import tile_types
import colors
import random

if TYPE_CHECKING:
    from components.ai import BaseAI
    from components.consumable import Consumable
    from components.battler import Battler
    from components.equipment import Equipment
    from components.stairs import Stairs
    from game_map import GameMap

T = TypeVar("T", bound = "Entity")

class Entity:
    """
    A generic object to represent players, enemies, items, etc.

    """

    parent: Union[Gamemap, Inventory]
    
    def __init__(
        self,
        parent: Optional[GameMap] = None,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = (colors.white, colors.white),
        color: Tuple[int, int, int] = colors.white,
        name: str = "<Unnamed>",
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.CORPSE,
        stairs = None,
        number: int = 1,
        dungeon_level: int = 1,
        level = None,
        gold_value: int = 1,
    ):
        self.x = x
        self.y = y
        self.char = char
        self.tile_code = tile_code
        self.tile_colors = tile_colors
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        self.stairs = stairs
        self.number = number
        self.dungeon_level = dungeon_level
        self.level = level
        self.gold_value = gold_value
        if parent:
            # If parent isn't provided now then it will be set later.
            self.parent = parent
            parent.entities.add(self)

    @property
    def gamemap(self) -> GameMap:
        return self.parent.gamemap

    @property
    def base_gold(self) -> int:
        base_gold_by_cr = {0.125: 15, 0.2: 20, 0.25: 25, 0.4: 33, 0.5: 50,
                           1: 100, 2: 200, 3: 250, 4: 350, 5: 450, 6: 550,
                           7: 700, 8: 900, 9: 1250, 10: 1500, 11: 1800,
                           12: 2500, 13: 2500, 14: 3500, 15: 4500,
                           16: 6500, 17: 7500, 18: 10500, 19: 13500,
                           20: 18000, 21: 24000, 22: 32000, 23: 43000,
                           24: 57000, 25: 80000, 26: 100000, 27: 100000,
                           28: 100000, 29: 100000, 30: 100000}
        return base_gold_by_cr[self.battler.cr]

    def spawn(self: T, gamemap: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        try: clone.battler.hp = clone.battler.max_hp # Yes, ugly hack
        except: None
        gamemap.entities.add(clone)
        return clone

    def spawn_summon(self: T, gamemap: GameMap, x: int, y: int, duration: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        try: clone.battler.hp = clone.battler.max_hp # Yes, ugly hack
        except: None
        clone.battler.current_buffs["Player Summoned"] = gamemap.engine.current_turn + duration
        gamemap.entities.add(clone)
        return clone

    def spawn_w_items(self: T, gamemap: GameMap, x: int, y: int, inventory: List[Item], equipment: Equipment()
                      ) -> T:
        """Spawn a copy of this Actor with items at given location."""
        """Equipment adds to inventory and is equipped, Inventory is only loot."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone_equipment = copy.deepcopy(equipment)
        clone.equipment = clone_equipment
        clone.equipment.parent = clone
        clone_inv = copy.deepcopy(inventory)
        clone.inventory = Inventory(capacity = 26, items = clone_inv)
        inventory_random = random_choice_from_cr(self.battler.cr)
        new_random_item = get_inv(inventory_random)
        clone.inventory.items.append(new_random_item)
        clone.inventory.parent = clone
        for item_worn in (clone.equipment.main_hand, clone.equipment.off_hand,
                          clone.equipment.ranged, clone.equipment.body,
                          clone.equipment.neck, clone.equipment.waist,
                          clone.equipment.lring, clone.equipment.rring,
                          clone.equipment.head, clone.equipment.cloak,
                          clone.equipment.eyes, clone.equipment.shirt,
                          clone.equipment.wrists, clone.equipment.feet,
                          clone.equipment.hands, clone.equipment.misc):
            if item_worn != None:
                item_worn.parent = clone.equipment
        clone.battler.gold = int(clone.base_gold * (random.random() + 0.5)) # gold int between 50% and 150% base gold
        clone.battler.hp = clone.battler.max_hp # Yes, ugly hack
            
        clone.parent = gamemap
        gamemap.entities.add(clone)
        return clone

    def place_on_death(self: T, gamemap: GameMap, x: int, y: int) -> T:
        """Spawn an item/gold dropped on death.  Prioritizes near corpse."""
        clone = copy.deepcopy(self)
        temp_x = x
        temp_y = y
        blocked = False
        #Could randomize?  Sort 3X3 randomly by absolute value ascending?  Currently 2-3 items -1, 0
        #is always picked, 0, -1 close to never.
        for (i, j) in [(0, 0), (-1, 0), (0, 1), (1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1),
                       (0, 2), (2, 0), (0, -2), (-2, 0), (1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1),
                       (2, -1), (-2, 1), (-2, -1), (2, 2), (2, -2), (-2, 2), (-2, -2)]:
            if x + i not in range(0, gamemap.width) or y + j not in range(0, gamemap.height):
                blocked = True
            if gamemap.tiles[x + i, y + j] != tile_types.floor:
                blocked = True
            for entity in gamemap.entities:
                if entity.x == x + i and entity.y == y + j:
                    blocked = True
                    break
            if blocked == False:
                temp_x = x + i
                temp_y = y + j
                break
            blocked = False
        clone.x = temp_x
        clone.y = temp_y
        clone.parent = gamemap
        gamemap.entities.add(clone)
        return clone

    def place(self, x: int, y: int, gamemap: Optional[GameMap] = None) -> None:
        """Place this entity at a new location.  Handles moving across GameMaps."""
        self.x = x
        self.y = y
        if gamemap:
            if hasattr(self, "parent"): # Possibly uninitialized
                if self.parent is self.gamemap:
                    self.gamemap.entities.remove(self)
            self.parent = gamemap
            gamemap.entities.add(self)

    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dx: int, dy: int) -> None:
        # Move the entity by a given amount
        self.x += dx
        self.y += dy

class Shop(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        for_sale: list[Item] = [],
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            name = name,
            blocks_movement = False,
            render_order = RenderOrder.ACTOR,
        )
        self.for_sale = for_sale

class Enchant(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "^",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            name = name,
            blocks_movement = False,
            render_order = RenderOrder.ACTOR,
        )
        
class Actor(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        ai_cls: Type[BaseAI],
        battler: Battler,
        inventory: Inventory,
        equipment: Equipment,
        level = None,
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            name = name,
            blocks_movement = True,
            render_order = RenderOrder.ACTOR,
        )

        self.ai: Optional[BaseAI] = ai_cls(self)

        self.battler = battler
        if self.battler:
            self.battler.parent = self

        self.inventory = inventory
        if self.inventory:
            self.inventory.parent = self

        self.equipment = equipment
        if self.equipment:
            self.equipment.parent = self

        self.level = level

    @property
    def is_alive(self) -> bool:
        """Returns True as long as this actor can perform actions."""
        return bool(self.ai)

class Item(Entity):
    def __init__(
        self,
        parent: Equipment = None,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        base_name: str = "<Unnamed>",
        consumable: Consumable,
        equippable: Equipment = None,
        gold_value: int = 0,
        number_in_stack: int = 1,
        can_stack: bool = False,
        masterwork: bool = False,
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            name = name,
            blocks_movement = False,
            render_order = RenderOrder.ITEM,
            gold_value = gold_value,
        )

        if base_name == "<Unnamed>":
            self.base_name = name
        else:
            self.base_name = base_name
        self.consumable = consumable
        if self.consumable:
            self.consumable.parent = self
        self.equippable = equippable
        if self.equippable:
            self.equippable.parent = self
        self.number_in_stack = number_in_stack
        self.can_stack = can_stack
        self.masterwork = masterwork

class Bag(Item):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        base_name: str = "<Unnamed>",
        consumable: Consumable = None,
        equippable: Equipment = None,
        bag_inventory = Bag_Inventory,
        gold_value: int = 0,
        number_in_stack: int = 1,
        can_stack: bool = False,
        masterwork: bool = False,
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            name = name,
            #blocks_movement = False,
            #render_order = RenderOrder.ITEM,
            consumable = None,
            gold_value = gold_value,
        )
        self.bag_inventory = bag_inventory
        self.number_can_stack = can_stack
        self.masterwork = masterwork
        self.consumable = consumable
        self.equippable = equippable
        

class Gold(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "$",
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int] = (100, 100, 100),
        number: int = 0,
        name: str = " Gold pieces",
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            number = number,
            name = str(number) + name,
            blocks_movement = False,
            render_order = RenderOrder.ITEM,
        )

class Stairs(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str,
        tile_code: int = 0,
        tile_colors: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = ((255, 255, 255), (255, 255, 255)),
        color: Tuple[int, int, int],
        name: str,
        stairs: int = 1,
        dungeon_level: int = 1,
    ):
        super().__init__(
            x = x,
            y = y,
            char = char,
            tile_code = tile_code,
            tile_colors = tile_colors,
            color = color,
            name = name,
            blocks_movement = False,
            render_order = RenderOrder.STAIRS,
            stairs = stairs,
            dungeon_level = dungeon_level
        )
            
