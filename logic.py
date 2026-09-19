"""游戏核心逻辑：不依赖 pygame，可脱离界面单独测试。

本模块分三层：
1. 棋盘工具函数：parse_level / is_blocked / clearable_cells / apply_move
2. 求解器：solve_level（验关、提示、自动求解共用）
3. GameState：一局游戏的完整状态机（点击、失误、胜负、撤销、重启），
   GameState.from_level() / GameState.from_rows() 用于构造，
   GameState.restart() 用于恢复到初始状态。
游戏界面只负责把 GameState 的结果画出来，因此这些规则可以在没有窗口的
情况下用单元测试完整验证（见 test_gameplay.py）。
"""
import random

DIRS = {
    'U': (-1, 0),
    'D': (1, 0),
    'L': (0, -1),
    'R': (0, 1),
}
DIR_NAMES = {'U': '上', 'D': '下', 'L': '左', 'R': '右'}
EMPTY_CHARS = {'.', ' ', '\t'}

# 点击结果
CLICK_NONE = 'none'        # 点到空格 / 无效位置
CLICK_CLEARED = 'cleared'  # 前方无阻挡，箭头飞出
CLICK_BLOCKED = 'blocked'  # 前方有阻挡，消耗一次失误


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


def count_arrows(grid):
    """统计棋盘上的箭头总数。"""
    return sum(1 for line in grid for value in line if value)


def arrow_count_of_rows(rows):
    """统计字符画关卡里的箭头数量（选关卡片等处显示用）。"""
    return sum(1 for line in rows for ch in line if ch in DIRS)


def solve_level(grid, max_states=400000):
    """
    回溯搜索求解，返回点击顺序 [(row, col, direction), ...]，无解返回 None。

    这是个"每点一次必定消掉一个箭头"的游戏：只要搜到空棋盘，路径长度就一定
    等于箭头数，所以任意一条合法路径都是不会浪费点击的解法，不需要
    按最短路径去遍历所有局面。

    因此这里用带记忆化的深度优先搜索，而不是广度优先：DFS 一旦走到空棋盘
    就直接返回，不用把整张状态图展开完。
    实测同一个 6x6 / 29 个箭头的密集棋盘：DFS 约 0.1ms，
    而 BFS 要展开几十万个中间状态、耗时 40 秒以上——提示功能每点一次都要
    重算解法，这个差距直接决定界面会不会卡住。

    代价是搜索顺序固定（按行列顺序试），遇到无解的棋盘要靠遍历所有可达状态
    才能确认，所以用 max_states 兜底，防止关卡设计出错时把界面卡死。
    """
    if not grid:
        return []
    height = len(grid)
    start = tuple(tuple(line) for line in grid)
    if count_arrows(grid) == 0:
        return []

    memo = {}
    visited = [0]

    def blocked(state, r, c, direction):
        dr, dc = DIRS[direction]
        nr, nc = r + dr, c + dc
        while 0 <= nr < height and 0 <= nc < len(state[nr]):
            if state[nr][nc] is not None:
                return True
            nr += dr
            nc += dc
        return False

    def dfs(state):
        cached = memo.get(state, False)
        if cached is not False:
            return cached
        visited[0] += 1
        if visited[0] > max_states:
            raise RuntimeError("求解状态数超出上限，请检查关卡规模")
        for r in range(height):
            for c in range(len(state[r])):
                direction = state[r][c]
                if direction is None or blocked(state, r, c, direction):
                    continue
                row = list(state[r])
                row[c] = None
                nxt = list(state)
                nxt[r] = tuple(row)
                nxt = tuple(nxt)
                if count_arrows(nxt) == 0:
                    memo[state] = [(r, c, direction)]
                    return memo[state]
                rest = dfs(nxt)
                if rest is not None:
                    memo[state] = [(r, c, direction)] + rest
                    return memo[state]
        memo[state] = None
        return None

    return dfs(start)


def validate_level(rows, name="关卡"):
    """校验一份关卡数据：行列等长、至少一个箭头、存在通关顺序。

    返回 (箭头数, 解法步数)；不合法则抛 ValueError。
    """
    grid = parse_level(rows)
    if not grid:
        raise ValueError(f"{name}为空")
    total = count_arrows(grid)
    if total == 0:
        raise ValueError(f"{name}没有任何箭头")
    moves = solve_level(grid)
    if moves is None:
        raise ValueError(f"{name}无解（存在互相阻挡的死锁），请重新设计")
    if len(moves) != total:
        raise ValueError(f"{name}解法步数与箭头数不一致")
    return total, len(moves)


