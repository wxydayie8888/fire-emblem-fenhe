"""游戏状态机与回合调度。

状态: IDLE→MOVE→MENU→TARGET→FORECAST→COMBAT→(LEVELUP)→IDLE/ENEMY_TURN→END
"""
import math

import pygame

import assets
import combat
import ui
from ai import plan_action
from grid import Grid, manhattan, move_range
from settings import CELL, ENEMY_UNITS, GRID_H, GRID_W, PLAYER_UNITS
from unit import Unit

EVENT_DUR = 0.55      # 每次攻击动作时长(秒)
SLIDE_DUR = 0.25      # 移动滑行
BANNER_DUR = 1.4
LEVELUP_DUR = 2.2
ENEMY_PAUSE = 0.35
FLOAT_DUR = 0.9


class Game:
    def __init__(self):
        self.reset()

    # ---------- 初始化 / 回合调度 ----------

    def reset(self):
        self.grid = Grid()
        self.units = [Unit(s['name'], s['cls'], 'player', s['pos'])
                      for s in PLAYER_UNITS]
        self.units += [Unit(s['name'], s['cls'], 'enemy', s['pos'], boss=s.get('boss', False))
                       for s in ENEMY_UNITS]
        self.lord = self.units[0]
        self.turn = 1
        self.state = 'IDLE'
        self.win = None
        self.hover = None
        self.selected = None
        self.move_tiles = {}
        self.fringe = set()
        self.orig_pos = None
        self.menu_items, self.menu_rects, self.menu_sel = [], [], 0
        self.targets, self.target, self.fc = [], None, None
        self.combat_events, self.combat_idx = [], 0
        self.event_t, self.event_spawned = 0.0, False
        self.hp_display = {}
        self.pending_exp = {}
        self.after_combat = 'player'
        self.levelups, self.levelup_t = [], 0.0
        self.enemy_queue, self.enemy_sub, self.pause_t = [], None, 0.0
        self.slide = None      # {'unit','fr','to','t','next'}
        self.floats = []       # {'text','x','y','t','color'}
        self.banner = None     # {'text','color','t'}
        self.time = 0.0
        self.start_player_phase(first=True)

    def alive(self, team=None):
        return [u for u in self.units if u.alive and (team is None or u.team == team)]

    def unit_at(self, pos):
        for u in self.units:
            if u.alive and (u.x, u.y) == pos:
                return u
        return None

    def show_banner(self, text, color):
        self.banner = {'text': text, 'color': color, 't': 0.0}

    def fortress_heal(self, team):
        for u in self.alive(team):
            t = self.grid.terrain(u.x, u.y)
            if t['heal'] and u.hp < u.max_hp:
                amount = max(1, math.ceil(u.max_hp * t['heal']))
                amount = min(amount, u.max_hp - u.hp)
                u.heal(amount)
                self.add_float(f'+{amount}', (u.x, u.y), (120, 230, 120))

    def start_player_phase(self, first=False):
        if not first:
            self.turn += 1
        for u in self.alive('player'):
            u.acted = False
        self.fortress_heal('player')
        self.show_banner(f'第 {self.turn} 回合  玩家行动', ui.COL_PLAYER)
        self.state = 'IDLE'

    def start_enemy_phase(self):
        for u in self.alive('player'):
            u.acted = True
        self.clear_selection()
        self.fortress_heal('enemy')
        self.show_banner('敌方行动', ui.COL_ENEMY)
        self.enemy_queue = list(self.alive('enemy'))
        self.enemy_sub = 'banner'
        self.state = 'ENEMY_TURN'

    def clear_selection(self):
        self.selected = None
        self.move_tiles, self.fringe = {}, set()
        self.targets, self.target, self.fc = [], None, None

    # ---------- 选择 / 范围 ----------

    def select(self, unit):
        self.selected = unit
        self.orig_pos = (unit.x, unit.y)
        self.move_tiles = move_range(unit, self.grid, self.units)
        lo, hi = unit.weapon_range
        fringe = set()
        for (mx, my) in self.move_tiles:
            for dx in range(-hi, hi + 1):
                for dy in range(-hi, hi + 1):
                    if lo <= abs(dx) + abs(dy) <= hi:
                        p = (mx + dx, my + dy)
                        if self.grid.in_bounds(*p) and p not in self.move_tiles:
                            fringe.add(p)
        self.fringe = fringe
        self.state = 'MOVE'

    def targets_from(self, unit):
        lo, hi = unit.weapon_range
        return [u for u in self.alive('enemy')
                if lo <= manhattan((unit.x, unit.y), (u.x, u.y)) <= hi]

    def enter_menu(self):
        self.targets = self.targets_from(self.selected)
        self.menu_items = [('攻击', bool(self.targets)), ('待机', True)]
        self.menu_sel = 0
        self.state = 'MENU'

    def finish_unit(self):
        self.selected.acted = True
        self.clear_selection()
        self.state = 'IDLE'
        if all(u.acted for u in self.alive('player')):
            self.start_enemy_phase()

    # ---------- 战斗 ----------

    def add_float(self, text, pos, color):
        self.floats.append({'text': text, 'x': pos[0], 'y': pos[1], 't': 0.0, 'color': color})

    def start_combat(self, att, dfd, after):
        dist = manhattan((att.x, att.y), (dfd.x, dfd.y))
        att_avoid = self.grid.terrain(att.x, att.y)['avoid']
        def_avoid = self.grid.terrain(dfd.x, dfd.y)['avoid']
        self.hp_display = {att: att.hp, dfd: dfd.hp}
        events, exp = combat.resolve(att, dfd, dist, att_avoid, def_avoid)
        self.combat_events = events
        self.combat_idx, self.event_t, self.event_spawned = 0, 0.0, False
        self.pending_exp = exp
        self.after_combat = after
        self.state = 'COMBAT'

    def combat_finished(self):
        for u in list(self.pending_exp):
            if not u.alive:
                continue
            amount = self.pending_exp[u]
            self.add_float(f'+{amount}EXP', (u.x, u.y), (160, 200, 255))
            for gains in u.gain_exp(amount):
                self.levelups.append((u, gains))
        self.pending_exp = {}
        self.hp_display = {}
        if self.levelups:
            self.levelup_t = 0.0
            self.state = 'LEVELUP'
        else:
            self.continue_after_combat()

    def continue_after_combat(self):
        if not self.alive('enemy'):
            self.win = True
            self.state = 'END'
            return
        if not self.lord.alive or not self.alive('player'):
            self.win = False
            self.state = 'END'
            return
        if self.after_combat == 'player':
            self.finish_unit()
        else:
            self.enemy_sub = 'pause'
            self.pause_t = ENEMY_PAUSE
            self.state = 'ENEMY_TURN'

    # ---------- 敌方回合 ----------

    def enemy_step(self):
        while self.enemy_queue:
            enemy = self.enemy_queue.pop(0)
            if not enemy.alive:
                continue
            action = plan_action(enemy, self.grid, self.units)
            if action['move'] != (enemy.x, enemy.y):
                self.slide = {'unit': enemy, 'fr': (enemy.x, enemy.y),
                              'to': action['move'], 't': 0.0,
                              'next': lambda e=enemy, a=action: self.enemy_acted(e, a)}
            else:
                self.enemy_acted(enemy, action)
            return
        self.start_player_phase()

    def enemy_acted(self, enemy, action):
        target = action['target']
        if target is not None and target.alive:
            self.start_combat(enemy, target, 'enemy')
        else:
            self.enemy_sub = 'pause'
            self.pause_t = ENEMY_PAUSE

    # ---------- 输入 ----------

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover = (mx // CELL, my // CELL) if my < GRID_H * CELL else None
            if self.state == 'MENU':
                for i, r in enumerate(self.menu_rects):
                    if r.collidepoint(event.pos):
                        self.menu_sel = i
            return

        if self.state == 'END':
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.reset()
            return

        # 动画进行中不接受操作（升级弹窗除外）
        if self.slide or self.state in ('COMBAT', 'ENEMY_TURN'):
            if self.state == 'COMBAT':
                return
            if self.state == 'ENEMY_TURN':
                return
            return

        if self.state == 'LEVELUP':
            if (event.type == pygame.MOUSEBUTTONDOWN
                    or (event.type == pygame.KEYDOWN
                        and event.key in (pygame.K_RETURN, pygame.K_SPACE))):
                if self.levelup_t < 1.0:
                    self.levelup_t = 1.0      # 先跳过动画
                else:
                    self.levelups.pop(0)
                    self.levelup_t = 0.0
                    if not self.levelups:
                        self.continue_after_combat()
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_e and self.state == 'IDLE':
                self.start_enemy_phase()
            elif event.key == pygame.K_ESCAPE:
                self.cancel()
            elif event.key == pygame.K_RETURN and self.state == 'FORECAST':
                self.confirm_attack()
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.cancel()
            elif event.button == 1:
                self.click(event.pos)

    def cancel(self):
        if self.state == 'MOVE':
            self.clear_selection()
            self.state = 'IDLE'
        elif self.state == 'MENU':
            self.selected.x, self.selected.y = self.orig_pos
            self.state = 'MOVE'
        elif self.state == 'TARGET':
            self.enter_menu()
        elif self.state == 'FORECAST':
            self.target, self.fc = None, None
            self.state = 'TARGET'

    def click(self, pos):
        mx, my = pos
        cell = (mx // CELL, my // CELL) if my < GRID_H * CELL else None

        if self.state == 'MENU':
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(pos) and self.menu_items[i][1]:
                    if self.menu_items[i][0] == '攻击':
                        self.state = 'TARGET'
                    else:
                        self.finish_unit()
                    return
            return

        if cell is None:
            return

        if self.state == 'IDLE':
            u = self.unit_at(cell)
            if u and u.team == 'player' and not u.acted:
                self.select(u)

        elif self.state == 'MOVE':
            u = self.unit_at(cell)
            if u and u.team == 'player' and not u.acted and u is not self.selected:
                self.select(u)                    # 切换选择
                return
            if cell in self.move_tiles:
                if cell == (self.selected.x, self.selected.y):
                    self.enter_menu()
                else:
                    self.slide = {'unit': self.selected, 'fr': self.orig_pos,
                                  'to': cell, 't': 0.0, 'next': self.enter_menu}
            else:
                self.clear_selection()
                self.state = 'IDLE'

        elif self.state == 'TARGET':
            for t in self.targets:
                if (t.x, t.y) == cell:
                    self.target = t
                    dist = manhattan((self.selected.x, self.selected.y), cell)
                    self.fc = combat.forecast(
                        self.selected, t, dist,
                        self.grid.terrain(self.selected.x, self.selected.y)['avoid'],
                        self.grid.terrain(t.x, t.y)['avoid'])
                    self.state = 'FORECAST'
                    return

        elif self.state == 'FORECAST':
            self.confirm_attack()

    def confirm_attack(self):
        self.start_combat(self.selected, self.target, 'player')

    # ---------- 更新 ----------

    def update(self, dt):
        self.time += dt
        for f in self.floats:
            f['t'] += dt / FLOAT_DUR
        self.floats = [f for f in self.floats if f['t'] < 1.0]
        if self.banner is not None:
            self.banner['t'] += dt / BANNER_DUR
            if self.banner['t'] >= 1.0:
                self.banner = None

        if self.slide is not None:
            self.slide['t'] += dt / SLIDE_DUR
            if self.slide['t'] >= 1.0:
                s = self.slide
                s['unit'].x, s['unit'].y = s['to']
                self.slide = None
                s['next']()
            return

        if self.state == 'COMBAT':
            self.update_combat(dt)
        elif self.state == 'LEVELUP':
            self.levelup_t = min(1.0, self.levelup_t + dt / LEVELUP_DUR)
        elif self.state == 'ENEMY_TURN':
            if self.enemy_sub == 'banner':
                if self.banner is None:
                    self.enemy_sub = 'next'
            elif self.enemy_sub == 'pause':
                self.pause_t -= dt
                if self.pause_t <= 0:
                    self.enemy_sub = 'next'
            elif self.enemy_sub == 'next':
                self.enemy_sub = None
                self.enemy_step()

    def update_combat(self, dt):
        if self.combat_idx >= len(self.combat_events):
            self.combat_finished()
            return
        ev = self.combat_events[self.combat_idx]
        self.event_t += dt / EVENT_DUR
        if self.event_t >= 0.45 and not self.event_spawned:
            self.event_spawned = True
            target = ev['target']
            if not ev['hit']:
                self.add_float('MISS', (target.x, target.y), (180, 180, 190))
            else:
                if ev['crit']:
                    self.add_float('必杀!', (ev['actor'].x, ev['actor'].y), ui.COL_GOLD)
                self.add_float(str(ev['dmg']), (target.x, target.y), (255, 240, 120))
                self.hp_display[target] = max(0, self.hp_display.get(target, target.hp) - ev['dmg'])
        if self.event_t >= 1.0:
            self.combat_idx += 1
            self.event_t, self.event_spawned = 0.0, False

    # ---------- 绘制 ----------

    def unit_draw_pos(self, u):
        px, py = u.x * CELL, u.y * CELL
        if self.slide and self.slide['unit'] is u:
            t = min(1.0, self.slide['t'])
            fx, fy = self.slide['fr']
            tx, ty = self.slide['to']
            px = (fx + (tx - fx) * t) * CELL
            py = (fy + (ty - fy) * t) * CELL
        if (self.state == 'COMBAT' and self.combat_idx < len(self.combat_events)):
            ev = self.combat_events[self.combat_idx]
            if ev['actor'] is u:
                lunge = math.sin(math.pi * min(1.0, self.event_t)) * 10
                dx = ev['target'].x - u.x
                dy = ev['target'].y - u.y
                d = max(1, abs(dx) + abs(dy))
                px += lunge * dx / d
                py += lunge * dy / d
        return px, py

    def draw(self, surf):
        water_frame = int(self.time * 1.6) % 2
        for y in range(GRID_H):
            for x in range(GRID_W):
                ch = self.grid.rows[y][x]
                variant = 1 if (ch == 'B' and x > 0 and self.grid.rows[y][x - 1] == 'B') else 0
                surf.blit(assets.terrain_sprite(ch, water_frame, variant), (x * CELL, y * CELL))

        if self.state == 'MOVE':
            ui.draw_tiles(surf, self.fringe, ui.ATTACK_TILE)
            ui.draw_tiles(surf, self.move_tiles, ui.MOVE_TILE)
        elif self.state in ('TARGET', 'FORECAST'):
            ui.draw_tiles(surf, [(t.x, t.y) for t in self.targets], ui.TARGET_TILE)

        unit_frame = int(self.time * 2.4)
        for u in self.units:
            if not u.alive:
                continue
            px, py = self.unit_draw_pos(u)
            ui.draw_team_ring(surf, u, px, py)
            sprite = assets.unit_sprite(u.cls, (unit_frame + (id(u) % 2)) % 2)
            if u.acted and u.team == 'player':
                sprite = sprite.copy()
                sprite.set_alpha(110)
            surf.blit(sprite, (px, py))
            hp_override = self.hp_display.get(u)
            if hp_override is not None:
                shown = u.hp
                u_hp = u.hp
                u.hp = hp_override
                ui.draw_hp_bar(surf, u, px, py)
                u.hp = u_hp
            else:
                ui.draw_hp_bar(surf, u, px, py)
            if u.boss:
                ui.draw_boss_mark(surf, px, py)

        if self.selected and self.state in ('MOVE', 'MENU', 'TARGET', 'FORECAST'):
            ui.draw_cursor(surf, (self.selected.x, self.selected.y), ui.COL_GOLD)
        if self.hover and self.state in ('IDLE', 'MOVE', 'TARGET'):
            ui.draw_cursor(surf, self.hover)

        for f in self.floats:
            ui.draw_float_text(surf, f['text'], f['x'] * CELL, f['y'] * CELL, f['t'], f['color'])

        hover_unit = self.unit_at(self.hover) if self.hover else None
        info_unit = hover_unit or (self.selected if self.state != 'IDLE' else None)
        terrain_ch = (self.grid.rows[self.hover[1]][self.hover[0]]
                      if self.hover and self.grid.in_bounds(*self.hover) else None)
        ui.draw_info(surf, info_unit, terrain_ch)
        ui.draw_help(surf)

        if self.state == 'MENU':
            px = (self.selected.x + 1) * CELL + 4
            py = self.selected.y * CELL
            self.menu_rects = ui.draw_menu(surf, self.menu_items, self.menu_sel, px, py)
        elif self.state == 'FORECAST':
            ui.draw_forecast(surf, self.fc, self.selected, self.target)
        elif self.state == 'LEVELUP' and self.levelups:
            u, gains = self.levelups[0]
            ui.draw_levelup(surf, u, gains, self.levelup_t)

        if self.banner is not None:
            ui.draw_banner(surf, self.banner['text'], self.banner['t'], self.banner['color'])
        if self.state == 'END':
            ui.draw_end(surf, self.win)
