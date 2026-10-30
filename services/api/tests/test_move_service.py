"""招式学习者索引的纯函数测试（collect_learners）。"""

from __future__ import annotations

from app.services.move_service import collect_learners


def test_collect_learners_groups_by_move_and_version() -> None:
    payload = {
        "version_groups": {
            "scarlet-violet": {
                "methods": {
                    "level-up": [
                        {"name": "tackle", "level": 1},
                        {"name": "tackle", "level": 5},
                    ],
                    "machine": [{"name": "tackle", "level": 0}],
                }
            },
            "sword-shield": {
                "methods": {"machine": [{"name": "tackle", "level": 0}]},
            },
        }
    }

    learners = collect_learners(payload)

    assert list(learners) == ["tackle"]
    sv = learners["tackle"]["scarlet-violet"]
    # 同一学习方式只保留一条，等级取最小值（1）
    assert sv == [
        {"method": "level-up", "level": 1},
        {"method": "machine", "level": 0},
    ]
    # 不同版本组分别记录
    assert learners["tackle"]["sword-shield"] == [{"method": "machine", "level": 0}]


def test_collect_learners_handles_empty_payload() -> None:
    assert collect_learners({}) == {}
    assert collect_learners({"version_groups": None}) == {}
    assert collect_learners({"version_groups": {"scarlet-violet": {"methods": {}}}}) == {}
