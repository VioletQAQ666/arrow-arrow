"""游戏玩法自动化测试 —— 覆盖作业要求的 T01~T06 六个测试项。

这些测试操作的是 logic.GameState（一局游戏的完整状态机），不是界面，
所以不需要 pygame、不需要窗口，可以在命令行里几毫秒跑完：

    python -m unittest test_gameplay.py -v

界面层（game.py）只是把 GameState 的结果画出来，因此这里验证过的规则
就是玩家实际玩到的规则。
"""
import unittest

from levels import LEVELS
from logic import (
    CLICK_BLOCKED,
    CLICK_CLEARED,
    CLICK_NONE,
    GameState,
    count_arrows,
    parse_level,
)


def build(rows, **kwargs):
    """按字符画造一局游戏。"""
    return GameState.from_rows(rows, **kwargs)


# 作业文档里给的例子：第一个箭头朝右，但右侧还有箭头 → 不能飞出
EXAMPLE_BLOCKED = ["R..R"]
# 最后一个箭头朝右，右侧没有箭头 → 可以飞出
EXAMPLE_FREE = ["...R"]


class TestT01FreeArrow(unittest.TestCase):
    """T01 点击前方无阻挡的箭头 → 箭头飞出棋盘并消失。"""

    def test_single_arrow_flies_out(self):
        game = build(["U"])
        result = game.click(0, 0)
        self.assertEqual(result["kind"], CLICK_CLEARED)
        self.assertTrue(result["ok"])
        self.assertIsNone(game.grid[0][0])
        self.assertEqual(game.remaining, 0)
        self.assertTrue(game.won)

    def test_four_directions_all_fly_out_from_edge(self):
        """四个方向各自在最外圈、朝向棋盘外，都应该能直接飞出。"""
        for direction, (row, col) in (("U", (0, 1)), ("D", (4, 1)),
                                      ("L", (1, 0)), ("R", (1, 4))):
            with self.subTest(direction=direction):
                rows = ["....." for _ in range(5)]
                rows[row] = rows[row][:col] + direction + rows[row][col + 1:]
                game = build(rows)
                self.assertEqual(game.click(row, col)["kind"], CLICK_CLEARED)
                self.assertEqual(game.remaining, 0)

    def test_assignment_example_last_arrow_can_fly(self):
        """作业示例：↑ · · · → 中最后的 → 右侧无箭头，可以飞出。"""
        game = build(["U...R"])
        self.assertEqual(game.click(0, 4)["kind"], CLICK_CLEARED)
        self.assertEqual(game.remaining, 1)

    def test_click_does_not_cost_mistake(self):
        game = build(["R", "."])
        game.click(0, 0)
        self.assertEqual(game.mistakes_left, game.total_mistakes)


