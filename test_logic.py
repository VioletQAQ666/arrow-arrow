"""路径检测、关卡可解性、随机关卡生成与星级评价测试。

    python -m unittest test_logic.py -v
"""
import unittest

from levels import LEVELS, validate_levels
from logic import (
    GameState,
    apply_move,
    clearable_cells,
    compute_stars,
    count_arrows,
    directions_for_cell,
    generate_level,
    is_blocked,
    parse_level,
    solve_level,
    validate_level,
)


class TestPathChecking(unittest.TestCase):
    """边缘与阻挡判断。"""

    def test_left_edge_is_free(self):
        self.assertFalse(is_blocked(parse_level(["L"]), 0, 0, 'L'))

    def test_top_edge_is_free(self):
        self.assertFalse(is_blocked(parse_level(["U"]), 0, 0, 'U'))

    def test_bottom_edge_is_free(self):
        self.assertFalse(is_blocked(parse_level(["D", "."]), 1, 0, 'D'))

    def test_right_edge_is_free(self):
        self.assertFalse(is_blocked(parse_level(["..R"]), 0, 2, 'R'))

    def test_blocked_in_same_row(self):
        grid = parse_level(["R.R"])
        self.assertTrue(is_blocked(grid, 0, 0, 'R'))
        self.assertFalse(is_blocked(grid, 0, 2, 'R'))

    def test_blocked_in_same_column(self):
        grid = parse_level(["D", ".", "U"])
        self.assertTrue(is_blocked(grid, 0, 0, 'D'))
        self.assertTrue(is_blocked(grid, 2, 0, 'U'))

    def test_other_row_does_not_block(self):
        self.assertFalse(is_blocked(parse_level(["R..", ".U."]), 0, 0, 'R'))

    def test_clearable_helper(self):
        self.assertEqual(clearable_cells(parse_level(["R.R", "..."])),
                         [(0, 2, 'R')])

    def test_ragged_level_raises(self):
        with self.assertRaises(ValueError):
            parse_level(["RR", "R"])

    def test_directions_for_cell(self):
        """directions_for_cell：返回"此刻就能直接飞出"的方向。"""
        self.assertEqual(sorted(directions_for_cell(parse_level(["."]), 0, 0)),
                         list("DLRU"))
        # "RR" 里的 (0,0)：朝右被同行的 R 挡住，其余三个方向都能直接飞出棋盘
        self.assertEqual(sorted(directions_for_cell(parse_level(["RR"]), 0, 0)),
                         list("DLU"))
        # (0,1) 朝右畅通，所以右方向是自由的
        self.assertIn("R", directions_for_cell(parse_level(["RR"]), 0, 1))
        # 同列两个都朝上：下面那个朝上被上面挡住，但朝下、左右都能走
        grid = parse_level(["U", "U"])
        self.assertNotIn("U", directions_for_cell(grid, 1, 0))
        self.assertIn("D", directions_for_cell(grid, 1, 0))

    def test_directions_for_cell_in_open_board(self):
        grid = parse_level(["...", "...", "..."])
        self.assertEqual(sorted(directions_for_cell(grid, 1, 1)), list("DLRU"))


class TestLevels(unittest.TestCase):
    """每一关都必须存在合法的通关顺序。"""

    def test_every_level_solvable(self):
        for index, level in enumerate(LEVELS, start=1):
            grid = parse_level(level["rows"])
            moves = solve_level(grid)
            self.assertIsNotNone(moves, f"第 {index} 关无解")
            total = sum(1 for line in grid for value in line if value)
            self.assertEqual(len(moves), total, f"第 {index} 关步数不匹配")

    def test_solution_only_takes_free_arrows(self):
        for index, level in enumerate(LEVELS, start=1):
            grid = parse_level(level["rows"])
            moves = solve_level(grid)
            work = [list(line) for line in grid]
            for row, col, _ in moves:
                arrow = work[row][col]
                self.assertIsNotNone(arrow, f"第 {index} 关重复点击同一格")
                self.assertFalse(is_blocked(work, row, col, arrow),
                                 f"第 {index} 关点击了受阻箭头")
                work[row][col] = None
            self.assertTrue(all(v is None for line in work for v in line))

    def test_validate_levels_helper(self):
        report = validate_levels()
        self.assertEqual(len(report), len(LEVELS))

    def test_validate_level_rejects_deadlock(self):
        """互相挡死的关卡必须被校验出来（这是验关工具的用处）。"""
        with self.assertRaises(ValueError):
            validate_level(["R.L"], "死锁样例")

    def test_validate_level_rejects_empty(self):
        with self.assertRaises(ValueError):
            validate_level(["..."], "空关卡")

    def test_validate_level_accepts_good_level(self):
        total, steps = validate_level(["U", "R"], "小关卡")
        self.assertEqual(total, 2)
        self.assertEqual(steps, 2)

    def test_level_meta_complete(self):
        for index, level in enumerate(LEVELS, start=1):
            self.assertIn("name", level, f"第 {index} 关缺少 name")
            self.assertGreater(level["mistakes"], 0, f"第 {index} 关失误次数非法")
            self.assertGreater(level["par_time"], 0, f"第 {index} 关缺少 par_time")


