"""L2 空きニッチ探索（PLAN §4.3）— 疎領域、空きセル、Web照合を統合する."""
from __future__ import annotations

import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from aleph.core.model_output import parse_model_output
from aleph.explore.atlas import load_failures


@dataclass(frozen=True)
class VacancyClass:
    vacancy_type: str
    depth: str
    rationale: str
    excluded: bool
    ai_native_candidate: bool


def classify_vacancy(text: str) -> VacancyClass:
    """scout応答中の最初のJSONオブジェクトから空きの三分類を読む."""
    parsed = parse_model_output(text, schema=dict).value
    if parsed is None:
        return VacancyClass("未着手型", "中", text, False, False)
    vacancy_type = str(parsed.get("vacancy_type", "未着手型"))
    if vacancy_type not in {"不可能型", "未着手型", "空虚型"}:
        vacancy_type = "未着手型"
    depth = str(parsed.get("depth", "中"))
    rationale = str(parsed.get("rationale", text))
    return VacancyClass(
        vacancy_type=vacancy_type,
        depth=depth,
        rationale=rationale,
        excluded=vacancy_type == "空虚型",
        ai_native_candidate=vacancy_type == "不可能型",
    )


def rank_niches(niches: list[dict]) -> list[dict]:
    """除外候補を落とし、新奇性・到達可能性・解釈可能性の調和平均で並べる."""
    ranked: list[dict] = []
    for niche in niches:
        if niche.get("excluded"):
            continue
        values = [
            max(0.0, float(niche.get("novelty", 0.0))),
            max(0.0, float(niche.get("reachability", 0.0))),
            max(0.0, float(niche.get("interpretability", 0.0))),
        ]
        score = 0.0 if any(value == 0.0 for value in values) else 3.0 / sum(1.0 / v for v in values)
        item = dict(niche)
        item["score"] = score
        ranked.append(item)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)


def _normalized_inverse(values: list[float]) -> list[float]:
    inverse = np.asarray([1.0 / (1.0 + max(0.0, value)) for value in values], dtype=float)
    if inverse.size == 0:
        return []
    spread = float(inverse.max() - inverse.min())
    if spread == 0.0:
        return [1.0] * len(values)
    return [float(value) for value in (inverse - inverse.min()) / spread]


def _attach_measured_novelty(candidates: list[dict]) -> None:
    distances: list[float] = []
    for candidate in candidates:
        try:
            distances.append(float(candidate["atlas_nearest_dist"]))
        except (KeyError, TypeError, ValueError):
            continue
    sorted_distances = sorted(distances)
    for candidate in candidates:
        try:
            distance = float(candidate["atlas_nearest_dist"])
        except (KeyError, TypeError, ValueError):
            candidate["measured_novelty"] = None
            continue
        rank = int(np.searchsorted(sorted_distances, distance, side="right")) - 1
        candidate["measured_novelty"] = rank / max(1, len(sorted_distances) - 1)


def _failure_context(atlas) -> str:
    directory = getattr(atlas, "index_dir", None)
    if directory is None:
        return ""
    failures = load_failures(directory)
    if not failures:
        return ""
    return "\n過去の失敗座標:\n" + json.dumps(failures, ensure_ascii=False)


