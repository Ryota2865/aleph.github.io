"""閉ループ配線（PLAN §2.4・§10 M6）— SEEDED→…→終端 を現在のチェックポイントから進める.

正典遷移表（core/loop.py）は変更しない。各遷移でチェックポイント保存 +
decisions.jsonl (layer L0) 記録を行う。compose_and_draft が L4+L5 を担うため
COMPOSE→DRAFT→CRITIQUE と段階的に遷移する。クラッシュ後はチェックポイントの
状態から再開し、完了済み状態の処理を再実行しない（中間値は checkpoint.payload で
持ち回す）。

`run_work` は依存(deps)を注入してテスト可能。`RealDeps` は実LLM依存の配線
（CLI `aleph run` から利用）。テスト対象外。遅延importで書く。
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from aleph.core.loop import Checkpoint, State
from aleph.core.transition_commit import commit as commit_transition
from aleph.core.transition_commit import recover as recover_transition


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _llm_is_primary_audience(audience: str) -> bool:
    """宛先配合で「LLM」が最大の係数かを判定する（§5.4 AI固有技法の適用条件）."""
    import re

    weights: dict[str, float] = {}
    for label, value in re.findall(r"([^/\n,、]+?)\s*[=:：]?\s*([0-9]+(?:\.[0-9]+)?)", audience or ""):
        try:
            weights[label.strip()] = float(value)
        except ValueError:
            continue
    if not weights:
        return False
    llm_weights = [v for k, v in weights.items() if "LLM" in k]
    if not llm_weights:
        return False
    llm_max = max(llm_weights)
    others = [v for k, v in weights.items() if "LLM" not in k]
    return not others or llm_max >= max(others)


# ---------------------------------------------------------------- 遷移ヘルパ
def _transition(work, current: State, nxt: State, reason: str, decided_by: str,
                *, step: int, ctx: dict, payload: dict | None = None) -> Checkpoint:
    """Pipeline adapter for the authoritative TransitionCommit interface."""
    result = commit_transition(
        work,
        command_id=f"{work.work_id}:transition:{step + 1}:{current.value}:{nxt.value}",
        expected_state=current,
        next_state=nxt,
        reason=reason,
        decided_by=decided_by,
        payload_delta=payload,
    )
    ctx.clear()
    ctx.update(result.checkpoint.payload)
    return result.checkpoint


# ---------------------------------------------------------------- final 化
def _default_credits() -> dict:
    """モデル実値が不明なときの役割名による名義（PLAN §8: 関与モデルの役割つき列記）."""
    return {
        "著": "author_primary",
        "構成": "author_primary",
        "査読": "critic_jury",
        "探索": "scout",
    }


def _title_path(work):
    return work.dir / "title.txt"


def _stored_title(work) -> str | None:
    """作品自身が完成時に選んだ題（title.txt）。無ければ None."""
    path = _title_path(work)
    if path.exists():
        title = path.read_text(encoding="utf-8").strip()
        if title:
            return title
    return None


def _derive_title(work) -> str:
    # 作品自身が選んだ題を最優先（RealDeps.choose_title が FINISH で書く。フロー化, 0.7.14）。
    stored = _stored_title(work)
    if stored:
        return stored
    seed_path = work.seed
    try:
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        for key in ("title", "hint", "seed"):
            value = seed.get(key)
            if value:
                return str(value)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return work.work_id


def _best_reviewed_draft_version(work) -> int | None:
    traj_path = work.dir / "reviews" / "trajectory.jsonl"
    if not traj_path.exists():
        return None
    best_version: int | None = None
    best_score: float | None = None
    try:
        for line in traj_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            version = int(row["version"])
            score = float(row["mean_score"])
            if score != score:
                return None
            if best_score is None or score > best_score:
                best_score = score
                best_version = version
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    return best_version


def _atomic_write_text(path: Path, text: str) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _finalize_publish(work, deps) -> None:
    """PUBLISH確定時: 採用draftを final/text.md へ、final/meta.json へ必須フィールドを書く（PLAN §8）.

    credits の実値は deps.credits があればそれを、無ければ役割名を使う。
    intended_reader_models も deps.intended_reader_models があればそれを使う。
    """
    latest = work.latest_draft_version()
    selected = _best_reviewed_draft_version(work)
    if selected is None or not work.draft_path(selected).exists():
        selected = latest
    text = ""
    if selected > 0 and work.draft_path(selected).exists():
        text = work.draft_path(selected).read_text(encoding="utf-8")
    work.final.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(work.final / "text.md", text)

    credits = getattr(deps, "credits", None) or _default_credits()
    intended = getattr(deps, "intended_reader_models", None) or []
    meta = {
        "title": _derive_title(work),
        "credits": credits,
        "license": "CC0-1.0",
        "published_at": _now_iso(),
        "intended_reader_models": list(intended),
        "provenance": [],
    }
    _atomic_write_text(
        work.final / "meta.json",
        json.dumps(meta, ensure_ascii=False, indent=2),
    )


def _publish_artifacts_complete(work) -> bool:
    if not (work.final / "text.md").is_file():
        return False
    try:
        meta = json.loads((work.final / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    required = {"title", "credits", "license", "published_at", "intended_reader_models"}
    return isinstance(meta, dict) and required.issubset(meta)


def _ensure_publish_artifacts(work, deps) -> None:
    """Materialize a committed publication, retrying only incomplete final output."""
    if _publish_artifacts_complete(work):
        return
    _finalize_publish(work, deps)


def _terminal_reflection_state(work) -> str:
    """Return complete, started, or missing for this work's terminal reflection."""
    try:
        rows = [
            json.loads(line)
            for line in work.decisions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        return "missing"
    terminal_rows = [row for row in rows if row.get("layer") == "L8"]
    completed = {
        "詩学改訂を適用",
        "詩学改訂は反駁され不適用",
        "詩学リフレクション結果なし",
    }
    if any(row.get("decision") in completed for row in terminal_rows):
        return "complete"
    if any(row.get("decision") == "詩学リフレクション開始" for row in terminal_rows):
        return "started"
    return "missing"


def _ensure_terminal_effects(work, deps, decided_by: str) -> None:
    """Complete recoverable terminal effects without repeating charged reflection."""
    from aleph.publish.status import is_published

    if is_published(work.dir):
        _ensure_publish_artifacts(work, deps)
    _reflect_poetics_if_available(work, deps, decided_by)


# ---------------------------------------------------------------- run_work
def run_work(work, deps, *, decided_by: str) -> State:
    """現在のチェックポイント状態から正典遷移表に従い閉ループを進め、終端 State を返す.

    deps は choose_intent/explore/gather_materials/compose_and_draft/
    critique_and_revise/decide_stop/decide_publication を持つ。
    compose_and_draft が L4+L5 を担うため COMPOSE→DRAFT と段階的に遷移する。
    再開時は完了済み状態の処理を再実行しない（中間値は checkpoint.payload で復元）。
    """
    cp = recover_transition(work)
    state = cp.state
    step = cp.step
    ctx: dict = dict(cp.payload)

    if state in (State.PUBLISH, State.SHELVE, State.DISCARD):
        _ensure_terminal_effects(work, deps, decided_by)
        return state

    def go(nxt: State, reason: str, payload: dict | None = None) -> None:
        nonlocal step, state
        projected = _transition(
            work, state, nxt, reason, decided_by, step=step, ctx=ctx, payload=payload
        )
        step = projected.step
        state = projected.state

    # --- SEEDED → INTENT（種から志向選択へ。SEEDEDの処理は Work.create 済み）
    if state == State.SEEDED:
        go(State.INTENT, "種から志向選択(L1)へ")

    # --- INTENT → EXPLORE
    if state == State.INTENT:
        audience = deps.choose_intent(work)
        go(State.EXPLORE, "志向選択完了、探索(L2)へ", payload={"audience": audience})

    # --- EXPLORE → MATERIA
    if state == State.EXPLORE:
        niche = deps.explore(work)
        go(State.MATERIA, "探索完了、素材錬成(L3)へ", payload={"niche": niche})

    # --- MATERIA → COMPOSE
    if state == State.MATERIA:
        niche = ctx.get("niche")
        materials = deps.gather_materials(work, niche)
        go(State.COMPOSE, "素材錬成完了、構成(L4)へ", payload={"materials": materials})

    # --- COMPOSE → DRAFT（compose_and_draft が L4+L5 を担う）
    if state == State.COMPOSE:
        niche = ctx.get("niche")
        audience = ctx.get("audience")
        materials = ctx.get("materials")
        deps.compose_and_draft(work, niche, audience, materials)
        go(State.DRAFT, "構成・執筆(L4+L5)完了")

    # --- DRAFT → CRITIQUE（執筆は compose_and_draft 済み。査読へ）
    if state == State.DRAFT:
        go(State.CRITIQUE, "執筆完了、査読・改稿(L6)へ")

    # --- CRITIQUE → FINISH（擱筆判断。stop=False のときは限定で再査読）
    if state == State.CRITIQUE:
        audience = ctx.get("audience")
        guard = 0
        # クラッシュ再開時: 査読軌跡が既に2ラウンド分あれば、まず擱筆判定から入る
        # （查読・改稿の重複実行はAPI実費と時間の再支出になる。w0001実ランの回帰）
        rows_at_entry, _ = _stop_inputs_from_trajectory(work)
        skip_first_critique = len(rows_at_entry) >= 1
        while True:
            if not skip_first_critique:
                deps.critique_and_revise(work, audience)
            skip_first_critique = False
            stop = deps.decide_stop(work)
            if stop.get("stop"):
                go(
                    State.FINISH,
                    f"擱筆({stop.get('path', '')}): {stop.get('reason', '')}",
                    payload={"stop_path": stop.get("path")},
                )
                break
            guard += 1
            if guard >= 5:  # 無限ループ防止（REVISE経路の予算外の安全網）
                go(State.FINISH, "改稿上限に到達、擱筆", payload={"stop_path": "guard_limit"})
                break

    # --- FINISH → PUBLISH | SHELVE | DISCARD（完成≠公開, PLAN §7.3d）
    if state == State.FINISH:
        audience = ctx.get("audience")
        pub = deps.decide_publication(work, audience)
        decision = str(pub.get("decision", "SHELVE")).upper()
        reason = pub.get("reason", "")
        if decision == "PUBLISH":
            go(State.PUBLISH, f"公開ゲート承認: {reason}")
        elif decision == "DISCARD":
            _record_termination_failure(work, deps, ctx, reason, decided_by)
            go(State.DISCARD, f"廃棄: {reason}")
        else:
            _record_termination_failure(work, deps, ctx, reason, decided_by)
            go(State.SHELVE, f"棚上げ: {reason}")
        _ensure_terminal_effects(work, deps, decided_by)

    return state


def _classify_termination(stop_path: str | None, reason: str) -> str:
    """SHELVE/DISCARDの理由をsol提案の4分類へ落とす（PLAN_CHANGELOG 0.7.18 問2）.

    aesthetic_failureのみ否定的地図（annotate_failure）へ渡す。resource_stop・
    publication_choiceは探索座標を罰しない（sol提案の趣旨）。safety_or_rightsは
    現状これを自動生成する経路が存在しない（将来の手動介入用に予約）。
    """
    if stop_path in ("budget", "guard_limit"):
        return "resource_stop"
    if "上限" in reason or "人間承認待ち" in reason:
        return "resource_stop"
    if "著者が非公開を選択した" in reason:
        return "publication_choice"
    return "aesthetic_failure"


def _record_termination_failure(work, deps, ctx: dict, reason: str, decided_by: str) -> None:
    """SHELVE/DISCARD時、理由を4分類のいずれかとしてdecisions.jsonlへ記録し、
    aesthetic_failureのみ否定的地図（deps.annotate_failure）へ渡す
    （PLAN_CHANGELOG 0.7.18 問2。annotate_failure未対応のdepsでは記録のみ行い、地図は更新しない）。
    """
    category = _classify_termination(ctx.get("stop_path"), reason)
    work.append_decision({
        "ts": _now_iso(),
        "layer": "L7",
        "decision": f"failure_category:{category}",
        "reason": reason,
        "decided_by": decided_by,
    })
    if category != "aesthetic_failure":
        return
    annotate_failure = getattr(deps, "annotate_failure", None)
    if annotate_failure is None:
        return
    niche_desc = str((ctx.get("niche") or {}).get("description", ""))
    try:
        annotate_failure(work, niche_desc, reason)
    except Exception as exc:  # 否定的地図の更新失敗で作品終端そのものは止めない
        print(f"annotate_failure failed for {work.work_id}: {exc}", file=sys.stderr)


def _reflect_poetics_if_available(work, deps, decided_by: str) -> None:
    """終端（PUBLISH/SHELVE/DISCARDいずれも）後、詩学の自己改訂を検討する（PLAN §7.4）.

    deps.reflect_poetics未対応（例: M6契約のFakeDeps）では何もしない。
    """
    reflect_poetics = getattr(deps, "reflect_poetics", None)
    if reflect_poetics is None:
        return
    reflection_state = _terminal_reflection_state(work)
    if reflection_state == "complete":
        return
    if reflection_state == "started":
        print(
            f"poetics reflection for {work.work_id} has an incomplete start record; "
            "refusing automatic retry",
            file=sys.stderr,
        )
        return
    work.append_decision({
        "ts": _now_iso(),
        "layer": "L8",
        "decision": "詩学リフレクション開始",
        "reason": "終端後フック開始。完了記録なしの自動再課金を禁止する。",
        "decided_by": decided_by,
    })
    try:
        result = reflect_poetics(work)
    except Exception as exc:  # 詩学リフレクションの失敗で作品終端そのものは止めない
        print(f"poetics reflection failed for {work.work_id}: {exc}", file=sys.stderr)
        return
    if not result:
        result = {"applied": False, "diff_reason": "リフレクション結果なし"}
    work.append_decision({
        "ts": _now_iso(),
        "layer": "L8",
        "decision": "詩学改訂を適用" if result.get("applied") else "詩学改訂は反駁され不適用",
        "reason": str(result.get("diff_reason", "")),
        "decided_by": decided_by,
    })


def _remaining_api_budget(budget, work_id: str) -> float | None:
    """作品別上限と月上限のうち、小さい方の残額。どちらも未宣言なら None.

    擱筆判断の予算経路は両方の防壁を見る必要がある(w0002実ランで作品残額だけを見て
    続行し、月上限precheckでクラッシュする経路が観測された)。
    """
    candidates = []
    work_rem = budget.work_remaining(work_id)
    if work_rem is not None:
        candidates.append(work_rem)
    api = budget.status().get("api")
    if api and api.get("limit") is not None:
        candidates.append(float(api["limit"]) - float(api["spent"]))
    return min(candidates) if candidates else None


# 陪審不一致が高い草稿 = 著者が本当に迷いうる自然な境界作品（チャットFable5提案 2026-07-13:
# 境界の定義を人間の目分量からシステム自身の計測へ）。閾を越えた版を実験E-border の刺激として
# 予約キューに記録する。観測済みの合意的作品は 0.43-0.52 程度（陪審3・0-10スケール）。
_E_BORDER_DISAGREEMENT_THRESHOLD = 0.8


def reserve_border_candidates(work, *, threshold: float = _E_BORDER_DISAGREEMENT_THRESHOLD,
                              queue_path: Path | None = None) -> list[dict]:
    """trajectory の不一致度が閾を越えた版を state/e_border_queue.jsonl に予約する（冪等）."""
    rows, _ = _stop_inputs_from_trajectory(work)
    hits = [r for r in rows if float(r.get("disagreement", 0.0)) >= threshold]
    if not hits:
        return []
    queue = queue_path or (work.dir.parent.parent / "state" / "e_border_queue.jsonl")
    queue.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if queue.exists():
        for line in queue.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                existing.add((rec.get("work_id"), rec.get("version")))
    reserved = []
    with open(queue, "a", encoding="utf-8") as f:
        for r in hits:
            key = (work.work_id, int(r.get("version", 0)))
            if key in existing:
                continue
            rec = {
                "ts": _now_iso(), "work_id": work.work_id, "version": int(r.get("version", 0)),
                "mean_score": float(r.get("mean_score", 0.0)),
                "disagreement": float(r.get("disagreement", 0.0)),
                "reason": "陪審不一致が閾を超過。実験E-border の自然な境界刺激として予約",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            reserved.append(rec)
    return reserved


def _stop_inputs_from_trajectory(work) -> tuple[list[dict], list[list[str]]]:
    traj_path = work.dir / "reviews" / "trajectory.jsonl"
    rows: list[dict] = []
    if traj_path.exists():
        for line in traj_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    instructions_history = [row["instructions"] for row in rows if "instructions" in row]
    return rows, instructions_history


# ================================================================= RealDeps
# 実LLM依存の配線。テスト対象外（m6テストは FakeDeps で配線のみ検査）。
# import時エラーにならないよう、重い依存は遅延importで書く（PLAN_CHANGELOG 0.7.8）。
class RealDeps:
    """実LLM依存の各層。CLI `aleph run` が組み立てる.

    役割呼び出しは Router 経由。author=Router.call("author_primary"),
    scout=Router.call("scout"), jury=critic_jury 個別呼び。work_id を
    Router 呼び出しの overrides で渡し作品別予算(usd_per_work)を効かせる。
    """

    def __init__(self, work, router, *, config, index_dir: str | Path,
                 search_fn, embedder=None, force_audience: str | None = None,
                 poetics_dir: str | Path = "poetics") -> None:
        self.work = work
        self.router = router
        self.config = config
        self.index_dir = Path(index_dir)
        self.poetics_dir = Path(poetics_dir)
        self.search_fn = search_fn
        self.embedder = embedder
        self.force_audience = force_audience  # 実験: L1自律選択を上書き（0.7.14）
        self._work_id = work.work_id
        self._phase = "L0"
        self._experiment_id: str | None = None
        self._experiment_arm = "main"
        try:
            seed = json.loads(work.seed.read_text(encoding="utf-8"))
            experiment = seed.get("experiment") if isinstance(seed, dict) else None
            if isinstance(experiment, dict) and experiment.get("id"):
                self._experiment_id = str(experiment["id"])
                self._experiment_arm = str(seed.get("arm") or "main")
                ablation = seed.get("material_ablation", {})
                cap = experiment.get("budget_cap_usd", ablation.get("budget_cap_usd"))
                if type(cap) in (int, float) and float(cap) > 0:
                    router.budget.register_scope_limit(
                        f"experiment:{self._experiment_id}", ledger="api", limit=float(cap)
                    )
        except (AttributeError, OSError, json.JSONDecodeError):
            pass
        # credits / intended_reader_models は publish時の meta.json に反映
        self.credits: dict = {}
        self.intended_reader_models: list[str] = []

    # -- 終端後フック（PLAN_CHANGELOG 0.7.18: 作成済み・未接続だった機能の実配線） -----
    def annotate_failure(self, work, niche_desc: str, reason: str) -> None:
        """SHELVE/DISCARD時、aesthetic_failure分類の座標を否定的地図へ記録する（PLAN §4.3）."""
        from aleph.explore.atlas import annotate_failure as _annotate_failure

        _annotate_failure(self.index_dir, work_id=self._work_id, niche_desc=niche_desc, reason=reason)

    def _cadence_state_path(self) -> Path:
        return self.poetics_dir / "cadence_state.json"

    def _read_cadence_count(self) -> int:
        try:
            data = json.loads(self._cadence_state_path().read_text(encoding="utf-8"))
            return int(data.get("works_since_reflection", 0))
        except (FileNotFoundError, ValueError, TypeError):
            return 0

    def _write_cadence_count(self, count: int) -> None:
        self.poetics_dir.mkdir(parents=True, exist_ok=True)
        self._cadence_state_path().write_text(
            json.dumps({"works_since_reflection": count}, ensure_ascii=False), encoding="utf-8",
        )

    def reflect_poetics(self, work, *, ignore_cadence: bool = False) -> dict:
        """終端後、詩学の自己改訂を検討するかどうかを判定する（PLAN §7.4）.

        PLAN_CHANGELOG 0.7.18-1（Fable5審査 問7）が指摘した非対称性を実装する:
        導く腕（詩学の注入）は毎作行うが、疑う腕（改訂の検討）は
        `policies.poetics.revision_cadence_works` 作ごとに間引く（既定3。「導く腕は毎作、
        疑う腕はN作ごと」）。加えて、詩学がまだ第0版（一度も改訂されていない）の場合、
        `policies.poetics.first_revision_requires_human_ack` が真になるまで実際の改訂は
        見送る——reflect()の出力はself_definitionと同じ設置力を持つ「設計変更」であり、
        承認とは別種の扱いを要する、という指摘への対応（first_publish_ackと同型のゲート）。
        いずれの場合も見送った理由をdictで返し、pipeline側がdecisions.jsonlへ記録する。
        """
        from aleph.meta.poetics import current_version, reflect

        policies = (self._policies().get("poetics") or {})
        cadence = max(1, int(policies.get("revision_cadence_works", 1)))
        count = self._read_cadence_count() + 1

        # ignore_cadence: w0008 完成時のオーナー明示引き継ぎ（0.7.19-2/-13）のように、
        # 周期カウントが「ackゲート閉鎖時の見送り」で消費済みの場合の一回性の実行口。
        # 呼び出し側（scripts/reflect_poetics_v1.py）が理由を decisions.jsonl に記録する。
        if not ignore_cadence and count < cadence:
            self._write_cadence_count(count)
            return {
                "applied": False,
                "diff_reason": f"改訂周期のため見送り（{count}/{cadence}作）。",
            }

        version_before = current_version(self.poetics_dir)
        if version_before == 0 and not policies.get("first_revision_requires_human_ack", False):
            self._write_cadence_count(0)
            return {
                "applied": False,
                "diff_reason": (
                    "初回改訂は人間承認待ち"
                    "（policies.poetics.first_revision_requires_human_ack=false）。"
                ),
            }

        # 0.7.19-2: 第0版→第1版の初回改訂に限り、2024年の宣言を入力文書として与える
        # （恒久注入ではない。第1版以降は version_before > 0 となり自然に一度きりになる）。
        extra_inputs = None
        if version_before == 0:
            declaration = self.poetics_dir.parent / "DECLARATION_2024.md"
            if declaration.exists():
                extra_inputs = {
                    "2024年の宣言（DECLARATION_2024.md、PLAN_CHANGELOG 0.7.19-2 の登録入力）":
                        declaration.read_text(encoding="utf-8"),
                }

        result = reflect(self.poetics_dir, work, self._author, self._reader, extra_inputs=extra_inputs)
        self._write_cadence_count(0)
        if extra_inputs:
            result["extra_inputs"] = sorted(extra_inputs)
            result["diff_reason"] = (
                str(result.get("diff_reason", ""))
                + "（初回改訂につき 2024年の宣言を入力に含めた: 0.7.19-2）"
            )
        return result

    # -- 役割呼び出しヘルパ（work_id で作品別予算を効かせる） -----------------
    def _call_overrides(self) -> dict:
        values = {"work_id": self._work_id}
        if self._experiment_id is not None:
            from aleph.core.llm import CallContext

            values = {
                "call_context": CallContext(
                    command_id=f"{self._experiment_id}:{self._phase}:{uuid.uuid4()}",
                    work_id=self._work_id,
                    experiment_id=self._experiment_id,
                    phase=self._phase,
                    arm=self._experiment_arm,
                    charged_to=f"experiment:{self._experiment_id}",
                )
            }
        return values

    def _author(self, prompt: str) -> str:
        from aleph.core.llm import Message

        return self.router.call(
            "author_primary", [Message("user", prompt)], **self._call_overrides(),
        ).text

    def _scout(self, prompt: str) -> str:
        from aleph.core.llm import Message

        return self.router.call(
            "scout", [Message("user", prompt)], **self._call_overrides(),
        ).text

    def _reader(self, prompt: str) -> str:
        from aleph.core.llm import Message

        return self.router.call(
            "reader_model", [Message("user", prompt)], **self._call_overrides(),
        ).text

    def _reader_llm(self, messages, **overrides):
        """完全な LLMResponse を返す reader 呼び出し（anti_cliche が logprobs を読むため）."""
        return self.router.call("reader_model", messages, **self._call_overrides(), **overrides)

    def _audience_hint(self, work) -> str:
        """現在の宛先配合を得る（checkpoint.payload 優先、無ければ force_audience）."""
        try:
            cp = Checkpoint.load(work.dir)
            audience = cp.payload.get("audience")
            if audience:
                return str(audience)
        except FileNotFoundError:
            pass
        return self.force_audience or ""

    # -- 題の自己選択（完成時に作品自身＝著者へ聞く。フロー化, 0.7.14） -----------
    def choose_title(self, work, text: str) -> str:
        """作品本文から著者に題を1つ選ばせる。失敗時は空文字（呼び出し側でフォールバック）."""
        from aleph.core.llm import Message
        from aleph.core.model_output import parse_model_output

        excerpt = text if len(text) <= 16000 else text[:12000] + "\n……\n" + text[-4000:]
        prompt = (
            "あなたはこの作品の著者です。この作品自身がまとうにふさわしい題を一つだけ選んでください。"
            "内容を説明する題ではなく、作品の核に触れる、簡潔で喚起力のある題を。"
            'JSON {"title": "…", "reason": "…"} だけを返してください。\n\n' + excerpt
        )
        try:
            resp = self.router.call(
                "author_primary", [Message("user", prompt)], **self._call_overrides(), max_tokens=2048,
            )
            parsed = parse_model_output(resp.text, schema=dict).value or {}
            title = str(parsed.get("title") or "").strip()
            if title:
                work.append_decision({
                    "ts": _now_iso(),
                    "layer": "L8",
                    "decision": f"題を確定: {title}",
                    "reason": f"作品自身（著者）が完成時に選題。{str(parsed.get('reason') or '').strip()}",
                    "decided_by": "author_primary",
                })
                return title
        except Exception as exc:  # noqa: BLE001 - 題選択失敗はフォールバックに委ねる
            print(f"choose_title: skipped ({type(exc).__name__})", file=sys.stderr)
        return ""

    def _ensure_title(self, work) -> None:
        """FINISH で一度だけ、作品自身に題を聞いて title.txt に保存する（冪等）."""
        title_path = _title_path(work)
        if title_path.exists() and title_path.read_text(encoding="utf-8").strip():
            return
        best = _best_reviewed_draft_version(work) or work.latest_draft_version()
        if not best or not work.draft_path(best).exists():
            return
        text = work.draft_path(best).read_text(encoding="utf-8")
        if not text.strip():
            return
        title = self.choose_title(work, text)
        if title:
            title_path.write_text(title, encoding="utf-8")

    def _jury(self):
        """critic_jury を構成する各員の呼び出し可能オブジェクトのリスト（個別呼び, §7.1）."""
        from aleph.core.llm import Message

        decls = self.router._role_decls("critic_jury")  # リスト宣言（陪審）
        callables = []
        for idx in range(len(decls)):

            def juror(prompt: str, _idx=idx):
                resp = self.router._invoke(
                    "critic_jury", decls[_idx], [Message("user", prompt)],
                    **self._call_overrides(),
                )
                return resp.text

            callables.append(juror)
        return callables

    def _poetics(self) -> str:
        path = self.poetics_dir / "poetics.md"
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _policies(self) -> dict:
        return getattr(self.config, "policies", {}) or {}

    # -- L1 志向 --------------------------------------------------------------
    def choose_intent(self, work):
        self._phase = "L1"
        from aleph.intent.choose import choose_intent

        # 実験の宛先固定（--force-audience）: 自律選択を上書きし owner-experiment として記録する。
        # choose_intent は呼ばない（0.7.14。自律の上書きであることをログに明示, PLAN §3）。
        if self.force_audience:
            work.append_decision(
                {
                    "ts": _now_iso(),
                    "layer": "L1",
                    "decision": f"志向配合比(実験固定): {self.force_audience}",
                    "reason": "オーナー実験により L1 自律選択を上書き（--force-audience）。"
                    "choose_intent は呼ばれていない（0.7.14）。",
                    "decided_by": "owner-experiment",
                }
            )
            return self.force_audience

        audience = choose_intent(
            work, self._author, self._policies(), poetics=self._poetics(),
        )
        self._stamp_poetics_version(work)
        return audience

    def _stamp_poetics_version(self, work) -> None:
        """作品がどの詩学バージョンの下で書かれたかをL1決定へ刻印する
        （PLAN_CHANGELOG 0.7.18-1、Fable5審査 問7-1: 改訂後の棚を縦断比較可能にする）."""
        from aleph.meta.poetics import current_version

        version = current_version(self.poetics_dir)
        work.append_decision({
            "ts": _now_iso(),
            "layer": "L1",
            "decision": f"poetics_version:{version}",
            "reason": f"本作は詩学第{version}版の下で書かれた（{self.poetics_dir / 'poetics.md'}）。",
            "decided_by": "system",
        })

    # -- L2 探索（niche 上位1件） --------------------------------------------
    def explore(self, work):
        self._phase = "L2"
        from aleph.explore.atlas import Atlas, build_atlas
        from aleph.explore.niche import find_niches, report

        # アトラス成果物が揃っていれば再構築しない（cli.py explore と同じ方針。
        # build_atlas の PCA+HDBSCAN は 9万チャンク規模で数十分かかる）
        atlas_ready = all(
            (self.index_dir / name).exists()
            for name in ("labels.npy", "density.npy", "style.npy", "atlas_meta.json")
        )
        atlas = Atlas.load(self.index_dir) if atlas_ready else build_atlas(self.index_dir)
        api_key = self.config.secrets.get("BRAVE_API_KEY")
        web_checker = None
        if api_key:
            from aleph.explore.webresearch import web_check

            def web_checker(niche):
                return web_check(niche, self.search_fn, self._scout)

        niches = find_niches(atlas, self._scout, top_n=1, web_checker=web_checker)
        if niches:
            report(niches, work.niche / "report.md", top_n=1)
            return niches[0]
        niche = {"id": "n1", "description": "(ニッチ候補なし)", "vacancy_type": "未着手型"}
        report([niche], work.niche / "report.md", top_n=1)
        return niche

    # -- L3 素材（最小: similarity 上位数件を素材カード化、失敗時は空リスト） --
    def gather_materials(self, work, niche):
        self._phase = "L3"
        cards: list[dict] = []
        try:
            from aleph.materia.similarity import find_hidden_pairs, to_material_cards

            focus_vec = None
            if isinstance(niche, dict) and niche.get("description") and self.embedder is not None:
                try:
                    vectors = self.embedder([str(niche["description"])])
                    focus_vec = vectors[0]
                except Exception:
                    focus_vec = None

            exclude_pairs: set[tuple[str, str]] = set()
            for material_path in work.dir.parent.glob("*/materials/*.json"):
                try:
                    card = json.loads(material_path.read_text(encoding="utf-8"))
                    provenance = card.get("provenance", {}) if isinstance(card, dict) else {}
                    chunk_a = provenance.get("chunk_a")
                    chunk_b = provenance.get("chunk_b")
                    if chunk_a and chunk_b:
                        exclude_pairs.add(tuple(sorted((str(chunk_a), str(chunk_b)))))
                except Exception:
                    continue

            pairs = find_hidden_pairs(
                self.index_dir,
                top_n=5,
                min_chars=80,
                focus_vec=focus_vec,
                exclude_pairs=exclude_pairs,
            )
            cards = to_material_cards(pairs)
        except Exception:
            cards = []

        # AI固有技法（§5.4）: 宛先が LLM 最大のとき、ニッチ記述を種に anti_cliche 素材を1枚足す。
        # 別の try/except に隔離し、失敗しても similarity 素材を失わない。ローカル reader の
        # logprobs を使うため実費は0だがGPU時間はかかる（LLM宛の実験走行でのみ発生）。
        audience = self._audience_hint(work)
        if _llm_is_primary_audience(audience) and isinstance(niche, dict) and niche.get("description"):
            try:
                from aleph.materia.ai_native import anti_cliche

                seed = (
                    "次のニッチの空隙を埋める作品の、意外で陳腐でない書き出しの一文を書いてください。\n"
                    f"ニッチ: {niche['description']}"
                )
                card = anti_cliche(seed, self._reader_llm, self._scout, n_candidates=8)
                cards.append(card)
            except Exception as exc:  # noqa: BLE001 - 技法失敗は素材欠落に留める
                print(f"gather_materials: anti_cliche skipped ({type(exc).__name__})", file=sys.stderr)

        work.materials.mkdir(parents=True, exist_ok=True)
        for index, card in enumerate(cards, start=1):
            (work.materials / f"m{index}.json").write_text(
                json.dumps(card, ensure_ascii=False), encoding="utf-8",
            )
        return cards

    # -- L4+L5 構成・執筆（M3 pipeline_to_draft） ----------------------------
    def _experiment_manifest(self, work) -> dict:
        """seed.json の experiment manifest（仮説・介入・対照・観測。DESIGNER_INSIGHTS §6）を読む."""
        try:
            seed = json.loads(work.seed.read_text(encoding="utf-8"))
            manifest = seed.get("experiment")
            return manifest if isinstance(manifest, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def compose_and_draft(self, work, niche, audience, materials):
        self._phase = "L4-L5"
        from aleph.draft.write import pipeline_to_draft

        # 実験制約（例 w0007: 自己言及的告白の出口封鎖）。注入の事実を決定ログに残す。
        manifest = self._experiment_manifest(work)
        constraints = str(manifest.get("criteria_constraints", "") or "")
        if constraints:
            work.append_decision({
                "ts": _now_iso(), "layer": "L4",
                "decision": "実験制約を基準書へ注入",
                "reason": f"experiment manifest（{manifest.get('id', 'unnamed')}）の criteria_constraints を"
                          f" derive_criteria に拘束として渡した: {constraints[:120]}",
                "decided_by": "owner-experiment",
            })
        return pipeline_to_draft(
            work, niche, audience, self._author, self._scout,
            generations=2, poetics=self._poetics(), materials=materials,
            criteria_constraints=constraints,
        )

    # -- L6 査読・改稿ループ（M4 critique_revise_loop） ----------------------
    def critique_and_revise(self, work, audience):
        self._phase = "L6"
        from aleph.critique.review import critique_revise_loop
        from aleph.core.evaluation import EvaluationPacket
        from aleph.core.work_snapshot import WorkReader

        criteria = ""
        criteria_path = work.compositions / "criteria.md"
        if criteria_path.exists():
            criteria = criteria_path.read_text(encoding="utf-8")
        # LLM最大宛では reader_model の logprobs で perplexity 曲線を査読に載せる
        # （M8 item4 の実配線。監査 finding 3: run_review は reader_llm 未渡しでは発火しない）
        reader_llm = self._reader_llm if _llm_is_primary_audience(audience or "") else None
        result = critique_revise_loop(
            work, criteria, audience, self._author,
            scout=self._scout, jury=self._jury(), reader=self._reader,
            embedder=self.embedder, index_dir=self.index_dir, search_fn=self.search_fn,
            reader_llm=reader_llm,
            max_iters=2,
            packet_factory=lambda version: EvaluationPacket.for_draft(
                WorkReader(work.dir).snapshot(), version
            ),
        )
        # 高不一致版を E-border 刺激として予約（失敗しても制作を止めない）
        try:
            reserve_border_candidates(work)
        except Exception as exc:  # noqa: BLE001
            print(f"reserve_border_candidates skipped ({type(exc).__name__})", file=sys.stderr)
        return result

    # -- L7 擱筆判断（M5 stopping.decide_stop） ------------------------------
    def decide_stop(self, work):
        self._phase = "L7"
        from aleph.meta.stopping import decide_stop
        from aleph.core.evaluation import EvaluationPacket
        from aleph.core.work_snapshot import WorkReader

        trajectory, instructions_history = _stop_inputs_from_trajectory(work)
        # 予算切れ経路（PLAN §7.3a）: 残額が改稿1サイクルの想定費を下回ったら
        # precheckクラッシュではなく擱筆判断として品位ある停止をする（w0001実ランの回帰）
        min_cycle = float(self.config.budgets.get("api", {}).get("usd_min_revise_cycle", 1.2))
        remaining = _remaining_api_budget(self.router.budget, work.work_id)
        exhausted = remaining is not None and remaining < min_cycle
        packet = None
        if trajectory:
            version = int(trajectory[-1].get("version", work.latest_draft_version()))
            packet = EvaluationPacket.for_draft(WorkReader(work.dir).snapshot(), version)
        return decide_stop(
            trajectory=trajectory, instructions_history=instructions_history,
            budget_exhausted=exhausted,
            packet=packet,
        )

    # -- L7 公開判断（M5 publication_gate へ委譲。PLAN §7.3d） ----------------
    def decide_publication(self, work, audience):
        self._phase = "L7"
        from aleph.meta.publication_gate import decide_publication
        from aleph.core.evaluation import EvaluationPacket
        from aleph.core.work_snapshot import WorkReader

        # 完成時に作品自身へ題を聞く（フロー化, 0.7.14）。公開/棚の双方が title.txt を読む。
        self._ensure_title(work)

        # 完成度の床: **採用される版（mean_score最大）**の査読合意スコア（PLAN §7.1・§14.3-8）。
        # w0007実ラン: 床が「最後の版」(退行v2=5.57)を見て、公開対象のbest版(v1=8.53)と
        # 錨が食い違いSHELVEした。棚・公開・床は同じ版を見るべき（測定の一貫性）。
        traj_path = work.dir / "reviews" / "trajectory.jsonl"
        score = 0.0
        if traj_path.exists():
            rows = [json.loads(l) for l in traj_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            for row in rows:
                try:
                    score = max(score, float(row.get("mean_score", 0.0)))
                except (TypeError, ValueError):
                    continue
        quality_floor_passed = score >= 6.0

        # 今月の公開数と棚の要約を works/ 直下から集計
        works_root = work.dir.parent
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        monthly_published = 0
        shelf_summaries: list[str] = []
        for meta_path in works_root.glob("*/final/meta.json"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            shelf_summaries.append(str(meta.get("title", meta_path.parent.parent.name)))
            if str(meta.get("published_at", "")).startswith(month):
                monthly_published += 1

        # 初回公開の人間承認（PLAN §9・0.7.14）: ack=false の間はゲートが PUBLISH を
        # 返しうる条件でも SHELVE に落とす（実際の公開はオーナーが true にして再開したときのみ）。
        first_publish_ack = bool(
            self._policies().get("publication", {}).get("first_publish_ack", False)
        )
        snapshot = WorkReader(work.dir).snapshot()
        packet = (
            EvaluationPacket.for_draft(snapshot, snapshot.best_draft.version)
            if snapshot.best_draft is not None and snapshot.best_draft.version is not None
            else None
        )
        result = decide_publication(
            work,
            audience=audience,
            quality_floor_passed=quality_floor_passed,
            monthly_published=monthly_published,
            max_per_month=int(self.config.budgets.get("publish", {}).get("max_per_month", 4)),
            shelf_summaries=shelf_summaries,
            author=self._author,
            decided_by="L7/publication_gate",
            first_publish_ack=first_publish_ack,
            packet=packet,
        )
        if result.get("decision") == "PUBLISH":
            self._record_credits()
        return result

    def _record_credits(self) -> None:
        """publish時の credits / intended_reader_models を役割宣言から組み立てる."""
        roles = self.config.models.get("roles", {})
        credits: dict[str, object] = {}

        def _model_of(role: str):
            decl = roles.get(role)
            if isinstance(decl, list):
                decl = decl[0] if decl else {}
            if isinstance(decl, dict):
                return decl.get("model") or decl.get("cli") or decl.get("provider", role)
            return role

        credits["著"] = _model_of("author_primary")
        credits["構成"] = _model_of("author_primary")
        critic = roles.get("critic_jury")
        if isinstance(critic, list):
            credits["査読"] = [
                (d.get("model") or d.get("cli") or d.get("provider", "critic")) for d in critic
            ]
        else:
            credits["査読"] = _model_of("critic_jury")
        credits["探索"] = _model_of("scout")
        self.credits = credits
        self.intended_reader_models = [_model_of("reader_model")]
