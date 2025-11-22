"""Regression tests for BodyGraph spatial transforms and layout."""

from __future__ import annotations

import math

import pytest

from evolution.body.body_graph import BodyGraph
from evolution.body.modules import (
    TrunkCore,
    CephalonHead,
    HydroFin,
    TailThruster,
    SensorPod,
)


@pytest.fixture()
def assembled_graph() -> BodyGraph:
    core = TrunkCore(key="core")
    head = CephalonHead(key="head")
    fin_left = HydroFin(key="fin_left")
    fin_right = HydroFin(key="fin_right")
    thruster = TailThruster(key="thruster")
    cranial_sensor = SensorPod(key="sensor_head")
    tail_sensor = SensorPod(key="sensor_tail")

    graph = BodyGraph("core", core)
    graph.add_module("head", head, "core", "head_socket")
    graph.add_module("fin_left", fin_left, "core", "lateral_mount_left")
    graph.add_module("fin_right", fin_right, "core", "lateral_mount_right")
    graph.add_module("thruster", thruster, "core", "ventral_core")
    graph.add_module("sensor_head", cranial_sensor, "head", "cranial_sensor")
    graph.add_module("sensor_tail", tail_sensor, "thruster", "tail_sensors")
    return graph


def _angle_close(value: float, expected: float, eps: float = 1e-3) -> bool:
    return math.isclose((value - expected + 180.0) % 360.0, 180.0, abs_tol=eps)


def test_core_remains_origin(assembled_graph: BodyGraph) -> None:
    assert assembled_graph.node_transform("core") == pytest.approx((0.0, 0.0, 0.0))


def test_modules_extend_outward(assembled_graph: BodyGraph) -> None:
    head = assembled_graph.node_transform("head")
    left = assembled_graph.node_transform("fin_left")
    right = assembled_graph.node_transform("fin_right")
    tail = assembled_graph.node_transform("thruster")

    assert head[1] > 0.0  # dorsal attachment
    assert left[0] < 0.0  # port fin extends left
    assert right[0] > 0.0  # starboard fin extends right
    assert tail[1] < 0.0  # ventral thruster sits below core

    assert _angle_close(head[2], 0.0)
    assert _angle_close(left[2], 180.0)
    assert _angle_close(right[2], 0.0)
    assert _angle_close(tail[2], 180.0)


def test_nested_children_follow_parent_orientation(assembled_graph: BodyGraph) -> None:
    sensor_head = assembled_graph.node_transform("sensor_head")
    sensor_tail = assembled_graph.node_transform("sensor_tail")

    head_y = assembled_graph.node_transform("head")[1]
    thruster_x = assembled_graph.node_transform("thruster")[0]
    assert sensor_head[1] >= head_y
    assert sensor_tail[0] <= thruster_x
    assert _angle_close(sensor_tail[2], assembled_graph.node_transform("thruster")[2])
