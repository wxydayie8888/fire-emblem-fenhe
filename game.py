"""游戏状态机：战役流程 + 战斗回合调度。

流程: TITLE → INTRO → 战斗(IDLE/MOVE/MENU/TARGET/FORECAST/COMBAT/LEVELUP/ENEMY_TURN)
      → CLEAR → 下一章 INTRO … → COMPLETE；败北 → END(R 重试本章)
"""
import copy
import math
import random

import pygame

import assets
import combat
import config
import settings
import guide
import music
import records
import save
import sfx
import story
import supports
import ui
from ai import plan_action
from grid import Grid, manhattan, move_range
from settings import (CELL, CHAPTERS, DIFFICULTY, GOLD_PER_CLEAR, GOLD_PER_KILL,
                      GRID_H, GRID_W, MODES, PLAYER_ROSTER, POTION_USES,
                      SEED_STAT_GAIN, SHOP_ITEMS)
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
        self.seals = 0                # 转职证存量
        self.difficulty = 'normal'    # normal / hard
        self.permadeath = False       # 经典模式：阵亡永久退场
        self.fallen = set()           # 已永久阵亡的角色名（经典模式）
        self.gold = 0                 # 军资（击破/通关获得，章间商店消费）
        self.snapshot_gold = 0        # 本章开局的军资/转职证（败北重试时回滚，防刷）
        self.snapshot_seals = 0
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
        self.dialogue_t = 0.0                  # 对话逐字显示计时
        save.migrate_legacy()                  # 旧单档 → 槽1（幂等）
        self.refresh_slots()                   # 各槽摘要 + 是否有可继续的档
        self.records = records.load()          # 战绩记忆
        self.title_rects = []
        self.codex_sel, self.codex_rects = 0, []
        self.detail_unit, self.detail_return = None, 'IDLE'
        self.guide_page, self.guide_tabs = 0, []
        self.convo_lines, self.convo_idx, self.convo_title = [], 0, ''
        # 系统菜单/选项/存读档/部队列表 的临时选择态
        self.menu_return = 'TITLE'
        self.options_sel, self.options_return = 0, 'TITLE'
        self.slot_sel, self.slotmenu_mode, self.slotmenu_return = 0, 'load', 'TITLE'
        self.slot_rects, self.options_rects = [], []
        self.newgame_diff, self.newgame_mode, self.newgame_sel = 0, 0, 0
        self.newgame_rects = []
        self.roster_sel, self.roster_rects = 0, []
        self.shop_sel, self.shop_rects = 0, []
        self.shop_pending = None               # 待选目标的「之种」商品
        self.last_grade, self.last_clear_deaths = None, 0   # 本章战绩评定
        self.tower = False                     # 是否处于试炼之塔
        self.floor = 0
        self.tower_mut = None                  # 本层词条
        self.reward_cards, self.reward_sel, self.reward_rects = [], 0, []
        self.tower_sel, self.tower_rects = 0, []   # 元强化界面
        self.music_sel, self.music_rects = 0, []   # 音乐鉴赏室
        self.save_slot = 1                     # 上次手动存档使用的槽
        self.state = 'TITLE'

    def refresh_slots(self):
        """重新读取各存档槽摘要，并刷新「是否有可继续的存档」。"""
        self.slot_summaries = save.all_summaries()
        self._latest_slot = save.latest_slot()
        self.save_data = (save.load_game(self._latest_slot)
                          if self._latest_slot is not None else None)

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
        self.ff = False                # 空格按住：3倍速快进
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
        if not hasattr(self, 'events'):
            self.events = []           # 村庄/宝箱事件
        if not hasattr(self, 'recruited'):
            self.recruited = set()     # 已招降目标名

    @property
    def chapter(self):
        return CHAPTERS[self.chapter_idx]

    @property
    def lord(self):
        return self.roster[0]

    def begin_intro(self):
        self.state = 'INTRO'

    def open_support_convo(self, name):
        """打开某角色的全部支援对话（人物图鉴按 S）。"""
        import supports
        lines, partners = [], []
        for pair in supports.SUPPORT_PAIRS:
            if name in pair:
                other = next(p for p in pair if p != name)
                convo = story.support_convo(name, other)
                if convo:
                    partners.append(other)
                    lines.append(('—', f'· {name} 与 {other} ·'))
                    lines.extend(convo)
        if not lines:
            return
        sfx.play('confirm')
        self.convo_lines = lines
        self.convo_idx = 0
        self.convo_title = name
        self.state = 'CONVO'

    def new_game(self):
        """开新档：先进难度/模式选择界面。"""
        sfx.play('confirm')
        self.newgame_diff = ['normal', 'hard'].index(self.difficulty)
        self.newgame_mode = 1 if self.permadeath else 0
        self.newgame_sel = 0
        self.state = 'NEWGAME'

    def confirm_new_game(self):
        """从 NEWGAME 选择界面确认：定难度/模式后进入战役。"""
        self.difficulty = ['normal', 'hard'][self.newgame_diff]
        self.permadeath = (self.newgame_mode == 1)
        self.fallen = set()
        sfx.play('confirm')
        self.begin_campaign()

    def begin_campaign(self):
        self.chapter_idx = 0
        if all(assets.cinema(s['img']) is not None for s in story.CINEMA_SCENES):
            self.cinema_idx, self.cinema_t = 0, 0.0
            self.state = 'CINEMA'              # 电影化前情提要
            music.play_cinema()               # AI 史诗交响乐
        else:
            self.start_pages(story.PROLOGUE, self.begin_intro)

    def cinema_next(self, skip_all=False):
        sfx.play('select')
        self.cinema_idx += 1
        self.cinema_t = 0.0
        if skip_all or self.cinema_idx >= len(story.CINEMA_SCENES):
            music.stop_cinema()
            self.begin_intro()

    def load_slot(self, slot):
        """从指定槽读档并恢复。无效则提示。"""
        sd = save.load_game(slot)
        if sd is None:
            sfx.play('cancel')
            return False
        sfx.play('confirm')
        self.save_data = sd
        self.save_slot = slot if slot in save.MANUAL_SLOTS else self.save_slot
        self.continue_game()
        return True

    def continue_game(self):
        """从存档恢复：章节档进过场，战斗档直接回到战局。"""
        sd = self.save_data
        self.chapter_idx = sd['chapter_idx']
        self.camp_turns = sd.get('camp_turns', 0)
        self.seals = sd.get('seals', 0)
        self.gold = sd.get('gold', 0)
        self.difficulty = sd.get('difficulty', 'normal')
        self.permadeath = (sd.get('mode', 'casual') == 'classic')
        self.fallen = set(sd.get('fallen', []))
        if sd.get('kind') == 'battle':
            self.restore_battle(sd)
        else:
            self.roster = [Unit.from_dict(d) for d in sd['roster']]
            self.snapshot = copy.deepcopy(self.roster)
            self.snapshot_gold, self.snapshot_seals = self.gold, self.seals
            self.begin_intro()

    def restore_battle(self, sd):
        """精确恢复挂起的战局。"""
        self.grid = Grid(self.chapter['map'])
        self._apply_payload(sd)
        self.undo_stack, self.undo_left = [], 10
        self.pending_undo = None
        self.show_banner(f'第 {self.turn} 回合  继续战斗', ui.COL_PLAYER)
        sfx.play('turn')
        self.state = 'IDLE'

    def _battle_payload(self):
        """当前战局的完整可序列化快照（挂起存档与时光回溯共用）。"""
        return {
            'chapter_idx': self.chapter_idx,
            'turn': self.turn,
            'camp_turns': self.camp_turns,
            'seals': self.seals,
            'gold': self.gold,
            'snapshot_gold': self.snapshot_gold,
            'snapshot_seals': self.snapshot_seals,
            'difficulty': self.difficulty,
            'mode': 'classic' if self.permadeath else 'casual',
            'fallen': sorted(self.fallen),
            'boss_quote_shown': self.boss_quote_shown,
            'events_done': [list(e['pos']) for e in self.events if e['done']],
            'recruited': sorted(self.recruited),
            'reinforce_used': sorted(self.reinforce_used),
            'pending_reinforce': list(self.pending_reinforce),
            'roster_meta': [u.to_battle_dict() for u in self.roster],
            'snapshot': [u.to_dict() for u in self.snapshot],
            'enemies': [u.to_battle_dict() for u in self.units
                        if u.team == 'enemy' and u.alive],
        }

    def save_battle_state(self, slot=None):
        """战斗中挂起存档到指定槽（默认上次手动槽）。"""
        slot = slot if slot is not None else self.save_slot
        save.save_battle(self._battle_payload(), slot)
        self.refresh_slots()

    def autosave(self, chapter_idx=None):
        """章节进度写入「自动存档」槽（受选项开关控制）。"""
        if not config.get('autosave'):
            return
        idx = self.chapter_idx if chapter_idx is None else chapter_idx
        save.save_game(idx, [u.to_dict() for u in self.roster], save.AUTO_SLOT,
                       camp_turns=self.camp_turns, seals=self.seals, gold=self.gold,
                       mode='classic' if self.permadeath else 'casual',
                       difficulty=self.difficulty, fallen=self.fallen)
        self.refresh_slots()

    def _apply_payload(self, sd):
        """从快照恢复战局（读档与时光回溯共用）。"""
        self.roster = [Unit.from_battle_dict(d) for d in sd['roster_meta']]
        self.snapshot = [Unit.from_dict(d) for d in sd['snapshot']]
        enemies = [Unit.from_battle_dict(d) for d in sd['enemies']]
        self.units = self.roster + enemies
        self._clear_battle_state()
        self.turn = sd['turn']
        self.camp_turns = sd.get('camp_turns', self.camp_turns)
        self.boss_quote_shown = sd['boss_quote_shown']
        self.seals = sd.get('seals', self.seals)
        self.gold = sd.get('gold', self.gold)
        self.snapshot_gold = sd.get('snapshot_gold', self.gold)
        self.snapshot_seals = sd.get('snapshot_seals', self.seals)
        self.difficulty = sd.get('difficulty', self.difficulty)
        if 'mode' in sd:
            self.permadeath = (sd['mode'] == 'classic')
        self.fallen = set(sd.get('fallen', self.fallen))
        self.reinforce_used = set(sd['reinforce_used'])
        self.pending_reinforce = list(sd['pending_reinforce'])
        # 重建本章事件并恢复已完成状态 + 已招降名单
        self.events = [{'pos': tuple(e['pos']), 'kind': e['kind'],
                        'reward': dict(e['reward']), 'done': False}
                       for e in self.chapter.get('events', [])]
        done = {tuple(p) for p in sd.get('events_done', [])}
        for e in self.events:
            if e['pos'] in done:
                e['done'] = True
        self.recruited = set(sd.get('recruited', []))

    def commit_undo(self):
        """把待定快照压入回溯栈（在行动不可逆地开始时调用）。"""
        if self.pending_undo is not None:
            self.undo_stack.append(self.pending_undo)
            self.pending_undo = None
            if len(self.undo_stack) > 10:
                self.undo_stack.pop(0)

    def can_undo(self):
        return bool(self.undo_stack) and self.undo_left > 0

    def do_undo(self):
        """时光回溯：回到上一次我方行动开始前。"""
        sd = self.undo_stack.pop()
        self.undo_left -= 1
        self._apply_payload(sd)
        sfx.play('rewind')
        self.show_banner(f'时 光 回 溯（剩 {self.undo_left} 次）', (170, 140, 255))
        self.state = 'IDLE'

    # ---------- 对话/旁白播放器 ----------

    def start_dialogue(self, lines, after):
        """播放对话（战场背景），播完调用 after()。"""
        if not lines:
            after()
            return
        self.dialogue_lines = list(lines)
        self.dialogue_idx = 0
        self.dialogue_t = 0.0
        self.after_dialogue = after
        self.state = 'DIALOGUE'

    def advance_dialogue(self, skip=False):
        sfx.play('select')
        self.dialogue_idx += 1
        self.dialogue_t = 0.0
        if skip or self.dialogue_idx >= len(self.dialogue_lines):
            after = self.after_dialogue
            self.dialogue_lines, self.after_dialogue = [], None
            after()

    def _dialogue_full(self):
        """当前对话行是否已逐字显示完。"""
        if self.dialogue_idx >= len(self.dialogue_lines):
            return True
        text = self.dialogue_lines[self.dialogue_idx][2]
        return int(self.dialogue_t * config.text_cps()) >= len(text)

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
            self.gold, self.seals = self.snapshot_gold, self.snapshot_seals   # 回滚军资防刷
        elif not retry:
            for j in ch['join']:
                # 幂等：读档进来的 roster 可能已含本章同伴；经典模式：阵亡者不再归队
                if (j['name'] not in self.fallen
                        and all(u.name != j['name'] for u in self.roster)):
                    self.roster.append(Unit(j['name'], j['cls'], 'player', j['pos']))
        # 布阵：本章新加入者各就其专属入场格，其余主力依次填入 players 格。
        # 用名字映射而非按下标 zip——经典模式阵亡使队伍变短时也不会错位。
        join_pos = {j['name']: tuple(j['pos']) for j in ch['join']}
        army = [u for u in self.roster if u.name not in join_pos]
        posmap = {u.name: pos for u, pos in zip(army, ch['players'])}
        posmap.update({u.name: join_pos[u.name]
                       for u in self.roster if u.name in join_pos})
        for u in self.roster:
            if u.name in posmap:
                u.x, u.y = posmap[u.name]
            u.hp = u.max_hp            # 每章开始幸存者满血（经典模式阵亡者已不在队中）
            u.acted = False
            u.potions = POTION_USES
            u.refresh_weapon()         # 武器耐久修复满
        if not retry:
            self.snapshot = copy.deepcopy(self.roster)
            self.snapshot_gold, self.snapshot_seals = self.gold, self.seals
            self.autosave()
        diff_boost = DIFFICULTY[self.difficulty]['boost']
        enemies = []
        for e in ch['enemies']:
            u = Unit(e['name'], e['cls'], 'enemy', e['pos'],
                     boss=e.get('boss', False), ai=e.get('ai', 'aggro'))
            u.apply_boost(ch.get('enemy_boost', {}))
            u.apply_boost(e.get('boost', {}))
            u.apply_boost(diff_boost)               # 难度强化
            enemies.append(u)
        self.units = self.roster + enemies
        self.grid = Grid(ch['map'])
        self.turn = 1
        self._clear_battle_state()
        self.boss_quote_shown = False
        self.events = [{'pos': tuple(e['pos']), 'kind': e['kind'],
                        'reward': dict(e['reward']), 'done': False}
                       for e in ch.get('events', [])]
        self.recruited = set()         # 已招降目标名
        self.pending_reinforce, self.reinforce_used = [], set()
        self.undo_stack, self.undo_left = [], 10    # 时光回溯：每战 10 次
        self.pending_undo = None
        self.state = 'IDLE'

    def enter_battle(self):
        """开战：回合横幅 + 进入待机。"""
        self.show_banner(f'第 {self.turn} 回合  玩家行动', ui.COL_PLAYER)
        sfx.play('turn')
        self.state = 'IDLE'

    def start_chapter(self, retry=False):
        self.setup_chapter(retry)
        self.enter_battle()

    @staticmethod
    def _grade_for(turns, deaths):
        """战绩评定：无人阵亡 + 速度 → S/A，否则 B/C。"""
        if deaths == 0 and turns <= 7:
            return 'S'
        if deaths == 0 and turns <= 11:
            return 'A'
        if deaths <= 1 and turns <= 15:
            return 'B'
        return 'C'

    def chapter_clear(self):
        sfx.play('victory')
        self.camp_turns += self.turn
        self.seals += 1               # 每章通关获得 1 枚转职证
        self.gold += GOLD_PER_CLEAR    # 通关军资
        deaths = sum(1 for u in self.roster if not u.alive)
        self.last_grade = self._grade_for(self.turn, deaths)
        self.last_clear_deaths = deaths
        self.records = records.set_grade(self.chapter_idx, self.last_grade)
        if self.permadeath:           # 经典模式：本章阵亡者永久退场
            for u in self.roster:
                if not u.alive:
                    self.fallen.add(u.name)
            self.roster = [u for u in self.roster if u.alive]
        if self.chapter_idx + 1 < len(CHAPTERS):
            self.autosave(self.chapter_idx + 1)
        else:
            save.delete_save(save.AUTO_SLOT)   # 通关删自动档（手动档保留）
            self.refresh_slots()
        self.state = 'CLEAR'

    def next_chapter(self):
        self.chapter_idx += 1
        if self.chapter_idx >= len(CHAPTERS):
            self.chapter_idx = len(CHAPTERS) - 1     # COMPLETE 画面仍可安全访问 chapter
            self.start_pages(story.EPILOGUE, self._enter_complete)
        else:
            self.begin_intro()

    def _enter_complete(self):
        save.delete_save(save.AUTO_SLOT)   # 幂等兜底（手动档保留）
        self.refresh_slots()
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

    def hint_text(self):
        """顶部即时提示：当前状态下「该做什么」。"""
        s = self.state
        if s == 'IDLE':
            if self.threat_unit is not None:
                return '查看敌人威胁范围　·　右键关闭'
            if not [u for u in self.alive('player') if not u.acted]:
                return '全员已行动　·　按 E 结束回合'
            return '点击我方单位行动　·　点空地呼出菜单　·　E 结束回合'
        if s == 'MOVE':
            return '点击蓝色格移动　·　红格为攻击范围　·　右键取消'
        if s == 'MENU':
            return '选择行动'
        if s == 'TARGET':
            return '选择治疗对象' if self.target_mode == 'heal' else '选择攻击目标'
        if s == 'FORECAST':
            return '查看预测，回车 / 左键 确认攻击　·　右键取消'
        if s == 'ENEMY_TURN':
            return '敌方行动中……（按住空格快进）'
        return ''

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
                u.apply_boost(DIFFICULTY[self.difficulty]['boost'])   # 难度强化
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
            sfx.play('reinforce')
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
        self.pending_undo = self._battle_payload()   # 行动前快照（待提交）
        self.threat, self.threat_unit = set(), None
        self.selected = unit
        self.orig_pos = (unit.x, unit.y)
        self.move_tiles, self.fringe = self._range_tiles(unit)
        self.state = 'MOVE'

    def open_map_menu(self, cell):
        """火纹式系统菜单：点击空地呼出（结束回合/存读档/选项/回溯）。"""
        sfx.play('select')
        self.map_menu_pos = cell
        if self.tower:                          # 试炼中：不可存读档/回溯
            self.menu_items = [('结束回合', True), ('部队列表', True),
                               ('选项', True), ('放弃试炼', True)]
        else:
            self.menu_items = [('结束回合', True), ('保存进度', True), ('读取进度', True),
                               ('部队列表', True), ('选项', True),
                               (f'回溯×{self.undo_left}', self.can_undo())]
        self.menu_sel = 0
        self.state = 'MAP_MENU'

    def open_slot_menu(self, mode, return_state):
        """打开存/读档槽界面。mode: 'save'(仅手动槽) / 'load'(全部槽)。"""
        sfx.play('select')
        self.refresh_slots()
        self.slotmenu_mode = mode
        self.slotmenu_return = return_state
        self.slot_sel = 0
        self.state = 'SAVE_MENU' if mode == 'save' else 'LOAD_MENU'

    def open_options(self, return_state):
        sfx.play('select')
        self.options_sel = 0
        self.options_return = return_state
        self.state = 'OPTIONS'

    def open_roster(self, return_state='IDLE'):
        """部队列表：速览我方单位，可跳转/选中。"""
        if not self.alive('player'):
            return
        sfx.play('select')
        self.roster_sel = 0
        self.menu_return = return_state
        self.state = 'ROSTER'

    def open_shop(self):
        """章间商店（INTRO 按 S 进入）。"""
        sfx.play('select')
        self.shop_sel = 0
        self.shop_pending = None
        self.state = 'SHOP'

    def buy_item(self, item):
        """购买商品。之种类需先选角色（选后才扣费）。"""
        if self.gold < item['cost']:
            sfx.play('cancel')
            return
        if item['kind'] == 'seal':
            self.gold -= item['cost']
            self.seals += 1
            sfx.play('coin')
            self.autosave()
        elif item['kind'] == 'seed':
            if not self.alive('player') and not self.roster:
                return
            self.shop_pending = item
            self.roster_sel = 0
            sfx.play('select')
            self.state = 'SHOP_PICK'

    def apply_seed(self, unit):
        """对所选角色施用「之种」永久强化，扣费并存档。"""
        item = self.shop_pending
        if item is None:
            self.state = 'SHOP'
            return
        stat, gain = item['stat'], SEED_STAT_GAIN[item['stat']]
        if stat == 'hp':
            unit.max_hp += gain
            unit.hp = min(unit.max_hp, unit.hp + gain)
        else:
            setattr(unit, stat, getattr(unit, stat) + gain)
        self.gold -= item['cost']
        self.shop_pending = None
        sfx.play('coin')
        self.autosave()
        self.state = 'SHOP'

    def try_end_turn(self, from_menu=False):
        """结束我方回合。E 键在有未行动单位且开启确认时需二次按键；菜单选择直接结束。"""
        unacted = [u for u in self.alive('player') if not u.acted]
        if (not from_menu and unacted and config.get('confirm_end')
                and self.end_confirm_t <= 0):
            self.end_confirm_t = 2.0
            self.show_banner('尚有未行动单位 · 再按 E 确认', ui.COL_GOLD)
            return
        self.end_confirm_t = 0.0
        self.start_enemy_phase()

    def slot_list(self):
        """当前存/读档界面要显示的槽序列。"""
        if self.slotmenu_mode == 'save':
            return list(save.MANUAL_SLOTS)
        return list(save.ALL_SLOTS)

    def slot_choose(self, slot):
        """在存/读档界面确认某个槽。"""
        if self.slotmenu_mode == 'save':
            self.save_slot = slot
            self.save_battle_state(slot)
            self.add_float('已保存', self.map_menu_pos, ui.COL_GOLD)
            sfx.play('confirm')
            self.state = 'IDLE'
        else:
            if self.slot_summaries.get(slot, {}).get('exists'):
                self.load_slot(slot)           # 进入对应战局/过场
            else:
                sfx.play('cancel')

    def _activate_map_menu(self, label):
        """系统菜单项分发（鼠标点击与键盘回车共用）。"""
        if label == '结束回合':
            sfx.play('confirm')
            self.state = 'IDLE'
            self.try_end_turn(from_menu=True)
        elif label == '保存进度':
            self.open_slot_menu('save', 'IDLE')
        elif label == '读取进度':
            self.open_slot_menu('load', 'IDLE')
        elif label == '部队列表':
            self.open_roster('IDLE')
        elif label == '选项':
            self.open_options('IDLE')
        elif label == '放弃试炼':
            sfx.play('cancel')
            self.tower_defeat()
        elif label.startswith('回溯'):
            sfx.play('confirm')
            self.state = 'IDLE'
            self.do_undo()

    def _option_change(self, idx, direction):
        """调整某选项并即时生效（音量直接作用于 sfx/music）。"""
        key = config.SCHEMA[idx][0]
        config.cycle(key, direction)
        if key == 'music_vol':
            music.set_volume(config.music_frac())
        elif key == 'sfx_vol':
            sfx.set_volume(config.sfx_frac())
        sfx.play('select')

    def _roster_jump(self, unit):
        """部队列表确认：定位到该单位；未行动则直接选中，否则看详情。"""
        self.hover = (unit.x, unit.y)
        if not unit.acted:
            self.state = 'IDLE'
            self.select(unit)
        else:
            self.detail_unit, self.detail_return = unit, 'IDLE'
            self.state = 'DETAIL'

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
        """全部「可见」存活敌人的(移动∪攻击)范围并集（迷雾中隐藏敌人不计）。"""
        vis = self.visible_set()
        tiles = set()
        for e in self.alive('enemy'):
            if vis is not None and (e.x, e.y) not in vis:
                continue
            t, fringe = self._range_tiles(e, allow_move=not e.boss)
            tiles |= set(t) | fringe
        return tiles

    # ---------- 迷雾战争 / 天气 ----------

    def fog_radius(self):
        return self.chapter.get('ambient', {}).get('fog', 0)

    def weather_hit(self):
        from settings import WEATHER_HIT
        w = self.chapter.get('ambient', {}).get('weather')
        return WEATHER_HIT.get(w, 0)

    def visible_set(self):
        """迷雾下我方视野格的并集；无迷雾返回 None（全可见）。"""
        r = self.fog_radius()
        if not r:
            return None
        from settings import FOG_FLY_BONUS
        vis = set()
        for u in self.alive('player'):
            ur = r + (FOG_FLY_BONUS if u.fly else 0)
            for dx in range(-ur, ur + 1):
                for dy in range(-ur, ur + 1):
                    if abs(dx) + abs(dy) <= ur:
                        p = (u.x + dx, u.y + dy)
                        if self.grid.in_bounds(*p):
                            vis.add(p)
        return vis

    def enemy_hidden(self, e, vis=None):
        """敌人是否处于迷雾中（不可见）。"""
        if vis is None:
            vis = self.visible_set()
        return vis is not None and (e.x, e.y) not in vis

    # ---------- 试炼之塔（无尽 roguelite）----------

    def open_music_room(self):
        """音乐鉴赏室：逐曲试听全部配乐。"""
        sfx.play('confirm')
        self.music_sel = 0
        self.state = 'MUSIC'
        music.director.update(music.TRACK_LIST[0][0])   # 进入即放第一首

    def open_tower_hub(self):
        """标题进入试炼大厅（看最高层/晶核、买永久强化、出发）。"""
        sfx.play('confirm')
        self.tower_sel = 0
        self.state = 'TOWER_META'

    def start_tower(self):
        """开始一次试炼：组建队伍（叠加永久强化），布阵，刷第 1 层。"""
        self.tower = True
        self.floor = 1
        self.chapter_idx = 0           # 让 self.chapter 安全可访问（不用其胜负/氛围）
        self.difficulty, self.permadeath, self.gold = 'normal', False, 0
        up = self.records.get('tower', {})
        self.roster = []
        for name, cls in settings.TOWER_ROSTER:
            u = Unit(name, cls, 'player', (0, 0))
            for ud in settings.TOWER_UPGRADES:
                lv = up.get(ud['key'], 0)
                if lv:
                    u.apply_boost({ud['stat']: ud['gain'] * lv})
            self.roster.append(u)
        self.snapshot = None
        self.grid = Grid(settings.TOWER_MAP)
        self.tower_spawn_floor()
        sfx.play('turn')
        self.state = 'IDLE'

    def tower_spawn_floor(self):
        """按层数刷敌：数量/数值随层递增，floor≥2 随机词条，每 5 层首领。"""
        f = self.floor
        self._clear_battle_state()
        self.turn = 1
        self.undo_stack, self.undo_left, self.pending_undo = [], 0, None
        self.pending_reinforce, self.reinforce_used = [], set()
        self.events, self.recruited = [], set()
        self.boss_quote_shown = True
        self.tower_mut = random.choice(settings.TOWER_MUTATORS) if f >= 2 else None
        for u, pos in zip(self.roster, settings.TOWER_PLAYER_POS):
            u.x, u.y = pos
            u.acted = False
            u.refresh_weapon()
        count = min(len(settings.TOWER_ENEMY_CELLS), 3 + f // 2)
        boss_floor = (f % settings.TOWER_BOSS_EVERY == 0)
        base = {'hp': 2 * f, 'pow': f, 'skl': f // 2, 'spd': f // 2, 'dfn': f // 2}
        enemies = []
        for i in range(count):
            is_boss = boss_floor and i == 0
            cls = 'general' if is_boss else settings.TOWER_POOL[(f + i) % len(settings.TOWER_POOL)]
            u = Unit(f'F{f}-{i + 1}', cls, 'enemy', settings.TOWER_ENEMY_CELLS[i],
                     boss=is_boss, ai='aggro')
            u.apply_boost(base)
            if is_boss:
                u.apply_boost({'hp': 3 * f, 'pow': f, 'dfn': f // 2})
            if self.tower_mut:
                u.apply_boost(self.tower_mut['boost'])
            enemies.append(u)
        self.units = self.roster + enemies
        mut = f'　词条：{self.tower_mut["name"]}' if self.tower_mut else ''
        self.show_banner(f'第 {f} 层{mut}', ui.COL_GOLD)

    def tower_after_combat(self):
        """试炼战斗收尾：清层→奖励，全灭/主将阵亡→结束。"""
        if not self.alive('enemy'):
            self.tower_floor_clear()
        elif not self.lord.alive or not self.alive('player'):
            self.tower_defeat()
        elif self.after_combat == 'player':
            self.finish_unit()
        else:
            self.enemy_sub = 'pause'
            self.pause_t = ENEMY_PAUSE
            self.state = 'ENEMY_TURN'

    def tower_floor_clear(self):
        """通过一层：弹三选一奖励。"""
        sfx.play('victory')
        self.reward_cards = random.sample(settings.TOWER_REWARDS, 3)
        self.reward_sel = 0
        self.state = 'REWARD'

    def apply_tower_reward(self, card):
        """施用所选奖励，进入下一层。"""
        k = card['key']
        if k == 'heal':
            for u in self.roster:
                if u.alive:
                    u.hp = u.max_hp
        elif k == 'revive':
            dead = [u for u in self.roster if not u.alive]
            if dead:
                dead[0].hp = max(1, dead[0].max_hp // 2)
        else:
            for u in self.roster:
                if u.alive:
                    u.apply_boost({k: 3 if k == 'hp' else 1})
        sfx.play('levelup')
        self.floor += 1
        self.tower_spawn_floor()
        self.state = 'IDLE'

    def tower_defeat(self):
        """试炼结束：记录最高层并发放晶核（=到达层数）。"""
        sfx.play('defeat')
        reached = self.floor
        self.records = records.add_tower_run(reached, reached)
        self.tower = False
        self.tower_over_floor = reached
        self.state = 'TOWER_OVER'

    def buy_tower_upgrade(self, ud):
        """用晶核购买一级永久强化。"""
        tower = dict(self.records.get('tower', {}))
        lv = tower.get(ud['key'], 0)
        if lv >= ud['max']:
            sfx.play('cancel')
            return
        cost = settings.tower_upgrade_cost(lv)
        if self.records['crystals'] < cost:
            sfx.play('cancel')
            return
        tower[ud['key']] = lv + 1
        self.records = records.set_tower_upgrades(tower, self.records['crystals'] - cost)
        sfx.play('confirm')

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
        vis = self.visible_set()                 # 迷雾中的敌人不可作为攻击目标
        return [u for u in self.alive('enemy')
                if lo <= manhattan((unit.x, unit.y), (u.x, u.y)) <= hi
                and not self.enemy_hidden(u, vis)]

    def heal_targets_from(self, unit):
        """治疗目标：相邻的受伤友军（仅 can_heal 的单位）。"""
        if not unit.can_heal():
            return []
        return [u for u in self.alive('player')
                if u is not unit and u.hp < u.max_hp
                and manhattan((unit.x, unit.y), (u.x, u.y)) == 1]

    def event_at(self, pos):
        """该格上未完成的村庄/宝箱事件（无则 None）。"""
        for e in self.events:
            if not e['done'] and e['pos'] == pos:
                return e
        return None

    def recruit_for(self, unit):
        """unit 可对话招降的相邻敌人（按章节 recruits 配置）；无则 None。"""
        for r in self.chapter.get('recruits', []):
            if r['by'] != unit.name or r['target'] in self.recruited:
                continue
            for e in self.alive('enemy'):
                if e.name == r['target'] and \
                        manhattan((unit.x, unit.y), (e.x, e.y)) == 1:
                    return r, e
        return None

    def enter_menu(self):
        u = self.selected
        self.target_mode = 'attack'
        self.targets = self.targets_from(u)
        heals = self.heal_targets_from(u)
        self.menu_items = []
        if combat.can_attack(u):
            self.menu_items.append(('攻击', bool(self.targets)))
        if u.can_heal():
            self.menu_items.append(('治疗', bool(heals)))
        rec = self.recruit_for(u)
        if rec is not None:
            self.menu_items.append(('对话', True))
        ev = self.event_at((u.x, u.y))
        if ev is not None:
            self.menu_items.append(('开启' if ev['kind'] == 'chest' else '访问', True))
        if u.can_promote() and self.seals > 0:
            self.menu_items.append(('转职', True))
        self.menu_items += [('用药', u.potions > 0 and u.hp < u.max_hp),
                            ('待机', True)]
        self.menu_sel = 0
        self.state = 'MENU'

    def do_event(self, unit):
        """访问村庄 / 开启宝箱：发放奖励，消耗事件与本回合行动。"""
        ev = self.event_at((unit.x, unit.y))
        if ev is None:
            self.finish_unit()
            return
        self.commit_undo()
        ev['done'] = True
        r = ev['reward']
        msg = []
        if 'gold' in r:
            self.gold += r['gold']
            msg.append(f'军资 +{r["gold"]}')
        if 'seal' in r:
            self.seals += r['seal']
            msg.append(f'转职证 +{r["seal"]}')
        sfx.play('chest')
        verb = '宝箱' if ev['kind'] == 'chest' else '村庄'
        self.add_float('  '.join(msg) or verb, (unit.x, unit.y), ui.COL_GOLD)
        self.show_banner(f'{verb}：{"  ".join(msg)}', ui.COL_GOLD)
        self.finish_unit()

    def do_recruit(self, unit):
        """对话招降相邻敌人：转为我方并入队，播台词，消耗本回合行动。"""
        rec = self.recruit_for(unit)
        if rec is None:
            self.finish_unit()
            return
        r, enemy = rec
        self.commit_undo()
        self.recruited.add(enemy.name)
        enemy.team = 'player'
        enemy.acted = True
        enemy.ai = 'aggro'
        enemy.boss = False
        if all(p.name != enemy.name for p in self.roster):
            self.roster.append(enemy)      # 持久入队
        sfx.play('confirm')
        self.add_float('加入！', (enemy.x, enemy.y), ui.COL_PLAYER)

        def after():
            self.show_banner(f'{enemy.name} 加入了队伍！', ui.COL_PLAYER)
            self.finish_unit()
        self.start_dialogue(r.get('lines', []), after)

    def do_promote(self, unit):
        """执行转职：消耗转职证，切换高级职，闪光提示，消耗本回合行动。"""
        self.commit_undo()
        self.seals -= 1
        old = unit.cls_name
        unit.promote()
        self.flash_t = 0.35
        sfx.play('promote')
        self.add_float('转职!', (unit.x, unit.y), ui.COL_GOLD)
        self.show_banner(f'{unit.name}  {old} → {unit.cls_name}！', ui.COL_GOLD)
        self.finish_unit()

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
        events, exp = combat.resolve(att, dfd, dist, att_avoid, def_avoid,
                                     att_sup=supports.support_bonus(att, self.units),
                                     def_sup=supports.support_bonus(dfd, self.units),
                                     weather=self.weather_hit())
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
            if u.team == 'player':
                tag = f'{u.name} 阵亡' if self.permadeath else f'{u.name} 倒下'
                self.add_float(tag, (u.x, u.y), ui.COL_ENEMY)
        enemy_dead = len([u for u in dead if u.team == 'enemy'])
        if enemy_dead:
            self.records = records.add_kills(enemy_dead)
            self.gold += enemy_dead * GOLD_PER_KILL        # 击破获得军资
        # 武器耐久：每次出手 -1（攻方），归零后破损（本章命中/伤害下降）
        for ev in self.combat_events:
            a = ev['actor']
            if hasattr(a, 'uses') and a.uses > 0:
                a.uses -= 1
                if a.uses == 0 and a.alive and a.team == 'player':
                    self.add_float('武器破损', (a.x, a.y), ui.COL_GOLD)
                    sfx.play('break')
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
        if self.tower:
            self.tower_after_combat()
            return
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
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.ff = True
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.ff = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
            music.set_enabled(not music.is_on())   # M 键开关音乐
            self.show_banner('音乐 开' if music.is_on() else '音乐 关', ui.COL_GOLD)
        if event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover = (mx // CELL, my // CELL) if my < GRID_H * CELL else None
            if self.state in ('MENU', 'MAP_MENU'):
                for i, r in enumerate(self.menu_rects):
                    if r.collidepoint(event.pos):
                        self.menu_sel = i
            elif self.state == 'OPTIONS':
                for i, r in enumerate(self.options_rects):
                    if r.collidepoint(event.pos):
                        self.options_sel = i
            elif self.state in ('SAVE_MENU', 'LOAD_MENU'):
                for i, r in enumerate(self.slot_rects):
                    if r.collidepoint(event.pos):
                        self.slot_sel = i
            elif self.state == 'ROSTER':
                for i, r in enumerate(self.roster_rects):
                    if r.collidepoint(event.pos):
                        self.roster_sel = i
            elif self.state == 'NEWGAME':
                for i, r in enumerate(self.newgame_rects):
                    if r.collidepoint(event.pos):
                        self.newgame_sel = 0 if i < 2 else (1 if i < 4 else 2)
            elif self.state == 'SHOP':
                for i, r in enumerate(self.shop_rects):
                    if r.collidepoint(event.pos):
                        self.shop_sel = i
            elif self.state == 'SHOP_PICK':
                for i, r in enumerate(self.roster_rects):
                    if r.collidepoint(event.pos):
                        self.roster_sel = i
            elif self.state == 'REWARD':
                for i, r in enumerate(self.reward_rects):
                    if r.collidepoint(event.pos):
                        self.reward_sel = i
            elif self.state == 'TOWER_META':
                for i, r in enumerate(self.tower_rects):
                    if r.collidepoint(event.pos):
                        self.tower_sel = i
            elif self.state == 'MUSIC':
                for i, r in enumerate(self.music_rects):
                    if r.collidepoint(event.pos):
                        self.music_sel = i
            return

        click = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        key = event.key if event.type == pygame.KEYDOWN else None

        # --- 流程画面 ---
        if self.state == 'TITLE':
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                self.new_game()
            elif click:
                for i, r in enumerate(self.title_rects):
                    if not r.collidepoint(event.pos):
                        continue
                    if i == 0:
                        self.new_game()
                    elif i == 1 and self.save_data is not None:
                        self.load_slot(self._latest_slot)
                    elif i == 2 and any(s['exists'] for s in self.slot_summaries.values()):
                        self.open_slot_menu('load', 'TITLE')
                    elif i == 3:
                        self.open_tower_hub()
                    elif i == 4:
                        self.open_options('TITLE')
                    elif i == 5:
                        sfx.play('confirm')
                        self.codex_sel = 0
                        self.state = 'CODEX'
                    elif i == 6:
                        sfx.play('confirm')
                        self.guide_page = 0
                        self.state = 'GUIDE'
                    elif i == 7:
                        self.open_music_room()
                    return
            return
        if self.state == 'NEWGAME':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'TITLE'
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.newgame_sel = (self.newgame_sel + (1 if key == pygame.K_DOWN else -1)) % 3
                sfx.play('select')
            elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                if self.newgame_sel == 0:
                    self.newgame_diff ^= 1
                elif self.newgame_sel == 1:
                    self.newgame_mode ^= 1
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.newgame_sel == 2:
                    self.confirm_new_game()
                elif self.newgame_sel == 0:
                    self.newgame_diff ^= 1
                    sfx.play('select')
                else:
                    self.newgame_mode ^= 1
                    sfx.play('select')
            elif click:
                for i, r in enumerate(self.newgame_rects):
                    if not r.collidepoint(event.pos):
                        continue
                    if i in (0, 1):
                        self.newgame_diff = i
                    elif i in (2, 3):
                        self.newgame_mode = i - 2
                    else:
                        self.confirm_new_game()
                        return
                    sfx.play('select')
                    return
            return
        if self.state == 'OPTIONS':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            n = len(config.SCHEMA)
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = self.options_return
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.options_sel = (self.options_sel + (1 if key == pygame.K_DOWN else -1)) % n
                sfx.play('select')
            elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._option_change(self.options_sel, 1 if key == pygame.K_RIGHT else -1)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._option_change(self.options_sel, 1)
            elif click:
                for i, r in enumerate(self.options_rects):
                    if r.collidepoint(event.pos):
                        self.options_sel = i
                        self._option_change(i, 1)
                        return
            return
        if self.state in ('SAVE_MENU', 'LOAD_MENU'):
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            slots = self.slot_list()
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = self.slotmenu_return if self.slotmenu_return != 'MAP_MENU' else 'IDLE'
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.slot_sel = (self.slot_sel + (1 if key == pygame.K_DOWN else -1)) % len(slots)
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.slot_choose(slots[self.slot_sel])
            elif click:
                for i, r in enumerate(self.slot_rects):
                    if r.collidepoint(event.pos):
                        self.slot_sel = i
                        self.slot_choose(slots[i])
                        return
            return
        if self.state == 'ROSTER':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            party = self.alive('player')
            if not party:
                self.state = self.menu_return
                return
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = self.menu_return
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.roster_sel = (self.roster_sel + (1 if key == pygame.K_DOWN else -1)) % len(party)
                sfx.play('select')
            elif key == pygame.K_i:
                self.detail_unit = party[self.roster_sel]
                self.detail_return = 'IDLE'
                self.state = 'DETAIL'
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self._roster_jump(party[self.roster_sel])
            elif click:
                for i, r in enumerate(self.roster_rects):
                    if r.collidepoint(event.pos):
                        self.roster_sel = i
                        self._roster_jump(party[i])
                        return
            return
        if self.state == 'GUIDE':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            n = len(guide.pages())
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'TITLE'
            elif key == pygame.K_LEFT:
                self.guide_page = (self.guide_page - 1) % n
                sfx.play('select')
            elif key == pygame.K_RIGHT:
                self.guide_page = (self.guide_page + 1) % n
                sfx.play('select')
            elif click:
                for i, r in enumerate(self.guide_tabs):
                    if r.collidepoint(event.pos):
                        self.guide_page = i
                        sfx.play('select')
            return
        if self.state == 'CINEMA':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE):
                self.cinema_next()
            elif key == pygame.K_ESCAPE:
                self.cinema_next(skip_all=True)
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
            elif key == pygame.K_s:
                self.open_support_convo(story.CODEX_ORDER[self.codex_sel])
            elif click:
                for i, r in enumerate(self.codex_rects):
                    if r.collidepoint(event.pos):
                        self.codex_sel = i
                        sfx.play('select')
            return
        if self.state == 'CONVO':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'CODEX'
            elif click or key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('select')
                self.convo_idx += 1
                if self.convo_idx >= len(self.convo_lines):
                    self.state = 'CODEX'
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
                if self._dialogue_full():
                    self.advance_dialogue()
                else:
                    self.dialogue_t = 999.0        # 先把整行文字显示完
            elif key == pygame.K_ESCAPE:
                self.advance_dialogue(skip=True)
            return
        if self.state == 'INTRO':
            if key == pygame.K_s:
                self.open_shop()                  # 章前商店
            elif click or key in (pygame.K_RETURN, pygame.K_SPACE):
                sfx.play('confirm')
                self.setup_chapter()
                pre = story.CHAPTER_DIALOGUE[self.chapter_idx]['pre']
                self.start_dialogue(pre, self.enter_battle)
            return
        if self.state == 'SHOP':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            n = len(SHOP_ITEMS)
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'INTRO'
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.shop_sel = (self.shop_sel + (1 if key == pygame.K_DOWN else -1)) % n
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.buy_item(SHOP_ITEMS[self.shop_sel])
            elif click:
                for i, r in enumerate(self.shop_rects):
                    if r.collidepoint(event.pos):
                        self.shop_sel = i
                        self.buy_item(SHOP_ITEMS[i])
                        return
            return
        if self.state == 'SHOP_PICK':
            party = self.roster
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            if key == pygame.K_ESCAPE or rclick or not party:
                sfx.play('cancel')
                self.shop_pending = None
                self.state = 'SHOP'
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.roster_sel = (self.roster_sel + (1 if key == pygame.K_DOWN else -1)) % len(party)
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.apply_seed(party[self.roster_sel])
            elif click:
                for i, r in enumerate(self.roster_rects):
                    if r.collidepoint(event.pos):
                        self.roster_sel = i
                        self.apply_seed(party[i])
                        return
            return
        if self.state == 'REWARD':
            n = len(self.reward_cards)
            if key in (pygame.K_LEFT, pygame.K_UP):
                self.reward_sel = (self.reward_sel - 1) % n
                sfx.play('select')
            elif key in (pygame.K_RIGHT, pygame.K_DOWN):
                self.reward_sel = (self.reward_sel + 1) % n
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.apply_tower_reward(self.reward_cards[self.reward_sel])
            elif click:
                for i, r in enumerate(self.reward_rects):
                    if r.collidepoint(event.pos):
                        self.apply_tower_reward(self.reward_cards[i])
                        return
            return
        if self.state == 'TOWER_META':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            n = len(settings.TOWER_UPGRADES)
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'TITLE'
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.tower_sel = (self.tower_sel + (1 if key == pygame.K_DOWN else -1)) % (n + 1)
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.tower_sel == n:
                    self.start_tower()
                else:
                    self.buy_tower_upgrade(settings.TOWER_UPGRADES[self.tower_sel])
            elif click:
                for i, r in enumerate(self.tower_rects):
                    if r.collidepoint(event.pos):
                        if i == n:
                            self.start_tower()
                        else:
                            self.tower_sel = i
                            self.buy_tower_upgrade(settings.TOWER_UPGRADES[i])
                        return
            return
        if self.state == 'TOWER_OVER':
            if click or key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.full_reset()
            return
        if self.state == 'MUSIC':
            rclick = event.type == pygame.MOUSEBUTTONDOWN and event.button == 3
            n = len(music.TRACK_LIST)
            if key == pygame.K_ESCAPE or rclick:
                sfx.play('cancel')
                self.state = 'TITLE'              # _update_music 自动切回标题曲
            elif key in (pygame.K_UP, pygame.K_DOWN):
                self.music_sel = (self.music_sel + (1 if key == pygame.K_DOWN else -1)) % n
                sfx.play('select')
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                music.director.update(music.TRACK_LIST[self.music_sel][0])
            elif click:
                for i, r in enumerate(self.music_rects):
                    if r.collidepoint(event.pos):
                        self.music_sel = i
                        music.director.update(music.TRACK_LIST[i][0])
                        return
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
            elif key == pygame.K_z and self.can_undo():
                self.do_undo()                     # 败北瞬间的后悔药
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
            if self.state == 'MAP_MENU':
                if key in (pygame.K_UP, pygame.K_DOWN):
                    d = 1 if key == pygame.K_DOWN else -1
                    for _ in range(len(self.menu_items)):       # 跳过禁用项
                        self.menu_sel = (self.menu_sel + d) % len(self.menu_items)
                        if self.menu_items[self.menu_sel][1]:
                            break
                    sfx.play('select')
                elif key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.menu_items[self.menu_sel][1]:
                        self._activate_map_menu(self.menu_items[self.menu_sel][0])
                elif key == pygame.K_ESCAPE:
                    sfx.play('cancel')
                    self.state = 'IDLE'
                return
            if key == pygame.K_e and self.state == 'IDLE':
                self.try_end_turn()
            elif key == pygame.K_z and self.state == 'IDLE':
                if self.can_undo():
                    self.do_undo()
                else:
                    self.show_banner('无法回溯', ui.COL_DIM)
            elif key == pygame.K_l and self.state in ('IDLE', 'MOVE'):
                self.open_roster(self.state if self.state == 'IDLE' else 'IDLE')
            elif key == pygame.K_o and self.state == 'IDLE':
                self.open_options('IDLE')
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
                if r.collidepoint(pos) and self.menu_items[i][1]:
                    self._activate_map_menu(self.menu_items[i][0])
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
                    elif label == '转职':
                        self.do_promote(self.selected)
                    elif label == '对话':
                        self.do_recruit(self.selected)
                    elif label in ('访问', '开启'):
                        self.do_event(self.selected)
                    elif label == '用药':
                        self.commit_undo()
                        healed = self.selected.use_potion()
                        self.add_float(f'+{healed}', (self.selected.x, self.selected.y),
                                       (120, 230, 120))
                        sfx.play('heal')
                        self.finish_unit()
                    else:
                        self.commit_undo()
                        self.finish_unit()
                    return
            return

        if cell is None:
            return

        if self.state == 'IDLE':
            u = self.unit_at(cell)
            if u and u.team == 'player' and not u.acted:
                self.select(u)
            elif u and u.team == 'enemy' and not self.enemy_hidden(u):
                self.toggle_threat(u)
            else:
                self.threat, self.threat_unit = set(), None
                self.open_map_menu(cell)         # 空地（或迷雾敌人）→ 地图菜单

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
                    self.fc = combat.forecast(
                        self.selected, t, dist,
                        self.grid.avoid(self.selected), self.grid.avoid(t),
                        att_sup=supports.support_bonus(self.selected, self.units),
                        def_sup=supports.support_bonus(t, self.units),
                        weather=self.weather_hit())
                    self.state = 'FORECAST'
                    return

        elif self.state == 'FORECAST':
            self.confirm_attack()

    def perform_heal(self, target):
        """修女治疗：立即结算，无预测无反击。"""
        self.commit_undo()
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
        self.commit_undo()
        if self.target.boss and not self.boss_quote_shown:
            self.boss_quote_shown = True
            att, dfd = self.selected, self.target
            self.start_dialogue(story.BOSS_QUOTES[self.chapter_idx],
                                lambda: self.start_combat(att, dfd, 'player'))
        else:
            self.start_combat(self.selected, self.target, 'player')

    # ---------- 更新 ----------

    def _update_music(self):
        """每帧驱动音乐总监：CINEMA 用 AI 交响乐，其余按状态/章节情绪切曲。"""
        if self.state == 'CINEMA':
            return                         # 由 enter/exit 钩子控制 mixer.music
        if self.state == 'MUSIC':
            return                         # 鉴赏室自行驱动总监，勿覆盖选曲
        music.director.update(
            music.track_for(self.state, self.chapter_idx,
                            enemy_phase=(self.state == 'ENEMY_TURN'),
                            tower=self.tower,
                            boss_engaged=(self.boss_quote_shown and not self.tower)))

    def update(self, dt):
        self.time += dt
        self._update_music()
        if self.state == 'CINEMA':
            self.cinema_t += dt
            if self.cinema_t >= story.CINEMA_SCENES[self.cinema_idx]['dur']:
                self.cinema_next()
            return
        if self.state == 'DIALOGUE':
            self.dialogue_t += dt      # 逐字显示计时
        if self.state in ('TITLE', 'INTRO', 'COMPLETE', 'PROLOGUE', 'DIALOGUE',
                          'CODEX', 'DETAIL', 'GUIDE', 'CONVO', 'NEWGAME', 'OPTIONS',
                          'SAVE_MENU', 'LOAD_MENU', 'ROSTER', 'SHOP', 'SHOP_PICK',
                          'REWARD', 'TOWER_META', 'TOWER_OVER', 'MUSIC'):
            return
        if (self.ff or config.get('skip_anim')) and self.state in ('ENEMY_TURN', 'COMBAT'):
            dt *= 3                    # 空格按住 / 选项「跳过战斗动画」：快进
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
                elif combat.is_effective(ev['actor'], target):
                    sfx.play('effective')           # 特效克制：金属斩鸣
                    self.add_float('特效!', (ev['actor'].x, ev['actor'].y), (255, 150, 90))
                else:
                    sfx.play('hit')
                self.add_float(str(ev['dmg']), (target.x, target.y), (255, 240, 120))
                self.hp_display[target] = max(0, self.hp_display.get(target, target.hp) - ev['dmg'])
        if self.event_t >= 1.0:
            self.combat_idx += 1
            self.event_t, self.event_spawned = 0.0, False

    # ---------- 绘制 ----------

    def _draw_terrain(self, surf, rows, wf):
        """FE 式分层渲染：森林/山/要塞画统一草地底再叠物件，余者照常；最后描浪沿。"""
        for y in range(GRID_H):
            for x in range(GRID_W):
                ch = rows[y][x]
                obj = assets.terrain_object(ch, x, y)
                base = 'P' if obj is not None else ch
                variant = 1 if (ch == 'B' and x > 0 and rows[y][x - 1] == 'B') else 0
                surf.blit(assets.terrain_sprite(base, wf, variant, cell=(x, y)),
                          (x * CELL, y * CELL))
                if obj is not None:
                    surf.blit(obj, (x * CELL, y * CELL))
        self._draw_shorelines(surf, rows)

    def _draw_shorelines(self, surf, rows):
        """水格朝向陆地的边描一道浅沙色浪沿，软化草水直角接缝。"""
        b = 5
        sand = (214, 198, 150)
        for y in range(GRID_H):
            for x in range(GRID_W):
                if rows[y][x] != 'W':
                    continue
                px, py = x * CELL, y * CELL
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H and rows[ny][nx] == 'W':
                        continue                    # 邻居也是水，无岸
                    band = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                    if dy == -1:   rect = (0, 0, CELL, b)
                    elif dy == 1:  rect = (0, CELL - b, CELL, b)
                    elif dx == -1: rect = (0, 0, b, CELL)
                    else:          rect = (CELL - b, 0, b, CELL)
                    pygame.draw.rect(band, (*sand, 120), rect)
                    surf.blit(band, (px, py))

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
                     ('读取存档', any(s['exists'] for s in self.slot_summaries.values())),
                     ('试炼之塔', True),
                     ('选项设置', True),
                     ('人物图鉴', True),
                     ('攻略看板', True),
                     ('音乐鉴赏', True)]
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
            self.title_rects = ui.draw_title_menu(surf, items, summary,
                                                  bg=assets.cinema('keyart_title'))
            r = self.records
            parts = []
            if r['clears']:
                parts.append(f'通关 {r["clears"]} 周目')
            if r['kills']:
                parts.append(f'击破 {r["kills"]}')
            if r.get('best_turns'):
                parts.append(f'最佳 {r["best_turns"]} 回合')
            sr = records.s_rank_count(r)
            if sr:
                parts.append(f'★ S评定 ×{sr}')
            if r.get('best_floor'):
                parts.append(f'试炼 第{r["best_floor"]}层')
            if parts:
                ui.draw_records_line(surf, ' ｜ '.join(parts))
            return
        if self.state == 'INTRO':
            rows = self.chapter['map']      # 本章地图做暗化背景
            wf = int(self.time * 1.6) % 2
            self._draw_terrain(surf, rows, wf)
            pygame.draw.rect(surf, (16, 14, 24), (0, GRID_H * CELL, GRID_W * CELL, 100))
            ui.draw_intro(surf, self.chapter_idx, self.chapter, backdrop=True,
                          gold=self.gold,
                          best_grade=self.records.get('grades', {}).get(str(self.chapter_idx)))
            return
        if self.state == 'SHOP':
            self.shop_rects = ui.draw_shop(surf, SHOP_ITEMS, self.gold,
                                           self.shop_sel, self.seals)
            return
        if self.state == 'SHOP_PICK':
            surf.fill((16, 14, 24))
            item = self.shop_pending or {}
            ui.draw_text_center(surf, f'选择强化对象 — {item.get("name", "")}', 22, 18)
            self.roster_rects = ui.draw_roster(surf, self.roster, self.roster_sel)
            return
        if self.state == 'TOWER_META':
            self.tower_rects = ui.draw_tower_meta(
                surf, self.records, settings.TOWER_UPGRADES,
                settings.tower_upgrade_cost, self.tower_sel,
                bg=assets.cinema('keyart_title'))
            return
        if self.state == 'TOWER_OVER':
            ui.draw_tower_over(surf, self.tower_over_floor, self.records)
            return
        if self.state == 'MUSIC':
            self.music_rects = ui.draw_music_room(
                surf, music.TRACK_LIST, self.music_sel, music.current(),
                bg=assets.cinema('keyart_title'))
            return
        if self.state == 'COMPLETE':
            ui.draw_complete(surf, self.roster, story.FATES)
            return
        if self.state == 'CINEMA':
            sc = story.CINEMA_SCENES[self.cinema_idx]
            p = min(1.0, self.cinema_t / sc['dur'])
            ui.draw_cinema(surf, assets.cinema(sc['img']), sc.get('motion'),
                           p, sc['lines'], sc.get('title'), self.time,
                           weather=sc.get('weather'))
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
        if self.state == 'GUIDE':
            self.guide_tabs = ui.draw_guide(surf, guide.pages(), self.guide_page)
            return
        if self.state == 'CONVO':
            ui.draw_convo(surf, self.convo_title, self.convo_lines, self.convo_idx,
                          assets.portrait, story.NAME_TO_CLS)
            return
        if self.state == 'NEWGAME':
            self.newgame_rects = ui.draw_newgame(
                surf, self.newgame_diff, self.newgame_mode, self.newgame_sel,
                bg=assets.cinema('keyart_title'))
            return
        if self.state == 'OPTIONS':
            self.options_rects = ui.draw_options(surf, self.options_sel)
            return
        if self.state in ('SAVE_MENU', 'LOAD_MENU'):
            slots = self.slot_list()
            summaries = [self.slot_summaries[s] for s in slots]
            title = '保存进度' if self.slotmenu_mode == 'save' else '读取存档'
            self.slot_rects = ui.draw_slot_menu(
                surf, title, slots, summaries, self.slot_sel, self.slotmenu_mode)
            return

        water_frame = int(self.time * 1.6) % 2
        rows = self.grid.rows
        self._draw_terrain(surf, rows, water_frame)
        ev_vis = self.visible_set()             # 村庄/宝箱图标（迷雾外不画）
        for e in self.events:
            if e['done'] or (ev_vis is not None and e['pos'] not in ev_vis):
                continue
            ex, ey = e['pos']
            if e['kind'] == 'chest':
                ui.draw_chest(surf, ex * CELL, ey * CELL)
            else:
                ui.draw_village(surf, ex * CELL, ey * CELL)

        if self.threat_all and self.state in ('IDLE', 'MOVE'):
            self._danger_tiles = self.all_threat_tiles()
            ui.draw_tiles(surf, self._danger_tiles, ui.ATTACK_TILE)
        else:
            self._danger_tiles = set()
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
        fog_vis = self.visible_set()           # 迷雾可见格（None=无迷雾）
        for u in self.units:
            if not u.alive:
                continue
            if fog_vis is not None and u.team == 'enemy' and (u.x, u.y) not in fog_vis:
                continue                        # 迷雾中的敌人不可见
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
            if u.team == 'player' and supports.has_support(u, self.units):
                ui.draw_support_mark(surf, px, py)  # 羁绊加成生效
            if (u.team == 'player' and self._danger_tiles
                    and (u.x, u.y) in self._danger_tiles):
                ui.draw_danger_mark(surf, px, py)   # 处于敌方威胁中

        for d in self.dying:               # 死亡淡出
            u = d['unit']
            spr = assets.unit_sprite(u.cls, 0).copy()
            spr.set_alpha(max(0, int(200 * (1 - d['t']))))
            surf.blit(spr, (u.x * CELL, u.y * CELL))
        if fog_vis is not None:            # 迷雾：未照亮格变暗
            fog = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            fog.fill((8, 12, 22, 168))
            for fy in range(GRID_H):
                for fx in range(GRID_W):
                    if (fx, fy) not in fog_vis:
                        surf.blit(fog, (fx * CELL, fy * CELL))
        if self.flash_t > 0:               # 必杀白闪
            veil = pygame.Surface((GRID_W * CELL, GRID_H * CELL), pygame.SRCALPHA)
            veil.fill((255, 255, 255, 80))
            surf.blit(veil, (0, 0))
        amb = self.chapter.get('ambient')
        if amb:                            # 章节氛围：色调 + 天气
            if amb.get('tint'):
                tint = pygame.Surface((GRID_W * CELL, GRID_H * CELL), pygame.SRCALPHA)
                tint.fill(tuple(amb['tint']))
                surf.blit(tint, (0, 0))
            if amb.get('weather'):
                ui.draw_weather(surf, amb['weather'], self.time)

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
            reveal = int(self.dialogue_t * config.text_cps())
            shown = text if reveal >= len(text) else text[:reveal]   # 逐字显示
            pic = None
            if side is not None:
                pic = (assets.portrait(speaker)
                       or assets.unit_sprite(story.NAME_TO_CLS[speaker]))
            ui.draw_dialogue(surf, speaker, side, shown, pic)
            return

        hover_unit = self.unit_at(self.hover) if self.hover else None
        info_unit = hover_unit or (self.selected if self.state != 'IDLE' else None)
        terrain_ch = (self.grid.rows[self.hover[1]][self.hover[0]]
                      if self.hover and self.grid.in_bounds(*self.hover) else None)
        ui.draw_info(surf, info_unit, terrain_ch)
        ui.draw_help(surf)
        if self.tower:
            obj = f'歼灭全部敌人　·　敌 {len(self.alive("enemy"))}'
            if self.tower_mut:
                obj += f'　·　词条：{self.tower_mut["name"]}'
            ui.draw_objective(surf, self.turn, obj, tag=f'试炼 第{self.floor}层')
        else:
            obj = self.chapter['objective']
            if self.chapter['win'] == 'defend':
                remain = max(0, self.chapter['hold_turns'] - self.turn + 1)
                obj = f'{obj}（剩 {remain} 回合）'
            obj += f'　·　敌 {len(self.alive("enemy"))}'
            obj += f'　·　军资 {self.gold}'
            if self.seals > 0:
                obj += f'　·　转职证 ×{self.seals}'
            wh = self.weather_hit()
            if wh:
                obj += f'　·　天气 命中-{wh}'
            if self.fog_radius():
                obj += '　·　迷雾'
            tag = DIFFICULTY[self.difficulty]['label']
            if self.permadeath:
                tag += '·经典'
            ui.draw_objective(surf, self.turn, obj, tag=tag)
        ui.draw_action_hint(surf, self.hint_text())   # 顶部即时操作提示

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
        elif self.state == 'ROSTER':
            self.roster_rects = ui.draw_roster(surf, self.alive('player'), self.roster_sel)
        elif self.state == 'REWARD':
            self.reward_rects = ui.draw_reward(surf, self.reward_cards,
                                               self.reward_sel, self.floor)

        if self.ff and self.state in ('ENEMY_TURN', 'COMBAT'):
            ui.draw_ff_indicator(surf)
        if self.banner is not None:
            ui.draw_banner(surf, self.banner['text'], self.banner['t'], self.banner['color'])
        if self.state == 'CLEAR':
            ui.draw_clear(surf, self.chapter_idx, self.chapter['title'], self.turn,
                          grade=self.last_grade, deaths=self.last_clear_deaths,
                          t=self.time)
        elif self.state == 'END':
            ui.draw_defeat(surf, self.can_undo())
