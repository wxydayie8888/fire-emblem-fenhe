"""游戏状态机：战役流程 + 战斗回合调度。

流程: TITLE → INTRO → 战斗(IDLE/MOVE/MENU/TARGET/FORECAST/COMBAT/LEVELUP/ENEMY_TURN)
      → CLEAR → 下一章 INTRO … → COMPLETE；败北 → END(R 重试本章)
"""
import copy
import math

import pygame

import assets
import combat
import records
import save
import sfx
import story
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
        self.camp_turns = 0            # 本周目累计回合（战绩用）
        self.roster = [Unit(s['name'], s['cls'], 'player', (0, 0)) for s in PLAYER_ROSTER]
        self.snapshot = None
        self.units = []
        self.grid = Grid(CHAPTERS[0]['map'])
        self.turn = 1
        self.time = 0.0
        self._clear_battle_state()
        # 对话/旁白播放器（跨 battle-state 存活，不进 _clear_battle_state）
        self.dialogue_lines, self.dialogue_idx, self.after_dialogue = [], 0, None
        self.pages, self.page_idx, self.after_pages = [], 0, None
        self.boss_quote_shown = False
        self.save_data = save.load_game()      # None = 无可用存档
        self.records = records.load()          # 战绩记忆
        self.title_rects = []
        self.codex_sel, self.codex_rects = 0, []
        self.detail_unit, self.detail_return = None, 'IDLE'
        self.state = 'TITLE'

    def _clear_battle_state(self):
        self.hover = None
        self.selected = None
        self.move_tiles = {}
        self.fringe = set()
        self.orig_pos = None
        self.menu_items, self.menu_rects, self.menu_sel = [], [], 0
        self.targets, self.target, self.fc = [], None, None
        self.target_mode = 'attack'
        self.map_menu_pos = (0, 0)
        self.threat, self.threat_unit = set(), None
        self.threat_all = False        # D键：全敌威胁范围
        self.dying = []                # 死亡淡出动画 [{'unit','t'}]
        self.flash_t = 0.0             # 必杀白闪
        self.end_confirm_t = 0.0       # E键二次确认窗口
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

    def new_game(self):
        self.chapter_idx = 0
        self.start_pages(story.PROLOGUE, self.begin_intro)

    def continue_game(self):
        """从存档恢复：章节档进过场，战斗档直接回到战局。"""
        sd = self.save_data
        self.chapter_idx = sd['chapter_idx']
        self.camp_turns = sd.get('camp_turns', 0)
        if sd.get('kind') == 'battle':
            self.restore_battle(sd)
        else:
            self.roster = [Unit.from_dict(d) for d in sd['roster']]
            self.snapshot = copy.deepcopy(self.roster)
            self.begin_intro()

    def restore_battle(self, sd):
        """精确恢复挂起的战局。"""
        self.roster = [Unit.from_battle_dict(d) for d in sd['roster_meta']]
        self.snapshot = [Unit.from_dict(d) for d in sd['snapshot']]
        enemies = [Unit.from_battle_dict(d) for d in sd['enemies']]
        self.units = self.roster + enemies
        self.grid = Grid(self.chapter['map'])
        self._clear_battle_state()
        self.turn = sd['turn']
        self.boss_quote_shown = sd['boss_quote_shown']
        self.reinforce_used = set(sd['reinforce_used'])
        self.pending_reinforce = list(sd['pending_reinforce'])
        self.show_banner(f'第 {self.turn} 回合  继续战斗', ui.COL_PLAYER)
        sfx.play('turn')
        self.state = 'IDLE'

    def save_battle_state(self):
        """战斗中挂起存档（地图菜单「保存进度」）。"""
        save.save_battle({
            'chapter_idx': self.chapter_idx,
            'turn': self.turn,
            'camp_turns': self.camp_turns,
            'boss_quote_shown': self.boss_quote_shown,
            'reinforce_used': sorted(self.reinforce_used),
            'pending_reinforce': list(self.pending_reinforce),
            'roster_meta': [u.to_battle_dict() for u in self.roster],
            'snapshot': [u.to_dict() for u in self.snapshot],
            'enemies': [u.to_battle_dict() for u in self.units
                        if u.team == 'enemy' and u.alive],
        })

    # ---------- 对话/旁白播放器 ----------

    def start_dialogue(self, lines, after):
        """播放对话（战场背景），播完调用 after()。"""
        if not lines:
            after()
            return
        self.dialogue_lines = list(lines)
        self.dialogue_idx = 0
        self.after_dialogue = after
        self.state = 'DIALOGUE'

    def advance_dialogue(self, skip=False):
        sfx.play('select')
        self.dialogue_idx += 1
        if skip or self.dialogue_idx >= len(self.dialogue_lines):
            after = self.after_dialogue
            self.dialogue_lines, self.after_dialogue = [], None
            after()

    def start_pages(self, pages, after):
        """播放黑底旁白页（序章/尾声），播完调用 after()。"""
        if not pages:
            after()
            return
        self.pages = list(pages)
        self.page_idx = 0
        self.after_pages = after
        self.state = 'PROLOGUE'

    def advance_page(self, skip=False):
        sfx.play('select')
        self.page_idx += 1
        if skip or self.page_idx >= len(self.pages):
            after = self.after_pages
            self.pages, self.after_pages = [], None
            after()

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
            save.save_game(self.chapter_idx, [u.to_dict() for u in self.roster],
                           camp_turns=self.camp_turns)
        enemies = []
        for e in ch['enemies']:
            u = Unit(e['name'], e['cls'], 'enemy', e['pos'],
                     boss=e.get('boss', False), ai=e.get('ai', 'aggro'))
            u.apply_boost(ch.get('enemy_boost', {}))
            u.apply_boost(e.get('boost', {}))
            enemies.append(u)
        self.units = self.roster + enemies
        self.grid = Grid(ch['map'])
        self.turn = 1
        self._clear_battle_state()
        self.boss_quote_shown = False
        self.pending_reinforce, self.reinforce_used = [], set()
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
        self.camp_turns += self.turn
        if self.chapter_idx + 1 < len(CHAPTERS):
            save.save_game(self.chapter_idx + 1, [u.to_dict() for u in self.roster],
                           camp_turns=self.camp_turns)
        else:
            save.delete_save()         # 通关删档
        self.state = 'CLEAR'

    def next_chapter(self):
        self.chapter_idx += 1
        if self.chapter_idx >= len(CHAPTERS):
            self.chapter_idx = len(CHAPTERS) - 1     # COMPLETE 画面仍可安全访问 chapter
            self.start_pages(story.EPILOGUE, self._enter_complete)
        else:
            self.begin_intro()

    def _enter_complete(self):
        save.delete_save()             # 幂等兜底
        self.records = records.add_clear(self.camp_turns)
        self.state = 'COMPLETE'

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
        ch = self.chapter
        if ch['win'] == 'defend' and self.turn > ch['hold_turns']:
            sfx.play('victory')              # 坚守成功
            self.trigger_victory()
            return
        for u in self.alive('player'):
            u.acted = False
        self.fortress_heal('player')
        self.show_banner(f'第 {self.turn} 回合  玩家行动', ui.COL_PLAYER)
        sfx.play('turn')
        self.state = 'IDLE'

    def spawn_reinforcements(self):
        """敌方阶段开始时刷增援；落点被占则顺延下回合。返回是否有刷出。"""
        specs = list(self.pending_reinforce)
        self.pending_reinforce = []
        table = self.chapter.get('reinforce', {})
        if self.turn in table and self.turn not in self.reinforce_used:
            self.reinforce_used.add(self.turn)
            specs += table[self.turn]
        spawned = False
        for spec in specs:
            if self.unit_at(tuple(spec['pos'])) is None:
                u = Unit(spec['name'], spec['cls'], 'enemy', spec['pos'],
                         boss=spec.get('boss', False), ai=spec.get('ai', 'aggro'))
                u.apply_boost(self.chapter.get('enemy_boost', {}))
                u.apply_boost(spec.get('boost', {}))
                self.units.append(u)
                spawned = True
            else:
                self.pending_reinforce.append(spec)
        return spawned

    def start_enemy_phase(self):
        for u in self.alive('player'):
            u.acted = True
        self.clear_selection()
        self.fortress_heal('enemy')
        if self.spawn_reinforcements():
            self.show_banner('敌 方 增 援 ！', ui.COL_ENEMY)
        else:
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

    def open_map_menu(self, cell):
        """火纹式地图菜单：点击空地呼出。"""
        sfx.play('select')
        self.map_menu_pos = cell
        self.menu_items = [('结束回合', True), ('保存进度', True)]
        self.menu_sel = 0
        self.state = 'MAP_MENU'

    def select_next_unit(self):
        """Tab 循环选择下一个未行动单位。"""
        avail = [u for u in self.alive('player') if not u.acted]
        if not avail:
            return
        if self.selected in avail:
            idx = (avail.index(self.selected) + 1) % len(avail)
        else:
            idx = 0
        self.select(avail[idx])

    def all_threat_tiles(self):
        """全部存活敌人的(移动∪攻击)范围并集。"""
        tiles = set()
        for e in self.alive('enemy'):
            t, fringe = self._range_tiles(e, allow_move=not e.boss)
            tiles |= set(t) | fringe
        return tiles

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
        if not combat.can_attack(unit):
            return []
        lo, hi = unit.weapon_range
        return [u for u in self.alive('enemy')
                if lo <= manhattan((unit.x, unit.y), (u.x, u.y)) <= hi]

    def heal_targets_from(self, unit):
        """治疗杖目标：相邻的受伤友军。"""
        if combat.can_attack(unit):
            return []
        return [u for u in self.alive('player')
                if u is not unit and u.hp < u.max_hp
                and manhattan((unit.x, unit.y), (u.x, u.y)) == 1]

    def enter_menu(self):
        u = self.selected
        self.target_mode = 'attack'
        self.targets = self.targets_from(u)
        heals = self.heal_targets_from(u)
        self.menu_items = []
        if combat.can_attack(u):
            self.menu_items.append(('攻击', bool(self.targets)))
        else:
            self.menu_items.append(('治疗', bool(heals)))
        self.menu_items += [('用药', u.potions > 0 and u.hp < u.max_hp),
                            ('待机', True)]
        self.menu_sel = 0
        self.state = 'MENU'

    def trigger_victory(self):
        post = story.CHAPTER_DIALOGUE[self.chapter_idx]['post']
        self.start_dialogue(post, self.chapter_clear)

    def finish_unit(self):
        self.selected.acted = True
        ch = self.chapter
        if (ch['win'] == 'seize' and self.selected is self.lord
                and (self.lord.x, self.lord.y) == tuple(ch['goal'])):
            self.clear_selection()
            sfx.play('victory')
            self.trigger_victory()           # 占领目标点
            return
        self.clear_selection()
        self.state = 'IDLE'
        if all(u.acted for u in self.alive('player')):
            self.start_enemy_phase()

    # ---------- 战斗 ----------

    def add_float(self, text, pos, color):
        self.floats.append({'text': text, 'x': pos[0], 'y': pos[1], 't': 0.0, 'color': color})

    def start_combat(self, att, dfd, after):
        dist = manhattan((att.x, att.y), (dfd.x, dfd.y))
        att_avoid = self.grid.avoid(att)
        def_avoid = self.grid.avoid(dfd)
        self.hp_display = {att: att.hp, dfd: dfd.hp}
        events, exp = combat.resolve(att, dfd, dist, att_avoid, def_avoid)
        self.combat_events = events
        self.combat_idx, self.event_t, self.event_spawned = 0, 0.0, False
        self.pending_exp = exp
        self.after_combat = after
        self.state = 'COMBAT'

    def combat_finished(self):
        # 死亡淡出动画 + 击破计数
        dead = {u for ev in self.combat_events for u in (ev['actor'], ev['target'])
                if not u.alive}
        for u in dead:
            self.dying.append({'unit': u, 't': 0.0})
            sfx.play('die')
        enemy_dead = len([u for u in dead if u.team == 'enemy'])
        if enemy_dead:
            self.records = records.add_kills(enemy_dead)
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
            self.trigger_victory()
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
            if self.state in ('MENU', 'MAP_MENU'):
                for i, r in enumerate(self.menu_rects):
                    if r.collidepoint(event.pos):
                        self.menu_sel = i
            return

        click = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        key = event.key if event.type == pygame.KEYDOWN else None

        # --- 流程画面 ---
        if self.state == 'TITLE':
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('confirm')
                self.new_game()
            elif click:
                for i, r in enumerate(self.title_rects):
                    if not r.collidepoint(event.pos):
                        continue
                    if i == 0:
                        sfx.play('confirm')
                        self.new_game()
                    elif i == 1 and self.save_data is not None:
                        sfx.play('confirm')
                        self.continue_game()
                    elif i == 2:
                        sfx.play('confirm')
                        self.codex_sel = 0
                        self.state = 'CODEX'
                    return
            return
        if self.state == 'CODEX':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'TITLE'
            elif key == pygame.K_LEFT:
                self.codex_sel = (self.codex_sel - 1) % len(story.CODEX_ORDER)
                sfx.play('select')
            elif key == pygame.K_RIGHT:
                self.codex_sel = (self.codex_sel + 1) % len(story.CODEX_ORDER)
                sfx.play('select')
            elif click:
                for i, r in enumerate(self.codex_rects):
                    if r.collidepoint(event.pos):
                        self.codex_sel = i
                        sfx.play('select')
            return
        if self.state == 'DETAIL':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            if click or rclick or key in (pygame.K_ESCAPE, pygame.K_i):
                sfx.play('cancel')
                self.state = self.detail_return
            return
        if self.state == 'PROLOGUE':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                self.advance_page()
            elif key == pygame.K_ESCAPE:
                self.advance_page(skip=True)
            return
        if self.state == 'DIALOGUE':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                self.advance_dialogue()
            elif key == pygame.K_ESCAPE:
                self.advance_dialogue(skip=True)
            return
        if self.state == 'INTRO':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('confirm')
                self.setup_chapter()
                pre = story.CHAPTER_DIALOGUE[self.chapter_idx]['pre']
                self.start_dialogue(pre, self.enter_battle)
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
                unacted = [u for u in self.alive('player') if not u.acted]
                if not unacted or self.end_confirm_t > 0:
                    self.end_confirm_t = 0.0
                    self.start_enemy_phase()
                else:
                    self.end_confirm_t = 2.0
                    self.show_banner('尚有未行动单位 · 再按 E 确认', ui.COL_GOLD)
            elif key == pygame.K_d and self.state in ('IDLE', 'MOVE'):
                self.threat_all = not self.threat_all
                sfx.play('select')
            elif key == pygame.K_TAB and self.state in ('IDLE', 'MOVE'):
                self.select_next_unit()
            elif key == pygame.K_i and self.state in ('IDLE', 'MOVE'):
                u = ((self.unit_at(self.hover) if self.hover else None)
                     or self.selected or self.threat_unit)
                if u is not None:
                    sfx.play('select')
                    self.detail_unit, self.detail_return = u, self.state
                    self.state = 'DETAIL'
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
        if self.state == 'MAP_MENU':
            sfx.play('cancel')
            self.state = 'IDLE'
        elif self.state == 'MOVE':
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

        if self.state == 'MAP_MENU':
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(pos):
                    label = self.menu_items[i][0]
                    sfx.play('confirm')
                    self.state = 'IDLE'
                    if label == '结束回合':
                        self.start_enemy_phase()
                    else:                          # 保存进度
                        self.save_battle_state()
                        self.add_float('已保存', self.map_menu_pos, ui.COL_GOLD)
                    return
            self.state = 'IDLE'                    # 点菜单外关闭
            return

        if self.state == 'MENU':
            for i, r in enumerate(self.menu_rects):
                if r.collidepoint(pos) and self.menu_items[i][1]:
                    label = self.menu_items[i][0]
                    sfx.play('confirm')
                    if label == '攻击':
                        self.target_mode = 'attack'
                        self.state = 'TARGET'
                    elif label == '治疗':
                        self.target_mode = 'heal'
                        self.targets = self.heal_targets_from(self.selected)
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
                self.open_map_menu(cell)         # 空地 → 地图菜单

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
                    if self.target_mode == 'heal':
                        self.perform_heal(t)
                        return
                    self.target = t
                    dist = manhattan((self.selected.x, self.selected.y), cell)
                    self.fc = combat.forecast(self.selected, t, dist,
                                              self.grid.avoid(self.selected),
                                              self.grid.avoid(t))
                    self.state = 'FORECAST'
                    return

        elif self.state == 'FORECAST':
            self.confirm_attack()

    def perform_heal(self, target):
        """修女治疗：立即结算，无预测无反击。"""
        sfx.play('heal')
        amount = min(combat.heal_amount(self.selected), target.max_hp - target.hp)
        target.heal(amount)
        self.add_float(f'+{amount}', (target.x, target.y), (120, 230, 120))
        self.add_float('+15EXP', (self.selected.x, self.selected.y), (160, 200, 255))
        self.after_combat = 'player'
        for gains in self.selected.gain_exp(15):
            self.levelups.append((self.selected, gains))
        if self.levelups:
            self.levelup_t = 0.0
            sfx.play('levelup')
            self.state = 'LEVELUP'
        else:
            self.finish_unit()

    def confirm_attack(self):
        sfx.play('confirm')
        if self.target.boss and not self.boss_quote_shown:
            self.boss_quote_shown = True
            att, dfd = self.selected, self.target
            self.start_dialogue(story.BOSS_QUOTES[self.chapter_idx],
                                lambda: self.start_combat(att, dfd, 'player'))
        else:
            self.start_combat(self.selected, self.target, 'player')

    # ---------- 更新 ----------

    def update(self, dt):
        self.time += dt
        if self.state in ('TITLE', 'INTRO', 'COMPLETE', 'PROLOGUE', 'DIALOGUE',
                          'CODEX', 'DETAIL'):
            return
        for f in self.floats:
            f['t'] += dt / FLOAT_DUR
        self.floats = [f for f in self.floats if f['t'] < 1.0]
        for d in self.dying:
            d['t'] += dt / 0.6
        self.dying = [d for d in self.dying if d['t'] < 1.0]
        self.flash_t = max(0.0, self.flash_t - dt)
        self.end_confirm_t = max(0.0, self.end_confirm_t - dt)
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
                    self.flash_t = 0.12
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
            items = [('新游戏', True),
                     ('继续游戏', self.save_data is not None),
                     ('人物图鉴', True)]
            summary = None
            if self.save_data is not None:
                sd = self.save_data
                idx = sd['chapter_idx']
                num = '一二三四五六七八九十'[idx]
                if sd.get('kind') == 'battle':
                    alive = len([d for d in sd['roster_meta'] if d['hp'] > 0])
                    summary = (f'存档：第{num}章「{CHAPTERS[idx]["title"]}」'
                               f'战斗中·回合{sd["turn"]} ｜ {alive}人存活')
                else:
                    roster = sd['roster']
                    avg = round(sum(d['level'] for d in roster) / len(roster))
                    summary = (f'存档：第{num}章「{CHAPTERS[idx]["title"]}」'
                               f' ｜ {len(roster)}人 平均Lv{avg}')
            self.title_rects = ui.draw_title_menu(surf, items, summary)
            r = self.records
            if r['clears'] or r['kills']:
                best = f' ｜ 最佳 {r["best_turns"]} 回合' if r['best_turns'] else ''
                ui.draw_records_line(
                    surf, f'通关 {r["clears"]} 周目 ｜ 累计击破 {r["kills"]}{best}')
            frame = int(self.time * 2.4)
            start_x = (720 - len(self.roster) * 84) // 2
            for i, u in enumerate(self.roster):
                surf.blit(assets.unit_sprite(u.cls, (frame + i) % 2), (start_x + i * 84, 282))
            return
        if self.state == 'INTRO':
            ui.draw_intro(surf, self.chapter_idx, self.chapter)
            return
        if self.state == 'COMPLETE':
            ui.draw_complete(surf, self.roster, story.FATES)
            return
        if self.state == 'PROLOGUE':
            ui.draw_prologue(surf, self.pages[self.page_idx],
                             self.page_idx, len(self.pages))
            return
        if self.state == 'CODEX':
            entries = [(n, story.BIOS[n]) for n in story.CODEX_ORDER]
            pic_fn = lambda name, cls: assets.portrait(name) or assets.unit_sprite(cls)
            self.codex_rects = ui.draw_codex(surf, entries, self.codex_sel, pic_fn)
            return

        water_frame = int(self.time * 1.6) % 2
        for y in range(GRID_H):
            for x in range(GRID_W):
                ch = self.grid.rows[y][x]
                variant = 1 if (ch == 'B' and x > 0 and self.grid.rows[y][x - 1] == 'B') else 0
                surf.blit(assets.terrain_sprite(ch, water_frame, variant), (x * CELL, y * CELL))

        if self.threat_all and self.state in ('IDLE', 'MOVE'):
            ui.draw_tiles(surf, self.all_threat_tiles(), ui.ATTACK_TILE)
        if self.state == 'MOVE':
            ui.draw_tiles(surf, self.fringe, ui.ATTACK_TILE)
            ui.draw_tiles(surf, self.move_tiles, ui.MOVE_TILE)
        elif self.state in ('TARGET', 'FORECAST'):
            tile_col = ui.MOVE_TILE if self.target_mode == 'heal' else ui.TARGET_TILE
            ui.draw_tiles(surf, [(t.x, t.y) for t in self.targets], tile_col)
        elif self.state == 'IDLE' and self.threat:
            ui.draw_tiles(surf, self.threat, ui.ATTACK_TILE)
        if self.chapter['win'] == 'seize' and int(self.time * 2) % 2 == 0:
            ui.draw_cursor(surf, tuple(self.chapter['goal']), ui.COL_GOLD)   # 占领点闪烁

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

        for d in self.dying:               # 死亡淡出
            u = d['unit']
            spr = assets.unit_sprite(u.cls, 0).copy()
            spr.set_alpha(max(0, int(200 * (1 - d['t']))))
            surf.blit(spr, (u.x * CELL, u.y * CELL))
        if self.flash_t > 0:               # 必杀白闪
            veil = pygame.Surface((GRID_W * CELL, GRID_H * CELL), pygame.SRCALPHA)
            veil.fill((255, 255, 255, 80))
            surf.blit(veil, (0, 0))

        if self.selected and self.state in ('MOVE', 'MENU', 'TARGET', 'FORECAST'):
            ui.draw_cursor(surf, (self.selected.x, self.selected.y), ui.COL_GOLD)
        if self.threat_unit is not None and self.state == 'IDLE':
            ui.draw_cursor(surf, (self.threat_unit.x, self.threat_unit.y), ui.COL_ENEMY)
        if self.hover and self.state in ('IDLE', 'MOVE', 'TARGET'):
            ui.draw_cursor(surf, self.hover)

        for f in self.floats:
            ui.draw_float_text(surf, f['text'], f['x'] * CELL, f['y'] * CELL, f['t'], f['color'])

        if self.state == 'DIALOGUE':
            # 对话框盖在战场上，信息栏/菜单不再绘制
            pygame.draw.rect(surf, (16, 14, 24),
                             (0, GRID_H * CELL, 720, 100))
            speaker, side, text = self.dialogue_lines[self.dialogue_idx]
            pic = None
            if side is not None:
                pic = (assets.portrait(speaker)
                       or assets.unit_sprite(story.NAME_TO_CLS[speaker]))
            ui.draw_dialogue(surf, speaker, side, text, pic)
            return

        hover_unit = self.unit_at(self.hover) if self.hover else None
        info_unit = hover_unit or (self.selected if self.state != 'IDLE' else None)
        terrain_ch = (self.grid.rows[self.hover[1]][self.hover[0]]
                      if self.hover and self.grid.in_bounds(*self.hover) else None)
        ui.draw_info(surf, info_unit, terrain_ch)
        ui.draw_help(surf)
        obj = self.chapter['objective']
        if self.chapter['win'] == 'defend':
            remain = max(0, self.chapter['hold_turns'] - self.turn + 1)
            obj = f'{obj}（剩 {remain} 回合）'
        ui.draw_objective(surf, self.turn, obj)

        if self.state == 'MENU':
            px = (self.selected.x + 1) * CELL + 4
            py = self.selected.y * CELL
            self.menu_rects = ui.draw_menu(surf, self.menu_items, self.menu_sel, px, py)
        elif self.state == 'MAP_MENU':
            px = min((self.map_menu_pos[0] + 1) * CELL + 4, 720 - 130)
            py = min(self.map_menu_pos[1] * CELL, GRID_H * CELL - 90)
            self.menu_rects = ui.draw_menu(surf, self.menu_items, self.menu_sel, px, py)
        elif self.state == 'FORECAST':
            ui.draw_forecast(surf, self.fc, self.selected, self.target)
        elif self.state == 'LEVELUP' and self.levelups:
            u, gains = self.levelups[0]
            ui.draw_levelup(surf, u, gains, self.levelup_t)
        elif self.state == 'DETAIL':
            ui.draw_unit_detail(surf, self.detail_unit,
                                story.BIOS.get(self.detail_unit.name))

        if self.banner is not None:
            ui.draw_banner(surf, self.banner['text'], self.banner['t'], self.banner['color'])
        if self.state == 'CLEAR':
            ui.draw_clear(surf, self.chapter_idx, self.chapter['title'], self.turn)
        elif self.state == 'END':
            ui.draw_defeat(surf)
