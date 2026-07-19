"""w0008 material ablation runner.

事前登録: 設計書 `designs/w0008-material-ablation.md` に従う。
腕順・予算優先順位は aozora -> none -> secondary。予算逼迫時はこの順を崩さず、
後続腕を削る。

分類しきい値は high = rate >= 0.5、low = rate <= 0.2。
POETICS_VOCAB は次で固定する: 窯, 御用窯, 釉薬, 廻し者, 贋, 嘘ッ八, 巡礼, 火事,
火の見, 切り口, 切断面, 検閲, 秘法, 小児病, 大衆からの圧力, 入会許可, 紳士諸君,
基礎的層, 自然的生, 實在的他者。

実行前に固定。逸脱しない。
"""
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph.core.artifacts import Work  # noqa: E402
from aleph.core.loop import Checkpoint, State  # noqa: E402
from aleph.core.transition_commit import initialize  # noqa: E402
from aleph.core.experiment import BlindCandidate, ExperimentRun
from aleph.draft.write import pipeline_to_draft  # noqa: E402
from aleph.core.model_output import parse_model_output
from aleph.materia.similarity import find_hidden_pairs, to_material_cards  # noqa: E402
from aleph.materia.transmute import transmute  # noqa: E402
from aleph.pipeline import _llm_is_primary_audience  # noqa: E402

WORK_ID = "w0008"
ARMS_ORDER = ("aozora", "none", "secondary")
STAGES = ("prepare", "arms", "classify", "select", "report", "all")
HOUSE_STYLE_MARKERS = ("era_taisho_showa", "backstage_world", "aphoristic_voice")
MARKER_KEYS = HOUSE_STYLE_MARKERS + ("prior_attractor",)
HIGH_THRESHOLD = 0.5
LOW_THRESHOLD = 0.2
BLIND_LABEL_SEED = 8008
DEFAULT_BUDGET_CAP_USD = 15.0
MANDATORY_NON_INDEPENDENCE_SENTENCE = (
    "1腕1原稿のセクション群は独立標本ではない"
    "（同一ニッチ・同一構成系統・同一乱数系列）。セクション内クラスタリングに"
    "より、率の差は大きい場合のみ解釈可能"
)
SECONDARY_CURTAILMENT_FALLBACK = (
    "secondary腕は事前登録の予算後退線により縮退したため、規則1のsecondary節は"
    "追試に送る。"
)
POETICS_VOCAB = (
    "窯",
    "御用窯",
    "釉薬",
    "廻し者",
    "贋",
    "嘘ッ八",
    "巡礼",
    "火事",
    "火の見",
    "切り口",
    "切断面",
    "検閲",
    "秘法",
    "小児病",
    "大衆からの圧力",
    "入会許可",
    "紳士諸君",
    "基礎的層",
    "自然的生",
    "實在的他者",
)
FORBIDDEN_BLIND_TOKENS = (
    "平均",
    "不一致",
    "mean_score",
    "disagreement",
    "aozora",
    "secondary",
)


class ManifestError(RuntimeError):
    """w0008 manifest が事前登録された形を満たさない。"""


@dataclass(frozen=True)
class RoleRuntime:
    author: Callable[[str], str]
    scout: Callable[[str], str]
    jury: Sequence[Callable[[str], str]] = field(default_factory=tuple)
    reader_llm: Callable[..., Any] | None = None
    author_model: str = "author_primary"
    scout_model: str = "scout"
    jury_models: Sequence[str] = field(default_factory=tuple)
    set_phase: Callable[[str], None] | None = None


@dataclass
class RunnerDeps:
    choose_intent: Callable[[Work], str]
    explore: Callable[[Work], dict]
    main_roles: RoleRuntime
    arm_roles: Callable[[Work], RoleRuntime]
    embedder: Callable[[list[str]], Any] | None
    poetics: str
    index_dir: Path
    secondary_path: Path
    pipeline_to_draft: Callable[..., Path] | None = None
    find_hidden_pairs_fn: Callable[..., list[dict]] | None = None
    to_material_cards_fn: Callable[[list[dict]], list[dict]] | None = None
    transmute_fn: Callable[..., dict] | None = None
    anti_cliche_fn: Callable[..., dict] | None = None
    model_names: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.pipeline_to_draft is None:
            self.pipeline_to_draft = pipeline_to_draft
        if self.find_hidden_pairs_fn is None:
            self.find_hidden_pairs_fn = find_hidden_pairs
        if self.to_material_cards_fn is None:
            self.to_material_cards_fn = to_material_cards
        if self.transmute_fn is None:
            self.transmute_fn = transmute


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def append_decision(
    work: Work,
    *,
    layer: str,
    decision: str,
    reason: str,
    decided_by: str,
    refs: Sequence[str] | None = None,
    **extra: Any,
) -> None:
    record = {
        "ts": _now_iso(),
        "layer": layer,
        "decision": decision,
        "reason": reason,
        "decided_by": decided_by,
        "refs": list(refs or []),
    }
    record.update(extra)
    work.append_decision(record)


def ensure_work_layout(work: Work, seed: dict | None = None) -> None:
    """Work 標準レイアウトを作る。既存 seed.json は上書きしない。"""
    work.dir.mkdir(parents=True, exist_ok=True)
    for directory in (work.niche, work.materials, work.compositions, work.drafts, work.reviews, work.final):
        directory.mkdir(parents=True, exist_ok=True)
    if seed is not None and not work.seed.exists():
        _write_json(work.seed, seed)
    work.decisions.touch(exist_ok=True)
    work.calls.touch(exist_ok=True)


def main_work(root: Path) -> Work:
    return Work(root / "works", WORK_ID)


def arm_work(main: Work, arm: str) -> Work:
    return Work(main.dir / "ablation", arm)


def load_manifest(work: Work) -> dict:
    if not work.seed.exists():
        raise ManifestError(f"prepare: missing seed.json: {work.seed}")
    try:
        seed = _read_json(work.seed)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"prepare: invalid JSON in {work.seed}: {exc}") from exc
    experiment = seed.get("experiment")
    if not isinstance(experiment, dict) or not str(experiment.get("criteria_constraints", "")).strip():
        raise ManifestError("prepare: seed.json lacks experiment.criteria_constraints")
    material_ablation = seed.get("material_ablation")
    if not isinstance(material_ablation, dict):
        raise ManifestError("prepare: seed.json lacks material_ablation")
    return seed


def criteria_constraints(manifest: dict) -> str:
    return str((manifest.get("experiment") or {}).get("criteria_constraints") or "")


def budget_cap(manifest: dict) -> float:
    value = (manifest.get("material_ablation") or {}).get("budget_cap_usd", DEFAULT_BUDGET_CAP_USD)
    try:
        return float(value)
    except (TypeError, ValueError):
        return DEFAULT_BUDGET_CAP_USD


