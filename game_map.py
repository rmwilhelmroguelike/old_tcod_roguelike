from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np # type: ignore
from tcod.console import Console

from entity import Actor, Item, Gold, Shop, Enchant, Stairs
import tile_types

if TYPE_CHECKING:
    from engine import Engine
    from entity import Entity

class GameMap:
    def __init__(
        self,
        engine: Engine,
        width: int,
        height: int,
        dungeon_level: int,
        entities: Iterable[Entity] = (),
        stairs: int = 1,
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.entities = set(entities)
        self.tiles = np.full((width, height), fill_value = tile_types.wall, order = "F")

        self.dungeon_level = dungeon_level
        self.stairs = stairs

        self.visible = np.full(
            (width, height), fill_value = False, order = "F"
        ) # Tiles the player can currently see.
        self.explored = np.full(
            (width, height), fill_value = False, order = "F"
        ) # Tiles the player has seen before.

    @property
    def gamemap(self) -> GameMap:
        return self

    @property
    def actors(self) -> Iterator[Actor]:
        """Iterate over this maps living actors."""
        yield from (
            entity
            for entity in self.entities
            if isinstance(entity, Actor) and entity.is_alive
        )

    @property
    def items(self) -> Iterator[Item]:
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    @property
    def gold_piles(self) -> Iterator[Gold]:
        yield from (entity for entity in self.entities if isinstance(entity, Gold))

    @property
    def shops(self) -> Iterator[Shop]:
        yield from (entity for entity in self.entities if isinstance(entity, Shop))

    @property
    def enchant(self) -> Iterator[Enchant]:
        yield from (entity for entity in self.entities if isinstance(entity, Enchant))

    @property
    def stairs_iter(self) -> Iterator[Stairs]:
        yield from (entity for entity in self.entities if isinstance(entity, Stairs))

    def get_blocking_entity_at_location(
        self, location_x: int, location_y: int,
    ) -> Optional[Entity]:
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity
            
        return None

    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor

        return None

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def render(self, console: Console) -> None:
        """
        Renders the map.

        If a tile is in the "visible" array, then draw it with the "light" colors.
        If it isn't, but it's in the "explored" array, then draw it with the "dark" colors.
        Otherwise, the default is "SHROUD".
        """
        
        console.tiles_rgb[0 : self.width, 0 : self.height] = np.select(
            condlist=[self.visible, self.explored],
            choicelist=[self.tiles["light"], self.tiles["dark"]],
            default=tile_types.SHROUD
        )
        
        """
        console.tiles_rgb[0 : self.width, 0 : self.height] = 10150, [255, 255, 0], [0, 0, 0]
        """
        
        entities_sorted_for_rendering = sorted(
            self.entities, key = lambda x: x.render_order.value
        )
        

        for entity in entities_sorted_for_rendering:
            # Only print entities that are in the FOV
            if self.visible[entity.x, entity.y] or ((entity in self.stairs_iter or entity in self.shops) and self.explored[entity.x, entity.y]):
                if entity.tile_code == 0:
                    console.print(
                        x = entity.x, y = entity.y, string = entity.char, fg = entity.color
                    )
                else:
                    console.tiles_rgb[entity.x, entity.y] = entity.tile_code, entity.tile_colors[0], entity.tile_colors[1] #[255, 255, 255], [255, 255, 255]

class GameWorld:
    """
    Holds the settings for the GameMap, and generates new maps when moving down the stairs.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        map_width: int,
        map_height: int,
        max_rooms: int,
        room_min_size: int,
        room_max_size: int,
        current_floor: int = 0
    ):
        self.engine = engine

        self.map_width = map_width
        self.map_height = map_height

        self.max_rooms = max_rooms

        self.room_min_size = room_min_size
        self.room_max_size = room_max_size

        self.current_floor = current_floor

    def generate_floor(self, stairs: int = 0) -> None:
        from procgen import generate_dungeon, generate_town

        self.stairs = stairs
        self.current_floor = self.engine.game_map.dungeon_level
        self.current_floor += self.stairs

        if self.current_floor == 0:
            self.engine.game_map = generate_town(
                engine = self.engine,
                max_rooms=self.max_rooms,
                room_min_size=self.room_min_size,
                room_max_size=self.room_max_size,
                map_width=self.map_width,
                map_height=self.map_height,
                dungeon_level = self.current_floor
            )
        else:
            self.engine.game_map = generate_dungeon(
                max_rooms=self.max_rooms,
                room_min_size=self.room_min_size,
                room_max_size=self.room_max_size,
                map_width=self.map_width,
                map_height=self.map_height,
                engine=self.engine,
                dungeon_level = self.current_floor,
                stairs = self.stairs
            )
