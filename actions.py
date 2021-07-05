from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

import colors
import exceptions
import math
import copy
import entity_factories

from random import randint
from entity import Actor, Entity, Item, Gold, Shop

if TYPE_CHECKING:
    from engine import Engine
    from entity import Actor, Entity, Item, Gold, Shop
        
def check_turn_advance(engine: Engine, entity: Actor):
    if entity == engine.player:
        engine.current_turn += 1

    player_buffs = list(engine.player.battler.current_buffs)
    for buff in player_buffs:
        if engine.player.battler.current_buffs[buff] < engine.current_turn:
            engine.message_log.add_message(f"{engine.player.name}'s {buff} fades.", colors.red)
            del engine.player.battler.current_buffs[buff]

    remove_summons = []
    for npc in engine.game_map.actors:
        if npc == engine.player:
            continue
        npc_buffs = list(npc.battler.current_buffs)
        for buff in npc_buffs:
            if npc.battler.current_buffs[buff] < engine.current_turn:
                if buff == "Player Summoned":
                    remove_summons.append(npc)
                else:
                    engine.message_log.add_message(f"{npc.name}'s {buff} fades.", colors.red)
                    del npc.battler.current_buffs[buff]

    for removes in remove_summons:
        engine.message_log.add_message(f"{removes.name} vanishes in a puff of smoke.", colors.red)
        engine.game_map.entities.remove(removes)
            

def get_size_damage_diff(num_damage_dice: int , size_damage_dice: int, entity: Actor):
    main_damage_list = [[1, 1], [1, 2], [1, 3], [1, 4], [1, 6], [1, 8], [2, 6], [3, 6], [4, 6],
                        [6, 6], [8, 6]]
    twodfour_damage_list = [[1, 1], [1, 2], [1, 3], [1, 4], [1, 6], [2, 4], [2, 6], [3, 6], [4, 6],
                          [6, 6], [8, 6]]
    onedten_damage_list = [[1, 1], [1, 2], [1, 3], [1, 4], [1, 6], [1, 8], [1, 10], [2, 8], [3, 8],
                         [4, 8], [6, 8]]
    onedtwelve_damage_list = [[1, 1], [1, 2], [1, 3], [1, 4], [1, 6], [1, 8], [1, 10], [1, 12], [3, 6],
                              [4, 6], [6, 6], [8, 6]]
    twodsix_damage_list = [[1, 1], [1, 2], [1, 3], [1, 4], [1, 6], [1, 8], [1, 10], [2, 6], [3, 6],
                           [4, 6], [6, 6], [8, 6]]
    
    if (num_damage_dice, size_damage_dice) == (2, 4):
        working_list = twodfour_damage_list
    elif (num_damage_dice, size_damage_dice) == (1, 10):
        working_list = onedten_damage_list
    elif (num_damage_dice, size_damage_dice) == (1, 12):
        working_list = onedtwelve_damage_list
    elif (num_damage_dice, size_damage_dice) == (2, 6):
        working_list = twodsix_damage_list
    else:
        working_list = main_damage_list

    current_position = working_list.index([num_damage_dice, size_damage_dice])

    if entity.battler.size == "Medium":
        pass
    elif entity.battler.size == "Small":
        current_position -= 1
    elif entity.battler.size == "Tiny":
        current_position -= 2
    elif entity.battler.size == "Large":
        current_position += 1

    return working_list[current_position]
        

class Action:
    def __init__(self, entity: Actor, penalty: int = 0) -> None:
        super().__init__()
        self.entity = entity
        self.penalty = penalty

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.gamemap.engine

    def perform(self) -> None:
        """Perform this action with the objects needed to determine its scope.

        `self.engine` is the scope this action is being performed in.

        `self.entity` is the object performing the action.

        This method must be overridden by Action subclasses.
        """
        raise NotImplementedError()

class ToggleCombatModeAction(Action):
    """Toggles between Melee and Ranged.  Quick Draw makes it free action."""
    """Otherwise takes turn to do so."""

    def __init__(self, entity: Actor):
        super().__init__(entity)

    def perform(self) -> None:
        inventory = self.entity.inventory

        if self.entity.battler.combat_mode == "Ranged":
            self.entity.battler.combat_mode = "Melee"
            if "Quick Draw" in self.entity.battler.combat_feats:
                raise exceptions.Impossible("You quickly shift to melee.")
            else:
                self.engine.message_log.add_message(f"Now in Melee mode.")
                check_turn_advance(self.engine, self.entity)
                return
        elif self.entity.battler.combat_mode == "Melee":
            if self.entity.equipment.ranged == None:
                self.engine.message_log.add_message(f"You have no ranged weapon")
            else:
                self.entity.battler.combat_mode = "Ranged"
                if "Quick Draw" in self.entity.battler.combat_feats:
                    raise exceptions.Impossible("You quickly shift to your ranged weapon.")
                else:
                    self.engine.message_log.add_message(f"Now in ranged mode.")
                    check_turn_advance(self.engine, self.entity)
                    return
        else:
            raise exceptions.Impossible("Error: Combat mode not melee or ranged found.")

