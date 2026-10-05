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


def _reachable(rooms, connections, start):
    adjacency = {r["id"]: [] for r in rooms}
    for a, b in connections:
        adjacency[a].append(b)
        adjacency[b].append(a)
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(adjacency[cur])
    return seen


class TestLevelGenerator:
    def setup_method(self):
        self.system = LevelGenerator()

    # ---- 关卡生成：房间 + 连接 ----

    def test_case_01(self):
        """生成的关卡包含多个房间"""
        level = self.system.generate_level(seed=1)
        assert len(level["rooms"]) >= 4

    def test_case_02(self):
        """房间类型齐全：必有入口和出口"""
        level = self.system.generate_level(seed=2)
        types = {r["type"] for r in level["rooms"]}
        assert "entrance" in types
        assert "exit" in types

    def test_case_03(self):
        """房间之间存在连接通道"""
        level = self.system.generate_level(seed=3)
        assert len(level["connections"]) > 0
        room_ids = {r["id"] for r in level["rooms"]}
        for a, b in level["connections"]:
            assert a in room_ids and b in room_ids

    def test_case_04(self):
        """从入口出发可达所有房间（图连通）"""
        level = self.system.generate_level(seed=4)
        entrance = next(r for r in level["rooms"] if r["type"] == "entrance")
        seen = _reachable(level["rooms"], level["connections"], entrance["id"])
        assert seen == {r["id"] for r in level["rooms"]}

    def test_case_05(self):
        """相同种子可复现，不同种子生成不同关卡"""
        a = self.system.generate_level(seed=42)
        b = self.system.generate_level(seed=42)
        c = self.system.generate_level(seed=43)
        assert a["rooms"] == b["rooms"]
        assert a["connections"] == b["connections"]
        assert (a["rooms"], a["connections"]) != (c["rooms"], c["connections"])

    # ---- 难度曲线：递增 + 波动 ----

    def test_case_06(self):
        """难度曲线整体递增：后半段平均难度高于前半段"""
        curve = self.system.difficulty_curve(20)
        half = len(curve) // 2
        assert sum(curve[half:]) / half > sum(curve[:half]) / half

    def test_case_07(self):
        """难度曲线有波动：存在局部下降（有难有易调节奏）"""
        curve = self.system.difficulty_curve(20)
        dips = sum(1 for i in range(1, len(curve)) if curve[i] < curve[i - 1])
        assert dips >= 2

    def test_case_08(self):
        """难度值都在 [0, 1] 合法范围内且不是恒定值"""
        curve = self.system.difficulty_curve(20)
        assert all(0.0 <= v <= 1.0 for v in curve)
        assert len(set(curve)) > 1

    # ---- 关卡设计：节奏 + 引导 ----

    def test_case_09(self):
        """设计包含节奏序列，且战斗与探索交替出现"""
        level = self.system.generate_level(seed=5)
        design = self.system.level_design(level)
        categories = {p["category"] for p in design["pacing"]}
        assert "combat" in categories
        assert "exploration" in categories

    def test_case_10(self):
        """引导给出从入口到出口的关键路径"""
        level = self.system.generate_level(seed=6)
        design = self.system.level_design(level)
        path = design["guidance"]["critical_path"]
        rooms = {r["id"]: r for r in level["rooms"]}
        assert rooms[path[0]]["type"] == "entrance"
        assert rooms[path[-1]]["type"] == "exit"
        edges = {tuple(sorted(c)) for c in level["connections"]}
        for i in range(len(path) - 1):
            assert tuple(sorted((path[i], path[i + 1]))) in edges

    def test_case_11(self):
        """引导包含提示信息，帮助玩家知道往哪走"""
        level = self.system.generate_level(seed=7)
        design = self.system.level_design(level)
        assert len(design["guidance"]["hints"]) > 0

    # ---- 玩家体验：心流 + 反馈 ----

    def test_case_12(self):
        """挑战远高于能力时玩家焦虑，远低于能力时无聊"""
        anxious = self.system.player_experience(skill=0.2, challenge=0.9)
        bored = self.system.player_experience(skill=0.9, challenge=0.1)
        assert anxious["flow_state"] == "anxious"
        assert bored["flow_state"] == "bored"

    def test_case_13(self):
        """挑战与能力匹配时玩家处于心流状态"""
        result = self.system.player_experience(skill=0.5, challenge=0.55)
        assert result["flow_state"] == "flow"
        assert result["flow_score"] > 0.5

    def test_case_14(self):
        """体验评估必须给出可执行的反馈建议"""
        for skill, challenge in [(0.2, 0.9), (0.9, 0.1), (0.5, 0.5)]:
            result = self.system.player_experience(skill=skill,
                                                   challenge=challenge)
            assert len(result["feedback"]) > 0

    # ---- 自适应难度：评估 + 调整 ----

    def test_case_15(self):
        """能评估玩家水平：表现差评为 struggling，表现好评为 dominating"""
        bad = self.system.adaptive_difficulty(
            {"deaths": 8, "completion_time": 600, "expected_time": 300,
             "hit_rate": 0.2})
        good = self.system.adaptive_difficulty(
            {"deaths": 0, "completion_time": 200, "expected_time": 300,
             "hit_rate": 0.95})
        assert bad["evaluation"] == "struggling"
        assert good["evaluation"] == "dominating"
        assert good["skill"] > bad["skill"]

    def test_case_16(self):
        """根据评估调整难度：太简单上调，太难下调，且保持在 [0, 1]"""
        easy = self.system.adaptive_difficulty(
            {"deaths": 0, "hit_rate": 0.95}, current_difficulty=0.5)
        hard = self.system.adaptive_difficulty(
            {"deaths": 10, "hit_rate": 0.1}, current_difficulty=0.5)
        assert easy["adjusted_difficulty"] > 0.5
        assert hard["adjusted_difficulty"] < 0.5
        assert 0.0 <= easy["adjusted_difficulty"] <= 1.0
        assert 0.0 <= hard["adjusted_difficulty"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
