from __future__ import annotations

from typing import Callable, Optional, Tuple, TYPE_CHECKING, List, Union

from loader_functions.data_loaders import save_game, load_game
from loader_functions.initialize_new_game import get_constants
from feat_stuff import get_all_feats, get_feat_reqs
from equipment_slots import EquipmentSlots
import feat_stuff
import components.enchanter

from procgen import generate_dungeon, generate_town
from entity import Item, Bag
 
import tcod
import tcod.event
import tcod.console
import copy
import math

import actions
from actions import (
    Action,
    BumpAction,
    PickupAction,
    WaitAction,
    RangedAction,
    ToggleCombatModeAction,
    CastSelfBuffAction,
    TakeStairsAction,
    CastSelfHealAction,
    FastMoveAction,
    SummonMonsterAction,
)
import colors
import exceptions


if TYPE_CHECKING:
    from engine import Engine

MOVE_KEYS = {
    # Arrow keys.
    tcod.event.K_UP: (0, -1),
    tcod.event.K_DOWN: (0, 1),
    tcod.event.K_LEFT: (-1, 0),
    tcod.event.K_RIGHT: (1, 0),
    tcod.event.K_HOME: (-1, -1),
    tcod.event.K_END: (-1, 1),
    tcod.event.K_PAGEUP: (1, -1),
    tcod.event.K_PAGEDOWN: (1, 1),
    # Numpad keys.
    tcod.event.K_KP_1: (-1, 1),
    tcod.event.K_KP_2: (0, 1),
    tcod.event.K_KP_3: (1, 1),
    tcod.event.K_KP_4: (-1, 0),
    tcod.event.K_KP_6: (1, 0),
    tcod.event.K_KP_7: (-1, -1),
    tcod.event.K_KP_8: (0, -1),
    tcod.event.K_KP_9: (1, -1),
    # Vi keys.
    #tcod.event.K_h: (-1, 0),
    #tcod.event.K_j: (0, 1),
    #tcod.event.K_k: (0, -1),
    #tcod.event.K_l: (1, 0),
    #tcod.event.K_y: (-1, -1),
    #tcod.event.K_u: (1, -1),
    #tcod.event.K_b: (-1, 1),
    #tcod.event.K_n: (1, 1),
}

WAIT_KEYS = {
    tcod.event.K_PERIOD,
    tcod.event.K_KP_5,
    tcod.event.K_CLEAR,
}

CONFIRM_KEYS = {
    tcod.event.K_RETURN,
    tcod.event.K_KP_ENTER,
}

ActionOrHandler = Union[Action, "BaseEventHandler"]
"""An event handler return value which can trigger an action or switch active handlers.

If a handler is returned then it will become the active handler for future events.
If an action is returned it will be attempted and if it's valid then
MainGameEventHandler will become the active handler.
"""

