"""Lightweight editor tool panel for world-building interactions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence, Tuple

import pygame

from ..world.types import BiomeRegion
from .window_chrome import WindowChrome, draw_resize_grip


class EditorTool(Enum):
    """Enumeration of the supported editor interactions."""

    INSPECT = "inspect"
    SPAWN_MOSS = "spawn_moss"
    PAINT_MOSS = "paint_moss"
    PAINT_WALL = "paint_wall"
    DRAW_BARRIER = "draw_barrier"
    PAINT_BIOME = "paint_biome"


@dataclass
class _ToolEntry:
    tool: EditorTool
    label: str
    rect: pygame.Rect


@dataclass
class _BrushEntry:
    size: int
    label: str
    rect: pygame.Rect


@dataclass
class _BiomeEntry:
    name: str
    color: Tuple[int, int, int]
    template: BiomeRegion


class ToolsPanel:
    """Small helper panel for selecting editor tools and brush sizes."""

    def __init__(
        self,
        font: pygame.font.Font,
        heading_font: pygame.font.Font,
        *,
        topleft: Tuple[int, int] = (24, 24),
        available_biomes: Optional[Sequence[BiomeRegion]] = None,
    ) -> None:
        self.font = font
        self.heading_font = heading_font
        self.rect = pygame.Rect(topleft[0], topleft[1], 280, 360)
        self._chrome = WindowChrome(self.rect, min_size=(260, 320))
        self.visible = True
        self.selected_tool: EditorTool = EditorTool.INSPECT
        self.brush_size: int = 48
        self._header_height = 64

        self._tool_buttons: List[_ToolEntry] = []
        self._brush_buttons: List[_BrushEntry] = []
        self._hide_button = pygame.Rect(0, 0, 24, 24)
        self._show_button = pygame.Rect(self.rect.left, self.rect.top, 120, 32)
        self._biome_prev_button = pygame.Rect(0, 0, 28, 28)
        self._biome_next_button = pygame.Rect(0, 0, 28, 28)
        self._biome_display_rect = pygame.Rect(0, 0, 140, 32)
        self._biome_entries: List[_BiomeEntry] = []
        self._selected_biome_index = 0
        self.set_biomes(available_biomes or [])
        self._build_layout()

    def set_biomes(self, biomes: Sequence[BiomeRegion]) -> None:
        unique: List[_BiomeEntry] = []
        seen: set[str] = set()
        for biome in biomes:
            key = biome.name.lower()
            if key in seen:
                continue
            unique.append(_BiomeEntry(biome.name, biome.color, biome))
            seen.add(key)
        if unique:
            self._biome_entries = unique
            self._selected_biome_index = min(
                self._selected_biome_index, len(self._biome_entries) - 1
            )

    def get_selected_biome(self) -> Optional[BiomeRegion]:
        if not self._biome_entries:
            return None
        return self._biome_entries[self._selected_biome_index].template

    def _cycle_biome(self, step: int) -> None:
        if not self._biome_entries:
            return
        self._selected_biome_index = (self._selected_biome_index + step) % len(
            self._biome_entries
        )

    def _build_layout(self) -> None:
        button_height = 34
        y_offset = self.rect.top + 62
        labels: Sequence[Tuple[EditorTool, str]] = (
            (EditorTool.INSPECT, "Inspectie"),
            (EditorTool.SPAWN_MOSS, "Mos spawnen"),
            (EditorTool.PAINT_MOSS, "Mos verven"),
            (EditorTool.PAINT_WALL, "Muur verven"),
            (EditorTool.DRAW_BARRIER, "Barrière kader"),
            (EditorTool.PAINT_BIOME, "Biome verven"),
        )
        self._tool_buttons = []
        for tool, label in labels:
            rect = pygame.Rect(self.rect.left + 18, y_offset, self.rect.width - 36, button_height)
            self._tool_buttons.append(_ToolEntry(tool, label, rect))
            y_offset += button_height + 8

        bottom_margin = 24
        biome_section_height = 64
        brush_section_height = 60
        brush_y = self.rect.bottom - (biome_section_height + brush_section_height + bottom_margin)
        brush_width = max(60, (self.rect.width - 48) // 3)
        brush_labels: Sequence[Tuple[int, str]] = ((28, "Klein"), (48, "Normaal"), (78, "Groot"))
        self._brush_buttons = []
        for idx, (size, label) in enumerate(brush_labels):
            rect = pygame.Rect(
                self.rect.left + 18 + idx * (brush_width + 6),
                brush_y,
                brush_width,
                30,
            )
            self._brush_buttons.append(_BrushEntry(size, label, rect))

        biome_y = self.rect.bottom - (biome_section_height + bottom_margin)
        self._biome_prev_button = pygame.Rect(self.rect.left + 18, biome_y + 24, 28, 28)
        self._biome_next_button = pygame.Rect(self.rect.right - 46, biome_y + 24, 28, 28)
        self._biome_display_rect = pygame.Rect(
            self._biome_prev_button.right + 8,
            biome_y + 20,
            self.rect.width - 36 - self._biome_prev_button.width * 2 - 16,
            36,
        )

        self._hide_button = pygame.Rect(self.rect.right - 34, self.rect.top + 18, 20, 20)
        self._show_button = pygame.Rect(self.rect.left, self.rect.top, 140, 36)

    def _header_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.left, self.rect.top, self.rect.width, self._header_height)

    def _handle_geometry_change(self) -> None:
        self._build_layout()

    def contains_point(self, pos: Tuple[int, int]) -> bool:
        if self.visible:
            return self.rect.collidepoint(pos)
        return self._show_button.collidepoint(pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.visible:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._hide_button.collidepoint(event.pos):
                    self.visible = False
                    return True
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                chrome_consumed, geometry_changed = self._chrome.handle_event(
                    event, self._header_rect()
                )
                if geometry_changed:
                    self._handle_geometry_change()
                if chrome_consumed:
                    return True
            if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                return False
            if not self.rect.collidepoint(event.pos):
                return False
            for button in self._tool_buttons:
                if button.rect.collidepoint(event.pos):
                    self.selected_tool = button.tool
                    return True
            for entry in self._brush_buttons:
                if entry.rect.collidepoint(event.pos):
                    self.brush_size = entry.size
                    return True
            if self._biome_prev_button.collidepoint(event.pos):
                self._cycle_biome(-1)
                return True
            if self._biome_next_button.collidepoint(event.pos):
                self._cycle_biome(1)
                return True
        else:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self._show_button.collidepoint(event.pos):
                    self.visible = True
                    self._chrome.mark_geometry_dirty()
                    return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            pygame.draw.rect(surface, (235, 235, 235), self._show_button, border_radius=6)
            pygame.draw.rect(surface, (70, 70, 70), self._show_button, 1, border_radius=6)
            label = self.font.render("Tools tonen", True, (30, 30, 30))
            surface.blit(
                label,
                (
                    self._show_button.centerx - label.get_width() // 2,
                    self._show_button.centery - label.get_height() // 2,
                ),
            )
            return

        overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 235))
        surface.blit(overlay, self.rect.topleft)
        pygame.draw.rect(surface, (40, 40, 40), self.rect, 1, border_radius=10)

        heading = self.heading_font.render("Bouwtools", True, (30, 30, 30))
        surface.blit(
            heading,
            (
                self.rect.centerx - heading.get_width() // 2,
                self.rect.top + 16,
            ),
        )

        pygame.draw.rect(surface, (200, 80, 80), self._hide_button, border_radius=4)
        pygame.draw.rect(surface, (60, 30, 30), self._hide_button, 1, border_radius=4)
        close_label = self.font.render("×", True, (255, 255, 255))
        surface.blit(
            close_label,
            (
                self._hide_button.centerx - close_label.get_width() // 2,
                self._hide_button.centery - close_label.get_height() // 2,
            ),
        )

        for button in self._tool_buttons:
            color = (90, 160, 120) if button.tool == self.selected_tool else (230, 230, 230)
            border = (40, 80, 60) if button.tool == self.selected_tool else (120, 120, 120)
            pygame.draw.rect(surface, color, button.rect, border_radius=6)
            pygame.draw.rect(surface, border, button.rect, 1, border_radius=6)
            label = self.font.render(button.label, True, (30, 30, 30))
            surface.blit(
                label,
                (button.rect.left + 10, button.rect.centery - label.get_height() // 2),
            )

        brush_heading = self.font.render("Kwastgrootte", True, (30, 30, 30))
        surface.blit(brush_heading, (self.rect.left + 18, self.rect.bottom - 88 - 36))
        for entry in self._brush_buttons:
            color = (80, 140, 190) if entry.size == self.brush_size else (230, 230, 230)
            border = (40, 70, 120) if entry.size == self.brush_size else (120, 120, 120)
            pygame.draw.rect(surface, color, entry.rect, border_radius=6)
            pygame.draw.rect(surface, border, entry.rect, 1, border_radius=6)
            label = self.font.render(entry.label, True, (30, 30, 30))
            surface.blit(
                label,
                (
                    entry.rect.centerx - label.get_width() // 2,
                    entry.rect.centery - label.get_height() // 2,
                ),
            )

        biome_heading = self.font.render("Biome selectie", True, (30, 30, 30))
        surface.blit(biome_heading, (self.rect.left + 18, self._biome_display_rect.top - 24))

        pygame.draw.rect(surface, (230, 230, 230), self._biome_prev_button, border_radius=6)
        pygame.draw.rect(surface, (120, 120, 120), self._biome_prev_button, 1, border_radius=6)
        pygame.draw.polygon(
            surface,
            (50, 50, 50),
            [
                (self._biome_prev_button.centerx + 4, self._biome_prev_button.top + 6),
                (self._biome_prev_button.centerx + 4, self._biome_prev_button.bottom - 6),
                (self._biome_prev_button.centerx - 4, self._biome_prev_button.centery),
            ],
        )

        pygame.draw.rect(surface, (230, 230, 230), self._biome_next_button, border_radius=6)
        pygame.draw.rect(surface, (120, 120, 120), self._biome_next_button, 1, border_radius=6)
        pygame.draw.polygon(
            surface,
            (50, 50, 50),
            [
                (self._biome_next_button.centerx - 4, self._biome_next_button.top + 6),
                (self._biome_next_button.centerx - 4, self._biome_next_button.bottom - 6),
                (self._biome_next_button.centerx + 4, self._biome_next_button.centery),
            ],
        )

        pygame.draw.rect(surface, (245, 245, 245), self._biome_display_rect, border_radius=8)
        pygame.draw.rect(surface, (120, 120, 120), self._biome_display_rect, 1, border_radius=8)
        if self._biome_entries:
            current = self._biome_entries[self._selected_biome_index]
            swatch_rect = pygame.Rect(
                self._biome_display_rect.left + 8,
                self._biome_display_rect.top + 6,
                24,
                self._biome_display_rect.height - 12,
            )
            pygame.draw.rect(surface, current.color, swatch_rect, border_radius=4)
            pygame.draw.rect(surface, (60, 60, 60), swatch_rect, 1, border_radius=4)
            label = self.font.render(current.name, True, (30, 30, 30))
            surface.blit(
                label,
                (
                    swatch_rect.right + 8,
                    self._biome_display_rect.centery - label.get_height() // 2,
                ),
            )
        else:
            placeholder = self.font.render("Geen biomes", True, (120, 120, 120))
            surface.blit(
                placeholder,
                (
                    self._biome_display_rect.centerx - placeholder.get_width() // 2,
                    self._biome_display_rect.centery - placeholder.get_height() // 2,
                ),
            )

        draw_resize_grip(surface, self._chrome)