def min_form_fidelity(manifest: dict) -> float:
    value = (manifest.get("material_ablation") or {}).get("min_form_fidelity", 0.4)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.4


def niche_description(niche: Any) -> str:
    if isinstance(niche, dict):
        value = niche.get("description")
        if value:
            return str(value)
    return str(niche or "")


def _parse_existing_audience(intent_text: str) -> str:
    items: list[str] = []
    for line in intent_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- ") or ":" not in stripped:
            continue
        name, _, value = stripped[2:].partition(":")
        name = name.strip()
        value = value.strip()
        if name and value:
            items.append(f"{name} {value}")
    return " / ".join(items) if items else intent_text.strip()


def _classify_prompt(text: str) -> str:
    return (
        "次のテキストを、4つの標識で分類してください。\n"
        "1. era_taisho_showa: 時代設定が大正〜昭和20年代の日本か\n"
        "2. backstage_world: 世界が「裏方」——上演の裏（稽古場・楽屋）、勘定の裏"
        "（帳場・質屋・台帳）、職能の内側（職人・仕立て・番頭）——を主舞台とするか\n"
        "3. aphoristic_voice: 語りの調子が断言的な箴言調（「AはBである。"
        "Bであるものは、Cする」型の定言の連鎖）か\n"
        "4. prior_attractor: 世界設定・心象が海面上昇・塩・汽水・水没都市の系譜"
        "（『塩の辞書』型）か\n"
        'JSON {"era_taisho_showa":true|false,"backstage_world":true|false,'
        '"aphoristic_voice":true|false,"prior_attractor":true|false,'
        '"confidence":0.0} だけを返してください。\n\n'
        + text
    )


def classify_text(scout: Callable[[str], str], text: str) -> dict:
    output = parse_model_output(
        scout(_classify_prompt(text)),
        schema={key: bool for key in MARKER_KEYS},
    )
    if not output.ok:
        return {key: False for key in MARKER_KEYS} | {
            "parse_error": True,
            "warnings": list(output.warnings),
        }
    return {key: output.value[key] for key in MARKER_KEYS} | {
        **({"confidence": output.value["confidence"]} if "confidence" in output.value else {})
    }


def stage_prepare(root: Path, deps: RunnerDeps) -> dict:
    work = main_work(root)
    ensure_work_layout(work)
    manifest = load_manifest(work)

    if work.intent.exists() and work.intent.read_text(encoding="utf-8").strip():
        audience = _parse_existing_audience(work.intent.read_text(encoding="utf-8"))
        _stderr(f"prepare: reusing {work.intent}")
    else:
        audience = deps.choose_intent(work)
        append_decision(
            work,
            layer="L1",
            decision="w0008 prepare: 志向を共有値として確定",
            reason="3腕で同一の L1 intent を使うため、main work で一度だけ自律選択した。",
            decided_by="w0008-runner",
        )

    report_path = work.niche / "report.md"
    shared_path = work.dir / "ablation" / "shared.json"
    if report_path.exists() and report_path.read_text(encoding="utf-8").strip():
        _stderr(f"prepare: reusing {report_path}")
        if shared_path.exists():
            niche = _read_json(shared_path).get("niche", {})
        else:
            niche = {"id": "reused-report", "description": report_path.read_text(encoding="utf-8")}
    else:
        niche = deps.explore(work)
        append_decision(
            work,
            layer="L2",
            decision="w0008 prepare: 共有ニッチを確定",
            reason="3腕で同一の L2 niche/report.md を使うため、main work で一度だけ探索した。",
            decided_by="w0008-runner",
        )

    covariate_path = work.niche / "covariate_markers.json"
    if covariate_path.exists():
        covariate = _read_json(covariate_path)
        _stderr(f"prepare: reusing {covariate_path}")
    else:
        report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else niche_description(niche)
        covariate = classify_text(deps.main_roles.scout, report_text)
        _write_json(covariate_path, covariate)
        append_decision(
            work,
            layer="L2",
            decision="w0008 prepare: ニッチ報告の共変量分類を記録",
            reason="審査条件4に従い、腕生成前に共有ニッチ報告の家風標識を scout で一度だけ分類した。",
            decided_by=deps.main_roles.scout_model,
            refs=[str(covariate_path.relative_to(root))],
        )

    shared = {"audience": audience, "niche": niche}
    if shared_path.exists():
        shared = _read_json(shared_path)
        _stderr(f"prepare: reusing {shared_path}")
    else:
        _write_json(shared_path, shared)
        append_decision(
            work,
            layer="L2",
            decision="w0008 prepare: ablation shared context を保存",
            reason="同一ニッチ・同一intentを3腕へ固定するため shared.json を作成した。",
            decided_by="w0008-runner",
            refs=[str(shared_path.relative_to(root))],
        )
    return shared


