"""火焰纹章风格战棋 — 入口。

操作: 左键 选择/确认   右键/ESC 取消   E 结束回合   R 重新开始(结局画面)
"""
import pygame

import settings


def main():
    pygame.init()
    pygame.display.set_caption('火焰纹章·芬河战记')
    screen = pygame.display.set_mode((settings.SCREEN_W, settings.SCREEN_H))
    import assets
    assets.load()
    import sfx
    sfx.init()
    import music
    music.init()
    import config
    config.load()                       # 玩家选项（音量/文字速度/…）
    sfx.set_volume(config.sfx_frac())
    music.set_volume(config.music_frac())
    from game import Game
    clock = pygame.time.Clock()
    game = Game()
    running = True
    while running:
        dt = clock.tick(settings.FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                game.handle(event)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == '__main__':
    main()
