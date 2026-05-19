from dataclasses import dataclass, field


# 骰子结果 → 情感变化映射
DICE_EMOTION_MAP: dict[str, tuple[float, float]] = {
    "大成功": (0.3, 0.3),
    "成功":  (0.1, 0.1),
    "失败":  (-0.1, 0.1),
    "大失败": (-0.4, 0.3),
}

# valence/arousal → 主导情绪
EMOTION_QUADRANTS = [
    (0.3,  0.5,  "开心"),
    (-0.3, 0.5,  "愤怒"),
    (-0.3, 0.0,  "悲伤"),
    (0.3,  0.0,  "平静"),
]


@dataclass
class EmotionalState:
    valence: float = 0.0           # [-1, 1] 负面 → 正面
    arousal: float = 0.0           # [0, 1]  平静 → 激动
    dominant_emotion: str = "平静"
    emotion_log: list[tuple[int, str, float]] = field(default_factory=list)

    def shift(self, event: str, valence_delta: float, arousal_delta: float = 0.0,
              tick: int = 0):
        self.valence = max(-1.0, min(1.0, self.valence + valence_delta))
        self.arousal = max(0.0, min(1.0, self.arousal + arousal_delta))
        if tick or valence_delta:
            self.emotion_log.append((tick, event, valence_delta))
        self.update_dominant()

    def decay(self, rate: float = 0.1):
        self.valence *= (1 - rate)
        self.arousal *= (1 - rate)

    def update_dominant(self):
        v, a = self.valence, self.arousal
        for threshold_v, threshold_a, label in EMOTION_QUADRANTS:
            if v >= threshold_v and a >= threshold_a:
                self.dominant_emotion = label
                return
        self.dominant_emotion = "平静"

    def apply_dice(self, degree: str, tick: int):
        if degree in DICE_EMOTION_MAP:
            vd, ad = DICE_EMOTION_MAP[degree]
            self.shift(f"骰子{degree}", vd, ad, tick)

    def bonus_for_dice(self) -> float:
        if self.valence > 0:
            return self.arousal * 5
        if self.valence < 0:
            return -abs(self.valence) * 3
        return 0.0
