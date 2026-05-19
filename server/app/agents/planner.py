from dataclasses import dataclass


@dataclass
class PlanAction:
    tick: int
    action: str
    target_id: str | None = None
    location: str | None = None
    priority: int = 5


# 地点名从 YAML huashan-mvp.yaml 的 locations 取
DAILY_TEMPLATES: dict[str, dict[int, dict]] = {
    "弟子型": {
        0: {"action": "睡觉", "location": "弟子精舍"},
        1: {"action": "睡觉", "location": "弟子精舍"},
        2: {"action": "睡觉", "location": "弟子精舍"},
        3: {"action": "早课", "location": "华山大殿"},
        4: {"action": "练功", "location": "练武场"},
        5: {"action": "午饭", "location": "食堂"},
        6: {"action": "自由活动"},
        7: {"action": "练功", "location": "练武场"},
        8: {"action": "晚饭", "location": "食堂"},
        9: {"action": "自由活动"},
        10: {"action": "休息", "location": "弟子精舍"},
        11: {"action": "睡觉", "location": "弟子精舍"},
    },
    "掌门型": {
        0: {"action": "睡觉", "location": "掌门卧房"},
        1: {"action": "睡觉", "location": "掌门卧房"},
        2: {"action": "睡觉", "location": "掌门卧房"},
        3: {"action": "早课", "location": "华山大殿"},
        4: {"action": "处理门务", "location": "华山大殿"},
        5: {"action": "午饭", "location": "食堂"},
        6: {"action": "授徒", "location": "练武场"},
        7: {"action": "修炼内功", "location": "掌门卧房"},
        8: {"action": "晚饭", "location": "食堂"},
        9: {"action": "与家人相处", "location": "掌门卧房"},
        10: {"action": "处理门务", "location": "华山大殿"},
        11: {"action": "睡觉", "location": "掌门卧房"},
    },
    "师娘型": {
        0: {"action": "睡觉", "location": "掌门卧房"},
        1: {"action": "睡觉", "location": "掌门卧房"},
        2: {"action": "睡觉", "location": "掌门卧房"},
        3: {"action": "早课", "location": "华山大殿"},
        4: {"action": "指导弟子", "location": "练武场"},
        5: {"action": "午饭", "location": "食堂"},
        6: {"action": "巡查弟子", "location": "练武场"},
        7: {"action": "修炼", "location": "华山大殿"},
        8: {"action": "晚饭", "location": "食堂"},
        9: {"action": "与家人相处", "location": "掌门卧房"},
        10: {"action": "休息", "location": "掌门卧房"},
        11: {"action": "睡觉", "location": "掌门卧房"},
    },
}


class Planner:
    # 自由活动 tick，可被情感偏好覆盖
    FREE_TICKS = {6, 9}

    def generate_plan(self, template: str, agent_name: str = "",
                      emotion_valence: float = 0.0) -> list[PlanAction]:
        tmpl = DAILY_TEMPLATES.get(template, DAILY_TEMPLATES["弟子型"])
        plan = []
        for tick, step in tmpl.items():
            action = step["action"]
            location = step.get("location")

            # 情感影响自由活动
            if tick in self.FREE_TICKS and action == "自由活动":
                if emotion_valence < -0.3:
                    action = "休息"
                    location = "弟子精舍"
                elif emotion_valence > 0.3:
                    action = "闲逛"
                    # 不改 location，留在原地更可能遇到人

            plan.append(PlanAction(
                tick=tick,
                action=action,
                location=location,
                priority=self._action_priority(action),
            ))
        return plan

    def revise_plan(
        self,
        plan: list[PlanAction],
        from_tick: int,
        new_action: str,
        location: str | None = None,
    ) -> list[PlanAction]:
        revised = []
        for action in plan:
            if action.tick == from_tick:
                revised.append(PlanAction(
                    tick=action.tick,
                    action=new_action,
                    location=location,
                    priority=action.priority,
                ))
            else:
                revised.append(action)
        return revised

    def get_action_for_tick(self, plan: list[PlanAction], tick: int) -> PlanAction | None:
        for action in plan:
            if action.tick == tick:
                return action
        return None

    def _action_priority(self, action: str) -> int:
        high = {"修炼", "修炼内功", "处理门务"}
        mid = {"练功", "练剑", "起床练剑", "授徒", "指导弟子", "早课"}
        if any(h in action for h in high):
            return 8
        if any(m in action for m in mid):
            return 6
        return 4
