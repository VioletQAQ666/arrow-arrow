"""无头整局冒烟测试：真的把游戏跑一遍，检查界面流程不会崩。

它不弹窗口（用 SDL 的 dummy 驱动离屏渲染），而是像一个玩家那样：
进关卡 → 按求解器给的顺序点击 → 每点一次都推进并渲染若干帧 →
等飞出动画播完 → 检查结算界面 → 进下一关 / 重开 / 选关。

单元测试（test_logic.py / test_gameplay.py）验证的是规则，
这个脚本验证的是"界面 + 规则 + 动画 + 状态切换"接在一起还能不能跑通，
专门用来抓 AttributeError、除零、动画卡死、状态机漏跳这类集成问题。

    python self_test.py

全部通过时退出码为 0，任何一项失败退出码为 1。
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from game import Game  # noqa: E402
from levels import LEVELS  # noqa: E402

DT = 1.0 / 60.0
FAILURES = []


def check(condition, message):
    if condition:
        print(f"  [通过] {message}")
    else:
        print(f"  [失败] {message}")
        FAILURES.append(message)
    return bool(condition)


def advance(game, frames=1):
    """推进并渲染若干帧。"""
    for _ in range(frames):
        game.update(DT)
        game.draw()


def clear_level(game, max_clicks=200):
    """按当前局面的解法一路点完，返回点击次数。"""
    clicks = 0
    while game.pending_result != "win" and clicks < max_clicks:
        moves = game.solution_moves()
        if not moves:
            break
        row, col, _direction = moves[0]
        game.try_clear(row, col)
        clicks += 1
        advance(game, 3)
    return clicks


def test_all_levels(game):
    print("\n[1] 四个固定关卡：按解法逐关通关")
    for index, level in enumerate(LEVELS):
        game.play_level(index)
        advance(game, 2)
        check(game.state == "PLAYING", f"第 {index + 1} 关进入游戏界面")
        clicks = clear_level(game)
        advance(game, 80)          # 等飞行动画播完 + 结算面板弹出
        check(game.state == "WIN",
              f"第 {index + 1} 关（{level['name']}）通关，用了 {clicks} 次点击")
        check(game.stars >= 1, f"第 {index + 1} 关结算给出了星级 {game.stars}")


def test_win_flow(game):
    print("\n[2] 通关流程：选关 / 重新开始")
    game.back_to_level_select()
    advance(game, 2)
    check(game.state == "LEVEL_SELECT", "能回到选关界面")
    check(len(game.level_card_rects) == len(LEVELS), "选关卡片数量与关卡数一致")
    game.play_level(0)
    advance(game, 2)
    game.restart_level()
    advance(game, 2)
    check(game.state == "PLAYING" and game.remaining == game.initial_count,
          "重新开始后箭头数量恢复")


def test_collision_and_lose(game):
    print("\n[3] 碰撞反馈与失败流程")
    game.play_level(0)
    advance(game, 2)
    # 找一个开局就被挡住的箭头来撞
    blocked_cell = None
    for row in range(game.rows):
        for col in range(game.cols):
            if game.board[row][col] is not None and not game.game.is_free(row, col):
                blocked_cell = (row, col)
                break
        if blocked_cell:
            break
    if not check(blocked_cell is not None, "第 1 关存在被挡住的箭头"):
        return
    row, col = blocked_cell
    before_remaining = game.remaining
    before_mistakes = game.mistakes_left
    game.try_clear(row, col)
    advance(game, 2)
    check(game.remaining == before_remaining, "被挡的箭头没有消失")
    check(game.mistakes_left == before_mistakes - 1, "被挡后失误次数 -1")
    check(game.board[row][col].feedback > 0, "被挡的箭头触发了碰撞反馈动画")
    # 撞到失误耗尽
    game.mistakes_left = 1
    game.game.mistakes_left = 1
    game.try_clear(row, col)
    advance(game, 90)
    check(game.state == "LOSE", "失误耗尽后进入失败界面")
    check(game.lose_reason == "mistakes", "失败原因记录为失误耗尽")
    game.restart_level()
    advance(game, 2)
    check(game.state == "PLAYING" and game.mistakes_left == game.total_mistakes,
          "失败后重新开始，失误次数恢复")


def test_timeout(game):
    print("\n[4] 超时失败")
    game.play_level(1)
    advance(game, 2)
    game.elapsed = game.par_time + 1
    advance(game, 90)
    check(game.state == "LOSE", "时间用尽后进入失败界面")
    check(game.lose_reason == "timeout", "失败原因记录为超时")
    game.restart_level()
    advance(game, 2)
    check(game.elapsed < 1.0, "重新开始后计时归零")


def test_hint_undo_auto(game):
    print("\n[5] 扩展功能：提示 / 撤销 / 自动求解")
    game.play_level(1)
    advance(game, 2)
    game.show_hint()
    advance(game, 2)
    check(game.hint_cell is not None, "提示功能高亮了一个箭头")
    row, col = game.hint_cell
    game.try_clear(row, col)
    advance(game, 4)
    check(game.remaining == game.initial_count - 1, "按提示点击后箭头被消除")
    game.undo_move()
    advance(game, 2)
    check(game.remaining == game.initial_count, "撤销后箭头回到棋盘")
    check(game.history_len == 0, "撤销后没有可撤销的操作了")

    game.start_auto()
    check(game.auto_running, "自动求解已启动")
    # 每个箭头要等 AUTO_STEP_DELAY 才走下一步，还要等飞行动画播完，
    # 这里按帧推进直到通关（上限给足，避免测试本身卡住）
    for _ in range(4000):
        advance(game, 1)
        if game.state == "WIN":
            break
    check(game.state == "WIN", "自动求解把这一关点完了")
    check(game.stars == 1, "用过自动求解，星级被限制为 1 星")


def test_random_levels(game):
    print("\n[6] 扩展功能：随机关卡（三个难度档位）")
    for difficulty in (1, 2, 3):
        game.play_random_level(difficulty)
        advance(game, 2)
        check(game.state == "PLAYING" and game.remaining > 0,
              f"随机关卡（难度 {difficulty}）成功生成，共 {game.remaining} 个箭头")
        clear_level(game)
        advance(game, 80)
        check(game.state == "WIN", f"随机关卡（难度 {difficulty}）可以通关")
    game.back_to_level_select()
    advance(game, 2)


def main():
    print("=" * 60)
    print("一箭又一箭 —— 无头整局冒烟测试")
    print("=" * 60)
    game = Game()
    try:
        test_all_levels(game)
        test_win_flow(game)
        test_collision_and_lose(game)
        test_timeout(game)
        test_hint_undo_auto(game)
        test_random_levels(game)
    finally:
        pygame.quit()

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"冒烟测试失败：{len(FAILURES)} 项未通过")
        for item in FAILURES:
            print("  -", item)
        return 1
    print("冒烟测试全部通过：界面、路径判断、碰撞、结算、扩展功能均正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