def directions_for_cell(grid, row, col):
    """列出该格放哪些方向的箭头时「此刻就能直接飞出」（到边界一路无阻挡）。

    这是随机关卡生成器的核心判据：逆序造关卡时，只有此刻能飞出的箭头
    才允许被放上去。
    """
    height = len(grid)
    width = len(grid[0])
    free = []
    for direction, (dr, dc) in DIRS.items():
        r, c = row + dr, col + dc
        clear = True
        while 0 <= r < height and 0 <= c < width:
            if grid[r][c] is not None:
                clear = False
                break
            r += dr
            c += dc
        if clear:
            free.append(direction)
    return free


def generate_level(rows=5, cols=5, arrows=8, rng=None, min_fill=0.0,
                   max_attempts=None):
    """随机生成一个「保证可通关」的关卡。

    做法是**逆序造关卡**：从空棋盘开始，一个一个往上放箭头；每次只允许把箭头
    放在「此刻就能直接飞出」的格子（即 directions_for_cell 判定的方向）。
    把放置顺序倒过来就是一份合法通关顺序——放上去时能飞出，说明轮到它飞的时候，
    挡在它前面的箭头早都清掉了。

    这一步不是"生成完再碰运气"，而是**构造性保证有解**：任意一份
    按这个规则造出来的布局，倒序就是解法，不可能出现死锁。
    生成完再交给 solve_level() 独立复验一次，构造逻辑和求解器互为验证。

    min_fill 控制难度：要求箭头占棋盘格子的比例不低于它，否则重抽。
    摆得越满，能放的位置越少、阻挡链越长，关卡越难；空心棋盘则几乎处处可点。
    某些 (格子数, 箭头数) 组合下随机摆法很难正好达到 min_fill，
    这时会退而返回试过的里面最满的一个，不会返回 None。

    返回 dict：{"rows": 字符画, "solution": 解法, "arrows": 箭头数,
    "blocked": 开局被挡住的箭头数, "fill": 摆放密度}；参数不合理返回 None。
    """
    rng = random.Random(rng)
    if rows < 1 or cols < 1 or arrows < 1 or arrows > rows * cols:
        return None
    if max_attempts is None:
        max_attempts = 2000
    best = None
    for _ in range(max_attempts):
        grid = [[None] * cols for _ in range(rows)]
        placed = []                       # 摆放顺序（倒过来就是通关顺序）
        for _ in range(arrows):
            # 候选位置：空着，并且此刻至少有一个方向能直接飞出
            options = []
            for r in range(rows):
                for c in range(cols):
                    if grid[r][c] is not None:
                        continue
                    free = directions_for_cell(grid, r, c)
                    if free:
                        options.append((r, c, free))
            if not options:
                break
            r, c, free = rng.choice(options)
            direction = rng.choice(free)
            grid[r][c] = direction
            placed.append((r, c, direction))
        if len(placed) != arrows:
            # 这个 (格子数, 箭头数) 组合下摆不满（例如格子太少或太挤），
            # 记下已经摆出来的当作兜底，不必再空转剩下的尝试次数
            fill = len(placed) / (rows * cols)
            if placed and (best is None or fill > best["fill"]):
                best = {"grid": grid, "fill": fill, "arrows": len(placed)}
            continue
        fill = arrows / (rows * cols)
        if fill < min_fill:
            # 达不到难度要求就不必花代价去求解，直接记下最满的一次备用
            if best is None or fill > best["fill"]:
                best = {"grid": grid, "fill": fill, "arrows": arrows}
            continue
        moves = solve_level(grid)
        if moves is None:
            # 构造性保证不该出现；真出现说明生成器有 bug，直接暴露出来
            raise RuntimeError(
                f"逆序构造的关卡竟然无解，生成器存在缺陷：{grid}")
        if len(moves) != arrows:
            continue
        return _level_info(grid, moves, arrows, fill)
    if best is None:
        return None
    # 兜底：达不到 min_fill，就返回试过的里面最满的那一个（同样保证有解）
    grid = best["grid"]
    return _level_info(grid, solve_level(grid), best["arrows"], best["fill"])


def _level_info(grid, moves, arrows, fill):
    """把棋盘整理成对外的关卡字典。"""
    return {
        "rows": ["".join(cell if cell else '.' for cell in line)
                 for line in grid],
        "solution": moves,
        "arrows": arrows,
        "blocked": arrows - len(clearable_cells(grid)),
        "fill": fill,
    }



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


