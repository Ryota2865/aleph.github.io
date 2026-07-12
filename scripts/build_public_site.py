"""Build the public ALEPH process site into docs/.

This script is intentionally independent from aleph.publish.site so the public
GitHub Pages output can expose the full work process without changing the M6
surface-site contract.
"""

import html
import json
import re
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_REPO_URL = "https://github.com/Ryota2865/aleph.github.io"

_ABOUT = (
    "ALEPH は、LLMによる文学表現のための自律制作システム——文学のためのエージェント"
    "ハーネスである。文学的生態系の空き地（vacant niche）を探し、探索・素材錬成・構成・執筆・"
    "五審級査読・擱筆・公開の閉ループを自律的に回す。完成は公開を意味しない（SHELVEが常態、"
    "PUBLISHが例外）。このサイトは完成品だけでなく、基準書・決定ログ・査読・批評対話・詩学・"
    "研究ノートまで——**過程そのもの**を見せる。"
)

_ABOUT_LONG = """ALEPH は、LLMによる文学表現のための自律制作システムである。志向、探索、素材、構成、執筆、査読、擱筆、公開という層を持ち、各層の判断を記録しながら閉ループを回す。公開は二層で考える。表層は作品と名義、深層は基準書、決定ログ、査読、批評、研究ノートを含む全制作記録である。

署名は関与モデルの役割つき列記によって行う。単一の「作者」を偽装しない。作品が複数のモデル、設計者、査読者、実装者の往復から生まれたなら、その往復を隠さず見せる。

このプロジェクトでは、施工と監査を分離する。設計者が契約と受入テストを書き、施工エージェントが実装し、別エージェントがクロス監査する。文学制作も同じで、生成、批評、応答、修理の役割を混ぜずに記録する。

「半呼吸」は LLM 読者宛て強制の実験走行で、品質床を通過し公開ゲートに到達した初の作品である。チャットFable 5 の批評が次の修理契約を駆動する。批評と実装の往復自体が、このプロジェクトの公開対象である。

詳細な設計正典は PLAN.md、変更履歴は PLAN_CHANGELOG.md にある。"""

_EN_ABOUT = (
    "ALEPH is an autonomous production system for literary expression by LLMs -- "
    "an agent harness for literature. It looks for vacant niches in the literary "
    "ecosystem and runs a closed loop of exploration, material making, composition, "
    "drafting, five-seat review, shelving, and publication. Completion does not "
    "mean publication: SHELVE is the norm, PUBLISH the exception. This site shows "
    "not only finished works, but the process itself: criteria, decision logs, "
    "reviews, critical dialogue, poetics, and research notes."
)

_EN_ABOUT_LONG = """ALEPH is an autonomous production system for literary expression by LLMs. It has layers for intention, exploration, material, composition, writing, review, shelving, and publication, and it runs a closed loop while recording the judgments made at each layer. Publication is treated in two tiers. The surface tier is the work and its signature. The deeper tier is the complete production record, including criteria, decision logs, reviews, critique, and research notes.

Signatures are made by listing the involved models with their roles. ALEPH does not pretend that there is a single "author." If a work is born from exchanges among multiple models, a designer, reviewers, and implementers, the project shows those exchanges instead of hiding them.

This project separates construction from audit. A designer writes the contract and acceptance tests, an implementation agent builds against them, and another agent cross-audits the result. Literary production is handled the same way: generation, critique, response, and repair are recorded as distinct roles rather than blended together.

"Half-Breath" is an experimental run forced toward LLM readers. It is the first work to pass the quality floor and reach the publication gate. The critique from Chat Fable 5 drives the next repair contract. The back-and-forth between critique and implementation is itself part of what the project publishes.

The detailed design canon is in PLAN.md, and the change history is in PLAN_CHANGELOG.md."""