class BaseEventHandler(tcod.event.EventDispatch[ActionOrHandler]):
    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle an event and return the next active event handler."""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, Action), f"{self!r} can not handle actions."
        return self

    def on_render(self, console: tcod.Console) -> None:
        raise NotImplementedError()

    def ev_quit(self, event: tcod.event.Quit) -> Optional[Action]:
        raise SystemExit()

class EventHandler(BaseEventHandler):
    def __init__(self, engine: Engine):
        self.engine = engine

    def handle_events(self, event: tcod.event.Event) -> BaseEventHandler:
        """Handle events for input handlers with an engine."""
        action_or_state = self.dispatch(event)
        if isinstance(action_or_state, BaseEventHandler):
            return action_or_state
        if self.handle_action(action_or_state):
            # A valid action was performed.
            if not self.engine.player.is_alive:
                # The player was killed sometime during or after the action.
                return GameOverEventHandler(self.engine)
            return MainGameEventHandler(self.engine) # Return to the main handler.
        return self

    def handle_action(self, action: Optional[Action]) -> bool:
        """Handle actions returned from event methods.

        Returns True if the action will advance a turn.
        """
        if action is None:
            return False

        try:
            action.perform()
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], colors.impossible)
            return False # Skip enemy turn on exceptions

        self.engine.handle_enemy_turns()

        self.engine.update_fov()
        return True

    def ev_mousemotion(self, event: tcod.event.MouseMotion) -> None:
        if self.engine.game_map.in_bounds(event.tile.x, event.tile.y):
            self.engine.mouse_location = event.tile.x, event.tile.y

    def on_render(self, console: tcod.Console) -> None:
        self.engine.render(console)

class MainGameEventHandler(EventHandler):
    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        action: Optional[Action] = None

        key = event.sym
        modifier = event.mod

        player = self.engine.player
        
        # Very ugly hack.  Killing yourself with damage doesn't end game.
        # This checks every turn if you were flagged a corpse and ends game.
        # Even uglier: You can move once here during game over, so waitaction wastes final turn
        if player.char == "%":
            return GameOverEventHandler(self.engine)
            action = WaitAction(player)

        if key in MOVE_KEYS and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT):
            dx, dy = MOVE_KEYS[key]
            action = FastMoveAction(player, dx, dy)
        elif key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            action = BumpAction(player, dx, dy)
        elif key in (tcod.event.K_PERIOD, tcod.event.K_COMMA) and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT):
            action = TakeStairsAction(player)
        elif key in WAIT_KEYS:
            action = WaitAction(player)

        elif key == tcod.event.K_q and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT):
            return GameOverEventHandler(self.engine)
        elif key == tcod.event.K_v:
            return HistoryViewer(self.engine)

        elif key == tcod.event.K_g:
            action = PickupAction(player)
        elif key == tcod.event.K_x:
            action = ToggleCombatModeAction(player)

        elif key == tcod.event.K_i:
            return InventoryActivateHandler(self.engine)
        elif key == tcod.event.K_d:
            return InventoryDropHandler(self.engine)
        elif key == tcod.event.K_e:
            return EquipmentHandler(self.engine)
        elif key == tcod.event.K_SLASH and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT
        ):
            return HelpMenuEventHandler(self.engine)
        elif key == tcod.event.K_SLASH:
            return LookHandler(self.engine)
        elif key == tcod.event.K_c:
            return CharacterScreenEventHandler(self.engine)
        elif key == tcod.event.K_a:
            return LevelUpMenuEventHandler(self.engine)
        elif key == tcod.event.K_f:
            return FeatSelectionEventHandler(self.engine)
        elif key == tcod.event.K_r:
            return RenameItemEventHandler(self.engine)
        elif key == tcod.event.K_s and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT
        ):
            return CastSpellHandler(self.engine)
        elif key == tcod.event.K_s:
            return SaveGameEventHandler
            """
            save_game(self.engine, self.engine.player, self.engine.game_map)
            self.engine.message_log.add_message("Game saved.", colors.white)
            """
        elif key == tcod.event.K_t:
            return SingleRangedAttackHandler(
                self.engine,
                callback = lambda xy: actions.FullAttackRangedAction(self.engine.player, xy),
                )
        elif key == tcod.event.K_b and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT
        ):
            return BuffListHandler(self.engine)
        elif key == tcod.event.K_b:
            shop_found = False
            for shop in self.engine.game_map.shops:
                if shop.x == self.engine.player.x and shop.y == self.engine.player.y:
                    return ShopBuyEventHandler(self.engine)
                    shop_found = True
            if shop_found == False:
                self.engine.message_log.add_message("No shop is here to buy from.", colors.white)
        elif key == tcod.event.K_n:
            shop_found = False
            for shop in self.engine.game_map.shops:
                if shop.x == self.engine.player.x and shop.y == self.engine.player.y:
                    return ShopSellEventHandler(self.engine)
                    shop_found = True
            if shop_found == False:
                self.engine.message_log.add_message("No shop is here to sell to.", colors.white)
        elif key == tcod.event.K_u and modifier & (
            tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT
        ):
            enchant_found = False
            for enchant in self.engine.game_map.enchant:
                if enchant.x == self.engine.player.x and enchant.y == self.engine.player.y:
                    return EnchantEventHandler(self.engine)
                    enchant_found = True
            if enchant_found == False:
                self.engine.message_log.add_message("You cannot enchant items here.", colors.white)
                    
        # No valid key was pressed
        return action

CURSOR_Y_KEYS = {
    tcod.event.K_UP: -1,
    tcod.event.K_DOWN: 1,
    tcod.event.K_PAGEUP: -10,
    tcod.event.K_PAGEDOWN: 10,
}

class HistoryViewer(EventHandler):
    """Print the history on a larger window which can be navigated."""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console) # Draw the main state as the background.

        log_console = tcod.Console(console.width - 6, console.height - 6)

        # Draw a frame with a custom banner title.
        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print_box(
            0, 0, log_console.width, 1, "<Message history>", alignment = tcod.CENTER
        )

        # Render the message log using the cursor parameter.
        self.engine.message_log.render_messages(
            log_console,
            1,
            1,
            log_console.width - 2,
            log_console.height - 2,
            self.engine.message_log.messages[: self.cursor + 1],
        )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, event: tcod.event.KeyDown) -> None:
        # Fancy conditional movement to make it feel right.
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == tcod.event.K_HOME:
            self.cursor = 0 # Move directly to the top message.
        elif event.sym == tcod.event.K_END:
            self.cursor = self.log_length - 1 # Move directly to the last message.
        else: # Any other key moves back to the main game state.
            return MainGameEventHandler(self.engine)

class AskUserEventHandler(EventHandler):
    """Handles user input for actions which require special input."""

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """By default any key exits this input handler."""
        if event.sym in { # Ignore modifier keys.
            tcod.event.K_LSHIFT,
            tcod.event.K_RSHIFT,
            tcod.event.K_LCTRL,
            tcod.event.K_RCTRL,
            tcod.event.K_LALT,
            tcod.event.K_RALT,
        }:
            return None
        return self.on_exit()

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
        ) -> Optional[ActionOrHandler]:
        """By default any mouse click exits this input handler."""
        return self.on_exit()

    def on_exit(self) -> Optional[ActionOrHandler]:
        """Called when the user is trying to exit or cancel an action.

        By default this returns to the main event handler.
        """
        """
        self.engine.event_handler = MainGameEventHandler(self.engine)
        return None
        """
        return MainGameEventHandler(self.engine)

class GameOverEventHandler(AskUserEventHandler):

    def on_render(self, console: tcod.Console) -> None:
        """Screen to confirm quit command."""
        super().on_render(console)

        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 4,
            title = 'Quit the game?',
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        console.print(x + 1, y + 1, f"Do you really wish to quit?  Progress will not be saved.")
        console.print(x + 1, y + 2, f"'Esc' to quit, any other key to return to game.")
        
    def ev_keydown(self, event: tcod.event.KeyDown) -> None:
        if event.sym == tcod.event.K_ESCAPE:
            raise SystemExit()
        else:
            return MainGameEventHandler(self.engine)

class HelpMenuEventHandler(AskUserEventHandler):
    """Displays Help Menu, with keypress uses.  Any key to abort."""

    def on_render(self, console: tcod.Console) -> None:
        """Screen with Help Menu."""
        super().on_render(console)

        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 40,
            title = 'Help Menu: Available Buttons:  Any Key to return to game.',
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        console.print(x + 1, y + 1, f"Press Shift for capital letter choices.")
        console.print(x + 1, y + 2, f"Arrows or Number Keys 1-9 to move/attack.")
        console.print(x + 1, y + 3, f"'a': Level Up Screen.")
        console.print(x + 1, y + 4, f"'b': (B)uy from shop.")
        console.print(x + 1, y + 5, f"'c': Display (C)haracter screen (Your stats)")
        console.print(x + 1, y + 6, f"'d': (D)rop an item from inventory to ground.")
        console.print(x + 1, y + 7, f"'e': (E)quipment screen.  Can remove worn gear.")
        console.print(x + 1, y + 8, f"'f': Choose (F)eats, or see available feats.")
        console.print(x + 1, y + 9, f"'g': (G)et item from floor.")
        console.print(x + 1, y + 10, f"'i': (I)nventory display.  Then equip or use items.")
        console.print(x + 1, y + 11, f"'n': Sell an item to shop.")
        console.print(x + 1, y + 12, f"'r': (R)ename item in inventory.")
        console.print(x + 1, y + 13, f"'s': (S)ave game.")
        console.print(x + 1, y + 14, f"'t': (T)hrow or Shoot ranged weapon.")
        console.print(x + 1, y + 15, f"'v': (V)iew message history.  Can scroll though past messages.")
        console.print(x + 1, y + 16, f"'x':  e(X)change melee and ranged weapons.")
        console.print(x + 1, y + 17, f"'B': Display current (B)uffs on character.")
        console.print(x + 1, y + 18, f"'Q': (Q)uit game: (Esc) to confirm.  Will not save.")
        console.print(x + 1, y + 19, f"'S': (S)pell selection screen, cast spells.")
        console.print(x + 1, y + 20, f"'U': Enchant item in inventory at enchanter's shop.")
        console.print(x + 1, y + 21, f"'/': Look at monster, item, or feature.")
        console.print(x + 1, y + 22, f"'<', '>': Take stairs.")
        console.print(x + 1, y + 23, f"'.', '5': Wait one turn.")
        console.print(x + 1, y + 24, f"'?', This Help screen.")

    def ev_keydown(self, event: tcod.event.KeyDown) -> None:
            return MainGameEventHandler(self.engine)

class TownPortalEventHandler(AskUserEventHandler):
    """Handles town portal to/from town.  Esc to abort, Q to use."""

    def on_render(self, console: tcod.Console) -> None:
        """Screen to confirm or abort town portal."""
        super().on_render(console)

        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 10,
            title = 'Select an Option',
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        console.print(x + 1, y + 1, f"You have activated a town portal.")
        console.print(x + 1, y + 2, f"'Y' to confirm, 'Esc' to abort.")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        from loader_functions.initialize_new_game import get_constants
        constants = get_constants()
        player = self.engine.player
        engine = self.engine
        key = event.sym

        if key == tcod.event.K_ESCAPE or key == tcod.event.K_y:
            if key == tcod.event.K_ESCAPE:
                return MainGameEventHandler(self.engine)
            if key == tcod.event.K_y:
                if engine.game_map.dungeon_level > 0:
                    engine.last_level = engine.game_map.dungeon_level
                    engine.game_map = generate_town(
                        engine = engine,
                        max_rooms = constants['max_rooms'],
                        room_min_size = constants['room_min_size'],
                        room_max_size = constants['room_max_size'],
                        map_width = constants['map_width'],
                        map_height = constants['map_height'],
                    )
                else:
                    engine.game_map = generate_dungeon(
                        max_rooms = constants['max_rooms'],
                        room_min_size = constants['room_min_size'],
                        room_max_size = constants['room_max_size'],
                        map_width = constants['map_width'],
                        map_height = constants['map_height'],
                        engine = engine,
                        dungeon_level = engine.last_level,
                        stairs = 1
                    )
                    engine.last_level = 0
                engine.update_fov()
                return MainGameEventHandler(engine)

class StartMenuEventHandler(AskUserEventHandler):
    """Selects New game or Loads save.  Esc to quit."""
    """No longer used, see setup_game."""

    def on_render(self, console: tcod.Console) -> None:
        """Displays New Game/Load Game selection screen.
        """
        super().on_render(console)

        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 40,
            height = 10,
            title = 'Select an Option',
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        console.print(x + 1, y + 1, "Hit 'Z' to load saved game,")
        console.print(x + 1, y + 2, "'N' for new Dwarf Fighter,")
        console.print(x + 1, y + 3, "'H' for new Human Fighter,")
        console.print(x + 1, y + 4, "'W' for new Elf Wizard,")
        console.print(x + 1, y + 5, "'G' for graphics testing,")
        console.print(x + 1, y + 6, "or 'Esc' to quit.")

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        if key == tcod.event.K_z:
            #self.engine.event_handler = MainGameEventHandler(self.engine)
            #present(self.console)
            #self.engine = load_game()
            #self.engine.screen_reset = True
            return MainGameEventHandler(self.engine)
            #self.engine.update_fov()
        elif key in (tcod.event.K_h, tcod.event.K_n, tcod.event.K_w):
            return MainGameEventHandler(self.engine)
        elif key == tcod.event.K_ESCAPE:
            raise SystemExit()

class UseBagHandler(AskUserEventHandler):
    """Uses a Bag, take item out or put item in."""

    def on_render(self, console: tcod.Console) -> None:
        """Just displays take out or put in options."""
        super().on_render(console)

        player = self.engine.player
        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 20,
            title = f"{player.name}'s Bag use.",
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        console.print(x + 1, y + 1, "Press 'p' to place an item in the bag.")
        console.print(x + 1, y + 2, "Press 't' to take an item from the bag.")
        console.print(x + 1, y + 3, "Press 'Esc' to abort.")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        if key == tcod.event.K_t:
            return TakeFromBagHandler(self.engine)

        if key == tcod.event.K_p:
            return PlaceInBagHandler(self.engine)
        
        if key == tcod.event.K_q or key == tcod.event.K_ESCAPE:
            return MainGameEventHandler(self.engine)
        
class CastSpellHandler(AskUserEventHandler):
    """Casts a spell known"""

    def on_render(self, console: tcod.Console) -> None:
        """Displays available spells and mana costs."""
        super().on_render(console)

        player = self.engine.player
        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 30,
            title = f"{player.name}'s spells:",
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        y_hold = 2
        if len(list(player.battler.spells)) == 0:
            console.print(x + 1, y_hold, "You know no spells.  Esc or Q to quit")
        else:
            console.print(x + 1, y_hold, f"Select a letter to cast spell, Esc or Q to quit")
            y_hold += 1
            console.print(x + 1, y_hold, f"You currently have {player.battler.mana} mana remaining")
            current_spells_list = list(player.battler.spells)
            current_spells_list.sort()
            for i in range(len(current_spells_list)):
                y_hold += 1
                console.print(x + 1, y_hold, f"Press '{chr(i+97)}' for {current_spells_list[i]}: {player.battler.spells[current_spells_list[i]]} Mana.")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        current_spells_list = list(player.battler.spells)
        current_spells_list.sort()
        letter_found = key - 97

        if letter_found in range(len(current_spells_list)):
            if current_spells_list[letter_found] in ("Mage Armor", "Shield", "Magic Weapon", "Alter Self"):
                return CastSelfBuffAction(player, current_spells_list[letter_found])
            elif current_spells_list[letter_found] in ("Magic Missile"):
                return SingleRangedAttackHandler(
                    self.engine,
                    callback = lambda xy: actions.CastMagicMissileAction(self.engine.player, xy),
                    )
            elif current_spells_list[letter_found] in ("Shocking Grasp"):
                return SingleMeleeAttackHandler(
                    self.engine,
                    callback = lambda xy: actions.CastShockingGraspAction(self.engine.player, xy),
                    )
            elif current_spells_list[letter_found] in ("Ray of Enfeeblement"):
                return SingleRangedAttackHandler(
                    self.engine,
                    callback = lambda xy: actions.CastRayOfEnfeeblementAction(self.engine.player, xy),
                    )
            elif current_spells_list[letter_found] in ("Cure Light Wounds", "Cure Moderate Wounds", "Cure Serious Wounds", "Cure Critical Wounds"):
                return CastSelfHealAction(player, current_spells_list[letter_found])
            elif current_spells_list[letter_found] in ("Summon Monster 1", "Summon Monster 2", "Summon Monster 3"):
                mana = player.battler.spells[current_spells_list[letter_found]]
                return SummonMonsterHandler(
                    self.engine,
                    callback = lambda xy: actions.SummonMonsterAction(self.engine.player, xy, current_spells_list[letter_found], mana),
                    )

        if key == tcod.event.K_ESCAPE:
            return MainGameEventHandler(self.engine)


class FeatSelectionEventHandler(AskUserEventHandler):
    """Selects new feats.  Esc or Q to quit."""

    def on_render(self, console: tcod.Console) -> None:
        """Displays feat selection screen."""
        super().on_render(console)

        player = self.engine.player
        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 30,
            title = f"{player.name}'s feats:",
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        y_hold = 2
        console.print(x + 1, y_hold, f"Select a letter to learn feat or improve stat, Esc or Q to quit.")
        y_hold += 1
        console.print(x + 1, y_hold, f"You have {player.battler.feats_to_take} feats to learn, and {player.battler.stats_to_take} stat points to spend.")
        current_feats_list = list(player.battler.combat_feats)
        for i in range(len(current_feats_list)):
            y_hold += 1
            if player.battler.combat_feats[current_feats_list[i]] > 1:
                console.print(x + 1, y_hold, f"Known feat: {current_feats_list[i]} (X{player.battler.combat_feats[current_feats_list[i]]})")
            else:
                console.print(x + 1, y_hold, f"Known feat: {current_feats_list[i]}.")
        y_hold += 2
        taken_once_feats, taken_multiple_feats = get_all_feats()
        combined_feats = {**taken_once_feats, **taken_multiple_feats}
        taken_multiple_feats_list = list(taken_multiple_feats)
        taken_once_feats_list = list(taken_once_feats)
        possible_feats_list = list((set(taken_once_feats_list) - set(current_feats_list))|set(taken_multiple_feats_list))
        main_feats_list = copy.deepcopy(possible_feats_list)
        for i in range(len(possible_feats_list)):
            if get_feat_reqs(player, combined_feats[possible_feats_list[i]]) == False:
                main_feats_list.remove(possible_feats_list[i])
        main_feats_list.sort()
        for j in range(len(main_feats_list)):
            y_hold += 1
            console.print(x + 1, y_hold, f"Select '{chr(j+97)}' to learn {main_feats_list[j]}.")
        stat = list(["Str","Dex","Con","Int","Wis","Cha"])
        for k in range(6):
            y_hold += 1
            console.print(x + 1, y_hold, f"Select '{chr(len(main_feats_list)+k+97)}' to gain {stat[k]}.")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        current_feats_list = list(player.battler.combat_feats)
        taken_once_feats, taken_multiple_feats = get_all_feats()
        combined_feats = {**taken_once_feats, **taken_multiple_feats}
        taken_multiple_feats_list = list(taken_multiple_feats)
        taken_once_feats_list = list(taken_once_feats)
        possible_feats_list = list((set(taken_once_feats_list) - set(current_feats_list))|set(taken_multiple_feats_list))
        main_feats_list = copy.deepcopy(possible_feats_list)
        for i in range(len(possible_feats_list)):
            if get_feat_reqs(player, combined_feats[possible_feats_list[i]]) == False:
                main_feats_list.remove(possible_feats_list[i])
        main_feats_list.sort()
        letter_found = key - 97

        if player.battler.feats_to_take > 0:
            if letter_found in range(len(main_feats_list)):
                if main_feats_list[letter_found] in player.battler.combat_feats:
                    player.battler.combat_feats[main_feats_list[letter_found]] += 1
                else:
                    player.battler.combat_feats[main_feats_list[letter_found]] = 1
                player.battler.feats_to_take -= 1
                return MainGameEventHandler(self.engine)

        if player.battler.stats_to_take > 0:
            stat_choice = letter_found - len(main_feats_list)
            if stat_choice >= 0 and stat_choice < 6:
                player.battler.stats_to_take -= 1
                if stat_choice == 0:
                    player.battler.strength += 1
                elif stat_choice == 1:
                    player.battler.dexterity += 1
                elif stat_choice == 2:
                    player.battler.constitution += 1
                elif stat_choice == 3:
                    player.battler.intelligence += 1
                elif stat_choice == 4:
                    player.battler.wisdom += 1
                elif stat_choice == 5:
                    player.battler.charisma += 1
                else:
                    raise Impossible(f"This statistic does not exist.")
                

        if key == tcod.event.K_q or key == tcod.event.K_ESCAPE:
            return MainGameEventHandler(self.engine)

class BuffListHandler(AskUserEventHandler):
    """Displays Buffs and durations.  No interaction.  Esc to quit."""

    def on_render(self, console: tcod.Console) -> None:
        """Display character's buff list.
        """
        super().on_render(console)

        x = 0
        y = 0
        player = self.engine.player

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 20,
            title = f"{player.name}'s current buffs.",
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        y_hold = y + 1

        console.print(x + 1, y_hold, f"{player.name}'s Buffs: (Turn is now {self.engine.current_turn})")
        y_hold += 1
        if len(list(player.battler.current_buffs)) == 0:
            y_hold += 1
            console.print(x + 1, y_hold, f"You have no buffs active.")
        else:
            buffs = list(player.battler.current_buffs)
            buffs.sort()
            for i in range(len(buffs)):
                y_hold += 1
                console.print(x + 1, y_hold, f"{buffs[i]}: {player.battler.current_buffs[buffs[i]] - self.engine.current_turn} turns remaining.")
        console.print(x + 1, y_hold + 2, f"'Esc' or 'Q' to quit.")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        if key == tcod.event.K_ESCAPE or key == tcod.event.K_q:
            return MainGameEventHandler(self.engine)

class CharacterScreenEventHandler(AskUserEventHandler):
    """Displays character statistics.  No interaction.  Esc to quit."""

    def on_render(self, console: tcod.Console) -> None:
        """Display character screen.
        """
        super().on_render(console)

        x = 0
        y = 0
        player = self.engine.player

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 20,
            title = f"{player.name}'s vital statistics",
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        console.print(x + 1, y + 1, f"Character Information")
        console.print(x + 1, y + 2, f"{player.name}: Level {player.level.current_level} {player.battler.hit_dice}.")
        console.print(x + 1, y + 3, f"Experience: {player.level.current_xp}.")
        console.print(x + 1, y + 4, f"Experience to Level: {player.level.experience_to_next_level}.")
        console.print(x + 1, y + 6, f"Maximum HP: {player.battler.max_hp}.  Maximum Mana: {player.battler.max_mana}")
        if player.equipment.main_hand == None:
            console.print(x + 1, y + 7, f"Melee Damage: {player.battler.unarmed_num_dice}d{player.battler.unarmed_size_dice} + {player.battler.melee_to_damage} (+{player.battler.melee_to_hit} to hit).")
        else:
            console.print(x + 1, y + 7, f"Melee Damage: {player.equipment.main_hand.equippable.weapon_num_dice}d{player.equipment.main_hand.equippable.weapon_size_dice} + {player.battler.melee_to_damage}. (+{player.battler.melee_to_hit} to hit.)")
        console.print(x + 1, y + 9, f"Strength: {player.battler.current_str}({player.battler.strength}). Dexterity: {player.battler.current_dex}({player.battler.dexterity}).  Constitution: {player.battler.current_con}({player.battler.constitution}).")
        console.print(x + 1, y + 10, f"Intelligence: {player.battler.current_int}({player.battler.intelligence}).  Wisdom: {player.battler.current_wis}({player.battler.wisdom}).  Charisma: {player.battler.current_cha}({player.battler.charisma}).")
        if player.equipment.ranged != None:
            console.print(x + 1, y + 12, f"Ranged Damage: {player.equipment.ranged.equippable.weapon_num_dice}d{player.equipment.ranged.equippable.weapon_size_dice} + {player.battler.ranged_to_damage}. (+{player.battler.ranged_to_hit} to hit.)")
        console.print(x + 1, y + 14, f"AC: {player.battler.current_ac}. Dex to AC: {player.battler.dex_to_ac}.")
        console.print(x + 1, y + 16, f"BAB: +{player.battler.bab}. Saves: Fort: (+{player.battler.fort_save}), Reflex: (+{player.battler.reflex_save}), Will: (+{player.battler.will_save}).")

        feats_string = "Feats: "
        if len(player.battler.combat_feats) == 0:
            feats_string = feats_string + "None."
        else:
            current_feats_list = list(player.battler.combat_feats)
            for i in range(len(current_feats_list)):
                feats_string += current_feats_list[i] + " "
        console.print(x + 1, y + 18, feats_string)

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        if key == tcod.event.K_ESCAPE or key == tcod.event.K_q:
            return MainGameEventHandler(self.engine)
            
class LevelUpMenuEventHandler(AskUserEventHandler):
    """Selects level up stat gain.  Escape or Q to leave."""

    def on_render(self, console: tcod.Console) -> None:
        """Displays Level Up screen.
        """
        super().on_render(console)

        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = 80,
            height = 10,
            title = 'Select an Option',
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )
        feats_gained = 0
        next_level = self.engine.player.level.current_level + 1
        if self.engine.player.level.current_xp >= self.engine.player.level.experience_to_next_level:
            console.print(x + 1, y + 1, f"Congratulations! You are now level {self.engine.player.level.current_level + 1}!")
            console.print(x + 1, y + 2, f"Max hps increase by placeholder!")
            if self.engine.player.battler.hit_dice == "Fighter":
                console.print(x + 1, y + 3, f"Base Attack Bonus (BAB) increases by 1!")
            elif self.engine.player.battler.hit_dice == "Wizard":
                if (next_level) % 2 == 1:
                    console.print(x + 1, y + 3, f"Base Attack Bonus (BAB) increases by 1!")
            if self.engine.player.battler.hit_dice == "Fighter":
                feats_gained += 1
            elif (next_level) % 2 == 1:
                feats_gained += 1
            if self.engine.player.battler.hit_dice == "Wizard":
                if (next_level) % 5 == 0:
                    feats_gained += 1
            if feats_gained > 0:
                console.print(x + 1, y + 4, f"You gain {feats_gained} feat(s) to learn!")
            if next_level % 4 == 0:
                console.print(x + 1, y + 5, f"You have {self.engine.player.battler.stats_to_take+1} stat points to spend.")
        else:
            console.print(x + 1, y + 1, f"You do not have sufficient experience to level.")

        console.print(x + 1, y + 7, f"Escape or 'q' to continue.")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym

        if key == tcod.event.K_ESCAPE or key == tcod.event.K_q:
            if player.level.current_xp >= player.level.experience_to_next_level:
                self.engine.player.battler.hp = self.engine.player.battler.max_hp
                player.level.current_xp -= player.level.experience_to_next_level
                player.level.current_level += 1
                if player.level.current_level % 4 == 0:
                    self.engine.player.battler.stats_to_take += 1
                if player.battler.hit_dice == "Fighter":
                    self.engine.player.battler.feats_to_take += 1 #Fighters get feats every level
                elif player.level.current_level % 2 == 1:
                    self.engine.player.battler.feats_to_take += 1
                if player.battler.hit_dice == "Wizard":
                    if player.level.current_level % 5 == 0:
                        self.engine.player.battler.feats_to_take += 1
                player.battler.hp = player.battler.max_hp
                player.battler.mana = player.battler.max_mana
            return MainGameEventHandler(self.engine)        

class ShopBuyEventHandler(AskUserEventHandler):
    """This handler selects items to buy from a shop."""


    TITLE = "Shop items for sale"

    def on_render(self, console: tcod.Console) -> None:
        super().on_render(console)
        for shop in self.engine.game_map.shops:
            if shop.x == self.engine.player.x and shop.y == self.engine.player.y:
                number_of_items_for_sale = len(shop.for_sale)
                items_for_sale = shop.for_sale

        height = number_of_items_for_sale + 2

        if height <= 3:
            height = 3

        width = max(40, len(self.TITLE)) + 4

        x = 0
        y = 0

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        if number_of_items_for_sale > 0:
            for i, item in enumerate(items_for_sale):
                item_key = chr(ord("a") + i)
                console.print(x + 1, y + i + 1, f"({item_key}) {item.name} ${item.gold_value}")
        else:
            console.print(x + 1, y + 1, "(Empty)")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a
        for shop in self.engine.game_map.shops:
            if shop.x == self.engine.player.x and shop.y == self.engine.player.y:
                number_of_items_for_sale = len(shop.for_sale)
                items_for_sale = shop.for_sale

        if 0 <= index <= 26:
            try:
                selected_item = items_for_sale[index]
            except IndexError:
                self.engine.message_log.add_message("Invalid entry.", colors.invalid)
                return None
            return self.buy_item(selected_item, player)
        return super().ev_keydown(event)

    def buy_item(
        self, item: Item, player: Entity
        ) -> Optional[ActionOrHandler]:
        """Called when the user selects a valid item."""
        if len(player.inventory.items) >= player.inventory.capacity:
            raise exceptions.Impossible("Your inventory is full")
        elif player.battler.gold >= item.gold_value:
            stacking = False
            for i in range(len(player.inventory.items)):
                if player.inventory.items[i].name == item.name:
                    if item.can_stack == True:
                        player.inventory.items[i].number_in_stack += 1
                        stacking = True
                        self.engine.message_log.add_message(f"You buy another {item.name} for {item.gold_value} gold.", colors.yellow)
            if stacking == False:
                clone_item = copy.deepcopy(item)
                clone_item.parent = player.inventory
                player.inventory.items.append(clone_item)
                self.engine.message_log.add_message(f"You buy {item.name} for {item.gold_value} gold.", colors.yellow)
            player.battler.gold -= item.gold_value
        else :
            self.engine.message_log.add_message("You don't have the gold for that.", colors.yellow) 

class TakeFromBagHandler(AskUserEventHandler):
    """This handler takes from a bag, placing items in inventory."""

    TITLE = "Items in this bag."

    def on_render(self, console: tcod.Console) -> None:
        """Render a bag's inventory."""
        super().on_render(console)
        number_of_items_in_bag = len(self.engine.enchanting_item.bag_inventory.items)

        height = number_of_items_in_bag + 2

        if height <= 3:
            height = 3

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.TITLE) + 4

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        if number_of_items_in_bag > 0:
            for i, item in enumerate(self.engine.enchanting_item.bag_inventory.items):
                item_key = chr(ord("a") + i)
                num_in_pack = ""
                item_gold_str = ""
                if self.engine.enchanting_item.bag_inventory.items[i].number_in_stack > 1:
                    num_in_pack = f" ({self.engine.enchant_item.bag_inventory.items[i].number_in_stack})"
                if item.gold_value > 0:
                    item_gold_str = f" ${item.gold_value}"
                console.print(x + 1, y + i + 1, f"({item_key}) {item.name}" + num_in_pack + item_gold_str)
        else:
            console.print(x + 1, y + 1, "(Empty)")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a
        bag = self.engine.enchanting_item

        if 0 <= index <= 26:
            try:
                selected_item = self.engine.enchanting_item.bag_inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message("Invalid entry.", colors.invalid)
                return None
            if len(player.inventory.items) >= player.inventory.capacity:
                self.engine.message_log.add_message(f"You can't remove items from bags, inventory is full.")
            else:
                player.inventory.items.append(selected_item)
                self.engine.enchanting_item.bag_inventory.items.remove(selected_item)
                self.engine.message_log.add_message(f"You take the {selected_item.name} from the {bag.name}.")
        else:
            return super().ev_keydown(event)

