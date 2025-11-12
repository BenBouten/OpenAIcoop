"""Player management functionality."""
from __future__ import annotations

from typing import List

import pygame

from . import settings
from .notifications import NotificationManager


class PlayerController:
    def __init__(
        self,
        notification_manager: NotificationManager,
        dna_profiles: List[dict],
        lifeforms: List[object],
    ):
        self.notification_manager = notification_manager
        self.dna_profiles = dna_profiles
        self.lifeforms = lifeforms
        self.resources = {"dna_points": 120}
        self.management_mode = False
        self.selected_profile = 0
        self.attributes = [
            "health",
            "vision",
            "attack_power",
            "defence_power",
            "energy",
            "longevity",
        ]
        self.selected_attribute_index = 0

    def reset(self) -> None:
        self.resources = {"dna_points": 120}
        self.management_mode = False
        self.selected_profile = 0
        self.selected_attribute_index = 0

    def toggle_management(self) -> None:
        self.management_mode = not self.management_mode
        state = "geopend" if self.management_mode else "gesloten"
        self.notification_manager.add(f"Genlab {state}.")

    def cycle_profile(self, direction: int) -> None:
        if not self.dna_profiles:
            return
        self.selected_profile = (self.selected_profile + direction) % len(self.dna_profiles)

    def cycle_attribute(self, direction: int) -> None:
        self.selected_attribute_index = (self.selected_attribute_index + direction) % len(self.attributes)

    def adjust_attribute(self, direction: int) -> None:
        if not self.dna_profiles:
            return
        profile = self.dna_profiles[self.selected_profile]
        attribute = self.attributes[self.selected_attribute_index]
        cost = 6
        modifier = 3 * direction
        if direction > 0:
            if self.resources["dna_points"] < cost:
                self.notification_manager.add("Onvoldoende DNA-punten.", settings.RED)
                return
            profile[attribute] += modifier
            self.resources["dna_points"] -= cost
            self.notification_manager.add(
                f"DNA {profile['dna_id']}: +{modifier} {attribute}.", settings.GREEN
            )
        else:
            new_value = max(1, profile[attribute] + modifier)
            profile[attribute] = new_value
            self.resources["dna_points"] += cost // 2
            self.notification_manager.add(
                f"DNA {profile['dna_id']}: -{abs(modifier)} {attribute} voor punten.", settings.BLUE
            )

        for lifeform in self.lifeforms:
            if getattr(lifeform, "dna_id", None) == profile["dna_id"]:
                setattr(lifeform, attribute, profile[attribute])
                if attribute == "health":
                    lifeform.health_now = min(lifeform.health, lifeform.health_now)
                if attribute == "energy":
                    lifeform.energy_now = min(lifeform.energy, lifeform.energy_now)

    def apply_reward(self, reward: dict) -> None:
        points = reward.get("dna_points", 0)
        if points:
            self.resources["dna_points"] += points
            self.notification_manager.add(
                f"Beloning: {points} DNA-punten ontvangen!", settings.GREEN
            )

    def on_birth(self) -> None:
        self.resources["dna_points"] += 1

    def draw_overlay(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        panel_x = surface.get_width() - 220
        panel_y = 20
        pygame.draw.rect(surface, (240, 240, 240), (panel_x - 10, panel_y - 10, 200, 120), border_radius=6)
        pygame.draw.rect(surface, settings.BLACK, (panel_x - 10, panel_y - 10, 200, 120), 2, border_radius=6)
        dna_text = font.render(f"DNA-punten: {self.resources['dna_points']}", True, settings.BLACK)
        surface.blit(dna_text, (panel_x, panel_y))
        if self.management_mode and self.dna_profiles:
            profile = self.dna_profiles[self.selected_profile]
            attribute = self.attributes[self.selected_attribute_index]
            lines = [
                "Genlab actief",
                f"Profiel: {profile['dna_id']}",
                f"Attribuut: {attribute}",
                f"Waarde: {profile[attribute]}",
            ]
            y_offset = panel_y + 20
            for line in lines:
                text_surface = font.render(line, True, settings.BLACK)
                surface.blit(text_surface, (panel_x, y_offset))
                y_offset += 20
