"""游戏主体：状态机、交互与渲染。"""
import math
import random
import pygame
import theme as T
from effects import Effects
from graphics import (
    Button,
    draw_round_panel,
    draw_text_with_shadow,
    ease_out_cubic,
    get_arrow_surface,
    get_heart_surface,
    get_star_surface,
    load_font,
    make_vertical_gradient,
    render_gradient_text,
)
from levels import LEVELS
from logic import DIRS, compute_stars, is_blocked, parse_level, solve_level


def format_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class Arrow:
    """棋盘上的一个箭头。"""
    __slots__ = ("direction", "feedback")

    def __init__(self, direction):
        self.direction = direction
        self.feedback = 0.0


class FlyingArrow:
    """飞出棋盘时的动画对象。"""
    __slots__ = ("start", "direction", "size", "distance", "duration", "elapsed")

    def __init__(self, start, direction, size, distance, duration=T.FLY_TIME):
        self.start = start
        self.direction = direction
        self.size = size
        self.distance = distance
        self.duration = duration
        self.elapsed = 0.0

    @property
    def finished(self):
        return self.elapsed >= self.duration

    def update(self, dt):
        self.elapsed += dt

    def position(self):
        progress = min(1.0, self.elapsed / self.duration)
        eased = progress * progress            # 越飞越快
        dr, dc = DIRS[self.direction]        # dr 影响行(屏幕y)，dc 影响列(屏幕x)
        return (self.start[0] + dc * self.distance * eased,
                self.start[1] + dr * self.distance * eased)

    def draw(self, surface):
        sprite = get_arrow_surface(self.direction, self.size, self.direction)
        surface.blit(sprite, sprite.get_rect(center=self.position()))


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(T.WINDOW_TITLE)
        self.window = pygame.display.set_mode((T.WINDOW_WIDTH, T.WINDOW_HEIGHT))
        self.canvas = pygame.Surface(
            (T.WINDOW_WIDTH, T.WINDOW_HEIGHT)).convert_alpha()
        self.clock = pygame.time.Clock()
        self.fonts = {
            "title": load_font(58, bold=True),
            "big": load_font(36, bold=True),
            "mid": load_font(24, bold=True),
            "normal": load_font(20),
            "small": load_font(16),
            "tiny": load_font(14),
        }
        self.background = make_vertical_gradient(
            (T.WINDOW_WIDTH, T.WINDOW_HEIGHT), T.BG_TOP, T.BG_BOTTOM)
        self.effects = Effects()
        self.running = True

        # ---- 关卡数据 ----
        self.state = "START"
        self.level_index = 0
        self.board = []
        self.rows = 0
        self.cols = 0
        self.cell_size = T.BOARD_MAX_CELL
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.remaining = 0
        self.initial_count = 0
        self.mistakes_left = 0
        self.total_mistakes = 0
        self.par_time = 60.0
        self.flying = []
        self.hover_cell = None

        # ---- 扩展功能状态 ----
        self.history = []          # 操作历史，用于撤销
        self.solution = None       # 当前局面的解法缓存
        self.hint_cell = None      # 提示高亮格
        self.hints_used = 0
        self.auto_running = False
        self.auto_queue = []
        self.auto_timer = 0.0
        self.auto_used = False
        self.elapsed = 0.0
        self.stars = 0

        # ---- 结算与提示条 ----
        self.pending_result = None
        self.result_timer = 0.0
        self.lose_reason = "mistakes"   # mistakes / timeout
        self.overlay_t = 0.0
        self.toast_text = ""
        self.toast_color = T.TEXT_MAIN
        self.toast_life = 0.0
        self.toast_total = T.TOAST_TIME
        self.active_buttons = []
        self.buttons_by_key = {}
        self.level_card_rects = []   # 选关界面每张卡片的矩形
        self.set_state("START")
        try:
            pygame.display.set_icon(get_arrow_surface("U", 64, "U"))
        except pygame.error:
            pass

    # ------------------------------------------------------------ 状态
    def set_state(self, state):
        self.state = state
        self.overlay_t = 0.0
        if state != "PLAYING":
            self.auto_running = False
            self.auto_queue.clear()
        self.refresh_buttons()

    def refresh_buttons(self):
        self.active_buttons = self._make_buttons(self.state)

    def _make_buttons(self, state):
        width = T.WINDOW_WIDTH
        buttons = []
        self.buttons_by_key = {}
        if state == "START":
            buttons.append(Button(
                (width // 2 - 130, 520, 260, 62), "开始游戏",
                self.fonts["big"], self.start_game,
                style="primary", radius=18))
        elif state == "PLAYING":
            # 顶栏右侧按钮组，从右往左排布
            right = width - 22
            restart = pygame.Rect(right - 118, 14, 118, 36)
            auto = pygame.Rect(restart.x - 10 - 118, 14, 118, 36)
            hint = pygame.Rect(auto.x - 10 - 96, 14, 96, 36)
            undo = pygame.Rect(hint.x - 10 - 96, 14, 96, 36)
            btn_undo = Button(undo, "撤销 Z", self.fonts["small"],
                              self.undo_move, style="secondary", radius=10)
            btn_hint = Button(hint, "提示 H", self.fonts["small"],
                              self.show_hint, style="secondary", radius=10)
            btn_auto = Button(
                auto, "停止求解" if self.auto_running else "自动求解",
                self.fonts["small"], self.toggle_auto,
                style="primary" if self.auto_running else "secondary",
                radius=10)
            btn_restart = Button(restart, "重新开始", self.fonts["small"],
                                 self.restart_level, style="secondary", radius=10)
            buttons.extend([btn_undo, btn_hint, btn_auto, btn_restart])
            self.buttons_by_key.update({
                "undo": btn_undo,
                "hint": btn_hint,
                "auto": btn_auto,
            })
        elif state == "LEVEL_SELECT":
            self.level_card_rects = []
            card_w, card_h, gap = 196, 130, 18
            total = len(LEVELS) * card_w + (len(LEVELS) - 1) * gap
            x0 = (width - total) // 2
            y0 = 300
            for i, lv in enumerate(LEVELS):
                rect = pygame.Rect(x0 + i * (card_w + gap), y0, card_w, card_h)
                buttons.append(Button(
                    rect, lv["name"], self.fonts["mid"],
                    lambda idx=i: self.play_level(idx),
                    style="primary", radius=16))
                self.level_card_rects.append((rect, lv))
        elif state == "WIN":
            has_next = self.level_index + 1 < len(LEVELS)
            buttons.append(Button(
                (width // 2 - 235, 455, 150, 50),
                "下一关" if has_next else "重玩本关",
                self.fonts["small"],
                self.next_level if has_next else self.restart_level,
                style="primary", radius=12))
            buttons.append(Button(
                (width // 2 - 75, 455, 150, 50), "选关",
                self.fonts["small"], self.back_to_level_select,
                style="secondary", radius=12))
            buttons.append(Button(
                (width // 2 + 85, 455, 150, 50), "返回主页",
                self.fonts["small"], self.back_to_start,
                style="secondary", radius=12))
        elif state == "LOSE":
            buttons.append(Button(
                (width // 2 - 235, 455, 150, 50), "重新开始",
                self.fonts["small"], self.restart_level,
                style="primary", radius=12))
            buttons.append(Button(
                (width // 2 - 75, 455, 150, 50), "选关",
                self.fonts["small"], self.back_to_level_select,
                style="secondary", radius=12))
            buttons.append(Button(
                (width // 2 + 85, 455, 150, 50), "返回主页",
                self.fonts["small"], self.back_to_start,
                style="secondary", radius=12))
        return buttons

    def _sync_buttons(self):
        """按钮可用状态随游戏状态实时变化。"""
        undo = self.buttons_by_key.get("undo")
        if undo is not None:
            undo.enabled = bool(self.history) and not self.auto_running
        hint = self.buttons_by_key.get("hint")
        if hint is not None:
            hint.enabled = not self.auto_running

    # ------------------------------------------------------------ 关卡
    def load_level(self, index):
        self.level_index = index
        data = LEVELS[index]
        raw = parse_level(data["rows"])
        self.rows = len(raw)
        self.cols = len(raw[0])
        self.board = [[Arrow(value) if value else None for value in line]
                      for line in raw]
        self.total_mistakes = data["mistakes"]
        self.mistakes_left = self.total_mistakes
        self.par_time = float(data.get("par_time", 60.0))
        self.remaining = sum(1 for line in self.board for a in line if a)
        self.initial_count = self.remaining
        self.flying.clear()
        self.effects.clear()
        # 扩展功能状态复位
        self.history.clear()
        self.solution = None
        self.hint_cell = None
        self.hints_used = 0
        self.auto_running = False
        self.auto_queue.clear()
        self.auto_timer = 0.0
        self.auto_used = False
        self.elapsed = 0.0
        self.stars = 0
        self.pending_result = None
        self.result_timer = 0.0
        self.lose_reason = "mistakes"
        self.toast_life = 0.0
        self.hover_cell = None
        avail_w = T.WINDOW_WIDTH - 200
        avail_h = T.WINDOW_HEIGHT - T.TOP_BAR_H - T.HUD_H - 118
        cell = min(avail_w // self.cols, avail_h // self.rows, T.BOARD_MAX_CELL)
        cell = max(cell, T.BOARD_MIN_CELL)
        self.cell_size = cell
        board_w = cell * self.cols
        board_h = cell * self.rows
        center_x = T.WINDOW_WIDTH // 2
        center_y = T.TOP_BAR_H + T.HUD_H + (
            T.WINDOW_HEIGHT - T.TOP_BAR_H - T.HUD_H - 46) // 2
        self.board_rect = pygame.Rect(center_x - board_w // 2,
                                      center_y - board_h // 2,
                                      board_w, board_h)

    def start_game(self):
        self.set_state("LEVEL_SELECT")

    def play_level(self, index):
        self.load_level(index)
        self.set_state("PLAYING")

    def back_to_level_select(self):
        self.flying.clear()
        self.effects.clear()
        self.set_state("LEVEL_SELECT")

    def restart_level(self):
        self.load_level(self.level_index)
        self.set_state("PLAYING")

    def next_level(self):
        if self.level_index + 1 < len(LEVELS):
            self.load_level(self.level_index + 1)
            self.set_state("PLAYING")

    def back_to_start(self):
        self.flying.clear()
        self.effects.clear()
        self.set_state("START")

    # ------------------------------------------------------------ 提示条
    def toast(self, text, color=T.TEXT_MAIN):
        self.toast_text = text
        self.toast_color = color
        self.toast_life = self.toast_total

    # ------------------------------------------------------------ 求解器
    def logic_grid(self):
        return [[self.board[r][c].direction if self.board[r][c] else None
                 for c in range(self.cols)]
                for r in range(self.rows)]

    def get_solution(self):
        """当前局面的解法（带缓存，任何棋盘变动都会失效）。"""
        if self.solution is None:
            self.solution = solve_level(self.logic_grid())
        return self.solution

    def invalidate_solution(self):
        self.solution = None

    # ------------------------------------------------------------ 扩展：提示
    def show_hint(self):
        if self.state != "PLAYING" or self.pending_result is not None:
            return
        if self.auto_running:
            self.toast("自动求解进行中，先停止再使用提示", T.TEXT_SUB)
            return
        moves = self.get_solution()
        if not moves:
            self.toast("当前没有可点击的箭头", T.DANGER)
            return
        row, col, direction = moves[0]
        self.hint_cell = (row, col)
        self.hints_used += 1
        self.toast(f"提示：点击高亮箭头（还需 {len(moves)} 步）", T.HINT)

    # ------------------------------------------------------------ 扩展：自动求解
    def toggle_auto(self):
        if self.auto_running:
            self.stop_auto("已停止自动求解")
        else:
            self.start_auto()

    def start_auto(self):
        if self.state != "PLAYING" or self.pending_result is not None:
            return
        if self.remaining == 0:
            return
        moves = self.get_solution()
        if not moves:
            self.toast("当前局面无法求解", T.DANGER)
            return
        self.auto_queue = list(moves)
        self.auto_running = True
        self.auto_used = True
        self.hint_cell = None
        self.auto_timer = 0.10
        self.toast(f"AI 求解中：共 {len(moves)} 步，点击「停止求解」可接管", T.HINT)
        self.refresh_buttons()

    def stop_auto(self, message=None):
        was_running = self.auto_running
        self.auto_running = False
        self.auto_queue.clear()
        if message and was_running:
            self.toast(message, T.TEXT_SUB)
        self.refresh_buttons()

    # ------------------------------------------------------------ 扩展：撤销
    def undo_move(self):
        if self.state != "PLAYING" or self.auto_running:
            return
        if not self.history:
            self.toast("没有可以撤销的操作", T.TEXT_SUB)
            return
        last = self.history.pop()
        if last["kind"] == "block":
            arrow = self.board[last["row"]][last["col"]]
            if arrow is not None:
                arrow.feedback = 0.0
            self.mistakes_left = min(self.total_mistakes, self.mistakes_left + 1)
            if self.mistakes_left > 0:
                self.pending_result = None
            self.toast("已撤销：恢复 1 次失误", T.HINT)
        else:
            self.board[last["row"]][last["col"]] = Arrow(last["direction"])
            self.remaining += 1
            fly = last.get("fly")
            if fly is not None and fly in self.flying:
                self.flying.remove(fly)
            if self.pending_result == "win":
                self.pending_result = None
            self.toast("已撤销：箭头回到棋盘", T.HINT)
        self.invalidate_solution()
        self.hint_cell = None

    # ------------------------------------------------------------ 交互
    def cell_rect(self, row, col):
        return pygame.Rect(self.board_rect.x + col * self.cell_size,
                           self.board_rect.y + row * self.cell_size,
                           self.cell_size, self.cell_size)

    def cell_at(self, pos):
        if not self.board_rect.collidepoint(pos):
            return None
        col = int((pos[0] - self.board_rect.x) // self.cell_size)
        row = int((pos[1] - self.board_rect.y) // self.cell_size)
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if self.board[row][col] is not None:
                return (row, col)
        return None

    def handle_board_click(self, pos):
        if self.pending_result is not None:
            return
        if self.auto_running:
            self.toast("AI 求解中，点击「停止求解」可接管操作", T.TEXT_SUB)
            return
        cell = self.cell_at(pos)
        if cell is None:
            return
        self.hint_cell = None
        self.try_clear(*cell)

    def try_clear(self, row, col, record=True):
        """点击处理。record=False 时不计入撤销历史（自动求解用）。"""
        arrow = self.board[row][col]
        if arrow is None:
            return False
        center = self.cell_rect(row, col).center
        direction = arrow.direction
        if is_blocked(self.logic_grid(), row, col, direction):
            # ---------------- 被阻挡 ----------------
            arrow.feedback = T.FEEDBACK_TIME
            self.mistakes_left = max(0, self.mistakes_left - 1)
            self.effects.burst(center, T.DANGER, count=14,
                               speed=(80, 260), life=(0.30, 0.65),
                               radius=(2, 5), gravity=420)
            self.effects.floating_text(
                (center[0], center[1] - self.cell_size * 0.42),
                "-1", T.DANGER, self.fonts["mid"])
            if record:
                self.history.append({
                    "kind": "block", "row": row, "col": col,
                    "direction": direction,
                })
            if self.mistakes_left <= 0:
                self.pending_result = "lose"
                self.lose_reason = "mistakes"
                self.result_timer = T.LOSE_DELAY
            return True
        # ---------------- 成功飞出 ----------------
        palette = T.ARROW_PALETTES.get(direction, T.ARROW_PALETTES["U"])
        self.effects.burst(center, palette["bottom"], count=9,
                           speed=(60, 210), life=(0.25, 0.50),
                           radius=(2, 4.5), gravity=260)
        self.board[row][col] = None
        self.remaining -= 1
        fly = FlyingArrow(center, direction, int(self.cell_size * 0.66),
                          math.hypot(T.WINDOW_WIDTH, T.WINDOW_HEIGHT))
        self.flying.append(fly)
        self.invalidate_solution()
        if record:
            self.history.append({
                "kind": "clear", "row": row, "col": col,
                "direction": direction, "fly": fly,
            })
        if self.remaining == 0:
            self.pending_result = "win"
            self.result_timer = T.WIN_DELAY
        return True

    # ------------------------------------------------------------ 事件
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "START":
                        self.running = False
                    else:
                        self.back_to_start()
                    continue
                if self.state == "PLAYING":
                    if event.key == pygame.K_r:
                        self.restart_level()
                        continue
                    if event.key == pygame.K_h:
                        self.show_hint()
                        continue
                    if event.key == pygame.K_z:
                        self.undo_move()
                        continue
                    if event.key == pygame.K_a:
                        self.toggle_auto()
                        continue
            if self._handle_button_event(event):
                continue
            if (self.state == "PLAYING"
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1):
                self.handle_board_click(event.pos)

    def _handle_button_event(self, event):
        if self.state in ("WIN", "LOSE") and self.overlay_t <= 0.35:
            return False
        for button in self.active_buttons:
            if button.process_event(event):
                return True
        return False

    # ------------------------------------------------------------ 更新
    def update(self, dt):
        mouse_pos = pygame.mouse.get_pos()
        self._sync_buttons()
        buttons_ready = (self.state not in ("WIN", "LOSE")) or self.overlay_t > 0.35
        if buttons_ready:
            for button in self.active_buttons:
                button.update(dt, mouse_pos)
        self.effects.update(dt)
        if self.toast_life > 0:
            self.toast_life = max(0.0, self.toast_life - dt)
        if self.state == "PLAYING":
            self._update_playing(dt)
        if self.state in ("WIN", "LOSE"):
            self.overlay_t = min(1.0, self.overlay_t + dt / 0.34)

    def _update_playing(self, dt):
        if self.pending_result is None:
            self.elapsed += dt
        # 超时判负：时间用尽且棋盘未清空
        if (self.pending_result is None and self.remaining > 0
                and self.par_time > 0 and self.elapsed >= self.par_time):
            self.pending_result = "lose"
            self.lose_reason = "timeout"
            self.result_timer = T.LOSE_DELAY
        # ---- 自动求解推进 ----
        if self.auto_running:
            if self.remaining == 0:
                self.stop_auto()
            else:
                self.auto_timer -= dt
                if self.auto_timer <= 0:
                    if self.auto_queue:
                        row, col, _ = self.auto_queue.pop(0)
                        self.try_clear(row, col, record=False)
                        self.auto_timer = T.AUTO_STEP_DELAY
                    else:
                        self.stop_auto("AI 求解结束")
        # ---- 碰撞反馈计时 ----
        for line in self.board:
            for arrow in line:
                if arrow is not None and arrow.feedback > 0:
                    arrow.feedback = max(0.0, arrow.feedback - dt)
        # ---- 飞出动画 ----
        for fly in self.flying:
            fly.update(dt)
            if random.random() < 0.55:
                palette = T.ARROW_PALETTES.get(fly.direction,
                                               T.ARROW_PALETTES["U"])
                self.effects.sparks(fly.position(), palette["bottom"], count=1)
        self.flying = [f for f in self.flying if not f.finished]
        # ---- 结算判定 ----
        if self.pending_result == "win":
            if not self.flying:
                self.result_timer -= dt
                if self.result_timer <= 0:
                    self.stars = compute_stars(
                        self.mistakes_left, self.total_mistakes,
                        self.elapsed, self.par_time,
                        hints_used=self.hints_used,
                        auto_used=self.auto_used)
                    self.pending_result = None
                    self.set_state("WIN")
        elif self.pending_result == "lose":
            self.result_timer -= dt
            if self.result_timer <= 0:
                self.pending_result = None
                self.set_state("LOSE")
        if self.pending_result is None and not self.auto_running:
            self.hover_cell = self.cell_at(pygame.mouse.get_pos())
        else:
            self.hover_cell = None

    # ------------------------------------------------------------ 绘制
    def draw(self):
        self.canvas.blit(self.background, (0, 0))
        if self.state == "START":
            self._draw_start()
        elif self.state == "LEVEL_SELECT":
            self._draw_level_select()
        else:
            self._draw_playfield()
            if self.state == "WIN":
                self._draw_result_overlay("win")
            elif self.state == "LOSE":
                self._draw_result_overlay("lose")
        self._draw_toast()
        self.window.blit(self.canvas, (0, 0))
        pygame.display.flip()

    # -------------------------------------------------- 开始界面
    def _draw_start(self):
        width = T.WINDOW_WIDTH
        cx = width // 2
        ticks = pygame.time.get_ticks() / 1000.0
        decorations = [
            ("U", 150, 180, 0.0),
            ("D", width - 150, 180, 1.3),
            ("L", 150, 470, 2.1),
            ("R", width - 150, 470, 0.7),
        ]
        for direction, x, y, phase in decorations:
            sprite = get_arrow_surface(direction, 72, direction).copy()
            sprite.set_alpha(46)
            offset = math.sin(ticks * 1.3 + phase) * 12
            self.canvas.blit(sprite, sprite.get_rect(center=(x, y + offset)))
        # 渐变金属标题 + 柔和投影
        title_shadow = self.fonts["title"].render(T.WINDOW_TITLE, True, (0, 0, 0))
        title_shadow.set_alpha(120)
        self.canvas.blit(title_shadow,
                         title_shadow.get_rect(center=(cx + 5, 159)))
        title = render_gradient_text(
            self.fonts["title"], T.WINDOW_TITLE,
            (226, 236, 255), (116, 150, 230))
        self.canvas.blit(title, title.get_rect(center=(cx, 154)))
        subtitle = self.fonts["normal"].render(
            "观察箭头方向与阻挡关系，按正确顺序清空棋盘", True, T.TEXT_SUB)
        self.canvas.blit(subtitle, subtitle.get_rect(center=(cx, 210)))
        card = pygame.Rect(cx - 300, 258, 600, 190)
        draw_round_panel(self.canvas, card, radius=18,
                         bg=T.PANEL_BG, border=T.PANEL_BORDER)
        rules_title = self.fonts["mid"].render("玩法说明", True, T.ACCENT)
        self.canvas.blit(rules_title,
                         rules_title.get_rect(center=(card.centerx, card.y + 34)))
        rules = [
            "点击箭头：若它到棋盘边界的路径上没有其他箭头，箭头飞出并消失。",
            "若前方有箭头阻挡，箭头会晃动变红，失误次数减 1。",
            "清空全部箭头即可过关；失误次数耗尽则本关失败。",
        ]
        for index, line in enumerate(rules):
            text = self.fonts["small"].render(line, True, T.TEXT_MAIN)
            self.canvas.blit(text, text.get_rect(
                center=(card.centerx, card.y + 76 + index * 34)))
        tips = self.fonts["tiny"].render(
            "关卡内快捷键：H 提示　Z 撤销　A 自动求解　R 重开　ESC 返回主页",
            True, T.TEXT_DIM)
        self.canvas.blit(tips, tips.get_rect(center=(cx, 600)))
        for button in self.active_buttons:
            button.draw(self.canvas)

    # -------------------------------------------------- 选关界面
    def _draw_level_select(self):
        width = T.WINDOW_WIDTH
        cx = width // 2
        title = render_gradient_text(
            self.fonts["title"], "选择关卡",
            (226, 236, 255), (116, 150, 230))
        self.canvas.blit(title, title.get_rect(center=(cx, 150)))
        sub = self.fonts["normal"].render(
            "点击任意关卡开始挑战", True, T.TEXT_SUB)
        self.canvas.blit(sub, sub.get_rect(center=(cx, 210)))
        for button in self.active_buttons:
            button.draw(self.canvas)
        for i, (rect, lv) in enumerate(self.level_card_rects):
            head = self.fonts["small"].render(
                f"第 {i + 1} 关", True, T.ACCENT)
            self.canvas.blit(head, head.get_rect(
                center=(rect.centerx, rect.top - 22)))
            n = sum(1 for line in lv["rows"] for ch in line if ch in "UDLR")
            stats = self.fonts["tiny"].render(
                f"{n} 箭头 · 限时 {int(lv['par_time'])}s", True, T.TEXT_DIM)
            self.canvas.blit(stats, stats.get_rect(
                center=(rect.centerx, rect.bottom + 18)))
        back = self.fonts["small"].render(
            "按 ESC 返回主页", True, T.TEXT_DIM)
        self.canvas.blit(back, back.get_rect(
            center=(cx, T.WINDOW_HEIGHT - 40)))

    # -------------------------------------------------- 游戏界面
    def _draw_playfield(self):
        width = T.WINDOW_WIDTH
        hud_top = T.TOP_BAR_H
        # ---- 顶栏：关卡徽章 + 功能按钮 ----
        badge_text = f"第 {self.level_index + 1} 关 / 共 {len(LEVELS)} 关"
        badge = self.fonts["small"].render(badge_text, True, T.TEXT_MAIN)
        badge_rect = pygame.Rect(22, 14, badge.get_width() + 36, 36)
        pygame.draw.rect(self.canvas, T.PANEL_BG, badge_rect, border_radius=18)
        pygame.draw.rect(self.canvas, T.PANEL_BORDER, badge_rect,
                         width=2, border_radius=18)
        self.canvas.blit(badge, badge.get_rect(center=badge_rect.center))
        name = LEVELS[self.level_index]["name"]
        name_text = self.fonts["small"].render(f"· {name}", True, T.TEXT_DIM)
        self.canvas.blit(name_text, name_text.get_rect(
            midleft=(badge_rect.right + 12, badge_rect.centery)))
        for button in self.active_buttons:
            button.draw(self.canvas)
        # ---- HUD：剩余箭头 + 进度条 ----
        info = self.fonts["normal"].render(
            f"剩余箭头 {self.remaining} / {self.initial_count}", True, T.TEXT_MAIN)
        self.canvas.blit(info, info.get_rect(midleft=(46, hud_top + 20)))
        bar = pygame.Rect(46, hud_top + 38, 200, 8)
        pygame.draw.rect(self.canvas, (46, 52, 82), bar, border_radius=4)
        if self.initial_count > 0:
            ratio = self.remaining / self.initial_count
            if ratio > 0:
                fill = pygame.Rect(bar.x, bar.y,
                                   max(8, int(bar.w * ratio)), bar.h)
                pygame.draw.rect(self.canvas, T.ACCENT, fill, border_radius=4)
        # ---- HUD：计时 + 时间条 ----
        over_par = self.elapsed > self.par_time
        time_text = f"用时 {format_time(self.elapsed)} / {format_time(self.par_time)}"
        time_color = T.DANGER if over_par else T.TEXT_SUB
        draw_text_with_shadow(
            self.canvas, self.fonts["normal"], time_text, time_color,
            (width // 2, hud_top + 24), shadow=(0, 0, 0),
            offset=1, shadow_alpha=120)
        # 时间条：随时间消耗而缩短，剩余越少越红
        time_bar = pygame.Rect(width // 2 - 110, hud_top + 40, 220, 8)
        pygame.draw.rect(self.canvas, (46, 52, 82), time_bar, border_radius=4)
        remain = (max(0.0, 1.0 - self.elapsed / self.par_time)
                  if self.par_time > 0 else 0.0)
        if remain > 0:
            if over_par or remain < 0.25:
                tcolor = T.DANGER
            elif remain < 0.5:
                tcolor = T.ACCENT
            else:
                tcolor = T.SUCCESS
            fill = pygame.Rect(time_bar.x, time_bar.y,
                               max(8, int(time_bar.w * remain)), time_bar.h)
            pygame.draw.rect(self.canvas, tcolor, fill, border_radius=4)
        # ---- HUD：失误心形 ----
        heart_size, gap = 26, 8
        total_w = (self.total_mistakes * heart_size
                   + max(0, self.total_mistakes - 1) * gap)
        right_x = width - 46
        label = self.fonts["normal"].render("失误", True, T.TEXT_SUB)
        self.canvas.blit(label, label.get_rect(
            midright=(right_x - total_w - 14, hud_top + 24)))
        for index in range(self.total_mistakes):
            x = right_x - total_w + index * (heart_size + gap) + heart_size / 2
            color = T.HEART_ON if index < self.mistakes_left else T.HEART_OFF
            heart = get_heart_surface(heart_size, color)
            self.canvas.blit(heart, heart.get_rect(center=(x, hud_top + 24)))
        # ---- 棋盘 ----
        panel = self.board_rect.inflate(T.BOARD_PADDING * 2, T.BOARD_PADDING * 2)
        draw_round_panel(self.canvas, panel, radius=22,
                         bg=T.BOARD_BG, border=(58, 68, 104))
        pygame.draw.rect(self.canvas, T.BOARD_INNER, self.board_rect,
                         border_radius=14)
        for row in range(1, self.rows):
            y = self.board_rect.y + row * self.cell_size
            pygame.draw.line(self.canvas, T.BOARD_GRID,
                             (self.board_rect.x + 10, y),
                             (self.board_rect.right - 10, y))
        for col in range(1, self.cols):
            x = self.board_rect.x + col * self.cell_size
            pygame.draw.line(self.canvas, T.BOARD_GRID,
                             (x, self.board_rect.y + 10),
                             (x, self.board_rect.bottom - 10))
        if self.hover_cell is not None:
            rect = self.cell_rect(*self.hover_cell).inflate(-8, -8)
            glow = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 255, 255, 20), glow.get_rect(),
                             border_radius=12)
            self.canvas.blit(glow, rect.topleft)
        self._draw_hint()
        for row in range(self.rows):
            for col in range(self.cols):
                arrow = self.board[row][col]
                if arrow is not None:
                    self._draw_arrow(row, col, arrow)
        for fly in self.flying:
            fly.draw(self.canvas)
        self.effects.draw(self.canvas)
        hint = self.fonts["tiny"].render(
            "提示：先处理路径通畅的箭头，再逐步解开阻挡链",
            True, T.TEXT_DIM)
        self.canvas.blit(hint, hint.get_rect(
            center=(width // 2, T.WINDOW_HEIGHT - 26)))

    def _draw_hint(self):
        """提示高亮：呼吸光圈，画在箭头下方。"""
        if self.hint_cell is None:
            return
        row, col = self.hint_cell
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            self.hint_cell = None
            return
        if self.board[row][col] is None:
            self.hint_cell = None
            return
        rect = self.cell_rect(row, col).inflate(-6, -6)
        pulse = (math.sin(pygame.time.get_ticks() / 1000.0 * 5.0) + 1.0) / 2.0
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        fill_alpha = int(38 + 54 * pulse)
        pygame.draw.rect(layer, (*T.HINT, fill_alpha), layer.get_rect(),
                         border_radius=14)
        pygame.draw.rect(layer, (*T.HINT, 225), layer.get_rect(),
                         width=3, border_radius=14)
        self.canvas.blit(layer, rect.topleft)

    def _draw_arrow(self, row, col, arrow):
        size = int(self.cell_size * 0.66)
        center_x, center_y = self.cell_rect(row, col).center
        if arrow.feedback > 0:
            ratio = arrow.feedback / T.FEEDBACK_TIME
            offset = math.sin(arrow.feedback * 46.0) * self.cell_size * 0.08 * ratio
            palette = "X"
        else:
            offset = 0.0
            palette = arrow.direction
        sprite = get_arrow_surface(arrow.direction, size, palette)
        self.canvas.blit(sprite,
                         sprite.get_rect(center=(center_x + offset, center_y)))

    # -------------------------------------------------- 结算界面
    def _draw_result_overlay(self, kind):
        progress = ease_out_cubic(self.overlay_t)
        shade = pygame.Surface((T.WINDOW_WIDTH, T.WINDOW_HEIGHT), pygame.SRCALPHA)
        shade.fill((6, 8, 16, int(205 * progress)))
        self.canvas.blit(shade, (0, 0))
        panel_w, panel_h = 470, 380
        rise = int((1.0 - progress) * 40)
        center = (T.WINDOW_WIDTH // 2, T.WINDOW_HEIGHT // 2 + rise)
        layer = pygame.Surface((panel_w + 80, panel_h + 80), pygame.SRCALPHA)
        local = pygame.Rect(40, 40, panel_w, panel_h)
        draw_round_panel(layer, local, radius=24,
                         bg=T.PANEL_BG, border=T.PANEL_BORDER)
        has_next = self.level_index + 1 < len(LEVELS)
        if kind == "win":
            title_text = "关卡完成！" if has_next else "全部通关！"
            title_color = T.SUCCESS
            used = self.total_mistakes - self.mistakes_left
            line1 = (f"用时 {format_time(self.elapsed)}　"
                     f"失误 {used} / {self.total_mistakes}")
            if self.auto_used:
                line2 = "本关由 AI 自动求解完成"
            elif self.hints_used:
                line2 = f"本关使用了 {self.hints_used} 次提示"
            else:
                line2 = ("点击「下一关」继续挑战" if has_next
                         else "你已通关全部关卡")
        else:
            title_text = "挑战失败"
            title_color = T.DANGER
            if self.lose_reason == "timeout":
                line1 = f"时间用尽，还剩 {self.remaining} 个箭头未消除"
                line2 = "点击「重新开始」再来一次，动作再快一点"
            else:
                line1 = f"本关还剩 {self.remaining} 个箭头"
                line2 = "失误次数已耗尽，点击「重新开始」再来一次"
        # ---- 渐变标题 ----
        if kind == "win":
            grad_top, grad_bottom = (206, 246, 224), (82, 219, 162)
        else:
            grad_top, grad_bottom = (255, 186, 196), (238, 91, 108)
        title_shadow = self.fonts["big"].render(title_text, True, (0, 0, 0))
        title_shadow.set_alpha(110)
        layer.blit(title_shadow,
                   title_shadow.get_rect(center=(local.centerx + 3,
                                                 local.y + 85)))
        title = render_gradient_text(self.fonts["big"], title_text,
                                    grad_top, grad_bottom)
        layer.blit(title, title.get_rect(center=(local.centerx, local.y + 82)))
        # ---- 星级 ----
        for index in range(3):
            filled = index < self.stars
            sprite = get_star_surface(46, filled)
            x = local.centerx + (index - 1) * 60
            layer.blit(sprite, sprite.get_rect(center=(x, local.y + 140)))
        # ---- 分隔线 ----
        pygame.draw.line(layer, (58, 66, 100),
                         (local.centerx - 95, local.y + 186),
                         (local.centerx + 95, local.y + 186), 2)
        text1 = self.fonts["normal"].render(line1, True, T.TEXT_MAIN)
        layer.blit(text1, text1.get_rect(center=(local.centerx, local.y + 222)))
        text2 = self.fonts["small"].render(line2, True, T.TEXT_SUB)
        layer.blit(text2, text2.get_rect(center=(local.centerx, local.y + 260)))
        layer.set_alpha(int(255 * progress))
        self.canvas.blit(layer, layer.get_rect(center=center))
        if self.overlay_t > 0.35:
            for button in self.active_buttons:
                button.draw(self.canvas)

    # -------------------------------------------------- 提示条
    def _draw_toast(self):
        if self.toast_life <= 0 or not self.toast_text:
            return
        fade = min(1.0, self.toast_life / 0.45)
        surface = self.fonts["small"].render(self.toast_text, True, self.toast_color)
        surface.set_alpha(int(255 * fade))
        rect = surface.get_rect(
            center=(T.WINDOW_WIDTH // 2, T.WINDOW_HEIGHT - 64))
        box = rect.inflate(34, 18)
        panel = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*T.TOAST_BG, int(210 * fade)),
                         panel.get_rect(), border_radius=12)
        pygame.draw.rect(panel, (*T.PANEL_BORDER, int(200 * fade)),
                         panel.get_rect(), width=2, border_radius=12)
        self.canvas.blit(panel, box.topleft)
        self.canvas.blit(surface, rect)

    # ------------------------------------------------------------ 主循环
    def run(self):
        while self.running:
            dt = min(self.clock.tick(T.FPS) / 1000.0, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
