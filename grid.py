"""地图、地形与范围计算（Dijkstra 移动范围 / 曼哈顿攻击范围）。零 pygame 依赖。"""
import heapq

import settings
from settings import TERRAIN


class Grid:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else settings.MAP
        self.h = len(self.rows)
        self.w = len(self.rows[0])

    def terrain(self, x, y):
        return TERRAIN[self.rows[y][x]]

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def cost(self, x, y, unit):
        """unit 进入 (x,y) 的移动消耗；None=不可进入"""
        t = self.terrain(x, y)
        if t['cost'] is None:
            return None
        if unit.mounted and t.get('no_mount'):
            return None
        return t['cost']


def neighbors(x, y):
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def move_range(unit, grid, units):
    """Dijkstra 可达范围。返回 {格子: 已耗移动力}。
    敌方单位阻挡通行；任何存活单位占据的格子不能作为落点（自身除外）。"""
    occupied = {(u.x, u.y): u for u in units if u.alive}
    start = (unit.x, unit.y)
    dist = {start: 0}
    pq = [(0, start)]
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if d > dist[(x, y)]:
            continue
        for nx, ny in neighbors(x, y):
            if not grid.in_bounds(nx, ny):
                continue
            c = grid.cost(nx, ny, unit)
            if c is None:
                continue
            blocker = occupied.get((nx, ny))
            if blocker is not None and blocker.team != unit.team:
                continue                     # 敌人挡路，不可穿过
            nd = d + c
            if nd <= unit.mov and nd < dist.get((nx, ny), float('inf')):
                dist[(nx, ny)] = nd
                heapq.heappush(pq, (nd, (nx, ny)))
    return {p: d for p, d in dist.items() if p == start or p not in occupied}


def attack_tiles(pos, weapon_range, grid):
    """从 pos 出发、射程 (lo,hi) 内的所有格子（曼哈顿距离）。"""
    lo, hi = weapon_range
    out = set()
    for dx in range(-hi, hi + 1):
        for dy in range(-hi, hi + 1):
            d = abs(dx) + abs(dy)
            if lo <= d <= hi:
                x, y = pos[0] + dx, pos[1] + dy
                if grid.in_bounds(x, y):
                    out.add((x, y))
    return out


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