class TestHintAndAutoSolveSupport(unittest.TestCase):
    """提示 / 自动求解依赖的能力：任意合法中间局面仍可求解。"""

    def test_solving_from_partial_board(self):
        grid = parse_level(LEVELS[1]["rows"])
        free = clearable_cells(grid)
        self.assertTrue(free, "第 2 关开局应存在可点击箭头")
        row, col, _ = free[0]
        partial = apply_move(grid, row, col)
        moves = solve_level(partial)
        self.assertIsNotNone(moves, "清掉一个箭头后仍应可解")
        total = sum(1 for line in partial for v in line if v)
        self.assertEqual(len(moves), total)

    def test_empty_board_solution_is_empty(self):
        self.assertEqual(solve_level(parse_level(["..."])), [])


class TestRandomLevelGenerator(unittest.TestCase):
    """扩展功能：随机生成可通关关卡。

    生成器是"构造性保证有解"的（逆序摆放），这些测试验证它真的没撒谎：
    生成的每一关都能被求解器独立解出来，并且按解法真的能点完。
    """

    def test_generated_levels_are_solvable(self):
        for size in (3, 4, 5):
            for arrows in (3, 5, 8):
                with self.subTest(size=size, arrows=arrows):
                    level = generate_level(size, size, arrows, rng=size * 100 + arrows)
                    self.assertIsNotNone(level)
                    grid = parse_level(level["rows"])
                    self.assertEqual(count_arrows(grid), level["arrows"])
                    self.assertIsNotNone(solve_level(grid),
                                         f"随机生成的关卡无解：{level['rows']}")

    def test_generated_level_can_be_played_to_the_end(self):
        """生成的解法必须真的能一格格点完，且不消耗失误。"""
        for seed in range(12):
            with self.subTest(seed=seed):
                level = generate_level(4, 4, 7, rng=seed)
                game = GameState.from_rows(level["rows"])
                for row, col, _direction in level["solution"]:
                    result = game.click(row, col)
                    self.assertEqual(result["kind"], "cleared",
                                     f"解法里的 ({row},{col}) 点不动")
                self.assertTrue(game.won, "按生成的解法点完却没通关")
                self.assertEqual(game.mistakes_left, game.total_mistakes)

    def test_same_seed_gives_same_level(self):
        """同一个种子生成同一关，方便复现和写测试。"""
        first = generate_level(5, 5, 8, rng=42)
        second = generate_level(5, 5, 8, rng=42)
        self.assertEqual(first["rows"], second["rows"])

    def test_different_seeds_give_different_levels(self):
        layouts = {tuple(generate_level(5, 5, 8, rng=seed)["rows"])
                   for seed in range(8)}
        self.assertGreater(len(layouts), 1, "不同种子应该生成不同布局")

    def test_impossible_request_returns_none(self):
        """要的箭头比格子还多，直接返回 None。"""
        self.assertIsNone(generate_level(2, 2, 9, rng=0))
        self.assertIsNone(generate_level(3, 3, 0, rng=0))

    def test_generated_level_uses_up_to_four_directions(self):
        """生成的多个关卡里应该 U/D/L/R 四种方向都出现过。"""
        seen = set()
        for seed in range(10):
            level = generate_level(4, 4, 6, rng=seed)
            seen.update(ch for line in level["rows"] for ch in line if ch in "UDLR")
        self.assertEqual(seen, set("UDLR"))


class TestStarRating(unittest.TestCase):
    """星级评价纯函数。"""

    def test_perfect_run_is_three_stars(self):
        self.assertEqual(compute_stars(3, 3, 10, 60), 3)

    def test_one_mistake_is_two_stars(self):
        self.assertEqual(compute_stars(2, 3, 10, 60), 2)

    def test_all_mistakes_used_is_one_star(self):
        self.assertEqual(compute_stars(0, 3, 10, 60), 1)

    def test_overtime_costs_one_star(self):
        self.assertEqual(compute_stars(3, 3, 120, 60), 2)

    def test_hint_caps_at_two_stars(self):
        self.assertEqual(compute_stars(3, 3, 10, 60, hints_used=1), 2)

    def test_auto_solve_caps_at_one_star(self):
        self.assertEqual(compute_stars(3, 3, 10, 60, auto_used=True), 1)

    def test_never_below_one_star(self):
        stars = compute_stars(0, 3, 999, 60, hints_used=2, auto_used=True)
        self.assertEqual(stars, 1)


if __name__ == "__main__":
    unittest.main()