class InventoryEventHandler(AskUserEventHandler):
    """This handler lets the user select an item.

    What happens then depends on the subclass.
    """



    def on_render(self, console: tcod.Console) -> None:
        """Render an inventory menu, which displays the items in the inventory,
        and the letter to select them.  Will move to a different position based
        on where the player is located, so the player can always see where
        they are.
        """
        super().on_render(console)
        number_of_items_in_inventory = len(self.engine.player.inventory.items)

        height = number_of_items_in_inventory + 2

        if height <= 3:
            height = 3

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.TITLE) + 4

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.engine.player.inventory.items):
                item_key = chr(ord("a") + i)
                num_in_pack = ""
                equip_status = ""
                item_gold_str = ""
                if self.engine.player.equipment.main_hand == item:
                    if self.engine.player.equipment.main_hand.equippable.slot == EquipmentSlots.MAIN_HAND:
                        equip_status = " (in main hand)"
                    elif self.engine.player.equipment.main_hand.equippable.slot == EquipmentSlots.TWO_HAND:
                        equip_status = " (in both hands)"
                elif self.engine.player.equipment.off_hand == item:
                    equip_status = " (on off hand)"
                elif self.engine.player.equipment.ranged == item:
                    equip_status = " (as ranged)"
                elif self.engine.player.equipment.body == item:
                    equip_status = " (worn on body)"
                elif self.engine.player.equipment.neck == item:
                    equip_status = " (worn on neck)"
                elif self.engine.player.equipment.waist == item:
                    equip_status = " (on waist)"
                elif self.engine.player.equipment.lring == item:
                    equip_status = " (on left hand)"
                elif self.engine.player.equipment.rring == item:
                    equip_status = " (on right hand)"
                elif self.engine.player.equipment.head == item:
                    equip_status = " (on head)"
                elif self.engine.player.equipment.cloak == item:
                    equip_status = " (worn on shoulders)"
                elif self.engine.player.equipment.eyes == item:
                    equip_status = " (worn on face)"
                elif self.engine.player.equipment.shirt == item:
                    equip_status = " (worn about torso)"
                elif self.engine.player.equipment.wrists == item:
                    equip_status = " (worn on wrists)"
                elif self.engine.player.equipment.feet == item:
                    equip_status = " (worn on feet)"
                elif self.engine.player.equipment.hands == item:
                    equip_status = " (worn on hands)"
                elif self.engine.player.equipment.misc == item:
                    equip_status =  " (worn slotless)"
                if self.engine.player.inventory.items[i].number_in_stack > 1:
                    num_in_pack = f" ({self.engine.player.inventory.items[i].number_in_stack})"
                if item.gold_value > 0:
                    item_gold_str = f" ${item.gold_value}"
                console.print(x + 1, y + i + 1, f"({item_key}) {item.name}" + equip_status + num_in_pack + item_gold_str)
        else:
            console.print(x + 1, y + 1, "(Empty)")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a


        if self.engine.enchant_now == False:
            if 0 <= index <= 26:
                try:
                    selected_item = player.inventory.items[index]
                except IndexError:
                    self.engine.message_log.add_message("Invalid entry.", colors.invalid)
                    return None
                return self.on_item_selected(selected_item)
            return super().ev_keydown(event)
        else:
            return None

