from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from aleph.core.loop import Checkpoint, State
from scripts import run_w0008 as runner

pytestmark = pytest.mark.m6


def seed_data(*, cap: float = 15.0) -> dict:
    return {
        "hint": "w0008 test",
        "experiment": {
            "id": "exp-w0008-test",
            "criteria_constraints": "解除条項",
        },
        "material_ablation": {
            "arms": ["aozora", "none", "secondary"],
            "budget_priority": "aozora→none→secondary",
            "secondary_source": "corpus/secondary/works.jsonl",
            "min_form_fidelity": 0.4,
            "budget_cap_usd": cap,
        },
    }


def make_main(root: Path, *, cap: float = 15.0):
    work = runner.main_work(root)
    runner.ensure_work_layout(work, seed=seed_data(cap=cap))
    return work


def write_shared(main, *, audience: str = "人間 1.0", niche: dict | None = None) -> dict:
    shared = {"audience": audience, "niche": niche or {"id": "n1", "description": "テストニッチ"}}
    runner._write_json(main.dir / "ablation" / "shared.json", shared)
    return shared


def fake_roles(*, author=None, scout=None, jury=None) -> runner.RoleRuntime:
    return runner.RoleRuntime(
        author=author or (lambda prompt: '{"choice":"A","rationale":"理由"}'),
        scout=scout or (lambda prompt: '{"era_taisho_showa":false,"backstage_world":false,"aphoristic_voice":false,"prior_attractor":false}'),
        jury=jury or (),
        author_model="author-test",
        scout_model="scout-test",
        jury_models=("jury-a", "jury-b", "jury-c"),
    )


