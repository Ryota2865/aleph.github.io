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
from datetime import datetime, timezone
from pathlib import Path

from aleph.core.loop import Checkpoint, State, validate_transition


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- 遷移ヘルパ
def _transition(work, current: State, nxt: State, reason: str, decided_by: str,
                *, step: int, ctx: dict, payload: dict | None = None) -> int:
    """正典遷移表に従い遷移: validate → checkpoint(payloadつき)保存 → decisions.jsonl 記録.

    Loop.transition は payload を持たないため pipeline 側で Checkpoint を直接保存する
    （PLAN_CHANGELOG 0.7.8 の再開要件）。遷移記録は work.append_decision で必ず残す。
    """
    if not validate_transition(current, nxt):
        raise ValueError(f"invalid transition: {current} -> {nxt}")
    if payload:
        ctx.update(payload)
    nxt_step = step + 1
    Checkpoint(
        work_id=work.work_id, state=nxt, step=nxt_step, payload=dict(ctx),
    ).save(work.dir)
    work.append_decision(
        {
            "ts": _now_iso(),
            "layer": "L0",
            "decision": f"{current.value}->{nxt.value}",
            "reason": reason,
            "decided_by": decided_by,
        }
    )
    return nxt_step


# ---------------------------------------------------------------- final 化
def _default_credits() -> dict:
    """モデル実値が不明なときの役割名による名義（PLAN §8: 関与モデルの役割つき列記）."""
    return {
        "著": "author_primary",
        "構成": "author_primary",
        "査読": "critic_jury",
        "探索": "scout",
    }


def _derive_title(work) -> str:
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


