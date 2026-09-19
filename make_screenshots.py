"""一键截图：无头渲染真实界面到 screenshots/。

用法（装好 pygame 后、在项目目录下运行）：
    python make_screenshots.py

它不弹窗口（SDL 用 dummy 驱动离屏渲染），直接把真实界面导出成 PNG：

    screenshots/start.png          开始界面
    screenshots/select.png         选关界面（含星级记录与随机关卡入口）
    screenshots/game.png           游戏进行中（含提示高亮）
    screenshots/collision.png      点中被挡的箭头：碰撞反馈（变红 + 朝前顶出 + 飘 -1）
    screenshots/win.png            通关 + 星级评价
    screenshots/lose.png           失败（失误耗尽 / 超时两种文案）
    screenshots/random.png         随机关卡（求解器验证有解）
"""
import os

# 必须在 import pygame 相关模块前设置：不弹窗口，离屏渲染
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame  # noqa: E402

from game import Game  # noqa: E402
from levels import LEVELS  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
os.makedirs(OUT, exist_ok=True)
DT = 1.0 / 60.0


def settle(game, frames=40):
    """手动推进若干帧，让动画 / 辉光 / 光尘到位。"""
    for _ in range(frames):
        game.update(DT)
        game.draw()


def shot(game, name):
    game.draw()
    path = os.path.join(OUT, name)
    pygame.image.save(game.canvas, path)
    print("saved:", path)


def blocked_cell(game, order="first"):
    """找一个当前点不动的箭头，用来演示碰撞反馈。"""
    cells = [(r, c) for r in range(game.rows) for c in range(game.cols)
             if game.board[r][c] is not None and not game.game.is_free(r, c)]
    if not cells:
        return None
    return cells[0] if order == "first" else cells[-1]


def main():
    game = Game()

    # 1) 开始界面
    game.set_state("START")
    settle(game, 30)
    shot(game, "start.png")

    # 2) 选关界面
    game.start_game()
    settle(game, 20)
    shot(game, "select.png")

    # 3) 游戏界面：第 2 关进行中，并高亮一个可点箭头（演示提示功能）
    game.play_level(1)
    for _ in range(3):
        moves = game.solution_moves()
        if moves:
            row, col, _ = moves[0]
            game.try_clear(row, col)
        settle(game, 6)
    game.elapsed = 12.0
    game.hint_cell = game.solution_moves()[0][:2] if game.solution_moves() else None
    game.game.hints_used = 1
    settle(game, 12)
    shot(game, "game.png")

    # 4) 碰撞反馈：点一个被挡住的箭头，抓它"顶出去"的那一帧
    game.play_level(3)
    settle(game, 4)
    cell = blocked_cell(game)
    if cell is not None:
        game.try_clear(*cell)
        # 反馈动画在 FEEDBACK_TIME 内，取刚冲出去的一小段
        for _ in range(6):
            game.update(DT)
            game.draw()
        shot(game, "collision.png")
    else:
        print("警告：第 4 关开局没有被挡住的箭头，跳过碰撞截图")

    # 5) 通关界面：0 失误、3 星
    game.play_level(0)
    settle(game, 4)
    for _ in range(200):
        if game.pending_result == "win":
            break
        moves = game.solution_moves()
        if not moves:
            break
        row, col, _ = moves[0]
        game.try_clear(row, col)
        settle(game, 2)
    settle(game, 80)
    shot(game, "win.png")

    # 6) 失败界面：失误耗尽
    game.play_level(3)
    settle(game, 4)
    cell = blocked_cell(game)
    if cell is not None:
        game.game.mistakes_left = 1
        game.sync_state()
        game.try_clear(*cell)
        settle(game, 90)
        shot(game, "lose.png")

    # 7) 随机关卡（求解器验证有解）
    game.play_random_level(2)
    settle(game, 12)
    shot(game, "random.png")

    pygame.quit()
    print("完成，目录内容：", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
