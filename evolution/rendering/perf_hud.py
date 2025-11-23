"""Small runtime HUD for render/perf telemetry."""

from __future__ import annotations

from typing import Dict, Tuple

import pygame

WARNING_COLOR = (240, 120, 120)
INFO_COLOR = (235, 245, 255)
BACKGROUND_COLOR = (12, 20, 32, 170)


class PerfHUD:
    """Render a compact overlay with live render stats and toggles."""

    def __init__(self) -> None:
        self.visible = True
        self._font = pygame.font.Font(None, 18)
        self._metrics: Dict[str, object] = {}
        self._warn_entity_blits = False
        self._warn_rebuilds = False

    def toggle(self) -> None:
        self.visible = not self.visible

    def update(self, metrics: Dict[str, object]) -> None:
        self._metrics = metrics
        entity_blits = int(metrics.get("entity_blits", 0))
        rebuilds = int(metrics.get("chunk_rebuilds", 0))
        self._warn_entity_blits = entity_blits > 1500
        self._warn_rebuilds = rebuilds > 2

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible or not self._metrics:
            return

        lines = self._build_lines()
        if not lines:
            return

        padding = 8
        line_height = self._font.get_height()
        width = max(self._font.size(text)[0] for text, _ in lines) + padding * 2
        height = line_height * len(lines) + padding * 2

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill(BACKGROUND_COLOR)

        for idx, (text, color) in enumerate(lines):
            panel.blit(self._font.render(text, True, color), (padding, padding + idx * line_height))

        surface.blit(panel, (12, 12))

    def _build_lines(self) -> Tuple[Tuple[str, Tuple[int, int, int]], ...]:
        fps = float(self._metrics.get("fps", 0.0))
        visible_chunks = int(self._metrics.get("visible_chunks", 0))
        chunk_size = int(self._metrics.get("chunk_size", 0))
        culling_margin = int(self._metrics.get("culling_margin", 0))
        entity_blits = int(self._metrics.get("entity_blits", 0))
        chunk_rebuilds = int(self._metrics.get("chunk_rebuilds", 0))
        render_ms = float(self._metrics.get("render_ms", 0.0))
        streaming = bool(self._metrics.get("streaming", False))
        rebuild_queue = int(self._metrics.get("rebuild_queue", 0))

        lines = [
            (f"FPS: {fps:5.1f} | Render: {render_ms:4.1f} ms", INFO_COLOR),
            (
                f"Chunks vis: {visible_chunks} @ {chunk_size}px | streaming: {'on' if streaming else 'off'}",
                INFO_COLOR,
            ),
            (
                f"Culling margin: {culling_margin}px | Rebuilds: {chunk_rebuilds} (queue {rebuild_queue})",
                WARNING_COLOR if self._warn_rebuilds else INFO_COLOR,
            ),
            (
                f"Entity blits: {entity_blits}",
                WARNING_COLOR if self._warn_entity_blits else INFO_COLOR,
            ),
            ("Toggles: [F3] HUD [F5] streaming [ [ ] chunk [ ; ' ] margin", INFO_COLOR),
        ]
        return tuple(lines)
