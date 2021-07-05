from random import randint
import entity_factories

def get_inv(choice):
    if choice == "Potion of Cure Light Wounds":
        return entity_factories.cure_light_wounds_potion
    elif choice == 'Potion of Cure Moderate Wounds':
        return entity_factories.cure_moderate_wounds_potion
    elif choice == 'Potion of Cure Serious Wounds':
        return entity_factories.cure_serious_wounds_potion
    elif choice == 'Potion of Cure Critical Wounds':
        return entity_factories.cure_critical_wounds_potion
    elif choice == 'Masterwork Breastplate':
        return entity_factories.breastplate_masterwork
    elif choice == 'Masterwork Composite Long Bow':
        return entity_factories.composite_long_bow_masterwork
    elif choice == '+1 Composite Long Bow':
        return entity_factories.composite_long_bow_plus_one
    elif choice == '+1 Full Plate':
        return entity_factories.full_plate_plus_one
    elif choice == 'Ring of Protection + 1':
        return entity_factories.ring_of_prot_plus_one
    else:
        print("Item choice not found: " + choice)
        return entity_factories.cure_light_wounds_potion

def from_dungeon_level(table, dungeon_level):
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value

    return 0

def random_choice_index(chances):
    random_chance = randint(1, sum(chances))

    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        if random_chance <= running_sum:
            return choice
        choice += 1

def random_choice_from_dict(choice_dict):
    choices = list(choice_dict.keys())
    chances = list(choice_dict.values())

    return choices[random_choice_index(chances)]

def random_monster_choice(dungeon_level):
    monster_chances = {
        'orc': from_dungeon_level([[20, 1], [40, 3], [50, 5]], dungeon_level),
        'goblin': 40,
        'boar': from_dungeon_level([[10, 2], [30, 4]], dungeon_level),
        'troll': from_dungeon_level([[15, 4], [30, 6], [60, 8]], dungeon_level),
        'bison': from_dungeon_level([[10, 2], [30, 4]], dungeon_level),
        'camel': from_dungeon_level([[15, 1], [30, 3]], dungeon_level),
        'crocodile': from_dungeon_level([[10, 2], [30, 4]], dungeon_level),
        'hawk': 15,
        'hyena': from_dungeon_level([[15, 1], [30, 3]], dungeon_level),
        'snake': from_dungeon_level([[5, 1], [15, 2], [25, 4]], dungeon_level),
        'wolf': from_dungeon_level([[10, 1], [20, 2]], dungeon_level),
        'ogre': from_dungeon_level([[10, 2], [20, 3], [30, 4]], dungeon_level),
        'human skeleton': from_dungeon_level([[20, 1], [10, 3], [5, 5]], dungeon_level),
        'hill giant': from_dungeon_level([[10, 4], [20, 6], [30, 7], [40, 8]], dungeon_level),
        'frost giant': from_dungeon_level([[10, 6], [20, 8], [30, 9], [40, 10]], dungeon_level),
        'fire giant': from_dungeon_level([[10, 7], [20, 9], [30, 10], [40, 11]], dungeon_level),
        'ettin': from_dungeon_level([[10, 4], [20, 6], [30, 7], [40, 8]], dungeon_level),
        'manticore': from_dungeon_level([[10, 3], [20, 5], [30, 6]], dungeon_level),
        'young red dragon': from_dungeon_level([[5, 4], [20, 6], [100, 8]], dungeon_level),
    }
    choices = list(monster_chances.keys())
    chances = list(monster_chances.values())

    return choices[random_choice_index(chances)]

def loot_from_cr(table, monster_cr):
    for (value, table_cr) in reversed(table):
        if monster_cr >= table_cr:
            return value

    return 0

def random_choice_from_cr(cr):
    inventory_results = {
        'Potion of Cure Light Wounds': loot_from_cr([[100, 0], [60, 2], [30, 4], [10, 6]], cr),
        'Potion of Cure Moderate Wounds': loot_from_cr([[5, 0], [10, 1], [20, 2], [30, 4]], cr),
        'Potion of Cure Serious Wounds': loot_from_cr([[3, 1], [5, 2], [20, 4], [30, 6]], cr),
        'Potion of Cure Critical Wounds': loot_from_cr([[2, 2], [10, 4], [20, 6], [30, 8]], cr),
        'Masterwork Breastplate': loot_from_cr([[1, 0], [3, 2]], cr),
        'Masterwork Composite Long Bow': loot_from_cr([[1, 0], [3, 2], [5, 4]], cr),
        '+1 Composite Long Bow': loot_from_cr([[1, 2], [3, 4], [4, 6]], cr),
        '+1 Full Plate': loot_from_cr([[1, 2], [2, 4], [3, 6]], cr),
        'Ring of Protection + 1': loot_from_cr([[1, 2], [4, 4]], cr),
    }
    choices = list(inventory_results.keys())
    chances = list(inventory_results.values())

    return choices[random_choice_index(chances)]

