"""Attachment primitives describing how body modules connect to each other."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence, Tuple, Type, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used only for type checking to avoid circular import
    from .modules import BodyModule


class JointType(str, Enum):
    """Enumeration describing the mechanical joint type between two modules."""

    FIXED = "fixed"
    HINGE = "hinge"
    BALL = "ball"
    MUSCLE = "muscle"


@dataclass(frozen=True)
class Joint:
    """Mechanical joint data describing motion constraints between modules."""

    joint_type: JointType
    swing_limits: Tuple[float, float] | None = None
    twist_limits: Tuple[float, float] | None = None
    torque_limit: float | None = None

    def describe_limits(self) -> str:
        """Return a human readable description of the joint limits."""

        parts: list[str] = [self.joint_type.value]
        if self.swing_limits:
            parts.append(f"swing={self.swing_limits[0]:.1f}/{self.swing_limits[1]:.1f}")
        if self.twist_limits:
            parts.append(f"twist={self.twist_limits[0]:.1f}/{self.twist_limits[1]:.1f}")
        if self.torque_limit is not None:
            parts.append(f"torque<= {self.torque_limit:.1f}")
        return ", ".join(parts)


@dataclass(frozen=True)
class AttachmentPoint:
    """Defines where a child module can connect to a parent module."""

    name: str
    joint: Joint
    allowed_modules: Sequence[Type["BodyModule"]]
    description: str = ""
    max_child_mass: float | None = None
    allowed_materials: Sequence[str] | None = None
    offset: Tuple[float, float] = (0.0, 0.0)
    angle: float = 0.0
    clearance: float = 0.0
    relative: bool = False

    def allows(self, module: "BodyModule" | Type["BodyModule"]) -> bool:
        """Return ``True`` if the ``module`` is allowed to attach here."""

        module_type = module if isinstance(module, type) else type(module)
        if not any(issubclass(module_type, allowed) for allowed in self.allowed_modules):
            return False

        if isinstance(module, type):
            return True

        stats = getattr(module, "stats", None)
        if self.max_child_mass is not None:
            if stats is None or stats.mass > self.max_child_mass:
                return False

        if self.allowed_materials is not None:
            material = getattr(module, "material", None)
            if material is None or material not in self.allowed_materials:
                return False
        return True
