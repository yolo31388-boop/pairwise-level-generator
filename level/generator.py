"""
游戏内程序化关卡生成与难度曲线系统 - 核心模块
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import random
import time


@dataclass
class Config:
    pass


class LevelGenerator:
    """程序化关卡生成 + 难度曲线 + 关卡设计 + 玩家体验 + 自适应难度。"""

    ROOM_TYPES = ("combat", "explore", "treasure", "rest")
    # 节奏模板：探索 -> 战斗 -> 战斗 -> 休整，循环往复形成张弛节奏
    PACING_TEMPLATE = ("explore", "combat", "combat", "rest")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._state = {}
        self._history = []
        self._difficulty_adjustment = 0.0

    def update(self, dt: float):
        self._state["time"] = self._state.get("time", 0.0) + dt

    def reset(self):
        self._state = {}
        self._history = []
        self._difficulty_adjustment = 0.0

    # ------------------------------------------------------------------
    # 1. 程序化关卡生成：房间 + 连接
    # ------------------------------------------------------------------
    def generate_level(self, seed: Optional[int] = None,
                       num_rooms: Optional[int] = None,
                       difficulty: Optional[float] = None) -> Dict:
        """按种子程序化生成关卡，包含房间列表与房间之间的连接。"""
        if seed is None:
            seed = time.time_ns()
        rng = random.Random(seed)
        if num_rooms is None:
            num_rooms = self.config.get("num_rooms", rng.randint(6, 10))
        num_rooms = max(3, int(num_rooms))
        if difficulty is None:
            difficulty = self.config.get("difficulty", 1.0) + self._difficulty_adjustment

        rooms = []
        for i in range(num_rooms):
            if i == 0:
                room_type = "start"
            elif i == num_rooms - 1:
                room_type = "boss"
            else:
                room_type = rng.choice(self.ROOM_TYPES)
            rooms.append({
                "id": i,
                "type": room_type,
                "x": i * 10 + rng.randint(-2, 2),
                "y": rng.randint(-5, 5),
                "difficulty": round(difficulty * (1.0 + i / max(1, num_rooms - 1)), 4),
            })

        connections = []
        edges = set()

        def _link(a: int, b: int, kind: str):
            edge = (min(a, b), max(a, b))
            if edge in edges or a == b:
                return
            edges.add(edge)
            connections.append({"from": edge[0], "to": edge[1], "type": kind})

        # 主路径：保证所有房间连通
        for i in range(num_rooms - 1):
            _link(i, i + 1, "corridor")
        # 额外支路：增加关卡多样性
        for _ in range(num_rooms // 2):
            _link(rng.randrange(num_rooms), rng.randrange(num_rooms), "branch")

        level = {
            "seed": seed,
            "difficulty": difficulty,
            "rooms": rooms,
            "connections": connections,
        }
        self._history.append(level)
        return level

    # ------------------------------------------------------------------
    # 2. 难度曲线：整体递增 + 局部波动
    # ------------------------------------------------------------------
    def difficulty_curve(self, num_levels: int = 10, base: float = 1.0,
                         growth: float = 0.3, wave: float = 0.2) -> List[float]:
        """生成难度曲线：线性递增趋势叠加正弦波动，张弛有度。"""
        num_levels = max(2, int(num_levels))
        curve = []
        for i in range(num_levels):
            trend = base + growth * i
            fluctuation = 2.0 * wave * math.sin(i * math.pi / 2.0)
            curve.append(round(trend + fluctuation, 4))
        return curve

    # ------------------------------------------------------------------
    # 3. 关卡设计：节奏（哪里战斗哪里探索）+ 引导（玩家往哪走）
    # ------------------------------------------------------------------
    def level_design(self, level: Optional[Dict] = None) -> Dict:
        """为关卡生成设计方案：节奏编排与玩家引导路径。"""
        if level is None:
            level = self.generate_level()
        rooms = level["rooms"]
        connections = level["connections"]

        pacing = []
        for i, room in enumerate(rooms):
            if room["type"] == "start":
                phase = "intro"
            elif room["type"] == "boss":
                phase = "climax"
            else:
                phase = self.PACING_TEMPLATE[(i - 1) % len(self.PACING_TEMPLATE)]
            pacing.append({"room_id": room["id"], "phase": phase})

        guidance = self._find_path(connections, rooms[0]["id"], rooms[-1]["id"])
        hints = []
        for step, room_id in enumerate(guidance):
            if step == 0:
                hints.append({"room_id": room_id, "hint": "起点：跟随主路前进"})
            elif step == len(guidance) - 1:
                hints.append({"room_id": room_id, "hint": "终点：Boss 房间，做好准备"})
            else:
                hints.append({"room_id": room_id,
                              "hint": "前往下一个目标房间 %d" % guidance[step + 1]})

        return {
            "principles": ["张弛有度", "先探索后战斗", "Boss 前休整", "主路清晰可见"],
            "pacing": pacing,
            "guidance": {"path": guidance, "hints": hints},
        }

    @staticmethod
    def _find_path(connections: List[Dict], start: int, goal: int) -> List[int]:
        """BFS 求 start 到 goal 的引导路径。"""
        adjacency: Dict[int, List[int]] = {}
        for conn in connections:
            adjacency.setdefault(conn["from"], []).append(conn["to"])
            adjacency.setdefault(conn["to"], []).append(conn["from"])
        queue = [(start, [start])]
        visited = {start}
        while queue:
            node, path = queue.pop(0)
            if node == goal:
                return path
            for nxt in adjacency.get(node, []):
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [nxt]))
        return [start]

    # ------------------------------------------------------------------
    # 4. 玩家体验：心流评估 + 改进反馈
    # ------------------------------------------------------------------
    def player_experience(self, metrics: Optional[Dict] = None) -> Dict:
        """根据挑战与玩家水平评估心流状态，并给出改进反馈。"""
        metrics = metrics or {}
        skill = float(metrics.get("skill", 0.5))
        challenge = float(metrics.get("challenge",
                                      self.config.get("difficulty", 1.0) / 2.0))
        delta = challenge - skill
        flow_score = max(0.0, 1.0 - abs(delta) * 2.0)

        if abs(delta) <= 0.15:
            state = "flow"
        elif delta > 0:
            state = "anxiety"
        else:
            state = "boredom"

        feedback = []
        if state == "flow":
            feedback.append("挑战与水平匹配，保持当前节奏")
        elif state == "anxiety":
            feedback.append("挑战过高，建议降低难度或增加补给")
            feedback.append("在高压区域前增加休整房间")
        else:
            feedback.append("挑战过低，建议提高敌人强度或密度")
            feedback.append("增加战斗房间比例以提升张力")

        return {
            "flow_state": state,
            "flow_score": round(flow_score, 4),
            "challenge": challenge,
            "skill": skill,
            "feedback": feedback,
        }

    # ------------------------------------------------------------------
    # 5. 自适应难度：评估玩家水平 + 动态调整难度
    # ------------------------------------------------------------------
    def adaptive_difficulty(self, performance: Optional[Dict] = None) -> Dict:
        """评估玩家表现并据此调整后续关卡难度。"""
        performance = performance or {}
        win_rate = float(performance.get("win_rate", 0.5))
        deaths = float(performance.get("deaths", 0))
        completion = float(performance.get("completion", 0.5))

        skill_score = max(0.0, min(1.0,
            0.6 * win_rate + 0.3 * completion + 0.1 * max(0.0, 1.0 - deaths / 10.0)))
        if skill_score >= 0.7:
            level_name = "expert"
        elif skill_score >= 0.4:
            level_name = "intermediate"
        else:
            level_name = "beginner"

        if skill_score > 0.75:
            adjustment = 0.2
        elif skill_score > 0.6:
            adjustment = 0.1
        elif skill_score < 0.25:
            adjustment = -0.2
        elif skill_score < 0.4:
            adjustment = -0.1
        else:
            adjustment = 0.0

        self._difficulty_adjustment += adjustment
        base = self.config.get("difficulty", 1.0)
        new_difficulty = max(0.1, base + self._difficulty_adjustment)

        return {
            "evaluation": {
                "skill_score": round(skill_score, 4),
                "level": level_name,
            },
            "adjustment": adjustment,
            "new_difficulty": round(new_difficulty, 4),
        }