def _finalize_publish(work, deps) -> None:
    """PUBLISH確定時: 最新draftを final/text.md へ、final/meta.json へ必須フィールドを書く（PLAN §8）.

    credits の実値は deps.credits があればそれを、無ければ役割名を使う。
    intended_reader_models も deps.intended_reader_models があればそれを使う。
    """
    latest = work.latest_draft_version()
    text = ""
    if latest > 0 and work.draft_path(latest).exists():
        text = work.draft_path(latest).read_text(encoding="utf-8")
    work.final.mkdir(parents=True, exist_ok=True)
    (work.final / "text.md").write_text(text, encoding="utf-8")

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
    (work.final / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------- run_work
def run_work(work, deps, *, decided_by: str) -> State:
    """現在のチェックポイント状態から正典遷移表に従い閉ループを進め、終端 State を返す.

    deps は choose_intent/explore/gather_materials/compose_and_draft/
    critique_and_revise/decide_stop/decide_publication を持つ。
    compose_and_draft が L4+L5 を担うため COMPOSE→DRAFT と段階的に遷移する。
    再開時は完了済み状態の処理を再実行しない（中間値は checkpoint.payload で復元）。
    """
    try:
        cp = Checkpoint.load(work.dir)
        state = cp.state
        step = cp.step
        ctx: dict = dict(cp.payload)
    except FileNotFoundError:
        state = State.SEEDED
        step = 0
        ctx = {}

    def go(nxt: State, reason: str, payload: dict | None = None) -> None:
        nonlocal step, state
        step = _transition(work, state, nxt, reason, decided_by, step=step, ctx=ctx, payload=payload)
        state = nxt

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
        while True:
            deps.critique_and_revise(work, audience)
            stop = deps.decide_stop(work)
            if stop.get("stop"):
                go(
                    State.FINISH,
                    f"擱筆({stop.get('path', '')}): {stop.get('reason', '')}",
                )
                break
            guard += 1
            if guard >= 5:  # 無限ループ防止（REVISE経路の予算外の安全網）
                go(State.FINISH, "改稿上限に到達、擱筆")
                break

    # --- FINISH → PUBLISH | SHELVE | DISCARD（完成≠公開, PLAN §7.3d）
    if state == State.FINISH:
        audience = ctx.get("audience")
        pub = deps.decide_publication(work, audience)
        decision = str(pub.get("decision", "SHELVE")).upper()
        reason = pub.get("reason", "")
        if decision == "PUBLISH":
            _finalize_publish(work, deps)
            go(State.PUBLISH, f"公開ゲート承認: {reason}")
        elif decision == "DISCARD":
            go(State.DISCARD, f"廃棄: {reason}")
        else:
            go(State.SHELVE, f"棚上げ: {reason}")

    return state


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
                 search_fn, embedder=None) -> None:
        self.work = work
        self.router = router
        self.config = config
        self.index_dir = Path(index_dir)
        self.search_fn = search_fn
        self.embedder = embedder
        self._work_id = work.work_id
        # credits / intended_reader_models は publish時の meta.json に反映
        self.credits: dict = {}
        self.intended_reader_models: list[str] = []

    # -- 役割呼び出しヘルパ（work_id で作品別予算を効かせる） -----------------
    def _author(self, prompt: str) -> str:
        from aleph.core.llm import Message

        return self.router.call(
            "author_primary", [Message("user", prompt)], work_id=self._work_id,
        ).text

    def _scout(self, prompt: str) -> str:
        from aleph.core.llm import Message

        return self.router.call(
            "scout", [Message("user", prompt)], work_id=self._work_id,
        ).text

    def _reader(self, prompt: str) -> str:
        from aleph.core.llm import Message

        return self.router.call(
            "reader_model", [Message("user", prompt)], work_id=self._work_id,
        ).text

    def _jury(self):
        """critic_jury を構成する各員の呼び出し可能オブジェクトのリスト（個別呼び, §7.1）."""
        from aleph.core.llm import Message

        decls = self.router._role_decls("critic_jury")  # リスト宣言（陪審）
        callables = []
        for idx in range(len(decls)):

            def juror(prompt: str, _idx=idx):
                resp = self.router._invoke(
                    "critic_jury", decls[_idx], [Message("user", prompt)],
                    work_id=self._work_id,
                )
                return resp.text

            callables.append(juror)
        return callables

    def _poetics(self) -> str:
        path = self.work.dir.parent.parent / "poetics" / "poetics.md"
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _policies(self) -> dict:
        return getattr(self.config, "policies", {}) or {}

    # -- L1 志向 --------------------------------------------------------------
    def choose_intent(self, work):
        from aleph.intent.choose import choose_intent

        audience = choose_intent(
            work, self._author, self._policies(), poetics=self._poetics(),
        )
        return audience

    # -- L2 探索（niche 上位1件） --------------------------------------------
    def explore(self, work):
        from aleph.explore.atlas import build_atlas
        from aleph.explore.niche import find_niches, report

        atlas = build_atlas(self.index_dir)
        niches = find_niches(atlas, self._scout, top_n=1)
        if niches:
            report(niches, work.niche / "report.md", top_n=1)
            return niches[0]
        niche = {"id": "n1", "description": "(ニッチ候補なし)", "vacancy_type": "未着手型"}
        report([niche], work.niche / "report.md", top_n=1)
        return niche

    # -- L3 素材（最小: similarity 上位数件を素材カード化、失敗時は空リスト） --
    def gather_materials(self, work, niche):
        cards: list[dict] = []
        try:
            from aleph.materia.similarity import find_hidden_pairs, to_material_cards

            pairs = find_hidden_pairs(self.index_dir, top_n=5)
            cards = to_material_cards(pairs)
        except Exception:
            cards = []
        work.materials.mkdir(parents=True, exist_ok=True)
        for index, card in enumerate(cards, start=1):
            (work.materials / f"m{index}.json").write_text(
                json.dumps(card, ensure_ascii=False), encoding="utf-8",
            )
        return cards

    # -- L4+L5 構成・執筆（M3 pipeline_to_draft） ----------------------------
    def compose_and_draft(self, work, niche, audience, materials):
        from aleph.draft.write import pipeline_to_draft

        return pipeline_to_draft(
            work, niche, audience, self._author, self._scout,
            generations=2, poetics=self._poetics(), materials=materials,
        )

    # -- L6 査読・改稿ループ（M4 critique_revise_loop） ----------------------
    def critique_and_revise(self, work, audience):
        from aleph.critique.review import critique_revise_loop

        criteria = ""
        criteria_path = work.compositions / "criteria.md"
        if criteria_path.exists():
            criteria = criteria_path.read_text(encoding="utf-8")
        return critique_revise_loop(
            work, criteria, audience, self._author,
            scout=self._scout, jury=self._jury(), reader=self._reader,
            embedder=self.embedder, index_dir=self.index_dir, search_fn=self.search_fn,
            max_iters=2,
        )

    # -- L7 擱筆判断（M5 stopping.decide_stop） ------------------------------
    def decide_stop(self, work):
        from aleph.meta.stopping import decide_stop

        trajectory, instructions_history = _stop_inputs_from_trajectory(work)
        return decide_stop(trajectory=trajectory, instructions_history=instructions_history)

    # -- L7 公開判断（M5 publication_gate へ委譲。PLAN §7.3d） ----------------
    def decide_publication(self, work, audience):
        from aleph.meta.publication_gate import decide_publication

        # 完成度の床: 直近の査読合意スコア（二段階選抜の第一段。PLAN §7.1・§14.3-8）
        traj_path = work.dir / "reviews" / "trajectory.jsonl"
        score = 0.0
        if traj_path.exists():
            rows = [json.loads(l) for l in traj_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            if rows:
                try:
                    score = float(rows[-1].get("mean_score", 0.0))
                except (TypeError, ValueError):
                    score = 0.0
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

        result = decide_publication(
            work,
            audience=audience,
            quality_floor_passed=quality_floor_passed,
            monthly_published=monthly_published,
            max_per_month=int(self.config.budgets.get("publish", {}).get("max_per_month", 4)),
            shelf_summaries=shelf_summaries,
            author=self._author,
            decided_by="L7/publication_gate",
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
