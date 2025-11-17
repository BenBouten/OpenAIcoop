"""Modern floating window that visualises population statistics."""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import pygame

from .window_chrome import WindowChrome, draw_resize_grip


class StatsWindow:
    """Display the aggregated stats that previously lived in the legacy UI."""

    def __init__(self, body_font: pygame.font.Font, heading_font: pygame.font.Font) -> None:
        self.font = body_font
        self.heading_font = heading_font
        self.rect = pygame.Rect(24, 24, 360, 440)
        self._chrome = WindowChrome(self.rect, min_size=(320, 320))
        self._header_height = 60
        self._stats: Optional[Dict[str, object]] = None

    def update_stats(self, stats: Dict[str, object]) -> None:
        self._stats = stats

    def clear(self) -> None:
        self._stats = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self._stats:
            return False
        consumed = False
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            chrome_consumed, _ = self._chrome.handle_event(event, self._header_rect())
            consumed = chrome_consumed
        return consumed

    def draw(self, surface: pygame.Surface) -> None:
        if not self._stats:
            return

        self._chrome.clamp_to_display()

        panel_surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        panel_surface.fill((250, 250, 250, 235))
        surface.blit(panel_surface, self.rect.topleft)
        pygame.draw.rect(surface, (70, 70, 70), self.rect, 1, border_radius=12)

        heading = self.heading_font.render("Populatiestatistieken", True, (40, 40, 40))
        surface.blit(
            heading,
            (
                self.rect.centerx - heading.get_width() // 2,
                self.rect.top + 16,
            ),
        )

        summary_lines = self._summary_lines()
        available_height = max(120, self.rect.height - 140)
        line_height = self.font.get_linesize()
        lines_per_column = max(1, available_height // line_height)
        column_count = max(1, math.ceil(len(summary_lines) / lines_per_column))
        column_width = max(140, (self.rect.width - 32) // column_count)

        for idx, line in enumerate(summary_lines):
            column = idx // lines_per_column
            row = idx % lines_per_column
            x = self.rect.left + 16 + column * column_width
            y = self.rect.top + 70 + row * line_height
            text_surface = self.font.render(line, True, (30, 30, 30))
            surface.blit(text_surface, (x, y))

        dna_lines = self._dna_lines()
        if dna_lines:
            dna_heading_y = self.rect.top + 70 + lines_per_column * line_height + 12
            heading_surface = self.font.render("DNA verdeling", True, (60, 60, 60))
            surface.blit(heading_surface, (self.rect.left + 16, dna_heading_y))
            y_offset = dna_heading_y + heading_surface.get_height() + 4
            for line in dna_lines:
                text_surface = self.font.render(line, True, (70, 70, 70))
                surface.blit(text_surface, (self.rect.left + 24, y_offset))
                y_offset += line_height

        draw_resize_grip(surface, self._chrome)

    def _summary_lines(self) -> List[str]:
        stats = self._stats or {}
        dna_total = stats.get('dna_count', {})
        total_dna = len(dna_total) if isinstance(dna_total, dict) else 0
        lines = [
            f"Lifeforms totaal: {int(stats.get('lifeform_count', 0))}",
            f"Tijd verlopen: {stats.get('formatted_time', '00:00')}",
            f"Gem. gezondheid: {int(stats.get('average_health', 0))}",
            f"Gem. zicht: {int(stats.get('average_vision', 0))}",
            f"Gem. generatie: {int(stats.get('average_gen', 0))}",
            f"Gem. honger: {int(stats.get('average_hunger', 0))}",
            f"Gem. grootte: {int(stats.get('average_size', 0))}",
            f"Gem. leeftijd: {int(stats.get('average_age', 0))}",
            f"Gem. leeftijd overlijden: {int(stats.get('death_age_avg', 0))}",
            f"Gem. volwassen: {int(stats.get('average_maturity', 0))}",
            f"Gem. snelheid: {self._format_float(stats.get('average_speed', 0), 2)}",
            f"Gem. massa: {self._format_float(stats.get('average_mass', 0), 2)}",
            f"Gem. fys. massa: {self._format_float(stats.get('average_body_mass', 0), 1)}",
            f"Gem. reikwijdte: {self._format_float(stats.get('average_reach', 0), 2)}",
            f"Gem. onderhoud: {self._format_float(stats.get('average_maintenance_cost', 0), 3)}",
            f"Gem. fys. onderhoud: {self._format_float(stats.get('average_body_energy_cost', 0), 3)}",
            f"Gem. sensoren: {self._format_float(stats.get('average_perception_rays', 0), 1)}",
            f"Gem. gehoor: {self._format_float(stats.get('average_hearing_range', 0), 1)}",
            f"Gem. modules: {self._format_float(stats.get('average_module_count', 0), 1)}",
            f"Gem. drag: {self._format_float(stats.get('average_drag', 0), 2)}",
            f"Gem. thrust: {self._format_float(stats.get('average_max_thrust', 0), 1)}",
            f"Gem. cooldown: {self._format_float(stats.get('average_cooldown', 0), 1)}",
            f"Aantal DNA-profielen: {total_dna}",
        ]
        return lines

    def _dna_lines(self) -> List[str]:
        stats = self._stats or {}
        dna_count = stats.get('dna_count', {})
        if not isinstance(dna_count, dict) or not dna_count:
            return []
        sorted_counts = sorted(dna_count.items(), key=lambda item: item[1], reverse=True)
        return [f"dna_{dna_id}: {count}" for dna_id, count in sorted_counts]

    def _format_float(self, value: object, digits: int) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        return f"{numeric:.{digits}f}"

    def _header_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left,
            self.rect.top,
            self.rect.width,
            self._header_height,
        )
