"""
游戏内程序化关卡生成与难度曲线系统 - 核心模块

功能：
- generate_level():      程序化关卡生成（房间 + 连接）
- difficulty_curve():    难度曲线（整体递增 + 局部波动）
- level_design():        关卡设计（节奏 + 引导）
- player_experience():   玩家体验（心流 + 反馈）
- adaptive_difficulty(): 自适应难度（评估 + 调整）
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import random
import time


@dataclass
class Config:
    pass


# 房间类型 -> 节奏类别
_PACING_CATEGORY = {
    "entrance": "rest",
    "exit": "rest",
    "rest": "rest",
    "combat": "combat",
    "boss": "combat",
    "exploration": "exploration",
    "treasure": "exploration",
}


class LevelGenerator:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._state = {}
        self._history = []

    def update(self, dt: float):
        pass

    def reset(self):
        self._state = {}
        self._history = []

    # ------------------------------------------------------------------
    # 1. 程序化关卡生成：房间 + 连接
    # ------------------------------------------------------------------
    def generate_level(self, seed: Optional[int] = None,
                       num_rooms: int = 8) -> Dict:
        """生成一个带房间与连接的关卡。

        返回 {"seed", "rooms", "connections"}：
        - rooms: [{"id", "type", "x", "y"}]，必含 entrance 与 exit
        - connections: [(room_id_a, room_id_b)]，保证全图连通
        """
        if seed is None:
            seed = int(time.time() * 1000) % (2 ** 31)
        rng = random.Random(seed)
        num_rooms = max(4, int(num_rooms))

        pool = ["combat", "exploration", "treasure", "rest"]
        room_types = ["entrance"]
        while len(room_types) < num_rooms - 2:
            room_types.append(rng.choice(pool))
        room_types += ["boss", "exit"]
        # 打乱中间房间顺序，保持首尾为 entrance/exit
        middle = room_types[1:-1]
        rng.shuffle(middle)
        room_types = ["entrance"] + middle + ["exit"]

        rooms = []
        for i, rtype in enumerate(room_types):
            rooms.append({
                "id": i,
                "type": rtype,
                "x": rng.randint(0, 100),
                "y": rng.randint(0, 100),
            })

        # 主干链保证连通，再随机加额外通道
        connections = [(i, i + 1) for i in range(num_rooms - 1)]
        extra = rng.randint(1, max(1, num_rooms // 3))
        existing = {tuple(sorted(c)) for c in connections}
        for _ in range(extra):
            a, b = rng.sample(range(num_rooms), 2)
            key = (min(a, b), max(a, b))
            if key not in existing:
                existing.add(key)
                connections.append(key)

        level = {"seed": seed, "rooms": rooms, "connections": connections}
        self._history.append(("generate_level", seed))
        return level

    # ------------------------------------------------------------------
    # 2. 难度曲线：整体递增 + 局部波动
    # ------------------------------------------------------------------
    def difficulty_curve(self, num_levels: int, base: float = 0.15,
                         slope: float = 0.06,
                         amplitude: float = 0.08) -> List[float]:
        """返回 num_levels 个关卡的难度值（0~1）。

        整体随关卡递增（slope），叠加正弦波动（amplitude）调节奏。
        """
        num_levels = max(1, int(num_levels))
        curve = []
        for i in range(num_levels):
            trend = base + slope * i
            wave = amplitude * math.sin(i * math.pi / 2.0)
            value = min(1.0, max(0.0, trend + wave))
            curve.append(round(value, 4))
        return curve

    # ------------------------------------------------------------------
    # 3. 关卡设计：节奏 + 引导
    # ------------------------------------------------------------------
    def level_design(self, level: Dict) -> Dict:
        """根据生成的关卡给出设计方案。

        返回 {"pacing", "guidance"}：
        - pacing: [{"room_id", "category", "intensity"}] 节奏序列
        - guidance: {"critical_path", "hints"} 从入口到出口的引导
        """
        rooms = {r["id"]: r for r in level["rooms"]}
        connections = level["connections"]

        pacing = []
        for room in level["rooms"]:
            category = _PACING_CATEGORY.get(room["type"], "exploration")
            intensity = {"rest": 0.2, "exploration": 0.5,
                         "combat": 0.9}[category]
            pacing.append({"room_id": room["id"],
                           "category": category,
                           "intensity": intensity})

        # BFS 求入口到出口的关键路径作为引导
        adjacency = {rid: [] for rid in rooms}
        for a, b in connections:
            adjacency[a].append(b)
            adjacency[b].append(a)
        start = next(r["id"] for r in level["rooms"] if r["type"] == "entrance")
        goal = next(r["id"] for r in level["rooms"] if r["type"] == "exit")
        prev = {start: None}
        queue = [start]
        while queue:
            cur = queue.pop(0)
            if cur == goal:
                break
            for nxt in adjacency[cur]:
                if nxt not in prev:
                    prev[nxt] = cur
                    queue.append(nxt)
        path = []
        node = goal
        while node is not None:
            path.append(node)
            node = prev.get(node)
        path.reverse()

        hints = []
        for rid in path:
            rtype = rooms[rid]["type"]
            if rtype == "combat":
                hints.append("前方有战斗，做好准备")
            elif rtype == "treasure":
                hints.append("附近有宝藏，值得探索")
            elif rtype == "boss":
                hints.append("Boss 在前方，建议先补给")
            elif rtype == "exit":
                hints.append("出口就在前方")

        return {"pacing": pacing,
                "guidance": {"critical_path": path, "hints": hints}}

    # ------------------------------------------------------------------
    # 4. 玩家体验：心流 + 反馈
    # ------------------------------------------------------------------
    def player_experience(self, skill: float, challenge: float) -> Dict:
        """根据玩家能力与关卡挑战评估体验。

        返回 {"flow_state", "flow_score", "feedback"}：
        - flow_state: "bored" / "flow" / "anxious"
        - feedback: 改进建议列表
        """
        skill = min(1.0, max(0.0, float(skill)))
        challenge = min(1.0, max(0.0, float(challenge)))
        gap = challenge - skill

        if gap > 0.15:
            state = "anxious"
        elif gap < -0.15:
            state = "bored"
        else:
            state = "flow"
        flow_score = round(1.0 - min(1.0, abs(gap) / 0.5), 4)

        feedback = []
        if state == "anxious":
            feedback.append("挑战高于玩家能力，建议降低难度或增加引导")
        elif state == "bored":
            feedback.append("挑战低于玩家能力，建议提高难度或增加新机制")
        else:
            feedback.append("挑战与能力匹配，玩家处于心流状态")
        if challenge > 0.8:
            feedback.append("高难度区域前后应安排休息点调节奏")

        return {"flow_state": state, "flow_score": flow_score,
                "feedback": feedback}

    # ------------------------------------------------------------------
    # 5. 自适应难度：评估 + 调整
    # ------------------------------------------------------------------
    def adaptive_difficulty(self, performance: Dict,
                            current_difficulty: float = 0.5) -> Dict:
        """根据玩家表现评估水平并调整难度。

        performance: {"deaths", "completion_time", "expected_time",
                      "hit_rate"}（均可选）
        返回 {"skill", "evaluation", "adjusted_difficulty"}。
        """
        deaths = float(performance.get("deaths", 0))
        completion = float(performance.get("completion_time", 0))
        expected = float(performance.get("expected_time", 0))
        hit_rate = float(performance.get("hit_rate", 0.5))

        skill = 1.0 / (1.0 + deaths)
        if expected > 0 and completion > 0:
            time_score = min(1.0, expected / completion)
            skill = 0.5 * skill + 0.3 * time_score + 0.2 * hit_rate
        else:
            skill = 0.7 * skill + 0.3 * hit_rate
        skill = min(1.0, max(0.0, skill))

        if skill < 0.4:
            evaluation = "struggling"
        elif skill > 0.7:
            evaluation = "dominating"
        else:
            evaluation = "balanced"

        current = min(1.0, max(0.0, float(current_difficulty)))
        adjusted = current + 0.5 * (skill - 0.5)
        adjusted = min(1.0, max(0.0, adjusted))

        result = {"skill": round(skill, 4),
                  "evaluation": evaluation,
                  "adjusted_difficulty": round(adjusted, 4)}
        self._history.append(("adaptive_difficulty", result["evaluation"]))
        return result
