import random
from dataclasses import dataclass

# 难度惩罚值：越高越难
# DICE_ACTIONS 中的 difficulty 改为惩罚值，降低 target


@dataclass
class RollResult:
    raw: int
    target: int
    difficulty_penalty: int
    bonus: float
    success: bool
    degree: str


def roll(attribute_value: float, difficulty_penalty: int = 0, bonus: float = 0) -> RollResult:
    """
    Percentile roll-under system.
    target = attribute_value - difficulty_penalty + bonus, clamped to [5, 95]
    Roll 1-100, succeed if raw <= target.
    """
    target = int(attribute_value - difficulty_penalty + bonus)
    target = max(5, min(95, target))

    raw = random.randint(1, 100)

    # 大失败：天然 96-100 或超出 target 30+
    if raw >= 96:
        degree = "大失败"
        success = False
    # 大成功：天然 1-5 或低于 target/5
    elif raw <= max(5, target // 5):
        degree = "大成功"
        success = True
    elif raw <= target:
        degree = "成功"
        success = True
    elif raw <= target + 10:
        degree = "失败"
        success = False
    else:
        degree = "大失败"
        success = False

    return RollResult(
        raw=raw,
        target=target,
        difficulty_penalty=difficulty_penalty,
        bonus=bonus,
        success=success,
        degree=degree,
    )
