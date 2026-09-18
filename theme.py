"""主题配置：颜色、尺寸、字体与手感参数。"""
import math  # noqa: F401  (保留给后续扩展)
# ---------------- 窗口 ----------------
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 720
FPS = 60
WINDOW_TITLE = "一箭又一箭"

# ---------------- 颜色 ----------------
BG_TOP = (31, 36, 60)
BG_BOTTOM = (13, 15, 26)
TEXT_MAIN = (238, 241, 250)
TEXT_SUB = (152, 162, 194)
TEXT_DIM = (104, 114, 146)
PANEL_BG = (37, 42, 66)
PANEL_BORDER = (64, 72, 108)
BOARD_BG = (33, 38, 60)
BOARD_INNER = (25, 29, 46)
BOARD_GRID = (46, 52, 80)
BTN_PRIMARY = (88, 118, 232)
BTN_PRIMARY_HOVER = (116, 148, 255)
BTN_PRIMARY_EDGE = (132, 162, 255)
BTN_SECONDARY = (54, 62, 96)
BTN_SECONDARY_HOVER = (76, 86, 128)
BTN_SECONDARY_EDGE = (100, 112, 158)
BTN_DISABLED = (40, 44, 66)
BTN_DISABLED_EDGE = (58, 64, 92)
TEXT_DISABLED = (124, 132, 162)
ACCENT = (255, 199, 89)
DANGER = (238, 91, 108)
SUCCESS = (82, 219, 162)
HINT = (118, 214, 255)
HEART_ON = (250, 112, 138)
HEART_OFF = (62, 68, 100)
STAR_TOP = (255, 226, 130)
STAR_BOTTOM = (247, 178, 46)
STAR_EDGE = (168, 112, 16)
TOAST_BG = (14, 17, 30)

# ---------------- 箭头调色板 ----------------
ARROW_PALETTES = {
    'U': {'top': (152, 222, 250), 'bottom': (72, 168, 226), 'edge': (32, 100, 148)},
    'D': {'top': (250, 180, 198), 'bottom': (228, 96, 132), 'edge': (140, 44, 76)},
    'L': {'top': (255, 234, 164), 'bottom': (245, 188, 66), 'edge': (158, 116, 24)},
    'R': {'top': (152, 246, 210), 'bottom': (44, 200, 152), 'edge': (18, 118, 90)},
    'X': {'top': (255, 162, 162), 'bottom': (224, 74, 92), 'edge': (128, 28, 44)},
}

# ---------------- 布局 ----------------
TOP_BAR_H = 64
HUD_H = 52
BOARD_MAX_CELL = 118
BOARD_MIN_CELL = 64
BOARD_PADDING = 22

# ---------------- 手感参数 ----------------
FEEDBACK_TIME = 0.42     # 碰撞晃动持续时间
FLY_TIME = 0.44          # 飞出动画持续时间
WIN_DELAY = 0.50         # 清空后延迟弹结算
LOSE_DELAY = 0.90        # 失误耗尽后延迟弹结算
AUTO_STEP_DELAY = 0.55   # 自动求解每步间隔
TOAST_TIME = 1.80        # 提示条停留时间