class TestT02BlockedArrow(unittest.TestCase):
    """T02 点击前方有阻挡的箭头 → 不消失，失误次数减 1。"""

    def test_blocked_arrow_stays_and_costs_mistake(self):
        game = build(EXAMPLE_BLOCKED)
        result = game.click(0, 0)
        self.assertEqual(result["kind"], CLICK_BLOCKED)
        self.assertIsNotNone(game.grid[0][0], "被挡的箭头不应该消失")
        self.assertEqual(game.remaining, 2, "被挡的箭头不计入消除")
        self.assertEqual(game.mistakes_left, game.total_mistakes - 1)

    def test_assignment_example_first_arrow_is_blocked(self):
        """作业示例：→ · · ↑ · 中第一个 → 右侧还有箭头，不能飞出。"""
        game = build(["R..U."])
        self.assertEqual(game.click(0, 0)["kind"], CLICK_BLOCKED)
        self.assertEqual(game.remaining, 2)

    def test_free_arrow_right_of_the_blocker_still_works(self):
        """同一行最右边的箭头先飞出后，左边那个就解锁了。"""
        game = build(EXAMPLE_BLOCKED)
        self.assertEqual(game.click(0, 3)["kind"], CLICK_CLEARED)
        self.assertEqual(game.click(0, 0)["kind"], CLICK_CLEARED)
        self.assertTrue(game.won)

    def test_vertical_blocking(self):
        """同列相向而行：上面的 D 想往下走，被下面的 U 挡住；
        下面那个 U 朝上、离上边界更近，同样被挡住——两个都点不动，
        只有先把其中一个的方向腾出来才行。这里测的是"被挡住"的判定本身。"""
        game = build(["D", ".", "U"])
        self.assertEqual(game.click(0, 0)["kind"], CLICK_BLOCKED)
        self.assertEqual(game.mistakes_left, game.total_mistakes - 1)
        self.assertEqual(game.click(0, 0)["kind"], CLICK_BLOCKED)

    def test_vertical_unlock_after_removing_blocker(self):
        """同一列里朝外的那一个能飞出去，飞掉之后同列另一个才解锁。"""
        game = build(["U", "D"])
        # (0,0)=U 朝上、贴着上边界，可以直接飞出；(1,0)=D 朝下、贴着下边界同理
        self.assertEqual(game.click(0, 0)["kind"], CLICK_CLEARED)
        self.assertEqual(game.click(1, 0)["kind"], CLICK_CLEARED)

    def test_same_column_stacked_arrows(self):
        """同一列三个都朝上：最上面那个贴着边界能飞出，清掉后依次解锁。"""
        game = build(["U", "U", "U"])
        self.assertEqual(game.click(1, 0)["kind"], CLICK_BLOCKED)
        self.assertEqual(game.click(0, 0)["kind"], CLICK_CLEARED)
        self.assertEqual(game.click(1, 0)["kind"], CLICK_CLEARED)

    def test_mistakes_run_out_after_repeated_clicks(self):
        game = build(EXAMPLE_BLOCKED, mistakes=2)
        game.click(0, 0)
        self.assertEqual(game.mistakes_left, 1)
        self.assertFalse(game.lost)
        result = game.click(0, 0)
        self.assertEqual(game.mistakes_left, 0)
        self.assertTrue(result["lost"], "失误耗尽时应返回 lost")
        self.assertTrue(game.lost)
        self.assertFalse(game.won)

    def test_click_empty_cell_is_ignored(self):
        game = build(["R.R"])
        self.assertEqual(game.click(0, 1)["kind"], CLICK_NONE)
        self.assertEqual(game.mistakes_left, game.total_mistakes)


class TestT03EdgeCases(unittest.TestCase):
    """T03 点击位于边缘且朝向棋盘外的箭头 → 正常消失，不发生越界错误。"""

    def test_all_four_corners_pointing_outward(self):
        rows = ["U..R",
                "....",
                "....",
                "L..D"]
        for row, col in ((0, 0), (0, 3), (3, 0), (3, 3)):
            with self.subTest(cell=(row, col)):
                game = build(list(rows))
                self.assertEqual(game.click(row, col)["kind"], CLICK_CLEARED)

    def test_single_cell_board(self):
        """1×1 棋盘：没有别的格子，任何方向都应该直接飞出，不能报越界。"""
        for direction in "UDLR":
            with self.subTest(direction=direction):
                game = build([direction])
                self.assertEqual(game.click(0, 0)["kind"], CLICK_CLEARED)
                self.assertTrue(game.won)

    def test_edge_arrow_blocked_by_nothing_but_wall(self):
        """整行只有一个箭头、且朝边界时，不能因为"越界"被误判成被挡。"""
        game = build(["R....",])
        self.assertEqual(game.click(0, 0)["kind"], CLICK_CLEARED)

    def test_click_outside_board_is_ignored(self):
        game = build(["R"])
        self.assertEqual(game.click(5, 5)["kind"], CLICK_NONE)
        self.assertEqual(game.click(-1, 0)["kind"], CLICK_NONE)
        self.assertEqual(game.remaining, 1)

    def test_one_column_board(self):
        game = build(["U", "U", "U"])
        self.assertEqual(game.click(0, 0)["kind"], CLICK_CLEARED)
        self.assertEqual(game.click(1, 0)["kind"], CLICK_CLEARED)
        self.assertEqual(game.click(2, 0)["kind"], CLICK_CLEARED)
        self.assertTrue(game.won)


