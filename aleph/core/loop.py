"""ステートマシン（PLAN §2.4）.

遷移図はここにデータとして定義されており、これが設計の正典である。
変更にはPLAN_CHANGELOGへの記録が必要（PLAN §12）。

- 機会的エッジ: DRAFT/CRITIQUE → EXPLORE/MATERIA（限定予算つき。PLAN §2.4）
- 完成 ≠ 公開: FINISH からは PUBLISH / SHELVE / DISCARD に分岐（PLAN §7.3d）
- REVISE は構成に遡る（→COMPOSE）か文面のみ（→DRAFT）かをL7が振り分ける（PLAN §7.2）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class State(str, Enum):
    SEEDED = "SEEDED"
    INTENT = "INTENT"
    EXPLORE = "EXPLORE"
    MATERIA = "MATERIA"
    COMPOSE = "COMPOSE"
    DRAFT = "DRAFT"
    CRITIQUE = "CRITIQUE"
    REVISE = "REVISE"
    FINISH = "FINISH"
    PUBLISH = "PUBLISH"
    SHELVE = "SHELVE"
    DISCARD = "DISCARD"


TERMINAL_STATES = frozenset({State.PUBLISH, State.SHELVE, State.DISCARD})

# 正典の遷移表。キー=現在状態、値=許される次状態。
ALLOWED_TRANSITIONS: dict[State, frozenset[State]] = {
    State.SEEDED: frozenset({State.INTENT}),
    State.INTENT: frozenset({State.EXPLORE}),
    State.EXPLORE: frozenset({State.MATERIA}),
    State.MATERIA: frozenset({State.COMPOSE}),
    State.COMPOSE: frozenset({State.DRAFT}),
    # 機会的エッジ（PLAN §2.4）: 執筆中の偶発的発見からの限定再入
    State.DRAFT: frozenset({State.CRITIQUE, State.EXPLORE, State.MATERIA}),
    State.CRITIQUE: frozenset({State.REVISE, State.FINISH, State.EXPLORE, State.MATERIA}),
    State.REVISE: frozenset({State.COMPOSE, State.DRAFT}),
    # 完成≠公開（PLAN §7.3d）
    State.FINISH: frozenset({State.PUBLISH, State.SHELVE, State.DISCARD}),
    State.PUBLISH: frozenset(),
    State.SHELVE: frozenset(),
    State.DISCARD: frozenset(),
}


def validate_transition(current: State, nxt: State) -> bool:
    return nxt in ALLOWED_TRANSITIONS[current]


@dataclass
class Checkpoint:
    """各遷移で書かれる再開点（PLAN §2.4）. works/<id>/checkpoint.json に永続化.

    施工: M0（受入テスト: tests/test_m0_acceptance.py::test_checkpoint_resume）
    """

    work_id: str
    state: State
    step: int
    payload: dict = field(default_factory=dict)

    def save(self, work_dir) -> None:
        raise NotImplementedError("M0: 施工対象")

    @classmethod
    def load(cls, work_dir) -> "Checkpoint":
        raise NotImplementedError("M0: 施工対象")


class Loop:
    """閉ループの実行器。遷移時に必ず: checkpoint保存 → decisions.jsonl 追記.

    ローカルモデルのswapコスト（PLAN §2.3）を考慮し、同一モデルで処理できる
    ステップを束ねてスケジュールする。

    施工: M0（骨格の実行）、M3以降（各状態の実処理を接続）
    """

    def __init__(self, work, router, budget, policies) -> None:
        self.work = work
        self.router = router
        self.budget = budget
        self.policies = policies

    def transition(self, nxt: State, reason: str, decided_by: str) -> None:
        raise NotImplementedError("M0: 施工対象")

    def run(self) -> State:
        raise NotImplementedError("M0: 施工対象")
