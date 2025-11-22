"""Persistence helpers for Creature Creator templates."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

from ..config import settings
from .templates import CreatureTemplate

_TEMPLATE_DIR = Path(getattr(settings, "CREATURE_TEMPLATE_DIR", "creature_templates"))
_SLUG_PATTERN = re.compile(r"[^a-z0-9_]+")


def _ensure_dir(directory: Optional[Path] = None) -> Path:
    target = Path(directory) if directory is not None else _TEMPLATE_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _slugify(name: str) -> str:
    base = name.strip().lower().replace(" ", "_")
    slug = _SLUG_PATTERN.sub("", base)
    return slug or "template"


def template_path(name: str, *, directory: Optional[Path] = None) -> Path:
    folder = _ensure_dir(directory)
    slug = _slugify(name)
    return folder / f"{slug}.json"


def list_templates(*, directory: Optional[Path] = None) -> List[str]:
    folder = _ensure_dir(directory)
    return sorted(path.stem for path in folder.glob("*.json"))


def save_template(template: CreatureTemplate, *, directory: Optional[Path] = None) -> Path:
    path = template_path(template.name, directory=directory)
    data = template.to_dict()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path


def load_template(name: str, *, directory: Optional[Path] = None) -> CreatureTemplate:
    path = template_path(name, directory=directory)
    if not path.exists():
        raise FileNotFoundError(f"Template '{name}' not found at {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return CreatureTemplate.from_dict(data)


def import_templates(files: Iterable[Path], *, directory: Optional[Path] = None) -> List[Path]:
    saved: List[Path] = []
    for file_path in files:
        with Path(file_path).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        template = CreatureTemplate.from_dict(data)
        saved.append(save_template(template, directory=directory))
    return saved


def delete_template(name: str, *, directory: Optional[Path] = None) -> None:
    path = template_path(name, directory=directory)
    if not path.exists():
        raise FileNotFoundError(f"Template '{name}' not found at {path}")
    path.unlink()


def rename_template(old_name: str, new_name: str, *, directory: Optional[Path] = None) -> Path:
    if not new_name.strip():
        raise ValueError("Nieuwe naam mag niet leeg zijn")
    template = load_template(old_name, directory=directory)
    template.name = new_name
    dest = template_path(new_name, directory=directory)
    src = template_path(old_name, directory=directory)
    if dest != src and dest.exists():
        raise FileExistsError(f"Template '{new_name}' bestaat al")
    save_template(template, directory=directory)
    if dest != src and src.exists():
        src.unlink()
    return dest
