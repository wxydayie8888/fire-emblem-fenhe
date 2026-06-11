# 火焰纹章·芬河战记 — 存档 / 剧情 / 图鉴 完整化计划

## Context

游戏目前已是可通关的三章战役（pygame，逻辑/渲染分层，38 个 pytest），但缺三块「完整游戏」要素：关机即丢进度、角色没有故事、世界观只有每章三行简介。用户确认的方案：**章节自动存档**（标题菜单加「继续游戏」）、**序章旁白 + 火纹式章节对话**（精灵头像+名字+台词，含 Boss 叫阵）、**人物图鉴 + 战斗内 I 键详情**。

项目路径：`/Users/wangxingyu/claude/火焰纹章`（本会话所建，结构全部已知）。

## 关键设计决策（已由 Plan 代理对照代码验证）

1. **`start_chapter` 拆分为 `setup_chapter(retry)` + `enter_battle()`**：先布阵→章前对话在真实战场上播放→再弹回合横幅开战。`start_chapter` 保留为 wrapper（END 重试路径不变，天然不重播章前对话）。
2. **菲尔入队幂等化**：`setup_chapter` 的 join 改为按 name 查重再 append。两种合法存档（第1章通关档 roster=4 / 第2章开局档 roster=5）加载后都收敛到正确的 5 人，无需 from_save 特判。
3. **通关对话先于 CLEAR**：`continue_after_combat` 判定 `_chapter_won()` 后先播 post 对话（战场背景），回调 `chapter_clear()`。
4. **Boss 叫阵**：`confirm_attack()` 里 `target.boss and not self.boss_quote_shown` → 播叫阵对话，回调进 `start_combat`。标志在 `setup_chapter` 重置（败北重试会重播一次，火纹惯例）。
5. **存档时机**：写档 2 处——`setup_chapter` 非 retry（snapshot 之后）、`chapter_clear` 非末章（idx+1）；删档 2 处——末章 clear、进 COMPLETE 兜底。原子写（tmp + `os.replace`）。损坏/版本不符 → load 返回 None →「继续游戏」灰显，不崩溃。
6. **图鉴数据源**：`CLASSES` 基础值 + 成长率（与进度无关，随时可看）；敌方 growth 为空显示「—」。

## 存档 Schema（save.json，gitignore）

```json
{"version": 1, "chapter_idx": 1,
 "roster": [{"name":"罗伊","cls":"lord","level":3,"exp":40,
             "max_hp":23,"pow":8,"skl":9,"spd":11,"dfn":6}, ...]}
```
校验：version 匹配、chapter_idx 在界内、roster[0].cls=='lord'、全字段非负 int、cls∈CLASSES、name 不重复且属于合法名单。hp/potions/坐标不存（每章开局重置）。

## 状态机增量

```
TITLE(菜单: 新游戏/继续游戏/人物图鉴)
  ├新游戏→ PROLOGUE(旁白页) → INTRO(ch0)
  ├继续→ 载档建roster+snapshot → INTRO(存档章)
  └图鉴→ CODEX ←ESC→ TITLE
INTRO →点击→ setup_chapter() → DIALOGUE(pre,战场背景) → enter_battle()→IDLE
FORECAST →确认且Boss首次→ DIALOGUE(叫阵) → COMBAT
胜利 → DIALOGUE(post) → CLEAR → next_chapter（末章→ PROLOGUE(尾声页) → COMPLETE）
IDLE/MOVE →I键(悬停/选中单位)→ DETAIL →ESC/I→ 原状态
```
`update()` 早返回守卫追加 PROLOGUE/DIALOGUE/CODEX/DETAIL；DIALOGUE 的 draw 不早返回（画地图+单位后盖对话框）。

## 文件改动

| 文件 | 改动 |
|------|------|
| `unit.py` | `SAVE_FIELDS` + `to_dict()/from_dict()`（仅可变属性；from_dict 后 hp=max_hp） |
| `save.py` 新建 | `save_game/load_game/delete_save/_validate`，纯逻辑零 pygame |
| `story.py` 新建 | PROLOGUE/EPILOGUE 旁白页、CHAPTER_DIALOGUE{idx:{pre,post}}、BOSS_QUOTES、BIOS（5 我方+3 Boss）、NAME_TO_CLS、CODEX_ORDER；台词条目 `(speaker, side, text)`，旁白居中无头像。**全部中文文案由我撰写**（世界观：芬河边境、黑铁牙盗贼团、各角色生平与性格） |
| `game.py` | setup/enter 拆分、join 幂等、四个新状态与播放器（start_dialogue/advance_dialogue/start_pages）、continue_game()、存档钩子、confirm_attack 叫阵、K_i 详情、TITLE 菜单 rects |
| `ui.py` | `draw_title_menu`(返回 rects+存档摘要)、`draw_prologue`、`draw_dialogue`(2x 精灵头像左右停靠)、`draw_codex`(左名单右详情+成长率条)、`draw_unit_detail`；复用 font/draw_menu rects 模式 |
| `.gitignore` | `save.json` |
| `tests/` | test_save.py（往返/坏档/版本/缺字段/delete 幂等）、test_story.py（三章 pre/post 齐全、speaker 可解析、BIOS 覆盖 CODEX_ORDER）、test_unit.py 追加序列化用例 |
| `README.md` | 操作说明（I 键、标题菜单）、存档说明 |

不改：`combat/grid/ai/assets/sfx/main`（对话音效复用 select/confirm）。

## 任务拆分（逐个提交，纯逻辑 TDD）

1. **T1** unit 序列化 + 测试
2. **T2** save.py + 测试 + gitignore
3. **T3** story.py 全部正式文案 + 结构测试
4. **T4** game 重构（setup/enter 拆分 + join 幂等，行为不变，38 测试全过）
5. **T5** 对话系统（播放器 + draw_dialogue/draw_prologue + 四个集成点）
6. **T6** 存档集成（钩子 + continue_game + 标题菜单）
7. **T7** 图鉴 CODEX + 战斗内 DETAIL
8. **T8** 收尾验收 + README + 重启游戏窗口

## 验证

- `pytest tests/`（预计 ~50 用例）全过
- headless 冒烟脚本：新游戏→序章→章前对话→Boss 叫阵→通关对话→CLEAR 时 save.json 内容断言→重建 Game→继续游戏直达第 2 章且菲尔不重复→图鉴/详情截图→通关后档被删
- 手写坏 save.json → 标题「继续游戏」灰显不崩溃
- 关键画面截图人工核对（对话框、图鉴、标题菜单）
- 最后真窗口启动试玩
