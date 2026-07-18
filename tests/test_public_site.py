from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from scripts.build_public_site import (
    _demote_headings,
    _RESEARCH_META,
    _artifact_id,
    _dialogue_paths,
    _home_work_selection,
    _nav,
    _production_note,
    _public_experiment_text,
    _verify_relative_hrefs,
    _work_fact,
    build_public_site,
    iter_published,
)
from scripts.build_work_colophon import write_colophon


ROOT = Path(__file__).resolve().parents[1]


class _AuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.h1 = 0
        self.lang = ""
        self.descriptions: list[str] = []
        self.current = 0
        self.ids: list[str] = []
        self.hrefs: list[str] = []
        self.unwrapped_tables = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = values.get("lang", "")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and values.get("name") == "description":
            self.descriptions.append(values.get("content", "").strip())
        elif tag == "a":
            if values.get("aria-current") == "page":
                self.current += 1
            if values.get("href"):
                self.hrefs.append(values["href"])
        elif tag == "table":
            wrapped = any("table-wrap" in node.get("class", "").split() for _, node in self.stack)
            if not wrapped:
                self.unwrapped_tables += 1
        if values.get("id"):
            self.ids.append(values["id"])
        self.stack.append((tag, values))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def _parse(path: Path) -> _AuditParser:
    parser = _AuditParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_minimal_site_sources(root: Path) -> None:
    for relative in (
        "site/home.md",
        "site/about.md",
        "site/poetics-intro.md",
        "site/research-intro.md",
        "site/en/home.md",
        "site/en/about.md",
        "site/en/poetics-intro.md",
        "site/en/research-intro.md",
    ):
        _write_text(root / relative, "minimal\n")
    _write_text(root / "poetics" / "poetics.md", "# 詩学\n")
    _write_text(root / "ODE.md", "# ODE\n")
    _write_text(root / "DECLARATION_2024.md", "# Declaration\n\n2024年4月18日、記録。\n")
    _write_text(root / "reports" / "RESPONSE_TO_FABLE5_CHAT_20260712.md", "# Response\n")
    for name in _RESEARCH_META:
        _write_text(root / "reports" / name, "# Experiment\n")
    _write_text(root / "reports" / "EN_L1_selfconcept_note.md", "# English note\n")


def test_embedded_artifact_headings_leave_page_h1_unique() -> None:
    embedded = _demote_headings("# report\n## section\ntext")
    page = f"<h1>Page</h1>{embedded}"

    assert embedded.startswith("## report\n### section")
    assert len(re.findall(r"<h1(?:\\s|>)", page)) == 1


def test_nav_marks_current_page() -> None:
    nav = _nav("../", "works/index.html")

    assert "href='../works/index.html' aria-current='page'" in nav
    assert nav.count("aria-current='page'") == 1


def test_nav_groups_detail_pages() -> None:
    assert "href='../archive.html' aria-current='page'" in _nav("../", "process/w0004-reviews.html")
    assert "href='../research/index.html' aria-current='page'" in _nav("../", "research/EXP_x.html")
    assert "href='../en/research/index.html' aria-current='page'" in _nav("../", "en/research-l1.html", "en")


def test_publish_filter_removes_known_shell_scar() -> None:
    filtered = _public_experiment_text("本文・費用/bin/bash.39。")

    assert "費用/bin" not in filtered
    assert filtered == "本文。"