class PlaceInBagHandler(InventoryEventHandler):
    """Places one item from inventory in bag."""
    
    TITLE = "Choose an item to place in the bag."

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Return the action for the selected item."""
        
        return None

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        modifier = event.mod
        
        index = key - tcod.event.K_a

        if 0 <= index <= 26:
            try:
                selected_item = player.inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message(f"Invalid entry.", colors.invalid)
                return None
            bag = self.engine.enchanting_item #Need to rename to some chosen item
            if len(bag.bag_inventory.items) >= bag.bag_inventory.capacity:
                self.engine.message_log.add_message(f"Your bag is full.")
            elif selected_item in (player.equipment.main_hand, player.equipment.off_hand, player.equipment.body,
                        player.equipment.neck, player.equipment.ranged, player.equipment.waist,
                        player.equipment.lring, player.equipment.rring, player.equipment.head,
                        player.equipment.cloak, player.equipment.eyes, player.equipment.shirt,
                        player.equipment.wrists, player.equipment.feet, player.equipment.hands,
                        player.equipment.misc):
                self.engine.message_log.add_message("You can't place something you are wearing in a bag.", colors.white)
            elif selected_item.can_stack == True:
                self.engine.message_log.add_message("Stacking items not implemented for bags.", colors.white)
            elif selected_item == bag:
                self.engine.message_log.add_message("You can't place a bag in itself.", colors.white)
            else:
                self.engine.message_log.add_message(f"You place the {selected_item.name} in the {bag.name}.", colors.white)
                bag.bag_inventory.items.append(selected_item)
                player.inventory.items.remove(selected_item)
        return super().ev_keydown(event)

class TextEntryEventHandler(AskUserEventHandler):
    def __init__(self, engine: Engine, input_text: str):
        self.engine = engine
        self.input_text = input_text
    """For user to enter text, naming items or save files."""

    TITLE = "Enter text here."

    def on_render(self, console: tcod.Console) -> None:
        """Renders text being entered.
        """
        super().on_render(console)

        height = 5
        width = 30

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0

        width = len(self.TITLE) + 20

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        console.print(x + 1, y + 1, f"{self.engine.enchanting_item.name}")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        modifier = event.mod
        
        index = key - tcod.event.K_a


        print(f"{chr(ord('a') + index)}")
        print(f"in text input self.input_text")
        if key != tcod.event.K_ESCAPE and key != tcod.event.K_RETURN:
            if modifier & (tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT): #Ugly hack, lshift or rshift
                if key == tcod.event.K_EQUALS:
                    self.input_text += "+"
                if 0 <= index < 26:
                    self.input_text += chr(ord("a") + index - 32)
            else: #Need check for valid ascii, index range?
                self.input_text += chr(ord("a") + index)
                return None
        else:
            self.engine.enchant_now = False
            self.engine.message_log.add_message(f"Text entered.")
            return None

        return super().ev_keydown(event)

class SaveGameEventHandler(TextEntryEventHandler):
    """Save in game slot, name text input."""

    TITLE = "Enter save game name:"

    

class RenameItemEventHandler(InventoryEventHandler):
    """Rename an Item, handy for enchanted gear"""

    TITLE = "Choose an item to rename."

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Return the action for the selected item."""
        
        return None

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        modifier = event.mod
        
        index = key - tcod.event.K_a
        new_item_name = ""

        if self.engine.enchant_now == True:
            if key != tcod.event.K_ESCAPE and key != tcod.event.K_RETURN:
                if modifier & (tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT): #Ugly hack, lshift or rshift
                    if key == tcod.event.K_EQUALS:
                            self.engine.enchanting_item.name += "+"
                    if 0 <= index < 26:
                        self.engine.enchanting_item.name = self.engine.enchanting_item.name + chr(ord("a") + index - 32)
                else: #Need check for valid ascii, index range?
                    if index < 1000:
                        self.engine.enchanting_item.name = self.engine.enchanting_item.name + chr(ord("a") + index)
            else:
                self.engine.message_log.add_message(f"Item renaming complete.")
                self.engine.enchant_now = False

        if self.engine.enchant_now == False:
            if 0 <= index <= 26:
                try:
                    selected_item = player.inventory.items[index]
                except IndexError:
                    self.engine.message_log.add_message(f"Invalid entry.", colors.invalid)
                    return None
                self.engine.message_log.add_message(f"Blanking item name.  Enter new name.", colors.white)
                self.engine.enchanting_item = selected_item
                selected_item.name = ""
                self.engine.enchant_now = True

        return super().ev_keydown(event)

