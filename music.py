"""程序化作曲引擎：用 numpy 多声部合成火焰纹章风格的循环配乐。

设计与 sfx.py 一脉相承——零外部音频文件，缺 numpy / 音频设备时静音降级。
对外接口：
  init()                 启动时调用一次（须在 pygame.mixer 已初始化后，即 sfx.init() 之后）
  set_enabled(on)        总开关（M 键静音）
  director.update(key)   音乐总监：按曲目 key 交叉淡入，重复同 key 不打断

音色用加法合成（多谐波 + 轻微离调合唱 + 颤音）+ ADSR 包络近似管弦乐；
循环用「释放尾音环绕回开头」实现无缝。曲目定义为纯数据（见 SONGS），易于增删。
"""
import math

SAMPLE_RATE = 44100
CHANNELS = 2
_enabled = False
_user_on = True
_music_vol = 1.0          # 全局音乐音量 0..1（由 config 设置）
_BASE_VOL = 0.55          # 程序化曲目基准音量
_CINEMA_VOL = 0.6         # 开场交响乐基准音量
_sounds = {}

# ---------- 乐理工具 ----------

_NOTE = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def _midi(name):
    """'C4' / 'F#3' / 'Bb4' -> MIDI 号（C4=60）。"""
    letter = name[0].upper()
    i = 1
    semi = _NOTE[letter]
    if i < len(name) and name[i] in '#b':
        semi += 1 if name[i] == '#' else -1
        i += 1
    octave = int(name[i:])
    return 12 * (octave + 1) + semi


def _mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# ---------- 音色表 ----------
# harm: 各谐波相对振幅；detune: 合唱离调量；vib: (频率Hz, 深度)；
# adsr: (attack秒, decay秒, sustain电平, release秒)；gain: 音色总增益
TIMBRES = {
    'strings': {'harm': [1, 0.5, 0.34, 0.2, 0.1, 0.05], 'detune': 0.007,
                'vib': (5.0, 0.004), 'adsr': (0.10, 0.10, 0.82, 0.22), 'gain': 0.9},
    'brass':   {'harm': [1, 0.7, 0.52, 0.38, 0.26, 0.16, 0.1], 'detune': 0.004,
                'vib': (5.5, 0.005), 'adsr': (0.045, 0.08, 0.8, 0.12), 'gain': 0.85},
    'flute':   {'harm': [1, 0.22, 0.1, 0.04], 'detune': 0.0,
                'vib': (5.2, 0.007), 'adsr': (0.07, 0.05, 0.9, 0.14), 'gain': 0.8},
    'bass':    {'harm': [1, 0.45, 0.18, 0.08], 'detune': 0.0,
                'vib': (0, 0), 'adsr': (0.012, 0.12, 0.62, 0.09), 'gain': 1.0},
    'pluck':   {'harm': [1, 0.6, 0.42, 0.28, 0.16], 'detune': 0.002,
                'vib': (0, 0), 'adsr': (0.005, 0.22, 0.0, 0.05), 'gain': 0.8},
    'bell':    {'harm': [1, 0, 0.55, 0, 0.32, 0, 0.18], 'detune': 0.0,
                'vib': (0, 0), 'adsr': (0.004, 0.7, 0.0, 0.4), 'gain': 0.7},
    'timpani': {'harm': [1, 0.3], 'detune': 0.0,
                'vib': (0, 0), 'adsr': (0.004, 0.28, 0.0, 0.06), 'gain': 1.1},
}


