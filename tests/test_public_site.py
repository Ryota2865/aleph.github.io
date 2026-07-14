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
    _nav,
    _public_experiment_text,
    _verify_relative_hrefs,
    _work_fact,
    build_public_site,
    iter_published,
)


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


def test_w0004_publication_history_is_complete_and_naturally_punctuated() -> None:
    work = (ROOT / "docs" / "works" / "w0004.html").read_text(encoding="utf-8")

    assert "publication:SHELVE — 初回公開は人間承認待ち" in work
    assert " → publication:PUBLISH — 品質の床" in work
    assert "）。）" not in work


def test_surface_keeps_explanation_behind_the_work() -> None:
    home = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    work = (ROOT / "docs" / "works" / "w0004.html").read_text(encoding="utf-8")

    assert "作品ができるまで" not in home
    assert "なぜ古い文体なのか" not in home
    assert home.index("<h2>作品</h2>") < home.index("制作記録を検証する")
    assert work.index("id='work-body'") < work.index("id='production-note'")
    assert "<details class='production-note'" in work


def test_machine_index_tracks_every_published_work() -> None:
    index = (ROOT / "docs" / "llms.txt").read_text(encoding="utf-8")

    work_ids = [path.stem for path in (ROOT / "docs" / "works").glob("w*.html")]
    assert work_ids
    for work_id in work_ids:
        assert f"works/{work_id}.html" in index
        assert f"archive.html#{work_id}" in index