class EnchantEventHandler(AskUserEventHandler):
    """This handler enchants items.

    Only at enchanting shops.
    """

    TITLE = "Enchanter's Shop"
    def on_render(self, console: tcod.Console) -> None:
        """Render an inventory menu, which displays the items in the inventory,
        and the letter to select them.  Will move to a different position based
        on where the player is located, so the player can always see where
        they are.
        """
        super().on_render(console)
        number_of_items_in_inventory = len(self.engine.player.inventory.items)

        height = number_of_items_in_inventory + 2

        if height <= 3:
            height = 3

        x = 0
        y = 0

        width = max(40, len(self.TITLE)) + 4

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.engine.player.inventory.items):
                item_key = chr(ord("a") + i)
                equip_status = ""
                num_of_items = ""
                if self.engine.player.equipment.main_hand == item:
                    if self.engine.player.equipment.main_hand.equippable.slot == EquipmentSlots.MAIN_HAND:
                        equip_status = " (in main hand)"
                    elif self.engine.player.equipment.main_hand.equippable.slot == EquipmentSlots.TWO_HAND:
                        equip_status = " (in both hands)"
                elif self.engine.player.equipment.off_hand == item:
                    equip_status = " (on off hand)"
                elif self.engine.player.equipment.body == item:
                    equip_status = " (worn on body)"
                elif self.engine.player.equipment.neck == item:
                    equip_status = " (worn on neck)"
                elif self.engine.player.equipment.ranged == item:
                    equip_status = " (as ranged)"
                elif self.engine.player.equipment.waist == item:
                    equip_status = " (on waist)"
                elif self.engine.player.equipment.lring == item:
                    equip_status = " (on left hand)"
                elif self.engine.player.equipment.rring == item:
                    equip_status = " (on right hand)"
                elif self.engine.player.equipment.head == item:
                    equip_status = " (on head)"
                elif self.engine.player.equipment.cloak == item:
                    equip_status = " (worn on shoulders)"
                elif self.engine.player.equipment.eyes == item:
                    equip_status = " (worn on face)"
                elif self.engine.player.equipment.shirt == item:
                    equip_status = " (worn about torso)"
                elif self.engine.player.equipment.wrists == item:
                    equip_status = " (worn on wrists)"
                elif self.engine.player.equipment.feet == item:
                    equip_status = " (worn on feet)"
                elif self.engine.player.equipment.hands == item:
                    equip_status = " (worn on hands)"
                elif self.engine.player.equipment.misc == item:
                    equip_status =  " (worn slotless)"
                sell_price = int(item.gold_value / 2)
                if item.number_in_stack > 1:
                    num_of_items = f" ({item.number_in_stack})"
                console.print(x + 1, y + i + 1, f"({item_key}) {item.name}" + num_of_items + equip_status + f" Sell price: {sell_price} gold.")
        else:
            console.print(x + 1, y + 1, "(Empty)")

        if self.engine.enchant_now == True:
            x = 5
            y = 5
            super().on_render(console)
            console.draw_frame(
                x,
                y,
                width = 60,
                height = 20,
                title = "Enchanting Options",
                clear = True,
                fg = (255, 255, 255),
                bg = (0, 0, 0),
            )
            enc_item = self.engine.enchanting_item
            mint = enc_item.equippable.enhance_int_bonus
            slot_choices = []

            slot_choices = components.enchanter.enchanter_options(enc_item, enc_item.equippable.slot, slot_choices)

            console.print(x + 1, y + 20, f"{enc_item.name}, slot: {enc_item.equippable.slot}, list size: {len(slot_choices)}")

            y_hold = 1
            console.print(x + 1, y + y_hold, f"{enc_item.name}, value: {enc_item.gold_value}")

            for choices in range(len(slot_choices) - 1):
                y_hold += 1
                letter = chr(ord("a") + choices)
                console.print(x + 1, y + y_hold,
                    f"({letter}) to improve {slot_choices[choices + 1][0]} bonus to {slot_choices[choices + 1][2]}: {int(slot_choices[choices + 1][2])**2*slot_choices[choices + 1][4]} gold.")
            """
                item_key = chr(ord("a") + i)
            console.print(x + 1, y + 1, f"{enc_item.name}, value: {enc_item.gold_value}")
            console.print(x + 1, y + 2, f"Int Enhancement bonus of + {enc_item.equippable.enhance_int_bonus}")
            console.print(x + 1, y + 3, f"(a) to Improve Int bonus to 2: 4000 - " + str(mint**2*1000) + " gold.")
            console.print(x + 1, y + 4, f"(b) to Improve Int bonus to 4: 16000 - " + str(mint**2*1000) + " gold.")
            console.print(x + 1, y + 5, f"(c) to Improve Int bonus to 6: 36000 - " + str(mint**2*1000) + " gold.")
            console.print(x + 1, y + 6, f"Bonus value: " + str(mint**2*1000))
            """

    def ev_keydown(
        self, event: tcod.event.KeyDown,
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a
        test = False
        discount = 0

        enc_item = self.engine.enchanting_item
        slot_choices = []

        if self.engine.enchant_now == True:
            if key == tcod.event.K_ESCAPE:
                self.engine.enchant_now = False
                self.engine.message_log.add_message("Enchant Aborted.", colors.invalid)
                return None
            slot_choices = components.enchanter.enchanter_options(enc_item, enc_item.equippable.slot, slot_choices)
            if slot_choices[index + 1][3] == "square":
                cost = slot_choices[index +1 ][2]**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][3] == "square+2":
                cost = (slot_choices[index + 1][2] + 2)**2*slot_choices[index + 1][4]
            else:
                self.engine.message_log.add_message("Enchant formula not recognized.", colors.invalid)
                self.engine.enchant_now = False
                return None
            if slot_choices[index + 1][0] == "Int":
                discount = enc_item.equippable.enhance_int_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Wis":
                discount = enc_item.equippable.enhance_wis_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Cha":
                discount = enc_item.equippable.enhance_cha_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Str":
                discount = enc_item.equippable.enhance_str_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Dex":
                discount = enc_item.equippable.enhance_dex_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Con":
                discount = enc_item.equippable.enhance_con_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Armor":
                discount = enc_item.equippable.enhance_armor_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Weapon":
                discount = enc_item.equippable.enhance_melee_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Ranged Weapon":
                discount = enc_item.equippable.enhance_ranged_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Shield":
                discount = enc_item.equippable.enhance_shield_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Animated Shield":
                discount = (enc_item.equippable.enhance_shield_bonus + 2)**2*slot_choices[index + 1][4] #Animated costs + 2 bonus
            elif slot_choices[index + 1][0] == "Ring of Protection":
                discount = enc_item.equippable.deflection_bonus**2*slot_choices[index + 1][4]
            elif slot_choices[index + 1][0] == "Amulet of Natural Armor":
                discount = enc_item.equippable.enhance_na_bonus**2*slot_choices[index + 1][4]
            else:
                self.engine.message_log.add_message("Discount option not found.", colors.invalid)
            if player.battler.gold < (cost - discount):
                self.engine.message_log.add_message("You don't have enough gold.", colors.invalid)
            elif discount >= cost:
                self.engine.message_log.add_message("That wouldn't improve the item.", colors.invalid)
            else:
                player.battler.gold -= (cost - discount)
                self.engine.message_log.add_message(f"Your {slot_choices[0][1]} now gives + {slot_choices[index+1][2]} to {slot_choices[index+1][0]}.")
                if slot_choices[index + 1][0] == "Int":
                    enc_item.equippable.enhance_int_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Wis":
                    enc_item.equippable.enhance_wis_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Cha":
                    enc_item.equippable.enhance_cha_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Str":
                    enc_item.equippable.enhance_str_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Dex":
                    enc_item.equippable.enhance_dex_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Con":
                    enc_item.equippable.enhance_con_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Armor":
                    enc_item.equippable.enhance_armor_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Weapon":
                    enc_item.equippable.enhance_melee_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Ranged Weapon":
                    enc_item.equippable.enhance_ranged_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Shield":
                    enc_item.equippable.enhance_shield_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Animated Shield":
                    enc_item.equippable.enhance_shield_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Ring of Protection":
                    enc_item.equippable.deflection_bonus = slot_choices[index + 1][2]
                elif slot_choices[index + 1][0] == "Amulet of Natural Armor":
                    enc_item.equippable.enhance_na_bonus = slot_choices[index + 1][2]
                else:
                    self.engine.message_log.add_message("Enchant option not found.", colors.invalid)
            self.engine.enchant_now = False
            return None

        if 0 <= index <= 26:
            try:
                selected_item = player.inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message("Invalid entry.", colors.invalid)
                return None
            return self.enchant_item(selected_item)
        return super().ev_keydown(event)

    def enchant_item(self, item: Item) -> Optional[Action]:
        """Called when the user selects a valid item."""
        player = self.engine.player
        if item in (player.equipment.main_hand, player.equipment.off_hand, player.equipment.body,
                    player.equipment.neck, player.equipment.ranged, player.equipment.waist,
                    player.equipment.lring, player.equipment.rring, player.equipment.head,
                    player.equipment.cloak, player.equipment.eyes, player.equipment.shirt,
                    player.equipment.wrists, player.equipment.feet, player.equipment.hands,
                    player.equipment.misc):
            self.engine.message_log.add_message("You can't enchant something you are wearing.", colors.white)
        elif item.can_stack == True:
            self.engine.message_log.add_message("The shop has no interest in that item.", colors.white)
        elif item.equippable != None:
            self.engine.enchanting_item = item
            self.engine.message_log.add_message(f"Enchanting item is: {self.engine.enchanting_item.name}")
            self.engine.enchant_now = True
            return None
        else:
            raise Impossible(f"This item is not valid for enchanting.")


