"""Overlay panel for inspecting and logging individual lifeforms."""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import pygame

from ..config import settings

if TYPE_CHECKING:  # pragma: no cover - imported for type hints only
    from ..entities.lifeform import Lifeform
    from ..rendering.camera import Camera
    from ..systems.notifications import NotificationManager
    from ..simulation.state import SimulationState


logger = logging.getLogger("evolution.simulation")


class LifeformInspector:
    """Manage selection, rendering and logging of a focused lifeform."""

    def __init__(
        self,
        state: "SimulationState",
        body_font: pygame.font.Font,
        heading_font: pygame.font.Font,
    ) -> None:
        self._state = state
        self._body_font = body_font
        self._heading_font = heading_font
        self._selected: Optional["Lifeform"] = None
        self._panel_rect = pygame.Rect(0, 0, 420, 420)
        self._debug_button = pygame.Rect(0, 0, 160, 36)
        self._close_button = pygame.Rect(0, 0, 24, 24)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    @property
    def selected(self) -> Optional["Lifeform"]:
        return self._selected

    def select(self, lifeform: Optional["Lifeform"]) -> None:
        if lifeform is not None and lifeform.health_now <= 0:
            lifeform = None
        self._selected = lifeform
        self._state.selected_lifeform = lifeform

    def clear(self) -> None:
        self.select(None)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._selected is None:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_button.collidepoint(event.pos):
                self.clear()
                return True
            if self._debug_button.collidepoint(event.pos):
                self._write_debug_log()
                return True
            if not self._panel_rect.collidepoint(event.pos):
                # Let the caller handle potential selection changes.
                self.clear()
                return False

        return False

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def draw_highlight(self, surface: pygame.Surface, camera: "Camera") -> None:
        lifeform = self._selected
        if lifeform is None:
            return
        if lifeform.health_now <= 0 or lifeform not in self._state.lifeforms:
            self.clear()
            return

        center = (
            int(lifeform.rect.centerx - camera.viewport.x),
            int(lifeform.rect.centery - camera.viewport.y),
        )
        if not (0 <= center[0] < surface.get_width() and 0 <= center[1] < surface.get_height()):
            return

        radius = max(lifeform.width, lifeform.height) + 18
        pygame.draw.circle(surface, (255, 200, 40), center, radius, 2)
        pygame.draw.circle(surface, (30, 30, 30), center, radius + 2, 1)

    def draw(self, surface: pygame.Surface) -> None:
        lifeform = self._selected
        if lifeform is None:
            return
        if lifeform.health_now <= 0 or lifeform not in self._state.lifeforms:
            self.clear()
            return

        width = min(self._panel_rect.width, surface.get_width() - 80)
        height = min(self._panel_rect.height + 60, surface.get_height() - 80)
        left = surface.get_width() // 2 - width // 2
        top = surface.get_height() // 2 - height // 2
        self._panel_rect = pygame.Rect(left, top, width, height)

        overlay = pygame.Surface(self._panel_rect.size, pygame.SRCALPHA)
        overlay.fill((255, 255, 255, 235))
        surface.blit(overlay, self._panel_rect.topleft)
        pygame.draw.rect(surface, (40, 40, 40), self._panel_rect, 2, border_radius=12)

        heading = self._heading_font.render("Lifeform-informatie", True, (30, 30, 30))
        heading_pos = (
            self._panel_rect.left + (self._panel_rect.width - heading.get_width()) // 2,
            self._panel_rect.top + 18,
        )
        surface.blit(heading, heading_pos)

        self._close_button = pygame.Rect(
            self._panel_rect.right - 36,
            self._panel_rect.top + 18,
            20,
            20,
        )
        pygame.draw.rect(surface, (180, 70, 70), self._close_button, border_radius=4)
        pygame.draw.rect(surface, (60, 30, 30), self._close_button, 1, border_radius=4)
        close_label = self._body_font.render("X", True, (255, 255, 255))
        surface.blit(
            close_label,
            (
                self._close_button.x + (self._close_button.width - close_label.get_width()) // 2,
                self._close_button.y + (self._close_button.height - close_label.get_height()) // 2,
            ),
        )

        preview_rect = pygame.Rect(
            self._panel_rect.left + 24,
            self._panel_rect.top + 64,
            120,
            120,
        )
        pygame.draw.rect(surface, (240, 240, 240), preview_rect, border_radius=12)
        pygame.draw.rect(surface, (180, 180, 180), preview_rect, 1, border_radius=12)
        body_center = (
            preview_rect.x + preview_rect.width // 2,
            preview_rect.y + preview_rect.height // 2,
        )
        body_radius = min(preview_rect.width, preview_rect.height) // 3
        pygame.draw.circle(surface, lifeform.color, body_center, body_radius)
        pygame.draw.circle(surface, (50, 50, 50), body_center, body_radius + 1, 1)

        text_start_x = preview_rect.right + 20
        text_y = preview_rect.top

        def _render_line(label: str, value: str) -> None:
            nonlocal text_y
            text_surface = self._body_font.render(f"{label}: {value}", True, (30, 30, 30))
            surface.blit(text_surface, (text_start_x, text_y))
            text_y += text_surface.get_height() + 4

        _render_line("ID", lifeform.id)
        _render_line("DNA", str(lifeform.dna_id))
        _render_line("Generatie", str(lifeform.generation))
        _render_line("Leeftijd", f"{lifeform.age:.0f} / {lifeform.longevity}")
        _render_line("Gezondheid", f"{lifeform.health_now:.0f} / {lifeform.health}")
        _render_line("Energie", f"{lifeform.energy_now:.0f} / {lifeform.energy}")
        _render_line("Honger", f"{lifeform.hunger:.0f}")
        _render_line("Snelheid", f"{lifeform.speed:.2f}")
        _render_line("Massa", f"{lifeform.mass:.2f}")
        _render_line("Visie", f"{lifeform.vision:.1f}")

        text_y += 6
        targets = {
            "Prooi": getattr(getattr(lifeform, "closest_prey", None), "id", None),
            "Vijand": getattr(getattr(lifeform, "closest_enemy", None), "id", None),
            "Partner": getattr(getattr(lifeform, "closest_partner", None), "id", None),
        }
        for label, value in targets.items():
            _render_line(label, value or "-" )

        text_y += 6
        position = f"({lifeform.rect.centerx:.0f}, {lifeform.rect.centery:.0f})"
        biome = getattr(lifeform.current_biome, "name", "onbekend")
        _render_line("Positie", position)
        _render_line("Biome", biome)

        self._debug_button = pygame.Rect(
            self._panel_rect.left + 24,
            self._panel_rect.bottom - 70,
            self._panel_rect.width - 48,
            44,
        )
        pygame.draw.rect(surface, (70, 120, 200), self._debug_button, border_radius=8)
        pygame.draw.rect(surface, (40, 60, 100), self._debug_button, 2, border_radius=8)
        button_label = self._heading_font.render("Maak debug log", True, (255, 255, 255))
        surface.blit(
            button_label,
            (
                self._debug_button.x + (self._debug_button.width - button_label.get_width()) // 2,
                self._debug_button.y + (self._debug_button.height - button_label.get_height()) // 2,
            ),
        )

        log_hint_y = self._debug_button.bottom + 10
        last_path = self._state.last_debug_log_path
        hint_text = "Laatste log: " + (Path(last_path).name if last_path else "geen")
        hint_surface = self._body_font.render(hint_text, True, (60, 60, 60))
        surface.blit(hint_surface, (self._panel_rect.left + 24, log_hint_y))

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _write_debug_log(self) -> None:
        lifeform = self._selected
        if lifeform is None:
            return

        log_dir = Path(settings.LOG_DIRECTORY)
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lifeform_{lifeform.id}_{timestamp}.json"
        log_path = log_dir / filename

        payload = {
            "generated_at": timestamp,
            "world_type": getattr(self._state, "world_type", None),
            "lifeform": lifeform.debug_snapshot(),
        }

        with log_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)

        self._state.last_debug_log_path = str(log_path)

        notifications: Optional["NotificationManager"] = self._state.notifications
        if notifications:
            notifications.add(
                f"Debug log opgeslagen: {log_path.name}",
                settings.SEA,
                duration=settings.FPS * 4,
            )

        logger.info("Lifeform debug log geschreven naar %s", log_path)
