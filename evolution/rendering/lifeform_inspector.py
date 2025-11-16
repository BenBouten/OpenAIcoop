"""Overlay panel for inspecting and logging individual lifeforms."""

from __future__ import annotations

import datetime as _dt
import json
import logging
import math
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

import pygame

from ..config import settings
from ..dna.development import describe_feature, describe_skin_stage
from .window_chrome import WindowChrome, draw_resize_grip

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
        self._panel_rect = pygame.Rect(80, 80, 640, 520)
        self._debug_button = pygame.Rect(0, 0, 160, 36)
        self._close_button = pygame.Rect(0, 0, 24, 24)
        self._hover_entries: List[Tuple[pygame.Rect, List[str]]] = []
        self._chrome = WindowChrome(self._panel_rect, min_size=(420, 360))
        self._header_height = 70

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
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            chrome_consumed, _ = self._chrome.handle_event(event, self._header_rect())
            if chrome_consumed:
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._panel_rect.collidepoint(event.pos):
                self.clear()
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

        center = camera.world_to_screen((lifeform.rect.centerx, lifeform.rect.centery))
        if not (0 <= center[0] < surface.get_width() and 0 <= center[1] < surface.get_height()):
            return

        radius = int((max(lifeform.width, lifeform.height) + 18) * camera.zoom)
        pygame.draw.circle(surface, (255, 200, 40), center, radius, 2)
        pygame.draw.circle(surface, (30, 30, 30), center, radius + 2, 1)

    def draw(self, surface: pygame.Surface) -> None:
        lifeform = self._selected
        if lifeform is None:
            return
        if lifeform.health_now <= 0 or lifeform not in self._state.lifeforms:
            self.clear()
            return

        preview_surface = self._capture_preview(surface, lifeform)

        self._chrome.clamp_to_display()

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

        self._hover_entries = []

        usable_width = self._panel_rect.width - 48
        preview_size = max(140, min(220, usable_width // 2))
        preview_rect = pygame.Rect(
            self._panel_rect.left + 24,
            self._panel_rect.top + 64,
            preview_size,
            preview_size,
        )
        pygame.draw.rect(surface, (235, 236, 240), preview_rect, border_radius=16)
        pygame.draw.rect(surface, (160, 160, 160), preview_rect, 1, border_radius=16)
        if preview_surface:
            scaled_preview = pygame.transform.smoothscale(preview_surface, preview_rect.size)
            surface.blit(scaled_preview, preview_rect)
        else:
            body_center = (
                preview_rect.x + preview_rect.width // 2,
                preview_rect.y + preview_rect.height // 2,
            )
            body_radius = min(preview_rect.width, preview_rect.height) // 3
            pygame.draw.circle(surface, lifeform.color, body_center, body_radius)
            pygame.draw.circle(surface, (50, 50, 50), body_center, body_radius + 1, 1)

        info_x = preview_rect.right + 24
        info_y = preview_rect.top

        def _render_line(label: str, value: str, tooltip: Optional[List[str]] = None) -> pygame.Rect:
            nonlocal info_y
            text_surface = self._body_font.render(f"{label}: {value}", True, (30, 30, 30))
            surface.blit(text_surface, (info_x, info_y))
            rect = pygame.Rect(info_x, info_y, text_surface.get_width(), text_surface.get_height())
            if tooltip:
                self._register_tooltip(rect, tooltip)
            info_y += text_surface.get_height() + 4
            return rect

        age_tooltip = [
            f"Volwassen op: {lifeform.maturity}",
            f"Levensverwachting: {lifeform.longevity}",
        ]
        position = f"({lifeform.rect.centerx:.0f}, {lifeform.rect.centery:.0f})"
        biome_name = getattr(lifeform.current_biome, "name", "onbekend") or "onbekend"
        weather = lifeform.environment_effects
        weather_tooltip = [
            f"Weer: {weather.get('weather_name', '-')}",
            f"Temperatuur: {weather.get('temperature', '?')}°C",
            f"Neerslag: {weather.get('precipitation', '-')}",
        ]
        last_activity_value, last_activity_tooltip = self._last_activity_summary(lifeform)

        _render_line("ID", lifeform.id)
        _render_line("DNA", str(lifeform.dna_id))
        _render_line("Generatie", str(lifeform.generation))
        _render_line("Leeftijd", f"{lifeform.age:.1f} / {lifeform.longevity}", age_tooltip)
        _render_line("Positie", position)
        _render_line("Biome", biome_name, weather_tooltip)
        _render_line("Laatste gebeurtenis", last_activity_value, last_activity_tooltip)

        activity_title, activity_details = self._activity_summary(lifeform)
        _render_line("Huidige actie", activity_title)
        for detail in activity_details:
            detail_surface = self._body_font.render(f"• {detail}", True, (70, 70, 70))
            surface.blit(detail_surface, (info_x + 12, info_y))
            info_y += detail_surface.get_height() + 2

        content_left = self._panel_rect.left + 24
        section_top = max(preview_rect.bottom, info_y) + 18
        section_top = self._render_section_heading(surface, "Kernstatistieken", content_left, section_top)

        stats_tooltips = self._build_stat_tooltips(lifeform)
        stats_left_x = content_left
        stats_right_x = self._panel_rect.left + self._panel_rect.width // 2 + 12
        stats_y_left = section_top
        stats_y_right = section_top

        def _render_stat(
            x: int,
            y: int,
            label: str,
            value: str,
            tooltip_key: str,
        ) -> int:
            text_surface = self._body_font.render(f"{label}: {value}", True, (30, 30, 30))
            surface.blit(text_surface, (x, y))
            rect = pygame.Rect(x, y, text_surface.get_width(), text_surface.get_height())
            self._register_tooltip(rect, stats_tooltips.get(tooltip_key))
            return y + text_surface.get_height() + 4

        stats_y_left = _render_stat(
            stats_left_x,
            stats_y_left,
            "Gezondheid",
            f"{lifeform.health_now:.0f} / {lifeform.health}",
            "health",
        )
        stats_y_left = _render_stat(
            stats_left_x,
            stats_y_left,
            "Energie",
            f"{lifeform.energy_now:.0f} / {lifeform.energy}",
            "energy",
        )
        stats_y_left = _render_stat(
            stats_left_x,
            stats_y_left,
            "Honger",
            f"{lifeform.hunger:.0f}",
            "hunger",
        )
        stats_y_left = _render_stat(
            stats_left_x,
            stats_y_left,
            "Dieet",
            self._format_diet_value(lifeform),
            "diet",
        )
        stats_y_left = _render_stat(
            stats_left_x,
            stats_y_left,
            "Leeftijd",
            f"{lifeform.age:.1f}",
            "age",
        )

        stats_y_right = _render_stat(
            stats_right_x,
            stats_y_right,
            "Aanval",
            f"{lifeform.attack_power_now:.1f}",
            "attack",
        )
        stats_y_right = _render_stat(
            stats_right_x,
            stats_y_right,
            "Verdediging",
            f"{lifeform.defence_power_now:.1f}",
            "defence",
        )
        stats_y_right = _render_stat(
            stats_right_x,
            stats_y_right,
            "Snelheid",
            f"{lifeform.speed:.2f}",
            "speed",
        )
        stats_y_right = _render_stat(
            stats_right_x,
            stats_y_right,
            "Zicht",
            f"{lifeform.vision:.1f}",
            "vision",
        )

        stats_bottom = max(stats_y_left, stats_y_right)

        env_top = stats_bottom + 12
        env_top = self._render_section_heading(surface, "Omgeving & sociaal", content_left, env_top)
        for line in self._environment_lines(lifeform):
            text_surface = self._body_font.render(line, True, (60, 60, 60))
            surface.blit(text_surface, (content_left, env_top))
            env_top += text_surface.get_height() + 2

        memory_top = env_top + 12
        memory_top = self._render_section_heading(surface, "Geheugen", content_left, memory_top)
        self._render_memory(surface, content_left, memory_top, lifeform)

        self._debug_button = pygame.Rect(
            self._panel_rect.left + 24,
            self._panel_rect.bottom - 80,
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

        draw_resize_grip(surface, self._chrome)
        self._draw_tooltip(surface)

    def _header_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self._panel_rect.left,
            self._panel_rect.top,
            self._panel_rect.width,
            self._header_height,
        )

    # ------------------------------------------------------------------
    # Detail helpers
    # ------------------------------------------------------------------

    def _register_tooltip(
        self, rect: pygame.Rect, lines: Optional[List[str]]
    ) -> None:
        if not lines:
            return
        if rect.width <= 0 or rect.height <= 0:
            return
        expanded = rect.inflate(6, 4)
        self._hover_entries.append((expanded, [str(line) for line in lines]))

    def _draw_tooltip(self, surface: pygame.Surface) -> None:
        if not self._hover_entries:
            return

        mouse_pos = pygame.mouse.get_pos()
        tooltip: Optional[List[str]] = None
        for rect, lines in reversed(self._hover_entries):
            if rect.collidepoint(mouse_pos):
                tooltip = lines
                break

        if not tooltip:
            return

        rendered = [self._body_font.render(line, True, (255, 255, 255)) for line in tooltip]
        width = max(160, max(text.get_width() for text in rendered) + 16)
        height = sum(text.get_height() for text in rendered) + 16 + max(0, (len(rendered) - 1) * 2)

        tooltip_rect = pygame.Rect(mouse_pos[0] + 16, mouse_pos[1] + 16, width, height)
        if tooltip_rect.right > surface.get_width():
            tooltip_rect.x = mouse_pos[0] - width - 16
        if tooltip_rect.bottom > surface.get_height():
            tooltip_rect.y = mouse_pos[1] - height - 16

        box = pygame.Surface((tooltip_rect.width, tooltip_rect.height), pygame.SRCALPHA)
        box.fill((30, 34, 46, 235))
        surface.blit(box, tooltip_rect.topleft)

        text_y = tooltip_rect.y + 8
        for text in rendered:
            surface.blit(text, (tooltip_rect.x + 8, text_y))
            text_y += text.get_height() + 2

    def _render_section_heading(
        self, surface: pygame.Surface, text: str, x: int, y: int
    ) -> int:
        heading = self._heading_font.render(text, True, (45, 70, 120))
        surface.blit(heading, (x, y))
        underline_y = y + heading.get_height() + 2
        pygame.draw.line(
            surface,
            (185, 185, 190),
            (x, underline_y),
            (self._panel_rect.right - 24, underline_y),
            1,
        )
        return underline_y + 6

    def _capture_preview(
        self, surface: pygame.Surface, lifeform: "Lifeform"
    ) -> Optional[pygame.Surface]:
        camera = getattr(self._state, "camera", None)
        if camera is None:
            return None

        sample_side = 180
        center_x, center_y = camera.world_to_screen(
            (lifeform.rect.centerx, lifeform.rect.centery)
        )
        source_rect = pygame.Rect(
            center_x - sample_side // 2,
            center_y - sample_side // 2,
            sample_side,
            sample_side,
        )
        screen_rect = surface.get_rect()
        if not source_rect.colliderect(screen_rect):
            return None

        clip_rect = source_rect.clip(screen_rect)
        preview = pygame.Surface((sample_side, sample_side))
        world = getattr(self._state, "world", None)
        if world is not None:
            preview.fill(world.background_color)
        else:
            preview.fill((228, 222, 208))

        try:
            region = surface.subsurface(clip_rect).copy()
        except ValueError:
            return None

        destination = (clip_rect.x - source_rect.x, clip_rect.y - source_rect.y)
        preview.blit(region, destination)
        pygame.draw.rect(preview, (255, 255, 255), preview.get_rect(), 6)
        crosshair = (sample_side // 2, sample_side // 2)
        pygame.draw.circle(preview, (255, 210, 120), crosshair, 6, 2)
        return preview

    def _activity_summary(self, lifeform: "Lifeform") -> Tuple[str, List[str]]:
        if lifeform.health_now <= 0:
            return "Overleden", ["Geen activiteit; het wezen is gestorven."]

        details: List[str] = []
        enemy = getattr(lifeform, "closest_enemy", None)
        if getattr(lifeform, "_escape_timer", 0) > 0:
            if enemy and enemy.health_now > 0:
                details.append(f"Ontsnapt aan {enemy.id}")
            else:
                details.append("Noodmanoeuvre actief")
            return "Vluchten", details

        if enemy and enemy.health_now > 0:
            relation = "In gevecht"
            if lifeform.attack_power_now < enemy.attack_power_now:
                relation = "Vluchten"
            verb = "met" if relation == "In gevecht" else "voor"
            details.append(f"{relation} {verb} {enemy.id}")
            return relation, details

        last_recorded = getattr(lifeform, "last_activity", {})
        now = pygame.time.get_ticks()
        feeding_recently = lifeform._feeding_frames > 0
        if not feeding_recently and last_recorded.get("name") == "Eet plant":
            last_bite = int(last_recorded.get("timestamp", 0))
            if (
                lifeform.hunger > settings.HUNGER_SATIATED_THRESHOLD
                and now - last_bite <= settings.FEEDING_ACTIVITY_MEMORY_MS
            ):
                feeding_recently = True

        if feeding_recently:
            plant = getattr(lifeform, "closest_plant", None)
            if plant:
                plant_center = (
                    plant.x + plant.width / 2,
                    plant.y + plant.height / 2,
                )
                distance = math.hypot(
                    lifeform.rect.centerx - plant_center[0],
                    lifeform.rect.centery - plant_center[1],
                )
                details.append(f"Eet van plant op {distance:.1f}m")
            else:
                details.append("Laatste hap verwerken")
            return "Eten", details

        prey = getattr(lifeform, "closest_prey", None)
        if (
            prey
            and getattr(prey, "health_now", 0) > 0
            and lifeform.closest_enemy is None
            and lifeform.prefers_meat()
        ):
            distance = lifeform.distance_to(prey)
            details.append(f"Jaagt op {prey.id} ({distance:.1f}m)")
            return "Zoekt prooi", details

        partner = getattr(lifeform, "closest_partner", None)
        if lifeform.closest_enemy is None and lifeform.can_reproduce():
            if partner and partner.health_now > 0:
                distance = lifeform.distance_to(partner)
                details.append(f"Benadert partner {partner.id} ({distance:.1f}m)")
                return "Zoekt partner", details
            details.append("Zoekt naar geschikte partner")
            return "Zoekt partner", details

        if lifeform.is_foraging or lifeform.hunger >= settings.HUNGER_SEEK_THRESHOLD:
            if lifeform.prefers_plants() and lifeform.closest_plant:
                plant = lifeform.closest_plant
                plant_center = (
                    plant.x + plant.width / 2,
                    plant.y + plant.height / 2,
                )
                distance = math.hypot(
                    lifeform.rect.centerx - plant_center[0],
                    lifeform.rect.centery - plant_center[1],
                )
                details.append(f"Op weg naar plant ({distance:.1f}m)")
            elif lifeform.prefers_meat() and prey:
                distance = lifeform.distance_to(prey)
                details.append(f"Zoekt vlees op {distance:.1f}m")
            else:
                details.append("Zoekt nieuwe voedselbron")
            return "Zoekt voedsel", details

        if lifeform.search:
            details.append("Verkent omgeving, geen doelen dichtbij")
            return "Verkennen", details

        last_event = last_recorded.get("name") if last_recorded else None
        if last_event:
            details.append("Gebaseerd op recente gebeurtenis")
            return str(last_event), details

        return "Zwerft rond", ["Geen specifieke doelen gedetecteerd"]

    def _last_activity_summary(self, lifeform: "Lifeform") -> Tuple[str, List[str]]:
        entry = getattr(lifeform, "last_activity", None) or {}
        name = str(entry.get("name", "Onbekend"))
        timestamp = float(entry.get("timestamp", 0))
        now = pygame.time.get_ticks()
        elapsed = max(0.0, (now - timestamp) / 1000.0)
        details = entry.get("details", {}) or {}
        tooltip = [f"{elapsed:.1f}s geleden"]
        for key, value in details.items():
            tooltip.append(f"{key}: {value}")
        label = f"{name} ({elapsed:.1f}s geleden)"
        return label, tooltip

    def _build_stat_tooltips(self, lifeform: "Lifeform") -> dict[str, List[str]]:
        effects = lifeform.environment_effects
        tips: dict[str, List[str]] = {
            "health": [
                f"Maximaal DNA: {lifeform.health}",
                f"Huidig: {lifeform.health_now:.1f}",
                f"Wonden: {lifeform.wounded:.1f}",
                f"Biome bonus: {effects.get('health', 0.0):+.2f}/s",
            ],
            "energy": [
                f"Maximaal DNA: {lifeform.energy}",
                f"Huidig: {lifeform.energy_now:.1f}",
                f"Omgeving: x{float(effects.get('energy', 1.0)):.2f}",
                f"Onderhoudskosten: {lifeform.maintenance_cost:.2f}/s",
            ],
            "hunger": [
                f"Huidig: {lifeform.hunger:.1f}",
                f"Zoekdrempel: {settings.HUNGER_SEEK_THRESHOLD}",
                f"Ontspan-drempel: {settings.HUNGER_RELAX_THRESHOLD}",
                f"Minimum: {settings.HUNGER_MINIMUM}",
            ],
            "age": [
                f"Maturiteit: {lifeform.maturity}",
                f"Levensverwachting: {lifeform.longevity}",
                "Na de levensverwachting neemt kracht af",
            ],
            "attack": self._attack_breakdown(lifeform),
            "defence": self._defence_breakdown(lifeform),
            "speed": self._speed_breakdown(lifeform),
            "vision": [
                f"Basis DNA: {lifeform.vision - lifeform.morph_stats.vision_range_bonus:.1f}",
                f"Morph bonus: +{lifeform.morph_stats.vision_range_bonus:.1f}",
                f"Perceptiestralen: {lifeform.perception_rays}",
                f"Hoorbereik: {lifeform.hearing_range:.1f}",
            ],
            "diet": self._diet_breakdown(lifeform),
        }
        return tips

    def _format_diet_value(self, lifeform: "Lifeform") -> str:
        labels = {
            "herbivore": "Herbivoor",
            "omnivore": "Omnivoor",
            "carnivore": "Carnivoor",
        }
        label = labels.get(lifeform.diet, lifeform.diet.title())
        features = len(lifeform.development_features)
        if features:
            return f"{label} (+{features} mutaties)"
        return label

    def _diet_breakdown(self, lifeform: "Lifeform") -> List[str]:
        lines = [f"Voorkeur: {self._format_diet_value(lifeform)}"]
        lines.append(f"Huidige honger: {lifeform.hunger:.1f}")
        lines.append(f"Zoekdrempel: {settings.HUNGER_SEEK_THRESHOLD}")
        lines.append(f"Ontspan-drempel: {settings.HUNGER_RELAX_THRESHOLD}")
        if lifeform.is_foraging:
            lines.append("Status: actief op zoek naar voedsel")
        else:
            lines.append("Status: geen actief zoekgedrag")
        stage_info = describe_skin_stage(lifeform.skin_stage)
        lines.append(
            f"Huidfase: {stage_info['label']} – {stage_info['description']}"
        )
        if lifeform.development_features:
            lines.append("Ontwikkelde kenmerken:")
            for feature_id in lifeform.development_features:
                info = describe_feature(feature_id)
                lines.append(f"• {info['label']}: {info['description']}")
        else:
            lines.append("Nog geen speciale kenmerken ontgrendeld.")
        return lines

    def _attack_breakdown(self, lifeform: "Lifeform") -> List[str]:
        lines: List[str] = [f"Basis DNA: {lifeform.attack_power:.2f}"]
        energy_factor = lifeform.energy_now / 100.0
        lines.append(f"Energie ({lifeform.energy_now:.1f}) → x{energy_factor:.2f}")
        if lifeform.wounded > 0:
            penalty = lifeform.attack_power * (lifeform.wounded / 100.0)
            lines.append(f"Wonden {lifeform.wounded:.1f}% → -{penalty:.2f}")
        size_bonus = (lifeform.size - 50.0) * 0.8
        if abs(size_bonus) > 0.01:
            lines.append(f"Grootte {lifeform.size:.1f} → {size_bonus:+.2f}")
        if lifeform.hunger > 0:
            hunger_penalty = lifeform.hunger * 0.1
            lines.append(f"Honger {lifeform.hunger:.1f} → -{hunger_penalty:.2f}")
        age_factor = lifeform.calculate_age_factor()
        if not math.isclose(age_factor, 1.0, rel_tol=1e-3):
            lines.append(f"Leeftijdsfactor → x{age_factor:.2f}")
        mass_bonus = 1.0 + (lifeform.mass - 1.0) * 0.12
        reach_bonus = 1.0 + (lifeform.reach - 4.0) * 0.03
        combined = max(0.4, mass_bonus * reach_bonus)
        lines.append(
            f"Massa {lifeform.mass:.2f} & bereik {lifeform.reach:.2f} → x{combined:.2f}"
        )
        lines.append(f"Resultaat: {lifeform.attack_power_now:.2f}")
        return lines

    def _defence_breakdown(self, lifeform: "Lifeform") -> List[str]:
        lines: List[str] = [f"Basis DNA: {lifeform.defence_power:.2f}"]
        energy_factor = lifeform.energy_now / 100.0
        lines.append(f"Energie ({lifeform.energy_now:.1f}) → x{energy_factor:.2f}")
        if lifeform.wounded > 0:
            penalty = lifeform.defence_power * (lifeform.wounded / 100.0)
            lines.append(f"Wonden {lifeform.wounded:.1f}% → -{penalty:.2f}")
        size_bonus = (lifeform.size - 50.0) * 0.8
        if abs(size_bonus) > 0.01:
            lines.append(f"Grootte {lifeform.size:.1f} → {size_bonus:+.2f}")
        if lifeform.hunger > 0:
            hunger_penalty = lifeform.hunger * 0.1
            lines.append(f"Honger {lifeform.hunger:.1f} → -{hunger_penalty:.2f}")
        age_factor = lifeform.calculate_age_factor()
        if not math.isclose(age_factor, 1.0, rel_tol=1e-3):
            lines.append(f"Leeftijdsfactor → x{age_factor:.2f}")
        grip_bonus = 1.0 + (lifeform.grip_strength - 1.0) * 0.25
        mass_bonus = 1.0 + (lifeform.mass - 1.0) * 0.08
        combined = max(0.4, grip_bonus * mass_bonus)
        lines.append(
            f"Grip {lifeform.grip_strength:.2f} & massa {lifeform.mass:.2f} → x{combined:.2f}"
        )
        lines.append(f"Resultaat: {lifeform.defence_power_now:.2f}")
        return lines

    def _speed_breakdown(self, lifeform: "Lifeform") -> List[str]:
        lines: List[str] = ["Basis snelheid: 6.00"]
        lines.append(f"Honger invloed: -{lifeform.hunger / 500.0:.3f}")
        lines.append(f"Leeftijd invloed: -{lifeform.age / 1000.0:.3f}")
        lines.append(f"Grootte invloed: -{lifeform.size / 250.0:.3f}")
        lines.append(f"Wonden invloed: -{lifeform.wounded / 20.0:.3f}")
        lines.append(f"Gezondheid bonus: +{lifeform.health_now / 200.0:.3f}")
        lines.append(f"Energie bonus: +{lifeform.energy / 100.0:.3f}")

        movement_modifier = float(lifeform.environment_effects.get("movement", 1.0))
        lines.append(f"Biome beweging: x{movement_modifier:.2f}")

        plant_modifier: Optional[float] = None
        for plant in getattr(self._state, "plants", []):
            if getattr(plant, "resource", 0) <= 0:
                continue
            if plant.contains_point(lifeform.rect.centerx, lifeform.rect.centery):
                plant_modifier = plant.movement_modifier_for(lifeform)
                break
        if plant_modifier is not None:
            lines.append(f"Vegetatie: x{plant_modifier:.2f}")

        if lifeform.age < lifeform.maturity:
            average = None
            if self._state.lifeforms:
                average = sum(l.maturity for l in self._state.lifeforms) / len(
                    self._state.lifeforms
                )
            if average:
                juvenile_factor = (lifeform.maturity / average) / 10.0
                lines.append(f"Jeugdfactor: x{juvenile_factor:.2f}")

        lines.append(f"Hydrodynamica: x{lifeform.speed_multiplier:.2f}")
        lines.append(f"Grip: x{lifeform.grip_strength:.2f}")
        mass_divisor = max(0.75, lifeform.mass)
        lines.append(f"Massa factor: /{mass_divisor:.2f}")
        pause_factor = getattr(lifeform, "_wander_pause_speed_factor", 1.0)
        if not math.isclose(pause_factor, 1.0, rel_tol=1e-3):
            lines.append(f"Pauzefactor: x{pause_factor:.2f}")
        lines.append(f"Resultaat: {lifeform.speed:.2f}")
        return lines

    def _environment_lines(self, lifeform: "Lifeform") -> List[str]:
        effects = lifeform.environment_effects
        locomotion_label = getattr(lifeform, "locomotion_label", "Onbekend")
        locomotion_desc = getattr(lifeform, "locomotion_description", "Geen omschrijving beschikbaar")
        locomotion_line = f"Locomotie: {locomotion_label}"
        lines = [
            locomotion_line,
            locomotion_desc,
            f"Weer: {effects.get('weather_name', '-')}, {effects.get('temperature', '?')}°C, {effects.get('precipitation', '-')}",
            (
                f"Beweging x{float(effects.get('movement', 1.0)):.2f} • "
                f"Energie x{float(effects.get('energy', 1.0)):.2f} • "
                f"Honger x{float(effects.get('hunger', 1.0)):.2f}"
            ),
            (
                f"Dieptebias {float(getattr(lifeform, 'depth_bias', 0.0)):+.2f} • "
                f"Drift voorkeur {float(getattr(lifeform, 'drift_preference', 0.0)):.2f}"
            ),
            f"Groei x{float(effects.get('regrowth', 1.0)):.2f} • Gezondheid {float(effects.get('health', 0.0)):+.2f}/s",
        ]
        if lifeform.in_group:
            lines.append(
                f"In groep met {len(lifeform.group_neighbors) + 1} leden (sterkte {lifeform.group_strength:.2f})"
            )
        else:
            lines.append("Geen groepsverband actief")
        if lifeform.is_leader:
            lines.append("Dit wezen fungeert als leider")
        return lines

    def _render_memory(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        lifeform: "Lifeform",
    ) -> int:
        now = pygame.time.get_ticks()
        label_map = {
            "food": "Voedsel",
            "threats": "Dreigingen",
            "partner": "Partners",
            "visited": "Bezocht",
        }

        section_y = y
        has_entries = False
        for key in ("food", "threats", "partner", "visited"):
            entries = list(lifeform.memory.get(key, ()))
            if not entries:
                continue
            has_entries = True
            label = label_map.get(key, key.title()) + ":"
            label_surface = self._body_font.render(label, True, (40, 40, 40))
            surface.blit(label_surface, (x, section_y))
            section_y += label_surface.get_height() + 2

            recent = list(entries)[-3:][::-1]
            for entry in recent:
                formatted = self._format_memory_entry(entry, now)
                text_surface = self._body_font.render(f"- {formatted}", True, (70, 70, 70))
                surface.blit(text_surface, (x + 12, section_y))
                section_y += text_surface.get_height() + 2
            section_y += 4

        if not has_entries:
            text_surface = self._body_font.render(
                "Geen herinneringen opgeslagen", True, (90, 90, 90)
            )
            surface.blit(text_surface, (x, section_y))
            section_y += text_surface.get_height() + 4

        return section_y

    def _format_memory_entry(self, entry: object, now_ms: int) -> str:
        if isinstance(entry, dict):
            pos = entry.get("pos") or entry.get("position")
            if isinstance(pos, (tuple, list)) and len(pos) >= 2:
                pos_text = f"({pos[0]:.0f}, {pos[1]:.0f})"
            else:
                pos_text = "(onbekend)"
            age_ms = max(0, now_ms - int(entry.get("time", now_ms)))
            age = age_ms / 1000.0
            weight = entry.get("weight")
            parts = [f"{age:.1f}s", pos_text]
            if weight is not None:
                parts.append(f"w={float(weight):.2f}")
            tag = entry.get("tag")
            if tag:
                parts.append(str(tag))
            return " | ".join(parts)

        return str(entry)

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
