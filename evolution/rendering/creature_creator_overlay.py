"""Creature Creator overlay UI for Alien Ocean."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, TYPE_CHECKING
from typing import Tuple
import math
import time

import pygame

from ..config import settings
from ..creator import (
    CreatureDraft,
    CreatureTemplate,
    SurvivabilityMetrics,
    evaluate_graph,
    list_templates,
    load_template,
    save_template,
    delete_template,
    rename_template,
)
from ..creator.templates import ModuleDraft
from ..rendering.window_chrome import WindowChrome, draw_resize_grip
from ..rendering.modular_palette import MODULE_COLORS

if TYPE_CHECKING:  # pragma: no cover
    from ..world.world import World


BUTTON_SIZE = (120, 28)
PALETTE_ENTRY_SIZE = (90, 26)
STAT_FIELDS = [
    ("mass", "Massa", 0.5),
    ("energy_cost", "Energie", 0.1),
    ("integrity", "Integriteit", 5.0),
    ("heat_dissipation", "Koeling", 0.5),
    ("power_output", "Power", 5.0),
    ("buoyancy_bias", "Drijf", 0.05),
]
DEFAULT_MODULE_CONFIG = {
    "scale": 1.0,
    "shape": "ellipse",
    "buoyancy": 0.0,
    "biolum": 0.0,
    "color": (120, 200, 230),
    "attachment_points": 3,
}
SHAPE_OPTIONS = ("ellipse", "fin", "arrow", "disk")
COLOR_SWATCHES = [
    (120, 200, 230),
    (230, 120, 150),
    (90, 190, 120),
    (240, 210, 120),
    (160, 120, 220),
    (220, 220, 220),
]


@dataclass
class PaletteEntry:
    module_type: str
    label: str
    description: str


class CreatureCreatorOverlay:
    """Manage interactive creature builder overlay."""

    def __init__(
        self,
        font: pygame.font.Font,
        heading_font: pygame.font.Font,
        palette: List[PaletteEntry],
        world: "World",
        *,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        on_spawn: Optional[Callable[[CreatureTemplate], None]] = None,
    ) -> None:
        self.font = font
        self.heading_font = heading_font
        self.palette_entries = palette
        self.world: "World" = world
        self.visible = False
        width = viewport_width or 980
        height = viewport_height or 720
        self.rect = pygame.Rect(80, 60, width, height)
        self._chrome = WindowChrome(self.rect, min_size=(760, 520))
        self._viewport = pygame.Rect(0, 0, 0, 0)
        self._stats_rect = pygame.Rect(0, 0, 0, 0)
        self._buttons: Dict[str, pygame.Rect] = {}
        self._node_button_rects: Dict[str, pygame.Rect] = {}
        self._selected_module: Optional[str] = None
        self._selected_node: Optional[str] = None
        self._selected_template: Optional[str] = None
        self._draft = CreatureDraft.new("prototype")
        self._name_input = self._draft.template.name
        self._name_editing = False
        self._name_rect = pygame.Rect(self.rect.left + 180, self.rect.top + 20, 260, 32)
        self._template_entries: List[str] = []
        self._template_buttons: Dict[str, pygame.Rect] = {}
        self._metrics: Optional[SurvivabilityMetrics] = None
        self._status_message = ""
        self._template_hover: Optional[str] = None
        self._property_panel = pygame.Rect(0, 0, 0, 0)
        self._property_button_keys: List[str] = []
        self._palette_rect = pygame.Rect(0, 0, 0, 0)
        self._template_list_rect = pygame.Rect(0, 0, 0, 0)
        self._node_positions: Dict[str, pygame.Vector2] = {}
        self._dragging_module: Optional[str] = None
        self._dragging_node: Optional[str] = None
        self._drag_position = pygame.Vector2()
        self._drop_candidate: Optional[Tuple[str, str]] = None
        self._pending_palette_drag: Optional[str] = None
        self._drag_start_pos = pygame.Vector2()
        self._click_start_pos = pygame.Vector2()
        self._last_click_pos = pygame.Vector2()
        self._popup_button_keys: List[str] = []
        self._pending_node_click: Optional[str] = None
        self._module_popup_rect = pygame.Rect(0, 0, 0, 0)
        self._active_popup_node: Optional[str] = None
        self._on_spawn = on_spawn
        self._floating_module: Optional[Dict[str, object]] = None
        self._floating_counter = 1
        self._dragging_floating = False
        self._active_drag_module: Optional[str] = None
        self._update_layout()
        self._rebuild_buttons()
        self._refresh_templates()
        self._appearance_cache: Dict[str, Dict[str, object]] = self._build_node_appearance()
        self._popup_buttons: Dict[str, pygame.Rect] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self.visible

    def toggle(self) -> None:
        self.visible = not self.visible
        if self.visible:
            self.recalculate()
            self._refresh_templates()

    def recalculate(self) -> None:
        try:
            graph = self._draft.build_graph()
            self._metrics = evaluate_graph(graph, self.world.layers)
            self._status_message = "Ontwerp geanalyseerd"
            self._appearance_cache = self._build_node_appearance()
        except Exception as exc:  # pragma: no cover - UI feedback
            self._metrics = None
            self._status_message = f"Fout tijdens analyse: {exc}"

    def save_current(self) -> None:
        try:
            self._draft.template.name = self._name_input or self._draft.template.name
            save_template(self._draft.template)
            self._status_message = f"Template '{self._draft.template.name}' opgeslagen"
            self._refresh_templates()
        except Exception as exc:  # pragma: no cover
            self._status_message = f"Opslaan mislukt: {exc}"

    def load_template(self, name: str) -> None:
        try:
            template = load_template(name)
            self._draft = CreatureDraft(template)
            self._name_input = template.name
            self._name_editing = False
            self.recalculate()
            self._status_message = f"Template '{name}' geladen"
            self._refresh_templates()
        except FileNotFoundError:
            self._status_message = f"Template '{name}' niet gevonden"
        except Exception as exc:  # pragma: no cover
            self._status_message = f"Laden mislukt: {exc}"

    def new_template(self) -> None:
        slug = f"draft_{int(time.time())}"
        self._draft = CreatureDraft.new(slug)
        self._name_input = slug
        self._name_editing = False
        self._selected_node = None
        self._selected_module = None
        self.recalculate()
        self._status_message = f"Nieuw template '{slug}' gestart"
        self._refresh_templates()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            chrome_consumed, geometry_changed = self._chrome.handle_event(event, self._header_rect())
            if geometry_changed:
                self._rebuild_buttons()
                self._name_rect.topleft = (self.rect.left + 180, self.rect.top + 20)
                self._update_layout()
            if chrome_consumed:
                return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self._name_rect.collidepoint(event.pos):
                    self._name_editing = True
                    return True
                self._name_editing = False
                if self._handle_button_click(event.pos):
                    return True
                if self._handle_template_click(event.pos):
                    return True
                if self._handle_popup_click(event.pos):
                    return True
                if self._palette_rect.collidepoint(event.pos):
                    self._pending_palette_drag = self._palette_hit_test(event.pos)
                    self._drag_start_pos.update(event.pos)
                    return bool(self._pending_palette_drag)
                if self._viewport.collidepoint(event.pos):
                    node_id = self._node_hit_test(event.pos)
                    if node_id:
                        if event.clicks == 1:
                            self._pending_node_click = node_id
                            pygame.time.set_timer(pygame.USEREVENT + 5, 150, True)
                        self._begin_drag(node_id, event.pos)
                        return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_node:
                self._commit_drag()
                return True
            if self._dragging_module:
                self._finalize_drag(event.pos)
                return True
            self._pending_palette_drag = None
        if event.type == pygame.MOUSEMOTION:
            if self._dragging_node:
                self._drag_position.update(event.pos)
                self._update_drop_candidate()
                return True
            if self._dragging_module:
                self._drag_position.update(event.pos)
                self._update_drop_candidate()
                return True
            if self._pending_palette_drag and (pygame.Vector2(event.pos) - self._drag_start_pos).length() > 6:
                self._selected_module = self._pending_palette_drag
                self._begin_drag(None, event.pos, spawn_from_palette=True)
                self._pending_palette_drag = None
                return True
        if event.type == pygame.KEYDOWN and self._name_editing:
            return self._handle_name_input(event)
        if event.type == pygame.USEREVENT + 5 and self._pending_node_click:
            self._selected_node = self._pending_node_click
            self._toggle_module_popup(self._pending_node_click)
            self._pending_node_click = None
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        overlay.fill((8, 16, 32, 230))
        surface.blit(overlay, self.rect.topleft)
        pygame.draw.rect(surface, (60, 120, 180), self.rect, 2, border_radius=12)

        heading = self.heading_font.render("Creature Lab", True, settings.WHITE)
        surface.blit(heading, (self.rect.left + 24, self.rect.top + 20))
        self._draw_name_field(surface)
        status = self.font.render(self._status_message or "", True, settings.SEA)
        surface.blit(status, (self.rect.left + 24, self.rect.top + 60))

        self._draw_palette(surface)
        self._draw_viewport(surface)
        self._draw_stats(surface)
        self._draw_properties(surface)
        self._draw_template_list(surface)
        draw_resize_grip(surface, self._chrome)

    # ------------------------------------------------------------------
    # UI drawing helpers
    # ------------------------------------------------------------------

    def _draw_palette(self, surface: pygame.Surface) -> None:
        start_y = self.rect.top + 120
        for entry in self.palette_entries:
            label = f"{entry.label}"
            rect = self._buttons.get(f"palette:{entry.module_type}")
            if rect is None:
                continue
            color = (120, 180, 200) if self._selected_module == entry.module_type else (45, 80, 110)
            pygame.draw.rect(surface, color, rect, border_radius=6)
            pygame.draw.rect(surface, (20, 35, 55), rect, 1, border_radius=6)
            text = self.font.render(label, True, settings.WHITE)
            surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

        save_rect = self._buttons.get("action:save")
        if save_rect:
            self._draw_button(surface, save_rect, "Opslaan")
        load_rect = self._buttons.get("action:load")
        if load_rect:
            self._draw_button(surface, load_rect, "Laden")
        recalc_rect = self._buttons.get("action:recalc")
        if recalc_rect:
            self._draw_button(surface, recalc_rect, "Analyseer")

    def _draw_viewport(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (18, 28, 40), self._viewport, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 110), self._viewport, 1, border_radius=10)

        # Draw grid
        grid_color = (30, 45, 60)
        grid_size = 40
        start_x = self._viewport.left + (self._viewport.width // 2) % grid_size
        start_y = self._viewport.top + (self._viewport.height // 2) % grid_size
        
        for x in range(start_x - grid_size * (self._viewport.width // grid_size + 1), self._viewport.right, grid_size):
            if x >= self._viewport.left:
                pygame.draw.line(surface, grid_color, (x, self._viewport.top), (x, self._viewport.bottom))
        
        for y in range(start_y - grid_size * (self._viewport.height // grid_size + 1), self._viewport.bottom, grid_size):
            if y >= self._viewport.top:
                pygame.draw.line(surface, grid_color, (self._viewport.left, y), (self._viewport.right, y))

        modules = list(self._draft.iter_modules())
        if not modules:
            return
        positions = self._layout_nodes(modules)
        module_shapes: Dict[str, List[Tuple[int, int]]] = {}
        for module in modules:
            center_vec = positions.get(module.node_id, pygame.Vector2(0, 0))
            if module.parent_id and module.parent_id in positions:
                start_vec = positions[module.parent_id]
                pygame.draw.line(surface, (100, 120, 140), start_vec, center_vec, 3)

            appearance = self._appearance_cache.get(module.node_id, DEFAULT_MODULE_CONFIG)
            default_color = MODULE_COLORS.get(module.module_type, (120, 200, 230))
            color = appearance.get("color", default_color)
            if "color" not in appearance:
                 color = default_color

            polygon = self._shape_polygon(
                appearance.get("shape", "circle"),
                center_vec,
                appearance.get("scale", 1.0)
            )
            
            pygame.draw.polygon(surface, color, polygon)
            # Low poly outline
            outline_color = (200, 240, 120) if module.node_id == self._selected_node else (220, 240, 255)
            pygame.draw.polygon(
                surface,
                outline_color,
                polygon,
                2,
            )
            # Internal triangulation lines
            center_pt = (int(center_vec.x), int(center_vec.y))
            internal_color = (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40))
            for pt in polygon:
                pygame.draw.line(surface, internal_color, center_pt, pt, 1)
            label = self.font.render(module.module_type, True, (10, 15, 25))
            rect = label.get_rect(center=(int(center_vec.x), int(center_vec.y)))
            surface.blit(label, rect)
            bbox = pygame.Rect(min(p[0] for p in polygon), min(p[1] for p in polygon), 1, 1)
            bbox.width = max(p[0] for p in polygon) - bbox.left
            bbox.height = max(p[1] for p in polygon) - bbox.top
            self._node_button_rects[module.node_id] = bbox.inflate(12, 12)
            self._appearance_cache[module.node_id]["polygon"] = polygon
            if self._active_popup_node == module.node_id:
                pygame.draw.polygon(surface, (250, 240, 180), polygon, 2)
            self._draw_attachment_points(surface, module)
        if self._floating_module:
            floating_id = self._floating_module["id"]
            appearance = self._appearance_cache.get(floating_id, DEFAULT_MODULE_CONFIG)
            polygon = self._shape_polygon(
                appearance.get("shape", "ellipse"),
                pygame.Vector2(self._drag_position if self._dragging_floating else self._viewport.center),
                appearance.get("scale", 1.0),
            )
            pygame.draw.polygon(surface, (180, 220, 250), polygon, 2)

    def _layout_nodes(self, modules: List[ModuleDraft]) -> Dict[str, pygame.Vector2]:
        viewport_center = pygame.Vector2(
            self._viewport.left + self._viewport.width / 2,
            self._viewport.top + self._viewport.height / 2,
        )
        if not modules:
            return {}
        root_id = self._draft.template.root_node().node_id
        adjacency: Dict[str, List[str]] = {}
        depths: Dict[str, int] = {root_id: 0}
        queue: List[str] = [root_id]
        module_map = {module.node_id: module for module in modules}
        for module in modules:
            adjacency.setdefault(module.parent_id or root_id, []).append(module.node_id)
        while queue:
            current = queue.pop(0)
            for child in adjacency.get(current, []):
                if child == current:
                    continue
                depths[child] = depths[current] + 1
                queue.append(child)
        max_depth = max(depths.values() or [0])
        level_height = self._viewport.height / max(1, max_depth + 1)
        positions: Dict[str, pygame.Vector2] = {}
        for node_id, depth in depths.items():
            siblings = [nid for nid, d in depths.items() if d == depth]
            count = len(siblings)
            if count == 1:
                x = viewport_center.x
            else:
                spread = min(self._viewport.width - 80, 160 * (count - 1))
                start_x = viewport_center.x - spread / 2
                step = spread / max(1, count - 1)
                index = siblings.index(node_id)
                x = start_x + index * step
            if node_id == root_id:
                y = viewport_center.y
            else:
                y = self._viewport.top + depth * level_height + level_height / 2
            positions[node_id] = pygame.Vector2(x, y)
        for module in modules:
            if module.node_id not in positions:
                positions[module.node_id] = viewport_center
        return positions

    def _draw_stats(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (18, 28, 40), self._stats_rect, border_radius=10)
        pygame.draw.rect(surface, (70, 90, 110), self._stats_rect, 1, border_radius=10)
        title = self.font.render("Survivability", True, settings.WHITE)
        surface.blit(title, (self._stats_rect.left + 12, self._stats_rect.top + 8))
        if not self._metrics:
            placeholder = self.font.render("Nog geen analyse", True, settings.SEA)
            surface.blit(placeholder, (self._stats_rect.left + 12, self._stats_rect.top + 40))
            return
        lines = [
            f"Mobiliteit: {self._metrics.mobility_rating} ({self._metrics.thrust_to_drag:.2f})",
            f"Energie-efficiëntie: {self._metrics.energy_efficiency:.2f}",
            f"Zintuigen: {self._metrics.sensors:.1f}",
            f"Aanval: {self._metrics.offence:.1f}",
            f"Verdediging: {self._metrics.defence:.1f}",
        ]
        y = self._stats_rect.top + 40
        for line in lines:
            text = self.font.render(line, True, settings.WHITE)
            surface.blit(text, (self._stats_rect.left + 12, y))
            y += 24
        y += 12
        surface.blit(self.font.render("Buoyancy per laag:", True, settings.WHITE), (self._stats_rect.left + 12, y))
        y += 24
        for row in self._metrics.buoyancy_by_layer:
            text = self.font.render(f"{row.layer_name}: {row.drift}", True, settings.SEA)
            surface.blit(text, (self._stats_rect.left + 12, y))
            y += 20
        self._template_list_rect = pygame.Rect(self._stats_rect.left, y + 16, self._stats_rect.width, 140)

    def _update_layout(self) -> None:
        margin = 20
        header_height = 90
        palette_width = 180
        stats_width = 320
        available_width = self.rect.width - (margin * 3) - palette_width - stats_width
        viewport_width = max(320, int(available_width * 0.55))
        property_width = max(240, available_width - viewport_width)
        top = self.rect.top + header_height
        height = max(360, self.rect.height - header_height - margin)
        self._palette_rect = pygame.Rect(self.rect.left + margin, top, palette_width, height)
        self._viewport = pygame.Rect(self._palette_rect.right + margin, top, viewport_width, height)
        self._property_panel = pygame.Rect(self._viewport.right + margin, top, property_width, height)
        self._stats_rect = pygame.Rect(self._property_panel.right + margin, top, stats_width, int(height * 0.6))
        templates_height = height - self._stats_rect.height - margin
        self._template_list_rect = pygame.Rect(self._property_panel.right + margin, self._stats_rect.bottom + margin, stats_width, templates_height)

    def _draw_properties(self, surface: pygame.Surface) -> None:
        for key in self._property_button_keys:
            self._buttons.pop(key, None)
        self._property_button_keys.clear()
        pygame.draw.rect(surface, (25, 30, 45), self._property_panel, border_radius=10)
        pygame.draw.rect(surface, (80, 90, 110), self._property_panel, 1, border_radius=10)
        title = self.font.render("Eigenschappen", True, settings.WHITE)
        surface.blit(title, (self._property_panel.left + 8, self._property_panel.top + 6))
        if not self._selected_node:
            surface.blit(
                self.font.render("Selecteer een module", True, settings.SEA),
                (self._property_panel.left + 8, self._property_panel.top + 34),
            )
            return
        node = next((m for m in self._draft.template.nodes if m.node_id == self._selected_node), None)
        if not node:
            return
        try:
            module = self._draft.effective_module(node.node_id)
        except Exception as exc:
            surface.blit(
                self.font.render(f"{exc}", True, (200, 120, 120)),
                (self._property_panel.left + 8, self._property_panel.top + 34),
            )
            return
        surface.blit(
            self.font.render(f"{node.module_type}", True, settings.WHITE),
            (self._property_panel.left + 8, self._property_panel.top + 30),
        )
        y = self._property_panel.top + 54
        for stat_name, label, step in STAT_FIELDS:
            value = getattr(module.stats, stat_name)
            text = self.font.render(f"{label}: {value:.2f}", True, settings.WHITE)
            surface.blit(text, (self._property_panel.left + 8, y))
            minus_rect = pygame.Rect(self._property_panel.right - 70, y - 2, 24, 20)
            plus_rect = pygame.Rect(self._property_panel.right - 35, y - 2, 24, 20)
            self._draw_mini_button(surface, minus_rect, "-")
            self._draw_mini_button(surface, plus_rect, "+")
            minus_key = f"statdec:{node.node_id}:{stat_name}:{step}"
            plus_key = f"statinc:{node.node_id}:{stat_name}:{step}"
            self._buttons[minus_key] = minus_rect
            self._buttons[plus_key] = plus_rect
            self._property_button_keys.extend([minus_key, plus_key])
            y += 24
        reset_button = pygame.Rect(self._property_panel.left + 8, y + 10, self._property_panel.width - 16, 24)
        self._draw_button(surface, reset_button, "Reset")
        reset_key = f"reset:{node.node_id}"
        self._buttons[reset_key] = reset_button
        self._property_button_keys.append(reset_key)

    def _draw_mini_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str) -> None:
        pygame.draw.rect(surface, (100, 120, 150), rect, border_radius=4)
        pygame.draw.rect(surface, (20, 30, 40), rect, 1, border_radius=4)
        text = self.font.render(label, True, settings.WHITE)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------

    def _header_rect(self) -> pygame.Rect:
        return pygame.Rect(self.rect.left, self.rect.top, self.rect.width, 80)

    def _rebuild_buttons(self) -> None:
        self._buttons.clear()
        palette_x = self.rect.left + 24
        palette_y = self.rect.top + 120
        for idx, entry in enumerate(self.palette_entries):
            rect = pygame.Rect(
                palette_x,
                palette_y + idx * (PALETTE_ENTRY_SIZE[1] + 8),
                PALETTE_ENTRY_SIZE[0],
                PALETTE_ENTRY_SIZE[1],
            )
            self._buttons[f"palette:{entry.module_type}"] = rect
        button_y = self.rect.top + 60
        for idx, action in enumerate(("recalc", "save", "load", "spawn", "new", "add", "rename", "delete")):
            rect = pygame.Rect(
                self.rect.right - (idx + 1) * (BUTTON_SIZE[0] + 12),
                button_y,
                BUTTON_SIZE[0],
                BUTTON_SIZE[1],
            )
            self._buttons[f"action:{action}"] = rect

    def _draw_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str) -> None:
        pygame.draw.rect(surface, (50, 120, 90), rect, border_radius=6)
        pygame.draw.rect(surface, (20, 60, 40), rect, 1, border_radius=6)
        text = self.font.render(label, True, settings.WHITE)
        surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _handle_button_click(self, position) -> bool:
        for key, rect in self._buttons.items():
            if rect.collidepoint(position):
                if key.startswith("palette:"):
                    self._selected_module = key.split(":", 1)[1]
                    return True
                if key.startswith("node:"):
                    node_id = key.split(":", 1)[1]
                    rect = self._node_button_rects.get(node_id)
                    if rect and rect.collidepoint(position):
                        self._selected_node = node_id
                        return True
                if key == "action:recalc":
                    self.recalculate()
                    return True
                if key == "action:save":
                    self.save_current()
                    return True
                if key == "action:load":
                    available = list_templates()
                    if available:
                        self.load_template(available[0])
                    return True
                if key == "action:spawn":
                    self._spawn_in_ocean()
                    return True
                if key == "action:new":
                    self.new_template()
                    return True
                if key == "action:add" and self._selected_module and self._selected_node:
                    try:
                        self._draft.attach_module(self._selected_module, self._selected_node)
                        self.recalculate()
                        self._status_message = (
                            f"{self._selected_module} gekoppeld aan {self._selected_node}"
                        )
                    except Exception as exc:
                        self._status_message = str(exc)
                    return True
                if key == "action:rename":
                    self._prompt_rename()
                    return True
                if key == "action:delete":
                    self._delete_selected_template()
                    return True
                if key.startswith("statdec:"):
                    _, node_id, stat, step = key.split(":")
                    self._adjust_stat(node_id, stat, -float(step))
                    return True
                if key.startswith("statinc:"):
                    _, node_id, stat, step = key.split(":")
                    self._adjust_stat(node_id, stat, float(step))
                    return True
                if key.startswith("reset:"):
                    _, node_id = key.split(":")
                    self._draft.reset_overrides(node_id)
                    self.recalculate()
                    self._status_message = f"Overrides hersteld voor {node_id}"
                    return True
        return False

    def _adjust_stat(self, node_id: str, stat: str, delta: float) -> None:
        try:
            new_value = self._draft.adjust_stat_override(node_id, stat, delta)
            self._status_message = f"{stat} -> {new_value:.2f}"
            self.recalculate()
        except Exception as exc:
            self._status_message = str(exc)

    def _handle_template_click(self, position: Tuple[int, int]) -> bool:
        for name, rect in self._template_buttons.items():
            if rect.collidepoint(position):
                self.load_template(name)
                return True
        return False

    def _draw_template_list(self, surface: pygame.Surface) -> None:
        if not hasattr(self, "_template_list_rect"):
            return
        rect = self._template_list_rect
        pygame.draw.rect(surface, (15, 24, 36), rect, border_radius=8)
        pygame.draw.rect(surface, (60, 80, 110), rect, 1, border_radius=8)
        title = self.font.render("Templates", True, settings.WHITE)
        surface.blit(title, (rect.left + 8, rect.top + 6))
        self._template_buttons.clear()
        if not self._template_entries:
            empty = self.font.render("(geen templates)", True, settings.SEA)
            surface.blit(empty, (rect.left + 8, rect.top + 30))
            return
        y = rect.top + 30
        for name in self._template_entries[:6]:
            entry_rect = pygame.Rect(rect.left + 8, y, rect.width - 16, 24)
            highlight = (90, 140, 170) if name == self._draft.template.name else (40, 60, 80)
            pygame.draw.rect(surface, highlight, entry_rect, border_radius=4)
            pygame.draw.rect(surface, (20, 30, 40), entry_rect, 1, border_radius=4)
            label = self.font.render(name, True, settings.WHITE)
            surface.blit(label, (entry_rect.left + 6, entry_rect.top + 4))
            self._template_buttons[name] = entry_rect
            y += 28
        if self._name_editing:
            pygame.draw.rect(surface, (90, 160, 190), self._name_rect, 2, border_radius=6)

    def _draw_name_field(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (50, 70, 100), self._name_rect, border_radius=6)
        pygame.draw.rect(surface, (20, 30, 40), self._name_rect, 1, border_radius=6)
        display = self._name_input
        if self._name_editing and int(pygame.time.get_ticks() / 400) % 2 == 0:
            display += "|"
        text = self.font.render(display, True, settings.WHITE)
        surface.blit(text, (self._name_rect.left + 8, self._name_rect.top + 4))

    def _handle_name_input(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_RETURN:
            self._name_editing = False
            self._draft.template.name = self._name_input or self._draft.template.name
            return True
        if event.key == pygame.K_ESCAPE:
            self._name_editing = False
            self._name_input = self._draft.template.name
            return True
        if event.key == pygame.K_BACKSPACE:
            self._name_input = self._name_input[:-1]
            return True
        if 32 <= event.key <= 126:
            self._name_input += event.unicode
            self._name_input = self._name_input[:32]
            return True
        return False

    def _refresh_templates(self) -> None:
        try:
            self._template_entries = list_templates()
        except Exception:  # pragma: no cover
            self._template_entries = []

    def _prompt_rename(self) -> None:
        if not self._draft.template.name:
            return
        try:
            rename_template(self._draft.template.name, self._name_input or self._draft.template.name)
            self._status_message = "Template hernoemd"
            self._refresh_templates()
        except Exception as exc:
            self._status_message = str(exc)

    def _delete_selected_template(self) -> None:
        name = self._draft.template.name
        try:
            delete_template(name)
            self.new_template()
            self._status_message = f"Template '{name}' verwijderd"
            self._refresh_templates()
        except Exception as exc:
            self._status_message = str(exc)

    def _node_hit_test(self, position: Tuple[int, int]) -> Optional[str]:
        for node_id, rect in self._node_button_rects.items():
            if rect.collidepoint(position):
                return node_id
        return None

    def _palette_hit_test(self, position: Tuple[int, int]) -> Optional[str]:
        for entry in self.palette_entries:
            rect = self._buttons.get(f"palette:{entry.module_type}")
            if rect and rect.collidepoint(position):
                return entry.module_type
        return None

    def _begin_drag(self, node_id: Optional[str], position: Tuple[int, int], *, spawn_from_palette: bool = False) -> None:
        if spawn_from_palette:
            self._dragging_module = self._selected_module
            self._drag_position.update(position)
            self._drop_candidate = None
            return
        if node_id is None:
            return
        self._dragging_node = node_id
        self._drag_position.update(position)
        self._drop_candidate = None

    def _begin_palette_drag(self, module_type: str, position: Tuple[int, int]) -> None:
        self._pending_palette_drag = module_type
        self._drag_start_pos.update(position)

    def _update_drop_candidate(self) -> None:
        if not (self._dragging_module or self._dragging_node):
            return
        pointer = pygame.Vector2(self._drag_position)
        self._drop_candidate = None
        for parent_id, rect in self._node_button_rects.items():
            if rect.collidepoint(pointer):
                module_type = self._selected_module or self._draft.get_module(parent_id).module_type
                try:
                    slots = self._draft.available_attachment_points(parent_id, module_type)
                except Exception:
                    slots = ()
                if slots:
                    self._drop_candidate = (parent_id, slots[0])
                break

    def _finalize_drag(self, position: Tuple[int, int]) -> None:
        if self._dragging_module and self._drop_candidate:
            parent_id, slot = self._drop_candidate
            try:
                module_type = self._selected_module or "core"
                self._draft.add_module(
                    self._draft.generate_node_id(module_type),
                    module_type,
                    parent_id,
                    slot,
                )
                self.recalculate()
                self._status_message = f"{self._selected_module} gekoppeld aan {parent_id}"
            except Exception as exc:
                self._status_message = str(exc)
        self._dragging_module = None
        self._drop_candidate = None
        self._dragging_node = None

    def _commit_drag(self) -> None:
        if self._dragging_node and self._drop_candidate:
            parent_id, slot = self._drop_candidate
            try:
                self._draft.reparent(self._dragging_node, parent_id, slot)
                self.recalculate()
            except Exception as exc:
                self._status_message = str(exc)
        self._dragging_node = None
        self._drop_candidate = None

    def _toggle_module_popup(self, node_id: str) -> None:
        if self._active_popup_node == node_id:
            self._active_popup_node = None
        else:
            self._active_popup_node = node_id

    def _handle_popup_click(self, position: Tuple[int, int]) -> bool:
        if self._module_popup_rect and self._module_popup_rect.collidepoint(position):
            self._last_click_pos.update(position)
            for key, rect in self._popup_buttons.items():
                if rect.collidepoint(position):
                    self._handle_popup_button(key)
                    return True
            return True
        for node_id, rect in self._node_button_rects.items():
            if rect.collidepoint(position):
                self._toggle_module_popup(node_id)
                return True
        if self._active_popup_node and self._module_popup_rect.width > 0:
            self._active_popup_node = None
            self._module_popup_rect.size = (0, 0)
            self._clear_popup_buttons()
            return False
        return False

    def _draw_module_popup(self, surface: pygame.Surface, position: Tuple[int, int]) -> None:
        if not self._active_popup_node:
            return
        node = next((m for m in self._draft.template.nodes if m.node_id == self._active_popup_node), None)
        if not node:
            return
        self._clear_popup_buttons()
        popup_width = 260
        popup_height = 260
        popup_rect = pygame.Rect(position[0] - popup_width // 2, position[1] - popup_height - 20, popup_width, popup_height)
        popup_rect.clamp_ip(self.rect.inflate(-40, -40))
        self._module_popup_rect = popup_rect
        pygame.draw.rect(surface, (28, 34, 52), popup_rect, border_radius=10)
        pygame.draw.rect(surface, (80, 90, 110), popup_rect, 1, border_radius=10)
        title = self.font.render(f"Module: {node.module_type}", True, settings.WHITE)
        surface.blit(title, (popup_rect.left + 12, popup_rect.top + 10))
        close_button = pygame.Rect(popup_rect.right - 32, popup_rect.top + 8, 24, 24)
        pygame.draw.rect(surface, (200, 50, 50), close_button, border_radius=4)
        pygame.draw.rect(surface, (20, 30, 40), close_button, 1, border_radius=4)
        close_label = self.font.render("X", True, settings.WHITE)
        surface.blit(close_label, (close_button.centerx - close_label.get_width() // 2, close_button.centery - close_label.get_height() // 2))
        self._register_popup_button("popup:close", close_button)

        y = popup_rect.top + 44
        cfg = node.parameters.setdefault("editor", dict(DEFAULT_MODULE_CONFIG))

        scale_value = cfg.get("scale", 1.0)
        scale_label = self.font.render(f"Grootte: {scale_value:.1f}x", True, settings.WHITE)
        surface.blit(scale_label, (popup_rect.left + 12, y))
        scale_minus = pygame.Rect(popup_rect.left + 170, y - 2, 28, 22)
        scale_plus = pygame.Rect(popup_rect.left + 204, y - 2, 28, 22)
        self._draw_mini_button(surface, scale_minus, "-")
        self._draw_mini_button(surface, scale_plus, "+")
        self._register_popup_button(f"popup:scale:-:{node.node_id}", scale_minus)
        self._register_popup_button(f"popup:scale:+:{node.node_id}", scale_plus)
        y += 32

        surface.blit(self.font.render("Vorm", True, settings.WHITE), (popup_rect.left + 12, y))
        shape_rect = pygame.Rect(popup_rect.left + 90, y - 2, 140, 22)
        pygame.draw.rect(surface, (50, 80, 110), shape_rect, border_radius=4)
        pygame.draw.rect(surface, (20, 30, 40), shape_rect, 1, border_radius=4)
        surface.blit(self.font.render(cfg.get("shape", "ellipse"), True, settings.WHITE), (shape_rect.left + 8, shape_rect.top + 3))
        self._register_popup_button(f"popup:shape:{node.node_id}", shape_rect)
        y += 32

        buoyancy = cfg.get("buoyancy", 0.0)
        buoy_label = self.font.render(f"Buoyancy: {buoyancy:+.2f}", True, settings.WHITE)
        surface.blit(buoy_label, (popup_rect.left + 12, y))
        buoy_slider = pygame.Rect(popup_rect.left + 12, y + 18, popup_rect.width - 24, 10)
        pygame.draw.rect(surface, (40, 60, 80), buoy_slider, border_radius=5)
        knob_x = buoy_slider.left + int((buoyancy + 1) / 2 * buoy_slider.width)
        pygame.draw.circle(surface, (180, 220, 250), (knob_x, buoy_slider.centery), 6)
        self._register_popup_button(f"popup:buoyancy:{node.node_id}", buoy_slider)
        y += 40

        biolum = cfg.get("biolum", 0.0)
        biolum_label = self.font.render(f"Bioluminescentie: {biolum:.2f}", True, settings.WHITE)
        surface.blit(biolum_label, (popup_rect.left + 12, y))
        biolum_slider = pygame.Rect(popup_rect.left + 12, y + 18, popup_rect.width - 24, 10)
        pygame.draw.rect(surface, (40, 60, 80), biolum_slider, border_radius=5)
        biolum_knob = biolum_slider.left + int(biolum * biolum_slider.width)
        pygame.draw.circle(surface, (250, 220, 120), (biolum_knob, biolum_slider.centery), 6)
        self._register_popup_button(f"popup:biolum:{node.node_id}", biolum_slider)
        y += 44

        surface.blit(self.font.render("Kleur", True, settings.WHITE), (popup_rect.left + 12, y))
        y += 22
        swatch_rects = []
        swatch_x = popup_rect.left + 12
        for idx, color in enumerate(COLOR_SWATCHES):
            rect = pygame.Rect(swatch_x, y, 28, 28)
            pygame.draw.rect(surface, color, rect, border_radius=4)
            pygame.draw.rect(surface, (20, 30, 40), rect, 1, border_radius=4)
            if color == tuple(cfg.get("color", COLOR_SWATCHES[0])):
                pygame.draw.rect(surface, settings.WHITE, rect, 2, border_radius=4)
            self._register_popup_button(f"popup:color:{idx}:{node.node_id}", rect)
            swatch_rects.append(rect)
            swatch_x += 34
        y += 40

        attach_label = self.font.render(f"Attachment points: {int(cfg.get('attachment_points', 3))}", True, settings.WHITE)
        surface.blit(attach_label, (popup_rect.left + 12, y))
        attach_minus = pygame.Rect(popup_rect.left + 190, y - 2, 24, 20)
        attach_plus = pygame.Rect(popup_rect.left + 220, y - 2, 24, 20)
        self._draw_mini_button(surface, attach_minus, "-")
        self._draw_mini_button(surface, attach_plus, "+")
        self._register_popup_button(f"popup:attach:-:{node.node_id}", attach_minus)
        self._register_popup_button(f"popup:attach:+:{node.node_id}", attach_plus)

    def _handle_popup_button(self, key: str) -> None:
        if not self._active_popup_node:
            return
        node = self._draft.get_module(self._active_popup_node)
        cfg = node.parameters.setdefault("editor", dict(DEFAULT_MODULE_CONFIG))
        if key == "popup:close":
            self._active_popup_node = None
            return
        if key.startswith("popup:scale:"):
            _, _, direction, _ = key.split(":")
            delta = 0.1 if direction == "+" else -0.1
            cfg["scale"] = max(0.3, min(3.0, cfg.get("scale", 1.0) + delta))
        elif key.startswith("popup:shape:"):
            current = cfg.get("shape", SHAPE_OPTIONS[0])
            idx = SHAPE_OPTIONS.index(current)
            cfg["shape"] = SHAPE_OPTIONS[(idx + 1) % len(SHAPE_OPTIONS)]
        elif key.startswith("popup:color:"):
            _, _, idx, _ = key.split(":")
            cfg["color"] = COLOR_SWATCHES[int(idx)]
        elif key.startswith("popup:attach:"):
            _, _, direction, _ = key.split(":")
            delta = 1 if direction == "+" else -1
            cfg["attachment_points"] = int(max(1, min(12, cfg.get("attachment_points", 3) + delta)))
        elif key.startswith("popup:buoyancy:"):
            self._apply_slider(cfg, "buoyancy", -1.0, 1.0)
        elif key.startswith("popup:biolum:"):
            self._apply_slider(cfg, "biolum", 0.0, 1.0)
        self._status_message = "Moduleparameters bijgewerkt"
        self._apply_editor_overrides(node, cfg)
        self._appearance_cache[node.node_id] = self._appearance_from_config(cfg)

    def _apply_slider(self, cfg: Dict[str, object], field: str, min_value: float, max_value: float) -> None:
        slider_rect = self._popup_buttons.get(f"popup:{field}:{self._active_popup_node}")
        if not slider_rect:
            return
        ratio = (self._last_click_pos.x - slider_rect.left) / slider_rect.width
        cfg[field] = max(min_value, min(max_value, ratio * (max_value - min_value) + min_value))

    def _apply_editor_overrides(self, node: ModuleDraft, cfg: Dict[str, object]) -> None:
        overrides = dict(node.parameters)
        scale = cfg.get("scale", 1.0)
        stats = overrides.setdefault("stats", {})
        stats["mass"] = scale
        stats["buoyancy_bias"] = cfg.get("buoyancy", 0.0)
        stats["power_output"] = scale
        overrides["color"] = cfg.get("color")
        overrides["biolum"] = cfg.get("biolum")
        node.parameters = overrides
        self._appearance_cache[node.node_id] = self._appearance_from_config(cfg)
        self.recalculate()

    def _clear_popup_buttons(self) -> None:
        self._popup_button_keys.clear()
        self._popup_buttons.clear()

    def _register_popup_button(self, key: str, rect: pygame.Rect) -> None:
        self._popup_buttons[key] = rect
        self._popup_button_keys.append(key)

    def _build_node_appearance(self) -> Dict[str, Dict[str, object]]:
        look: Dict[str, Dict[str, object]] = {}
        for module in self._draft.template.nodes:
            cfg = self._editor_config(module)
            look[module.node_id] = self._appearance_from_config(cfg)
        return look

    def _editor_config(self, module: ModuleDraft) -> Dict[str, object]:
        cfg = dict(DEFAULT_MODULE_CONFIG)
        cfg.update(module.parameters.get("editor", {}))
        return cfg

    def _appearance_from_config(self, cfg: Dict[str, object]) -> Dict[str, object]:
        return {
            "color": tuple(cfg.get("color", DEFAULT_MODULE_CONFIG["color"])),
            "biolum": float(cfg.get("biolum", DEFAULT_MODULE_CONFIG["biolum"])),
            "scale": float(cfg.get("scale", DEFAULT_MODULE_CONFIG["scale"])),
            "shape": cfg.get("shape", DEFAULT_MODULE_CONFIG["shape"]),
        }

    def _shape_polygon(self, shape: str, center: pygame.Vector2, scale: float) -> List[Tuple[int, int]]:
        if shape == "ellipse":
            return self._ellipse_polygon(center, scale * 18, scale * 12)
        if shape == "fin":
            return self._fin_polygon(center, scale * 20)
        if shape == "arrow":
            return self._arrow_polygon(center, scale * 20)
        if shape == "disk":
            return self._disk_polygon(center, scale * 12)
        return []

    def _ellipse_polygon(self, center: pygame.Vector2, a: float, b: float, segments: int = 7) -> List[Tuple[int, int]]:
        points = []
        offset_angle = 15.0
        for i in range(segments):
            theta = i * (math.pi * 2) / segments + math.radians(offset_angle)
            x = center.x + a * math.cos(theta)
            y = center.y + b * math.sin(theta)
            points.append((x, y))
        return points

    def _fin_polygon(self, center: pygame.Vector2, size: float) -> List[Tuple[int, int]]:
        tip = (center.x, center.y - size)
        base_left = (center.x - size * 0.6, center.y + size * 0.8)
        base_right = (center.x + size * 0.6, center.y + size * 0.8)
        return [tip, base_left, base_right]

    def _arrow_polygon(self, center: pygame.Vector2, size: float) -> List[Tuple[int, int]]:
        shaft = (center.x, center.y - size * 0.6)
        tip = (center.x, center.y - size)
        return [shaft, tip]

    def _disk_polygon(self, center: pygame.Vector2, radius: float, segments: int = 6) -> List[Tuple[int, int]]:
        return self._ellipse_polygon(center, radius, radius, segments)

    def _draw_attachment_points(self, surface: pygame.Surface, module: ModuleDraft) -> None:
        polygon: List[Tuple[int, int]] = self._appearance_cache.get(module.node_id, {}).get("polygon", [])
        if not polygon:
            return
        center = pygame.Vector2(sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon))
        try:
            attachment_points = self._draft.attachment_points(module.node_id)
        except Exception:
            attachment_points = []
        if not attachment_points:
            return
        for point in attachment_points:
            angle = math.radians(point.angle or 0.0)
            radius = 16.0 * self._appearance_cache.get(module.node_id, {}).get("scale", 1.0)
            direction = pygame.Vector2(math.cos(angle), math.sin(angle))
            if point.offset:
                direction.x += point.offset[0]
                direction.y += point.offset[1]
            handle = center + direction.normalize() * radius
            pygame.draw.circle(surface, (220, 240, 180), (int(handle.x), int(handle.y)), 5, 1)
            pygame.draw.circle(surface, (220, 240, 180), (int(handle.x), int(handle.y)), 2)
            label = self.font.render(point.name[:4], True, (220, 240, 180))
            surface.blit(label, (handle.x - label.get_width() / 2, handle.y - label.get_height() / 2))


    def _draw_attachment_points(self, surface: pygame.Surface, module: ModuleDraft) -> None:
        polygon: List[Tuple[int, int]] = self._appearance_cache.get(module.node_id, {}).get("polygon", [])
        if not polygon:
            return
        center = pygame.Vector2(sum(p[0] for p in polygon) / len(polygon), sum(p[1] for p in polygon) / len(polygon))
        try:
            attachment_points = self._draft.attachment_points(module.node_id)
        except Exception:
            attachment_points = []
        if not attachment_points:
            return
        for point in attachment_points:
            angle = math.radians(point.angle or 0.0)
            radius = 16.0 * self._appearance_cache.get(module.node_id, {}).get("scale", 1.0)
            direction = pygame.Vector2(math.cos(angle), math.sin(angle))
            if point.offset:
                direction.x += point.offset[0]
                direction.y += point.offset[1]
            handle = center + direction.normalize() * radius
            pygame.draw.circle(surface, (220, 240, 180), (int(handle.x), int(handle.y)), 5, 1)
            pygame.draw.circle(surface, (220, 240, 180), (int(handle.x), int(handle.y)), 2)
            label = self.font.render(point.name[:4], True, (220, 240, 180))
            surface.blit(label, (handle.x - label.get_width() / 2, handle.y - label.get_height() / 2))