def _render_note(np, midi, dur, instr):
    """合成单音 -> float 数组（长度含释放尾音）。"""
    tb = TIMBRES[instr]
    a, d, s, r = tb['adsr']
    total = dur + r
    n = int(SAMPLE_RATE * total)
    t = np.arange(n) / SAMPLE_RATE
    f = _mtof(midi)
    vr, vd = tb['vib']
    if vr > 0:
        inst_f = f * (1 + vd * np.sin(2 * math.pi * vr * t))
        phase = 2 * math.pi * np.cumsum(inst_f) / SAMPLE_RATE
    else:
        phase = 2 * math.pi * f * t
    wave = np.zeros(n)
    for k, amp in enumerate(tb['harm'], start=1):
        if amp:
            wave += amp * np.sin(k * phase)
    if tb['detune']:                       # 合唱：叠一层离调拷贝
        wave += 0.5 * np.sin(phase * (1 + tb['detune']))
    # ADSR 包络
    env = np.zeros(n)
    na, nd, nr = int(a * SAMPLE_RATE), int(d * SAMPLE_RATE), int(r * SAMPLE_RATE)
    na = max(1, min(na, n)); nd = max(1, nd); nr = max(1, nr)
    pos = 0
    env[pos:pos + na] = np.linspace(0, 1, na); pos += na
    if pos < n:
        seg = min(nd, n - pos)
        env[pos:pos + seg] = np.linspace(1, s, seg); pos += seg
    sus_end = max(pos, n - nr)
    if sus_end > pos:
        env[pos:sus_end] = s
    pos = sus_end
    if pos < n:
        env[pos:] = np.linspace(env[pos - 1] if pos > 0 else s, 0, n - pos)
    return wave * env * tb['gain']


def _render_track(np, pattern, instr, vol, loop_len, tempo):
    """把 [(token, beats)] 渲染到 loop_len 长度，释放尾音环绕回开头实现无缝循环。"""
    spb = 60.0 / tempo                      # 每拍秒数
    tail = int(SAMPLE_RATE * 0.6)
    buf = np.zeros(loop_len + tail)
    cursor = 0
    for token, beats in pattern:
        dur = beats * spb
        nsamp = int(beats * spb * SAMPLE_RATE)
        if token != 'R':
            notes = token.split('+')
            mix = None
            for nm in notes:
                seg = _render_note(np, _midi(nm), dur, instr)
                mix = seg if mix is None else mix[:len(seg)] + seg[:len(mix)]
            if len(notes) > 1:
                mix = mix / math.sqrt(len(notes))
            end = cursor + len(mix)
            if end <= len(buf):
                buf[cursor:end] += mix
            else:                            # 超出尾缓冲：截断
                buf[cursor:] += mix[:len(buf) - cursor]
        cursor += nsamp
    # 环绕：尾音回卷到开头
    buf[:tail] += buf[loop_len:loop_len + tail]
    return buf[:loop_len] * vol


def _build_song(np, song):
    tempo = song['tempo']
    loop_len = int(song['beats'] * (60.0 / tempo) * SAMPLE_RATE)
    mix = np.zeros(loop_len)
    for instr, vol, pattern in song['tracks']:
        mix += _render_track(np, pattern, instr, vol, loop_len, tempo)
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak * 0.86 * song.get('master', 1.0)
    # 防循环接缝爆音：首尾 3ms 微淡
    dc = int(SAMPLE_RATE * 0.003)
    mix[:dc] *= np.linspace(0, 1, dc)
    mix[-dc:] *= np.linspace(1, 0, dc)
    return mix


# ---------- 曲库（火焰纹章风格）----------
# 每曲: tempo(BPM), beats(循环总拍数), master(总音量), tracks=[(音色, 音量, 模式)]
# 模式: [(音符token, 拍数)]；token 用 '+' 表示和弦，'R' 表示休止。

