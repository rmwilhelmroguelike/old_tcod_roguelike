import entity_factories
import copy

def get_player(class_race: str = None):
    if class_race == None:
        player = copy.deepcopy(entity_factories.player)
        return player

    if class_race == 'Dwarf Fighter':
        player = copy.deepcopy(entity_factories.dwarf_fighter)

        player_armor = copy.deepcopy(entity_factories.breastplate)
        player_shield = copy.deepcopy(entity_factories.heavy_shield)
        player_weapon = copy.deepcopy(entity_factories.dwarven_waraxe)
        player_ranged = copy.deepcopy(entity_factories.composite_long_bow)

        player_armor.parent = player.inventory
        player_shield.parent = player.inventory
        player_weapon.parent = player.inventory
        player_ranged.parent = player.inventory

        player.inventory.items = [player_armor, player_shield, player_weapon, player_ranged]

        player.equipment.body = player_armor
        player.equipment.off_hand = player_shield
        player.equipment.main_hand = player_weapon
        player.equipment.ranged = player_ranged
        return player

    if class_race == 'Human Fighter':
        player = copy.deepcopy(entity_factories.human_fighter)

        player_armor = copy.deepcopy(entity_factories.breastplate)
        player_weapon = copy.deepcopy(entity_factories.greatsword)
        player_ranged = copy.deepcopy(entity_factories.composite_long_bow)

        player_armor.parent = player.inventory
        player_weapon.parent = player.inventory
        player_ranged.parent = player.inventory

        player.inventory.items = [player_armor, player_weapon, player_ranged]

        player.equipment.body = player_armor
        player.equipment.main_hand = player_weapon
        player.equipment.ranged = player_ranged
        return player

    if class_race == 'Human Cleric':
        player = copy.deepcopy(entity_factories.human_cleric)

        player_armor = copy.deepcopy(entity_factories.breastplate)
        player_shield = copy.deepcopy(entity_factories.heavy_shield)
        player_weapon = copy.deepcopy(entity_factories.morningstar)
        player_ranged = copy.deepcopy(entity_factories.javelin)

        player_armor.parent = player.inventory
        player_shield.parent = player.inventory
        player_weapon.parent = player.inventory
        player_ranged.parent = player.inventory

        player.inventory.items = [player_armor, player_shield, player_weapon, player_ranged]

        player.equipment.body = player_armor
        player.equipment.off_hand = player_shield
        player.equipment.main_hand = player_weapon
        player.equipment.ranged = player_ranged
        return player

    if class_race == 'Elf Wizard':
        player = copy.deepcopy(entity_factories.elf_wizard)

        player_armor = copy.deepcopy(entity_factories.spellthief_armor)
        player_weapon = copy.deepcopy(entity_factories.long_sword)
        player_ranged = copy.deepcopy(entity_factories.composite_long_bow)

        player_armor.parent = player.inventory
        player_weapon.parent = player.inventory
        player_ranged.parent = player.inventory

        player.inventory.items = [player_armor, player_weapon, player_ranged]

        player.equipment.body = player_armor
        player.equipment.main_hand = player_weapon
        player.equipment.ranged = player_ranged
        return player
