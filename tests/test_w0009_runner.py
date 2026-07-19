from __future__ import annotations

import json
from pathlib import Path

import pytest

from aleph.core.artifacts import Work
from aleph.core.experiment import ExperimentError, ExperimentRun
from aleph.core.loop import Checkpoint, State
from scripts import run_w0009 as runner

pytestmark = pytest.mark.m6


def seed_data() -> dict:
    return {
        "hint": "w0009 test",
        "experiment": {
            "id": "exp-w0009-l2-era-pin",
            "version": 1,
            "hypothesis": "era pin changes house style",
            "intervention": "era_unpinned intervention",
            "control": "era_pinned control",
            "observations": ["classification"],
            "budget_cap_usd": 12.0,
            "budget_envelope": {
                "prepare": 0.75,
                "era_unpinned_L4_L5": 2.5,
                "era_pinned_L4_L5": 2.5,
                "blind_select": 0.75,
                "jury_reveal": 1.5,
                "canonical_L6_L7": 3.5,
                "failure_reserve": 0.5,
            },
            "arms": ["era_pinned", "era_unpinned"],
            "generation_order": ["era_unpinned", "era_pinned"],
            "blind": {"seed": 9009},
            "semantic_kernel": runner.SEMANTIC_KERNEL,
            "niche_variants": dict(runner.NICHE_VARIANTS),
            "fixed_conditions": {
                "author_model": "claude-fable-5",
                "intent": "main workで一度だけ自律選択し両腕で共有",
                "materials": "両腕とも空配列",
                "poetics": "実走時の詩学第1版の同一bytes",
                "composition": "3案・進化2世代",
                "draft_segmentation_min_chars": 600,
                "classifier_prompt_version": "w0009-house-style-v1",
            },
            "constraints": [
                {
                    "id": "shared-semantic-form",
                    "text": "意味核、三人称複数焦点、書簡群の形式を両腕で同一に保つ。",
                    "source": "test",
                    "scope": ["L4", "L5", "L6", "L7"],
                    "priority": 10,
                }
            ],
            "amendments": [],
        },
    }


