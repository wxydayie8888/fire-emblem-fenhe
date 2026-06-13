"""攻略看板内容：把全部玩法系统整理成分页图鉴。纯数据，零 pygame 依赖。

pages() 返回 [(标题, [段落...])]，段落为 (类型, 内容)：
  ('h', 文字)       小标题
  ('p', 文字)       正文行
  ('kv', (左, 右))  键值两列（操作/数据）
  ('gap',)          空行
内容部分从 settings 动态生成（职业/转职/技能），保证与数值同步。
"""
from settings import CLASSES, PROMOTIONS, WEAPONS, PROMOTE_LEVEL


def _controls():
    rows = [
        ('左键', '选择单位 / 确认移动 / 选择目标 / 确认攻击'),
        ('左键点敌人', '显示该敌人的威胁范围（再点取消）'),
        ('左键点空地', '地图菜单：结束回合 / 保存进度 / 时光回溯'),
        ('右键 · ESC', '取消，逐级退回；剧情中整段跳过'),
        ('Tab', '循环选中下一个未行动单位'),
        ('D', '开关全体敌人危险范围（受威胁单位头顶红「!」）'),
        ('Z', '时光回溯：撤销上一步（每战 10 次，败北亦可用）'),
        ('空格（按住）', '战斗 / 敌方回合 3 倍速快进'),
        ('I', '查看单位详情（属性 + 职业技 + 生平）'),
        ('M', '开关背景音乐'),
        ('E', '结束我方回合（有未行动单位时按两次确认）'),
        ('R', '败北后重试本章 / 通关画面返回标题'),
    ]
    return ('操作 · 键位', [('kv', r) for r in rows])


def _combat():
    return ('战斗规则', [
        ('h', '武器三角'),
        ('p', '剑 ▶ 斧 ▶ 枪 ▶ 剑（循环克制）。克制方 +1 伤害、+15 命中；被克反之。'),
        ('p', '弓与魔法不参与三角。'),
        ('gap',),
        ('h', '特效武器（克制兵种）'),
        ('p', '弓 → 飞行（天马/飞龙）；光魔 / 罗伊圣剑 → 邪龙。'),
        ('p', '特效时攻击力×3 再减防御，常能一击秒杀——预测框标「★ 特效克制」。'),
        ('gap',),
        ('h', '命中 / 伤害 / 必杀'),
        ('p', '命中 = 武器命中 + 技巧×2 + 三角 − (对方速度×2 + 地形回避)'),
        ('p', '伤害 = 力量 + 武器威力 + 三角 − 对方防御'),
        ('p', '必杀率 = 武器必杀 + 技巧÷2 + 职业技；必杀造成 3 倍伤害'),
        ('p', '追击：速度比对方高 4 点及以上，一回合攻击两次'),
        ('gap',),
        ('h', '射程'),
        ('p', '近战 1 格；弓只能打 2 格（贴脸打不到、也不被近战反击）；魔法 1–2 格'),
        ('gap',),
        ('h', '地形'),
        ('p', '森林 +20 回避/消耗2；山地 +30 回避/消耗3（骑兵不可入）；'),
        ('p', '要塞 +20 回避且每回合回 10% HP；城门 +10；水域 / 城墙不可通行'),
        ('p', '飞行单位无视全部地形消耗，但也不享受地形回避'),
    ])


def _promotion():
    paras = [('h', f'转职（Lv{PROMOTE_LEVEL}+ 且持有转职证）'),
             ('p', '每章通关获得 1 枚转职证。行动菜单「转职」进阶为高级职，'),
             ('p', '属性大幅跃升、成长率提高、解锁职业技。'),
             ('gap',),
             ('h', '转职树')]
    for base, (adv, _) in PROMOTIONS.items():
        bn, an = CLASSES[base]['name'], CLASSES[adv]['name']
        sk = CLASSES[adv].get('skill', {}).get('name', '')
        paras.append(('kv', (f'{bn} → {an}', f'职业技：{sk}' if sk else '')))
    return ('职业 · 转职', paras)


def _skills():
    paras = [('h', '职业技（转职后获得，自动生效）')]
    seen = set()
    for cls, c in CLASSES.items():
        sk = c.get('skill')
        if not sk or sk['name'] in seen:
            continue
        seen.add(sk['name'])
        desc = {
            '鼓舞': '相邻友军 +命中 +回避（光环）',
            '坚韧': '命中 +12，防御 +1',
            '狙击': '必杀 +15',
            '魔导': '魔法伤害 +2',
            '必杀': '必杀 +20',
            '祈祷': '治疗量 +5',
            '疾风': '回避 +15',
            '大盾': '50% 几率受到的伤害减半',
        }.get(sk['name'], '')
        paras.append(('kv', (f'{sk["name"]}（{c["name"]}）', desc)))
    return ('职业技', paras)


def _supports():
    import supports as S
    paras = [('h', '羁绊 · 支援'),
             ('p', '相邻同队友军互相提供 +命中 +回避 +必杀（头顶金「羁」标记）。'),
             ('p', f'普通相邻：+{S.GENERIC["hit"]} 命中 / +{S.GENERIC["avoid"]} 回避。'),
             ('p', f'剧情 CP 相邻：额外 +{S.PAIR["hit"]} 命中 / +{S.PAIR["avoid"]} 回避 / +{S.PAIR["crit"]} 必杀。'),
             ('p', '相邻「大将」额外提供鼓舞光环。各项有封顶。'),
             ('gap',),
             ('h', '剧情 CP')]
    for pair, rel in S.SUPPORT_PAIRS.items():
        a, b = sorted(pair)
        paras.append(('kv', (f'{a} × {b}', rel)))
    return ('羁绊', paras)


def _mechanics():
    return ('特殊机制', [
        ('h', '时光回溯'),
        ('p', '每战 10 次。Z 键或地图菜单触发，精确回到上一次我方行动前，'),
        ('p', '可撤销整个敌方回合；败北瞬间也能反悔。'),
        ('gap',),
        ('h', '胜利条件'),
        ('kv', ('歼灭', '消灭全部敌人')),
        ('kv', ('击破敌将', '击败 Boss 即可，无需清场')),
        ('kv', ('占领', '主角抵达指定城门/点位即胜')),
        ('kv', ('坚守', '撑过指定回合数即胜')),
        ('gap',),
        ('h', '敌方增援'),
        ('p', '部分章节敌方按回合从地图边缘涌入，有「敌方增援！」横幅预警。'),
        ('gap',),
        ('h', '存档与成长'),
        ('p', '每章自动存档；空地菜单可战斗中挂起存档。等级经验跨章保留，'),
        ('p', '休闲模式：非主角阵亡本章退场、下章回归；主角阵亡即败北（可回溯/重试）。'),
    ])


def _lore():
    import story
    paras = []
    for title, lines in story.WORLD_LORE:
        paras.append(('h', title))
        for line in lines:
            paras.append(('p', line))
        paras.append(('gap',))
    return ('世界观 · 史话', paras)


def pages():
    return [_controls(), _combat(), _promotion(), _skills(), _supports(),
            _mechanics(), _lore()]
