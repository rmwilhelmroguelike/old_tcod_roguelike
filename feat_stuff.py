from __future__ import annotations

from typing import List, TYPE_CHECKING

def get_all_feats():
    
    taken_once_feats = {
        "Toughness": {},
        "Power Attack": {},
        "Weapon Finesse": {},
        "Quick Draw": {},
        "Weapon Focus (Dwarven Waraxe)": {},
        "Weapon Specialization (Dwarven Waraxe)": {"Feats": ["Weapon Focus (Dwarven Waraxe)"], "Fighter Level": 4},
        "Greater Weapon Focus (Dwarven Waraxe)": {"Feats": ["Weapon Focus (Dwarven Waraxe)"], "Fighter Level": 8},
        "Greater Weapon Specialization (Dwarven Waraxe)": {"Feats": ["Weapon Focus (Dwarven Waraxe)", "Greater Weapon Focus (Dwarven Waraxe)", "Weapon Specialization (Dwarven Waraxe)"], "Fighter Level": 12},
        "Improved Critical (Dwarven Waraxe)": {"BAB": 8},
        "Cleave": {"Feats": ["Power Attack"]},
        "Great Cleave": {"Feats": ["Power Attack", "Cleave"]},
        "Point Blank Shot": {},
        "Rapid Shot": {"Feats": ["Point Blank Shot"]},
        "Deadly Aim": {},
        "Weapon Focus (Composite Long Bow)": {},
        "Weapon Specialization (Composite Long Bow)": {"Feats": ["Weapon Focus (Composite Long Bow)"], "Fighter Level": 4},
        "Greater Weapon Focus (Composite Long Bow)": {"Feats": ["Weapon Focus (Composite Long Bow)"], "Fighter Level": 8},
        "Greater Weapon Specialization (Composite Long Bow)": {"Feats": ["Weapon Focus (Composite Long Bow)", "Greater Weapon Focus (Composite Long Bow)", "Weapon Specialization (Composite Long Bow)"], "Fighter Level": 12},
        "Improved Critical (Composite Long Bow)": {"BAB": 8},
        "Weapon Focus (Greatsword)": {},
        "Weapon Specialization (Greatsword)": {"Feats": ["Weapon Focus (Greatsword)"], "Fighter Level": 4},
        "Greater Weapon Focus (Greatsword)": {"Feats": ["Weapon Focus (Greatsword)"], "Fighter Level": 8},
        "Greater Weapon Specialization (Greatsword)": {"Feats": ["Weapon Focus (Greatsword)", "Greater Weapon Focus (Greatsword)", "Weapon Specialization (Greatsword)"], "Fighter Level": 12},
        "Improved Critical (Greatsword)": {"BAB": 8},
    }

    taken_multiple_feats = {
        "Extra Turning": {},
    }

    return taken_once_feats, taken_multiple_feats

def get_feat_reqs(pc, feat: {}):

    if len(feat) == 0:
        return True

    if "Feats" in feat:
        for i in range(len(feat["Feats"])):
            if feat["Feats"][i] not in pc.battler.combat_feats:
                return False

    if "BAB" in feat:
        if pc.battler.bab < feat["BAB"]:
            return False

    if "Fighter Level" in feat:
        if pc.battler.bab < feat["Fighter Level"]:
            return False

    return True
