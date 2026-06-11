"""游戏状态机：战役流程 + 战斗回合调度。

流程: TITLE → INTRO → 战斗(IDLE/MOVE/MENU/TARGET/FORECAST/COMBAT/LEVELUP/ENEMY_TURN)
      → CLEAR → 下一章 INTRO … → COMPLETE；败北 → END(R 重试本章)
"""
import copy
import math

import pygame

import assets
import combat
import sfx
import ui
from ai import plan_action
from grid import Grid, manhattan, move_range
from settings import CELL, CHAPTERS, GRID_H, GRID_W, PLAYER_ROSTER, POTION_USES
from unit import Unit

EVENT_DUR = 0.55      # 每次攻击动作时长(秒)
SLIDE_DUR = 0.25      # 移动滑行
BANNER_DUR = 1.4
LEVELUP_DUR = 2.2
ENEMY_PAUSE = 0.35
FLOAT_DUR = 0.9


class Game:
    def __init__(self):
        self.full_reset()

    # ---------- 战役流程 ----------

    def full_reset(self):
        """回到标题画面，重建战役。"""
        self.chapter_idx = 0
        self.roster = [Unit(s['name'], s['cls'], 'player', (0, 0)) for s in PLAYER_ROSTER]
        self.snapshot = None
        self.units = []
        self.grid = Grid(CHAPTERS[0]['map'])
        self.turn = 1
        self.time = 0.0
        self._clear_battle_state()
        self.state = 'TITLE'

    def _clear_battle_state(self):
        self.hover = None
        self.selected = None
        self.move_tiles = {}
        self.fringe = set()
        self.orig_pos = None
        self.menu_items, self.menu_rects, self.menu_sel = [], [], 0
        self.targets, self.target, self.fc = [], None, None
        self.threat, self.threat_unit = set(), None
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

    @property
    def chapter(self):
        return CHAPTERS[self.chapter_idx]

    @property
    def lord(self):
        return self.roster[0]

    def begin_intro(self):
        self.state = 'INTRO'

    def setup_chapter(self, retry=False):
        """布阵：建队伍与敌人、放置单位、拍快照。不开战（对话可先在战场上播放）。"""
        ch = self.chapter
        if retry and self.snapshot is not None:
            self.roster = copy.deepcopy(self.snapshot)
        elif not retry:
            for j in ch['join']:
                # 幂等：读档进来的 roster 可能已含本章同伴
                if all(u.name != j['name'] for u in self.roster):
                    self.roster.append(Unit(j['name'], j['cls'], 'player', j['pos']))
        positions = list(ch['players']) + [j['pos'] for j in ch['join']]
        for u, pos in zip(self.roster, positions):
            u.x, u.y = pos
            u.hp = u.max_hp            # 休闲模式: 每章开始全员复活满血
            u.acted = False
            u.potions = POTION_USES
        if not retry:
            self.snapshot = copy.deepcopy(self.roster)
        enemies = [Unit(e['name'], e['cls'], 'enemy', e['pos'],
                        boss=e.get('boss', False), ai=e.get('ai', 'aggro'))
                   for e in ch['enemies']]
        self.units = self.roster + enemies
        self.grid = Grid(ch['map'])
        self.turn = 1
        self._clear_battle_state()
        self.boss_quote_shown = False
        self.state = 'IDLE'

    def enter_battle(self):
        """开战：回合横幅 + 进入待机。"""
        self.show_banner(f'第 {self.turn} 回合  玩家行动', ui.COL_PLAYER)
        sfx.play('turn')
        self.state = 'IDLE'

    def start_chapter(self, retry=False):
        self.setup_chapter(retry)
        self.enter_battle()

    def chapter_clear(self):
        sfx.play('victory')
        self.state = 'CLEAR'

    def next_chapter(self):
        self.chapter_idx += 1
        if self.chapter_idx >= len(CHAPTERS):
            self.state = 'COMPLETE'
        else:
            self.begin_intro()

    # ---------- 回合调度 ----------

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
                amount = min(max(1, math.ceil(u.max_hp * t['heal'])), u.max_hp - u.hp)
                u.heal(amount)
                self.add_float(f'+{amount}', (u.x, u.y), (120, 230, 120))

    def start_player_phase(self):
        self.turn += 1
        for u in self.alive('player'):
            u.acted = False
        self.fortress_heal('player')
        self.show_banner(f'第 {self.turn} 回合  玩家行动', ui.COL_PLAYER)
        sfx.play('turn')
        self.state = 'IDLE'

    def start_enemy_phase(self):
        for u in self.alive('player'):
            u.acted = True
        self.clear_selection()
        self.fortress_heal('enemy')
        self.show_banner('敌方行动', ui.COL_ENEMY)
        sfx.play('turn')
        self.enemy_queue = list(self.alive('enemy'))
        self.enemy_sub = 'banner'
        self.state = 'ENEMY_TURN'

    def clear_selection(self):
        self.selected = None
        self.move_tiles, self.fringe = {}, set()
        self.targets, self.target, self.fc = [], None, None

    # ---------- 选择 / 范围 ----------

    def _range_tiles(self, unit, allow_move=True):
        """unit 的(移动∪攻击)范围。返回 (move_tiles, 攻击边缘)"""
        tiles = move_range(unit, self.grid, self.units) if allow_move else {(unit.x, unit.y): 0}
        lo, hi = unit.weapon_range
        fringe = set()
        for (mx, my) in tiles:
            for dx in range(-hi, hi + 1):
                for dy in range(-hi, hi + 1):
                    if lo <= abs(dx) + abs(dy) <= hi:
                        p = (mx + dx, my + dy)
                        if self.grid.in_bounds(*p) and p not in tiles:
                            fringe.add(p)
        return tiles, fringe

    def select(self, unit):
        sfx.play('select')
        self.threat, self.threat_unit = set(), None
        self.selected = unit
        self.orig_pos = (unit.x, unit.y)
        self.move_tiles, self.fringe = self._range_tiles(unit)
        self.state = 'MOVE'

    def toggle_threat(self, enemy):
        """待机时点击敌人 → 显示/关闭其威胁范围"""
        if self.threat_unit is enemy:
            self.threat, self.threat_unit = set(), None
            return
        sfx.play('select')
        tiles, fringe = self._range_tiles(enemy, allow_move=not enemy.boss)
        self.threat = set(tiles) | fringe
        self.threat_unit = enemy

    def targets_from(self, unit):
        lo, hi = unit.weapon_range
        return [u for u in self.alive('enemy')
                if lo <= manhattan((unit.x, unit.y), (u.x, u.y)) <= hi]

    def enter_menu(self):
        self.targets = self.targets_from(self.selected)
        u = self.selected
        self.menu_items = [('攻击', bool(self.targets)),
                           ('用药', u.potions > 0 and u.hp < u.max_hp),
                           ('待机', True)]
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
        # 被打的驻守敌人被激活
        for ev in self.combat_events:
            t = ev['target']
            if t.team == 'enemy' and t.alive and t.ai == 'guard':
                t.ai = 'aggro'
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
            sfx.play('levelup')
            self.state = 'LEVELUP'
        else:
            self.continue_after_combat()

    def _chapter_won(self):
        enemies = self.alive('enemy')
        if not enemies:
            return True
        if self.chapter['win'] == 'boss':
            return not any(u.boss for u in enemies)
        return False

    def continue_after_combat(self):
        if self._chapter_won():
            self.chapter_clear()
            return
        if not self.lord.alive or not self.alive('player'):
            sfx.play('defeat')
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

        click = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        key = event.key if event.type == pygame.KEYDOWN else None

        # --- 流程画面 ---
        if self.state == 'TITLE':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('confirm')
                self.begin_intro()
            return
        if self.state == 'INTRO':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('confirm')
                self.start_chapter()
            return
        if self.state == 'CLEAR':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('confirm')
                self.next_chapter()
            return
        if self.state == 'COMPLETE':
            if key == pygame.K_r:
                self.full_reset()
            return
        if self.state == 'END':
            if key == pygame.K_r:
                sfx.play('confirm')
                self.start_chapter(retry=True)
            return

        # --- 战斗动画进行中不接受操作 ---
        if self.slide or self.state in ('COMBAT', 'ENEMY_TURN'):
            return

        if self.state == 'LEVELUP':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.levelup_t < 1.0:
                    self.levelup_t = 1.0       # 先跳过动画
                else:
                    self.levelups.pop(0)
                    self.levelup_t = 0.0
                    if self.levelups:
                        sfx.play('levelup')
                    else:
                        self.continue_after_combat()
            return

        if event.type == pygame.KEYDOWN:
            if key == pygame.K_e and self.state == 'IDLE':
                self.start_enemy_phase()
            elif key == pygame.K_ESCAPE:
                self.cancel()
            elif key == pygame.K_RETURN and self.state == 'FORECAST':
                self.confirm_attack()
            return

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 3:
                self.cancel()
            elif event.button == 1:
                self.click(event.pos)

    def cancel(self):
        if self.state == 'MOVE':
            sfx.play('cancel')
            self.clear_selection()
            self.state = 'IDLE'
        elif self.state == 'MENU':
            sfx.play('cancel')
            self.selected.x, self.selected.y = self.orig_pos
            self.state = 'MOVE'
        elif self.state == 'TARGET':
            sfx.play('cancel')
            self.enter_menu()
        elif self.state == 'FORECAST':
            sfx.play('cancel')
            self.target, self.fc = None, None
            self.state = 'TARGET'
        elif self.state == 'IDLE' and self.threat_unit is not None:
            self.threat, self.threat_unit = set(), None

    def click(self, pos):
        mx, my = pos
        cell = (mx // CELL, my // CELL) if my < GRID_H * CELL else None

        if self.state == 'MENU':
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(pos) and self.menu_items[i][1]:
                    label = self.menu_items[i][0]
                    sfx.play('confirm')
                    if label == '攻击':
                        self.state = 'TARGET'
                    elif label == '用药':
                        healed = self.selected.use_potion()
                        self.add_float(f'+{healed}', (self.selected.x, self.selected.y),
                                       (120, 230, 120))
                        sfx.play('heal')
                        self.finish_unit()
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
            elif u and u.team == 'enemy':
                self.toggle_threat(u)
            else:
                self.threat, self.threat_unit = set(), None

        elif self.state == 'MOVE':
            u = self.unit_at(cell)
            if u and u.team == 'player' and not u.acted and u is not self.selected:
                self.select(u)                    # 切换选择
                return
            if cell in self.move_tiles:
                sfx.play('confirm')
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
                    sfx.play('select')
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
        sfx.play('confirm')
        self.start_combat(self.selected, self.target, 'player')

    # ---------- 更新 ----------

    def update(self, dt):
        self.time += dt
        if self.state in ('TITLE', 'INTRO', 'COMPLETE'):
            return
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
                sfx.play('miss')
                self.add_float('MISS', (target.x, target.y), (180, 180, 190))
            else:
                if ev['crit']:
                    sfx.play('crit')
                    self.add_float('必杀!', (ev['actor'].x, ev['actor'].y), ui.COL_GOLD)
                else:
                    sfx.play('hit')
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
        if self.state == 'COMBAT' and self.combat_idx < len(self.combat_events):
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
        if self.state == 'TITLE':
            ui.draw_title(surf, self.time)
            frame = int(self.time * 2.4)
            start_x = (720 - len(self.roster) * 84) // 2
            for i, u in enumerate(self.roster):
                surf.blit(assets.unit_sprite(u.cls, (frame + i) % 2), (start_x + i * 84, 290))
            return
        if self.state == 'INTRO':
            ui.draw_intro(surf, self.chapter_idx, self.chapter)
            return
        if self.state == 'COMPLETE':
            ui.draw_complete(surf, self.roster)
            return

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
        elif self.state == 'IDLE' and self.threat:
            ui.draw_tiles(surf, self.threat, ui.ATTACK_TILE)

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
                real_hp = u.hp
                u.hp = hp_override
                ui.draw_hp_bar(surf, u, px, py)
                u.hp = real_hp
            else:
                ui.draw_hp_bar(surf, u, px, py)
            if u.boss:
                ui.draw_boss_mark(surf, px, py)

        if self.selected and self.state in ('MOVE', 'MENU', 'TARGET', 'FORECAST'):
            ui.draw_cursor(surf, (self.selected.x, self.selected.y), ui.COL_GOLD)
        if self.threat_unit is not None and self.state == 'IDLE':
            ui.draw_cursor(surf, (self.threat_unit.x, self.threat_unit.y), ui.COL_ENEMY)
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
        ui.draw_objective(surf, self.turn, self.chapter['objective'])

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
        if self.state == 'CLEAR':
            ui.draw_clear(surf, self.chapter_idx, self.chapter['title'], self.turn)
        elif self.state == 'END':
            ui.draw_defeat(surf)
