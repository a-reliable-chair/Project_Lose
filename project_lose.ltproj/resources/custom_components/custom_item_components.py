from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.item_components import ItemComponent, ItemTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random
from app.engine.movement import movement_funcs

class DoNothing(ItemComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class DrawBackOnEndCombatInitiate(ItemComponent):
    nid = 'draw_back_on_end_combat_initiate'
    desc = "Item moves both user and target back at the end of combat, only on initiation"
    tag = ItemTags.CUSTOM

    expose = ComponentType.Int
    value = 1

    def _check_draw_back(self, target, user, magnitude):
        offset_x = utils.clamp(target.position[0] - user.position[0], -1, 1)
        offset_y = utils.clamp(target.position[1] - user.position[1], -1, 1)
        new_position_user = (user.position[0] - offset_x * magnitude,
                             user.position[1] - offset_y * magnitude)
        new_position_target = (target.position[0] - offset_x * magnitude,
                               target.position[1] - offset_y * magnitude)

        mcost_user = movement_funcs.get_mcost(user, new_position_user)
        mcost_target = movement_funcs.get_mcost(target, new_position_target)
        #If we could pass through it if we had movement, allow the action to occur
        if mcost_user != 99:
            mcost_user = 0
        if mcost_target != 99:
            mcost_target = 0
        if game.board.check_bounds(new_position_user) and \
                not game.board.get_unit(new_position_user) and \
                mcost_user <= equations.parser.movement(user) and mcost_target <= equations.parser.movement(target):
            return new_position_user, new_position_target
        return None, None
    
    def end_combat(self, playback, unit, item, target, mode):
        if not skill_system.ignore_forced_movement(unit) and not skill_system.ignore_forced_movement(target) and mode and mode == 'attack':
            new_position_user, new_position_target = self._check_draw_back(target, unit, self.value)
            if new_position_user and new_position_target:
                action.do(action.Teleport(unit, new_position_user))
                action.do(action.Teleport(target, new_position_target))