def make_deps(
    root: Path,
    *,
    main_roles: runner.RoleRuntime | None = None,
    arm_roles: runner.RoleRuntime | None = None,
    embedder=None,
    pipeline=None,
    transmute_fn=None,
    find_hidden_pairs_fn=None,
) -> runner.RunnerDeps:
    roles = main_roles or fake_roles()
    arm_runtime = arm_roles or roles
    return runner.RunnerDeps(
        choose_intent=lambda work: "人間 1.0",
        explore=lambda work: {"id": "n1", "description": "テストニッチ"},
        main_roles=roles,
        arm_roles=lambda work: arm_runtime,
        embedder=embedder,
        poetics="窯 検閲",
        index_dir=root / "state" / "atlas",
        secondary_path=root / "corpus" / "secondary" / "works.jsonl",
        pipeline_to_draft=pipeline or fake_pipeline_to_draft,
        find_hidden_pairs_fn=find_hidden_pairs_fn or (lambda *args, **kwargs: []),
        transmute_fn=transmute_fn or runner.transmute,
        model_names={"author_primary": "author-test", "scout": "scout-test", "critic_jury": ["j1", "j2", "j3"]},
    )


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
    (work.compositions / "criteria.md").write_text("# criteria", encoding="utf-8")
    (work.compositions / "proposal_1.json").write_text(
        json.dumps(
            {"form": "f", "parts": [], "material_placement": "", "style_policy": "", "length_estimate": 100},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (work.compositions / "winner.json").write_text(
        json.dumps(
            {"form": "f", "parts": [], "material_placement": "", "style_policy": "", "length_estimate": 100},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    work.draft_path(1).write_text(f"draft for {work.work_id}", encoding="utf-8")
    return work.draft_path(1)


def write_call(work, cost: float) -> None:
    with work.calls.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"cost_usd": cost}) + "\n")


def setup_arm(main, arm: str, *, draft_text: str = "本文。", material: bool = False):
    work = runner.arm_work(main, arm)
    runner.ensure_work_layout(work, seed={"arm": arm})
    fake_pipeline_to_draft(work, {}, "", lambda _: "", lambda _: "")
    work.draft_path(1).write_text(draft_text, encoding="utf-8")
    if material:
        runner._write_json(work.materials / "m1.json", {"content": f"material {arm}"})
    return work


def decisions(work) -> list[dict]:
    return [json.loads(line) for line in work.decisions.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_prepare_fails_cleanly_when_seed_missing_or_lacks_manifest(tmp_path):
    deps = make_deps(tmp_path)
    with pytest.raises(runner.ManifestError, match="missing seed.json"):
        runner.stage_prepare(tmp_path, deps)

    work = runner.main_work(tmp_path)
    runner.ensure_work_layout(work, seed={"experiment": {}, "material_ablation": {}})
    with pytest.raises(runner.ManifestError, match="experiment.criteria_constraints"):
        runner.stage_prepare(tmp_path, deps)

    work.seed.write_text(json.dumps({"experiment": {"criteria_constraints": "x"}}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(runner.ManifestError, match="material_ablation"):
        runner.stage_prepare(tmp_path, deps)


def test_secondary_materials_passes_min_form_fidelity_and_records_cards(tmp_path):
    main = make_main(tmp_path)
    shared = write_shared(main, niche={"id": "n1", "description": "記憶の規約"})
    secondary = runner.arm_work(main, "secondary")
    runner.ensure_work_layout(secondary, seed={"arm": "secondary"})
    sources_path = tmp_path / "corpus" / "secondary" / "works.jsonl"
    sources_path.parent.mkdir(parents=True)
    sources = [
        {"id": "s1", "title": "law1", "form_type": "law", "text": "第一条 甲"},
        {"id": "s2", "title": "rfc1", "form_type": "rfc", "text": "Abstract\n\n1. Intro\nMUST"},
        {"id": "s3", "title": "far", "form_type": "law", "text": "第三"},
    ]
    sources_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in sources) + "\n", encoding="utf-8")
    calls: list[dict] = []

    def embedder(texts):
        vectors = [[1.0, 0.0], [1.0, 0.0], [0.8, 0.0], [0.0, 1.0]]
        return np.asarray(vectors[: len(texts)], dtype=np.float64)

    def fake_transmute(source_text, theme, llm, embedder, **kwargs):
        calls.append(kwargs)
        biblio = kwargs["source_biblio"]
        return {
            "content": f"card {biblio['id']}",
            "source": biblio,
            "provenance": {"form_fidelity": 0.5, "final_cos": 0.6, "iterations": 2},
        }

    deps = make_deps(tmp_path, embedder=embedder, transmute_fn=fake_transmute)
    cards = runner.build_secondary_materials(secondary, shared, seed_data(), deps, fake_roles())

    assert len(cards) == 2
    assert len(calls) == 2
    assert all(call["min_form_fidelity"] == 0.4 for call in calls)
    fidelity = json.loads((secondary.dir / "fidelity.json").read_text(encoding="utf-8"))
    assert [row["source_id"] for row in fidelity["rows"]] == ["s1", "s2"]
    assert all(row["form_fidelity"] == 0.5 for row in fidelity["rows"])
    assert len(list(secondary.materials.glob("*.json"))) == 2


def test_none_arm_writes_no_materials_and_passes_empty_materials_to_pipeline(tmp_path):
    main = make_main(tmp_path)
    shared = write_shared(main)
    captured: dict[str, object] = {}

    def pipeline(work, niche, audience, author, critic, **kwargs):
        captured["materials"] = kwargs["materials"]
        return fake_pipeline_to_draft(work, niche, audience, author, critic, **kwargs)

    deps = make_deps(tmp_path, pipeline=pipeline)
    runner.run_arm(main, "none", shared, seed_data(), deps)
    none = runner.arm_work(main, "none")

    assert captured["materials"] == []
    assert list(none.materials.glob("*.json")) == []
    assert none.draft_path(1).exists()


def test_budget_curtailment_skips_secondary_after_none(tmp_path):
    main = make_main(tmp_path, cap=5.0)
    write_shared(main)

    costs = {"aozora": 2.0, "none": 2.5, "secondary": 1.0}

    def pipeline(work, niche, audience, author, critic, **kwargs):
        path = fake_pipeline_to_draft(work, niche, audience, author, critic, **kwargs)
        write_call(work, costs[work.work_id])
        return path

    deps = make_deps(tmp_path, pipeline=pipeline)
    results = runner.stage_arms(tmp_path, deps)

    assert [row["arm"] for row in results] == ["aozora", "none"]
    assert runner.arm_work(main, "aozora").draft_path(1).exists()
    assert runner.arm_work(main, "none").draft_path(1).exists()
    assert not runner.arm_work(main, "secondary").draft_path(1).exists()
    text = main.decisions.read_text(encoding="utf-8")
    assert "事前登録の腕優先順位" in text
    assert "secondary" in text


def test_blind_selection_prompt_hides_arm_names_and_jury_runs_after_persist(tmp_path):
    main = make_main(tmp_path)
    write_shared(main)
    for arm in runner.ARMS_ORDER:
        setup_arm(main, arm, draft_text=f"候補本文 {arm.upper().replace('SECONDARY', 'S')}")

    author_prompts: list[str] = []

    def author(prompt: str) -> str:
        author_prompts.append(prompt)
        return json.dumps({"choice": "A", "rationale": "Aの密度を選ぶ"}, ensure_ascii=False)

    def scout(prompt: str) -> str:
        return json.dumps({"pass": True, "issues": ["破綻なし"]}, ensure_ascii=False)

    jury_calls: list[str] = []

    def juror(prompt: str) -> str:
        assert any("w0008 blind selection" in row["decision"] for row in decisions(main))
        jury_calls.append(prompt)
        return json.dumps({"score": 7.0, "rationale": "ok"}, ensure_ascii=False)

    roles = fake_roles(author=author, scout=scout, jury=(juror, juror, juror))
    deps = make_deps(tmp_path, main_roles=roles)
    result = runner.stage_select(tmp_path, deps)

    prompt = author_prompts[0]
    assert "技術床" in prompt and "破綻なし" in prompt
    for forbidden in {"平均", "不一致", "mean_score", "disagreement", "aozora", "secondary"}:
        assert forbidden not in prompt
    selection_rows = [row for row in decisions(main) if row["decision"].startswith("w0008 blind selection")]
    assert selection_rows and "label_mapping" in selection_rows[-1]
    assert jury_calls
    assert (main.dir / "ablation" / "jury_disclosure.json").exists()
    assert result["selection"]["label_mapping"] == selection_rows[-1]["label_mapping"]


def test_classification_aggregation_and_report_sentence(tmp_path):
    main = make_main(tmp_path)
    rows = [
        runner.row_with_cooccurrence(
            {
                "arm": "aozora",
                "level": "L4",
                "unit_id": "p1",
                "markers": {
                    "era_taisho_showa": True,
                    "backstage_world": False,
                    "aphoristic_voice": False,
                    "prior_attractor": False,
                },
            },
            "窯の話",
        ),
        runner.row_with_cooccurrence(
            {
                "arm": "aozora",
                "level": "L4",
                "unit_id": "p2",
                "markers": {
                    "era_taisho_showa": False,
                    "backstage_world": False,
                    "aphoristic_voice": False,
                    "prior_attractor": False,
                },
            },
            "窯はあるが標識はない",
        ),
        runner.row_with_cooccurrence(
            {
                "arm": "none",
                "level": "L5",
                "unit_id": "s1",
                "markers": {
                    "era_taisho_showa": False,
                    "backstage_world": True,
                    "aphoristic_voice": False,
                    "prior_attractor": False,
                },
            },
            "語彙なし",
        ),
        runner.row_with_cooccurrence(
            {
                "arm": "none",
                "level": "L5",
                "unit_id": "s2",
                "markers": {
                    "era_taisho_showa": False,
                    "backstage_world": True,
                    "aphoristic_voice": True,
                    "prior_attractor": True,
                },
            },
            "検閲の話",
        ),
    ]
    data = {"rows": rows, "aggregates": runner.aggregate_classification(rows)}
    runner._write_json(main.dir / "ablation" / "classification.json", data)

    aozora_l4 = data["aggregates"]["aozora"]["L4"]
    assert aozora_l4["marker_rates"]["era_taisho_showa"] == pytest.approx(0.5)
    assert aozora_l4["cooccurrence"]["denominator_marker_positive"] == 1
    assert aozora_l4["cooccurrence"]["rate"] == pytest.approx(1.0)
    none_l5 = data["aggregates"]["none"]["L5"]
    assert none_l5["marker_rates"]["backstage_world"] == pytest.approx(1.0)
    assert none_l5["cooccurrence"]["denominator_marker_positive"] == 2
    assert none_l5["cooccurrence"]["rate"] == pytest.approx(0.5)

    deps = make_deps(tmp_path)
    path = runner.write_report(tmp_path, deps, date_utc=datetime(2026, 7, 18, tzinfo=timezone.utc))
    report = path.read_text(encoding="utf-8")
    assert runner.MANDATORY_NON_INDEPENDENCE_SENTENCE in report
    assert "high = rate >= 0.5, low = rate <= 0.2" in report
    assert "検定" not in report and "p値" not in report


def test_blind_selection_supports_two_arm_fallback(tmp_path):
    """事前登録の後退線（secondary縮退）でも盲検選択が成立する（審査回答2）。"""
    main = make_main(tmp_path)
    write_shared(main)
    for arm in ("aozora", "none"):
        setup_arm(main, arm, draft_text=f"候補 {arm.upper().replace('SECONDARY', 'S')}")

    def author(prompt: str) -> str:
        assert "原稿A" in prompt and "原稿B" in prompt and "原稿C" not in prompt
        return json.dumps({"choice": "B", "rationale": "対比"}, ensure_ascii=False)

    roles = fake_roles(author=author)
    deps = make_deps(tmp_path, main_roles=roles)
    tech = {"aozora": {"pass": True, "issues": []}, "none": {"pass": True, "issues": []}}
    result = runner.stage_blind_selection(tmp_path, deps, tech)
    assert result["chosen_arm"] in {"aozora", "none"}
    assert set(result["label_mapping"].values()) == {"A", "B"}


def test_blind_prompt_does_not_mask_draft_body(tmp_path):
    """原稿本文は伏字加工しない（本文改変は選択観測を歪める）。伏字は技術床指摘のみ。"""
    mapping = {"x": "A", "y": "B"}
    tech = {"x": {"pass": True, "issues": ["平均的で冗長"]}, "y": {"pass": True, "issues": []}}
    drafts = {"x": "彼は平均という語を嫌った。", "y": "本文2"}
    prompt = runner.build_blind_selection_prompt(mapping, tech, drafts)
    assert "彼は平均という語を嫌った。" in prompt
    assert "[伏字]的で冗長" in prompt


def test_canon_handoff_never_overwrites_existing_checkpoint(tmp_path):
    """CRITIQUE以降へ進んだcheckpointをselect再実行でDRAFTへ巻き戻さない。"""
    main = make_main(tmp_path)
    write_shared(main)
    for arm in runner.ARMS_ORDER:
        setup_arm(main, arm, material=True)
    advanced = Checkpoint(work_id=main.work_id, state=State.CRITIQUE, step=9, payload={"audience": "x"})
    advanced.save(main.dir)

    deps = make_deps(tmp_path)
    runner.stage_canon_handoff(tmp_path, deps, {"chosen_arm": "none"})

    cp = Checkpoint.load(main.dir)
    assert cp.state == State.CRITIQUE
    assert cp.step == 9


def test_canon_handoff_writes_draft_checkpoint_and_meta(tmp_path):
    main = make_main(tmp_path)
    shared = write_shared(main, audience="人間 0.7 / LLM 0.3", niche={"id": "n1", "description": "正典ニッチ"})
    for arm in runner.ARMS_ORDER:
        setup_arm(main, arm, draft_text=f"{arm} draft", material=True)

    deps = make_deps(tmp_path)
    runner.stage_canon_handoff(tmp_path, deps, {"chosen_arm": "none"})

    cp = Checkpoint.load(main.dir)
    assert cp.state == State.DRAFT
    assert set(cp.payload) == {"audience", "niche", "materials", "canonical_arm"}
    assert cp.payload["audience"] == shared["audience"]
    assert cp.payload["canonical_arm"] == "none"
    assert (main.compositions / "criteria.md").exists()
    assert (main.compositions / "proposal_1.json").exists()
    assert main.draft_path(1).read_text(encoding="utf-8") == "none draft"
    assert (main.materials / "m1.json").exists()
    assert json.loads((runner.arm_work(main, "none").dir / "meta.json").read_text(encoding="utf-8")) == {
        "canonical": True,
        "promoted_to": "works/w0008",
    }
    assert json.loads((runner.arm_work(main, "aozora").dir / "meta.json").read_text(encoding="utf-8")) == {
        "canonical": False
    }
    assert json.loads((runner.arm_work(main, "secondary").dir / "meta.json").read_text(encoding="utf-8")) == {
        "canonical": False
    }