def write_seed(root: Path, seed: dict | None = None) -> None:
    work = root / "works" / runner.WORK_ID
    work.mkdir(parents=True, exist_ok=True)
    (work / "seed.json").write_text(
        json.dumps(seed or seed_data(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class Calls:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return "{}"


def deps(*, author: Calls | None = None, scout: Calls | None = None) -> runner.RunnerDeps:
    author_calls = author or Calls()
    scout_calls = scout or Calls()
    return runner.RunnerDeps(
        choose_intent=lambda work: "共有intent",
        main_roles=runner.RoleRuntime(
            author=author_calls,
            scout=scout_calls,
            jury=(),
            author_model="claude-fable-5",
            scout_model="scout-test",
        ),
        arm_roles=lambda work: runner.RoleRuntime(
            author=author_calls,
            scout=scout_calls,
            jury=(),
            author_model="claude-fable-5",
            scout_model="scout-test",
        ),
        poetics="詩学v1",
        atlas_identity={"index": "test-atlas", "version": "1"},
        config_hash="config-hash",
        pipeline_to_draft=fake_pipeline_to_draft,
    )


def test_prepare_rejects_era_unpinned_leaking_control_pin_before_adapters(tmp_path):
    seed = seed_data()
    seed["experiment"]["niche_variants"]["era_unpinned"] = "時代属性: 大正末期〜昭和初期の日本"
    write_seed(tmp_path, seed)
    author = Calls()
    scout = Calls()

    with pytest.raises(runner.ManifestError, match="era_unpinned.*era leakage"):
        runner.run_stage(tmp_path, deps(author=author, scout=scout), stage="prepare")

    assert author.calls == []
    assert scout.calls == []


def test_phase_costs_attributes_preserved_initial_l1_call_to_prepare(tmp_path):
    """phase固定前に保存されたprepareのL1 callも全phase実費から脱落させない."""
    work = Work(tmp_path / "works", runner.WORK_ID)
    work.create(seed_data())
    work.calls.write_text(
        json.dumps(
            {
                "phase": "L1",
                "experiment_id": "exp-w0009-l2-era-pin",
                "cost_usd": 0.08793,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    costs = runner._phase_costs(work)

    assert costs["prepare"] == pytest.approx(0.08793)


def test_phase_budget_report_exposes_aggregate_spend_and_cap():
    """三面照合がphase値の再加算に依存せず、全phase包絡を直接比較できる."""
    costs = {phase: 0.0 for phase in runner.BUDGET_ENVELOPE}
    costs["prepare"] = 0.25
    costs["canonical_L6_L7"] = 1.5

    report = runner._phase_budget_report(costs)

    assert report["total_spent"] == pytest.approx(1.75)
    assert report["total_cap"] == pytest.approx(12.0)


def fake_pipeline_to_draft(
    work,
    niche,
    audience,
    author,
    critic,
    *,
    generations=2,
    poetics="",
    materials=None,
    criteria_constraints="",
):
    work.compositions.mkdir(parents=True, exist_ok=True)
    work.drafts.mkdir(parents=True, exist_ok=True)
    (work.compositions / "criteria.md").write_text("criteria", encoding="utf-8")
    for index in range(1, 4):
        (work.compositions / f"proposal_{index}.json").write_text(
            json.dumps({"index": index, "arm": work.work_id, "niche": niche}, ensure_ascii=False),
            encoding="utf-8",
        )
    section = "本文。季節の通信が届く。" * 260
    work.draft_path(1).write_text(section + "\n\n" + section, encoding="utf-8")
    return work.draft_path(1)


def test_experiment_manifest_preserves_optional_budget_envelope_and_legacy_without_it(tmp_path):
    work = Work(tmp_path / "works", "with-envelope")
    work.create(seed_data())
    run = ExperimentRun.open(work.dir)
    assert run.manifest["budget_envelope"] == runner.BUDGET_ENVELOPE

    legacy_seed = seed_data()
    legacy_seed["experiment"].pop("budget_envelope")
    legacy = Work(tmp_path / "works", "legacy")
    legacy.create(legacy_seed)
    assert "budget_envelope" not in ExperimentRun.open(legacy.dir).manifest

    bad = seed_data()
    bad["experiment"]["budget_envelope"]["prepare"] = "0.75"
    broken = Work(tmp_path / "works", "bad-envelope")
    broken.create(bad)
    with pytest.raises(ExperimentError, match="allocations"):
        ExperimentRun.open(broken.dir)

    for key, value, match in (
        ("prepare", True, "allocations"),
        ("", 0.75, "phase keys"),
    ):
        malformed = seed_data()
        malformed["experiment"]["budget_envelope"].pop("prepare")
        malformed["experiment"]["budget_envelope"][key] = value
        target = Work(tmp_path / "works", f"bad-{match}-{key or 'empty'}")
        target.create(malformed)
        with pytest.raises(ExperimentError, match=match):
            ExperimentRun.open(target.dir)

    wrong_sum = seed_data()
    wrong_sum["experiment"]["budget_envelope"]["prepare"] = 0.76
    target = Work(tmp_path / "works", "bad-sum")
    target.create(wrong_sum)
    with pytest.raises(ExperimentError, match="sum"):
        ExperimentRun.open(target.dir)


def test_prepare_writes_deterministic_payloads_and_fails_on_resume_hash_drift(tmp_path):
    write_seed(tmp_path)
    first = runner.run_stage(tmp_path, deps(), stage="prepare")
    main = tmp_path / "works" / runner.WORK_ID
    payloads = {
        arm: json.loads((main / arm / "niche" / "payload.json").read_text(encoding="utf-8"))
        for arm in runner.GENERATION_ORDER
    }

    assert payloads["era_unpinned"]["semantic_kernel"] == payloads["era_pinned"]["semantic_kernel"]
    assert payloads["era_unpinned"]["semantic_kernel"] == runner.SEMANTIC_KERNEL
    assert payloads["era_unpinned"]["variant_line"] != payloads["era_pinned"]["variant_line"]
    assert first["poetics_hash"]

    with pytest.raises(runner.ManifestError, match="config_hash drift"):
        runner.run_stage(
            tmp_path,
            runner.RunnerDeps(
                choose_intent=lambda work: "new",
                main_roles=deps().main_roles,
                arm_roles=deps().arm_roles,
                poetics="詩学v1",
                atlas_identity={"index": "test-atlas", "version": "1"},
                config_hash="different",
                pipeline_to_draft=fake_pipeline_to_draft,
            ),
            stage="prepare",
        )


def test_prepare_requires_atlas_identity_before_adapter_calls(tmp_path):
    write_seed(tmp_path)
    author = Calls()
    bad_deps = deps(author=author)
    bad_deps.atlas_identity = None

    with pytest.raises(runner.ManifestError, match="atlas identity"):
        runner.run_stage(tmp_path, bad_deps, stage="prepare")

    assert author.calls == []


def test_prepare_requires_full_api_envelope_before_intent_call(tmp_path):
    write_seed(tmp_path)
    author = Calls()
    blocked = deps(author=author)
    blocked.api_remaining_usd = 11.99

    with pytest.raises(runner.ManifestError, match="full API envelope"):
        runner.run_stage(tmp_path, blocked, stage="prepare")

    assert author.calls == []


def test_prepare_rejects_author_model_substitution_before_adapter_calls(tmp_path):
    write_seed(tmp_path)
    author = Calls()
    scout = Calls()
    substituted = deps(author=author, scout=scout)
    substituted.main_roles = runner.RoleRuntime(
        author=author,
        scout=scout,
        jury=(),
        author_model="claude-opus-4-8",
        scout_model="scout-test",
    )

    with pytest.raises(runner.ManifestError, match="author model substitution"):
        runner.run_stage(tmp_path, substituted, stage="prepare")

    assert author.calls == []
    assert scout.calls == []


def test_prepare_rejects_fixed_condition_drift_before_adapter_calls(tmp_path):
    seed = seed_data()
    seed["experiment"]["fixed_conditions"]["draft_segmentation_min_chars"] = 601
    write_seed(tmp_path, seed)
    author = Calls()

    with pytest.raises(runner.ManifestError, match="fixed-condition drift"):
        runner.run_stage(tmp_path, deps(author=author), stage="prepare")

    assert author.calls == []


def test_arms_follow_generation_order_and_fixed_inputs(tmp_path):
    write_seed(tmp_path)
    runner.run_stage(tmp_path, deps(), stage="prepare")
    calls: list[dict] = []

    def pipeline(work, niche, audience, author, critic, **kwargs):
        calls.append(
            {
                "work": work.work_id,
                "niche": niche,
                "audience": audience,
                **kwargs,
            }
        )
        return fake_pipeline_to_draft(work, niche, audience, author, critic, **kwargs)

    d = deps()
    d.pipeline_to_draft = pipeline
    results = runner.run_stage(tmp_path, d, stage="arms")

    assert [row["work"] for row in calls] == list(runner.GENERATION_ORDER)
    assert [row["arm"] for row in results] == list(runner.GENERATION_ORDER)
    assert all(row["materials"] == [] for row in calls)
    assert {row["poetics"] for row in calls} == {"詩学v1"}
    arm_seeds = [
        json.loads((tmp_path / "works" / runner.WORK_ID / arm / "seed.json").read_text())
        for arm in runner.GENERATION_ORDER
    ]
    assert all(row["experiment"]["id"] == runner.EXPERIMENT_ID for row in arm_seeds)
    assert [row["arm_identity"]["arm"] for row in arm_seeds] == list(runner.GENERATION_ORDER)
    packet_hashes = [
        json.loads((tmp_path / "works" / runner.WORK_ID / arm / "reviews" / "packet_hashes.json").read_text())
        for arm in runner.GENERATION_ORDER
    ]
    assert all(row["packet_hash"] and row["effective_constraints_hash"] for row in packet_hashes)


def test_arms_revalidate_runtime_hashes_before_pipeline_calls(tmp_path):
    write_seed(tmp_path)
    runner.run_stage(tmp_path, deps(), stage="prepare")
    calls: list[str] = []

    def pipeline(*args, **kwargs):
        calls.append("called")
        return fake_pipeline_to_draft(*args, **kwargs)

    changed = deps()
    changed.config_hash = "changed-after-prepare"
    changed.pipeline_to_draft = pipeline

    with pytest.raises(runner.ManifestError, match="config_hash drift"):
        runner.run_stage(tmp_path, changed, stage="arms")

    assert calls == []


def test_arms_reject_arm_payload_tamper_before_pipeline_calls(tmp_path):
    write_seed(tmp_path)
    runner.run_stage(tmp_path, deps(), stage="prepare")
    payload_path = tmp_path / "works" / runner.WORK_ID / "era_unpinned" / "niche" / "payload.json"
    payload = json.loads(payload_path.read_text())
    payload["semantic_kernel"] += "tampered"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    calls: list[str] = []

    def pipeline(*args, **kwargs):
        calls.append("called")
        return fake_pipeline_to_draft(*args, **kwargs)

    changed = deps()
    changed.pipeline_to_draft = pipeline
    with pytest.raises(runner.ManifestError, match="arm input drift"):
        runner.run_stage(tmp_path, changed, stage="arms")

    assert calls == []


def test_select_rejects_saved_packet_hash_mismatch_before_adapter_calls(tmp_path):
    d = deps()
    run_until_arms(tmp_path, d)
    packet_path = tmp_path / "works" / runner.WORK_ID / "era_unpinned" / "reviews" / "packet_hashes.json"
    packet = json.loads(packet_path.read_text())
    packet["packet_hash"] = "0" * 64
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    author = Calls()
    scout = Calls()
    changed = deps(author=author, scout=scout)

    with pytest.raises(RuntimeError, match="packet hash mismatch"):
        runner.run_stage(tmp_path, changed, stage="select")

    assert author.calls == []
    assert scout.calls == []


def run_until_arms(root: Path, d: runner.RunnerDeps) -> None:
    write_seed(root)
    runner.run_stage(root, d, stage="prepare")
    runner.run_stage(root, d, stage="arms")


def selector_deps(author_prompts: list[str], scout_outputs: list[str] | None = None) -> runner.RunnerDeps:
    outputs = scout_outputs or []

    def author(prompt: str) -> str:
        author_prompts.append(prompt)
        return json.dumps({"choice": "A", "rationale": "picked A"}, ensure_ascii=False)

    def scout(prompt: str) -> str:
        if "w0009-house-style-v1" in prompt and outputs:
            return outputs.pop(0)
        return json.dumps({"pass": True, "issues": ["ok"]}, ensure_ascii=False)

    def juror(prompt: str) -> str:
        assert "Evaluation packet:" in prompt
        return json.dumps({"score": 7.0, "rationale": "ok"}, ensure_ascii=False)

    d = deps(author=Calls(), scout=Calls())
    d.main_roles = runner.RoleRuntime(
        author=author,
        scout=scout,
        jury=(juror, juror),
        author_model="claude-fable-5",
        scout_model="scout-test",
    )
    d.arm_roles = lambda _work: d.main_roles
    return d


def test_select_is_blind_then_reveal_classify_and_promote_once(tmp_path):
    prompts: list[str] = []
    d = selector_deps(prompts)
    run_until_arms(tmp_path, d)

    result = runner.run_stage(tmp_path, d, stage="select")
    prompt = prompts[0]
    assert "era_pinned" not in prompt
    assert "era_unpinned" not in prompt
    assert "classification" not in prompt.lower()
    assert "jury" not in prompt.lower()
    assert "cost" not in prompt.lower()
    assert result["jury"]
    events = ExperimentRun.open(tmp_path / "works" / runner.WORK_ID).events()
    assert [event["type"] for event in events if event["type"] in {"blind_selection", "jury_reveal"}] == [
        "blind_selection",
        "jury_reveal",
    ]
    prompt_count = len(prompts)
    assert runner.run_stage(tmp_path, d, stage="select") == result
    assert len(prompts) == prompt_count

    with pytest.raises(RuntimeError, match="classification must be durable"):
        runner.run_stage(tmp_path, d, stage="promote")

    classification = runner.run_stage(tmp_path, d, stage="classify")
    assert classification["rows"]
    promotion = runner.run_stage(tmp_path, d, stage="promote")
    assert promotion["type"] == "canonical_promotion"
    assert Checkpoint.load(tmp_path / "works" / runner.WORK_ID).state == State.DRAFT
    with pytest.raises(Exception, match="promotion"):
        ExperimentRun.open(tmp_path / "works" / runner.WORK_ID).promote(
            "era_pinned" if promotion["arm"] == "era_unpinned" else "era_unpinned",
            work_id=runner.WORK_ID,
            command_id="other",
            decided_by="test",
        )


def test_select_recovers_completed_unprojected_jury_calls_without_regeneration(tmp_path):
    prompts: list[str] = []
    d = selector_deps(prompts)
    run_until_arms(tmp_path, d)
    main = tmp_path / "works" / runner.WORK_ID
    run = ExperimentRun.open(main)
    selection = run.select_blind(
        {
            "era_unpinned": {"text": "A", "technical_floor": {"pass": True}},
            "era_pinned": {"text": "B", "technical_floor": {"pass": True}},
        },
        selector=lambda rows: {"choice": "A", "rationale": "fixed"},
        decided_by="claude-fable-5",
    )
    (main / "experiment" / "blind_selection.json").write_text(
        json.dumps(
            {
                "choice": selection.choice,
                "chosen_arm": selection.chosen_arm,
                "rationale": selection.rationale,
                "event_id": selection.event_id,
            }
        ),
        encoding="utf-8",
    )
    for arm in runner.GENERATION_ORDER:
        calls = main / arm / "calls.jsonl"
        calls.write_text(
            "".join(
                json.dumps(
                    {
                        "phase": "jury_reveal",
                        "call_id": f"{arm}-{index}",
                        "charge_id": f"charge-{arm}-{index}",
                        "response_hash": str(index) * 64,
                        "model": f"juror-{index}",
                        "billing_status": "charged",
                    }
                )
                + "\n"
                for index in range(2)
            ),
            encoding="utf-8",
        )

    def forbidden_juror(_prompt: str) -> str:
        pytest.fail("completed jury calls must not be regenerated")

    d.main_roles = runner.RoleRuntime(
        author=d.main_roles.author,
        scout=d.main_roles.scout,
        jury=(forbidden_juror, forbidden_juror),
        author_model=d.main_roles.author_model,
        scout_model=d.main_roles.scout_model,
    )
    d.arm_roles = lambda _work: d.main_roles

    recovered = runner.run_stage(tmp_path, d, stage="select")

    assert all(row["status"] == "INCOMPLETE_PARSE" for row in recovered["jury"])
    assert all(len(row["call_evidence"]) == 2 for row in recovered["jury"])
    assert ExperimentRun.open(main).events()[-1]["type"] == "jury_reveal"


def marker_json(value: bool) -> str:
    return json.dumps({key: value for key in runner.MARKER_KEYS}, ensure_ascii=False)


def aggregate_for(control: tuple[int, int], intervention: tuple[int, int]) -> dict:
    rows = []
    for arm, counts in (("era_pinned", control), ("era_unpinned", intervention)):
        l4_true, l5_true = counts
        for index in range(3):
            rows.append(
                {
                    "arm": arm,
                    "level": "L4",
                    "classified": True,
                    "markers": {key: (key == "era_taisho_showa" and index < l4_true) for key in runner.MARKER_KEYS},
                }
            )
        for index in range(5):
            rows.append(
                {
                    "arm": arm,
                    "level": "L5",
                    "classified": True,
                    "markers": {key: (key == "era_taisho_showa" and index < l5_true) for key in runner.MARKER_KEYS},
                }
            )
    return runner.aggregate_classification(rows)


@pytest.mark.parametrize(
    ("control", "intervention", "outcome"),
    [
        ((3, 3), (1, 1), "RULE_1_DIRECTIONAL_SUPPORT"),
        ((3, 3), (3, 3), "RULE_2_PIN_NOT_NECESSARY_HERE"),
        ((1, 1), (1, 1), "RULE_3_CONTROL_DID_NOT_PROPAGATE"),
        ((2, 1), (1, 1), "RULE_4_LEVEL_SPLIT_OR_MIXED"),
    ],
)
def test_decision_rules_cover_four_classified_outcomes(control, intervention, outcome):
    assert runner.decision_outcome(aggregate_for(control, intervention)) == outcome


def test_parse_failure_is_unclassified_and_can_make_report_inconclusive(tmp_path):
    prompts: list[str] = []
    d = selector_deps(prompts, scout_outputs=["not json"] + [marker_json(False)] * 20)
    run_until_arms(tmp_path, d)
    runner.run_stage(tmp_path, d, stage="select")

    classification = runner.run_stage(tmp_path, d, stage="classify")
    assert any(not row["classified"] and row["markers"] is None for row in classification["rows"])
    assert runner.decision_outcome(classification["aggregates"]) == "INCONCLUSIVE_CLASSIFICATION"
    d.main_roles = runner.RoleRuntime(
        author=d.main_roles.author,
        scout=lambda _prompt: pytest.fail("completed classification must be reused"),
        jury=d.main_roles.jury,
        author_model=d.main_roles.author_model,
        scout_model=d.main_roles.scout_model,
    )
    assert runner.run_stage(tmp_path, d, stage="classify") == classification
    report_path = runner.run_stage(tmp_path, d, stage="report")
    report = Path(report_path).read_text(encoding="utf-8")
    assert "INCONCLUSIVE_CLASSIFICATION" in report
    assert runner.MANDATORY_NON_INDEPENDENCE_WARNING in report
    assert "seed_hash:" in report and "poetics_hash:" in report and "config_hash:" in report
    assert "packet_hash" in report and "effective_constraints_hash" in report
    assert "deviations" in report
    assert "jury_argmax" in report and "blind_choice_matched_jury_argmax" in report
    assert "budget_envelope" in report and "phase_overruns" in report
    assert "reconciliation_status: unreconciled" in report
    assert "matched is not claimed" in report


def test_canonical_handoff_never_rewinds_existing_checkpoint(tmp_path):
    prompts: list[str] = []
    d = selector_deps(prompts)
    run_until_arms(tmp_path, d)
    runner.run_stage(tmp_path, d, stage="select")
    runner.run_stage(tmp_path, d, stage="classify")
    advanced = Checkpoint(work_id=runner.WORK_ID, state=State.CRITIQUE, step=9, payload={"x": "y"})
    advanced.save(tmp_path / "works" / runner.WORK_ID)

    runner.run_stage(tmp_path, d, stage="promote")

    cp = Checkpoint.load(tmp_path / "works" / runner.WORK_ID)
    assert cp.state == State.CRITIQUE
    assert cp.step == 9


def test_all_stops_after_report_and_does_not_publish_or_run_canonical_l6_l7(tmp_path):
    prompts: list[str] = []
    d = selector_deps(prompts, scout_outputs=[marker_json(False)] * 40)
    write_seed(tmp_path)
    report_path = runner.run_stage(tmp_path, d, stage="all")
    main = tmp_path / "works" / runner.WORK_ID
    assert Path(report_path).exists()
    assert not (main / "final" / "text.md").exists()
    assert Checkpoint.load(main).state == State.DRAFT


def test_canonical_stage_runs_only_after_promotion(tmp_path):
    prompts: list[str] = []
    d = selector_deps(prompts, scout_outputs=[marker_json(False)] * 40)
    write_seed(tmp_path)
    runner.run_stage(tmp_path, d, stage="all")
    observed = []
    d.run_canonical = lambda work: observed.append(Checkpoint.load(work.dir).state) or State.SHELVE

    result = runner.run_stage(tmp_path, d, stage="canonical")

    assert result == State.SHELVE
    assert observed == [State.DRAFT]