class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Actor):
        super().__init__(entity)

    def perform(self) -> None:
        actor_location_x = self.entity.x
        actor_location_y = self.entity.y
        inventory = self.entity.inventory

        for item in self.engine.game_map.items:
            if actor_location_x == item.x and actor_location_y == item.y:
                if item.can_stack == True:
                    for i in range(len(self.entity.inventory.items)):
                        if item.name == self.entity.inventory.items[i].name:
                            self.entity.inventory.items[i].number_in_stack += 1
                            self.engine.message_log.add_message(f"You have one more {item.name}!")
                            self.engine.game_map.entities.remove(item)
                            return

                if len(inventory.items) >= inventory.capacity:
                    raise exceptions.Impossible("Your inventory is full.")

                self.engine.game_map.entities.remove(item)
                item.parent = self.entity.inventory
                inventory.items.append(item)

                self.engine.message_log.add_message(f"You picked up the {item.name}!")
                check_turn_advance(self.engine, self.entity)
                return
        raise exceptions.Impossible("There is nothing here to pick up.")

class RangedAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
        penalty: int = 0,
        ranged_attack_list = [],
    ):
        super().__init__(entity)
        self.target_xy = target_xy
        self.penalty = penalty
        self.ranged_attack_list = ranged_attack_list
    @property
    def target_actor(self) -> Optional[Actor]:
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        """Fire bow or use thrown weapon."""
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")
        if self.entity == target:
            raise exceptions.Impossible("You can't target yourself.")

        damage = 0
        dam_string = "shoots"
        crit_needs = 20
        crit_mult = 2

        if "Point Blank Shot" in self.entity.battler.combat_feats and self.entity.distance(target.x, target.y) <= 6:
            pb = 1
        else:
            pb = 0

        if self.entity.equipment.ranged != None:
            dam_string = self.entity.equipment.ranged.equippable.damage_name
            num_damage_dice = self.entity.equipment.ranged.equippable.weapon_num_dice
            size_damage_dice = self.entity.equipment.ranged.equippable.weapon_size_dice
            num_damage_dice, size_damage_dice = get_size_damage_diff(num_damage_dice, size_damage_dice, self.entity)
            crit_needs = self.entity.equipment.ranged.equippable.crit_needs
            crit_mult = self.entity.equipment.ranged.equippable.crit_mult
        elif len(self.ranged_attack_list) == 0:
            raise exceptions.Impossible("You have no ranged weapon.")
        else:
            dam_string = self.ranged_attack_list[1]
            num_damage_dice = self.ranged_attack_list[2]
            size_damage_dice = self.ranged_attack_list[3]

        for i in range(num_damage_dice):
            damage = damage + randint(1, size_damage_dice)

            damage = damage + self.entity.battler.ranged_to_damage + pb #half damage on secondary attacks?
        attack_desc = f"{self.entity.name.capitalize()} {dam_string} {target.name}"
        if self.entity is self.engine.player:
            attack_color = colors.player_atk
            self.engine.last_target = target
        else:
            attack_color = colors.enemy_atk

        (damage, attack_desc) = HandleAttack(self.entity.battler.ranged_to_hit, target.battler.current_ac, damage, attack_desc, crit_needs, crit_mult)
        self.engine.message_log.add_message(attack_desc, attack_color)
        target.battler.hp -= damage

class FullAttackRangedAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
        penalty: int = 0,
    ):
        super().__init__(entity)
        self.target_xy = target_xy
        self.penalty = penalty

    @property
    def target_actor(self) -> Optional[Actor]:
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        target = self.target_actor
        if self.entity.battler.combat_mode != "Ranged":
            if "Quick Draw" in self.entity.battler.combat_feats:
                self.engine.message_log.add_message(f"{self.entity.name} quickly switches to a ranged weapon.")
                self.entity.battler.combat_mode = "Ranged"
            elif self.entity.equipment.ranged != None:
                self.engine.message_log.add_message(f"{self.entity.name} struggles to change to a ranged weapon.")
                self.entity.battler.combat_mode = "Ranged"
                check_turn_advance(self.engine, self.entity)
                return RangedAction(self.entity, self.target_xy).perform()
            elif len(self.entity.battler.full_ranged_attack) > 0:
                self.engine.message_log.add_message(f"{self.entity.name} struggles to change to a ranged weapon.")
                self.entity.battler.combat_mode = "Ranged"
                check_turn_advance(self.engine, self.entity)
                return RangedAction(self.entity, self.target_xy, 0, self.entity.battler.full_ranged_attack[0]).perform()
            #Doesn't handle secondary attack in first slot of full ranged attack, ignores -5 hit penalty, fix
        if not target:
            raise exceptions.Impossible("Nothing to attack.")
        if self.entity == target:
            raise exceptions.Impossible("You can't target yourself.")
        
        if self.entity.equipment.ranged != None:
            if self.entity.battler.bab < 6: #BAB can be 0, still 1 attack
                if "Rapid Shot" not in self.entity.battler.combat_feats:
                    check_turn_advance(self.engine, self.entity)
                    return RangedAction(self.entity, self.target_xy).perform()
                else:
                    RangedAction(self.entity, self.target_xy).perform()
                    if target.battler.is_dead == True:
                        target = FindNewTarget(self.engine, target, ranged = True)
                        if target == None:
                            check_turn_advance(self.engine, self.entity)
                            return None
                        self.engine.message_log.add_message(f"{self.entity.name} retargets to {target.name}.", colors.player_atk)
                        self.target_xy = (target.x, target.y)
                check_turn_advance(self.engine, self.entity)
                return RangedAction(self.entity, self.target_xy).perform()
            else: #Iteratives
                bab_counter = self.entity.battler.bab
                if "Rapid Shot" in self.entity.battler.combat_feats:
                    RangedAction(self.entity, self.target_xy).perform()
                while bab_counter > 0:
                    if target.battler.is_dead == True:
                        target = FindNewTarget(self.engine, target, ranged = True)
                        if target == None:
                            check_turn_advance(self.engine, self.entity)
                            return None
                        self.engine.message_log.add_message(f"{self.entity.name} retargets to {target.name}.", colors.player_atk)
                        self.target_xy = (target.x, target.y)
                    RangedAction(self.entity, self.target_xy, self.penalty).perform()
                    bab_counter -= 5
                    self.penalty += 5
                check_turn_advance(self.engine, self.entity)
                return None
        elif len(self.entity.battler.full_ranged_attack) == 0: #No weapons, no full attack
            raise exceptions.Impossible("You have no ranged weapon.")

        else:
            for i in range(len(self.entity.battler.full_ranged_attack)):
                if target.battler.is_dead == True:
                    check_turn_advance(self.engine, self.entity)
                    return None
                if self.entity.battler.full_ranged_attack[i][0] == 'P': #Primary attack
                    RangedAction(self.entity, self.target_xy, 0, self.entity.battler.full_ranged_attack[i]).perform()
                elif self.entity.battler.full_ranged_attack[i][0] == 'S': #Secondary attack
                    RangedAction(self.entity, self.target_xy, 5, self.entity.battler.full_ranged_attack[i]).perform()
            check_turn_advance(self.engine, self.entity)
            return None

def FindNewTarget(engine: Engine, target, ranged: bool=True):
    for newtarget in engine.game_map.actors:
        if newtarget == target or newtarget == engine.player:
            continue
        if engine.game_map.visible[newtarget.x, newtarget.y]:
            if ranged == True:
                return newtarget
            else:
                if InMeleeReach(engine.player, newtarget):
                    return newtarget
    return None

def InMeleeReach(attacker, target):
    melee_reach = 1.5 # Could be awhile until complete here, when reach implemented
    Xdist = attacker.x - target.x
    Ydist = attacker.y - target.y
    if math.sqrt(Xdist**2 + Ydist**2) < melee_reach:
        return True
    else:
        return False

class DragonBreathAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
    ):
        super().__init__(entity)
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

    def perform(self) -> None:
        target = self.target_actor
        choice = ''
        damage = 0
        if not target:
            raise exceptions.Impossible("Nothing to attack.")
        breath_weapons = ['Cone Fire Breath']
        for breath in breath_weapons:
            if breath in self.entity.battler.spells:
                choice = breath # doesn't handle multiple breath weapon options
        if choice == '':
            raise exception.Impossible("You found no breath attack")
        else:
            if choice == 'Cone Fire Breath':
                num_dice = self.entity.battler.spells[choice][0]
                for i in range(num_dice):
                    damage = damage + randint(1, self.entity.battler.spells[choice][1])
                attack_desc = f"{self.entity.name.capitalize()} breathes fire on {target.name}"
                
            if self.entity is self.engine.player:
                attack_color = colors.player_atk
                self.engine.last_target = target
            else:
                attack_color = colors.enemy_atk
            if make_save(breath_dc(self.entity), target, "Reflex"):
                damage = int(damage/2)
                attack_desc += f" save made"
            else:
                attack_desc += f" save failed"
            if damage > 0:
                self.engine.message_log.add_message(
                    f"{attack_desc} for {damage} hit points.", attack_color
                    )
            else:
                self.engine.message_log.add_message(
                    f"{attack_desc} but does no damage.", attack_color
                    )
        target.battler.take_damage(damage)
        check_turn_advance(self.engine, self.entity)
        return None
            