def _songs():
    return {
        # 标题曲：C大调，恢弘充满希望（I–V–vi–IV 进行）
        'title': {'tempo': 100, 'beats': 32, 'master': 0.95, 'tracks': [
            ('strings', 0.55, [('C3+E3+G3', 4), ('G2+D3+G3', 4), ('A2+E3+A3', 4),
                               ('F2+C3+F3', 4), ('C3+E3+G3', 4), ('G2+D3+G3', 4),
                               ('F2+C3+F3', 4), ('G2+D3+G3', 4)]),
            ('brass', 0.5, [('G4', 1), ('A4', 1), ('G4', 1), ('E4', 1),
                            ('D4', 1), ('E4', 1), ('D4', 1), ('B3', 1),
                            ('C4', 1), ('E4', 1), ('A4', 2),
                            ('G4', 1), ('F4', 1), ('E4', 2),
                            ('E4', 1), ('G4', 1), ('C5', 2),
                            ('B4', 1), ('G4', 1), ('D4', 2),
                            ('A4', 1), ('F4', 1), ('G4', 2),
                            ('G4', 2), ('R', 2)]),
            ('bass', 0.7, [('C2', 2), ('C3', 2), ('G2', 2), ('G3', 2),
                           ('A2', 2), ('A3', 2), ('F2', 2), ('F3', 2),
                           ('C2', 2), ('C3', 2), ('G2', 2), ('G3', 2),
                           ('F2', 2), ('F3', 2), ('G2', 2), ('G3', 2)]),
        ]},
        # 地图·第一幕：D大调英雄进行曲
        'map_hope': {'tempo': 112, 'beats': 16, 'master': 0.85, 'tracks': [
            ('strings', 0.5, [('D3+F#3+A3', 4), ('A2+E3+A3', 4),
                              ('B2+F#3+B3', 4), ('G2+D3+G3', 4)]),
            ('flute', 0.45, [('D4', 1), ('E4', 1), ('F#4', 1), ('A4', 1),
                             ('A4', 1), ('G4', 1), ('F#4', 2),
                             ('B4', 1), ('A4', 1), ('F#4', 1), ('D4', 1),
                             ('G4', 1), ('A4', 1), ('D4', 2)]),
            ('bass', 0.7, [('D2', 1), ('A2', 1), ('D3', 1), ('A2', 1),
                           ('A2', 1), ('E3', 1), ('A2', 1), ('E3', 1),
                           ('B2', 1), ('F#3', 1), ('B2', 1), ('F#3', 1),
                           ('G2', 1), ('D3', 1), ('G2', 1), ('A2', 1)]),
        ]},
        # 地图·第二幕：A小调紧张急行
        'map_tense': {'tempo': 124, 'beats': 16, 'master': 0.82, 'tracks': [
            ('strings', 0.48, [('A2+C3+E3', 2), ('A2+C3+E3', 2),
                               ('F2+A2+C3', 2), ('F2+A2+C3', 2),
                               ('D2+F2+A2', 2), ('D2+F2+A2', 2),
                               ('E2+G#2+B2', 2), ('E2+G#2+B2', 2)]),
            ('brass', 0.42, [('A4', 1), ('B4', 1), ('C5', 1), ('B4', 1),
                             ('A4', 2), ('E4', 2),
                             ('F4', 1), ('E4', 1), ('D4', 1), ('E4', 1),
                             ('C4', 2), ('E4', 1), ('B3', 1)]),
            ('bass', 0.78, [('A1', 1), ('A2', 1), ('A1', 1), ('E2', 1),
                            ('F1', 1), ('F2', 1), ('F1', 1), ('C2', 1),
                            ('D1', 1), ('D2', 1), ('D1', 1), ('A1', 1),
                            ('E1', 1), ('E2', 1), ('E1', 1), ('B1', 1)]),
        ]},
        # 地图·第三幕：D小调阴郁压迫
        'map_dark': {'tempo': 88, 'beats': 16, 'master': 0.85, 'tracks': [
            ('strings', 0.6, [('D3+F3+A3', 4), ('Bb2+D3+F3', 4),
                              ('G2+Bb2+D3', 4), ('A2+C#3+E3', 4)]),
            ('brass', 0.4, [('D4', 2), ('F4', 1), ('E4', 1),
                            ('D4', 2), ('Bb3', 2),
                            ('G4', 2), ('F4', 1), ('D4', 1),
                            ('A4', 2), ('A3', 2)]),
            ('bass', 0.8, [('D2', 2), ('D2', 2), ('Bb1', 2), ('Bb1', 2),
                           ('G1', 2), ('G1', 2), ('A1', 2), ('A2', 2)]),
        ]},
        # 敌方回合：低沉小调脉冲（全章节通用）
        'enemy': {'tempo': 104, 'beats': 8, 'master': 0.8, 'tracks': [
            ('strings', 0.55, [('A2+C3+E3', 4), ('F2+A2+C3', 4)]),
            ('bass', 0.85, [('A1', 1), ('A1', 1), ('E2', 1), ('A1', 1),
                            ('F1', 1), ('F1', 1), ('C2', 1), ('F1', 1)]),
            ('pluck', 0.3, [('E4', 1), ('C4', 1), ('A3', 1), ('C4', 1),
                            ('C4', 1), ('A3', 1), ('F3', 1), ('A3', 1)]),
        ]},
        # 剧情/过场：F大调温柔（长笛+竖琴琶音）
        'story': {'tempo': 80, 'beats': 16, 'master': 0.8, 'tracks': [
            ('strings', 0.45, [('F3+A3+C4', 4), ('C3+E3+G3', 4),
                               ('D3+F3+A3', 4), ('Bb2+D3+F3', 4)]),
            ('flute', 0.42, [('A4', 2), ('G4', 1), ('F4', 1),
                             ('G4', 2), ('E4', 2),
                             ('F4', 2), ('A4', 1), ('C5', 1),
                             ('A4', 2), ('F4', 2)]),
            ('pluck', 0.4, [('F3', 1), ('A3', 1), ('C4', 1), ('A3', 1),
                            ('C3', 1), ('E3', 1), ('G3', 1), ('E3', 1),
                            ('D3', 1), ('F3', 1), ('A3', 1), ('F3', 1),
                            ('Bb2', 1), ('D3', 1), ('F3', 1), ('D3', 1)]),
        ]},
        # 胜利号角：C大调辉煌
        'victory': {'tempo': 120, 'beats': 16, 'master': 1.0, 'tracks': [
            ('brass', 0.6, [('C4', 1), ('E4', 1), ('G4', 1), ('C5', 1),
                            ('G4', 2), ('C5', 2),
                            ('E5', 2), ('D5', 1), ('C5', 1),
                            ('C4+E4+G4+C5', 4)]),
            ('bell', 0.4, [('C5', 1), ('R', 1), ('G5', 1), ('R', 1),
                           ('C6', 2), ('R', 2),
                           ('R', 4),
                           ('C6', 4)]),
            ('bass', 0.75, [('C2', 1), ('C2', 1), ('G2', 1), ('G2', 1),
                            ('C2', 2), ('G2', 2),
                            ('C2', 1), ('G2', 1), ('C3', 2),
                            ('C2', 4)]),
            ('timpani', 0.5, [('C2', 1), ('R', 1), ('C2', 1), ('G1', 1),
                              ('C2', 2), ('G1', 2),
                              ('C2', 1), ('C2', 1), ('G1', 2),
                              ('C2', 1), ('G1', 1), ('C2', 2)]),
        ]},
        # 败北：D小调悲怆（纯弦乐）
        'defeat': {'tempo': 66, 'beats': 16, 'master': 0.85, 'tracks': [
            ('strings', 0.7, [('D3+F3+A3', 4), ('A2+C3+E3', 4),
                              ('Bb2+D3+F3', 4), ('A2+C#3+E3', 4)]),
            ('flute', 0.4, [('D4', 3), ('C4', 1),
                            ('A3', 4),
                            ('Bb3', 2), ('A3', 1), ('G3', 1),
                            ('A3', 4)]),
            ('bass', 0.6, [('D2', 4), ('A1', 4), ('Bb1', 4), ('A1', 4)]),
        ]},
    }


