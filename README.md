# 火焰纹章 · 芬河战记

用 Python + pygame 实现的火焰纹章（GBA 风格）回合制战棋——**完整三章战役**：
标题画面、剧情过场、跨章节成长、新同伴加入、Boss 战与通关结算一应俱全。
完整实现武器克制三角、地形效果、经验升级、伤药道具、守备 AI 与程序化 8-bit 音效。

| 标题画面 | 战斗（移动/攻击范围） | 第三章·要塞攻坚 |
|---|---|---|
| ![标题](docs/images/screenshot-title.png) | ![移动](docs/images/screenshot-move.png) | ![城堡](docs/images/screenshot-castle.png) |

| 章节过场 | 战斗预测 | 升级结算 |
|---|---|---|
| ![过场](docs/images/screenshot-intro.png) | ![预测](docs/images/screenshot-forecast.png) | ![升级](docs/images/screenshot-levelup.png) |

## 安装与启动

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tools/fetch_assets.py   # 下载 DawnLike 素材（约 1MB，仅需一次）
.venv/bin/python main.py
```

## 三章战役

| 章 | 标题 | 看点 | 胜利条件 |
|----|------|------|---------|
| 一 | 渡河遭遇 | 双桥渡河，利用地形卡口 | 歼灭全部敌人 |
| 二 | 林间伏击 | 森林伏兵（守备 AI），剑士菲尔加入 | 歼灭全部敌人 |
| 三 | 黑铁要塞 | 攻城战：城门突破或弓魔隔墙压制 | 击破敌将巴尔克 |

- 我方等级与经验**跨章节保留**；每章开始 HP 回满、伤药补满
- 休闲模式：非主角阵亡本章退场、下章回归；主角阵亡即败北
- 败北后按 **R** 重试本章（回滚到本章开局，之前章节的成长保留）

## 操作

| 输入 | 作用 |
|------|------|
| 左键 | 选择单位 / 确认移动 / 选择目标 / 确认攻击 |
| 左键点敌人（待机时） | 显示/隐藏该敌人的威胁范围 |
| 右键 / ESC | 取消，逐级退回上一步 |
| E | 提前结束我方回合 |
| R | 败北后重试本章；通关画面返回标题 |
| 鼠标悬停 | 底部信息栏查看单位属性与地形效果 |

## 规则速查

- **武器三角**：剑 ▶ 斧 ▶ 枪 ▶ 剑（克制方 +1 伤害 +15 命中，被克反之）；弓与魔法不参与
- **射程**：近战 1 格；弓只能打 2 格（贴脸打不到，但也不被近战反击）；魔法 1–2 格
- **追击**：速度比对方高 4 点及以上时攻击两次
- **必杀**：必杀率 = 武器必杀 + 技巧/2，造成 3 倍伤害
- **地形**：森林 +20 回避（移动消耗 2）；山地 +30 回避（消耗 3，骑兵不可入）；
  要塞 +20 回避且每回合恢复 20% HP；城门 +10 回避；水域/城墙不可通行
- **伤药**：每人每章 3 瓶，行动菜单「用药」恢复 10 HP（消耗该回合行动）
- **经验**：命中 +10、击杀 +30、击杀 Boss +60；满 100 升级，属性按职业成长率随机提升
- **守备 AI**：部分敌人原地驻守，进入其攻击圈或被攻击后会被激活

## 我方阵容

| 单位 | 职业 | 武器 | 定位 |
|------|------|------|------|
| 罗伊 | 领主 | 剑 | 均衡主力，不能阵亡 |
| 兰斯 | 重骑士 | 枪 | 移动 7 的先锋，注意山地不可入 |
| 丽贝卡 | 弓兵 | 弓 | 2 格狙击，无惧近战反击 |
| 莉莉娜 | 魔道士 | 魔法 | 高伤脆皮，1–2 格灵活输出 |
| 菲尔 | 剑士 | 剑 | 第二章加入，高速高必杀 |

## 开发

```bash
.venv/bin/python -m pytest tests/ -v   # 38 个纯逻辑单元测试
.venv/bin/python assets.py             # 生成精灵映射预览图
.venv/bin/python sfx.py                # 试听全部程序化音效
```

代码结构：`settings/unit/combat/grid/ai` 为零 pygame 依赖的纯逻辑层（pytest 覆盖），
`assets/ui/game/sfx/main` 为渲染交互层。三章地图与全部数值集中在 `settings.py`，
改平衡、加关卡只需改数据。设计文档见 `docs/superpowers/specs/`。

## 素材与许可

- 美术：[DawnLike v1.81](https://opengameart.org/content/dawnlike-16x16-universal-rogue-like-tileset-v181)
  （作者 DragonDePlatino，调色板 DawnBringer，CC-BY 4.0），详见 `CREDITS.txt`
- 音效：运行时 numpy 程序化合成，无外部音频文件