def breath_dc(entity):
    save_needed = 10
    save_needed = (int(entity.battler.current_con/2) + int(entity.level.current_level/2))
    return save_needed

def make_save(target_dc, target, save_type: str = "Reflex"):
    roll = randint(1,20)
    if roll == 1:
        roll = -10 # 1 auto-fail is just very bad roll now.
    if save_type == "Reflex":
        save_bonus = target.battler.reflex_save
    elif save_type == "Fortitude":
        save_bonus = target.battler.fort_save
    elif save_type == "Will":
        save_bonus = target.battler.will_save
    else:
        raise exceptions.Impossible("Save is not Fort, Reflex, or Will.  Undefined.")
        return True
    if (save_bonus + roll) >= target_dc or roll == 20: # natural 20 always saves
        return True
    else:
        return False

class SummonMonsterAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
        chosen_spell: str = "",
        mana_cost: int = 0,
    ):
        super().__init__(entity)
        self.target_xy = target_xy
        self.chosen_spell = chosen_spell
        self.mana_cost = mana_cost

    def perform(self) -> None:
        cost = self.mana_cost
        if cost > self.entity.battler.mana:
            raise exceptions.Impossible("You do not have enough mana for that.")
        if self.chosen_spell in ("Summon Monster 1", "Summon Monster 2", "Summon Monster 3"):
            Entity.spawn_summon(entity_factories.celestial_badger, self.engine.game_map,
                                self.target_xy[0], self.target_xy[1], self.entity.level.current_level)
        else:
            raise exceptions.Impossible(f"Summon spells not found: {chosen_spell}")
        self.entity.battler.use_mana(cost)
        check_turn_advance(self.engine, self.entity)
        return None

class CastMagicMissileAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
    ):
        super().__init__(entity)
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

    def perform(self) -> None:
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")
        cost = self.entity.battler.spells["Magic Missile"]
        if cost > self.entity.battler.mana:
            raise exceptions.Impossible("You do not have enough mana for that.")
        num_dice = int((self.entity.level.current_level + 1) / 2)
        num_dice = min(num_dice, 5)
        damage = 0
        for i in range(num_dice):
            damage = damage + randint(1, 4) + 1
        attack_desc = f"{self.entity.name.capitalize()} zaps {target.name}"
        if self.entity is self.engine.player:
            attack_color = colors.player_atk
            self.engine.last_target = target
        else:
            attack_color = colors.enemy_atk
        if damage > 0:
            self.engine.message_log.add_message(
                f"{attack_desc} for {damage} hit points.", attack_color
                )
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
                )
        target.battler.take_damage(damage)
        self.entity.battler.use_mana(cost)
        check_turn_advance(self.engine, self.entity)
        return None

class ItemAction(Action):
    def __init__(
        self,
        entity: Actor,
        item: Item,
        target_xy: Optional[Tuple[int, int]] = None
    ):
        super().__init__(entity)
        self.item = item
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        """Invoke the items ability, this action will be given to provide context."""
        check_turn_advance(self.engine, self.entity)
        if self.item.consumable:
            self.item.consumable.activate(self)

class DropItem(ItemAction):
    def perform(self) -> None:
        self.entity.inventory.drop(self.item)
        check_turn_advance(self.engine, self.entity)

class EquipItem(ItemAction):
    def perform(self) -> None:
        """Equip toggle Item"""
        if self.item.equippable:
            self.item.equippable.activate(self.engine.player)
        check_turn_advance(self.engine, self.entity)
        

class WaitAction(Action):
    def __init__(self, entity: Actor):
        super().__init__(entity)
    
    def perform(self) -> None:
        if self.entity.battler.mana < self.entity.battler.max_mana:
            self.entity.battler.mana += 1
        if self.entity.battler.hp < self.entity.battler.max_hp:
            self.entity.battler.hp += 1
        check_turn_advance(self.engine, self.entity)
        pass

class TakeStairsAction(Action):
    def perform(self) -> None:
        """
        Take the stairs, if any exist at the entity's location.
        """
        stairs_found = False
        for entity in self.engine.game_map.entities:
            if (entity.stairs and self.entity.x == entity.x and self.entity.y == entity.y):
                stairs_found = True
                found_stairs = entity
        if stairs_found == True:
            self.engine.last_level = self.engine.game_map.dungeon_level
            self.engine.game_world.generate_floor(found_stairs.stairs)
            self.engine.message_log.add_message(
                "You take the stairs.", colors.descend
            )
            check_turn_advance(self.engine, self.entity)
        else:
            raise exceptions.Impossible("There are no stairs here.")

