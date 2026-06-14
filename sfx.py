"""程序化音效：用 numpy 合成 8-bit 风格短音，无需任何外部音频文件。

numpy 或音频设备不可用时自动降级为静音（所有调用变 no-op）。
对外接口：init() 启动时调用一次；play(name) 播放音效。
"""
import math

_sounds = {}
_enabled = False
_vol = 1.0          # 全局音效音量 0..1（由 config 设置）

SAMPLE_RATE = 22050


def set_volume(frac):
    """设置音效音量（0..1）。即时生效，下次 play 应用。"""
    global _vol
    _vol = max(0.0, min(1.0, frac))


def _tone(freqs, dur, vol=0.5, shape='square', fade=True, seed=7):
    """freqs: 单频或 (起始,结束) 扫频；shape: square/sine/noise；seed: 噪声种子。"""
    import numpy as np
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    if shape == 'noise':
        wave = np.random.default_rng(seed).uniform(-1, 1, n)
    else:
        if isinstance(freqs, tuple):
            f0, f1 = freqs
            phase = 2 * math.pi * (f0 * t + (f1 - f0) * t * t / (2 * dur))
        else:
            phase = 2 * math.pi * freqs * t
        wave = np.sin(phase)
        if shape == 'square':
            wave = np.sign(wave) * 0.7
    env = np.ones(n)
    a = max(1, int(n * 0.02))
    env[:a] = np.linspace(0, 1, a)
    if fade:
        env *= np.linspace(1, 0, n) ** 0.7
    return wave * env * vol


def _concat(*parts):
    import numpy as np
    return np.concatenate(parts)


def _mix(*parts):
    """叠加多层（取最长，逐元素相加）→ 更厚实的音色。"""
    import numpy as np
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def _build():
    import numpy as np
    snd = {}
    # --- 基础交互 ---
    snd['select'] = _tone(880, 0.05, 0.25)
    snd['confirm'] = _concat(_tone(660, 0.05, 0.3), _tone(990, 0.07, 0.3))
    snd['cancel'] = _tone((440, 280), 0.08, 0.3)
    snd['turn'] = _concat(_tone(440, 0.06, 0.25), _tone(587, 0.10, 0.25))
    # --- 战斗 ---
    snd['hit'] = _mix(_tone((260, 90), 0.07, 0.5), _tone(70, 0.07, 0.45, 'noise'))   # 钝击叠噪
    snd['crit'] = _concat(_mix(_tone(90, 0.05, 0.6, 'noise'), _tone((200, 90), 0.05, 0.5)),
                          _mix(_tone((1320, 1980), 0.16, 0.4), _tone((660, 990), 0.16, 0.22)))
    snd['effective'] = _concat(_tone((1568, 2349), 0.07, 0.4, 'sine'),                 # 特效：金属斩鸣
                               _mix(_tone(60, 0.12, 0.6, 'noise', seed=5), _tone((420, 160), 0.12, 0.45)),
                               _tone((1760, 1175), 0.14, 0.3, 'sine'))
    snd['miss'] = _tone((900, 200), 0.12, 0.2, 'sine')
    snd['die'] = _tone((300, 70), 0.28, 0.4, 'sine')
    snd['break'] = _concat(_tone(200, 0.03, 0.55, 'noise', seed=3),                    # 武器破损：脆裂
                           _tone((520, 140), 0.10, 0.4), _tone(110, 0.06, 0.3, 'noise', seed=9))
    snd['heal'] = _concat(_tone(784, 0.07, 0.3, 'sine'), _tone(1175, 0.12, 0.3, 'sine'))
    # --- 成长 / 奖励 ---
    snd['levelup'] = _concat(_tone(523, 0.09, 0.35), _tone(659, 0.09, 0.35),
                             _tone(784, 0.09, 0.35), _tone(1047, 0.22, 0.4))
    snd['promote'] = _concat(_tone(523, 0.07, 0.3), _tone(659, 0.07, 0.3), _tone(784, 0.07, 0.3),
                             _tone(1047, 0.09, 0.35), _tone(1319, 0.09, 0.35),
                             _mix(_tone(1568, 0.35, 0.4, 'sine'), _tone(2093, 0.35, 0.22, 'sine')))
    snd['coin'] = _concat(_tone(1319, 0.05, 0.3, 'sine'), _tone(1760, 0.10, 0.3, 'sine'))
    snd['chest'] = _concat(_tone(880, 0.05, 0.25, 'sine'), _tone(1109, 0.05, 0.25, 'sine'),
                           _tone(1319, 0.05, 0.25, 'sine'),
                           _mix(_tone(1760, 0.18, 0.3, 'sine'), _tone(2637, 0.18, 0.16, 'sine')))
    # --- 系统 / 战场事件 ---
    snd['rewind'] = _mix(_tone((1320, 440), 0.28, 0.3, 'sine'), _tone((660, 1320), 0.28, 0.2, 'sine'),
                         _tone((990, 495), 0.28, 0.14, 'sine'))
    snd['reinforce'] = _concat(_mix(_tone(110, 0.16, 0.45), _tone(131, 0.16, 0.32)),    # 增援：低沉号角警讯
                               _mix(_tone(110, 0.30, 0.45), _tone(165, 0.30, 0.3)))
    # --- 胜负 ---
    snd['victory'] = _concat(_tone(523, 0.12, 0.4), _tone(523, 0.06, 0.35), _tone(659, 0.12, 0.4),
                             _tone(784, 0.12, 0.4), _tone(1047, 0.30, 0.45))
    snd['defeat'] = _concat(_tone(392, 0.18, 0.4, 'sine'), _tone(330, 0.18, 0.4, 'sine'),
                            _tone(262, 0.35, 0.4, 'sine'))
    return {k: (np.clip(v, -1, 1) * 32767).astype(np.int16) for k, v in snd.items()}


def init():
    """初始化混音器并合成全部音效。任何失败都静音降级。"""
    global _sounds, _enabled, SAMPLE_RATE
    try:
        import numpy as np
        import pygame
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        freq, _size, channels = pygame.mixer.get_init()
        SAMPLE_RATE = freq                      # 按实际采样率合成，避免变调
        arrays = _build()
        if channels >= 2:                       # 混音器若为立体声则复制声道
            arrays = {k: np.ascontiguousarray(np.column_stack([v] * channels))
                      for k, v in arrays.items()}
        _sounds = {k: pygame.sndarray.make_sound(v) for k, v in arrays.items()}
        _enabled = True
    except Exception:
        _sounds, _enabled = {}, False


def play(name):
    if _enabled and name in _sounds and _vol > 0:
        try:
            snd = _sounds[name]
            snd.set_volume(_vol)
            snd.play()
        except Exception:
            pass


if __name__ == '__main__':
    # python3 sfx.py — 依次试听全部音效
    import time
    import pygame
    pygame.init()
    init()
    print('音效可用:', _enabled)
    for name in _sounds:
        print(' ▶', name)
        play(name)
        time.sleep(0.7)
