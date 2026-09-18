"""通用绘制工具与 UI 组件。"""
import math
import pygame
import theme as T

# ---------------------------------------------------------------- 颜色
def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


def make_vertical_gradient(size, top_color, bottom_color, alpha=255):
    """生成纵向渐变表面。"""
    width, height = size
    height = max(1, height)
    strip = pygame.Surface((1, height), pygame.SRCALPHA)
    for y in range(height):
        t = y / (height - 1) if height > 1 else 0.0
        color = lerp_color(top_color, bottom_color, t)
        strip.set_at((0, y), (*color, alpha))
    return pygame.transform.scale(strip, (width, height))


# ---------------------------------------------------------------- 缓动
def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t, s=1.70158):
    t = max(0.0, min(1.0, t))
    return 1.0 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


# ---------------------------------------------------------------- 字体
_FONT_CACHE = {}
_FONT_NAMES = (
    "microsoftyaheiui,microsoftyahei,simhei,pingfangsc,hiraginosansgb,"
    "notosanscjksc,sourcehansanssc,wqymicrohei,arialunicodems"
)


def load_font(size, bold=False):
    key = (size, bold)
    font = _FONT_CACHE.get(key)
    if font is not None:
        return font
    path = pygame.font.match_font(_FONT_NAMES)
    font = pygame.font.Font(path, size) if path else pygame.font.Font(None, size)
    font.set_bold(bold)
    _FONT_CACHE[key] = font
    return font


# ---------------------------------------------------------------- 面板
def draw_round_panel(surface, rect, radius=16, bg=None, border=None,
                     shadow_alpha=80, border_width=2):
    bg = T.PANEL_BG if bg is None else bg
    border = T.PANEL_BORDER if border is None else border
    if shadow_alpha > 0:
        pygame.draw.rect(surface, (0, 0, 0, shadow_alpha), rect.move(0, 5),
                         border_radius=radius)
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    if border and border_width > 0:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


# ---------------------------------------------------------------- 箭头
def arrow_polygon(size, direction):
    """返回以原点为中心、外接正方形边长为 size 的箭头多边形。"""
    half = size / 2.0
    shaft_w = size * 0.30
    head_w = size * 0.62
    head_len = size * 0.40
    shaft_len = size - head_len
    base = [
        (-half, -shaft_w / 2),
        (-half + shaft_len, -shaft_w / 2),
        (-half + shaft_len, -head_w / 2),
        (half, 0.0),
        (-half + shaft_len, head_w / 2),
        (-half + shaft_len, shaft_w / 2),
        (-half, shaft_w / 2),
    ]
    if direction == 'R':
        return base
    if direction == 'L':
        return [(-x, -y) for x, y in base]
    if direction == 'D':
        return [(-y, x) for x, y in base]
    return [(y, -x) for x, y in base]


_ARROW_CACHE = {}
def get_arrow_surface(direction, size, palette_key=None):
    """带缓存的箭头表面。4 倍超采样 + smoothscale 获得平滑边缘。"""
    size = max(8, int(size))
    key = (direction, size, palette_key or direction)
    surface = _ARROW_CACHE.get(key)
    if surface is None:
        surface = _render_arrow(direction, size, palette_key or direction)
        _ARROW_CACHE[key] = surface
    return surface


def _render_arrow(direction, size, palette_key):
    ss = 4
    big = size * ss
    palette = T.ARROW_PALETTES.get(palette_key, T.ARROW_PALETTES['U'])
    layer = pygame.Surface((big, big), pygame.SRCALPHA)
    center = big / 2.0
    points = [(center + x, center + y)
              for x, y in arrow_polygon(big * 0.80, direction)]
    # 投影
    shadow = [(x + big * 0.014, y + big * 0.036) for x, y in points]
    pygame.draw.polygon(layer, (0, 0, 0, 84), shadow)
    # 渐变主体：用遮罩把渐变裁成箭头形状
    gradient = make_vertical_gradient((big, big), palette['top'], palette['bottom'])
    mask = pygame.Surface((big, big), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), points)
    gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    layer.blit(gradient, (0, 0))
    # 描边
    pygame.draw.polygon(layer, (*palette['edge'], 235), points,
                        width=max(2, int(big * 0.015)))
    return pygame.transform.smoothscale(layer, (size, size))


# ---------------------------------------------------------------- 心形
_HEART_CACHE = {}
def get_heart_surface(size, color):
    size = max(8, int(size))
    key = (size, tuple(color))
    surface = _HEART_CACHE.get(key)
    if surface is None:
        surface = _render_heart(size, color)
        _HEART_CACHE[key] = surface
    return surface


def _render_heart(size, color):
    ss = 4
    big = size * ss
    layer = pygame.Surface((big, big), pygame.SRCALPHA)
    radius = big * 0.25
    cx = big / 2.0
    cy = big * 0.40
    pygame.draw.circle(layer, color, (int(cx - radius * 0.86), int(cy)), int(radius))
    pygame.draw.circle(layer, color, (int(cx + radius * 0.86), int(cy)), int(radius))
    pygame.draw.polygon(layer, color, [
        (cx - radius * 1.80, cy + radius * 0.20),
        (cx + radius * 1.80, cy + radius * 0.20),
        (cx, big * 0.94),
    ])
    return pygame.transform.smoothscale(layer, (size, size))