class ActionWithDirection(Action):
    def __init__(self, entity: Actor, dx: int, dy: int, penalty: int = 0,
                 attack_list = []):
        super().__init__(entity)

        self.dx = dx
        self.dy = dy
        self.penalty = penalty
        self.attack_list = attack_list

    @property
    def dest_xy(self) -> Tuple[int, int]:
        """Returns this actions destination."""
        return self.entity.x + self.dx, self.entity.y + self.dy

    @property
    def blocking_entity(self) -> Optional[Entity]:
        """Return the blocking entity at this actions destination.."""
        return self.engine.game_map.get_blocking_entity_at_location(*self.dest_xy)

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.dest_xy)

    @property
    def target_shop(self) -> Optional[Shop]:
        """Return the shop at this actions destination."""
        return self.engine.game_map

    def perform(self) -> None:
        raise NotImplementedError()

class CastSelfBuffAction(Action):
    def __init__(
        self,
        entity: Actor,
        buff_spell: str = "",
        target_xy: Optional[Tuple[int, int]] = None
    ):
        super().__init__(entity)
        self.buff_spell = buff_spell
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy
        self.entity = entity

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        target = self.target_actor
        caster_level = self.entity.level.current_level
        if not target:
            raise exceptions.Impossible("Nothing to buff.")
        
        if self.buff_spell == "":
            raise exceptions.Impossible("No buff spell found: error.")
        if self.buff_spell in ("Mage Armor", "Shield", "Magic Weapon", "Alter Self"):
            if self.entity.battler.spells[self.buff_spell] > self.entity.battler.mana:
                raise exceptions.Impossible("You don't have enough mana for that.")
            if self.entity.battler.spells[self.buff_spell] > self.entity.level.current_level:
                raise exceptions.Impossible("You are not high enough level to cast that.")
            if self.buff_spell in target.battler.current_buffs:
                self.engine.message_log.add_message(
                    f"{self.entity.name} refreshes {self.buff_spell}", colors.white
                )
            else:
                self.engine.message_log.add_message(
                    f"{self.entity.name} gains {self.buff_spell}", colors.white
                )
            if self.buff_spell == "Mage Armor":
                self.entity.battler.current_buffs["Mage Armor"] = self.engine.current_turn + caster_level * 10 * 60
            elif self.buff_spell in ("Shield", "Magic Weapon"):
                self.entity.battler.current_buffs[self.buff_spell] = self.engine.current_turn + caster_level * 10
            elif self.buff_spell in ("Alter Self"):
                self.entity.battler.current_buffs[self.buff_spell] = self.engine.current_turn + caster_level * 10 * 10
        else:
            raise exceptions.Impossible("That is not a buff spell: error.")

        self.entity.battler.use_mana(self.entity.battler.spells[self.buff_spell])
        check_turn_advance(self.engine, self.entity)
        return None

class CastSelfHealAction(Action):
    def __init__(
        self,
        entity: Actor,
        heal_spell: str = "",
        target_xy: Optional[Tuple[int, int]] = None
    ):
        super().__init__(entity)
        self.heal_spell = heal_spell
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy
        self.entity = entity

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        target = self.target_actor
        caster_level = self.entity.level.current_level
        dice = 1
        level_cap = 5
        healing = 0
        if not target:
            raise exceptions.Impossible("Target not found.")
        
        if self.heal_spell == "":
            raise exceptions.Impossible("No healing spell found: error.")
        if self.heal_spell in ("Cure Light Wounds", "Cure Moderate Wounds", "Cure Serious Wounds", "Cure Critical Wounds"):
            if self.entity.battler.spells[self.heal_spell] > self.entity.battler.mana:
                raise exceptions.Impossible("You don't have enough mana for that.")
            if self.entity.battler.spells[self.heal_spell] > self.entity.level.current_level:
                raise exceptions.Impossible("You are not high enough level to cast that.")
            if self.entity.battler.hp >= self.entity.battler.max_hp:
                raise exceptions.Impossible("You do not need healing.")
            if self.heal_spell == "Cure Light Wounds":
                dice = 1
                level_cap = 5
            elif self.heal_spell == "Cure Moderate Wounds":
                dice = 2
                level_cap = 10
            elif self.heal_spell == "Cure Serious Wounds":
                dice = 3
                level_cap = 15
            elif self.heal_spell == "Cure Critical Wounds":
                dice = 4
                level_cap = 20
            for all_dice in range(dice):
                healing += randint(1,8)
            healing += max(caster_level, level_cap)
            healing = min(healing, (self.entity.battler.max_hp - self.entity.battler.hp))
            self.entity.battler.heal(healing)
        else:
            raise exceptions.Impossible("That is not a heal spell: error.")
        actual_heal = max(healing, self.entity.battler.max_hp - self.entity.battler.hp)
        self.engine.message_log.add_message(
            f"{self.entity.name} heals {healing} hps.", colors.white
        )
        self.entity.battler.use_mana(self.entity.battler.spells[self.heal_spell])
        check_turn_advance(self.engine, self.entity)
        return None

class CastShockingGraspAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
    ):
        super().__init__(entity)
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

    def perform(self) -> None:
        maximum_range = 1.43
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack")
        distance = self.entity.distance(target.x, target.y)
        if distance > maximum_range:
            raise exceptions.Impossible("That target is too far (Melee only)")

        damage = 0

        cost = self.entity.battler.spells["Shocking Grasp"]
        if cost > self.entity.battler.mana:
            raise exceptions.Impossible("You do not have enough mana for that.")
        num_dice = self.entity.level.current_level
        num_dice = min(num_dice, 5)
        for i in range(num_dice):
            damage = damage + randint(1, 6)
        attack_desc = f"{self.entity.name.capitalize()} shocks {target.name}"
        if self.entity is self.engine.player:
            attack_color = colors.player_atk
            self.engine.last_target = target
        else:
            attack_color = colors.enemy_atk


        """
        if (self.entity.battler.melee_to_hit + randint(1, 20) - self.penalty) >= target.battler.current_touch_ac:
            if damage > 0:
                self.engine.message_log.add_message(
                    f"{attack_desc} for {damage} hit points.", attack_color
                )
                target.battler.take_damage(damage)
            else:
                self.engine.message_log.add_message(
                    f"{attack_desc} but does no damage.", attack_color
                )
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} and misses.", attack_color
            )
        """
        (damage, attack_desc) = HandleAttack(self.entity.battler.melee_to_hit, target.battler.current_touch_ac, damage, attack_desc, 20, 2)
        self.engine.message_log.add_message(attack_desc, attack_color)
        target.battler.take_damage(damage)
        self.entity.battler.use_mana(cost)

        check_turn_advance(self.engine, self.entity)
        return None

class CastRayOfEnfeeblementAction(Action):
    def __init__(
        self,
        entity: Actor,
        target_xy: Tuple[int, int] = (0, 0),
    ):
        super().__init__(entity)
        self.target_xy = target_xy

    @property
    def target_actor(self) -> Optional[Actor]:
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

    def perform(self) -> None:
        maximum_range = 5 + self.entity.level.current_level / 2
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack")
        distance = self.entity.distance(target.x, target.y)
        if distance > maximum_range:
            raise exceptions.Impossible("That target is too far: " + str(int(maximum_range)) + " squares.")

        str_damage = 0

        cost = self.entity.battler.spells["Ray of Enfeeblement"]
        if cost > self.entity.battler.mana:
            raise exceptions.Impossible("You do not have enough mana for that.")
        str_damage = randint(1, 6) + min(5, self.entity.level.current_level)
        attack_desc = f"{self.entity.name.capitalize()} shoots a grey beam at {target.name}"
        if self.entity is self.engine.player:
            attack_color = colors.player_atk
            self.engine.last_target = target
        else:
            attack_color = colors.enemy_atk
        if (self.entity.battler.ranged_to_hit + randint(1, 20) - self.penalty) >= target.battler.current_touch_ac:
            if str_damage > 0:
                self.engine.message_log.add_message(
                    f"{attack_desc} lowering str by {str_damage}.", attack_color
                )
                target.battler.current_buffs["Ray of Enfeeblement"] = [self.engine.current_turn + 10 * self.entity.level.current_level, str_damage]
            else:
                self.engine.message_log.add_message(
                    f"{attack_desc} but does no damage.", attack_color
                )
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} and misses.", attack_color
            )
        self.entity.battler.use_mana(cost)

        check_turn_advance(self.engine, self.entity)
        return None

