"""ステートマシン（PLAN §2.4）.

遷移図はここにデータとして定義されており、これが設計の正典である。
変更にはPLAN_CHANGELOGへの記録が必要（PLAN §12）。

- 機会的エッジ: DRAFT/CRITIQUE → EXPLORE/MATERIA（限定予算つき。PLAN §2.4）
- 完成 ≠ 公開: FINISH からは PUBLISH / SHELVE / DISCARD に分岐（PLAN §7.3d）
- REVISE は構成に遡る（→COMPOSE）か文面のみ（→DRAFT）かをL7が振り分ける（PLAN §7.2）
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable


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
        """checkpoint.json を一時ファイル+renameで原子的に書く（PLAN_CHANGELOG 0.7.18
        問1、sol §3.3: 書き込み途中のプロセス終了で不完全なJSONが残ることを防ぐ）."""
        work_dir = Path(work_dir)
        path = work_dir / "checkpoint.json"
        payload = {
            "work_id": self.work_id,
            "state": self.state.value,
            "step": self.step,
            "payload": self.payload,
        }
        tmp_path = work_dir / f".checkpoint.json.{os.getpid()}.tmp"
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)

    @classmethod
    def load(cls, work_dir) -> "Checkpoint":
        path = Path(work_dir) / "checkpoint.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            work_id=data["work_id"],
            state=State(data["state"]),
            step=data["step"],
            payload=data.get("payload", {}),
        )


def replay_checkpoint(work_id: str, decisions_path) -> Checkpoint:
    """decisions.jsonl の L0 記録だけから checkpoint と等価な状態を再構成する.

    PLAN_CHANGELOG 0.7.18 問1（Fable5設計者審査）: 「decisions.jsonl が正、
    checkpoint.json はそこから再構築可能な投影である」という位置づけを、
    `Checkpoint.load(work.dir) == replay_checkpoint(work.work_id, work.decisions)`
    という契約テストで実際に保証するための関数。各L0記録の"payload"（そのステップで
    新規に追加された差分のみ。pipeline._transition が書く）を順に合成し、最後の
    遷移先を現在状態、L0記録数をstepとする。旧い作品（0.7.18以前に完了・payload
    未記録）を再生すると、payloadが空のCheckpointになる——これは既知の限界であり、
    偽装しない（該当作品は既に終端済みでreplayを必要としない）。
    """
    path = Path(decisions_path)
    state = State.SEEDED
    step = 0
    payload: dict = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("layer") != "L0":
                continue
            step += 1
            decision = str(record.get("decision", ""))
            if "->" in decision:
                _, _, nxt_name = decision.partition("->")
                state = State(nxt_name)
            record_payload = record.get("payload")
            if record_payload:
                payload.update(record_payload)
    return Checkpoint(work_id=work_id, state=state, step=step, payload=payload)


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
        # 状態ごとの実処理。接続はM3以降（各L2〜L8層の施工時）。未登録の状態に
        # 到達したら run() はそこで停止する（クラッシュではなく正常な一時停止）。
        self.handlers: dict[State, Callable[["Loop"], State]] = {}
        # 既存checkpointがあれば再開後もstepを単調増加させる（クラッシュ再開時の
        # 監査ログ順序保全。Codex監査 finding 3）。新規作品では0から開始する。
        self._step = self._load_last_step()

    def _load_last_step(self) -> int:
        try:
            return Checkpoint.load(self.work.dir).step
        except FileNotFoundError:
            return 0

    def current_state(self) -> State:
        try:
            return Checkpoint.load(self.work.dir).state
        except FileNotFoundError:
            return State.SEEDED

    def transition(self, nxt: State, reason: str, decided_by: str) -> None:
        current = self.current_state()
        if not validate_transition(current, nxt):
            raise ValueError(f"invalid transition: {current} -> {nxt}")
        self._step += 1
        Checkpoint(work_id=self.work.work_id, state=nxt, step=self._step, payload={}).save(self.work.dir)
        self.work.append_decision(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "layer": "L0",
                "decision": f"{current.value}->{nxt.value}",
                "reason": reason,
                "decided_by": decided_by,
            }
        )

    def run(self) -> State:
        state = self.current_state()
        while state not in TERMINAL_STATES:
            handler = self.handlers.get(state)
            if handler is None:
                break
            state = handler(self)
        return state