class ShopSellEventHandler(AskUserEventHandler):
    """This event sells to a shop."""

    TITLE = "Stuff to sell."

    def on_render(self, console: tcod.Console) -> None:
        """Render an inventory menu, which displays the items in the inventory,
        and the letter to select them.  Will move to a different position based
        on where the player is located, so the player can always see where
        they are.
        """
        super().on_render(console)
        number_of_items_in_inventory = len(self.engine.player.inventory.items)

        height = number_of_items_in_inventory + 2

        if height <= 3:
            height = 3

        x = 0
        y = 0

        width = max(40, len(self.TITLE)) + 4

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.engine.player.inventory.items):
                item_key = chr(ord("a") + i)
                equip_status = ""
                num_of_items = ""
                if self.engine.player.equipment.main_hand == item:
                    if self.engine.player.equipment.main_hand.equippable.slot == EquipmentSlots.MAIN_HAND:
                        equip_status = " (in main hand)"
                    elif self.engine.player.equipment.main_hand.equippable.slot == EquipmentSlots.TWO_HAND:
                        equip_status = " (in both hands)"
                elif self.engine.player.equipment.off_hand == item:
                    equip_status = " (on off hand)"
                elif self.engine.player.equipment.body == item:
                    equip_status = " (worn on body)"
                elif self.engine.player.equipment.neck == item:
                    equip_status = " (worn on neck)"
                elif self.engine.player.equipment.ranged == item:
                    equip_status = " (as ranged)"
                elif self.engine.player.equipment.waist == item:
                    equip_status = " (on waist)"
                elif self.engine.player.equipment.lring == item:
                    equip_status = " (on left hand)"
                elif self.engine.player.equipment.rring == item:
                    equip_status = " (on right hand)"
                elif self.engine.player.equipment.head == item:
                    equip_status = " (on head)"
                elif self.engine.player.equipment.cloak == item:
                    equip_status = " (worn on shoulders)"
                elif self.engine.player.equipment.eyes == item:
                    equip_status = " (worn on face)"
                elif self.engine.player.equipment.shirt == item:
                    equip_status = " (worn about torso)"
                elif self.engine.player.equipment.wrists == item:
                    equip_status = " (worn on wrists)"
                elif self.engine.player.equipment.feet == item:
                    equip_status = " (worn on feet)"
                elif self.engine.player.equipment.hands == item:
                    equip_status = " (worn on hands)"
                elif self.engine.player.equipment.misc == item:
                    equip_status =  " (worn slotless)"
                sell_price = int(item.gold_value / 2)
                if item.number_in_stack > 1:
                    num_of_items = f" ({item.number_in_stack})"
                console.print(x + 1, y + i + 1, f"({item_key}) {item.name}" + num_of_items + equip_status + f" Sell price: {sell_price} gold.")
        else:
            console.print(x + 1, y + 1, "(Empty)")

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a

        if 0 <= index <= 26:
            try:
                selected_item = player.inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message("Invalid entry.", colors.invalid)
                return None
            return self.sell_item(selected_item)
        return super().ev_keydown(event)

    def sell_item(self, item: Item) -> Optional[Action]:
        """Called when the user selects a valid item."""
        player = self.engine.player
        if item in (player.equipment.main_hand, player.equipment.off_hand, player.equipment.body,
                    player.equipment.neck, player.equipment.ranged, player.equipment.waist,
                    player.equipment.lring, player.equipment.rring, player.equipment.head,
                    player.equipment.cloak, player.equipment.eyes, player.equipment.shirt,
                    player.equipment.wrists, player.equipment.feet, player.equipment.hands,
                    player.equipment.misc):
            self.engine.message_log.add_message("You can't sell something you are wearing.", colors.white)
        elif item.gold_value > 0:
            player.battler.gold += int(item.gold_value / 2)
            self.engine.message_log.add_message(f"You sell the {item.name} for {int(item.gold_value / 2)} gold.", colors.yellow)
            if item.number_in_stack > 1:
                item.number_in_stack -= 1
            else:
                player.inventory.items.remove(item)
        else:
            self.engine.message_log.add_message("The shop has no interest in that item.", colors.white)

