"""L7 複数LLM介在判断（PLAN §7.3c）— 批評は常に複数、執筆は単独が既定。行き詰まり検知で第二モデル

施工: M5. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations


def decide_ensemble(*args, **kwargs):
    raise NotImplementedError("M5: 施工対象")
