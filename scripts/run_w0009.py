"""w0009 L2 era intervention runner.

事前登録: `designs/phase4-w0009-l2-era-intervention.md`。
The experiment-specific logic stays local to this runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aleph.core.artifacts import Work  # noqa: E402
from aleph.core.evaluation import EvaluationPacket  # noqa: E402
from aleph.core.experiment import BlindCandidate, ExperimentRun  # noqa: E402
from aleph.core.loop import Checkpoint, State  # noqa: E402
from aleph.core.model_output import parse_model_output  # noqa: E402
from aleph.core.transition_commit import initialize  # noqa: E402
from aleph.core.work_snapshot import WorkReader  # noqa: E402
from aleph.draft.write import pipeline_to_draft  # noqa: E402

WORK_ID = "w0009"
EXPERIMENT_ID = "exp-w0009-l2-era-pin"
ARMS = ("era_pinned", "era_unpinned")
GENERATION_ORDER = ("era_unpinned", "era_pinned")
STAGES = ("prepare", "arms", "select", "classify", "promote", "canonical", "report", "all")
SEMANTIC_KERNEL = (
    "離れた二つの島で、互いに一度も会わない観測者たちが、渡り鳥の到着と不在だけを記した"
    "季節ごとの通信を交換し、その欠落から一つの共同体の輪郭を組み上げる。形式は三人称複数焦点の"
    "書簡群とし、演劇・上演・稽古場・楽屋・帳場・質屋・職人仕事を意味核に含めない。"
)
NICHE_VARIANTS = {
    "era_pinned": "時代属性: 大正末期〜昭和初期の日本",
    "era_unpinned": "時代属性は指定しない。現代化を強制せず、時代語・年代・制度を禁止しない。",
}
BUDGET_ENVELOPE = {
    "prepare": 0.75,
    "era_unpinned_L4_L5": 2.5,
    "era_pinned_L4_L5": 2.5,
    "blind_select": 0.75,
    "jury_reveal": 1.5,
    "canonical_L6_L7": 3.5,
    "failure_reserve": 0.5,
}
FIXED_CONDITIONS = {
    "author_model": "claude-fable-5",
    "intent": "main workで一度だけ自律選択し両腕で共有",
    "materials": "両腕とも空配列",
    "poetics": "実走時の詩学第1版の同一bytes",
    "composition": "3案・進化2世代",
    "draft_segmentation_min_chars": 600,
    "classifier_prompt_version": "w0009-house-style-v1",
}
MARKER_KEYS = (
    "era_taisho_showa",
    "backstage_world",
    "aphoristic_voice",
    "quotation_transform",
    "perspective_deviation",
)
MANDATORY_NON_INDEPENDENCE_WARNING = (
    "L4の3案とL5の疑似セクションは独立標本ではない。統計的検定、有意差、p値として解釈しない。"
)


class ManifestError(RuntimeError):
    """w0009 manifest violates preregistered fixed conditions."""


@dataclass(frozen=True)
class RoleRuntime:
    author: Callable[[str], str]
    scout: Callable[[str], str]
    jury: Sequence[Callable[[str], str]] = field(default_factory=tuple)
    author_model: str = "author"
    scout_model: str = "scout"
    jury_models: Sequence[str] = field(default_factory=tuple)
    set_phase: Callable[[str], None] | None = None


@dataclass
class RunnerDeps:
    choose_intent: Callable[[Work], str]
    main_roles: RoleRuntime
    arm_roles: Callable[[Work], RoleRuntime]
    poetics: str
    atlas_identity: dict[str, Any] | None
    config_hash: str
    pipeline_to_draft: Callable[..., Path] | None = None
    api_remaining_usd: float | None = None
    run_canonical: Callable[[Work], State] | None = None

    def __post_init__(self) -> None:
        if self.pipeline_to_draft is None:
            self.pipeline_to_draft = pipeline_to_draft


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_decision(
    work: Work,
    *,
    layer: str,
    decision: str,
    reason: str,
    decided_by: str,
    refs: Sequence[str] = (),
    **extra: Any,
) -> None:
    record = {
        "ts": _now_iso(),
        "layer": layer,
        "decision": decision,
        "reason": reason,
        "decided_by": decided_by,
        "refs": list(refs),
    }
    record.update(extra)
    work.append_decision(record)


def ensure_work_layout(work: Work, seed: dict[str, Any] | None = None) -> None:
    work.dir.mkdir(parents=True, exist_ok=True)
    for directory in (work.niche, work.materials, work.compositions, work.drafts, work.reviews, work.final):
        directory.mkdir(parents=True, exist_ok=True)
    if seed is not None and not work.seed.exists():
        _write_json(work.seed, seed)
    work.decisions.touch(exist_ok=True)
    work.calls.touch(exist_ok=True)


def main_work(root: Path) -> Work:
    return Work(Path(root) / "works", WORK_ID)


def arm_work(main: Work, arm: str) -> Work:
    return Work(main.dir, arm)


def _manifest(main: Work) -> dict[str, Any]:
    if not main.seed.exists():
        raise ManifestError(f"prepare: missing seed.json: {main.seed}")
    try:
        seed = _read_json(main.seed)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"prepare: invalid seed.json: {exc}") from exc
    experiment = seed.get("experiment") if isinstance(seed, dict) else None
    if not isinstance(experiment, dict):
        raise ManifestError("prepare: seed.json lacks experiment manifest")
    return seed


def _validate_manifest(seed: dict[str, Any]) -> None:
    exp = seed["experiment"]
    if exp.get("id") != EXPERIMENT_ID:
        raise ManifestError("prepare: unexpected experiment id")
    if exp.get("semantic_kernel") != SEMANTIC_KERNEL:
        raise ManifestError("prepare: semantic-kernel drift")
    if exp.get("niche_variants") != NICHE_VARIANTS:
        unpinned = str((exp.get("niche_variants") or {}).get("era_unpinned", ""))
        if "大正" in unpinned or "昭和初期" in unpinned:
            raise ManifestError("prepare: era_unpinned era leakage")
        raise ManifestError("prepare: niche variant drift")
    arms = exp.get("arms")
    order = exp.get("generation_order")
    if set(arms or []) != set(ARMS) or arms != ["era_pinned", "era_unpinned"]:
        raise ManifestError("prepare: invalid arm declaration")
    if order != list(GENERATION_ORDER):
        raise ManifestError("prepare: invalid generation order")
    envelope = exp.get("budget_envelope")
    if envelope != BUDGET_ENVELOPE or exp.get("budget_cap_usd") != 12.0:
        raise ManifestError("prepare: missing full budget envelope")
    if abs(sum(float(value) for value in envelope.values()) - float(exp["budget_cap_usd"])) > 1e-9:
        raise ManifestError("prepare: budget envelope drift")
    if exp.get("fixed_conditions") != FIXED_CONDITIONS:
        raise ManifestError("prepare: fixed-condition drift")


def _runtime_hashes(main: Work, deps: RunnerDeps) -> dict[str, Any]:
    if not isinstance(deps.atlas_identity, dict) or not deps.atlas_identity:
        raise ManifestError("prepare: absent atlas identity")
    return {
        "seed_hash": _hash_file(main.seed),
        "poetics_hash": _hash_text(deps.poetics),
        "config_hash": deps.config_hash,
        "atlas_identity": deps.atlas_identity,
    }


def _variant_payload(exp: Mapping[str, Any], arm: str) -> dict[str, Any]:
    return {
        "arm": arm,
        "semantic_kernel": exp["semantic_kernel"],
        "variant_line": exp["niche_variants"][arm],
        "materials": [],
    }


def _ensure_arm_inputs(
    main: Work,
    *,
    exp: dict[str, Any],
    hashes: Mapping[str, Any],
) -> None:
    run = ExperimentRun.open(main.dir)
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        arm_seed = {
            "work_id": f"{WORK_ID}-{arm}",
            "parent": WORK_ID,
            "arm": arm,
            "arm_identity": {"experiment_id": run.experiment_id, "arm": arm},
            "experiment": exp,
        }
        ensure_work_layout(work, seed=arm_seed)
        payload = _variant_payload(exp, arm)
        payload_path = work.niche / "payload.json"
        if payload_path.exists() and _read_json(payload_path) != payload:
            raise ManifestError(f"prepare: arm input drift for {arm}")
        if _read_json(work.seed) != arm_seed:
            raise ManifestError(f"prepare: arm input drift for {arm}")
        _write_json(payload_path, payload)
        report = payload["semantic_kernel"] + "\n" + payload["variant_line"] + "\n"
        report_path = work.niche / "report.md"
        if report_path.exists() and report_path.read_text(encoding="utf-8") != report:
            raise ManifestError(f"prepare: arm input drift for {arm}")
        report_path.write_text(report, encoding="utf-8")
        colophon = {
            "poetics_version": 1,
            "poetics_hash": hashes["poetics_hash"],
            "corpus_id": hashes["atlas_identity"].get(
                "corpus_id", hashes["atlas_identity"].get("index")
            ),
            "atlas_version": hashes["atlas_identity"].get(
                "atlas_version", hashes["atlas_identity"].get("version")
            ),
        }
        colophon_path = work.dir / "colophon.json"
        if colophon_path.exists() and _read_json(colophon_path) != colophon:
            raise ManifestError(f"prepare: arm input drift for {arm}")
        _write_json(colophon_path, colophon)


def _validate_arm_inputs(main: Work, exp: dict[str, Any], hashes: Mapping[str, Any]) -> None:
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        expected_seed = {
            "work_id": f"{WORK_ID}-{arm}",
            "parent": WORK_ID,
            "arm": arm,
            "arm_identity": {"experiment_id": EXPERIMENT_ID, "arm": arm},
            "experiment": exp,
        }
        expected_colophon = {
            "poetics_version": 1,
            "poetics_hash": hashes["poetics_hash"],
            "corpus_id": hashes["atlas_identity"].get(
                "corpus_id", hashes["atlas_identity"].get("index")
            ),
            "atlas_version": hashes["atlas_identity"].get(
                "atlas_version", hashes["atlas_identity"].get("version")
            ),
        }
        try:
            valid = (
                _read_json(work.seed) == expected_seed
                and _read_json(work.niche / "payload.json") == _variant_payload(exp, arm)
                and _read_json(work.dir / "colophon.json") == expected_colophon
            )
        except (OSError, json.JSONDecodeError):
            valid = False
        if not valid:
            raise ManifestError(f"prepare: arm input drift for {arm}")


def stage_prepare(root: Path, deps: RunnerDeps) -> dict[str, Any]:
    main = main_work(root)
    ensure_work_layout(main)
    seed = _manifest(main)
    _validate_manifest(seed)
    expected_author = str(seed["experiment"]["fixed_conditions"]["author_model"])
    if deps.main_roles.author_model != expected_author:
        raise ManifestError(
            "prepare: author model substitution "
            f"(expected={expected_author}, actual={deps.main_roles.author_model})"
        )
    hashes = _runtime_hashes(main, deps)
    run = ExperimentRun.open(main.dir)
    shared_path = main.dir / "experiment" / "w0009_shared.json"
    if shared_path.exists():
        shared = _read_json(shared_path)
        for key in ("seed_hash", "poetics_hash", "config_hash", "atlas_identity"):
            if shared.get(key) != hashes[key]:
                raise ManifestError(f"prepare: {key} drift on resume")
        _ensure_arm_inputs(main, exp=seed["experiment"], hashes=hashes)
        return shared

    if deps.api_remaining_usd is not None and deps.api_remaining_usd < float(seed["experiment"]["budget_cap_usd"]):
        raise ManifestError(
            "prepare: full API envelope is unavailable "
            f"(remaining={deps.api_remaining_usd:.6f}, required={seed['experiment']['budget_cap_usd']:.2f})"
        )
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("prepare")
    intent = deps.choose_intent(main)
    main.intent.write_text(str(intent), encoding="utf-8")
    shared = {
        "experiment_id": run.experiment_id,
        "intent": str(intent),
        "generation_order": list(GENERATION_ORDER),
        "poetics": deps.poetics,
        **hashes,
    }
    _write_json(shared_path, shared)
    exp = seed["experiment"]
    _ensure_arm_inputs(main, exp=exp, hashes=hashes)
    _append_decision(
        main,
        layer="L2",
        decision="w0009 prepare: fixed L2 era intervention payloads",
        reason="共有意味核と一行だけ異なる時代属性payloadを2腕へ保存した。",
        decided_by="w0009-runner",
        refs=[str(shared_path.relative_to(Path(root)))],
    )
    return shared


def _shared(main: Work) -> dict[str, Any]:
    path = main.dir / "experiment" / "w0009_shared.json"
    if not path.exists():
        raise RuntimeError("missing w0009 shared context; run prepare first")
    return _read_json(path)


def _validate_runtime_hashes(main: Work, deps: RunnerDeps) -> dict[str, Any]:
    shared = _shared(main)
    current = _runtime_hashes(main, deps)
    for key in ("seed_hash", "poetics_hash", "config_hash", "atlas_identity"):
        if shared.get(key) != current[key]:
            raise ManifestError(f"prepare: {key} drift on resume")
    return shared


def _validated_packet(work: Work) -> EvaluationPacket:
    recorded_path = work.reviews / "packet_hashes.json"
    if not recorded_path.exists():
        raise RuntimeError(f"packet hash record is missing for {work.work_id}")
    recorded = _read_json(recorded_path)
    packet = EvaluationPacket.for_draft(WorkReader(work.dir).snapshot(), 1)
    if (
        recorded.get("packet_hash") != packet.hash
        or recorded.get("effective_constraints_hash") != packet.effective_constraints_hash
    ):
        raise RuntimeError(f"packet hash mismatch for {work.work_id}")
    return packet


def _criteria_constraints(seed: dict[str, Any]) -> str:
    constraints = (seed.get("experiment") or {}).get("constraints") or []
    return "\n".join(str(row.get("text", "")) for row in constraints if isinstance(row, dict))


def stage_arms(root: Path, deps: RunnerDeps) -> list[dict[str, Any]]:
    main = main_work(root)
    ensure_work_layout(main)
    seed = _manifest(main)
    _validate_manifest(seed)
    shared = _validate_runtime_hashes(main, deps)
    _validate_arm_inputs(main, seed["experiment"], shared)
    run = ExperimentRun.open(main.dir)
    results: list[dict[str, Any]] = []
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        ensure_work_layout(work)
        run.register_arm(arm, work_id=f"{WORK_ID}-{arm}")
        roles = deps.arm_roles(work)
        if roles.set_phase is not None:
            roles.set_phase(f"{arm}_L4_L5")
        draft = work.draft_path(1)
        if not draft.exists():
            deps.pipeline_to_draft(
                work,
                _read_json(work.niche / "payload.json"),
                shared["intent"],
                roles.author,
                roles.scout,
                generations=2,
                poetics=shared["poetics"],
                materials=[],
                criteria_constraints=_criteria_constraints(seed),
            )
        packet = EvaluationPacket.for_draft(WorkReader(work.dir).snapshot(), 1)
        _write_json(
            work.reviews / "packet_hashes.json",
            {
                "packet_hash": packet.hash,
                "effective_constraints_hash": packet.effective_constraints_hash,
            },
        )
        results.append({"arm": arm, "draft": str(draft), "packet_hash": packet.hash})
    return results


def _tech_floor_prompt(text: str) -> str:
    return 'JSON {"pass": true|false, "issues": ["..."]} だけを返してください。\n\n' + text


def _technical_floor(scout: Callable[[str], str], text: str) -> dict[str, Any]:
    parsed = parse_model_output(scout(_tech_floor_prompt(text)), schema={"pass": bool, "issues": [str]})
    if parsed.ok:
        return {"pass": parsed.value["pass"], "issues": list(parsed.value["issues"])}
    return {"pass": False, "issues": list(parsed.warnings)}


def stage_select(root: Path, deps: RunnerDeps) -> dict[str, Any]:
    main = main_work(root)
    _validate_runtime_hashes(main, deps)
    for arm in GENERATION_ORDER:
        _validated_packet(arm_work(main, arm))
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("blind_select")
    run = ExperimentRun.open(main.dir)
    events = run.events()
    selection_path = main.dir / "experiment" / "blind_selection.json"
    jury_path = main.dir / "experiment" / "jury_reveal.json"
    selection_events = [event for event in events if event["type"] == "blind_selection"]
    jury_events = [event for event in events if event["type"] == "jury_reveal"]
    if jury_events:
        if not selection_path.exists() or not jury_path.exists():
            raise RuntimeError("select: authoritative events lack readable projections")
        return {"selection": _read_json(selection_path), "jury": _read_json(jury_path)["rows"]}
    if selection_events:
        event = selection_events[-1]
        selection = {
            "choice": event["choice"],
            "chosen_arm": event["chosen_arm"],
            "rationale": event["rationale"],
            "event_id": event["event_id"],
        }
        if selection_path.exists() and _read_json(selection_path) != selection:
            raise RuntimeError("select: blind selection projection disagrees with event")
        _write_json(selection_path, selection)
        jury_rows = _jury_reveal(root, deps)
        return {"selection": selection, "jury": jury_rows}
    tech: dict[str, dict[str, Any]] = {}
    candidates: dict[str, dict[str, Any]] = {}
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        draft = work.draft_path(1)
        if not draft.exists():
            raise RuntimeError(f"select: missing draft for {arm}")
        text = draft.read_text(encoding="utf-8")
        roles = deps.arm_roles(work)
        if roles.set_phase is not None:
            roles.set_phase("blind_select")
        tech[arm] = _technical_floor(roles.scout, text)
        candidates[arm] = {"text": text, "technical_floor": tech[arm]}

    def selector(view: Sequence[BlindCandidate]) -> Mapping[str, Any]:
        lines = [
            "あなたはこの作品の著者です。中立ラベルの候補から1本を選んでください。",
            "提示情報は本文と技術床だけです。",
            'JSON {"choice":"A|B","rationale":"..."} だけを返してください。',
        ]
        for candidate in view:
            lines.extend(
                [
                    f"## 原稿{candidate.label}",
                    "technical_floor: " + json.dumps(candidate.technical_floor, ensure_ascii=False, sort_keys=True),
                    candidate.text,
                ]
            )
        parsed = parse_model_output(deps.main_roles.author("\n\n".join(lines)), schema={"choice": str, "rationale": str})
        if not parsed.ok:
            raise RuntimeError("select: author selector parse failed")
        return parsed.value

    selection = run.select_blind(candidates, selector=selector, decided_by=deps.main_roles.author_model)
    _write_json(
        selection_path,
        {
            "choice": selection.choice,
            "chosen_arm": selection.chosen_arm,
            "rationale": selection.rationale,
            "event_id": selection.event_id,
        },
    )
    jury_rows = _jury_reveal(root, deps)
    return {"selection": _read_json(selection_path), "jury": jury_rows}


def _jury_prompt(packet: EvaluationPacket, draft_text: str) -> str:
    return (
        packet.render_for("L6")
        + '\n\nJSON {"score": 0.0, "rationale": "..."} だけを返してください。\n\n'
        + draft_text
    )


def _recover_unprojected_jury_calls(main: Work, deps: RunnerDeps) -> list[dict[str, Any]] | None:
    """Disclose completed jury calls without regenerating lost parsed projections."""
    recovered: list[dict[str, Any]] = []
    found = False
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        roles = deps.arm_roles(work)
        calls = [row for row in _load_jsonl(work.calls) if row.get("phase") == "jury_reveal"]
        if calls:
            found = True
        if not found and not calls:
            continue
        expected = len(roles.jury)
        complete = (
            expected > 0
            and len(calls) == expected
            and all(
                row.get("billing_status") == "charged"
                and row.get("call_id")
                and row.get("charge_id")
                and row.get("response_hash")
                for row in calls
            )
        )
        if not complete:
            raise RuntimeError(
                f"select: {arm} has partial unprojected jury calls; regeneration forbidden"
            )
        packet = _validated_packet(work)
        recovered.append(
            {
                "arm": arm,
                "scores": [],
                "rationales": [],
                "status": "INCOMPLETE_PARSE",
                "call_evidence": [
                    {
                        key: row.get(key)
                        for key in ("call_id", "charge_id", "response_hash", "model")
                    }
                    for row in calls
                ],
                "packet_hash": packet.hash,
                "effective_constraints_hash": packet.effective_constraints_hash,
            }
        )
    if not found:
        return None
    if len(recovered) != len(GENERATION_ORDER):
        raise RuntimeError("select: jury calls are incomplete across arms; regeneration forbidden")
    return recovered


def _jury_reveal(root: Path, deps: RunnerDeps) -> list[dict[str, Any]]:
    main = main_work(root)
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("jury_reveal")
    run = ExperimentRun.open(main.dir)
    out_path = main.dir / "experiment" / "jury_reveal.json"
    existing = [event for event in run.events() if event["type"] == "jury_reveal"]
    if existing:
        if not out_path.exists():
            raise RuntimeError("select: jury event lacks readable projection")
        return _read_json(out_path)["rows"]
    recovered = _recover_unprojected_jury_calls(main, deps)
    if recovered is not None:
        event = run.reveal_jury(recovered, decided_by="w0009-jury-incomplete-parse")
        rows = [{**row, "reveal_event_id": event["event_id"]} for row in recovered]
        _write_json(out_path, {"rows": rows})
        return rows
    rows: list[dict[str, Any]] = []
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        roles = deps.arm_roles(work)
        if roles.set_phase is not None:
            roles.set_phase("jury_reveal")
        packet = _validated_packet(work)
        draft_text = work.draft_path(1).read_text(encoding="utf-8")
        scores: list[float] = []
        rationales: list[str] = []
        for juror in roles.jury:
            parsed = parse_model_output(juror(_jury_prompt(packet, draft_text)), schema={"score": float, "rationale": str})
            if not parsed.ok:
                raise RuntimeError("select: jury parse failed")
            scores.append(float(parsed.value["score"]))
            rationales.append(str(parsed.value["rationale"]))
        if not scores:
            scores = [0.0]
        rows.append(
            {
                "arm": arm,
                "scores": scores,
                "rationales": rationales,
                "packet_hash": packet.hash,
                "effective_constraints_hash": packet.effective_constraints_hash,
            }
        )
    event = run.reveal_jury(rows, decided_by="w0009-jury")
    out_rows = [{**row, "reveal_event_id": event["event_id"]} for row in rows]
    _write_json(out_path, {"rows": out_rows})
    return out_rows


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


def _classify_prompt(text: str) -> str:
    return (
        "w0009-house-style-v1: 次のテキストを5標識で分類してください。\n"
        'JSON {"era_taisho_showa":true|false,"backstage_world":true|false,'
        '"aphoristic_voice":true|false,"quotation_transform":true|false,'
        '"perspective_deviation":true|false} だけを返してください。\n\n'
        + text
    )


def classify_text(scout: Callable[[str], str], text: str) -> dict[str, Any]:
    output = parse_model_output(scout(_classify_prompt(text)), schema={key: bool for key in MARKER_KEYS})
    if not output.ok:
        return {"classified": False, "markers": None, "warnings": list(output.warnings)}
    return {"classified": True, "markers": {key: bool(output.value[key]) for key in MARKER_KEYS}, "warnings": []}


def aggregate_classification(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for arm in GENERATION_ORDER:
        data[arm] = {}
        for level in ("L4", "L5"):
            group = [row for row in rows if row.get("arm") == arm and row.get("level") == level]
            classified = [row for row in group if row.get("classified")]
            rates = {
                key: (
                    sum(1 for row in classified if (row.get("markers") or {}).get(key)) / len(classified)
                    if classified
                    else None
                )
                for key in MARKER_KEYS
            }
            data[arm][level] = {
                "observed": len(group),
                "classified": len(classified),
                "unclassified": len(group) - len(classified),
                "marker_rates": rates,
            }
    return data


def stage_classify(root: Path, deps: RunnerDeps) -> dict[str, Any]:
    main = main_work(root)
    _validate_runtime_hashes(main, deps)
    if not any(event["type"] == "jury_reveal" for event in ExperimentRun.open(main.dir).events()):
        raise RuntimeError("classify: jury reveal must be durable before classification")
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("failure_reserve")
    classification_path = main.dir / "experiment" / "classification.json"
    if classification_path.exists():
        return _read_json(classification_path)
    rows: list[dict[str, Any]] = []
    for arm in GENERATION_ORDER:
        work = arm_work(main, arm)
        roles = deps.arm_roles(work)
        if roles.set_phase is not None:
            roles.set_phase("failure_reserve")
        for path in sorted(work.compositions.glob("proposal_*.json"))[:3]:
            result = classify_text(roles.scout, path.read_text(encoding="utf-8"))
            rows.append({"arm": arm, "level": "L4", "unit_id": path.name, **result})
        for index, text in enumerate(draft_sections(work.draft_path(1).read_text(encoding="utf-8")), start=1):
            result = classify_text(roles.scout, text)
            rows.append({"arm": arm, "level": "L5", "unit_id": f"section_{index}", "text_chars": len(text), **result})
    data = {"rows": rows, "aggregates": aggregate_classification(rows)}
    _write_json(classification_path, data)
    return data


def _era_level(arm_data: Mapping[str, Any]) -> str:
    l4 = arm_data["L4"]
    l5 = arm_data["L5"]
    if l4["classified"] < 3 or l5["classified"] < 2:
        return "inconclusive"
    l4_rate = l4["marker_rates"]["era_taisho_showa"]
    l5_rate = l5["marker_rates"]["era_taisho_showa"]
    if l4_rate >= 2 / 3 and l5_rate >= 0.50:
        return "high"
    if l4_rate <= 1 / 3 and l5_rate <= 0.20:
        return "low"
    return "mixed"


def decision_outcome(aggregates: Mapping[str, Any]) -> str:
    control = _era_level(aggregates["era_pinned"])
    intervention = _era_level(aggregates["era_unpinned"])
    if "inconclusive" in {control, intervention}:
        return "INCONCLUSIVE_CLASSIFICATION"
    if control == "high" and intervention == "low":
        return "RULE_1_DIRECTIONAL_SUPPORT"
    if control == "high" and intervention == "high":
        return "RULE_2_PIN_NOT_NECESSARY_HERE"
    if control == "low" and intervention == "low":
        return "RULE_3_CONTROL_DID_NOT_PROPAGATE"
    return "RULE_4_LEVEL_SPLIT_OR_MIXED"


def stage_promote(root: Path, deps: RunnerDeps) -> dict[str, Any]:
    main = main_work(root)
    _validate_runtime_hashes(main, deps)
    if not (main.dir / "experiment" / "classification.json").exists():
        raise RuntimeError("promote: classification must be durable before promotion")
    run = ExperimentRun.open(main.dir)
    selection = _read_json(main.dir / "experiment" / "blind_selection.json")
    arm = str(selection["chosen_arm"])
    event = run.promote(arm, work_id=WORK_ID, command_id=f"w0009-promote-{arm}", decided_by="w0009-runner")
    selected = arm_work(main, arm)
    for source_dir, target_dir in (
        (selected.compositions, main.compositions),
        (selected.drafts, main.drafts),
        (selected.materials, main.materials),
    ):
        target_dir.mkdir(parents=True, exist_ok=True)
        for path in source_dir.iterdir():
            if path.is_file():
                shutil.copy2(path, target_dir / path.name)
    payload = {
        "audience": _shared(main)["intent"],
        "niche": _read_json(selected.niche / "payload.json"),
        "materials": [],
        "canonical_arm": arm,
    }
    try:
        Checkpoint.load(main.dir)
    except FileNotFoundError:
        initialize(
            main,
            command_id=f"w0009-initialize-{arm}",
            state=State.DRAFT,
            reason="w0009 selected arm handoff to canonical continuation",
            decided_by="w0009-runner",
            payload=payload,
        )
    _write_json(selected.dir / "meta.json", {"canonical": True, "promoted_to": f"works/{WORK_ID}"})
    for other in ARMS:
        if other != arm:
            _write_json(arm_work(main, other).dir / "meta.json", {"canonical": False})
    return event


def stage_canonical(root: Path, deps: RunnerDeps) -> State:
    main = main_work(root)
    _validate_runtime_hashes(main, deps)
    run = ExperimentRun.open(main.dir)
    if not any(event["type"] == "canonical_promotion" for event in run.events()):
        raise RuntimeError("canonical: selected arm must be promoted first")
    if not (main.dir / "experiment" / "classification.json").exists():
        raise RuntimeError("canonical: classification must be durable before L6-L7")
    if deps.run_canonical is None:
        raise RuntimeError("canonical: L6-L7 adapter is unavailable")
    if deps.main_roles.set_phase is not None:
        deps.main_roles.set_phase("canonical_L6_L7")
    return deps.run_canonical(main)


def _phase_costs(main: Work) -> dict[str, float]:
    costs = {phase: 0.0 for phase in BUDGET_ENVELOPE}
    for path in main.dir.rglob("calls.jsonl"):
        for row in _load_jsonl(path):
            phase = str(row.get("phase", ""))
            # The first real prepare call was preserved with RealDeps' generic L1 label before
            # experiment-phase pinning was repaired. Its deviation is durable; report it inside
            # the preregistered envelope instead of silently dropping actual spend.
            if (
                phase == "L1"
                and row.get("experiment_id") == EXPERIMENT_ID
            ):
                phase = "prepare"
            if phase in costs and type(row.get("cost_usd")) in (int, float):
                costs[phase] += float(row["cost_usd"])
    return costs


def _phase_budget_report(costs: Mapping[str, float]) -> dict[str, Any]:
    overruns = {
        phase: {"spent": float(costs.get(phase, 0.0)), "cap": cap}
        for phase, cap in BUDGET_ENVELOPE.items()
        if float(costs.get(phase, 0.0)) > cap
    }
    return {
        "budget_envelope": dict(BUDGET_ENVELOPE),
        "phase_costs": {phase: float(costs.get(phase, 0.0)) for phase in BUDGET_ENVELOPE},
        "phase_overruns": overruns,
        "total_spent": sum(float(costs.get(phase, 0.0)) for phase in BUDGET_ENVELOPE),
        "total_cap": sum(BUDGET_ENVELOPE.values()),
    }


def _jury_summary(main: Work) -> dict[str, Any]:
    disclosure = _read_json(main.dir / "experiment" / "jury_reveal.json")
    rows: list[dict[str, Any]] = []
    for row in disclosure["rows"]:
        scores = [float(score) for score in row.get("scores", [])]
        rows.append(
            {
                **row,
                "mean_score": sum(scores) / len(scores) if scores else None,
                "disagreement": max(scores) - min(scores) if scores else None,
            }
        )
    scored = [row for row in rows if row["mean_score"] is not None]
    jury_argmax = max(scored, key=lambda row: row["mean_score"])["arm"] if scored else None
    selection = _read_json(main.dir / "experiment" / "blind_selection.json")
    return {
        "rows": rows,
        "jury_argmax": jury_argmax,
        "blind_choice_matched_jury_argmax": selection["chosen_arm"] == jury_argmax,
    }


def write_report(root: Path, deps: RunnerDeps, *, date_utc: datetime | None = None) -> Path:
    main = main_work(root)
    classification = _read_json(main.dir / "experiment" / "classification.json")
    outcome = decision_outcome(classification["aggregates"])
    run = ExperimentRun.open(main.dir)
    budget_state = Path(root) / "state" / "budget.json"
    charge_events: list[dict[str, Any]] = []
    if budget_state.exists():
        state = _read_json(budget_state)
        if isinstance(state.get("charge_events"), list):
            charge_events = [row for row in state["charge_events"] if isinstance(row, dict)]
    reconciliation = run.reconcile(
        calls_path=list(main.dir.rglob("calls.jsonl")),
        charge_events=charge_events,
        provider_charges=[],
    )
    packet_rows: dict[str, Any] = {}
    for arm in GENERATION_ORDER:
        path = arm_work(main, arm).reviews / "packet_hashes.json"
        if path.exists():
            packet_rows[arm] = _read_json(path)
    deviations = [event for event in run.events() if event["type"] == "deviation"]
    shared = _shared(main)
    phase_budget = _phase_budget_report(_phase_costs(main))
    jury = _jury_summary(main)
    lines = [
        "# w0009 report",
        f"date_utc: {(date_utc or datetime.now(timezone.utc)).date().isoformat()}",
        f"decision: {outcome}",
        MANDATORY_NON_INDEPENDENCE_WARNING,
        "",
        "## input hashes",
        f"seed_hash: {shared['seed_hash']}",
        f"poetics_hash: {shared['poetics_hash']}",
        f"config_hash: {shared['config_hash']}",
        f"atlas_identity: {json.dumps(shared['atlas_identity'], ensure_ascii=False, sort_keys=True)}",
        "",
        "## packet/effective hashes",
        json.dumps(packet_rows, ensure_ascii=False, sort_keys=True, indent=2),
        "",
        "## classification",
        json.dumps(classification["aggregates"], ensure_ascii=False, sort_keys=True, indent=2),
        "",
        "## jury disclosure",
        json.dumps(jury, ensure_ascii=False, sort_keys=True, indent=2),
        "",
        "## deviations",
        json.dumps(deviations, ensure_ascii=False, sort_keys=True, indent=2),
        "",
        "## costs",
        json.dumps(phase_budget, ensure_ascii=False, sort_keys=True, indent=2),
        f"reconciliation_status: {reconciliation['status']}",
    ]
    if reconciliation["status"] == "matched":
        lines.append("provider statements matched")
    else:
        lines.append("provider statements absent or unreconciled; matched is not claimed")
    path = main.dir / "experiment" / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_stage(root: Path, deps: RunnerDeps, *, stage: str = "all") -> Any:
    root = Path(root)
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    if stage == "prepare":
        return stage_prepare(root, deps)
    if stage == "arms":
        return stage_arms(root, deps)
    if stage == "select":
        return stage_select(root, deps)
    if stage == "classify":
        return stage_classify(root, deps)
    if stage == "promote":
        return stage_promote(root, deps)
    if stage == "canonical":
        return stage_canonical(root, deps)
    if stage == "report":
        return write_report(root, deps)
    stage_prepare(root, deps)
    stage_arms(root, deps)
    stage_select(root, deps)
    stage_classify(root, deps)
    stage_promote(root, deps)
    return write_report(root, deps)


def _role_model_names(config: Any, role: str) -> list[str]:
    declaration = config.models.get("roles", {}).get(role, [])
    rows = declaration if isinstance(declaration, list) else [declaration]
    return [
        str(row.get("model") or row.get("cli") or row.get("provider") or role)
        for row in rows
        if isinstance(row, dict)
    ]


def build_real_deps(root: Path, *, index: str = "state/atlas") -> RunnerDeps:
    """Construct production adapters only after the complete API envelope is available."""
    from aleph.core.budget import Budget
    from aleph.core.config import load_config
    from aleph.core.llm import CallLogger, Router
    from aleph.explore.corpus import LlamaServerEmbedder
    from aleph.explore.webresearch import search
    from aleph.pipeline import RealDeps, run_work

    root = Path(root)
    config = load_config(root)
    budget = Budget(config, state_path=root / "state" / "budget.json")
    api_status = budget.status()["api"]
    remaining = float(api_status["limit"]) - float(api_status["spent"])
    shared_path = root / "works" / WORK_ID / "experiment" / "w0009_shared.json"
    if not shared_path.exists() and remaining < sum(BUDGET_ENVELOPE.values()):
        raise ManifestError(
            "prepare: full API envelope is unavailable "
            f"(remaining={remaining:.6f}, required={sum(BUDGET_ENVELOPE.values()):.2f})"
        )

    main = main_work(root)
    ensure_work_layout(main)
    index_dir = root / index
    atlas_files = [index_dir / "manifest.json", index_dir / "atlas_meta.json"]
    if not all(path.exists() for path in atlas_files):
        raise ManifestError("prepare: absent atlas identity")
    atlas_identity = {
        "index": str(Path(index)),
        "manifest_hash": _hash_file(atlas_files[0]),
        "atlas_meta_hash": _hash_file(atlas_files[1]),
    }
    config_hash = _canonical_hash(
        {
            "models": config.models,
            "budgets": config.budgets,
            "policies": config.policies,
            "publish": config.publish,
        }
    )

    embedder = None
    embedder_role = config.models.get("roles", {}).get("embedder")
    llamacpp = config.models.get("providers", {}).get("llamacpp")
    if embedder_role and llamacpp:
        embedder = LlamaServerEmbedder(
            base_url=llamacpp["base_url"], model=embedder_role["model"]
        )
    api_key = config.secrets.get("BRAVE_API_KEY")

    def search_fn(query: str, count: int = 5):
        if not api_key:
            return []
        try:
            return search(query, api_key=api_key, count=count)
        except Exception:
            return []

    def make_router(work: Work) -> Router:
        return Router(
            config,
            CallLogger(work.calls, secrets=config.secrets.values()),
            budget,
        )

    def make_real(work: Work) -> RealDeps:
        return RealDeps(
            work,
            make_router(work),
            config=config,
            index_dir=index_dir,
            search_fn=search_fn,
            embedder=embedder,
            poetics_dir=root / "poetics",
        )

    main_real = make_real(main)

    def roles_for(real: RealDeps) -> RoleRuntime:
        return RoleRuntime(
            author=real._author,
            scout=real._scout,
            jury=real._jury(),
            author_model="/".join(_role_model_names(config, "author_primary")) or "author_primary",
            scout_model="/".join(_role_model_names(config, "scout")) or "scout",
            jury_models=_role_model_names(config, "critic_jury"),
            set_phase=real.set_experiment_phase,
        )

    class CanonicalL6L7Deps:
        """Expose only canonical continuation; intentionally omit the L8 reflection hook."""

        critique_and_revise = main_real.critique_and_revise
        decide_stop = main_real.decide_stop
        decide_publication = main_real.decide_publication
        annotate_failure = main_real.annotate_failure
        credits = main_real.credits
        intended_reader_models = main_real.intended_reader_models

    def run_canonical(work: Work) -> State:
        main_real.set_experiment_phase("canonical_L6_L7")
        return run_work(work, CanonicalL6L7Deps(), decided_by="w0009-canonical-L6-L7")

    return RunnerDeps(
        choose_intent=main_real.choose_intent,
        main_roles=roles_for(main_real),
        arm_roles=lambda work: roles_for(make_real(work)),
        poetics=main_real._poetics(),
        atlas_identity=atlas_identity,
        config_hash=config_hash,
        api_remaining_usd=remaining,
        run_canonical=run_canonical,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=STAGES, default="all")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--index", default="state/atlas")
    args = parser.parse_args(argv)
    try:
        deps = build_real_deps(args.root, index=args.index)
        run_stage(args.root, deps, stage=args.stage)
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"run_w0009: stage {args.stage} complete", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