class MeleeAction(ActionWithDirection):

    def perform(self) -> None:
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        damage = 0
        dam_string = "punches"
        crit_needs = 20
        crit_mult = 2

        if self.entity.equipment.main_hand == None:
            if len(self.attack_list) == 0:
                num_damage_dice = self.entity.battler.unarmed_num_dice
                for i in range(num_damage_dice):
                    damage = damage + randint(1, self.entity.battler.unarmed_size_dice)
            else: 
                for i in range(self.attack_list[2]):
                    damage = damage + randint(1, self.attack_list[3])
        else:
            num_damage_dice = self.entity.equipment.main_hand.equippable.weapon_num_dice
            size_damage_dice = self.entity.equipment.main_hand.equippable.weapon_size_dice
            num_damage_dice, size_damage_dice = get_size_damage_diff(num_damage_dice, size_damage_dice, self.entity)
            crit_needs = self.entity.equipment.main_hand.equippable.crit_needs
            crit_mult = self.entity.equipment.main_hand.equippable.crit_mult
            for i in range(num_damage_dice):
                damage = damage + randint(1, size_damage_dice)
            dam_string = self.entity.equipment.main_hand.equippable.damage_name

        if len(self.attack_list) == 0:
            damage = damage + self.entity.battler.melee_to_damage
        else:
            dam_string = self.attack_list[1]
            if self.attack_list[0] == 'P':
                damage = damage + self.entity.battler.melee_to_damage
            elif self.attack_list[0] == '2H':
                damage = damage + int(1.5 * self.entity.battler.melee_to_damage) #This could fail in edge cases, like weapon specialization.  Work for str and power attack though
            else: #should be 'S'
                damage = damage + int(self.entity.battler.melee_to_damage / 2)
                
        attack_desc = f"{self.entity.name.capitalize()} {dam_string} {target.name}"
        if self.entity is self.engine.player:
            attack_color = colors.player_atk
        else:
            attack_color = colors.enemy_atk

        (damage, attack_desc) = HandleAttack(self.entity.battler.melee_to_hit, target.battler.current_ac, damage, attack_desc, crit_needs, crit_mult)
        self.engine.message_log.add_message(attack_desc, attack_color)
        target.battler.hp -= damage


def HandleAttack(attack_to_hit, target_ac, damage, attack_desc, crit_needs = 20, crit_mult = 2):
    first_roll = randint(1, 20)
    if first_roll == 20:
        first_roll = 30
    if damage < 1: damage = 1 #penalties don't reduce damage below 1.  DR can, though
    if first_roll >= crit_needs and attack_to_hit + first_roll >= target_ac: #critical threat
        if randint(1, 20) + attack_to_hit >= target_ac: #confirmed crit  20 does not guarantee this time
            damage = damage * crit_mult
            attack_desc += f" *Crit* for {damage} hit points."
        else:
            attack_desc += f" for {damage} hit points."
    elif first_roll + attack_to_hit >= target_ac:
        attack_desc += f" for {damage} hit points."
    else:
        attack_desc += f" and misses."
        damage = 0
    return (damage, attack_desc)

class FullAttackMeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.target_actor
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        if self.entity.battler.combat_mode == "Ranged":
            if self.entity.equipment.main_hand == None:
                self.entity.battler.combat_mode = "Melee"
                self.engine.message_log.add_message(f"{self.entity.name} enters melee mode.")
            elif "Quick Draw" in self.entity.battler.combat_feats:
                self.entity.battler.combat_mode = "Melee"
                self.engine.message_log.add_message(f"{self.entity.name} quickly shifts to melee mode.")
            elif self.entity.equipment.main_hand !=None:
                self.entity.battler.combat_mode = "Melee"
                self.engine.message_log.add_message(f"{self.entity.name} clumsily grabs its melee weapon.")
                check_turn_advance(self.engine, self.entity)
                return MeleeAction(self.entity, self.dx, self.dy).perform()
            else:
                raise exceptions.Impossible("This shouldn't be possible.")

        if self.entity.equipment.main_hand != None:
            if self.entity.battler.bab < 6: #BAB can be 0, still 1 attack
                check_turn_advance(self.engine, self.entity)
                return MeleeAction(self.entity, self.dx, self.dy).perform()
            else:
                iterative_penalty = 0
                bab_counter = self.entity.battler.bab #Doesn't handle BAB>20, but can't happen currently
                while bab_counter > 0:
                    if target.battler.is_dead == True:
                        target = FindNewTarget(self.engine, target, ranged = False)
                        if target == None:
                            check_turn_advance(self.engine, self.entity)
                            return None
                        self.engine.message_log.add_message(f"{self.entity.name} retargets to {target.name}.", colors.player_atk)
                        self.dx = target.x - self.entity.x
                        self.dy = target.y - self.entity.y
                    MeleeAction(self.entity, self.dx, self.dy, iterative_penalty).perform()
                    bab_counter -= 5
                    iterative_penalty += 5
                check_turn_advance(self.engine, self.entity)
                return None

        elif len(self.entity.battler.full_attack) == 0: #No weapons, no full attack
            check_turn_advance(self.engine, self.entity)
            return MeleeAction(self.entity, self.dx, self.dy).perform()

        else:
            for i in range(len(self.entity.battler.full_attack)):
                if target.battler.is_dead == True:
                    target = FindNewTarget(self.engine, target, ranged = False)
                    if target == None:
                        check_turn_advance(self.engine, self.entity)
                        return None
                    self.engine.message_log.add_message(f"{self.entity.name} retargets to {target.name}.", colors.player_atk)
                    self.dx = target.x - self.entity.x
                    self.dy = target.y - self.entity.y
                if self.entity.battler.full_attack[i][0] == 'P': #Primary attack
                    MeleeAction(self.entity, self.dx, self.dy, 0, self.entity.battler.full_attack[i]).perform()
                elif self.entity.battler.full_attack[i][0] == 'S': #Secondary attack
                    MeleeAction(self.entity, self.dx, self.dy, 5, self.entity.battler.full_attack[i]).perform()
                elif self.entity.battler.full_attack[i][0] == '2H': #"Two-hand": hard hitting single attack (crocodile bite)
                    MeleeAction(self.entity, self.dx, self.dy, 0, self.entity.battler.full_attack[i]).perform()
            check_turn_advance(self.engine, self.entity)
            return None

