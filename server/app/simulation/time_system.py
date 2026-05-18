SHICHEN_NAMES = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时",
                 "午时", "未时", "申时", "酉时", "戌时", "亥时"]

SHICHEN_PERIOD = {
    0: "深夜", 1: "深夜", 2: "凌晨",
    3: "清晨", 4: "上午", 5: "上午",
    6: "中午", 7: "下午", 8: "下午",
    9: "傍晚", 10: "夜间", 11: "深夜",
}


class TimeSystem:
    def __init__(self, current_tick: int = 0, current_day: int = 1):
        self.current_tick = current_tick
        self.current_day = current_day

    def advance(self) -> tuple[int, int]:
        self.current_tick += 1
        if self.current_tick >= 12:
            self.current_tick = 0
            self.current_day += 1
        return self.current_day, self.current_tick

    @property
    def time_of_day(self) -> str:
        return SHICHEN_NAMES[self.current_tick]

    @property
    def period(self) -> str:
        return SHICHEN_PERIOD[self.current_tick]

    def to_dict(self) -> dict:
        return {
            "tick": self.current_tick,
            "day": self.current_day,
            "time_of_day": self.time_of_day,
            "period": self.period,
        }