class InventoryActivateHandler(InventoryEventHandler):
    """Handle using an inventory item."""

    TITLE = "Select an item to use, letter corresponds to item."

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Return the action for the selected item."""
        if item.consumable:
            return item.consumable.get_action(self.engine.player)
        elif item.equippable:
            return item.equippable.activate(self.engine.player)
        elif isinstance(item, Bag): #item.name == "Red Bag":
            self.engine.enchanting_item = item
            return UseBagHandler(self.engine)

class InventoryDropHandler(InventoryEventHandler):
    """Handle dropping an inventory item."""

    TITLE = "Select an item to drop, letter corresponds to item."

    def on_item_selected(self, item: Item) -> Optional[ActionOrHandler]:
        """Drop this item."""
        return actions.DropItem(self.engine.player, item)

class EquipmentHandler(AskUserEventHandler):
    """Handle removing or viewing equipped items."""

    TITLE = "Select an item remove, letter corresponds to item."
            
    def on_render(self, console: tcod.Console) -> None:
        """Render equipment screen.  This displays worn gear,
        and allows the user to remove items.
        """
        super().on_render(console)

        height = 30

        x = 0
        y = 0

        width = max(40, len(self.TITLE)) + 4

        console.draw_frame(
            x = x,
            y = y,
            width = width,
            height = height,
            title = self.TITLE,
            clear = True,
            fg = (255, 255, 255),
            bg = (0, 0, 0),
        )

        equipment_set = ["in main hand", "on off hand", "worn on body", "worn on neck", "as ranged", "on waist", "on left hand", "on right hand",
                     "on head", "worn on shoulders", "worn on eyes", "worn about torso", "worn on wrists", "worn on feet", "worn on hands",
                     "as Animated Shield"]

        """
        gear_list = [f"{self.engine.player.equipment.main_hand.name}", f"{self.engine.player.equipment.off_hand.name}",
                     f"{self.engine.player.equipment.body.name}", f"{self.engine.player.equipment.neck.name}",
                     f"{self.engine.player.equipment.ranged.name}", f"{self.engine.player.equipment.waist.name}",
                     f"{self.engine.player.equipment.lring.name}", f"{self.engine.player.equipment.rring.name}",
                     f"{self.engine.player.equipment.head.name}", f"{self.engine.player.equipment.cloak.name}",
                     f"{self.engine.player.equipment.eyes.name}", f"{self.engine.player.equipment.shirt.name}",
                     f"{self.engine.player.equipment.wrists.name}", f"{self.engine.player.equipment.feet.name}",
                     f"{self.engine.player.equipment.hands.name}", f"{self.engine.player.equipment.misc.name}"]
        """
        check_list = [self.engine.player.equipment.main_hand, self.engine.player.equipment.off_hand,
                     self.engine.player.equipment.body, self.engine.player.equipment.neck,
                     self.engine.player.equipment.ranged, self.engine.player.equipment.waist,
                     self.engine.player.equipment.lring, self.engine.player.equipment.rring,
                     self.engine.player.equipment.head, self.engine.player.equipment.cloak,
                     self.engine.player.equipment.eyes, self.engine.player.equipment.shirt,
                     self.engine.player.equipment.wrists, self.engine.player.equipment.feet,
                     self.engine.player.equipment.hands, self.engine.player.equipment.misc]

        for gear in range(len(equipment_set)):
            line = f"[None]"
            if check_list[gear] == None:
                line = f"[None] ({equipment_set[gear]})"
            else:
                letter = chr(ord("a") + gear)
                line = f"({letter})    {check_list[gear].name} ({equipment_set[gear]})"
            console.print(x + 1, y + gear + 1, line)
                

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a

        check_list = [self.engine.player.equipment.main_hand, self.engine.player.equipment.off_hand,
                     self.engine.player.equipment.body, self.engine.player.equipment.neck,
                     self.engine.player.equipment.ranged, self.engine.player.equipment.waist,
                     self.engine.player.equipment.lring, self.engine.player.equipment.rring,
                     self.engine.player.equipment.head, self.engine.player.equipment.cloak,
                     self.engine.player.equipment.eyes, self.engine.player.equipment.shirt,
                     self.engine.player.equipment.wrists, self.engine.player.equipment.feet,
                     self.engine.player.equipment.hands, self.engine.player.equipment.misc]

        if len(check_list) > index >= 0 and check_list[index] != None:
            check_list[index].equippable.activate(self.engine.player)
        if key == tcod.event.K_ESCAPE:
            return super().ev_keydown(event)

class SelectIndexHandler(AskUserEventHandler):
    """Handles asking the user for an index on the map."""

    def __init__(self, engine: Engine):
        """Sets the cursor to the player when this handler is constructed."""
        super().__init__(engine)
        player = self.engine.player
        if self.engine.last_target.is_alive == True and self.engine.game_map.visible[self.engine.last_target.x][self.engine.last_target.y] == True:
            engine.mouse_location = self.engine.last_target.x, self.engine.last_target.y
        else:
            engine.mouse_location = player.x, player.y
            engine.last_target = player

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)
        x, y, = self.engine.mouse_location
        console.tiles_rgb["bg"][x, y] = colors.white
        console.tiles_rgb["fg"][x, y] = colors.black

    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1 # Holding modifier keys will speed up key movement.
            if event.mod & (tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT):
                modifier *= 5
            if event.mod & (tcod.event.KMOD_LCTRL | tcod.event.KMOD_RCTRL):
                modifier *= 10
            if event.mod & (tcod.event.KMOD_LALT | tcod.event.KMOD_RALT):
                modifier *= 20

            x, y = self.engine.mouse_location
            dx, dy = MOVE_KEYS[key]
            x += dx * modifier
            y += dy * modifier
            # Clamp the cursor index to the map size.
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None
        elif key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
        ) -> Optional[ActionOrHandler]:
        "Left click confirms a selction."""
        if self.engine.game_map.in_bounds(*event.tile):
            if event.button == 1:
                return self.on_index_selected(*event.tile)
        return super().ev_mousebuttondown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Called when an index is selected."""
        raise NotImplementedError()

class SelectMonsterHandler(AskUserEventHandler):
    """Rapidly target monsters.  Cone by arrow/number, closest first.."""

    def __init__(self, engine: Engine):
        """Sets the cursor to the player when this handler is constructed."""
        super().__init__(engine)
        player = self.engine.player
        if self.engine.last_target.is_alive == True and self.engine.game_map.visible[self.engine.last_target.x][self.engine.last_target.y] == True:
            engine.mouse_location = self.engine.last_target.x, self.engine.last_target.y # If alive and visible, target last opponent.
        else: # Without this check you can target around corners.  If not visible, reset to player so you can't.
            engine.mouse_location = player.x, player.y

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)
        x, y, = self.engine.mouse_location
        console.tiles_rgb["bg"][x, y] = colors.white
        console.tiles_rgb["fg"][x, y] = colors.black
        
    def ev_keydown(
        self, event: tcod.event.KeyDown
        ) -> Optional[ActionOrHandler]:
        """Check for key movement or confirmation keys."""
        key = event.sym
        NSEW_KEYS = (tcod.event.K_UP, tcod.event.K_KP_8, tcod.event.K_DOWN, tcod.event.K_KP_2,
                     tcod.event.K_LEFT, tcod.event.K_KP_4, tcod.event.K_RIGHT, tcod.event.K_KP_6)

        quick_list = []
        dist_list = []
        player = self.engine.player
        lastkey = self.engine.last_keypress
        num_times_pressed = self.engine.num_pressed
        
        if key in NSEW_KEYS:
            if lastkey == "None":
                x, y = player.x, player.y
            """Checks for monsters in cone for cardinal directions: N, S, E, W."""
            if key in (tcod.event.K_UP, tcod.event.K_KP_8):
                if lastkey == "Up":
                    self.engine.num_pressed += 1
                else:
                    self.engine.num_pressed = 0
                self.engine.last_keypress = "Up"
                for monster in self.engine.game_map.actors:
                    if monster.y < self.engine.player.y:
                        if self.engine.game_map.visible[monster.x, monster.y]:
                            if abs(monster.y - player.y) >= abs(monster.x - player.x):
                                quick_list.append(monster)
            elif key in (tcod.event.K_DOWN, tcod.event.K_KP_2):
                if lastkey == "Down":
                    self.engine.num_pressed += 1
                else:
                    self.engine.num_pressed = 0
                self.engine.last_keypress = "Down"
                for monster in self.engine.game_map.actors:
                    if monster.y > self.engine.player.y:
                        if self.engine.game_map.visible[monster.x, monster.y]:
                            if abs(monster.y - player.y) >= abs(monster.x - player.x):
                                quick_list.append(monster)
            elif key in (tcod.event.K_LEFT, tcod.event.K_KP_4):
                if lastkey == "Left":
                    self.engine.num_pressed += 1
                else:
                    self.engine.num_pressed = 0
                self.engine.last_keypress = "Left"
                for monster in self.engine.game_map.actors:
                    if monster.x < self.engine.player.x:
                        if self.engine.game_map.visible[monster.x, monster.y]:
                            if abs(monster.y - player.y) <= abs(monster.x - player.x):
                                quick_list.append(monster)             
            elif key in (tcod.event.K_RIGHT, tcod.event.K_KP_6):
                if lastkey == "Right":
                    self.engine.num_pressed += 1
                else:
                    self.engine.num_pressed = 0
                self.engine.last_keypress = "Right"
                for monster in self.engine.game_map.actors:
                    if monster.x > self.engine.player.x:
                        if self.engine.game_map.visible[monster.x, monster.y]:
                            if abs(monster.y - player.y) <= abs(monster.x - player.x):
                                quick_list.append(monster)
            """Sort by distance, closest first."""
            for monster in quick_list:
                dist = math.sqrt((player.x - monster.x)**2 + (player.y - monster.y)**2)
                dist_list.append([dist, monster])
            dist_list = sorted(dist_list, key=lambda x: x[0])
            if dist_list:
                if self.engine.num_pressed > len(dist_list) - 1:
                    self.engine.num_pressed = 0
                    self.engine.last_keypress = "None"                
                target = dist_list[self.engine.num_pressed][1]
                x, y = target.x, target.y
            else:
                x, y = player.x, player.y
                    
            x = max(0, min(x, self.engine.game_map.width - 1))
            y = max(0, min(y, self.engine.game_map.height - 1))
            self.engine.mouse_location = x, y
            return None
        
        if key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(
        self, event: tcod.event.MouseButtonDown
        ) -> Optional[ActionOrHandler]:
        "Left click confirms a selction."""
        if self.engine.game_map.in_bounds(*event.tile):
            if event.button == 1:
                return self.on_index_selected(*event.tile)
        return super().ev_mousebuttondown(event)

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        """Called when an index is selected."""
        raise NotImplementedError()


