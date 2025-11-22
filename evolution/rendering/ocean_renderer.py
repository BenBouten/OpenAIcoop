"""
Lightweight deep-ocean background renderer.

- Smooth gradient van oppervlakte naar abyss.
- Subtiele (optionele) scanlines.
- Zachtere godrays over de breedte, geen keiharde witte wig.
- Golven aan de oppervlakte.
- Glow helper voor rad vents & bioluminescente dingen.
"""

from __future__ import annotations

import math
import random
from typing import Tuple

import pygame

Color = Tuple[int, int, int]


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(a: Color, b: Color, t: float) -> Color:
    return (
        int(lerp(a[0], b[0], t)),
        int(lerp(a[1], b[1], t)),
        int(lerp(a[2], b[2], t)),
    )


class OceanRenderer:
    def __init__(self, world_width: int, world_height: int) -> None:
        self.w = world_width
        self.h = world_height

        # Eén grote achtergrond (gradient + optionele scanlines + godrays)
        self._static_bg: pygame.Surface = pygame.Surface((self.w, self.h)).convert()

        # Smalle strook voor golven
        self._wave_surface: pygame.Surface = pygame.Surface(
            (self.w, 80),
            pygame.SRCALPHA,
        )

        # Kleine glow-sprite voor vents / bioluminescentie
        self._base_glow: pygame.Surface = self._build_base_glow(72)

        self._build_static_background()

    # ------------------------------------------------------------------ #
    #  BUILD BACKGROUND
    # ------------------------------------------------------------------ #

    def _build_static_background(self) -> None:
        """Bouw een mooie oceaan: gradient + zachte godrays + subtiele scanlines."""

        bg = self._static_bg

        # 1) Verticale gradient
        self._fill_gradient(bg)

        # 2) Overlay: scanlines + godrays op een aparte surface
        overlay = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._add_scanlines(overlay)   # zet deze uit door regel te commenten
        self._add_godrays(overlay)

        # 3) Gewone alpha-blit (GEEN additive meer → geen witte vlakken)
        bg.blit(overlay, (0, 0))

    def _fill_gradient(self, target: pygame.Surface) -> None:
        """Diepe gradient van bright surface naar abyss."""
        h = self.h

        top_color = (118, 212, 233)   # helder cyaan
        mid_color = (34, 118, 176)    # sunlit
        deep_color = (14, 40, 76)     # midnight
        abyss_color = (2, 6, 18)      # abyss

        for y in range(h):
            t = y / max(1, h - 1)
            if t < 0.18:
                color = lerp_color(top_color, mid_color, t / 0.18)
            elif t < 0.55:
                color = lerp_color(mid_color, deep_color, (t - 0.18) / 0.37)
            else:
                color = lerp_color(deep_color, abyss_color, (t - 0.55) / 0.45)
            pygame.draw.line(target, color, (0, y), (self.w, y))

    def _add_scanlines(self, overlay: pygame.Surface) -> None:
        """
        Subtiele horizontale lijnen voor een retro vibe.

        Wil je ze helemaal weg? Comment deze hele functie-aanroep
        in _build_static_background() uit.
        """
        interval = 12
        alpha = 6  # heel zacht
        color = (255, 255, 255, alpha)

        rng = random.Random(42)
        for y in range(0, self.h, interval):
            # Kleine jitter in begin/eindpunt zodat het niet "hard" oogt
            jitter = rng.randint(-6, 6)
            start_x = max(0, jitter)
            end_x = min(self.w, self.w + jitter)
            pygame.draw.line(overlay, color, (start_x, y), (end_x, y))

    def _add_godrays(self, overlay: pygame.Surface) -> None:
        """
        Lichtstralen die van boven door het water vallen.

        - Verspreid over de hele breedte.
        - Lage alpha, meerdere overlappende stralen.
        - Naar beneden toe vervagen.
        """
        rng = random.Random(1337)
        ray_count = 9

        for i in range(ray_count):
            # Elke ray eigen horizontale start
            base_x = rng.randint(int(self.w * 0.05), int(self.w * 0.95))
            length = self.h * rng.uniform(0.55, 0.9)
            top_width = rng.randint(80, 180)
            bottom_width = int(top_width * rng.uniform(0.4, 0.7))
            base_angle = rng.uniform(-0.18, 0.18)

            # iets andere kleur per ray, heel zacht
            base_alpha = rng.randint(18, 28)
            color = (240, 250, 255, base_alpha)

            # we tekenen de ray als meerdere "segment-polygons" voor wat breking
            segments = 6
            prev_center_x = base_x
            prev_y = 0
            prev_half = top_width / 2

            for s in range(segments):
                t0 = s / segments
                t1 = (s + 1) / segments
                y0 = t0 * length
                y1 = t1 * length

                # center x verschuift een beetje sinusachtig → gebroken door water
                offset0 = math.sin(base_angle * 8 + t0 * 6.0 + i) * 30
                offset1 = math.sin(base_angle * 8 + t1 * 6.0 + i) * 30
                cx0 = base_x + offset0
                cx1 = base_x + offset1

                # breedte loopt af naar beneden
                half0 = lerp(top_width / 2, bottom_width / 2, t0)
                half1 = lerp(top_width / 2, bottom_width / 2, t1)

                poly = [
                    (cx0 - half0, y0),
                    (cx0 + half0, y0),
                    (cx1 + half1, y1),
                    (cx1 - half1, y1),
                ]

                pygame.draw.polygon(overlay, color, poly)

                prev_center_x, prev_y, prev_half = cx1, y1, half1

        # Naar beneden toe zwakker
        fade = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for y in range(self.h):
            t = y / max(1, self.h - 1)
            a = int(255 * (1.0 - t) ** 2)
            pygame.draw.line(fade, (255, 255, 255, a), (0, y), (self.w, y))
        overlay.blit(fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    def _build_base_glow(self, size: int) -> pygame.Surface:
        """Maak een radiale witte glow die later gekleurd kan worden."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size // 2
        r = size // 2
        for radius in range(r, 0, -1):
            t = radius / r
            alpha = int(255 * (1.0 - t) ** 2)
            pygame.draw.circle(surf, (255, 255, 255, alpha), (cx, cy), radius)
        return surf

    # ------------------------------------------------------------------ #
    #  PUBLIC DRAW API
    # ------------------------------------------------------------------ #

    def draw_background(self, surface: pygame.Surface, time_s: float) -> None:
        """
        Teken de volledige oceaanachtergrond op de wereldsurface.

        surface is hier je world_surface (WORLD_WIDTH x WORLD_HEIGHT).
        """
        surface.blit(self._static_bg, (0, 0))
        self._draw_waves(surface, time_s)

    def _draw_waves(self, surface: pygame.Surface, time_s: float) -> None:
        """Golven op de oppervlakte (y ≈ 0)."""
        wave = self._wave_surface
        wave.fill((0, 0, 0, 0))

        base_y = 40
        amp1 = 10
        amp2 = 6

        w = wave.get_width()
        for x in range(w):
            y1 = base_y + math.sin(x * 0.02 + time_s * 1.8) * amp1
            y2 = base_y + math.sin(x * 0.037 + time_s * 2.3 + 1.7) * amp2
            y = int((y1 + y2) * 0.5)

            pygame.draw.line(wave, (255, 255, 255, 170), (x, y), (x, y + 3))
            pygame.draw.line(wave, (215, 250, 255, 110), (x, y), (x, y + 7))

        # Plak op y=0 van de wereld
        surface.blit(wave, (0, 0))

    def draw_rad_vent(self, surface: pygame.Surface, center: Tuple[int, int],
                      radius: int, color: Color, intensity: float) -> None:
        """
        Tekent een pulserende rad-vent glow op world-coördinaten.

        surface = world_surface (world coords)
        center  = (x, y) in world coords
        radius  = straal in pixels
        color   = vent kleur
        intensity = 0..1
        """
        radius = max(18, radius)
        size = radius * 2

        glow = pygame.transform.smoothscale(self._base_glow, (size, size))
        glow.fill((*color, 0), special_flags=pygame.BLEND_RGBA_MULT)

        intensity = max(0.0, min(1.0, intensity))
        if intensity < 0.999:
            alpha_mod = pygame.Surface((size, size), pygame.SRCALPHA)
            alpha_mod.fill((255, 255, 255, int(255 * intensity)))
            glow.blit(alpha_mod, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        x, y = center
        surface.blit(
            glow,
            (x - radius, y - radius),
            special_flags=pygame.BLEND_ADD,
        )
