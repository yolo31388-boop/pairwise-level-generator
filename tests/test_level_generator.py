"""
游戏内程序化关卡生成与难度曲线系统 - 验收测试
运行方式：python -m pytest tests/test_level_generator.py -q
共 16 个测试用例
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from level.generator import LevelGenerator


def _reachable(connections, start):
    adjacency = {}
    for conn in connections:
        adjacency.setdefault(conn["from"], set()).add(conn["to"])
        adjacency.setdefault(conn["to"], set()).add(conn["from"])
    seen, stack = set(), [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, ()))
    return seen


class TestLevelGenerator:
    def setup_method(self):
        self.system = LevelGenerator()

    # ---- generate_level：房间与连接 ----

    def test_case_01(self):
        level = self.system.generate_level(seed=1, num_rooms=8)
        assert len(level["rooms"]) == 8
        assert len(level["connections"]) > 0

    def test_case_02(self):
        level = self.system.generate_level(seed=2, num_rooms=8)
        room_ids = {room["id"] for room in level["rooms"]}
        assert _reachable(level["connections"], 0) == room_ids

    def test_case_03(self):
        level_a = self.system.generate_level(seed=3, num_rooms=8)
        level_b = self.system.generate_level(seed=4, num_rooms=8)
        types_a = [room["type"] for room in level_a["rooms"]]
        types_b = [room["type"] for room in level_b["rooms"]]
        assert types_a != types_b

    def test_case_04(self):
        level = self.system.generate_level(seed=5, num_rooms=8)
        room_ids = {room["id"] for room in level["rooms"]}
        for conn in level["connections"]:
            assert conn["from"] in room_ids
            assert conn["to"] in room_ids
            assert conn["from"] != conn["to"]

    # ---- difficulty_curve：递增与波动 ----

    def test_case_05(self):
        curve = self.system.difficulty_curve(num_levels=10)
        assert len(curve) == 10
        assert curve[-1] > curve[0]
        first_half = sum(curve[:5]) / 5
        second_half = sum(curve[5:]) / 5
        assert second_half > first_half

    def test_case_06(self):
        curve = self.system.difficulty_curve(num_levels=10)
        assert any(curve[i + 1] < curve[i] for i in range(len(curve) - 1))

    def test_case_07(self):
        curve = self.system.difficulty_curve(num_levels=12, base=1.0, wave=0.2)
        assert all(value > 0 for value in curve)
        assert curve == self.system.difficulty_curve(num_levels=12, base=1.0, wave=0.2)

    # ---- level_design：节奏与引导 ----

    def test_case_08(self):
        level = self.system.generate_level(seed=6, num_rooms=10)
        design = self.system.level_design(level)
        phases = {item["phase"] for item in design["pacing"]}
        assert "combat" in phases
        assert "explore" in phases
        assert len(design["pacing"]) == len(level["rooms"])

    def test_case_09(self):
        level = self.system.generate_level(seed=7, num_rooms=10)
        design = self.system.level_design(level)
        path = design["guidance"]["path"]
        assert path[0] == level["rooms"][0]["id"]
        assert path[-1] == level["rooms"][-1]["id"]
        edges = {(c["from"], c["to"]) for c in level["connections"]}
        edges |= {(c["to"], c["from"]) for c in level["connections"]}
        for a, b in zip(path, path[1:]):
            assert (a, b) in edges

    def test_case_10(self):
        level = self.system.generate_level(seed=8, num_rooms=10)
        design = self.system.level_design(level)
        hints = design["guidance"]["hints"]
        assert len(hints) == len(design["guidance"]["path"])
        assert all(hint["hint"] for hint in hints)
        assert design["principles"]

    # ---- player_experience：心流与反馈 ----

    def test_case_11(self):
        result = self.system.player_experience({"skill": 0.5, "challenge": 0.5})
        assert result["flow_state"] == "flow"
        assert result["flow_score"] > 0.9

    def test_case_12(self):
        anxious = self.system.player_experience({"skill": 0.2, "challenge": 0.9})
        bored = self.system.player_experience({"skill": 0.9, "challenge": 0.1})
        assert anxious["flow_state"] == "anxiety"
        assert bored["flow_state"] == "boredom"

    def test_case_13(self):
        for metrics in ({"skill": 0.5, "challenge": 0.5},
                        {"skill": 0.2, "challenge": 0.9},
                        {"skill": 0.9, "challenge": 0.1}):
            result = self.system.player_experience(metrics)
            assert result["feedback"]
            assert all(isinstance(item, str) and item for item in result["feedback"])

    # ---- adaptive_difficulty：评估与调整 ----

    def test_case_14(self):
        result = self.system.adaptive_difficulty(
            {"win_rate": 0.95, "deaths": 0, "completion": 1.0})
        assert result["evaluation"]["level"] == "expert"
        assert 0.0 <= result["evaluation"]["skill_score"] <= 1.0

    def test_case_15(self):
        strong = self.system.adaptive_difficulty(
            {"win_rate": 0.95, "deaths": 0, "completion": 1.0})
        assert strong["adjustment"] > 0
        self.system.reset()
        weak = self.system.adaptive_difficulty(
            {"win_rate": 0.05, "deaths": 9, "completion": 0.1})
        assert weak["adjustment"] < 0

    def test_case_16(self):
        self.system.adaptive_difficulty(
            {"win_rate": 0.95, "deaths": 0, "completion": 1.0})
        result = self.system.adaptive_difficulty(
            {"win_rate": 0.95, "deaths": 0, "completion": 1.0})
        assert result["new_difficulty"] > self.system.config.get("difficulty", 1.0)
        level = self.system.generate_level(seed=9, num_rooms=6)
        assert level["difficulty"] > 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
