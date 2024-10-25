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
    
    def end_combat(self, playback, unit, item, target, item2, mode):
        if not skill_system.ignore_forced_movement(unit) and not skill_system.ignore_forced_movement(target) and mode and mode == 'attack':
            new_position_user, new_position_target = self._check_draw_back(target, unit, self.value)
            if new_position_user and new_position_target:
                action.do(action.Teleport(unit, new_position_user))
                action.do(action.Teleport(target, new_position_target))

class BackdashOnEndCombat(ItemComponent):
    nid = 'backdash_on_end_combat'
    desc = 'Unit shoves *itself* backwards from the target point after combat.'
    tag = ItemTags.CUSTOM
    author = 'mag, Lord_Tweed'

    expose = ComponentType.Int
    value = 1

    def _check_dash(self, target, user, magnitude):
        tpos = target.position
        upos = user.position
        offset = utils.tmult(utils.tclamp(utils.tuple_sub(upos, tpos), (-1, -1), (1, 1)), magnitude)
        npos = utils.tuple_add(upos, offset)

        mcost_user = movement_funcs.get_mcost(user, npos)
        if game.board.check_bounds(npos) and not game.board.get_unit(npos) and \
                mcost_user <= equations.parser.movement(user):
            return npos
        return None

    def end_combat(self, playback, unit, item, target, item2, mode):
        if target and not skill_system.ignore_forced_movement(unit):
            new_position = self._check_dash(target, unit, self.value)
            if new_position:
                action.do(action.ForcedMovement(unit, new_position))

class EvalEnemyBlastAOE(ItemComponent):
    nid = 'eval_smartblast_aoe'
    desc = "Grants EVAL Enemy AoE range."
    tag = ItemTags.CUSTOM

    expose = ComponentType.String

    def _get_power(self, unit) -> int:
        from app.engine import evaluate
        try:
            base_power = int(evaluate.evaluate(self.value, unit))
        except Exception as e:
            logging.error("Couldn't evaluate %s conditional (%s)", self.value, e)
            base_power = 0
        empowered_splash = skill_system.empower_splash(unit)
        return base_power + 1 + empowered_splash

    def splash(self, unit, item, position) -> tuple:
        ranges = set(range(self._get_power(unit)))
        splash = game.target_system.find_manhattan_spheres(ranges, position[0], position[1])
        splash = {pos for pos in splash if game.board.check_bounds(pos)}
        from app.engine import item_system, skill_system
        if item_system.is_spell(unit, item):
            # spell blast
            splash = [game.board.get_unit(s) for s in splash]
            splash = [s.position for s in splash if s and skill_system.check_enemy(unit, s)]
            return None, splash
        else:
            # regular blast
            splash = [game.board.get_unit(s) for s in splash if s != position]
            splash = [s.position for s in splash if s and skill_system.check_enemy(unit, s)]
            return position if game.board.get_unit(position) else None, splash

    def splash_positions(self, unit, item, position) -> set:
        from app.engine import skill_system
        ranges = set(range(self._get_power(unit)))
        splash = game.target_system.find_manhattan_spheres(ranges, position[0], position[1])
        splash = {pos for pos in splash if game.tilemap.check_bounds(pos)}
        # Doesn't highlight allies positions
        splash = {pos for pos in splash if not game.board.get_unit(pos) or skill_system.check_enemy(unit, game.board.get_unit(pos))}
        return splash

class EvalAllyBlastAOE(ItemComponent):
    nid = 'eval_ally_smartblast_aoe'
    desc = "Grants EVAL Ally AoE range."
    tag = ItemTags.CUSTOM

    expose = ComponentType.String

    def _get_power(self, unit) -> int:
        from app.engine import evaluate
        try:
            base_power = int(evaluate.evaluate(self.value, unit))
        except Exception as e:
            logging.error("Couldn't evaluate %s conditional (%s)", self.value, e)
            base_power = 0
        empowered_splash = skill_system.empower_splash(unit)
        return base_power + 1 + empowered_splash

    def splash(self, unit, item, position) -> tuple:
        ranges = set(range(self._get_power(unit)))
        splash = game.target_system.find_manhattan_spheres(ranges, position[0], position[1])
        splash = {pos for pos in splash if game.board.check_bounds(pos)}
        from app.engine import item_system, skill_system
        if item_system.is_spell(unit, item):
            # spell blast
            splash = [game.board.get_unit(s) for s in splash]
            splash = [s.position for s in splash if s and skill_system.check_ally(unit, s)]
            return None, splash
        else:
            # regular blast
            splash = [game.board.get_unit(s) for s in splash if s != position]
            splash = [s.position for s in splash if s and skill_system.check_ally(unit, s)]
            return position if game.board.get_unit(position) else None, splash

    def splash_positions(self, unit, item, position) -> set:
        from app.engine import skill_system
        ranges = set(range(self._get_power(unit)))
        splash = game.target_system.find_manhattan_spheres(ranges, position[0], position[1])
        splash = {pos for pos in splash if game.tilemap.check_bounds(pos)}
        # Doesn't highlight allies positions
        splash = {pos for pos in splash if not game.board.get_unit(pos) or skill_system.check_ally(unit, game.board.get_unit(pos))}
        return splash