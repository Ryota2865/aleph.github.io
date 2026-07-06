"""L2 空きニッチ探索（PLAN §4.3）— 疎領域+空きセル+Web照合。空きの三分類（不可能型/未着手型/空虚型）と深さの見立てを必須とする。ニッチはヒューリスティックであり価値関数ではない

施工: M1. 詳細はPLAN.mdの該当節を正典とする。
"""
from __future__ import annotations


def find_niches(*args, **kwargs):
    raise NotImplementedError("M1: 施工対象")

def classify_vacancy(*args, **kwargs):
    raise NotImplementedError("M1: 施工対象")

def report(*args, **kwargs):
    raise NotImplementedError("M1: 施工対象")