def _sparse_candidates(atlas, scout: Callable[[str], str], top_n: int, context: str) -> list[dict]:
    regions = atlas.sparse_regions(max(top_n * 3, top_n))
    if not regions:
        return []
    by_work: dict[str, dict] = {}
    for region in regions:
        previous = by_work.get(region["work_id"])
        if previous is None or float(region["knn_dist"]) > float(previous["knn_dist"]):
            by_work[region["work_id"]] = region

    distances = [float(region["knn_dist"]) for region in regions]
    sorted_distances = sorted(distances)
    reachability = _normalized_inverse([float(region["knn_dist"]) for region in by_work.values()])
    chunk_by_id = {
        chunk.get("chunk_id"): chunk
        for chunk in getattr(atlas, "chunks", [])
    }
    candidates: list[dict] = []
    for number, (region, reachable) in enumerate(zip(by_work.values(), reachability, strict=True), start=1):
        text = region.get("text") or chunk_by_id.get(region["chunk_id"], {}).get("text", "")
        prompt = (
            "次の疎なテキスト近傍に、どんな作品の空隙が可能か記述してください。"
            'JSON {"description": "..."} で返してください。\n'
            f"作品: {region['title']}\nテキスト:\n{text[:4000]}{context}"
        )
        response = scout(prompt)
        parsed = parse_model_output(response, schema=dict).value or {}
        description = str(
            parsed.get("description")
            or parsed.get("rationale")
            or response.strip()
            or f"{region['title']}近傍の疎領域"
        )
        rank = int(np.searchsorted(sorted_distances, float(region["knn_dist"]), side="right")) - 1
        novelty = rank / max(1, len(sorted_distances) - 1)
        candidates.append(
            {
                "id": f"sparse-{number:03d}",
                "kind": "sparse",
                "description": description,
                "work_id": region["work_id"],
                "chunk_id": region["chunk_id"],
                "nearest_cluster": region.get("nearest_cluster", -1),
                "atlas_nearest_dist": float(region["knn_dist"]),
                "novelty": float(novelty),
                "reachability": reachable,
            }
        )
    return candidates


def _cluster_entries(atlas) -> list[dict]:
    entries = getattr(atlas, "cluster_meta", None)
    if entries is not None:
        return sorted(list(entries), key=lambda entry: entry.get("size", 0), reverse=True)
    return sorted(
        list(getattr(atlas, "meta", {}).get("clusters", [])),
        key=lambda entry: entry.get("size", 0),
        reverse=True,
    )


def _persisted_cluster_labels(atlas) -> list[dict]:
    """永続化済みのクラスタ属性注釈があれば読む（PLAN_CHANGELOG 0.7.18 問4・C-1）.

    atlas.index_dir を持たない偽装アトラス（テスト等）や、まだ annotate_clusters が
    一度も実行されていない場合は空リストを返し、呼び出し側は従来どおり scout への
    その場ラベリングにフォールバックする。
    """
    from aleph.explore.atlas import load_cluster_annotations

    index_dir = getattr(atlas, "index_dir", None)
    if index_dir is None:
        return []
    annotations = load_cluster_annotations(index_dir)
    return [record["attributes"] for record in annotations if record.get("attributes")]


def _cell_candidates(atlas, scout: Callable[[str], str], top_n: int, context: str) -> list[dict]:
    chunk_by_id = {
        chunk.get("chunk_id"): chunk
        for chunk in getattr(atlas, "chunks", [])
    }
    labelled: list[dict] = _persisted_cluster_labels(atlas)
    if not labelled:
        # 永続化済み注釈が無ければ従来どおりその場でラベリングする（後方互換）。
        # 実行の都度scoutを呼ぶこの経路は、annotate_clusters()で一度永続化すれば
        # 以後は使われなくなる（sol §4.1: 同じラベリングの再計算・非永続化の解消）。
        for cluster in _cluster_entries(atlas)[:8]:
            excerpts = [
                chunk_by_id.get(chunk_id, {}).get("text", "")[:1500]
                for chunk_id in cluster.get("exemplars", [])
            ]
            response = scout(
                "クラスタ代表例を主題・形式・視点・時代で属性ラベリングしてください。"
                'JSON {"theme":"...","form":"...","viewpoint":"...","era":"..."} だけを返してください。\n'
                + "\n---\n".join(excerpts)
                + context
            )
            parsed = parse_model_output(response, schema=dict).value
            if parsed and all(parsed.get(axis) for axis in ("theme", "form", "viewpoint", "era")):
                labelled.append(parsed)
    if len(labelled) < 2:
        return []

    axes = ("theme", "form", "viewpoint", "era")
    values = {axis: list(dict.fromkeys(str(item[axis]) for item in labelled)) for axis in axes}
    occupied = {tuple(str(item[axis]) for axis in axes) for item in labelled}
    candidates: list[dict] = []
    for combination in itertools.product(*(values[axis] for axis in axes)):
        if combination in occupied:
            continue
        description = (
            f"主題「{combination[0]}」×形式「{combination[1]}」×"
            f"視点「{combination[2]}」×時代「{combination[3]}」"
        )
        candidates.append(
            {
                "id": f"cell-{len(candidates) + 1:03d}",
                "kind": "empty_cell",
                "description": description,
                "attributes": dict(zip(axes, combination, strict=True)),
                "novelty": 1.0,
                "measured_novelty": None,
                "reachability": 0.5,
            }
        )
        if len(candidates) >= max(top_n * 2, top_n):
            break
    return candidates