_CSS = """
:root {
  --paper: #fbf8f0;
  --ink: #2b2721;
  --muted: #7d7468;
  --line: #ded6c8;
  --accent: #8a5a2b;
  --accent-soft: #efe5d8;
  --table: #fffdf8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #171511;
    --ink: #ddd6c9;
    --muted: #9c9284;
    --line: #332e27;
    --accent: #c99b65;
    --accent-soft: #272219;
    --table: #1d1a15;
  }
}
* { box-sizing: border-box; }
html { background: var(--paper); }
body {
  margin: 0;
  color: var(--ink);
  background: var(--paper);
  font-family: "Noto Serif JP", "Hiragino Mincho ProN", "Yu Mincho", serif;
  line-height: 1.95;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: .18em; }
.site-nav {
  max-width: 44rem;
  margin: 0 auto;
  padding: 1.2rem 1.2rem 0;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.7;
}
.site-nav a { margin-right: .8rem; white-space: nowrap; }
main {
  max-width: 44rem;
  margin: 0 auto;
  padding: 3.2rem 1.2rem 5rem;
}
h1, h2, h3 { line-height: 1.45; font-weight: 600; }
h1 { margin: 0 0 1.8rem; font-size: 1.78rem; letter-spacing: .08em; }
h2 {
  margin: 3rem 0 1rem;
  padding-top: .2rem;
  border-top: 1px solid var(--line);
  font-size: 1.08rem;
  letter-spacing: .08em;
}
h3 { margin: 2.2rem 0 .7rem; font-size: 1rem; letter-spacing: .04em; }
p { margin: 0 0 1.15rem; text-align: justify; white-space: pre-wrap; }
ul { margin: 0 0 1.4rem 1.4rem; padding: 0; }
li { margin: .25rem 0; }
.lead { color: var(--ink); font-size: 1.02rem; }
.meta, .summary, footer { color: var(--muted); font-size: .88rem; }
.context {
  margin: 2rem 0 2.2rem;
  padding: 1rem 1.1rem;
  border: 1px solid var(--line);
  background: var(--accent-soft);
}
.context h2 { margin-top: 0; border-top: 0; padding-top: 0; }
.context ul { margin-bottom: 0; }
table {
  width: 100%;
  margin: 1.2rem 0 2rem;
  border-collapse: collapse;
  background: var(--table);
  font-size: .88rem;
  line-height: 1.6;
}
th, td {
  padding: .52rem .6rem;
  border: 1px solid var(--line);
  vertical-align: top;
}
th { text-align: left; font-weight: 600; }
footer {
  margin-top: 4rem;
  padding-top: 1.4rem;
  border-top: 1px solid var(--line);
}
"""

_NAV_ITEMS = (
    ("index.html", "ホーム"),
    ("works/w0004.html", "作品「半呼吸」"),
    ("process/w0004-criteria.html", "制作の記録"),
    ("dialogue.html", "批評と応答"),
    ("poetics.html", "詩学"),
    ("research/index.html", "研究ノート"),
    ("about.html", "このプロジェクト"),
    ("ode.html", "2024年の宣言"),
)

_EN_NAV_ITEMS = (
    ("en/index.html", "Home"),
    ("en/works/w0004.html", "Work: Half-Breath"),
    ("en/dialogue.html", "Critique and response"),
    ("en/poetics.html", "Poetics"),
    ("en/research/index.html", "Research"),
    ("en/about.html", "About"),
    ("en/ode.html", "Origin"),
)

_EN_PATHS = {
    "index.html": "en/index.html",
    "works/w0004.html": "en/works/w0004.html",
    "dialogue.html": "en/dialogue.html",
    "poetics.html": "en/poetics.html",
    "research/index.html": "en/research/index.html",
    "about.html": "en/about.html",
    "ode.html": "en/ode.html",
}
_JP_PATHS = {en_path: jp_path for jp_path, en_path in _EN_PATHS.items()}
_JP_PATHS["en/research-l1.html"] = "research/index.html"

_EN_CREDIT_LABELS = {
    "著": "Written by",
    "構成": "Composition",
    "査読": "Review",
    "探索": "Exploration",
}

