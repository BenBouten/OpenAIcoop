"""Pheromone entity extracted from the simulation module."""

from __future__ import annotations

import pygame


class Pheromone:
    def __init__(self, x, y, width, height, color, strength):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.strength = strength

    def draw(self, surface):
        r = int(self.color[0] + (255 - self.color[0]) * (255 - self.strength) / 255)
        g = int(self.color[1] + (255 - self.color[1]) * (255 - self.strength) / 255)
        b = int(self.color[2] + (255 - self.color[2]) * (255 - self.strength) / 255)
        color = (r, g, b)
        pygame.draw.rect(surface, color, (self.x, self.y, self.width, self.height))