# ---------------------------------------------------------------- 按钮
class Button:
    """圆角按钮：阴影 + 悬停变色 + 顶部高光 + 禁用态。"""
    def __init__(self, rect, text, font, callback, style='primary', radius=12):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.callback = callback
        self.style = style
        self.radius = radius
        self.hover = 0.0
        self.enabled = True

    def update(self, dt, mouse_pos):
        target = 1.0 if (self.enabled and self.rect.collidepoint(mouse_pos)) else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 16.0)

    def process_event(self, event):
        if not self.enabled:
            return False
        if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                and self.rect.collidepoint(event.pos)):
            self.callback()
            return True
        return False

    def draw(self, surface):
        if not self.enabled:
            base = T.BTN_DISABLED
            edge = T.BTN_DISABLED_EDGE
            label_color = T.TEXT_DISABLED
        else:
            if self.style == 'primary':
                base = lerp_color(T.BTN_PRIMARY, T.BTN_PRIMARY_HOVER, self.hover)
                edge = lerp_color(T.BTN_PRIMARY_EDGE, (186, 206, 255), self.hover)
            else:
                base = lerp_color(T.BTN_SECONDARY, T.BTN_SECONDARY_HOVER, self.hover)
                edge = lerp_color(T.BTN_SECONDARY_EDGE, (140, 152, 196), self.hover)
            label_color = (250, 252, 255)
        rect = self.rect
        pygame.draw.rect(surface, (0, 0, 0, 80), rect.move(0, 4),
                         border_radius=self.radius)
        pygame.draw.rect(surface, base, rect, border_radius=self.radius)
        gloss = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6,
                            max(1, rect.h // 2 - 5))
        gloss_layer = pygame.Surface(gloss.size, pygame.SRCALPHA)
        pygame.draw.rect(gloss_layer, (255, 255, 255, 26), gloss_layer.get_rect(),
                         border_radius=max(1, self.radius - 4))
        surface.blit(gloss_layer, gloss.topleft)
        pygame.draw.rect(surface, edge, rect, width=2, border_radius=self.radius)
        label = self.font.render(self.text, True, label_color)
        surface.blit(label, label.get_rect(center=rect.center))


# ---------------------------------------------------------------- 辉光
_GLOW_CACHE = {}


def get_glow_surface(diameter, color):
    """返回径向渐变（中心亮、边缘透明）的辉光表面，直径 diameter。"""
    diameter = max(8, int(diameter))
    key = (diameter, tuple(color))
    surface = _GLOW_CACHE.get(key)
    if surface is None:
        radius = diameter // 2
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        steps = 18
        for i in range(steps, 0, -1):
            r = max(1, int(radius * i / steps))
            alpha = int(80 * (1 - i / steps) ** 2)
            pygame.draw.circle(surface, (*color, alpha), (radius, radius), r)
        _GLOW_CACHE[key] = surface
    return surface


def blit_glow(surface, center, diameter, color):
    """在 center 处画一团径向辉光。"""
    sprite = get_glow_surface(diameter, color)
    surface.blit(sprite, sprite.get_rect(center=center))


# ---------------------------------------------------------------- 星形
_STAR_CACHE = {}


def get_star_surface(size, filled=True):
    size = max(10, int(size))
    key = (size, bool(filled))
    surface = _STAR_CACHE.get(key)
    if surface is None:
        surface = _render_star(size, filled)
        _STAR_CACHE[key] = surface
    return surface


def _star_points(size):
    cx = cy = size / 2.0
    outer = size * 0.47
    inner = outer * 0.42
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5
        points.append((cx + math.cos(angle) * radius,
                       cy + math.sin(angle) * radius))
    return points


def _render_star(size, filled):
    ss = 4
    big = size * ss
    layer = pygame.Surface((big, big), pygame.SRCALPHA)
    points = _star_points(big)
    shadow = [(x, y + big * 0.035) for x, y in points]
    pygame.draw.polygon(layer, (0, 0, 0, 90), shadow)
    if filled:
        gradient = make_vertical_gradient((big, big), T.STAR_TOP, T.STAR_BOTTOM)
        mask = pygame.Surface((big, big), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), points)
        gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        layer.blit(gradient, (0, 0))
        pygame.draw.polygon(layer, (*T.STAR_EDGE, 240), points,
                            width=max(2, int(big * 0.016)))
    else:
        pygame.draw.polygon(layer, (48, 54, 80, 215), points)
        pygame.draw.polygon(layer, (78, 86, 118, 235), points,
                            width=max(2, int(big * 0.016)))
    return pygame.transform.smoothscale(layer, (size, size))


# ---------------------------------------------------------------- 文字
def render_gradient_text(font, text, top_color, bottom_color):
    """用纵向渐变填充文字（金属/高级标题效果），返回透明背景表面。"""
    base = font.render(text, True, (255, 255, 255)).convert_alpha()
    gradient = make_vertical_gradient(base.get_size(), top_color, bottom_color)
    gradient.blit(base, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return gradient


def draw_text_with_shadow(surface, font, text, color, center,
                          shadow=(0, 0, 0), offset=2, shadow_alpha=140):
    """带投影的文字，提升在渐变背景上的可读性。"""
    sh = font.render(text, True, shadow)
    sh.set_alpha(shadow_alpha)
    surface.blit(sh, sh.get_rect(center=(center[0] + offset, center[1] + offset)))
    main = font.render(text, True, color)
    surface.blit(main, main.get_rect(center=center))