class TestT04ClearAllAndAdvanceLevel(unittest.TestCase):
    """T04 消除本关全部箭头 → 通关并进入下一关。"""

    def test_clearing_every_arrow_wins(self):
        game = build(["U", "R"])
        game.click(0, 0)
        self.assertFalse(game.won, "还有一个箭头时不算通关")
        game.click(1, 0)
        self.assertTrue(game.won)
        self.assertEqual(game.remaining, 0)

    def test_every_level_clears_completely_by_its_solution(self):
        """4 个关卡都能按各自解法真的清空（T04 的批量版本）。"""
        for index, level in enumerate(LEVELS, start=1):
            with self.subTest(level=index):
                game = GameState.from_level(index - 1, LEVELS)
                moves = game.solution()
                self.assertIsNotNone(moves, f"第 {index} 关无解")
                for row, col, _direction in moves:
                    result = game.click(row, col)
                    self.assertEqual(result["kind"], CLICK_CLEARED,
                                     f"第 {index} 关 ({row},{col}) 应该能飞出")
                self.assertTrue(game.won, f"第 {index} 关没有清空")
                self.assertEqual(game.mistakes_left, game.total_mistakes,
                                 f"第 {index} 关通关不该消耗失误")

    def test_next_level_resets_everything(self):
        """进入下一关后，新的关卡是完整初始状态。"""
        game = GameState.from_level(0, LEVELS)
        for row, col, _ in game.solution():
            game.click(row, col)
        self.assertTrue(game.won)
        # 模拟界面“下一关”
        nxt = GameState.from_level(1, LEVELS)
        self.assertEqual(nxt.remaining, nxt.initial_count)
        self.assertEqual(nxt.mistakes_left, nxt.total_mistakes)
        self.assertFalse(nxt.won)
        self.assertEqual(nxt.history, [])

    def test_win_state_not_reached_early(self):
        game = build(["U", "D"])
        game.click(1, 0)              # 清掉一个
        self.assertFalse(game.won)
        self.assertEqual(game.remaining, 1)


class TestT05MistakesRunOut(unittest.TestCase):
    """T05 失误次数耗尽 → 失败，并可以重新开始。"""

    def test_lose_when_mistakes_exhausted(self):
        game = build(EXAMPLE_BLOCKED, mistakes=3)
        for expected_left in (2, 1, 0):
            game.click(0, 0)
            self.assertEqual(game.mistakes_left, expected_left)
        self.assertTrue(game.lost)
        self.assertFalse(game.won)

    def test_lost_is_not_won(self):
        game = build(EXAMPLE_BLOCKED, mistakes=1)
        game.click(0, 0)
        self.assertTrue(game.lost)
        self.assertFalse(game.won)
        self.assertEqual(game.remaining, 2, "失败时棋盘上仍有箭头")

    def test_mistakes_never_go_negative(self):
        game = build(EXAMPLE_BLOCKED, mistakes=1)
        for _ in range(5):
            game.click(0, 0)
        self.assertEqual(game.mistakes_left, 0)

    def test_restart_after_losing(self):
        game = build(EXAMPLE_BLOCKED, mistakes=1)
        game.click(0, 0)
        self.assertTrue(game.lost)
        game.reset()
        self.assertFalse(game.lost)
        self.assertEqual(game.mistakes_left, game.total_mistakes)
        self.assertEqual(game.remaining, game.initial_count)
        self.assertTrue(game.click(0, 3)["ok"], "重开后应该能正常操作")

    def test_timeout_is_decided_by_ui_layer(self):
        """超时判负需要时钟，由界面层负责；逻辑层只保证不误判为通关。"""
        game = build(["U", "D"], par_time=10.0)
        self.assertEqual(game.par_time, 10.0)
        game.click(1, 0)
        self.assertFalse(game.won, "还有箭头时不能因超时以外的原因判通关")
        self.assertFalse(game.lost)


class TestT06Restart(unittest.TestCase):
    """T06 游戏进行中重新开始 → 箭头布局和失误次数恢复。"""

    def test_restart_restores_board_and_mistakes(self):
        game = build(EXAMPLE_BLOCKED, mistakes=3)   # 两个朝右的箭头，右边的挡着左边的
        game.click(0, 0)              # 先撞一次：被右边的箭头挡住
        self.assertEqual(game.remaining, 2, "被挡的箭头不该消失")
        self.assertEqual(game.mistakes_left, 2)
        game.click(0, 3)              # 最右边那个飞出去
        self.assertEqual(game.remaining, 1)

        game.reset()

        self.assertEqual(game.remaining, game.initial_count)
        self.assertEqual(game.remaining, count_arrows(parse_level(EXAMPLE_BLOCKED)))
        self.assertEqual(game.mistakes_left, game.total_mistakes)
        self.assertEqual(game.history, [])
        self.assertEqual(game.grid, parse_level(EXAMPLE_BLOCKED))

    def test_restart_midway_through_a_real_level(self):
        game = GameState.from_level(2, LEVELS)
        moves = game.solution()
        for row, col, _ in moves[:3]:
            game.click(row, col)
        self.assertLess(game.remaining, game.initial_count)

        game.reset()

        self.assertEqual(game.remaining, game.initial_count)
        self.assertEqual(game.mistakes_left, game.total_mistakes)
        self.assertEqual(game.grid, parse_level(LEVELS[2]["rows"]))

    def test_restart_clears_undo_history(self):
        game = build(["U", "R"])
        game.click(0, 0)
        self.assertEqual(len(game.history), 1)
        game.reset()
        self.assertEqual(len(game.history), 0)
        self.assertFalse(game.undo()["ok"], "重开之后不该还能撤销上局的操作")

    def test_reset_twice_is_idempotent(self):
        game = build(EXAMPLE_BLOCKED)
        game.click(0, 0)
        game.reset()
        game.reset()
        self.assertEqual(game.remaining, game.initial_count)
        self.assertEqual(game.mistakes_left, game.total_mistakes)