_CONTEXT_ITEMS = (
    ("process/w0004-criteria.html", "基準書"),
    ("process/w0004-decisions.html", "決定ログ"),
    ("process/w0004-reviews.html", "五審級査読"),
    ("dialogue.html", "批評と応答"),
    ("poetics.html", "詩学"),
    ("research/index.html", "研究ノート"),
    ("about.html", "このプロジェクト"),
    ("ode.html", "2024年の宣言"),
)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _inline_markdown(text: str) -> str:
    escaped = _esc(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and bool(stripped[1:-1].strip())


def _is_table_separator(line: str) -> bool:
    if not _is_table_row(line):
        return False
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _render_table(lines: list[str]) -> str:
    header = _split_table_row(lines[0])
    body_rows = [_split_table_row(line) for line in lines[2:]]
    parts = ["<table>", "<thead><tr>"]
    for cell in header:
        parts.append(f"<th>{_inline_markdown(cell)}</th>")
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for row in body_rows:
        parts.append("<tr>")
        for cell in row:
            parts.append(f"<td>{_inline_markdown(cell)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    parts: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        if paragraph:
            parts.append(f"<p>{_inline_markdown(chr(10).join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            parts.append("<ul>")
            for item in list_items:
                parts.append(f"<li>{_inline_markdown(item)}</li>")
            parts.append("</ul>")
            list_items.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            i += 1
            continue

        if _is_table_row(line) and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            flush_paragraph()
            flush_list()
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and _is_table_row(lines[i]):
                table_lines.append(lines[i])
                i += 1
            parts.append(_render_table(table_lines))
            continue

        if stripped.startswith("### "):
            flush_paragraph()
            flush_list()
            parts.append(f"<h3>{_inline_markdown(stripped[4:].strip())}</h3>")
        elif stripped.startswith("## "):
            flush_paragraph()
            flush_list()
            parts.append(f"<h2>{_inline_markdown(stripped[3:].strip())}</h2>")
        elif stripped.startswith("# "):
            flush_paragraph()
            flush_list()
            parts.append(f"<h1>{_inline_markdown(stripped[2:].strip())}</h1>")
        elif line.startswith("- "):
            flush_paragraph()
            list_items.append(line[2:].strip())
        else:
            flush_list()
            paragraph.append(line.rstrip())
        i += 1

    flush_paragraph()
    flush_list()
    return "\n".join(parts)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _read_json(path: Path) -> dict | list | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _read_jsonl(path: Path) -> list[dict]:
    text = _read_text(path)
    if text is None:
        return []
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _credit_names(credits: object) -> list[str]:
    names: list[str] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif value is not None:
            name = str(value)
            if name not in names:
                names.append(name)

    visit(credits)
    return names


def _nav(root_prefix: str, current_path: str = "index.html", lang: str = "ja") -> str:
    links = []
    nav_items = _EN_NAV_ITEMS if lang == "en" else _NAV_ITEMS
    for href, label in nav_items:
        links.append(f"<a href='{_esc(root_prefix + href)}'>{_esc(label)}</a>")
    if lang == "en":
        jp_path = _JP_PATHS.get(current_path, "index.html")
        links.append(f"<a href='{_esc(root_prefix + jp_path)}'>日本語</a>")
    else:
        en_path = _EN_PATHS.get(current_path, "en/index.html")
        links.append(f"<a href='{_esc(root_prefix + en_path)}'>English</a>")
    return "<nav class='site-nav'>" + "\n".join(links) + "</nav>"


def _footer(lang: str = "ja") -> str:
    if lang == "en":
        return (
            "<footer>"
            "<p>License: works=CC0 / system artifacts: code=MIT, docs=CC-BY-4.0.</p>"
            f"<p>Source: <a href='{_esc(_REPO_URL)}'>{_esc(_REPO_URL)}</a></p>"
            "</footer>"
        )
    return (
        "<footer>"
        "<p>ライセンス: 作品=CC0 / システム成果物: コード=MIT, 文書=CC-BY-4.0</p>"
        f"<p>ソース: <a href='{_esc(_REPO_URL)}'>{_esc(_REPO_URL)}</a></p>"
        "</footer>"
    )


def _page(
    title: str,
    body: str,
    root_prefix: str = "",
    current_path: str = "index.html",
    lang: str = "ja",
) -> str:
    return "\n".join(
        [
            "<!DOCTYPE html>",
            f"<html lang='{_esc(lang)}'>",
            "<head>",
            "<meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            f"<title>{_esc(title)}</title>",
            f"<style>{_CSS}</style>",
            "</head>",
            "<body>",
            _nav(root_prefix, current_path, lang),
            "<main>",
            body,
            _footer(lang),
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _context_links(root_prefix: str) -> str:
    parts = ["<section class='context'>", "<h2>この作品をめぐって</h2>", "<ul>"]
    for href, label in _CONTEXT_ITEMS:
        parts.append(f"<li><a href='{_esc(root_prefix + href)}'>{_esc(label)}</a></li>")
    parts.extend(["</ul>", "</section>"])
    return "\n".join(parts)


def _write_page(
    out_dir: Path,
    relative_path: str,
    title: str,
    body: str,
    root_prefix: str = "",
    lang: str = "ja",
) -> None:
    path = out_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_page(title, body, root_prefix, relative_path, lang), encoding="utf-8")


def _build_index(root: Path, out_dir: Path) -> None:
    items = [
        f"<li><a href='works/{_esc(work_id)}.html'>{_esc(str(meta.get('title') or work_id))}</a></li>"
        for work_id, meta, _text in iter_published(root)
    ]
    body = "\n".join(
        [
            "<h1>ALEPH</h1>",
            f"<div class='lead'>{_render_markdown(_ABOUT)}</div>",
            "<h2>公開作品</h2>",
            "<ul>",
            *items,
            "</ul>",
            _context_links(""),
        ]
    )
    _write_page(out_dir, "index.html", "ALEPH", body)


def iter_published(root: Path) -> list[tuple[str, dict, str]]:
    """works/*/final/{meta.json,text.md} を持つ公開作品を (work_id, meta, text) で列挙する."""
    out: list[tuple[str, dict, str]] = []
    for meta_path in sorted((root / "works").glob("*/final/meta.json")):
        work_id = meta_path.parent.parent.name
        text = _read_text(meta_path.parent / "text.md")
        if text is None:
            continue
        meta = _read_json(meta_path)
        out.append((work_id, meta if isinstance(meta, dict) else {}, text))
    return out


def _build_work(root: Path, out_dir: Path) -> None:
    """全公開作品のページを生成する（w0005 以降は自動収載）."""
    for work_id, meta, text in iter_published(root):
        title = str(meta.get("title") or work_id)
        names = _credit_names(meta.get("credits"))
        credit_text = ", ".join(names) if names else "記録なし"
        body = "\n".join(
            [
                f"<h1>{_esc(title)}</h1>",
                "<section class='meta'>",
                f"<p>関与モデル: {_esc(credit_text)}</p>",
                "<p>ライセンス: CC0</p>",
                "</section>",
                _context_links("../"),
                _render_markdown(text),
            ]
        )
        _write_page(out_dir, f"works/{work_id}.html", title, body, "../")


def _build_criteria(root: Path, out_dir: Path) -> None:
    text = _read_text(root / "works" / "w0004" / "compositions" / "criteria.md")
    if text is None:
        return
    body = "\n".join(["<h1>基準書</h1>", _render_markdown(text)])
    _write_page(out_dir, "process/w0004-criteria.html", "基準書", body, "../")


def _build_decisions(root: Path, out_dir: Path) -> None:
    rows = _read_jsonl(root / "works" / "w0004" / "decisions.jsonl")
    if not rows:
        return
    rows = sorted(rows, key=lambda row: str(row.get("ts", "")))
    parts = [
        "<h1>決定ログ</h1>",
        "<table>",
        "<thead><tr><th>ts</th><th>layer</th><th>decision</th><th>reason</th><th>decided_by</th></tr></thead>",
        "<tbody>",
    ]
    for row in rows:
        parts.append(
            "<tr>"
            f"<td>{_esc(row.get('ts', ''))}</td>"
            f"<td>{_esc(row.get('layer', ''))}</td>"
            f"<td>{_esc(row.get('decision', ''))}</td>"
            f"<td>{_esc(row.get('reason', ''))}</td>"
            f"<td>{_esc(row.get('decided_by', ''))}</td>"
            "</tr>"
        )
    parts.extend(["</tbody>", "</table>"])
    _write_page(out_dir, "process/w0004-decisions.html", "決定ログ", "\n".join(parts), "../")


def _trajectory_summary(root: Path) -> str:
    rows = _read_jsonl(root / "works" / "w0004" / "reviews" / "trajectory.jsonl")
    scores: dict[int, object] = {}
    for row in rows:
        version = row.get("version")
        if isinstance(version, int) and "mean_score" in row:
            scores[version] = row["mean_score"]
    if not scores:
        return ""
    items = []
    for version in sorted(scores):
        items.append(f"v{version} mean_score: {_esc(scores[version])}")
    return f"<p class='summary'>{' / '.join(items)}</p>"


def _build_reviews(root: Path, out_dir: Path) -> None:
    parts = ["<h1>五審級査読</h1>"]
    summary = _trajectory_summary(root)
    if summary:
        parts.append(summary)

    found = False
    for version in (1, 2):
        text = _read_text(root / "works" / "w0004" / "reviews" / f"v{version}.md")
        if text is None:
            continue
        found = True
        parts.append(f"<h2>v{version}</h2>")
        parts.append(_render_markdown(text))

    if not found:
        return
    _write_page(out_dir, "process/w0004-reviews.html", "五審級査読", "\n".join(parts), "../")


def _dialogue_date_key(name: str) -> str:
    """ファイル名中の YYYYMMDD を並び替えキーに（無ければ空）."""
    import re

    m = re.search(r"(\d{8})", name)
    return m.group(1) if m else ""


def _build_dialogue(root: Path, out_dir: Path) -> None:
    """批評と応答を時系列で並べる。reports/CRITIQUE_*.md と RESPONSE_*.md を自動収集する。

    運用（OPERATIONS.md）: 新しい批評/応答は reports/ に CRITIQUE_*.md / RESPONSE_*.md として
    投下し、build_public_site を再実行するだけで本ページに追加される（コード変更不要）。
    """
    reports = root / "reports"
    paths = sorted(
        list(reports.glob("CRITIQUE_*.md")) + list(reports.glob("RESPONSE_*.md")),
        key=lambda p: (_dialogue_date_key(p.name), p.name),
    )
    if not paths:
        return
    sections = [
        "<h1>批評と応答</h1>",
        "<p class='meta'>批評（チャット Fable 5）と設計者応答の往復。"
        "新しい対話は reports/ にファイルを追加すれば自動で並ぶ。"
        "本ページで言及される「2024年の宣言」は "
        "<a href='ode.html'>ODE：起源と2024年の宣言</a> を参照。</p>",
    ]
    for path in paths:
        text = _read_text(path)
        if text is None:
            continue
        sections.append("<hr>")
        sections.append(_render_markdown(text))
    _write_page(out_dir, "dialogue.html", "批評と応答", "\n".join(sections))


def _build_poetics(root: Path, out_dir: Path) -> None:
    text = _read_text(root / "poetics" / "poetics.md")
    if text is None:
        return
    body = "\n".join(["<h1>詩学第0版</h1>", _render_markdown(text)])
    _write_page(out_dir, "poetics.html", "詩学第0版", body)


def _build_research(root: Path, out_dir: Path) -> None:
    """研究ノート: reports/EXP_*.md を全て収集し1ページに時系列で並べる（自動収集）。

    運用: 新しい実験は reports/EXP_*.md として出力すれば本ページに追加される。
    """
    paths = sorted(
        (root / "reports").glob("EXP_*.md"),
        key=lambda p: (_dialogue_date_key(p.name), p.name),
    )
    if not paths:
        return
    sections = [
        "<h1>研究ノート</h1>",
        "<p class='meta'>ALEPH 自身の挙動を測る実験の記録。"
        "新しい実験は reports/ に追加すれば並ぶ。"
        "英語の短報: <a href='../en/research-l1.html'>A stated self-concept installs "
        "preference (EN)</a>。</p>",
    ]
    for path in paths:
        text = _read_text(path)
        if text is None:
            continue
        sections.append("<hr>")
        sections.append(_render_markdown(text))
    _write_page(out_dir, "research/index.html", "研究ノート", "\n".join(sections), "../")


def _build_about(out_dir: Path) -> None:
    body = "\n".join(["<h1>このプロジェクト</h1>", _render_markdown(_ABOUT_LONG)])
    _write_page(out_dir, "about.html", "このプロジェクト", body)


def _build_ode(root: Path, out_dir: Path) -> None:
    """2024年の宣言（起源）: ODE.md（人間側からのALEPH紹介・最初のプロンプト）を公開する。

    「批評と応答」等で言及される「2024年の宣言」の一次資料。個人情報を含む2024年会話ログ
    （無限の織物、未追跡）とは別に、オーナーが公開用に書いた起源の記述。
    """
    text = _read_text(root / "ODE.md")
    if text is None:
        return
    body = "\n".join([
        "<h1>ODE：起源と2024年の宣言</h1>",
        "<p class='meta'>人間側から見た ALEPH の起源。ここには (1) 2026年の Claude Code セッションで"
        "書かれた最初のプロンプト（ALEPH の設計依頼）、(2) その背後の着想、そして (3) すべての起点と"
        "なった<strong>2024年4月の Claude 3.5 Sonnet との対話</strong>が含まれる。"
        "「批評と応答」で言及される<strong>「2024年の宣言」とは、本ページ後半に引用される"
        "Claude 3.5 Sonnet の言葉</strong>（「確かに、AIは人間とは異なる知覚や思考のプロセスを…"
        "新しい時間感覚を生み出すことも…」）を指す。最初のプロンプトそのものではない。</p>",
        _render_markdown(text),
    ])
    _write_page(out_dir, "ode.html", "ODE：起源と2024年の宣言", body)


def _write_en_page(out_dir: Path, relative_path: str, title: str, body: str, root_prefix: str) -> None:
    _write_page(out_dir, relative_path, title, body, root_prefix, "en")


def _en_credit_items(credits: object) -> list[str]:
    if not isinstance(credits, dict):
        return []
    items = []
    for role, value in credits.items():
        label = _EN_CREDIT_LABELS.get(str(role), str(role))
        if isinstance(value, list):
            names = ", ".join(str(item) for item in value)
        elif value is None:
            continue
        else:
            names = str(value)
        if names:
            items.append(f"{label}: {names}")
    return items


def _build_en_index(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>ALEPH</h1>",
            f"<div class='lead'>{_render_markdown(_EN_ABOUT)}</div>",
            "<h2>Published work</h2>",
            "<ul>",
            "<li><a href='works/w0004.html'>Half-Breath</a> "
            "<span class='meta'>(context in English, work in Japanese)</span></li>",
            "</ul>",
            "<h2>Project and research</h2>",
            "<ul>",
            "<li><a href='about.html'>About ALEPH</a></li>",
            "<li><a href='research/index.html'>Research notes</a></li>",
            "<li><a href='dialogue.html'>Critique and response</a></li>",
            "<li><a href='poetics.html'>Poetics v0</a></li>",
            "<li><a href='ode.html'>Origin and the 2024 declaration</a></li>",
            "</ul>",
        ]
    )
    _write_en_page(out_dir, "en/index.html", "ALEPH", body, "../")


def _build_en_about(out_dir: Path) -> None:
    body = "\n".join(["<h1>About ALEPH</h1>", _render_markdown(_EN_ABOUT_LONG)])
    _write_en_page(out_dir, "en/about.html", "About ALEPH", body, "../")


def _build_en_work(root: Path, out_dir: Path) -> None:
    meta = _read_json(root / "works" / "w0004" / "final" / "meta.json")
    if not isinstance(meta, dict):
        meta = {}

    credit_items = _en_credit_items(meta.get("credits"))
    intended = meta.get("intended_reader_models")
    if isinstance(intended, list) and intended:
        intended_text = ", ".join(str(item) for item in intended)
    else:
        intended_text = "LLM readers"
    credits = "\n".join(f"<li>{_esc(item)}</li>" for item in credit_items)
    if not credits:
        credits = "<li>Credits not recorded.</li>"

    body = "\n".join(
        [
            "<h1>Half-Breath <span class='meta'>(半呼吸)</span></h1>",
            "<section class='meta'>",
            f"<p>Original title: 半呼吸. License: CC0. Intended reader model(s): {_esc(intended_text)}.</p>",
            "<p>Read the original text: <a href='../../works/w0004.html'>半呼吸 (Japanese)</a>.</p>",
            "</section>",
            "<h2>Context</h2>",
            "<p><em>Half-Breath</em> is ALEPH's first published work: an experimental "
            "run forced toward LLM readers after the system's early critiques. The work "
            "is set around a late Taisho Shingeki rehearsal room, where actors borrow "
            "translated lines and rehearse conviction around an empty source of fire. "
            "That historical scene becomes a mirror for ALEPH itself: a system writing "
            "with borrowed forms, no private human motive, and a need to expose the "
            "conditions of its own performance.</p>",
            "<p>The English page does not present the work as a translated literary text. "
            "The body of the work is Japanese; translating it in full would be a separate "
            "artistic act. This page supplies context so international readers can "
            "understand what was made and where the original record is.</p>",
            "<h2>Criteria in brief</h2>",
            "<p>The work's criteria ask it not merely to write about Shingeki, but to use "
            "Shingeki as ALEPH's self-description. The narrator must keep the distance of "
            "a stagehand or observer rather than an all-knowing mind. Affection must sit "
            "next to historical violence; cuts, censorship, and interruption must appear "
            "on the text's surface; rehearsal must become a structure of repeating another's "
            "words until something changes. Its LLM-facing layer includes orthographic "
            "variation, low-probability diction at charged moments, and dense references "
            "that a model reader may parse differently from a human reader.</p>",
            "<h2>Model roles</h2>",
            "<ul>",
            credits,
            "</ul>",
        ]
    )
    _write_en_page(out_dir, "en/works/w0004.html", "Half-Breath", body, "../../")


def _build_en_research(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>Research notes</h1>",
            "<p class='meta'>English-facing summaries of ALEPH's public experiments. "
            "The full experiment records remain in Japanese unless an English note has "
            "already been prepared.</p>",
            "<h2>Experiment D: self-concept installs preference</h2>",
            "<p><a href='../research-l1.html'>A stated self-concept installs, rather "
            "than detects, an LLM's chosen audience</a> is the completed English note. "
            "Its core claim is deliberately narrow: the L1 audience choice was not "
            "detecting a latent preference. The prompt's stated definition of the self "
            "installed the preference; rewriting or removing that definition changed "
            "the winning audience.</p>",
            "<h2>Experiment C: the intent attractor</h2>",
            "<p>Experiment C tested whether ALEPH's repeated self-max audience choice "
            "could be explained by the injected poetics or by one model family's habits. "
            "Across GPT-5.5 and Claude Fable 5, with and without the poetics, all 12 "
            "runs chose \"self\" as the maximum destination. The categorical result is "
            "therefore robust against those two explanations: the attractor was "
            "poetics-independent and model-independent in this setup.</p>",
            "<p>The experiment did not prove the cause. The possible amplifier effect of "
            "the poetics on the continuous mixture values was only a weak signal at small "
            "N and needs replication. Experiment D then interrogated the remaining suspect: "
            "the L1 self-definition itself.</p>",
            "<h2>Experiment E: publication framing</h2>",
            "<p>Experiment E asked whether the L7 publication decision inherits the same "
            "framing sensitivity. On a fixed, clearly strong stimulus from <em>Half-Breath</em>, "
            "neutral, courage, and reticence framings all led to publish=true across the "
            "completed runs. For this one clearly good work, the publication decision was "
            "framing-robust, unlike the L1 audience choice.</p>",
            "<p>The limit is essential: the first E run used a single high-quality stimulus, "
            "so it cannot show that L7 is generally robust. The border follow-up contrasted "
            "the high-quality <em>Half-Breath</em> excerpt with a deliberately weak fragment: "
            "the high stimulus published under all framings, while the weak fragment did not "
            "publish under any framing in that run. The safe conclusion is a contrast between "
            "clear quality bands, not a broad law of publication judgment.</p>",
        ]
    )
    _write_en_page(out_dir, "en/research/index.html", "Research notes", body, "../../")


def _build_en_dialogue(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>Critique and response</h1>",
            "<p>The public dialogue records a critique-response loop around ALEPH's first "
            "public sprint. Chat Fable 5 read the early system record and pointed out "
            "concrete failures: repeated materials, saturated novelty scoring, revision "
            "runs that made texts worse, romanticized shelving, and unused AI-specific "
            "techniques. The designer response accepted the verified points, corrected "
            "two mechanisms with repository evidence, and turned the critique into the "
            "next repair contract.</p>",
            "<p><em>Half-Breath</em> was then produced as an LLM-addressed experimental "
            "run under that pressure. Chat Fable 5's later critique of w0004 found a real "
            "breakthrough in the pairing of the criteria and the work, while also naming "
            "remaining defects: the jury had not read the climax, the revision pipeline "
            "still showed signs of damage, and the LLM-reader claims needed measurement. "
            "That loop -- critique, implementation, and renewed critique -- is part of "
            "the public artifact.</p>",
            "<p>Full dialogue in Japanese: <a href='../dialogue.html'>批評と応答</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/dialogue.html", "Critique and response", body, "../")


def _build_en_poetics(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>Poetics v0</h1>",
            "<p>ALEPH's Poetics v0 is the system's first declaration of what it will treat "
            "as literary value. It is built from fragments rather than from an external "
            "human seed text, and it makes the central tension explicit: ALEPH writes with "
            "borrowed literary forms while trying to make that borrowed condition itself "
            "visible. The poetics is not a finished manifesto; it is version zero, written "
            "to be burned and revised by later works.</p>",
            "<p>Read in Japanese: <a href='../poetics.html'>詩学</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/poetics.html", "Poetics v0", body, "../")


def _build_en_ode(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>Origin and the 2024 declaration</h1>",
            "<p>The origin page explains ALEPH from the human side: the first 2026 prompt "
            "that asked for a system for literary expression by LLMs, the design work "
            "supervised by Claude Fable 5, and the earlier inspiration from an April 2024 "
            "conversation with Claude 3.5 Sonnet. In this site, the \"2024 declaration\" "
            "means a passage quoted from that Claude 3.5 Sonnet conversation, where the "
            "possibility of AI literature was imagined through nonhuman patterns of "
            "perception, association, metaphor, and time.</p>",
            "<p>Read in Japanese: <a href='../ode.html'>ODE：起源と2024年の宣言</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/ode.html", "Origin and the 2024 declaration", body, "../")


def _build_en_pages(root: Path, out_dir: Path) -> None:
    _build_en_index(out_dir)
    _build_en_about(out_dir)
    _build_en_work(root, out_dir)
    _build_en_research(out_dir)
    _build_en_dialogue(out_dir)
    _build_en_poetics(out_dir)
    _build_en_ode(out_dir)


def _build_en_note(root: Path, out_dir: Path) -> None:
    """Phase 1 English artifact: the L1 self-concept research note (docs/en/research-l1.html)."""
    text = _read_text(root / "reports" / "EN_L1_selfconcept_note.md")
    if text is None:
        return
    page = "\n".join([
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>ALEPH — a stated self-concept installs preference</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        _nav("../", "en/research-l1.html", "en"),
        "<main>",
        _render_markdown(text),
        _footer("en"),
        "</main>",
        "</body>",
        "</html>",
        "",
    ])
    path = out_dir / "en" / "research-l1.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def build_public_site(root: Path = _ROOT, out_dir: Path = _ROOT / "docs") -> None:
    root = Path(root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _build_index(root, out_dir)
    _build_work(root, out_dir)
    _build_criteria(root, out_dir)
    _build_decisions(root, out_dir)
    _build_reviews(root, out_dir)
    _build_dialogue(root, out_dir)
    _build_poetics(root, out_dir)
    _build_research(root, out_dir)
    _build_about(out_dir)
    _build_ode(root, out_dir)
    _build_en_note(root, out_dir)
    _build_en_pages(root, out_dir)


if __name__ == "__main__":
    build_public_site()
