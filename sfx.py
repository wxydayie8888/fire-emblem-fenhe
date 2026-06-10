"""程序化音效：用 numpy 合成 8-bit 风格短音，无需任何外部音频文件。

numpy 或音频设备不可用时自动降级为静音（所有调用变 no-op）。
对外接口：init() 启动时调用一次；play(name) 播放音效。
"""
import math

_sounds = {}
_enabled = False

SAMPLE_RATE = 22050


def _tone(freqs, dur, vol=0.5, shape='square', fade=True):
    """freqs: 单频或 (起始,结束) 扫频；shape: square/sine/noise"""
    import numpy as np
    n = int(SAMPLE_RATE * dur)
    t = np.arange(n) / SAMPLE_RATE
    if shape == 'noise':
        wave = np.random.default_rng(7).uniform(-1, 1, n)
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


def _build():
    import numpy as np
    snd = {}
    snd['select'] = _tone(880, 0.05, 0.25)
    snd['confirm'] = _concat(_tone(660, 0.05, 0.3), _tone(990, 0.07, 0.3))
    snd['cancel'] = _tone((440, 280), 0.08, 0.3)
    snd['hit'] = _concat(_tone((220, 110), 0.06, 0.5), _tone(80, 0.06, 0.4, 'noise'))
    snd['crit'] = _concat(_tone(80, 0.10, 0.55, 'noise'), _tone((1320, 1760), 0.12, 0.4))
    snd['miss'] = _tone((900, 200), 0.12, 0.2, 'sine')
    snd['heal'] = _concat(_tone(784, 0.07, 0.3, 'sine'), _tone(1175, 0.12, 0.3, 'sine'))
    snd['levelup'] = _concat(_tone(523, 0.09, 0.35), _tone(659, 0.09, 0.35),
                             _tone(784, 0.09, 0.35), _tone(1047, 0.22, 0.4))
    snd['victory'] = _concat(_tone(523, 0.12, 0.4), _tone(523, 0.06, 0.35), _tone(659, 0.12, 0.4),
                             _tone(784, 0.12, 0.4), _tone(1047, 0.30, 0.45))
    snd['defeat'] = _concat(_tone(392, 0.18, 0.4, 'sine'), _tone(330, 0.18, 0.4, 'sine'),
                            _tone(262, 0.35, 0.4, 'sine'))
    snd['turn'] = _concat(_tone(440, 0.06, 0.25), _tone(587, 0.10, 0.25))
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
    if _enabled and name in _sounds:
        try:
            _sounds[name].play()
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