def test_work_fact_uses_historical_artifacts(tmp_path: Path) -> None:
    work = tmp_path / "works" / "wtest"
    (work / "reviews").mkdir(parents=True)
    (work / "seed.json").write_text('{"hint":"forced condition"}', encoding="utf-8")
    (work / "checkpoint.json").write_text(
        json.dumps(
            {"payload": {"audience": "人間 1.0", "niche": {"description": "test niche"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        work / "calls.jsonl",
        [
            {"role": "author_primary", "model": "criteria-model"},
            {"role": "author_primary", "model": "later-author"},
        ],
    )
    _write_jsonl(
        work / "reviews" / "trajectory.jsonl",
        [
            {"version": 1, "mean_score": 8.0, "disagreement": 1.0},
            {"version": 1, "mean_score": 8.2, "disagreement": 0.5},
        ],
    )
    _write_jsonl(
        work / "decisions.jsonl",
        [
            {"layer": "L1", "decision": "志向配合比(実験固定)", "decided_by": "owner-experiment"},
            {"layer": "L6", "decision": "採用 v1", "best_version": 1},
            {"layer": "L0", "decision": "CRITIQUE->FINISH", "reason": "stop"},
            {"layer": "L7", "decision": "publication:SHELVE", "reason": "await human"},
            {"layer": "L7", "decision": "publication:PUBLISH", "reason": "publish"},
        ],
    )

    fact = _work_fact(tmp_path, "wtest")

    assert fact["audience"] == "人間 1.0"
    assert fact["forced"] is True
    assert fact["criteria_model"] == "criteria-model"
    assert fact["trajectories"][1]["mean_score"] == 8.2
    assert fact["best_version"] == 1
    assert fact["finish"]["reason"] == "stop"
    assert [row["decision"] for row in fact["publications"]] == [
        "publication:SHELVE",
        "publication:PUBLISH",
    ]
    assert fact["publications"][0]["reason"] == "await human"


def test_work_colophon_builder_derives_versions_models_and_is_idempotent(tmp_path: Path) -> None:
    work = tmp_path / "works" / "wtest"
    work.mkdir(parents=True)
    (work / "meta.json").write_text('{"canonical": false}', encoding="utf-8")
    _write_jsonl(
        work / "decisions.jsonl",
        [
            {"decision": "志向配合比"},
            {"decision": "poetics_version:3"},
        ],
    )
    _write_jsonl(
        work / "calls.jsonl",
        [
            {"role": "author_primary", "model": "author-a"},
            {"role": "scout", "model": "scout-a"},
            {"role": "author_primary", "model": "author-a"},
            {"role": "author_primary", "model": "author-b"},
        ],
    )

    assert write_colophon(work) is True
    first_text = (work / "colophon.json").read_text(encoding="utf-8")
    payload = json.loads(first_text)

    assert payload["poetics_version"] == 3
    assert payload["author_models"] == ["author-a", "author-b"]
    assert payload["scout_models"] == ["scout-a"]
    assert payload["jury_models"] == []
    assert payload["reader_models"] == []
    assert payload["corpus_id"] == "aozora"
    assert payload["atlas_version"] is None
    assert payload["canonical"] is False
    assert payload["generated_by"] == "scripts/build_work_colophon.py"
    assert payload["generated_at"]
    assert write_colophon(work) is False
    assert (work / "colophon.json").read_text(encoding="utf-8") == first_text


def test_work_colophon_builder_tolerates_missing_annotation_and_calls(tmp_path: Path) -> None:
    work = tmp_path / "works" / "wtest"
    work.mkdir(parents=True)
    _write_jsonl(work / "decisions.jsonl", [{"decision": "志向配合比"}])

    assert write_colophon(work) is True
    payload = json.loads((work / "colophon.json").read_text(encoding="utf-8"))

    assert payload["poetics_version"] is None
    assert payload["author_models"] == []
    assert payload["scout_models"] == []
    assert payload["jury_models"] == []
    assert payload["reader_models"] == []
    assert payload["canonical"] is True


def test_production_note_uses_colophon_version_line_and_missing_fallback(tmp_path: Path) -> None:
    work = tmp_path / "works" / "wtest"
    work.mkdir(parents=True)
    (work / "colophon.json").write_text(
        json.dumps(
            {
                "poetics_version": 0,
                "author_models": ["author-from-colophon"],
                "corpus_id": "aozora",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    note = _production_note(tmp_path, "wtest", {})

    assert "版:</strong> 詩学第0版 · コーパス aozora · 著者 author-from-colophon" in note
    assert "宛先、詩学第0版を入力" in note
    (work / "colophon.json").write_text(
        json.dumps({"poetics_version": 2, "author_models": ["author-from-colophon"], "corpus_id": "aozora"}),
        encoding="utf-8",
    )
    assert "宛先、詩学第2版を入力" in _production_note(tmp_path, "wtest", {})

    missing_work = tmp_path / "works" / "wmissing"
    missing_work.mkdir(parents=True)
    missing_note = _production_note(tmp_path, "wmissing", {})

    assert "版:</strong> 記録なし" in missing_note
    assert "宛先、詩学第0版を入力" in missing_note


def test_public_site_ignores_w0008_ablation_dirs(tmp_path: Path) -> None:
    _write_minimal_site_sources(tmp_path)
    arm = tmp_path / "works" / "w0008" / "ablation" / "aozora"
    _write_jsonl(arm / "decisions.jsonl", [{"decision": "publication:PUBLISH"}])
    _write_text(arm / "final" / "meta.json", '{"title":"arm"}')
    _write_text(arm / "final" / "text.md", "arm text")

    out_dir = tmp_path / "docs"
    build_public_site(tmp_path, out_dir)

    assert iter_published(tmp_path) == []
    assert not (out_dir / "works" / "aozora.html").exists()
    assert "aozora" not in "\n".join(path.name for path in (out_dir / "works").glob("*.html"))


def test_relative_href_validator_accepts_nested_pages(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "index.html").write_text("<a href='nested/page.html'>page</a>", encoding="utf-8")
    (tmp_path / "nested" / "page.html").write_text("<a href='../index.html'>home</a>", encoding="utf-8")

    _verify_relative_hrefs(tmp_path)


def test_checked_in_html_contracts_and_fragments(tmp_path: Path) -> None:
    tracked_docs = ROOT / "docs"
    docs = tracked_docs
    if iter_published(ROOT):
        docs = tmp_path / "docs"
        build_public_site(ROOT, docs)
        generated_rel = {path.relative_to(docs) for path in docs.rglob("*.html")}
        tracked_rel = {path.relative_to(tracked_docs) for path in tracked_docs.rglob("*.html")}
        assert generated_rel == tracked_rel
        for relative_path in generated_rel:
            assert (docs / relative_path).read_bytes() == (tracked_docs / relative_path).read_bytes()
        assert (docs / "llms.txt").read_bytes() == (tracked_docs / "llms.txt").read_bytes()

    pages = sorted(docs.rglob("*.html"))
    parsed = {path.resolve(): _parse(path) for path in pages}

    assert pages
    for path, audit in parsed.items():
        assert audit.h1 == 1, path
        assert len(audit.descriptions) == 1 and audit.descriptions[0], path
        assert audit.current == 1, path
        assert audit.lang in {"ja", "en"}, path
        assert audit.unwrapped_tables == 0, path
        assert len(audit.ids) == len(set(audit.ids)), path

        for href in audit.hrefs:
            target = urlsplit(href)
            if target.scheme or target.netloc or not target.fragment:
                continue
            target_path = path if not target.path else (path.parent / target.path).resolve()
            if target_path.is_dir():
                target_path = target_path / "index.html"
            assert target_path in parsed, (path, href)
            assert target.fragment in parsed[target_path].ids, (path, href)


def test_research_and_dialogue_are_reciprocally_linked() -> None:
    dialogue = (ROOT / "docs" / "dialogue.html").read_text(encoding="utf-8")
    for report_name, meta in _RESEARCH_META.items():
        experiment_path = ROOT / "docs" / "research" / f"{Path(report_name).stem}.html"
        experiment = experiment_path.read_text(encoding="utf-8")
        anchor = _artifact_id(meta["dialogue"])

        assert f"../dialogue.html#{anchor}" in experiment
        assert f"id='{anchor}'" in dialogue
        assert f"research/{Path(report_name).stem}.html" in dialogue


def test_dialogue_surface_omits_operations_and_en_index_tracks_primary_record() -> None:
    dialogue = (ROOT / "docs" / "dialogue.html").read_text(encoding="utf-8")
    english = (ROOT / "docs" / "en" / "dialogue.html").read_text(encoding="utf-8")

    assert "reports/ にファイルを追加すれば自動で並ぶ" not in dialogue
    assert "synchronized structural index, not a translation" in english
    for path in _dialogue_paths(ROOT):
        assert f"../dialogue.html#{_artifact_id(path.name)}" in english


def test_w0004_criteria_distinguishes_generator_from_final_author() -> None:
    criteria = (ROOT / "docs" / "process" / "w0004-criteria.html").read_text(encoding="utf-8")
    work = (ROOT / "docs" / "works" / "w0004.html").read_text(encoding="utf-8")
    english = (ROOT / "docs" / "en" / "works" / "w0004.html").read_text(encoding="utf-8")

    assert "基準書生成時の著者役 <strong>claude-fable-5</strong>" in criteria
    assert "最終著者クレジットを <strong>gpt-5.5</strong>" in criteria
    assert "基準書生成後の構成・本文と最終著者クレジットは gpt-5.5" in work
    assert "criteria-stage author-role claude-fable-5" in english
    assert "final author credit then passed to gpt-5.5" in english


def test_w0004_publication_history_is_complete_and_naturally_punctuated() -> None:
    work = (ROOT / "docs" / "works" / "w0004.html").read_text(encoding="utf-8")

    assert "publication:SHELVE — 初回公開は人間承認待ち" in work
    assert " → publication:PUBLISH — 品質の床" in work
    assert "）。）" not in work


def test_surface_keeps_explanation_behind_the_work() -> None:
    home = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    english_home = (ROOT / "docs" / "en" / "index.html").read_text(encoding="utf-8")
    work = (ROOT / "docs" / "works" / "w0004.html").read_text(encoding="utf-8")

    assert "作品ができるまで" not in home
    assert "なぜ古い文体なのか" not in home
    assert home.index("<h2>作品</h2>") < home.index("制作記録を検証する")
    assert "すべての作品" not in home
    assert "All works" not in english_home
    assert work.index("id='work-body'") < work.index("id='production-note'")
    assert "<details class='production-note'" in work


def test_homepage_switches_from_complete_shelf_to_recent_works() -> None:
    five = [(f"w{i:04d}", {}, "") for i in range(1, 6)]
    six = [(f"w{i:04d}", {}, "") for i in range(1, 7)]

    complete, complete_is_excerpt = _home_work_selection(five)
    recent, recent_is_excerpt = _home_work_selection(six)

    assert [work_id for work_id, _meta, _text in complete] == [f"w{i:04d}" for i in range(1, 6)]
    assert complete_is_excerpt is False
    assert [work_id for work_id, _meta, _text in recent] == ["w0006", "w0005", "w0004"]
    assert recent_is_excerpt is True


def test_machine_index_tracks_every_published_work() -> None:
    index = (ROOT / "docs" / "llms.txt").read_text(encoding="utf-8")

    work_ids = [path.stem for path in (ROOT / "docs" / "works").glob("w*.html")]
    assert work_ids
    for work_id in work_ids:
        assert f"works/{work_id}.html" in index
        assert f"archive.html#{work_id}" in index


def test_every_published_work_has_curated_notes() -> None:
    # w0007/w0008 で再発した「一行解説がフォールバックに落ちる」問題の再発防止。
    # 公開作品は日英とも編集済み解説を必ず持つ（公開フローでの追加漏れをここで落とす）。
    from scripts.build_public_site import _EN_WORK_NOTES, _JP_WORK_NOTES, iter_published

    published = [work_id for work_id, _meta, _text in iter_published(ROOT)]
    assert published, "公開作品が検出されること"
    missing_jp = [w for w in published if w not in _JP_WORK_NOTES]
    missing_en = [w for w in published if w not in _EN_WORK_NOTES]
    assert not missing_jp, f"_JP_WORK_NOTES に解説がない公開作品: {missing_jp}"
    assert not missing_en, f"_EN_WORK_NOTES に解説がない公開作品: {missing_en}"
