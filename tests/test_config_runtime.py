"""Tests for the runtime configuration loader."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evolution.config import settings


def _write_tmp_config(tmp_path: Path, content: str) -> Path:
    file_path = tmp_path / "conf.yaml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_env_overrides_take_effect(monkeypatch):
    monkeypatch.setenv("EVOLUTION_WORLD_WIDTH", "9999")
    conf = settings.load_runtime_settings(args=[], env=os.environ)
    assert conf.WORLD_WIDTH == 9999


def test_cli_overrides_take_precedence():
    conf = settings.load_runtime_settings(args=["--world-width", "1234"])
    assert conf.WORLD_WIDTH == 1234


def test_config_file_used_when_provided(tmp_path):
    config = _write_tmp_config(tmp_path, "world_width: 7777\nfps: 15\n")
    conf = settings.load_runtime_settings(args=["--config", str(config)])
    assert conf.WORLD_WIDTH == 7777
    assert conf.FPS == 15


def test_env_overrides_config(monkeypatch, tmp_path):
    config = _write_tmp_config(tmp_path, "world_width: 4000\n")
    monkeypatch.setenv("EVOLUTION_WORLD_WIDTH", "4500")
    conf = settings.load_runtime_settings(args=["--config", str(config)], env=os.environ)
    assert conf.WORLD_WIDTH == 4500


def test_cli_overrides_config_and_env(monkeypatch, tmp_path):
    config = _write_tmp_config(tmp_path, "world_width: 4000\n")
    monkeypatch.setenv("EVOLUTION_WORLD_WIDTH", "4500")
    conf = settings.load_runtime_settings(args=["--config", str(config), "--world-width", "4700"], env=os.environ)
    assert conf.WORLD_WIDTH == 4700


def test_invalid_field_in_config_raises(tmp_path):
    config = _write_tmp_config(tmp_path, "unknown_value: 1\n")
    with pytest.raises(ValueError, match="Unknown config field"):
        settings.load_runtime_settings(args=["--config", str(config)])


def test_missing_config_file_errors(tmp_path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        settings.load_runtime_settings(args=["--config", str(missing)])


def test_invalid_numeric_range_raises(tmp_path):
    config = _write_tmp_config(tmp_path, "world_width: 100000\n")
    with pytest.raises(ValueError, match="WORLD_WIDTH"):
        settings.load_runtime_settings(args=["--config", str(config)])


def test_invalid_relationship_raises(tmp_path):
    config = _write_tmp_config(tmp_path, "n_lifeforms: 500\nmax_lifeforms: 100\n")
    with pytest.raises(ValueError, match="N_LIFEFORMS cannot exceed MAX_LIFEFORMS"):
        settings.load_runtime_settings(args=["--config", str(config)])
