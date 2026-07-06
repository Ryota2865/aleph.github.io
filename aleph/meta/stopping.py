"""L7 擱筆判断（PLAN §7.3a）— 収束/完成宣言/過剰彫琢警報の3経路。予算切れで強制起動

施工: M5. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations


def should_stop(*args, **kwargs):
    raise NotImplementedError("M5: 施工対象")