SONGS = None     # 延迟到 init 时按真实采样率构建


# ---------- 初始化与播放 ----------

def init():
    """合成全部曲目并预备播放通道。任何失败静音降级。"""
    global _enabled, _sounds, SAMPLE_RATE, CHANNELS
    try:
        import numpy as np
        import pygame
        got = pygame.mixer.get_init()
        if not got:
            raise RuntimeError('mixer not initialized')
        SAMPLE_RATE, _size, CHANNELS = got
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(2)          # 通道 0/1 留给音乐交叉淡入
        arrays = {}
        for name, song in _songs().items():
            mono = _build_song(np, song)
            data = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
            if CHANNELS >= 2:
                data = np.ascontiguousarray(np.column_stack([data] * CHANNELS))
            arrays[name] = data
        _sounds = {k: pygame.sndarray.make_sound(v) for k, v in arrays.items()}
        _enabled = True
        director._chan = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
    except Exception:
        _enabled = False
        _sounds = {}


_cinema_playing = False


def play_cinema():
    """开场动画的 AI 交响乐（流式播放，独立于程序化曲目通道）。"""
    global _cinema_playing
    if not (_enabled and _user_on):
        return
    try:
        import pygame
        from paths import resource_root
        path = resource_root() / 'assets' / 'cinema' / 'bgm_epic.mp3'
        if not path.exists():
            return
        director.update(None)               # 静默程序化通道
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(_CINEMA_VOL * _music_vol)
        pygame.mixer.music.play(fade_ms=1200)
        _cinema_playing = True
    except Exception:
        _cinema_playing = False


