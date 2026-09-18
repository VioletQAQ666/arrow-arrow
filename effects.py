"""粒子与飘字效果。"""
import math
import random
import pygame
import theme as T

MAX_PARTICLES = 420
AMBIENT_TARGET = 24


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "total", "color",
                 "radius", "gravity", "drag")

    def __init__(self, x, y, vx, vy, life, color, radius, gravity=0.0, drag=0.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.total = life
        self.color = color
        self.radius = radius
        self.gravity = gravity
        self.drag = drag

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            return False
        damp = max(0.0, 1.0 - self.drag * dt)
        self.vx *= damp
        self.vy *= damp
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return True

    def draw(self, surface):
        ratio = self.life / self.total
        alpha = int(255 * min(1.0, ratio * 2.0))
        radius = max(1, int(self.radius * (0.4 + 0.6 * ratio)))
        size = radius * 2
        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(sprite, (*self.color, alpha), (radius, radius), radius)
        surface.blit(sprite, (self.x - radius, self.y - radius))


class FloatingText:
    def __init__(self, x, y, text, color, font, life=0.85):
        self.x = x
        self.y = y
        self.life = life
        self.total = life
        self.surface = font.render(text, True, color)

    def update(self, dt):
        self.life -= dt
        self.y -= 46 * dt
        return self.life > 0

    def draw(self, surface):
        ratio = max(0.0, self.life / self.total)
        self.surface.set_alpha(int(255 * min(1.0, ratio * 1.8)))
        surface.blit(self.surface, self.surface.get_rect(center=(self.x, self.y)))


class Effects:
    """统一管理粒子与飘字。"""
    def __init__(self):
        self.particles = []
        self.texts = []
        self.ambient = []
        self._ambient_timer = 0.0

    def clear(self):
        self.particles.clear()
        self.texts.clear()

    def _append(self, particle):
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(particle)

    def burst(self, pos, color, count=12, speed=(70, 240), life=(0.28, 0.62),
              radius=(2, 5), gravity=380, drag=1.2):
        x, y = pos
        for _ in range(count):
            angle = random.uniform(0.0, math.tau)
            velocity = random.uniform(*speed)
            self._append(Particle(
                x, y,
                math.cos(angle) * velocity,
                math.sin(angle) * velocity,
                random.uniform(*life),
                color,
                random.uniform(*radius),
                gravity=gravity,
                drag=drag,
            ))

    def sparks(self, pos, color, count=4):
        x, y = pos
        for _ in range(count):
            angle = random.uniform(0.0, math.tau)
            velocity = random.uniform(25, 90)
            self._append(Particle(
                x, y,
                math.cos(angle) * velocity,
                math.sin(angle) * velocity,
                random.uniform(0.20, 0.42),
                color,
                random.uniform(1.5, 3.2),
                gravity=120,
                drag=1.6,
            ))

    def floating_text(self, pos, text, color, font):
        self.texts.append(FloatingText(pos[0], pos[1], text, color, font))

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]

    def draw(self, surface):
        for particle in self.particles:
            particle.draw(surface)
        for text in self.texts:
            text.draw(surface)

    # ---------------- 背景漂浮光尘 ----------------
    def update_ambient(self, dt, width, height):
        self._ambient_timer -= dt
        if self._ambient_timer <= 0 and len(self.ambient) < AMBIENT_TARGET:
            self._ambient_timer = random.uniform(0.25, 0.7)
            self.ambient.append({
                "x": random.uniform(0, width),
                "y": random.uniform(0, height),
                "vx": random.uniform(-9, 9),
                "vy": random.uniform(-18, -7),
                "r": random.uniform(1.4, 3.4),
                "a": random.randint(16, 44),
            })
        for p in self.ambient:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["y"] < -10:
                p["y"] = height + 10
                p["x"] = random.uniform(0, width)
            if p["x"] < -10:
                p["x"] = width + 10
            elif p["x"] > width + 10:
                p["x"] = -10

    def draw_ambient(self, surface):
        for p in self.ambient:
            pygame.draw.circle(
                surface, (*T.AMBIENT_COLOR, p["a"]),
                (int(p["x"]), int(p["y"])), int(p["r"]))