class TestUndo(unittest.TestCase):
    """扩展功能：撤销（对应 README 的 Z 键）。"""

    def test_undo_restores_cleared_arrow(self):
        game = build(["U", "R"])
        game.click(0, 0)
        self.assertEqual(game.remaining, 1)
        result = game.undo()
        self.assertEqual(result["kind"], "clear")
        self.assertEqual(game.grid[0][0], "U")
        self.assertEqual(game.remaining, 2)

    def test_undo_restores_mistake(self):
        game = build(EXAMPLE_BLOCKED)
        game.click(0, 0)
        self.assertEqual(game.mistakes_left, 2)
        result = game.undo()
        self.assertEqual(result["kind"], "block")
        self.assertEqual(game.mistakes_left, 3)

    def test_undo_without_history_is_safe(self):
        game = build(["U"])
        self.assertFalse(game.undo()["ok"])
        self.assertEqual(game.remaining, 1)

    def test_undo_after_losing_restores_playability(self):
        game = build(EXAMPLE_BLOCKED, mistakes=1)
        game.click(0, 0)
        self.assertTrue(game.lost)
        game.undo()
        self.assertFalse(game.lost)
        self.assertEqual(game.mistakes_left, 1)
        self.assertTrue(game.click(0, 3)["ok"], "撤销后应该能继续玩")


class TestStarsAndDifficulty(unittest.TestCase):
    """扩展功能：星级评价与关卡难度参数。"""

    def test_perfect_clear_is_three_stars(self):
        game = build(["U", "R"], par_time=60.0)
        game.click(0, 0)
        game.click(1, 0)
        self.assertEqual(game.stars_for(elapsed=5.0), 3)

    def test_mistake_lowers_stars(self):
        game = build(EXAMPLE_BLOCKED, mistakes=3, par_time=60.0)
        game.click(0, 0)
        self.assertEqual(game.stars_for(elapsed=5.0), 2)

    def test_auto_solve_caps_stars(self):
        game = build(["U"], par_time=60.0)
        game.auto_used = True
        game.click(0, 0)
        self.assertEqual(game.stars_for(elapsed=5.0), 1)

    def test_hint_caps_stars(self):
        game = build(["U"], par_time=60.0)
        game.hints_used = 1
        game.click(0, 0)
        self.assertEqual(game.stars_for(elapsed=5.0), 2)

    def test_hint_and_auto_caps_stay_in_effect_via_game_state(self):
        """回归测试：stars_for 必须真的把自己记录的提示/自动求解次数传下去。

        曾经出现过"Game 界面层自己存一份 hints_used/auto_used、GameState 存一份，
        结算时读的是另一边"的问题，结果是用了 AI 求解照样给 3 星。
        这里直接检查 GameState 上的计数会影响到星级。
        """
        game = build(["U"], par_time=60.0)
        game.hints_used = 2
        game.auto_used = True
        # 0 次失误、没超时，本来是 3 星，但用过提示和自动求解要压到 1 星
        self.assertEqual(game.stars_for(elapsed=1.0), 1)
        # 显式传参优先于自身记录
        self.assertEqual(
            game.stars_for(elapsed=1.0, hints_used=0, auto_used=False), 3)

    def test_overtime_lowers_stars(self):
        game = build(["U"], par_time=30.0)
        game.click(0, 0)
        self.assertEqual(game.stars_for(elapsed=100.0), 2)


if __name__ == "__main__":
    unittest.main()