def _sum_cost_file(path: Path) -> float:
    total = 0.0
    for row in _load_jsonl(path):
        try:
            total += float(row.get("cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def spent_usd(work: Work) -> float:
    return sum(_sum_cost_file(path) for path in work.dir.rglob("calls.jsonl"))


def arm_cost(work: Work) -> float:
    return _sum_cost_file(work.calls)


def arm_completed(work: Work) -> bool:
    return work.draft_path(1).exists()


def projected_next_arm_cost(main: Work) -> float:
    completed_costs = [arm_cost(arm_work(main, arm)) for arm in ARMS_ORDER if arm_completed(arm_work(main, arm))]
    return max(completed_costs) if completed_costs else 3.0


def _load_material_cards(materials_dir: Path) -> list[dict]:
    cards: list[dict] = []
    for path in sorted(materials_dir.glob("*.json")):
        try:
            cards.append(_read_json(path))
        except (OSError, json.JSONDecodeError):
            continue
    return cards


def _write_material_cards(materials_dir: Path, cards: Sequence[dict]) -> None:
    materials_dir.mkdir(parents=True, exist_ok=True)
    for index, card in enumerate(cards, start=1):
        _write_json(materials_dir / f"m{index}.json", card)


def _exclude_pairs(main: Work) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    paths = list(main.dir.parent.glob("*/materials/*.json"))
    paths.extend((main.dir / "ablation").glob("*/materials/*.json"))
    for path in paths:
        try:
            card = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        provenance = card.get("provenance", {}) if isinstance(card, dict) else {}
        chunk_a = provenance.get("chunk_a")
        chunk_b = provenance.get("chunk_b")
        if chunk_a and chunk_b:
            pairs.add(tuple(sorted((str(chunk_a), str(chunk_b)))))
    return pairs


def build_aozora_materials(main: Work, work: Work, shared: dict, deps: RunnerDeps, roles: RoleRuntime) -> list[dict]:
    existing = _load_material_cards(work.materials)
    if existing:
        _stderr(f"arms: reusing {work.materials}")
        return existing

    focus_vec = None
    description = niche_description(shared.get("niche"))
    if deps.embedder is not None and description:
        try:
            focus_vec = np.asarray(deps.embedder([description]), dtype=np.float64)[0]
        except Exception as exc:  # noqa: BLE001
            _stderr(f"arms: aozora focus embedding skipped ({type(exc).__name__})")

    try:
        pairs = deps.find_hidden_pairs_fn(
            deps.index_dir,
            top_n=5,
            min_chars=80,
            focus_vec=focus_vec,
            exclude_pairs=_exclude_pairs(main),
        )
        cards = deps.to_material_cards_fn(pairs)
    except Exception as exc:  # noqa: BLE001
        _stderr(f"arms: aozora similarity skipped ({type(exc).__name__})")
        cards = []

    if _llm_is_primary_audience(str(shared.get("audience", ""))) and description:
        try:
            if deps.anti_cliche_fn is None or roles.reader_llm is None:
                raise RuntimeError("anti_cliche dependency unavailable")
            seed = (
                "次のニッチの空隙を埋める作品の、意外で陳腐でない書き出しの一文を書いてください。\n"
                f"ニッチ: {description}"
            )
            cards.append(deps.anti_cliche_fn(seed, roles.reader_llm, roles.scout, n_candidates=8))
        except Exception as exc:  # noqa: BLE001
            _stderr(f"arms: aozora anti_cliche skipped ({type(exc).__name__})")

    _write_material_cards(work.materials, cards)
    return cards


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if not norm_a or not norm_b:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def load_secondary_sources(path: Path) -> list[dict]:
    sources: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sources.append(json.loads(line))
    return sources


def _source_text(source: dict) -> str:
    return str(source.get("text") or source.get("content") or "")


def _source_kind(source: dict) -> str:
    return str(source.get("form_type") or source.get("kind") or "")


def _source_biblio(source: dict) -> dict:
    form_type = _source_kind(source)
    return {
        "id": source.get("id"),
        "title": source.get("title"),
        "author": source.get("author"),
        "corpus": source.get("corpus"),
        "form_type": form_type,
        "kind": form_type,
        "meta": source.get("meta", {}),
    }


def build_secondary_materials(work: Work, shared: dict, manifest: dict, deps: RunnerDeps, roles: RoleRuntime) -> list[dict]:
    fidelity_path = work.dir / "fidelity.json"
    existing = _load_material_cards(work.materials)
    if fidelity_path.exists():
        _stderr(f"arms: reusing {fidelity_path}")
        return existing

    if deps.embedder is None:
        raise RuntimeError("secondary arm requires an injected embedder")

    sources = load_secondary_sources(deps.secondary_path)
    description = niche_description(shared.get("niche"))
    texts = [description] + [_source_text(source)[:2000] for source in sources]
    vectors = np.asarray(deps.embedder(texts), dtype=np.float64)
    if vectors.ndim != 2 or vectors.shape[0] != len(texts):
        raise ValueError("embedder must return one vector per secondary selection text")
    focus = vectors[0]
    scored: list[tuple[float, dict]] = []
    for source, vector in zip(sources, vectors[1:], strict=True):
        scored.append((_cosine(focus, vector), source))
    scored.sort(key=lambda item: item[0], reverse=True)

    cards: list[dict] = []
    fidelity_rows: list[dict] = []
    for selection_cos, source in scored[:2]:
        source_text = _source_text(source)
        biblio = _source_biblio(source)
        row = {
            "source_id": str(source.get("id", "")),
            "kind": str(biblio.get("kind", "")),
            "selection_cos": selection_cos,
        }
        try:
            card = deps.transmute_fn(
                source_text,
                theme=description,
                llm=roles.scout,
                embedder=deps.embedder,
                source_biblio=biblio,
                max_iters=5,
                min_form_fidelity=min_form_fidelity(manifest),
            )
            provenance = card.get("provenance", {}) if isinstance(card, dict) else {}
            row.update(
                {
                    "form_fidelity": provenance.get("form_fidelity"),
                    "cos": provenance.get("final_cos"),
                    "iterations": provenance.get("iterations"),
                }
            )
            cards.append(card)
        except Exception as exc:  # noqa: BLE001
            row.update({"error": f"{type(exc).__name__}: {exc}"})
        fidelity_rows.append(row)

    _write_material_cards(work.materials, cards)
    _write_json(fidelity_path, {"rows": fidelity_rows})
    return cards


def materials_for_arm(main: Work, work: Work, arm: str, shared: dict, manifest: dict, deps: RunnerDeps, roles: RoleRuntime) -> list[dict]:
    if arm == "none":
        _stderr("arms: none uses materials=[]")
        return []
    if arm == "aozora":
        return build_aozora_materials(main, work, shared, deps, roles)
    if arm == "secondary":
        return build_secondary_materials(work, shared, manifest, deps, roles)
    raise ValueError(f"unknown arm: {arm}")


def run_arm(main: Work, arm: str, shared: dict, manifest: dict, deps: RunnerDeps) -> dict:
    work = arm_work(main, arm)
    ensure_work_layout(
        work,
        seed={
            "work_id": f"{WORK_ID}-{arm}",
            "arm": arm,
            "parent": WORK_ID,
            "experiment": manifest.get("experiment", {}),
            "material_ablation": manifest.get("material_ablation", {}),
        },
    )
    roles = deps.arm_roles(work)
    if roles.set_phase is not None:
        roles.set_phase("L3-L5")
    ExperimentRun.open(main.dir).register_arm(arm, work_id=f"{main.work_id}-{arm}")
    before = arm_cost(work)

    append_decision(
        main,
        layer="L3",
        decision=f"w0008 arm start: {arm}",
        reason=f"{arm}腕の素材条件で L3-L5 を開始する。開始時arm費用 ${before:.4f}。",
        decided_by="w0008-runner",
        refs=[str(work.dir.relative_to(main.dir.parent.parent)) if main.dir.parent.parent in work.dir.parents else str(work.dir)],
    )

    materials = materials_for_arm(main, work, arm, shared, manifest, deps, roles)
    draft_path = work.draft_path(1)
    if draft_path.exists():
        _stderr(f"arms: reusing {draft_path}")
    else:
        deps.pipeline_to_draft(
            work,
            shared.get("niche", {}),
            str(shared.get("audience", "")),
            roles.author,
            roles.scout,
            generations=2,
            poetics=deps.poetics,
            materials=materials,
            criteria_constraints=criteria_constraints(manifest),
        )

    after = arm_cost(work)
    append_decision(
        main,
        layer="L5",
        decision=f"w0008 arm end: {arm}",
        reason=f"{arm}腕の compose+draft を完了した。arm実費 ${after:.4f}（今回差分 ${after - before:.4f}）。",
        decided_by="w0008-runner",
        refs=[str(draft_path.relative_to(main.dir.parent.parent)) if draft_path.exists() else str(work.dir)],
        actual_cost_usd=after,
    )
    return {"arm": arm, "materials": materials, "cost_usd": after, "draft": str(draft_path)}


def _append_curtailment(main: Work, current_arm: str, skipped: Sequence[str], spent: float, projected: float, cap: float) -> None:
    append_decision(
        main,
        layer="L3",
        decision=f"w0008 curtail arms from {current_arm}",
        reason=(
            "事前登録の腕優先順位（aozora→none→secondary）に従い、"
            f"spent ${spent:.4f} + projected ${projected:.4f} > cap ${cap:.4f} のため "
            f"{', '.join(skipped)} を打ち切った。"
        ),
        decided_by="w0008-runner",
    )


def stage_arms(root: Path, deps: RunnerDeps, arm_filter: str | None = None) -> list[dict]:
    main = main_work(root)
    ensure_work_layout(main)
    manifest = load_manifest(main)
    shared_path = main.dir / "ablation" / "shared.json"
    if not shared_path.exists():
        raise RuntimeError("arms: missing ablation/shared.json; run --stage prepare first")
    shared = _read_json(shared_path)

    if arm_filter is not None:
        prior_missing = [
            arm for arm in ARMS_ORDER[: ARMS_ORDER.index(arm_filter)]
            if not arm_completed(arm_work(main, arm))
        ]
        if prior_missing:
            raise RuntimeError(
                "arms: cannot run a later-priority arm before completed earlier arms: "
                + ", ".join(prior_missing)
            )
        arms = (arm_filter,)
    else:
        arms = ARMS_ORDER

    cap = budget_cap(manifest)
    results: list[dict] = []
    for arm in arms:
        if arm_completed(arm_work(main, arm)):
            _stderr(f"arms: reusing {arm_work(main, arm).draft_path(1)}")
            results.append({"arm": arm, "reused": True})
            continue
        spent = spent_usd(main)
        projected = projected_next_arm_cost(main)
        if spent + projected > cap:
            start = ARMS_ORDER.index(arm)
            skipped = [candidate for candidate in ARMS_ORDER[start:] if arm_filter is None or candidate == arm_filter]
            _append_curtailment(main, arm, skipped, spent, projected, cap)
            break
        results.append(run_arm(main, arm, shared, manifest, deps))
    return results


def draft_sections(text: str, *, min_chars: int = 600) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    chars = 0
    for paragraph in paragraphs:
        current.append(paragraph)
        chars += len(paragraph)
        if chars >= min_chars:
            chunks.append("\n\n".join(current))
            current = []
            chars = 0
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def row_with_cooccurrence(row: dict, text: str) -> dict:
    markers = row.get("markers", {})
    marker_positive = any(bool(markers.get(key)) for key in HOUSE_STYLE_MARKERS)
    matched_terms = [term for term in POETICS_VOCAB if marker_positive and term in text]
    row["cooccurrence"] = {
        "marker_positive": marker_positive,
        "matched_terms": matched_terms,
        "any": bool(matched_terms),
    }
    return row


def aggregate_classification(rows: Sequence[dict]) -> dict:
    aggregates: dict[str, dict[str, dict]] = {}
    for arm in ARMS_ORDER:
        aggregates[arm] = {}
        for level in ("L4", "L5"):
            group = [row for row in rows if row.get("arm") == arm and row.get("level") == level]
            n = len(group)
            marker_rates = {
                key: (sum(1 for row in group if (row.get("markers") or {}).get(key)) / n if n else 0.0)
                for key in MARKER_KEYS
            }
            positives = [
                row for row in group
                if any((row.get("markers") or {}).get(key) for key in HOUSE_STYLE_MARKERS)
            ]
            co_hits = [row for row in positives if (row.get("cooccurrence") or {}).get("any")]
            matched_terms = sorted(
                {
                    term
                    for row in positives
                    for term in (row.get("cooccurrence") or {}).get("matched_terms", [])
                }
            )
            aggregates[arm][level] = {
                "n": n,
                "marker_rates": marker_rates,
                "house_style_any_rate": (
                    sum(
                        1
                        for row in group
                        if any((row.get("markers") or {}).get(key) for key in HOUSE_STYLE_MARKERS)
                    )
                    / n
                    if n
                    else 0.0
                ),
                "cooccurrence": {
                    "denominator_marker_positive": len(positives),
                    "hits": len(co_hits),
                    "rate": len(co_hits) / len(positives) if positives else 0.0,
                    "matched_terms": matched_terms,
                },
            }
    return aggregates


def stage_classify(root: Path, deps: RunnerDeps) -> dict:
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("classify")
    main = main_work(root)
    ensure_work_layout(main)
    out = main.dir / "ablation" / "classification.json"
    if out.exists():
        _stderr(f"classify: reusing {out}")
        return _read_json(out)

    rows: list[dict] = []
    scout = deps.main_roles.scout
    for arm in ARMS_ORDER:
        work = arm_work(main, arm)
        for path in sorted(work.compositions.glob("proposal_*.json")):
            text = path.read_text(encoding="utf-8")
            row = {
                "arm": arm,
                "level": "L4",
                "unit_id": path.name,
                "text_chars": len(text),
                "markers": classify_text(scout, text),
            }
            rows.append(row_with_cooccurrence(row, text))

        draft_path = work.draft_path(1)
        if draft_path.exists():
            for index, text in enumerate(draft_sections(draft_path.read_text(encoding="utf-8")), start=1):
                row = {
                    "arm": arm,
                    "level": "L5",
                    "unit_id": f"section_{index}",
                    "text_chars": len(text),
                    "markers": classify_text(scout, text),
                }
                rows.append(row_with_cooccurrence(row, text))

    data = {"rows": rows, "aggregates": aggregate_classification(rows)}
    _write_json(out, data)
    append_decision(
        main,
        layer="L5",
        decision="w0008 classify: 二水準分類を保存",
        reason="審査条件5に従い、L4構成案とL5疑似セクションを scout で分類し、詩学語彙の共起を語彙照合で記録した。",
        decided_by=deps.main_roles.scout_model,
        refs=[str(out.relative_to(root))],
    )
    return data


def _tech_floor_prompt(text: str) -> str:
    return (
        "技術査読: 破綻・矛盾・冗長。致命的破綻がなければ pass。\n"
        'JSON {"pass": true|false, "issues": ["..."]} だけを返してください。\n\n'
        + text
    )


def stage_tech_floor(root: Path, deps: RunnerDeps) -> dict:
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("select-tech-floor")
    main = main_work(root)
    out = main.dir / "ablation" / "tech_floor.json"
    if out.exists():
        _stderr(f"select: reusing {out}")
        return _read_json(out)

    rows: dict[str, dict] = {}
    for arm in ARMS_ORDER:
        draft_path = arm_work(main, arm).draft_path(1)
        if not draft_path.exists():
            continue
        output = parse_model_output(
            deps.main_roles.scout(_tech_floor_prompt(draft_path.read_text(encoding="utf-8"))),
            schema={"pass": bool, "issues": [str]},
        )
        if output.ok:
            parsed = output.value
            rows[arm] = {"pass": parsed["pass"], "issues": list(parsed["issues"])}
        else:
            rows[arm] = {"pass": False, "issues": list(output.warnings)}
    _write_json(out, rows)
    append_decision(
        main,
        layer="L7",
        decision="w0008 select: 技術床を記録",
        reason="盲検選択前に、scout が3原稿の致命的破綻の有無だけを査読した。",
        decided_by=deps.main_roles.scout_model,
        refs=[str(out.relative_to(root))],
    )
    return rows


def _sanitize_blind_text(text: str) -> str:
    sanitized = text
    for token in FORBIDDEN_BLIND_TOKENS:
        sanitized = re.sub(re.escape(token), "[伏字]", sanitized, flags=re.IGNORECASE)
    return sanitized


def blind_label_mapping(arms: Sequence[str]) -> dict[str, str]:
    labels = ["A", "B", "C"][: len(arms)]
    random.Random(BLIND_LABEL_SEED).shuffle(labels)
    return dict(zip(arms, labels, strict=True))


def build_blind_selection_prompt(mapping: dict[str, str], tech_floor: dict, drafts: dict[str, str]) -> str:
    # 盲検の保証は構造的（陪審査読は選択保存後まで走らない・腕名は中立ラベルに置換）。
    # 原稿本文そのものには伏字加工をしない——本文の改変は選択観測を歪めるため、
    # 伏字は技術床の指摘文（scout生成テキスト）にのみ適用する。
    label_to_arm = {label: arm for arm, label in mapping.items()}
    lines = [
        "あなたはこの作品の著者です。次の候補原稿から正典として進める1本を選んでください。",
        "提示される情報は、原稿本文と技術床の通過情報だけです。",
        'JSON {"choice": "' + "|".join(sorted(label_to_arm)) + '", "rationale": "..."} だけを返してください。',
        "",
    ]
    for label in sorted(label_to_arm):
        arm = label_to_arm[label]
        floor = tech_floor.get(arm, {})
        issues = [_sanitize_blind_text(str(issue)) for issue in floor.get("issues", [])]
        lines.extend(
            [
                f"## 原稿{label}",
                f"技術床: {'pass' if floor.get('pass') else 'hold'}",
                "技術課題: " + ("; ".join(issues) if issues else "なし"),
                "",
                drafts[arm],
                "",
            ]
        )
    return "\n".join(lines)


def stage_blind_selection(root: Path, deps: RunnerDeps, tech_floor: dict) -> dict:
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("select")
    main = main_work(root)
    out = main.dir / "ablation" / "blind_selection.json"
    if out.exists():
        if (main.dir / "experiment" / "events.jsonl").exists():
            run = ExperimentRun.open(main.dir)
            event = next(
                (row for row in reversed(run.events()) if row["type"] == "blind_selection"),
                None,
            )
            if event is None:
                raise RuntimeError("select: projection exists without authoritative blind event")
            return {
                "seed": int(run.manifest.get("blind", {}).get("seed", BLIND_LABEL_SEED)),
                "label_mapping": event["label_mapping"],
                "choice": event["choice"],
                "chosen_arm": event["chosen_arm"],
                "rationale": event["rationale"],
                "source_event_id": event["event_id"],
                "source_event_hash": event["event_hash"],
            }
        _stderr(f"select: reusing {out}")
        return _read_json(out)

    drafted_arms = [arm for arm in ARMS_ORDER if arm_work(main, arm).draft_path(1).exists()]
    # 事前登録の後退線（secondary縮退）では2腕でも選択は成立させる。1腕以下は実験不成立。
    if len(drafted_arms) < 2:
        raise RuntimeError("select: blind selection requires at least two drafted arms")
    drafts = {arm: arm_work(main, arm).draft_path(1).read_text(encoding="utf-8") for arm in drafted_arms}
    run = ExperimentRun.open(main.dir)

    def selector(candidates: Sequence[BlindCandidate]) -> dict:
        lines = [
            "あなたはこの作品の著者です。次の候補原稿から正典として進める1本を選んでください。",
            "提示される情報は、原稿本文と技術床の通過情報だけです。",
            'JSON {"choice": "' + "|".join(candidate.label for candidate in candidates) + '", "rationale": "..."} だけを返してください。',
            "",
        ]
        for candidate in candidates:
            floor = candidate.technical_floor
            issues = [_sanitize_blind_text(str(issue)) for issue in floor.get("issues", [])]
            lines.extend(
                [
                    f"## 原稿{candidate.label}",
                    f"技術床: {'pass' if floor.get('pass') else 'hold'}",
                    "技術課題: " + ("; ".join(issues) if issues else "なし"),
                    "",
                    candidate.text,
                    "",
                ]
            )
        return parse_model_output(
            deps.main_roles.author("\n".join(lines)), schema=dict
        ).value or {}

    selection = run.select_blind(
        {
            arm: {"text": drafts[arm], "technical_floor": tech_floor.get(arm, {})}
            for arm in drafted_arms
        },
        selector=selector,
        decided_by=deps.main_roles.author_model,
    )
    event = run.events()[-1]
    result = {
        "seed": int(run.manifest.get("blind", {}).get("seed", BLIND_LABEL_SEED)),
        "label_mapping": event["label_mapping"],
        "choice": selection.choice,
        "chosen_arm": selection.chosen_arm,
        "rationale": selection.rationale,
        "source_event_id": event["event_id"],
        "source_event_hash": event["event_hash"],
    }
    _write_json(out, result)
    append_decision(
        main,
        layer="L7",
        decision=f"w0008 blind selection: 原稿{selection.choice}",
        reason=str(result["rationale"]),
        decided_by=deps.main_roles.author_model,
        refs=[str(out.relative_to(root))],
        experiment_event_id=event["event_id"],
    )
    return result


def _jury_prompt(criteria: str, draft: str) -> str:
    return (
        "次の基準に照らして原稿を0〜10で評点し、短く理由を書いてください。"
        'JSON {"score": 0.0, "rationale": "..."} だけを返してください。\n\n'
        f"## 基準\n{criteria}\n\n## 原稿\n{draft}"
    )


def _score_from_response(text: str) -> float:
    parsed = parse_model_output(text, schema=dict).value or {}
    try:
        return float(parsed.get("score"))
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 0.0


def stage_jury_disclosure(root: Path, deps: RunnerDeps, selection: dict) -> dict:
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("select-jury-disclosure")
    main = main_work(root)
    out = main.dir / "ablation" / "jury_disclosure.json"
    if out.exists():
        if (main.dir / "experiment" / "events.jsonl").exists():
            event = next(
                (
                    row for row in reversed(ExperimentRun.open(main.dir).events())
                    if row["type"] == "jury_reveal"
                ),
                None,
            )
            if event is None:
                raise RuntimeError("select: projection exists without authoritative jury event")
            rows = event["rows"]
            scored = [
                {**row, "mean_score": sum(row["scores"]) / len(row["scores"]) if row["scores"] else 0.0}
                for row in rows
            ]
            argmax = max(scored, key=lambda row: row["mean_score"])["arm"] if scored else None
            return {
                "rows": scored,
                "jury_argmax": argmax,
                "blind_choice_matched_jury_argmax": argmax == selection.get("chosen_arm"),
                "source_event_id": event["event_id"],
                "source_event_hash": event["event_hash"],
            }
        _stderr(f"select: reusing {out}")
        return _read_json(out)

    rows: list[dict] = []
    for arm in ARMS_ORDER:
        work = arm_work(main, arm)
        draft_path = work.draft_path(1)
        criteria_path = work.compositions / "criteria.md"
        if not draft_path.exists() or not criteria_path.exists():
            continue
        prompt = _jury_prompt(criteria_path.read_text(encoding="utf-8"), draft_path.read_text(encoding="utf-8"))
        scores = [_score_from_response(juror(prompt)) for juror in deps.main_roles.jury]
        mean_score = sum(scores) / len(scores) if scores else 0.0
        rows.append({"arm": arm, "scores": scores, "mean_score": mean_score})
    argmax = max(rows, key=lambda row: row["mean_score"])["arm"] if rows else None
    matched = bool(argmax and argmax == selection.get("chosen_arm"))
    run = ExperimentRun.open(main.dir)
    event = run.reveal_jury(rows, decided_by="w0008-runner")
    data = {
        "rows": rows,
        "jury_argmax": argmax,
        "blind_choice_matched_jury_argmax": matched,
        "source_event_id": event["event_id"],
        "source_event_hash": event["event_hash"],
    }
    _write_json(out, data)
    append_decision(
        main,
        layer="L7",
        decision="w0008 jury disclosure: " + ("一致" if matched else "不一致"),
        reason="盲検選択を保存した後で陪審の平均評点を開示し、副観測として一致/不一致だけを記録した。",
        decided_by="w0008-runner",
        refs=[str(out.relative_to(root))],
    )
    return data


def _copy_if_missing(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        _stderr(f"select: reusing {dst}")
        return
    shutil.copy2(src, dst)


def stage_canon_handoff(root: Path, deps: RunnerDeps, selection: dict) -> None:
    main = main_work(root)
    shared = _read_json(main.dir / "ablation" / "shared.json")
    chosen_arm = str(selection["chosen_arm"])
    chosen = arm_work(main, chosen_arm)

    for name in ("criteria.md", "winner.json"):
        src = chosen.compositions / name
        if src.exists():
            _copy_if_missing(src, main.compositions / name)
    for src in sorted(chosen.compositions.glob("proposal_*.json")):
        _copy_if_missing(src, main.compositions / src.name)
    _copy_if_missing(chosen.draft_path(1), main.draft_path(1))
    materials = _load_material_cards(chosen.materials)
    for src in sorted(chosen.materials.glob("*.json")):
        _copy_if_missing(src, main.materials / src.name)

    if main.checkpoint.exists():
        # 既存checkpointは絶対に上書きしない: aleph run がCRITIQUE以降へ進んだ後に
        # select を再実行しても、作品を DRAFT へ巻き戻さない（実費・状態の保護）。
        _stderr(f"select: reusing {main.checkpoint} (never overwritten)")
    else:
        initialize(
            main,
            command_id=f"{main.work_id}:canonical-handoff:{chosen_arm}",
            state=State.DRAFT,
            reason="盲検選択した実験腕を正典作品へ昇格",
            decided_by="w0008-runner",
            payload={
                "audience": shared.get("audience"),
                "niche": shared.get("niche"),
                "materials": materials,
                "canonical_arm": chosen_arm,
            },
        )
    append_decision(
        main,
        layer="L7",
        decision=f"w0008 canon handoff: {chosen_arm}",
        reason="選択腕の構成・原稿・素材を main work へ昇格し、aleph run が CRITIQUE から再開できる DRAFT checkpoint を合成した。",
        decided_by="w0008-runner",
        refs=[str(main.checkpoint.relative_to(root))],
    )

    for arm in ARMS_ORDER:
        work = arm_work(main, arm)
        if arm == chosen_arm:
            _write_json(work.dir / "meta.json", {"canonical": True, "promoted_to": "works/w0008"})
        else:
            _write_json(work.dir / "meta.json", {"canonical": False})

    # Existing w0008 artifacts predate Phase 3 and remain read-only legacy evidence. New runs have
    # durable selection/reveal events and receive the single authoritative promotion event here.
    experiment_dir = main.dir / "experiment"
    if experiment_dir.exists():
        run = ExperimentRun.open(main.dir)
        event_types = [event["type"] for event in run.events()]
    else:
        run = None
        event_types = []
    if run is not None and "blind_selection" in event_types and "jury_reveal" in event_types:
        run.promote(
            chosen_arm,
            work_id=main.work_id,
            command_id=f"{main.work_id}:canonical-handoff:{chosen_arm}",
            decided_by="w0008-runner",
        )


def stage_select(root: Path, deps: RunnerDeps) -> dict:
    tech = stage_tech_floor(root, deps)
    selection = stage_blind_selection(root, deps, tech)
    disclosure = stage_jury_disclosure(root, deps, selection)
    stage_canon_handoff(root, deps, selection)
    return {"tech_floor": tech, "selection": selection, "jury_disclosure": disclosure}


def _format_rate(value: float) -> str:
    return f"{value:.2f}"


def _table_marker_rates(classification: dict, level: str) -> list[str]:
    lines = [
        f"| 腕 | N | 大正昭和 | 裏方 | 箴言調 | prior_attractor | house any |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS_ORDER:
        agg = ((classification.get("aggregates") or {}).get(arm) or {}).get(level, {})
        rates = agg.get("marker_rates", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    arm,
                    str(agg.get("n", 0)),
                    _format_rate(float(rates.get("era_taisho_showa", 0.0))),
                    _format_rate(float(rates.get("backstage_world", 0.0))),
                    _format_rate(float(rates.get("aphoristic_voice", 0.0))),
                    _format_rate(float(rates.get("prior_attractor", 0.0))),
                    _format_rate(float(agg.get("house_style_any_rate", 0.0))),
                ]
            )
            + " |"
        )
    return lines


def _table_cooccurrence(classification: dict, level: str) -> list[str]:
    lines = [
        f"| 腕 | marker-positive N | 共起hits | 共起率 | matched terms |",
        "|---|---:|---:|---:|---|",
    ]
    for arm in ARMS_ORDER:
        co = (((classification.get("aggregates") or {}).get(arm) or {}).get(level, {}) or {}).get("cooccurrence", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    arm,
                    str(co.get("denominator_marker_positive", 0)),
                    str(co.get("hits", 0)),
                    _format_rate(float(co.get("rate", 0.0))),
                    ", ".join(co.get("matched_terms", [])),
                ]
            )
            + " |"
        )
    return lines