class GameState:
    """一局游戏的完整状态机：不依赖 pygame，界面只负责渲染它。

    负责：点击判定、失误扣减、胜负判定、撤销历史、重新开始。
    不负责：任何绘制、动画、计时（计时由界面层传入 elapsed 后判定）。
    """

    def __init__(self, data, index=0, random_level=False):
        self.data = dict(data)
        self.index = index
        self.random_level = random_level
        self.name = data.get("name", "随机关卡")
        self.total_mistakes = int(data.get("mistakes", 3))
        self.par_time = float(data.get("par_time", 60.0))
        self.initial_rows = [str(line) for line in data["rows"]]
        self.history = []
        self.hints_used = 0
        self.auto_used = False
        self.reset()

    # ------------------------------------------------------------ 构造
    @classmethod
    def from_level(cls, index, levels):
        """按关卡数据表构造。"""
        return cls(levels[index], index=index)

    @classmethod
    def from_rows(cls, rows, mistakes=3, par_time=60.0, name="随机关卡",
                  index=0, random_level=True):
        """直接按字符画构造（随机关卡、单元测试用）。"""
        return cls({"rows": rows, "mistakes": mistakes, "par_time": par_time,
                    "name": name}, index=index, random_level=random_level)

    # ------------------------------------------------------------ 生命周期
    def reset(self):
        """恢复到本关初始状态（“重新开始”按钮走这里）。"""
        self.grid = parse_level(self.initial_rows)
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.grid else 0
        self.initial_count = count_arrows(self.grid)
        self.remaining = self.initial_count
        self.mistakes_left = self.total_mistakes
        self.history.clear()
        self.hints_used = 0
        self.auto_used = False
        self.stars = 0

    # ------------------------------------------------------------ 查询
    def is_free(self, row, col):
        """该格箭头当前是否可以飞出（空格视为不可点）。"""
        direction = self.grid[row][col]
        if direction is None:
            return False
        return not is_blocked(self.grid, row, col, direction)

    def clearable(self):
        """当前所有可飞出的箭头。"""
        return clearable_cells(self.grid)

    def snapshot(self):
        """棋盘的不含对象快照，用于缓存求解结果。"""
        return tuple(tuple(line) for line in self.grid)

    # ------------------------------------------------------------ 操作
    def click(self, row, col, record=True):
        """点击某格，返回结果字典。

        kind 取值：CLICK_NONE / CLICK_CLEARED / CLICK_BLOCKED
        额外字段：
          clear  → direction
          block  → direction, lost（本次是否因失误耗尽判负）
        胜利/超时判负不在这里决定：胜利要等飞出动画播完，
        超时由界面层用 elapsed 判定，避免逻辑层依赖时钟。
        """
        result = {"ok": False, "kind": CLICK_NONE, "row": row, "col": col}
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return result
        direction = self.grid[row][col]
        if direction is None:
            return result
        if self.is_free(row, col):
            self.grid[row][col] = None
            self.remaining -= 1
            if record:
                self.history.append({"kind": "clear", "row": row, "col": col,
                                     "direction": direction})
            result.update(ok=True, kind=CLICK_CLEARED, direction=direction)
            return result
        self.mistakes_left = max(0, self.mistakes_left - 1)
        if record:
            self.history.append({"kind": "block", "row": row, "col": col,
                                 "direction": direction})
        result.update(ok=True, kind=CLICK_BLOCKED, direction=direction,
                      lost=self.mistakes_left <= 0)
        return result

    def undo(self):
        """撤销上一步。返回 {'ok', 'kind', ...}，无可撤销时 ok=False。"""
        if not self.history:
            return {"ok": False, "kind": None}
        last = self.history.pop()
        if last["kind"] == "block":
            self.mistakes_left = min(self.total_mistakes, self.mistakes_left + 1)
            return {"ok": True, "kind": "block", "row": last["row"],
                    "col": last["col"], "direction": last["direction"]}
        self.grid[last["row"]][last["col"]] = last["direction"]
        self.remaining += 1
        return {"ok": True, "kind": "clear", "row": last["row"],
                "col": last["col"], "direction": last["direction"]}

    # ------------------------------------------------------------ 结果
    @property
    def won(self):
        return self.remaining == 0

    @property
    def lost(self):
        return self.mistakes_left <= 0

    @property
    def mistakes_used(self):
        return self.total_mistakes - self.mistakes_left

    def stars_for(self, elapsed, hints_used=None, auto_used=None):
        """按当前局面算星级（默认取本局累计的提示/自动求解记录）。

        注意 hints_used / auto_used 必须真的传下去：compute_stars 里
        「用过提示最高 2 星、用过自动求解最高 1 星」这两条调整项完全依赖它们，
        漏传就会变成"用了 AI 求解照样给 3 星"。
        """
        return compute_stars(
            self.mistakes_left, self.total_mistakes, elapsed, self.par_time,
            hints_used=(self.hints_used if hints_used is None
                        else hints_used),
            auto_used=(self.auto_used if auto_used is None
                       else auto_used))

    def solution(self):
        """当前局面的解法（调用方自行按 snapshot 缓存）。"""
        return solve_level(self.grid)

    def status_text(self):
        """HUD 用的一行状态描述。"""
        return (f"{self.name}：剩余 {self.remaining}/{self.initial_count} 箭头，"
                f"失误 {self.mistakes_left}/{self.total_mistakes}")