class ThrowShootEventHandler(SelectMonsterHandler):
    """Throws or Shoots at target selected by keyboard or mouse."""

    def __init__(
        self, engine: Engine, callback: Callable[[Tuple[int, int]],
                                                 Optional[ActionOrHandler]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> RangedAction:
        return self.callback((x, y))

class LookHandler(SelectIndexHandler):
    "Lets the player look around using the keyboard."""

    def on_index_selected(self, x: int, y: int) -> None:
        """Return to main handler."""
        return MainGameEventHandler(self.engine)

class SingleMeleeAttackHandler(SelectIndexHandler):
    "Handles targeting a single melee enemy."

    def __init__(
        self,
        engine: Engine,
        callback: Callable[[Tuple[int, int]], Optional[ActionOrHandler]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return self.callback((x, y))

class SingleRangedAttackHandler(SelectMonsterHandler):
    "Handles targeting a single enemy.  Only the enemy selected will be affected."""

    def __init__(
        self,
        engine: Engine,
        callback: Callable[[Tuple[int, int]], Optional[ActionOrHandler]]
    ):
        super().__init__(engine)

        self.callback = callback

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return self.callback((x, y))

class AreaRangedAttackHandler(SelectIndexHandler):
    """
    Handles targeting an area with a given radious.
    Any entity within the area will be affected.
    """

    def __init__(
        self,
        engine: Engine,
        radius: int,
        callback: Callable[[Tuple[int, int]], Optional[ActionOrHandler]],
    ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)

        x, y = self.engine.mouse_location

        # Draw a rectangle around the targeted area, so the player
        # can see the affected tiles
        console.draw_frame(
            x = x - self.radius - 1,
            y = y - self.radius - 1,
            width = self.radius ** 2,
            height = self.radius ** 2,
            fg = colors.red,
            clear = False,
        )

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return self.callback((x, y))

class SummonMonsterHandler(SelectIndexHandler):
    """
    Handles targeting a square to summon a monster.
    """

    def __init__(
        self,
        engine: Engine,
        callback: Callable[[Tuple[int, int]], Optional[ActionOrHandler]],
        radius: int = 0,
    ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, console: tcod.Console) -> None:
        """Highlight the tile under the cursor."""
        super().on_render(console)

        x, y = self.engine.mouse_location

        # Draw a rectangle around the targeted area, so the player
        # can see the affected tiles
        console.draw_frame(
            x = x - self.radius - 1,
            y = y - self.radius - 1,
            width = 1, # self.radius ** 2,
            height = 1, # self.radius ** 2,
            fg = colors.red,
            clear = False,
        )

    def on_index_selected(self, x: int, y: int) -> Optional[ActionOrHandler]:
        return self.callback((x, y))
    
class TakeStairsHandler(EventHandler):
    #Takes stairs, up or down, generating new level.
    #No longer implements, see Actions
    
    def ___init__(
        self,
        engine: Engine,
    ):
        constants = get_constants()
        print("did it get here?")
        for entity in self.engine.game_map.entities:
            if (entity.stairs and entity.x == self.engine.player.x and entity.y == self.engine.player.y):
                self.engine.game_map = generate_dungeon(
                    max_rooms = constants['max_rooms'],
                    room_min_size = constants['room_min_size'],
                    room_max_size = constants['room_max_size'],
                    map_width = constants['map_width'],
                    map_height = constants['map_height'],
                    dungeon_level = self.engine.game_map.dungeon_level + entity.stairs.stairs,
                    engine = self.engine,
                )
            return MainGameEventHandler(self.engine)
        print('no stairs here.')
        return MainGameEventHandler(self.engine)