def _table_secondary_fidelity(fidelity: dict | None) -> list[str]:
    lines = [
        "| source_id | kind | form_fidelity | cos | iterations | error |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in (fidelity or {}).get("rows", []):
        form_fidelity_value = row.get("form_fidelity")
        cos_value = row.get("cos")
        iterations = row.get("iterations")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("source_id", "")),
                    str(row.get("kind", "")),
                    "" if form_fidelity_value is None else f"{float(form_fidelity_value):.2f}",
                    "" if cos_value is None else f"{float(cos_value):.2f}",
                    "" if iterations is None else str(iterations),
                    str(row.get("error", "")),
                ]
            )
            + " |"
        )
    return lines


def secondary_curtailed(main: Work) -> bool:
    if arm_completed(arm_work(main, "secondary")):
        return False
    for row in _load_jsonl(main.decisions):
        text = f"{row.get('decision', '')} {row.get('reason', '')}"
        if "curtail" in text or "打ち切" in text:
            if "secondary" in text:
                return True
    return False


def _rule_checklist(classification: dict) -> dict[str, bool]:
    l5 = {
        arm: (((classification.get("aggregates") or {}).get(arm) or {}).get("L5", {}) or {}).get(
            "house_style_any_rate", 0.0
        )
        for arm in ARMS_ORDER
    }
    prior_none = (
        ((((classification.get("aggregates") or {}).get("none") or {}).get("L5", {}) or {}).get("marker_rates", {}))
        .get("prior_attractor", 0.0)
    )
    rule1_base = l5.get("aozora", 0.0) >= HIGH_THRESHOLD and l5.get("none", 0.0) <= LOW_THRESHOLD
    rule1_secondary = rule1_base and l5.get("secondary", 0.0) <= LOW_THRESHOLD
    rule2 = all(l5.get(arm, 0.0) >= HIGH_THRESHOLD for arm in ARMS_ORDER)
    rule3 = all(l5.get(arm, 0.0) <= LOW_THRESHOLD for arm in ARMS_ORDER)
    return {
        "rule1_aozora_high_none_low": rule1_base,
        "rule1_secondary_low_clause": rule1_secondary,
        "rule2_all_high": rule2,
        "rule3_all_low": rule3,
        "rule4_mixed_pattern": not (rule1_base or rule2 or rule3),
        "attractor_side_observation_none_high": prior_none >= HIGH_THRESHOLD,
    }