class MovementAction(ActionWithDirection):
    def perform(self) -> None:
        dest_x, dest_y = self.dest_xy

        if not self.engine.game_map.in_bounds(dest_x, dest_y):
            # Destination is out of bounds.
            raise exceptions.Impossible("That way is blocked.")
        if not self.engine.game_map.tiles["walkable"][dest_x, dest_y]:
            # Destination is blocked by a tile.
            raise exceptions.Impossible("That way is blocked.")
        if self.engine.game_map.get_blocking_entity_at_location(dest_x, dest_y):
            # Destination is blocked by a tile.
            raise exceptions.Impossible("That way is blocked.")

        for gold in self.engine.game_map.gold_piles:
            if dest_x == gold.x and dest_y == gold.y:
                self.engine.message_log.add_message(f"{self.entity.name} picks up {gold.number} gold pieces.")
                self.entity.battler.gold += gold.number
                self.engine.game_map.entities.remove(gold)
                self.entity.move(self.dx, self.dy)
                return

        if self.entity == self.engine.player:
            log_items = True
            ground_message = ""
            for item_maybe in self.engine.game_map.entities:
                if dest_x == item_maybe.x and dest_y == item_maybe.y:
                    if item_maybe.blocks_movement == True:
                        log_items = False
                    else:
                        ground_message = ground_message + f"{item_maybe.name} is here.\n"
            if log_items == True and len(ground_message) > 0:
                self.engine.message_log.add_message(ground_message)

        check_turn_advance(self.engine, self.entity)
        self.entity.move(self.dx, self.dy)
        

class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        if self.target_actor:
            return FullAttackMeleeAction(self.entity, self.dx, self.dy).perform()
        else:
            return MovementAction(self.entity, self.dx, self.dy).perform()

class FastMoveAction(ActionWithDirection):
    def perform(self) -> None:
        dest_x, dest_y = self.dest_xy
        movecheck = False
        max_moves = 1
        while movecheck == False and max_moves < 100:
            for enemy in self.engine.game_map.actors:
                if enemy == self.engine.player:
                    continue
                if self.engine.game_map.visible[enemy.x][enemy.y] == True:
                    movecheck = True
            destin_x = self.engine.player.x + self.dx
            destin_y = self.engine.player.y + self.dy
            if not self.engine.game_map.in_bounds(destin_x, destin_y):
                # Destination is out of bounds.
                raise exceptions.Impossible("That way is blocked. (out of map)")
                break
            if not self.engine.game_map.tiles["walkable"][destin_x, destin_y]:
                # Destination is blocked by a tile.
                break
                raise exceptions.Impossible("That way is blocked. (tile)")
            if self.engine.game_map.get_blocking_entity_at_location(destin_x, destin_y):
                # Destination is blocked by a blocking entity.
                raise exceptions.Impossible("That way is blocked. (entity)")
                break

            if self.entity == self.engine.player:
                log_items = True
                ground_message = ""
                for item_maybe in self.engine.game_map.entities:
                    if destin_x == item_maybe.x and destin_y == item_maybe.y:
                        if item_maybe.blocks_movement == True:
                            log_items = False
                        else:
                            ground_message = ground_message + f"{item_maybe.name} is here.\n"
                if log_items == True and len(ground_message) > 0:
                    self.engine.message_log.add_message(ground_message)

            if movecheck == True:
                raise exceptions.Impossible("Enemy spotted.")
                break
            else:
                check_turn_advance(self.engine, self.entity)
                self.entity.move(self.dx, self.dy)
                max_moves += 1
                self.engine.update_fov()