def stop_cinema():
    global _cinema_playing
    if not _cinema_playing:
        return
    try:
        import pygame
        pygame.mixer.music.fadeout(900)
    except Exception:
        pass
    _cinema_playing = False


def set_enabled(on):
    """音乐总开关（M 键）。关闭时淡出当前曲。"""
    global _user_on
    _user_on = on
    if not on:
        director.stop()
        stop_cinema()
    else:
        director.resume()


def is_on():
    return _user_on


def set_volume(frac):
    """设置音乐音量（0..1）。即时作用于正在播放的程序化通道与开场交响乐。"""
    global _music_vol
    _music_vol = max(0.0, min(1.0, frac))
    try:
        import pygame
        for c in director._chan:
            if c.get_busy():
                c.set_volume(_BASE_VOL * _music_vol)
        if _cinema_playing:
            pygame.mixer.music.set_volume(_CINEMA_VOL * _music_vol)
    except Exception:
        pass


class MusicDirector:
    """按曲目 key 在两个保留通道间交叉淡入；重复同 key 不打断。"""
    FADE = 900

    def __init__(self):
        self._chan = []
        self._cur = None          # 当前曲目 key
        self._active = 0          # 当前活动通道索引

    def update(self, key):
        if not (_enabled and _user_on) or not self._chan:
            return
        if key == self._cur:
            return
        self._cur = key
        nxt = 1 - self._active
        if self._chan[self._active].get_busy():
            self._chan[self._active].fadeout(self.FADE)
        if key is not None and key in _sounds:
            self._chan[nxt].play(_sounds[key], loops=-1, fade_ms=self.FADE)
            self._chan[nxt].set_volume(_BASE_VOL * _music_vol)
        self._active = nxt

    def stop(self):
        for c in self._chan:
            if c.get_busy():
                c.fadeout(self.FADE)
        self._cur = None

    def resume(self):
        self._cur = None          # 下次 update 会重新起曲


director = MusicDirector()


# 游戏状态 -> 曲目 key 的映射
def track_for(state, chapter_idx=0, enemy_phase=False):
    if state in ('TITLE', 'CODEX', 'GUIDE'):
        return 'title'
    if state in ('CINEMA',):
        return None               # 开场动画用 AI 交响乐（game 单独处理）
    if state in ('PROLOGUE', 'INTRO', 'DIALOGUE'):
        return 'story'
    if state == 'COMPLETE':
        return 'victory'
    if state == 'CLEAR':
        return 'victory'
    if state == 'END':
        return 'defeat'
    if state in ('IDLE', 'MOVE', 'MENU', 'MAP_MENU', 'TARGET', 'FORECAST',
                 'COMBAT', 'LEVELUP', 'ENEMY_TURN', 'DETAIL'):
        if enemy_phase:
            return 'enemy'
        return ('map_hope', 'map_tense', 'map_dark')[min(2, chapter_idx // 4 + (chapter_idx >= 7))]
    return None


if __name__ == '__main__':
    # python3 music.py — 依次试听每首曲目 8 秒
    import time
    import pygame
    pygame.init()
    import sfx
    sfx.init()
    init()
    print('音乐可用:', _enabled, '| 采样率:', SAMPLE_RATE, '| 声道:', CHANNELS)
    for name in _sounds:
        print(' ♪', name)
        director._cur = None
        director.update(name)
        time.sleep(8)