def find_niches(
    atlas,
    scout: Callable[[str], str],
    *,
    top_n: int = 20,
    web_checker: Callable[[dict], object] | None = None,
) -> list[dict]:
    """疎領域と属性表の空きセルを生成・分類・照合し、上位候補を返す."""
    context = _failure_context(atlas)
    candidates = _sparse_candidates(atlas, scout, top_n, context)
    candidates.extend(_cell_candidates(atlas, scout, top_n, context))
    _attach_measured_novelty(candidates)

    classified: list[dict] = []
    for candidate in candidates:
        response = scout(
            "候補ニッチを空きの三分類で評価してください。深さと解釈可能性も必須です。"
            'JSON {"vacancy_type":"不可能型|未着手型|空虚型","depth":"高|中|低",'
            '"rationale":"...","interpretability":0.0} で返してください。\n'
            f"候補ID: {candidate['id']}\n候補: {candidate['description']}{context}"
        )
        vacancy = classify_vacancy(response)
        parsed = parse_model_output(response, schema=dict).value or {}
        try:
            interpretability = float(parsed.get("interpretability", 0.5))
        except (TypeError, ValueError):
            interpretability = 0.5
        item = {
            **candidate,
            "vacancy_type": vacancy.vacancy_type,
            "depth": vacancy.depth,
            "rationale": vacancy.rationale,
            "interpretability": min(1.0, max(0.0, interpretability)),
            "excluded": vacancy.excluded,
            "ai_native_candidate": vacancy.ai_native_candidate,
            "web_check": "not_checked",
        }
        if web_checker is not None:
            try:
                result = web_checker(item)
                if isinstance(result, dict):
                    web_excluded = bool(result.get("excluded", False))
                    prior_examples = result.get("prior_examples", [])
                    web_rationale = result.get("rationale", "")
                else:
                    web_excluded = bool(getattr(result, "excluded", False))
                    prior_examples = getattr(result, "prior_examples", [])
                    web_rationale = getattr(result, "rationale", "")
                item["excluded"] = item["excluded"] or web_excluded
                item["prior_examples"] = prior_examples
                item["web_check"] = web_rationale or ("excluded" if web_excluded else "clear")
            except Exception as e:
                print(f"{type(e).__name__}", file=sys.stderr)
                item["web_check"] = "error"
        classified.append(item)
    return rank_niches(classified)[:top_n]


def report(niches: list[dict], out_path: str | Path, top_n: int = 20) -> None:
    """上位ニッチを監査可能なMarkdownレポートへ書き出す."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ALEPH ニッチ探索レポート",
        "",
        "ニッチは発見のヒューリスティックであって価値関数ではない（PLAN §4.3）。",
        "",
    ]
    for niche in niches[:top_n]:
        measured = niche.get("measured_novelty")
        measured_text = "N/A" if measured is None else f"{float(measured):.3f}"
        lines.extend(
            [
                f"## {niche.get('id', '')}: {niche.get('description', '')}",
                "",
                f"- 三分類: {niche.get('vacancy_type', '未分類')}",
                f"- 深さ: {niche.get('depth', '不明')}",
                f"- 理由: {niche.get('rationale', '')}",
                (
                    "- スコア: "
                    f"新奇性={float(niche.get('novelty', 0.0)):.3f}, "
                    f"到達可能性={float(niche.get('reachability', 0.0)):.3f}, "
                    f"解釈可能性={float(niche.get('interpretability', 0.0)):.3f}"
                ),
                f"- 実測新奇性(percentile): {measured_text}",
                f"- Web照合: {niche.get('web_check', 'not_checked')}",
                "",
            ]
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
