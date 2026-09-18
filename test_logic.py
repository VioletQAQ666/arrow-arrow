"""路径检测、关卡可解性与星级评价测试。"""
import unittest
from levels import LEVELS, validate_levels
from logic import (
    apply_move,
    clearable_cells,
    compute_stars,
    is_blocked,
    parse_level,
    solve_level,
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
