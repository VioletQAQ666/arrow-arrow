"""游戏核心逻辑：不依赖 pygame，可单独测试。"""

DIRS = {
    'U': (-1, 0),
    'D': (1, 0),
    'L': (0, -1),
    'R': (0, 1),
}
DIR_NAMES = {'U': '上', 'D': '下', 'L': '左', 'R': '右'}
EMPTY_CHARS = {'.', ' ', '\t'}


def parse_level(rows):
    """把字符画关卡解析成二维列表，空格用 None 表示。"""
    if not rows:
        return []
    width = len(rows[0])
    grid = []
    for line in rows:
        if len(line) != width:
            raise ValueError(f"关卡每一行长度必须一致：{line!r}")
        grid.append([ch if ch in DIRS else None for ch in line])
    return grid


def is_blocked(grid, row, col, direction):
    """
    判断 (row, col) 处的箭头沿 direction 前进时是否被阻挡。
    只需要检查同一行或同一列、箭头与边界之间的格子。
    """
    dr, dc = DIRS[direction]
    height = len(grid)
    width = len(grid[0])
    r, c = row + dr, col + dc
    while 0 <= r < height and 0 <= c < width:
        if grid[r][c] is not None:
            return True
        r += dr
        c += dc
    return False


def clearable_cells(grid):
    """返回当前棋盘上所有可以飞出的箭头坐标与方向。"""
    result = []
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            direction = grid[r][c]
            if direction is not None and not is_blocked(grid, r, c, direction):
                result.append((r, c, direction))
    return result


def apply_move(grid, row, col):
    """返回移除指定箭头之后的新棋盘，不修改原对象。"""
    new_grid = [list(line) for line in grid]
    new_grid[row][col] = None
    return new_grid


def solve_level(grid, max_states=200000):
    """
    深度优先 + 记忆化求解。
    返回点击顺序 [(row, col, direction), ...]，无解返回 None。
    """
    if not grid:
        return []
    height = len(grid)
    width = len(grid[0])
    start = tuple(tuple(line) for line in grid)
    memo = {}
    visited = [0]

    def finished(state):
        for line in state:
            for value in line:
                if value is not None:
                    return False
        return True

    def dfs(state):
        if state in memo:
            return memo[state]
        visited[0] += 1
        if visited[0] > max_states:
            raise RuntimeError("求解状态数超出上限，请检查关卡规模")
        if finished(state):
            return []
        for r in range(height):
            for c in range(width):
                direction = state[r][c]
                if direction is None:
                    continue
                dr, dc = DIRS[direction]
                nr, nc = r + dr, c + dc
                blocked = False
                while 0 <= nr < height and 0 <= nc < width:
                    if state[nr][nc] is not None:
                        blocked = True
                        break
                    nr += dr
                    nc += dc
                if blocked:
                    continue
                nxt = [list(line) for line in state]
                nxt[r][c] = None
                nxt = tuple(tuple(line) for line in nxt)
                rest = dfs(nxt)
                if rest is not None:
                    memo[state] = [(r, c, direction)] + rest
                    return memo[state]
        memo[state] = None
        return None

    return dfs(start)


def compute_stars(mistakes_left, total_mistakes, elapsed, par_time,
                 hints_used=0, auto_used=False):
    """
    星级评价（纯函数，便于单元测试）。
    基础星级：
      - 0 次失误            → 3 星
      - 失误数不超过一半    → 2 星
      - 其他                → 1 星
    调整项：
      - 用时超过 par_time   → -1 星
      - 用过提示            → 最多 2 星
      - 用过自动求解        → 最多 1 星
    下限恒为 1 星（毕竟过关了）。
    """
    used = max(0, total_mistakes - mistakes_left)
    if used == 0:
        stars = 3
    elif used <= max(1, total_mistakes // 2):
        stars = 2
    else:
        stars = 1
    if elapsed > par_time:
        stars -= 1
    if hints_used > 0:
        stars = min(stars, 2)
    if auto_used:
        stars = min(stars, 1)
    return max(1, stars)