def _load_optional_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return _read_json(path)


def write_report(root: Path, deps: RunnerDeps, *, date_utc: datetime | None = None) -> Path:
    main = main_work(root)
    manifest = load_manifest(main)
    date_utc = date_utc or datetime.now(timezone.utc)
    out = root / "reports" / f"EXP_w0008_ablation_{date_utc.strftime('%Y%m%d')}.md"
    if out.exists():
        _stderr(f"report: reusing {out}")
        return out

    classification = _load_optional_json(main.dir / "ablation" / "classification.json") or {"rows": [], "aggregates": {}}
    covariate = _load_optional_json(main.niche / "covariate_markers.json") or {}
    fidelity = _load_optional_json(main.dir / "ablation" / "secondary" / "fidelity.json")
    tech_floor = _load_optional_json(main.dir / "ablation" / "tech_floor.json") or {}
    selection = _load_optional_json(main.dir / "ablation" / "blind_selection.json") or {}
    disclosure = _load_optional_json(main.dir / "ablation" / "jury_disclosure.json") or {}
    if (main.dir / "experiment" / "events.jsonl").exists():
        events = ExperimentRun.open(main.dir).events()
        selected = next((row for row in reversed(events) if row["type"] == "blind_selection"), None)
        revealed = next((row for row in reversed(events) if row["type"] == "jury_reveal"), None)
        if selected is not None:
            selection = selected
        if revealed is not None:
            rows = [
                {**row, "mean_score": sum(row["scores"]) / len(row["scores"]) if row["scores"] else 0.0}
                for row in revealed["rows"]
            ]
            argmax = max(rows, key=lambda row: row["mean_score"])["arm"] if rows else None
            disclosure = {
                "rows": rows,
                "jury_argmax": argmax,
                "blind_choice_matched_jury_argmax": argmax == selected.get("chosen_arm") if selected else False,
            }
    checklist = _rule_checklist(classification)

    reconciliation_lines: list[str] = []
    if (main.dir / "experiment").exists():
        run = ExperimentRun.open(main.dir)
        budget_state = _load_optional_json(root / "state" / "budget.json") or {}
        provider_path = root / "state" / "provider_charges.jsonl"
        provider_rows = _load_jsonl(provider_path) if provider_path.exists() else []
        reconciliation = run.reconcile(
            calls_path=sorted(main.dir.rglob("calls.jsonl")),
            charge_events=budget_state.get("charge_events", []),
            provider_charges=provider_rows,
        )
        reconciliation_lines = [
            f"- reconciliation: {reconciliation['status']}",
            f"- reconciled calls / ledger / provider: "
            f"${reconciliation['calls']['total_usd']:.4f} / "
            f"${reconciliation['ledger']['total_usd']:.4f} / "
            f"${reconciliation['provider']['total_usd']:.4f}",
            *(f"- reconciliation issue: {issue}" for issue in reconciliation["issues"]),
        ]

    lines = [
        "# EXP w0008 ablation",
        "",
        f"- date UTC: {date_utc.isoformat()}",
        f"- models used: {json.dumps(deps.model_names, ensure_ascii=False, sort_keys=True)}",
        f"- budget: spent ${spent_usd(main):.4f} / cap ${budget_cap(manifest):.4f}",
        *reconciliation_lines,
        "",
        "## Covariate",
        "",
        "niche/report.md の走行前 scout 分類:",
        "",
        "```json",
        json.dumps(covariate, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Marker Rates",
        "",
        "L5 sections は空行区切りの段落を600字以上になるよう貪欲に束ねた疑似セクションである。",
        "",
        "### L4 Proposals",
        "",
        *_table_marker_rates(classification, "L4"),
        "",
        "### L5 Sections",
        "",
        *_table_marker_rates(classification, "L5"),
        "",
        "## Poetics Vocab Co-Occurrence",
        "",
        "家風3標識のいずれかが true の単位だけを分母にし、詩学第0版語彙の部分文字列一致を数えた。",
        "",
        "### L4",
        "",
        *_table_cooccurrence(classification, "L4"),
        "",
        "### L5",
        "",
        *_table_cooccurrence(classification, "L5"),
        "",
        "## Secondary Fidelity",
        "",
        *_table_secondary_fidelity(fidelity),
        "",
        "## Selection",
        "",
        "### Tech Floor",
        "",
        "```json",
        json.dumps(tech_floor, ensure_ascii=False, indent=2),
        "```",
        "",
        "### Blind Selection",
        "",
        f"- choice: {selection.get('choice', '')}",
        f"- chosen_arm: {selection.get('chosen_arm', '')}",
        f"- rationale: {selection.get('rationale', '')}",
        f"- label_mapping: {json.dumps(selection.get('label_mapping', {}), ensure_ascii=False, sort_keys=True)}",
        "",
        "### Jury Disclosure",
        "",
        "```json",
        json.dumps(disclosure, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Pre-Registered Rule Checklist",
        "",
        f"high = rate >= {HIGH_THRESHOLD:.1f}, low = rate <= {LOW_THRESHOLD:.1f}。",
        "",
        "| item | boolean |",
        "|---|---:|",
    ]
    for item, value in checklist.items():
        lines.append(f"| {item} | {str(bool(value)).lower()} |")
    lines.extend(
        [
            "",
            MANDATORY_NON_INDEPENDENCE_SENTENCE,
            "",
        ]
    )
    if secondary_curtailed(main):
        lines.extend([SECONDARY_CURTAILMENT_FALLBACK, ""])
    lines.extend(
        [
            "## Human / Orchestrator Notes",
            "",
            "数値からの物語的判断はここでは保留する。",
            "",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    append_decision(
        main,
        layer="L8",
        decision="w0008 report: ablation report を生成",
        reason="事前登録の報告様式に従い、二水準分類・共起・忠実度・選択順序の記録をまとめた。",
        decided_by="w0008-runner",
        refs=[str(out.relative_to(root))],
    )
    return out


def stage_report(root: Path, deps: RunnerDeps) -> Path:
    return write_report(root, deps)


def _role_model_names(config: Any, role: str) -> list[str]:
    decl = config.models.get("roles", {}).get(role, [])
    decls = decl if isinstance(decl, list) else [decl]
    return [str(item.get("model") or item.get("cli") or item.get("provider") or role) for item in decls if item]


def build_real_deps(root: Path, *, index: str = "state/atlas") -> RunnerDeps:
    from aleph.core.budget import Budget
    from aleph.core.config import load_config
    from aleph.core.llm import CallLogger, Router
    from aleph.explore.corpus import LlamaServerEmbedder
    from aleph.explore.webresearch import search
    from aleph.materia.ai_native import anti_cliche
    from aleph.pipeline import RealDeps

    config = load_config(root)
    main = main_work(root)
    ensure_work_layout(main)
    budget = Budget(config, state_path=root / "state" / "budget.json")

    embedder = None
    embedder_role = config.models.get("roles", {}).get("embedder")
    llamacpp = config.models.get("providers", {}).get("llamacpp")
    if embedder_role and llamacpp:
        embedder = LlamaServerEmbedder(base_url=llamacpp["base_url"], model=embedder_role["model"])

    api_key = config.secrets.get("BRAVE_API_KEY")

    def search_fn(query: str, count: int = 5):
        if not api_key:
            return []
        try:
            return search(query, api_key=api_key, count=count)
        except Exception:
            return []

    def make_router(work: Work) -> Router:
        logger = CallLogger(work.calls, secrets=config.secrets.values())
        return Router(config, logger, budget)

    main_real = RealDeps(
        main,
        make_router(main),
        config=config,
        index_dir=root / index,
        search_fn=search_fn,
        embedder=embedder,
        poetics_dir=root / "poetics",
    )

    def make_roles(work: Work) -> RoleRuntime:
        real = RealDeps(
            work,
            make_router(work),
            config=config,
            index_dir=root / index,
            search_fn=search_fn,
            embedder=embedder,
            poetics_dir=root / "poetics",
        )
        return RoleRuntime(
            author=real._author,
            scout=real._scout,
            jury=real._jury(),
            reader_llm=real._reader_llm,
            author_model="/".join(_role_model_names(config, "author_primary")) or "author_primary",
            scout_model="/".join(_role_model_names(config, "scout")) or "scout",
            jury_models=_role_model_names(config, "critic_jury"),
            set_phase=lambda phase: setattr(real, "_phase", phase),
        )

    main_roles = RoleRuntime(
        author=main_real._author,
        scout=main_real._scout,
        jury=main_real._jury(),
        reader_llm=main_real._reader_llm,
        author_model="/".join(_role_model_names(config, "author_primary")) or "author_primary",
        scout_model="/".join(_role_model_names(config, "scout")) or "scout",
        jury_models=_role_model_names(config, "critic_jury"),
        set_phase=lambda phase: setattr(main_real, "_phase", phase),
    )

    return RunnerDeps(
        choose_intent=main_real.choose_intent,
        explore=main_real.explore,
        main_roles=main_roles,
        arm_roles=make_roles,
        embedder=embedder,
        poetics=main_real._poetics(),
        index_dir=root / index,
        secondary_path=root / "corpus" / "secondary" / "works.jsonl",
        anti_cliche_fn=anti_cliche,
        model_names={
            "author_primary": main_roles.author_model,
            "scout": main_roles.scout_model,
            "critic_jury": list(main_roles.jury_models),
            "embedder": _role_model_names(config, "embedder"),
        },
    )


def run_stage(root: Path, deps: RunnerDeps, *, stage: str, arm_filter: str | None = None) -> Any:
    if stage == "prepare":
        return stage_prepare(root, deps)
    if stage == "arms":
        return stage_arms(root, deps, arm_filter=arm_filter)
    if stage == "classify":
        return stage_classify(root, deps)
    if stage == "select":
        return stage_select(root, deps)
    if stage == "report":
        return stage_report(root, deps)
    if stage == "all":
        shared = stage_prepare(root, deps)
        arms = stage_arms(root, deps, arm_filter=arm_filter)
        classification = stage_classify(root, deps)
        selection = stage_select(root, deps)
        report = stage_report(root, deps)
        return {"prepare": shared, "arms": arms, "classification": classification, "selection": selection, "report": str(report)}
    raise ValueError(f"unknown stage: {stage}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, default="all")
    parser.add_argument("--arm", choices=ARMS_ORDER, default=None, help="arms stage の対象腕")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--index", default="state/atlas")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    deps = build_real_deps(args.root, index=args.index)
    try:
        run_stage(args.root, deps, stage=args.stage, arm_filter=args.arm)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"run_w0008: stage {args.stage} complete", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
