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

    def allows(self, module: "BodyModule" | Type["BodyModule"]) -> bool:
        """Return ``True`` if the ``module`` is allowed to attach here."""

        module_type = module if isinstance(module, type) else type(module)
        return any(issubclass(module_type, allowed) for allowed in self.allowed_modules)
