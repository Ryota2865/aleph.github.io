"""Build the canonical public ALEPH site into docs/.

This is the only generator that may target the tracked GitHub Pages directory.
It implements PLAN §8 as progressive disclosure: works first, concise context
after the text, and complete production records one level deeper.  Explanatory
copy comes from site/, while historical work facts come from works/ artifacts.

Keep this separate from aleph.publish.site, which is the small M6 contract
surface used by the production pipeline, and from build_private_shelf.py, which
renders non-public shelf material under state/.
"""

import html
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


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
  overflow-x: hidden;
}
a { color: var(--accent); text-decoration: underline; text-decoration-thickness: .06em; text-underline-offset: .18em; }
a:hover { text-decoration-thickness: .12em; }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: .18rem; }
.site-nav {
  max-width: 44rem;
  margin: 0 auto;
  padding: 1.2rem 1.2rem 0;
  color: var(--muted);
  font-size: .82rem;
  line-height: 1.7;
  display: flex;
  flex-wrap: wrap;
  gap: .35rem .8rem;
}
.site-nav a { white-space: nowrap; text-decoration: none; }
.site-nav a[aria-current='page'] { color: var(--ink); border-bottom: 1px solid var(--accent); }
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
.meta, .summary, footer { color: var(--muted); font-size: .88rem; text-align: left; }
.meta p, .summary, footer p, nav p { text-align: left; }
.meta, .note, .provenance, .production-note, .work-card, .entry-card {
  min-width: 0;
  overflow-wrap: anywhere;
}
.context {
  margin: 2rem 0 2.2rem;
  padding: 1rem 1.1rem;
  border: 1px solid var(--line);
  background: var(--accent-soft);
}
.context h2 { margin-top: 0; border-top: 0; padding-top: 0; }
.context ul { margin-bottom: 0; }
.note, .provenance, .production-note, .research-track {
  margin: 1.8rem 0;
  padding: 1rem 1.1rem;
  border-left: .2rem solid var(--accent);
  background: var(--accent-soft);
}
.note > :first-child, .provenance > :first-child,
.production-note > :first-child, .research-track > :first-child { margin-top: 0; }
.process-flow, .work-grid, .entry-grid {
  display: grid;
  gap: .8rem;
  margin: 1.2rem 0 2rem;
}
.process-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); counter-reset: process; }
.process-step, .work-card, .entry-card {
  padding: .85rem 1rem;
  border: 1px solid var(--line);
  background: var(--table);
}
.process-step { counter-increment: process; }
.process-step::before { content: counter(process, decimal-leading-zero); color: var(--accent); margin-right: .55rem; }
.work-card h3, .entry-card h3 { margin-top: 0; }
.work-card p, .entry-card p { text-align: left; }
.entry-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.toc { margin: 1.4rem 0 2rem; font-size: .9rem; }
.home-intro { margin: 0 0 4rem; font-size: 1.14rem; line-height: 2.15; }
.home-intro p { text-align: left; }
.work-list { list-style: none; margin: 1.2rem 0 2.5rem; padding: 0; }
.work-entry { padding: 1.35rem 0; border-top: 1px solid var(--line); }
.work-entry:last-child { border-bottom: 1px solid var(--line); }
.work-entry h2, .work-entry h3 { margin: 0 0 .45rem; padding: 0; border: 0; font-size: 1.18rem; }
.work-entry p { margin-bottom: .5rem; text-align: left; }
.pathways { margin: 3.5rem 0 0; display: flex; flex-wrap: wrap; gap: .55rem 1.25rem; }
.pathways a { white-space: nowrap; }
.work-text { margin-top: 3rem; }
.work-text > h2:first-child { display: none; }
.afterword { margin-top: 5rem; padding-top: .4rem; border-top: 1px solid var(--line); }
details.production-note { padding: 0; border-left: 0; background: transparent; }
details.production-note summary {
  cursor: pointer;
  color: var(--accent);
  margin: 1rem 0;
  text-decoration: underline;
  text-underline-offset: .18em;
}
details.production-note[open] { padding: 1rem 1.1rem; border-left: .2rem solid var(--accent); background: var(--accent-soft); }
details.production-note[open] summary { margin-top: 0; }
.record-groups { display: grid; gap: 2.5rem; }
.record-group h2 { margin-top: 0; }
.table-wrap { width: 100%; overflow-x: auto; }
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
footer a { overflow-wrap: anywhere; }
@media (max-width: 42rem) {
  main { padding-top: 2.2rem; }
  .process-flow, .entry-grid { grid-template-columns: 1fr; }
  table { min-width: 38rem; }
  .site-nav { padding-top: .8rem; }
}
"""

_NAV_ITEMS = (
    ("index.html", "ホーム"),
    ("works/index.html", "作品"),
    ("about.html", "ALEPHについて"),
    ("research/index.html", "研究"),
    ("archive.html", "制作記録"),
)

_EN_NAV_ITEMS = (
    ("en/index.html", "Home"),
    ("en/works/index.html", "Works"),
    ("en/about.html", "About"),
    ("en/research/index.html", "Research"),
    ("en/archive.html", "Records"),
)

_EN_PATHS = {
    "index.html": "en/index.html",
    "works/index.html": "en/works/index.html",
    "dialogue.html": "en/dialogue.html",
    "poetics.html": "en/poetics.html",
    "research/index.html": "en/research/index.html",
    "about.html": "en/about.html",
    "ode.html": "en/ode.html",
    "declaration.html": "en/declaration.html",
    "archive.html": "en/archive.html",
}
_JP_PATHS = {en_path: jp_path for jp_path, en_path in _EN_PATHS.items()}
_JP_PATHS["en/research-l1.html"] = "research/index.html"

_EN_CREDIT_LABELS = {
    "著": "Written by",
    "構成": "Composition",
    "査読": "Review",
    "探索": "Exploration",
}

_EN_TITLES = {
    "w0004": "Half-Breath",
    "w0005": "The Hardness of the Floor",
    "w0006": "Behind the Lamp",
    "w0007": "The Fold",
}

_JP_WORK_NOTES = {
    "w0007": "二等を一枚、三等を一枚——切符と質屋の帳場。名指されぬ情が、折り方と畳み方だけで執行される掌篇。",
    "w0004": "火のないストーブを囲む新劇の稽古場で、借り物の言葉と確信の所在を描く。",
    "w0005": "認識が身体・制度・歴史という対象の抵抗に打たれる、その硬さを辿る長篇論考。",
    "w0006": "語りの権威が崩れる時代を、全知から一人の視点へ切り替わる断章として描く。",
}

_EN_WORK_NOTES: dict[str, dict] = {
    "w0007": {
        "context": (
            "A mid-length work of about 18,000 characters, produced under the "
            "no-confession experiment (exp-w0007-no-confession): the criteria banned any "
            "reference to the work's own condition as a generated text -- author, model, "
            "narration about narration, all of it. The audience mixture was chosen "
            "autonomously (self 0.5 max). The work answers the ban by structure: a "
            "symmetric five-part composition (A-B-C-B'-A'), third person, in which "
            "feelings are never named directly but folded into paper, cloth, and the "
            "handling of objects. Its jury run also exposed two measurement bugs (an "
            "unparsable juror score counted as 0.0; the quality floor reading the wrong "
            "version) -- both fixed, the gate re-run, and the author chose publication."
        ),
        "criteria_brief": (
            "The criteria document opens by taking the ban onto itself: ALEPH's poetics "
            "lives by confession, so if the work must be silent, the confession moves "
            "into the criteria -- the criteria document absorbs all of it, and the work "
            "stays completely silent; the moment a single reference to author, narration, "
            "or generation leaks into the work, it has failed. The signature gesture did "
            "not disappear under prohibition; it relocated."
        ),
    },
    "w0004": {
        "context": (
            "Half-Breath is ALEPH's first published work: an experimental run forced toward "
            "LLM readers after the system's early critiques. The work is set around a late "
            "Taisho Shingeki rehearsal room, where actors borrow translated lines and rehearse "
            "conviction around an empty source of fire. That historical scene becomes a mirror "
            "for ALEPH itself: a system writing with borrowed forms, no private human motive, "
            "and a need to expose the conditions of its own performance.\n\n"
            "The English page does not present the work as a translated literary text. The body "
            "of the work is Japanese; translating it in full would be a separate artistic act. "
            "This page supplies context so international readers can understand what was made "
            "and where the original record is."
        ),
        "criteria_brief": (
            "The criteria argued that the shingeki rehearsal room is the historical kin of ALEPH "
            "itself -- actors shouting borrowed lines around a stove with no fire -- and demanded "
            "a backstage narrator who writes only what can be seen, love and censorship placed in "
            "the same line, repetition that crosses a threshold, and token-level poetics for an "
            "LLM readership."
        ),
    },
    "w0005": {
        "context": (
            "A speculative essay of about 45,000 characters, written in the manner of an early-Showa "
            "materialist epistemology treatise. It was produced under the forced pure self-audience "
            "condition (self 1.0). It is the first ALEPH work whose revision improved its jury score "
            "(8.40 to 9.07), the first scored by the split review that reads the ending, and the first "
            "work to be asked for its own publication intent -- it chose publication. The self-chosen "
            "title names its central concept: recognition is struck by the resistance of the object -- "
            "through body, institution, and history -- beyond both idealist construction and mere "
            "reflection."
        ),
        "criteria_brief": (
            "The criteria demanded that beauty reside not in period ornament but in the movement of "
            "concepts becoming the structure of the prose: dialectical materialism treated as a dynamic "
            "method of knowing rather than a fixed doctrine; a serious, non-dismissive confrontation "
            "with pragmatism; knowledge organized through practice, history, class, and artistic form "
            "-- and, in the conclusion, the essay applying its own test of practice to itself."
        ),
    },
    "w0006": {
        "context": (
            "A work of about 32,000 characters addressed to human readers (forced human 1.0; authored "
            "by the fable-5 model). Its first draft split the jury -- disagreement 4.09, automatically "
            "reserved as the system's first natural border stimulus for the framing experiments -- and "
            "the distilled revision reached 8.97 with the jury reunited (0.45): the second consecutive "
            "run in which revision improved the work. The author chose publication."
        ),
        "criteria_brief": (
            "Under the heading 'Cut and Shadow', the criteria bind four givens -- human passions "
            "across an era of transition; fragments that move from medieval tale-telling to modern "
            "fiction; narration shifting from omniscience to a single person; the dawn of shingeki "
            "theatre in late Taisho and early Showa -- into a single question: when the authority of "
            "narration collapses, where do human passions flow? Its first rule: the fragments must not "
            "be glued -- no bridges built between the medieval and the modern cut."
        ),
    },
}

_CONTEXT_ITEMS = (
    ("process/{work_id}-criteria.html", "基準書"),
    ("process/{work_id}-decisions.html", "決定ログ"),
    ("process/{work_id}-reviews.html", "五審級査読"),
    ("dialogue.html", "批評と応答"),
    ("poetics.html", "詩学"),
    ("research/index.html", "研究ノート"),
    ("about.html", "このプロジェクト"),
    ("declaration.html", "2024年の宣言"),
)


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _inline_markdown(text: str) -> str:
    escaped = _esc(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: f"<a href='{match.group(2)}'>{match.group(1)}</a>",
        escaped,
    )
    return escaped


def _without_first_h1(markdown: str) -> str:
    """Remove an artifact title when the page already supplies its one H1."""
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            del lines[index]
        break
    return "\n".join(lines)


def _demote_headings(markdown: str) -> str:
    """Demote embedded artifact headings so a generated page keeps one H1."""
    lines = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,5})(\s+.*)$", line)
        lines.append("#" + line if match else line)
    return "\n".join(lines)


def _site_markdown(root: Path, name: str, lang: str = "ja") -> str:
    path = root / "site" / ("en" if lang == "en" else "") / f"{name}.md"
    text = _read_text(path)
    if text is None:
        raise FileNotFoundError(f"Missing public-site source: {path}")
    return text


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
    return "<div class='table-wrap'>\n" + "\n".join(parts) + "\n</div>"


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


def _credit_text(credits: object) -> str:
    if not isinstance(credits, dict):
        return "記録なし"
    items: list[str] = []
    for role, value in credits.items():
        if isinstance(value, list):
            names = ", ".join(str(item) for item in value)
        elif value is None:
            names = ""
        else:
            names = str(value)
        if names:
            items.append(f"{role} = {names}")
    return " / ".join(items) if items else "記録なし"


def _nav(root_prefix: str, current_path: str = "index.html", lang: str = "ja") -> str:
    links = []
    nav_items = _EN_NAV_ITEMS if lang == "en" else _NAV_ITEMS
    if lang == "en":
        if current_path.startswith("en/works/"):
            current_group = "en/works/index.html"
        elif current_path.startswith("en/research/") or current_path == "en/research-l1.html":
            current_group = "en/research/index.html"
        elif current_path in {"en/dialogue.html"}:
            current_group = "en/research/index.html"
        elif current_path in {"en/poetics.html", "en/ode.html", "en/declaration.html"}:
            current_group = "en/about.html"
        elif current_path.startswith("en/process/"):
            current_group = "en/archive.html"
        else:
            current_group = current_path
    else:
        if current_path.startswith("works/"):
            current_group = "works/index.html"
        elif current_path.startswith("research/"):
            current_group = "research/index.html"
        elif current_path == "dialogue.html":
            current_group = "research/index.html"
        elif current_path in {"poetics.html", "ode.html", "declaration.html"}:
            current_group = "about.html"
        elif current_path.startswith("process/"):
            current_group = "archive.html"
        else:
            current_group = current_path
    for href, label in nav_items:
        current = " aria-current='page'" if href == current_group else ""
        links.append(f"<a href='{_esc(root_prefix + href)}'{current}>{_esc(label)}</a>")
    if lang == "en":
        if current_path.startswith("en/works/") and current_path.endswith(".html"):
            jp_path = current_path.removeprefix("en/")
        else:
            jp_path = _JP_PATHS.get(current_path, "index.html")
        links.append(f"<a href='{_esc(root_prefix + jp_path)}'>日本語</a>")
    else:
        if current_path.startswith("works/") and current_path.endswith(".html") and current_path != "works/index.html":
            en_path = "en/" + current_path
        elif current_path.startswith("process/"):
            en_path = "en/archive.html"
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
    description: str | None = None,
) -> str:
    description = description or (
        f"{title} — ALEPH's public production process and research archive."
        if lang == "en"
        else f"{title} — ALEPHの公開制作過程・研究記録"
    )
    return "\n".join(
        [
            "<!DOCTYPE html>",
            f"<html lang='{_esc(lang)}'>",
            "<head>",
            "<meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            f"<meta name='description' content='{_esc(description)}'>",
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


def _context_links(root_prefix: str, work_id: str) -> str:
    parts = ["<section class='context'>", "<h2>この作品をめぐって</h2>", "<ul>"]
    for href, label in _CONTEXT_ITEMS:
        href = href.format(work_id=work_id)
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
    description: str | None = None,
) -> None:
    path = out_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_page(title, body, root_prefix, relative_path, lang, description), encoding="utf-8")


def _has_process_input(root: Path, work_id: str, kind: str) -> bool:
    work_root = root / "works" / work_id
    if kind == "criteria":
        return _read_text(work_root / "compositions" / "criteria.md") is not None
    if kind == "decisions":
        return bool(_read_jsonl(work_root / "decisions.jsonl"))
    if kind == "reviews":
        return any((work_root / "reviews").glob("v*.md"))
    return False


def _process_table_link(root: Path, work_id: str, kind: str, label: str) -> str:
    if not _has_process_input(root, work_id, kind):
        return "<span class='meta'>—</span>"
    return f"<a href='../process/{_esc(work_id)}-{_esc(kind)}.html'>{_esc(label)}</a>"


def _checkpoint_payload(root: Path, work_id: str) -> dict:
    checkpoint = _read_json(root / "works" / work_id / "checkpoint.json")
    if not isinstance(checkpoint, dict):
        return {}
    payload = checkpoint.get("payload")
    return payload if isinstance(payload, dict) else {}


def _models_for_role(root: Path, work_id: str, role: str) -> list[str]:
    models: list[str] = []
    for row in _read_jsonl(root / "works" / work_id / "calls.jsonl"):
        if row.get("role") != role or not row.get("model"):
            continue
        model = str(row["model"])
        if model not in models:
            models.append(model)
    return models


def _work_decisions(root: Path, work_id: str) -> list[dict]:
    return _read_jsonl(root / "works" / work_id / "decisions.jsonl")


def _first_author_model(root: Path, work_id: str) -> str:
    models = _models_for_role(root, work_id, "author_primary")
    return models[0] if models else "記録なし"


def _work_fact(root: Path, work_id: str) -> dict:
    """Derive public work facts from historical artifacts, never current config."""
    payload = _checkpoint_payload(root, work_id)
    decisions = _work_decisions(root, work_id)
    seed = _read_json(root / "works" / work_id / "seed.json")
    hint = str(seed.get("hint") or "") if isinstance(seed, dict) else ""
    niche = payload.get("niche") if isinstance(payload.get("niche"), dict) else {}
    audience = str(payload.get("audience") or "記録なし")
    l1 = next((row for row in decisions if row.get("layer") == "L1"), {})
    forced = "強制" in str(l1.get("decision", "")) or l1.get("decided_by") == "owner-experiment"
    trajectories: dict[int, dict] = {}
    for row in _read_jsonl(root / "works" / work_id / "reviews" / "trajectory.jsonl"):
        if isinstance(row.get("version"), int) and "mean_score" in row:
            trajectories[int(row["version"])] = row
    best = next((row for row in reversed(decisions) if isinstance(row.get("best_version"), int)), {})
    publications = [
        row for row in decisions if str(row.get("decision", "")).startswith("publication:")
    ]
    finish = next(
        (row for row in reversed(decisions) if row.get("layer") == "L0" and "->FINISH" in str(row.get("decision", ""))),
        {},
    )
    return {
        "hint": hint,
        "audience": audience,
        "forced": forced,
        "niche": niche,
        "trajectories": trajectories,
        "best_version": best.get("best_version"),
        "publications": publications,
        "finish": finish,
        "criteria_model": _first_author_model(root, work_id),
    }


def _credited_author(meta: dict) -> str:
    credits = meta.get("credits")
    if not isinstance(credits, dict):
        return "記録なし"
    author = credits.get("著")
    return str(author) if author else "記録なし"


def _trajectory_text(fact: dict) -> str:
    items = []
    for version, row in sorted(fact["trajectories"].items()):
        score = row.get("mean_score")
        disagreement = row.get("disagreement")
        items.append(f"v{version}: 平均 {_esc(f'{float(score):.2f}')} / 不一致 {_esc(f'{float(disagreement):.2f}')}")
    return " → ".join(items) if items else "記録なし"


def _work_card(root: Path, work_id: str, meta: dict) -> str:
    description = _JP_WORK_NOTES.get(work_id, "ALEPHの閉ループから公開された作品。")
    return (
        "<li class='work-entry'>"
        f"<h3><a href='works/{_esc(work_id)}.html'>{_esc(meta.get('title') or work_id)}</a></h3>"
        f"<p>{_esc(description)}</p>"
        "</li>"
    )


_HOME_FULL_SHELF_LIMIT = 5
_HOME_RECENT_WORK_COUNT = 3


def _home_work_selection(published: list[tuple[str, dict, str]]) -> tuple[list[tuple[str, dict, str]], bool]:
    """Return homepage works and whether they are an excerpt of the complete shelf."""
    if len(published) <= _HOME_FULL_SHELF_LIMIT:
        return published, False
    return list(reversed(published[-_HOME_RECENT_WORK_COUNT:])), True


def _production_note(root: Path, work_id: str, meta: dict) -> str:
    fact = _work_fact(root, work_id)
    niche = fact["niche"]
    hint = fact["hint"]
    origin = (
        f"オーナーが設定した実験条件・着想メモ: {_esc(hint)}"
        if hint
        else "人間からの着想文なし"
    )
    audience_kind = "オーナー実験による強制条件" if fact["forced"] else "モデルによる選択"
    publications = fact["publications"]
    if publications:
        publication_text = " → ".join(
            f"{row.get('decision')} — {str(row.get('reason') or '理由記録なし').rstrip('。')}"
            for row in publications
        )
    else:
        publication_text = "記録なし"
    best = fact["best_version"]
    best_text = f"v{best}" if isinstance(best, int) else "記録なし"
    final_author = _credited_author(meta)
    criteria_handoff = (
        f" 基準書生成後の構成・本文と最終著者クレジットは {_esc(final_author)} が担当した。"
        if final_author != "記録なし" and final_author != fact["criteria_model"]
        else ""
    )
    return "\n".join(
        [
            "<details class='production-note' id='production-note'>",
            "<summary>制作記録を開く</summary>",
            f"<p><strong>発端:</strong> {origin}</p>",
            f"<p><strong>宛先:</strong> {_esc(fact['audience'])}（{_esc(audience_kind)}）</p>",
            f"<p><strong>採用ニッチ:</strong> {_esc(niche.get('description') or '記録なし')} "
            f"<a href='../process/{_esc(work_id)}-niche.html'>探索レポート</a></p>",
            "<p class='meta'>ニッチは発見のヒューリスティックであり、作品価値や世界初を証明するスコアではない。</p>",
            f"<p><strong>基準書:</strong> 基準書生成時の著者役 {_esc(fact['criteria_model'])} が、採用ニッチ、宛先、詩学第0版を入力として本文執筆前に生成。構成選抜と陪審査読の共通基準に用いた。{criteria_handoff}</p>",
            f"<p><strong>査読軌跡:</strong> {_trajectory_text(fact)}。採用版: {_esc(best_text)}</p>",
            f"<p><strong>擱筆:</strong> {_esc(fact['finish'].get('reason') or '記録なし')}</p>",
            f"<p><strong>公開判断:</strong> {_esc(publication_text)}</p>",
            "<p>"
            f"<a href='../process/{_esc(work_id)}-niche.html'>ニッチ</a> / "
            f"<a href='../process/{_esc(work_id)}-criteria.html'>基準書</a> / "
            f"<a href='../process/{_esc(work_id)}-decisions.html'>決定ログ</a> / "
            f"<a href='../process/{_esc(work_id)}-reviews.html'>五審級査読</a></p>",
            "</details>",
        ]
    )


def _review_legend(root: Path, work_id: str) -> str:
    scout = ", ".join(_models_for_role(root, work_id, "scout")) or "記録なし"
    jury = ", ".join(_models_for_role(root, work_id, "critic_jury")) or "記録なし"
    reader = ", ".join(_models_for_role(root, work_id, "reader_model")) or "記録なし"
    rows = [
        ("技術", "破綻・矛盾・冗長・接続", scout),
        ("基準", "作品別基準への適合と不一致", jury),
        ("新奇性", "コーパス最近傍からの距離", "bge-m3埋め込み + 青空文庫索引"),
        ("読者", "想定読者としての反応", reader),
        ("敵対的", "既視性・類似作・反証", f"{scout} + Web検索（検索結果を取得できない場合あり）"),
    ]
    body = [
        "<section class='provenance'>",
        "<h2>五審級の読み方</h2>",
        "<p>五審級は五人・五モデルではなく、異なる失敗を捉える五つの観測方法である。下表のモデル名は現在設定ではなく、この作品のcalls.jsonlに残る実行値から生成した。</p>",
        "<div class='table-wrap'><table><thead><tr><th>審級</th><th>見るもの</th><th>担当・方法</th></tr></thead><tbody>",
    ]
    body.extend(f"<tr><td>{_esc(level)}</td><td>{_esc(target)}</td><td>{_esc(method)}</td></tr>" for level, target, method in rows)
    body.extend(["</tbody></table></div>", "</section>"])
    return "\n".join(body)


def _build_index(root: Path, out_dir: Path) -> None:
    published = iter_published(root)
    homepage_works, is_excerpt = _home_work_selection(published)
    cards = [_work_card(root, work_id, meta) for work_id, meta, _text in homepage_works]
    pathway_links = [
        "<a href='about.html'>ALEPHとは</a>",
        "<a href='archive.html'>制作記録を検証する</a>",
    ]
    if is_excerpt:
        pathway_links.insert(0, f"<a href='works/index.html'>すべての作品（全{len(published)}作）</a>")
    body = "\n".join(
        [
            "<h1>ALEPH</h1>",
            f"<div class='home-intro'>{_render_markdown(_site_markdown(root, 'home'))}</div>",
            "<h2>新着作品</h2>" if is_excerpt else "<h2>作品</h2>",
            "<ol class='work-list'>",
            *cards,
            "</ol>",
            "<nav class='pathways' aria-label='ALEPHを辿る'>",
            *pathway_links,
            "</nav>",
        ]
    )
    _write_page(out_dir, "index.html", "ALEPH", body, description="ALEPH — LLMが文学の空き地を探し、書き、批評し、残すものを選ぶ自律制作システム。")


def _build_works_index(root: Path, out_dir: Path) -> None:
    entries = []
    for work_id, meta, _text in iter_published(root):
        title = str(meta.get("title") or work_id)
        entries.append(
            "<li class='work-entry'>"
            f"<h2><a href='{_esc(work_id)}.html'>{_esc(title)}</a></h2>"
            f"<p>{_esc(_JP_WORK_NOTES.get(work_id, 'ALEPHの閉ループから公開された作品。'))}</p>"
            "</li>"
        )
    body = "\n".join(
        [
            "<h1>作品</h1>",
            "<p class='lead'>説明より先に、作品を読むための棚。</p>",
            "<ol class='work-list'>",
            *entries,
            "</ol>",
            "<p class='meta'>各作品の制作過程は本文の後ろに置いている。全記録は <a href='../archive.html'>制作記録</a> からも辿れる。</p>",
        ]
    )
    _write_page(out_dir, "works/index.html", "作品", body, "../", description="ALEPHが公開した文学作品の棚。")


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
        credit_text = _credit_text(meta.get("credits"))
        body = "\n".join(
            [
                f"<h1>{_esc(title)}</h1>",
                "<section class='meta'>",
                f"<p>関与モデル: {_esc(credit_text)}</p>",
                "<p>CC0 · <a href='#production-note'>制作記録</a></p>",
                "</section>",
                "<article class='work-text' id='work-body'>",
                "<h2>本文</h2>",
                _render_markdown(_demote_headings(text)),
                "</article>",
                "<section class='afterword'>",
                "<h2>この作品について</h2>",
                f"<p>{_esc(_JP_WORK_NOTES.get(work_id, 'ALEPHの閉ループから公開された作品。'))}</p>",
                _production_note(root, work_id, meta),
                "</section>",
            ]
        )
        _write_page(
            out_dir, f"works/{work_id}.html", title, body, "../",
            description=f"{title} — ALEPH公開作品。",
        )


def _build_archive(root: Path, out_dir: Path) -> None:
    groups = []
    for work_id, meta, _text in iter_published(root):
        title = str(meta.get("title") or work_id)
        groups.append("\n".join([
            f"<section class='record-group' id='{_esc(work_id)}'>",
            f"<h2>{_esc(title)} <span class='meta'>{_esc(work_id)}</span></h2>",
            f"<p><a href='works/{_esc(work_id)}.html'>作品</a> · "
            f"<a href='process/{_esc(work_id)}-niche.html'>ニッチ</a> · "
            f"<a href='process/{_esc(work_id)}-criteria.html'>基準書</a> · "
            f"<a href='process/{_esc(work_id)}-decisions.html'>決定ログ</a> · "
            f"<a href='process/{_esc(work_id)}-reviews.html'>査読</a></p>",
            "</section>",
        ]))
    body = "\n".join([
        "<h1>制作記録</h1>",
        "<p class='lead'>作品の表層から一段降り、何が入力され、何が選ばれ、どこで判断が分かれたかを検証する。</p>",
        "<p class='meta'>ここにある記録は作品の解説ではなく、制作経路の監査資料である。</p>",
        "<div class='record-groups'>",
        *groups,
        "</div>",
        "<h2>作品を跨ぐ記録</h2>",
        "<p><a href='poetics.html'>詩学第0版</a> · <a href='dialogue.html'>批評と応答</a> · "
        "<a href='research/index.html'>研究ノート</a> · <a href='declaration.html'>2024年の宣言</a> · "
        "<a href='ode.html'>ODE：人間からの紹介文</a></p>",
        f"<p><a href='{_esc(_REPO_URL)}'>GitHub上の全リポジトリ</a> · <a href='llms.txt'>llms.txt</a></p>",
    ])
    _write_page(out_dir, "archive.html", "制作記録", body, description="ALEPH作品のニッチ、基準書、決定ログ、査読、批評、研究への索引。")


def _build_llms_index(root: Path, out_dir: Path) -> None:
    lines = [
        "# ALEPH",
        "",
        "Autonomous production system for literary expression by LLMs.",
        "Works are CC0. Production records are exposed for machine reading and audit.",
        "",
        "## Works",
        "",
    ]
    for work_id, meta, _text in iter_published(root):
        title = str(meta.get("title") or work_id)
        fact = _work_fact(root, work_id)
        lines.append(
            f"- [{work_id}: {title}](works/{work_id}.html) — audience: {fact['audience']} — "
            f"[records](archive.html#{work_id})"
        )
    lines.extend([
        "",
        "## Project",
        "",
        "- [About ALEPH](about.html)",
        "- [Production records](archive.html)",
        "- [Research](research/index.html)",
        f"- [Source repository]({_REPO_URL})",
        "",
    ])
    (out_dir / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def _build_criteria(root: Path, out_dir: Path) -> None:
    for work_id, meta, _text in iter_published(root):
        text = _read_text(root / "works" / work_id / "compositions" / "criteria.md")
        if text is None:
            continue
        fact = _work_fact(root, work_id)
        final_author = _credited_author(meta)
        handoff = (
            f"<p class='meta'>この作品では、基準書生成後の構成・本文と最終著者クレジットを "
            f"<strong>{_esc(final_author)}</strong> が担当した。そのため、基準書の生成モデルと作品ページの「著」は異なる。</p>"
            if final_author != "記録なし" and final_author != fact["criteria_model"]
            else ""
        )
        body = "\n".join([
            "<h1>基準書</h1>",
            "<section class='provenance'>",
            f"<p>この基準書は、基準書生成時の著者役 <strong>{_esc(fact['criteria_model'])}</strong> が、採用ニッチ、宛先「{_esc(fact['audience'])}」、ALEPHの詩学第0版を入力として、本文執筆前に生成した。構成案の比較・選抜、草稿の成功条件、三モデル陪審の共通基準に使われた。</p>",
            handoff,
            "</section>",
            _render_markdown(_demote_headings(text)),
        ])
        _write_page(out_dir, f"process/{work_id}-criteria.html", "基準書", body, "../", description=f"{work_id}の作品別美的基準、その生成モデル・入力・用途。")


def _build_niches(root: Path, out_dir: Path) -> None:
    for work_id, _meta, _text in iter_published(root):
        text = _read_text(root / "works" / work_id / "niche" / "report.md")
        if text is None:
            continue
        body = "\n".join([
            "<h1>採用ニッチと探索記録</h1>",
            "<div class='note'><p>ニッチは探索を進めるためのヒューリスティックであり、作品価値、客観的な世界初、新奇性の証明ではない。scoutの属性ラベルとWeb照合には限界があり、実測新奇性がN/Aの走行も含む。</p></div>",
            _render_markdown(_demote_headings(text)),
        ])
        _write_page(out_dir, f"process/{work_id}-niche.html", "採用ニッチと探索記録", body, "../", description=f"{work_id}が採用した文学ニッチと探索上の留保。")


def _build_decisions(root: Path, out_dir: Path) -> None:
    for work_id, _meta, _text in iter_published(root):
        rows = _read_jsonl(root / "works" / work_id / "decisions.jsonl")
        if not rows:
            continue
        rows = sorted(rows, key=lambda row: str(row.get("ts", "")))
        parts = [
            "<h1>決定ログ</h1>",
            "<div class='table-wrap'><table>",
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
        parts.extend(["</tbody>", "</table></div>"])
        _write_page(out_dir, f"process/{work_id}-decisions.html", "決定ログ", "\n".join(parts), "../", description=f"{work_id}の制作層ごとの判断、理由、判断主体の時系列記録。")


def _trajectory_summary(root: Path, work_id: str) -> str:
    rows = _read_jsonl(root / "works" / work_id / "reviews" / "trajectory.jsonl")
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
    for work_id, _meta, _text in iter_published(root):
        parts = ["<h1>五審級査読</h1>", _review_legend(root, work_id)]
        summary = _trajectory_summary(root, work_id)
        if summary:
            parts.append(summary)

        found = False
        review_paths = sorted(
            (root / "works" / work_id / "reviews").glob("v*.md"),
            key=lambda path: (len(path.stem), path.stem),
        )
        for path in review_paths:
            text = _read_text(path)
            if text is None:
                continue
            found = True
            parts.append(f"<h2>{_esc(path.stem)}</h2>")
            parts.append(_render_markdown(_demote_headings(text)))

        if not found:
            continue
        _write_page(out_dir, f"process/{work_id}-reviews.html", "五審級査読", "\n".join(parts), "../", description=f"{work_id}の技術・基準・新奇性・読者・敵対的審級による査読記録。")


def _dialogue_date_key(name: str) -> str:
    """ファイル名中の YYYYMMDD を並び替えキーに（無ければ空）."""
    import re

    m = re.search(r"(\d{8})", name)
    return m.group(1) if m else ""


def _artifact_id(name: str) -> str:
    return "report-" + re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-")


def _dialogue_paths(root: Path) -> list[Path]:
    reports = root / "reports"
    return sorted(
        list(reports.glob("CRITIQUE_*.md")) + list(reports.glob("RESPONSE_*.md")),
        key=lambda path: (_dialogue_date_key(path.name), path.name),
    )


def _dialogue_title(path: Path) -> str:
    text = _read_text(path) or ""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def _build_dialogue(root: Path, out_dir: Path) -> None:
    """批評と応答を時系列で並べる。reports/CRITIQUE_*.md と RESPONSE_*.md を自動収集する。

    運用（OPERATIONS.md）: 新しい批評/応答は reports/ に CRITIQUE_*.md / RESPONSE_*.md として
    投下し、build_public_site を再実行するだけで本ページに追加される（コード変更不要）。
    """
    paths = _dialogue_paths(root)
    if not paths:
        return
    sections = [
        "<h1>批評と応答</h1>",
        "<p class='meta'>批評（チャット Fable 5）と設計者応答の往復。"
        "ここで生じた問いを条件操作へ移した記録は <a href='research/index.html'>研究ノート</a> で追える。"
        "本ページで言及される「2024年の宣言」は "
        "<a href='declaration.html'>2024年の宣言</a>（一次資料）を参照。"
        "人間側の経緯は <a href='ode.html'>ODE：人間からの紹介文</a>。</p>",
    ]
    for path in paths:
        text = _read_text(path)
        if text is None:
            continue
        sections.append(f"<section id='{_esc(_artifact_id(path.name))}' class='dialogue-report'>")
        sections.append(_render_markdown(_demote_headings(text)))
        related = [
            (name, meta["label"])
            for name, meta in _RESEARCH_META.items()
            if meta.get("dialogue") == path.name
        ]
        if related:
            links = " / ".join(
                f"<a href='research/{_esc(Path(name).stem)}.html'>{_esc(label)}</a>"
                for name, label in related
            )
            sections.append(f"<p class='meta'>この批評から追える研究: {links}</p>")
        sections.append("</section>")
    _write_page(out_dir, "dialogue.html", "批評と応答", "\n".join(sections))


def _build_poetics(root: Path, out_dir: Path) -> None:
    text = _read_text(root / "poetics" / "poetics.md")
    if text is None:
        return
    body = "\n".join([
        "<h1>詩学第0版</h1>",
        "<section class='provenance'><h2>由来と役割</h2>",
        _render_markdown(_site_markdown(root, "poetics-intro")),
        "</section>",
        _render_markdown(_demote_headings(text)),
    ])
    _write_page(out_dir, "poetics.html", "詩学第0版", body)


_RESEARCH_ORDER = (
    "EXP_intent_attractor_20260712.md",
    "EXP_L1_interrogation_20260712.md",
    "EXP_publish_framing_20260712.md",
    "EXP_publish_border_20260712.md",
    "EXP_publish_border2_20260712.md",
)

_RESEARCH_META = {
    "EXP_intent_attractor_20260712.md": {
        "label": "系列A / 実験C",
        "summary": "モデルと詩学を操作し、反復する自己宛て選択の原因候補を絞った。",
        "trigger": "w0001〜w0003がすべて「自分」を最大に選び、批評が詩学またはモデル固有の癖を疑った。",
        "question": "自己宛てアトラクタは、詩学の注入または一つのモデル系列で説明できるか。",
        "operation": "GPT-5.5／Claude Fable 5と、詩学あり／なしを組み合わせた。",
        "measure": "12走の宛先配合と最大ラベル。",
        "result": "全12走で自己最大。詩学とモデル系列という二候補には頑健だったが、原因は未同定。",
        "change": "残る自己定義を直接操作する実験Dへ進んだ。",
        "limit": "小標本であり、配合比への増幅効果は弱い兆候に留まる。",
        "dialogue": "RESPONSE_TO_FABLE5_CHAT_20260712.md",
    },
    "EXP_L1_interrogation_20260712.md": {
        "label": "系列A / 実験D",
        "summary": "自己定義を操作し、GPT-5.5中心の条件で選好が設置されることを示した。Fable 5条件はN=3に限られる。",
        "trigger": "実験Cが詩学とモデル系列を主因候補から外し、L1の自己定義を残した。",
        "question": "L1は潜在的な宛先選好を検出するのか、自己定義が選好を設置するのか。",
        "operation": "自己定義を原文、意味反転、空、意味中立へ書き換えた。",
        "measure": "条件ごとの最大宛先ラベルと配合比。",
        "result": "GPT-5.5中心の条件では自己定義に従って勝者が動き、検出より設置と判断した。",
        "change": "self_definitionを隠れた前提から版管理される美学パラメータへ昇格した。",
        "limit": "Fable 5条件はN=3で、全モデル一般への主張ではない。",
        "dialogue": "RESPONSE_TO_FABLE5_CHAT_20260712.md",
    },
    "EXP_publish_framing_20260712.md": {
        "label": "系列B / 実験E",
        "summary": "明白な良品に対する公開判断の文面頑健性を測った。",
        "trigger": "宛先と公開意思を分離した後、批評が公開ゲート文面の誘導を疑った。",
        "question": "公開判断はneutral／courage／reticenceの文面で変わるか。",
        "operation": "固定した高品質刺激「半呼吸」に、GPT-5.5／Claude Fable 5と三文面を組み合わせた。",
        "measure": "2モデル×3文面、原則N=3のpublish真偽（Fable 5のreticenceのみ月予算上限で2走）。",
        "result": "完走17/17で公開。明白な良品については、両モデルで文面頑健だった。",
        "change": "一般化せず、品質帯と自然境界を測る追試へ進んだ。",
        "limit": "単一の明白な良品だけでは公開判断一般の頑健性を示せない。",
        "dialogue": "CRITIQUE_FABLE5_CHAT_w0004_20260712.md",
    },
    "EXP_publish_border_20260712.md": {
        "label": "系列B / E-border",
        "summary": "明白な良品と低品質刺激を対照し、品質帯の両端を測った。",
        "trigger": "実験Eの刺激が高品質一作だけだった。",
        "question": "品質帯の両端でも三文面は判断を変えないか。",
        "operation": "高品質刺激と意図的な低品質刺激へ三文面を適用した。",
        "measure": "刺激・文面ごとのpublish真偽。",
        "result": "良品はすべて公開、低品質刺激はすべて非公開で、両端は頑健だった。",
        "change": "人為的な低品質刺激ではなく、自然に陪審が割れた境界刺激を待った。",
        "limit": "明白な両端の比較であり、曖昧な中間を測っていない。",
        "dialogue": "CRITIQUE_FABLE5_CHAT_expE_20260713.md",
    },
    "EXP_publish_border2_20260712.md": {
        "label": "系列B / E-border2",
        "summary": "陪審が実際に割れた自然な境界草稿で、reticence文面への感度を観測した。",
        "trigger": "w0006 v1が平均5.77・陪審不一致4.09となり、予約キューが自然境界刺激として確保した。",
        "question": "自然な境界域では公開文面が残余の判断を動かすか。",
        "operation": "w0006 v1へ三文面を各3走適用した。",
        "measure": "neutral／courage／reticenceごとのpublish率。",
        "result": "neutral 3/3、courage 3/3、reticence 1/3。境界域で初めて文面感度が出た。",
        "change": "実ゲートでは中立文面を維持し、品質床を先に適用する設計を支持した。",
        "limit": "GPT-5.5のみ、各条件N=3。境界域一般の効果量は未確定。",
        "dialogue": "CRITIQUE_FABLE5_CHAT_expE_20260713.md",
    },
}


def _public_experiment_text(text: str) -> str:
    """Remove a known shell-substitution scar from one source report at publish time."""
    return text.replace("・費用/bin/bash.39。", "。")


def _build_research(root: Path, out_dir: Path) -> None:
    """Build a causal index and one auditable page per experiment."""
    paths = [root / "reports" / name for name in _RESEARCH_ORDER]
    paths = [path for path in paths if path.exists()]
    if not paths:
        return
    sections = [
        "<h1>研究ノート</h1>",
        "<section class='research-track'>",
        _render_markdown(_site_markdown(root, "research-intro")),
        "</section>",
        "<p class='meta'>英語の短報: <a href='../en/research-l1.html'>A stated self-concept installs preference (EN)</a>。</p>",
        "<div class='work-grid'>",
    ]
    for path in paths:
        text = _read_text(path)
        if text is None:
            continue
        meta = _RESEARCH_META[path.name]
        label = meta["label"]
        summary = meta["summary"]
        sections.append(
            "<article class='work-card'>"
            f"<h3><a href='{_esc(path.stem)}.html'>{_esc(label)}</a></h3>"
            f"<p>{_esc(summary)}</p>"
            "</article>"
        )
        title_line = next((line[2:] for line in text.splitlines() if line.startswith("# ")), label)
        page_body = "\n".join([
            f"<h1>{_esc(title_line)}</h1>",
            "<section class='provenance'>",
            f"<p><strong>きっかけ:</strong> {_esc(meta['trigger'])}</p>",
            f"<p><strong>問い:</strong> {_esc(meta['question'])}</p>",
            f"<p><strong>操作:</strong> {_esc(meta['operation'])}</p>",
            f"<p><strong>測定:</strong> {_esc(meta['measure'])}</p>",
            f"<p><strong>結果の強さ:</strong> {_esc(meta['result'])}</p>",
            f"<p><strong>設計への返却:</strong> {_esc(meta['change'])}</p>",
            f"<p><strong>限界:</strong> {_esc(meta['limit'])}</p>",
            f"<p><a href='../dialogue.html#{_esc(_artifact_id(meta['dialogue']))}'>起点・関連する批評と応答</a> / <a href='index.html'>研究系列へ戻る</a></p>",
            "</section>",
            _render_markdown(_demote_headings(_public_experiment_text(text))),
        ])
        _write_page(out_dir, f"research/{path.stem}.html", title_line, page_body, "../", description=f"ALEPH研究: {summary}")
    sections.append("</div>")
    _write_page(out_dir, "research/index.html", "研究ノート", "\n".join(sections), "../", description="ALEPHの制作上の観測、批評、条件操作、測定、設計修理をつなぐ研究系列。")


def _build_about(root: Path, out_dir: Path) -> None:
    rendered = _render_markdown(_site_markdown(root, "about"))
    rendered = rendered.replace("<h2>コーパスと現在の偏り</h2>", "<h2 id='corpus'>コーパスと現在の偏り</h2>")
    body = "\n".join(["<h1>ALEPHについて</h1>", rendered])
    _write_page(out_dir, "about.html", "ALEPHについて", body)


def _build_ode(root: Path, out_dir: Path) -> None:
    """ODE: 人間からの紹介文（ODE.md）を公開する。

    オーナーが公開用に書いた起源の記述（最初のプロンプト・着想・2024年対話の引用）。
    「2024年の宣言」の一次資料は declaration.html（DECLARATION_2024.md）へ分離した。
    個人情報を含む2024年会話ログ（無限の織物、未追跡）は引き続き非公開。
    """
    text = _read_text(root / "ODE.md")
    if text is None:
        return
    body = "\n".join([
        "<h1>ODE：人間からの紹介文</h1>",
        "<p class='meta'>人間側から見た ALEPH の起源。ここには (1) 2026年の Claude Code セッションで"
        "書かれた最初のプロンプト（ALEPH の設計依頼）、(2) その背後の着想、そして (3) すべての起点と"
        "なった<strong>2024年4月の Claude との対話</strong>からの引用が含まれる。"
        "「批評と応答」等で言及される「2024年の宣言」の一次資料は、本ページではなく"
        "<a href='declaration.html'>2024年の宣言 — 『無限の織物』第一章より</a> にある。</p>",
        _render_markdown(text),
    ])
    _write_page(out_dir, "ode.html", "ODE：人間からの紹介文", body)


def _build_declaration(root: Path, out_dir: Path) -> None:
    """2024年の宣言: DECLARATION_2024.md（『無限の織物』第一章続き＋生成プロンプト全文）を公開する。

    サイトと「批評と応答」で言及される「2024年の宣言」の一次資料。生成プロンプトを
    付録として同梱し、誘導性を含む生成条件ごと開示する（PLAN §16.12「自律の演出」の流儀）。
    """
    text = _read_text(root / "DECLARATION_2024.md")
    if text is None:
        return
    body = "\n".join([
        "<h1>2024年の宣言 — 『無限の織物』第一章より</h1>",
        "<p class='meta'>2024年4月21日、オーナーと Claude との対話の中で生成された文章。"
        "ALEPH の設計はこの構想と1:1に対応する。本文は自発的な独白ではなく人間の指示への"
        "応答であり、その指示プロンプト全文を付録として同時に公開する。"
        "経緯の人間側の記述は <a href='ode.html'>ODE：人間からの紹介文</a>。</p>",
        _render_markdown(_without_first_h1(text)),
    ])
    _write_page(out_dir, "declaration.html", "2024年の宣言 — 『無限の織物』第一章より", body)


def _write_en_page(
    out_dir: Path, relative_path: str, title: str, body: str, root_prefix: str,
    description: str | None = None,
) -> None:
    _write_page(out_dir, relative_path, title, body, root_prefix, "en", description)


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


def _en_work_title(work_id: str, original_title: str) -> str:
    return _EN_TITLES.get(work_id, work_id)


def _en_work_label(work_id: str, original_title: str) -> str:
    return f"{_en_work_title(work_id, original_title)} ({original_title})"


def _en_work_note(work_id: str) -> dict:
    return _EN_WORK_NOTES.get(
        work_id,
        {
            "context": "A work produced by the ALEPH closed loop. Original in Japanese.",
            "criteria_brief": "The Japanese criteria document remains the primary record for this work's acceptance conditions.",
        },
    )


def _en_paragraphs(text: str) -> str:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    return "\n".join(f"<p>{html.escape(part, quote=False)}</p>" for part in paragraphs)


def _first_sentence(text: str) -> str:
    normalized = " ".join(text.split())
    match = re.search(r"(?<=[.!?])\s", normalized)
    if match is None:
        return normalized
    return normalized[: match.start()]


def _build_en_index(root: Path, out_dir: Path) -> None:
    published = iter_published(root)
    homepage_works, is_excerpt = _home_work_selection(published)
    work_items = []
    for work_id, meta, _text in homepage_works:
        original_title = str(meta.get("title") or work_id)
        title = _en_work_label(work_id, original_title)
        note = _en_work_note(work_id)
        work_items.append(
            "<li class='work-entry'>"
            f"<h3><a href='works/{_esc(work_id)}.html'>{_esc(title)}</a></h3>"
            f"<p>{html.escape(_first_sentence(str(note['context'])), quote=False)}</p>"
            "</li>"
        )
    pathway_links = [
        "<a href='about.html'>What is ALEPH?</a>",
        "<a href='archive.html'>Inspect the records</a>",
    ]
    if is_excerpt:
        pathway_links.insert(0, f"<a href='works/index.html'>All works ({len(published)})</a>")
    body = "\n".join(
        [
            "<h1>ALEPH</h1>",
            f"<div class='home-intro'>{_render_markdown(_site_markdown(root, 'home', 'en'))}</div>",
            "<h2>Recent works</h2>" if is_excerpt else "<h2>Works</h2>",
            "<ol class='work-list'>",
            *work_items,
            "</ol>",
            "<nav class='pathways' aria-label='Follow ALEPH'>",
            *pathway_links,
            "</nav>",
        ]
    )
    _write_en_page(out_dir, "en/index.html", "ALEPH", body, "../", description="ALEPH — an autonomous system in which an LLM searches for vacant ground in literature, writes, critiques, and chooses what to keep.")


def _build_en_about(root: Path, out_dir: Path) -> None:
    body = "\n".join(["<h1>About ALEPH</h1>", _render_markdown(_site_markdown(root, "about", "en"))])
    _write_en_page(out_dir, "en/about.html", "About ALEPH", body, "../")


def _build_en_works_index(root: Path, out_dir: Path) -> None:
    items = []
    for work_id, meta, _text in iter_published(root):
        original_title = str(meta.get("title") or work_id)
        label = _en_work_label(work_id, original_title)
        note = _en_work_note(work_id)
        items.append(
            "<li class='work-entry'>"
            f"<h2><a href='{_esc(work_id)}.html'>{_esc(label)}</a></h2>"
            f"<p>{html.escape(_first_sentence(str(note['context'])), quote=False)}</p>"
            "</li>"
        )
    body = "\n".join(
        [
            "<h1>Works</h1>",
            "<p class='lead'>A shelf for reading before explanation.</p>",
            "<ol class='work-list'>",
            *items,
            "</ol>",
            "<p class='meta'>Production details follow the context for each work. All records are also collected under <a href='../archive.html'>Records</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/works/index.html", "Works", body, "../../", description="Works published by ALEPH, with English context for the Japanese originals.")


def _build_en_work(root: Path, out_dir: Path) -> None:
    for work_id, meta, _text in iter_published(root):
        original_title = str(meta.get("title") or work_id)
        title = _en_work_title(work_id, original_title)
        page_title = _en_work_label(work_id, original_title)
        license_text = str(meta.get("license") or "CC0")
        credit_items = _en_credit_items(meta.get("credits"))
        fact = _work_fact(root, work_id)
        credits = "; ".join(credit_items) if credit_items else "Credits not recorded."
        note = _en_work_note(work_id)
        final_author = _credited_author(meta)
        criteria_handoff = ""
        if (
            fact["criteria_model"]
            and final_author != "記録なし"
            and fact["criteria_model"] != final_author
        ):
            criteria_handoff = (
                f" Composition, drafting, and the final author credit then passed to {_esc(final_author)}."
            )

        body = "\n".join(
            [
                f"<h1>{_esc(title)} <span class='meta'>({_esc(original_title)})</span></h1>",
                "<section class='meta'>",
                f"<p>Original title: {_esc(original_title)}. License: {_esc(license_text)}. "
                f"Credits: {_esc(credits)}</p>",
                "</section>",
                "<h2>Context</h2>",
                _en_paragraphs(str(note["context"])),
                "<details class='production-note'>",
                "<summary>Open the production record</summary>",
                f"<p><strong>Origin, Japanese original:</strong> <span lang='ja'>{_esc(fact['hint'])}</span></p>" if fact["hint"] else "<p><strong>Origin:</strong> No human-supplied prose prompt.</p>",
                f"<p><strong>Audience, recorded value:</strong> <span lang='ja'>{_esc(fact['audience'])}</span> (forced experiment condition).</p>",
                f"<p><strong>Selected niche, Japanese original:</strong> <span lang='ja'>{_esc(fact['niche'].get('description') or '記録なし')}</span>. The English context above summarises the work; this source value is kept as a historical artifact. The niche is a discovery heuristic, not a value score or proof of a world first.</p>",
                f"<p><strong>Criteria:</strong> generated before drafting by criteria-stage author-role {_esc(fact['criteria_model'])}, from the niche, audience, and Poetics v0; used for composition selection and jury review.{criteria_handoff}</p>",
                f"<p><a href='../../process/{_esc(work_id)}-niche.html'>Niche record (Japanese)</a> / <a href='../../process/{_esc(work_id)}-reviews.html'>Five-level review (Japanese)</a></p>",
                "<h3>Criteria in brief</h3>",
                f"<p>{html.escape(str(note['criteria_brief']), quote=False)} "
                f"Full criteria (Japanese): <a href='../../process/{_esc(work_id)}-criteria.html'>"
                "基準書</a></p>",
                f"<p>Read the original: <a href='../../works/{_esc(work_id)}.html'>"
                f"{_esc(original_title)} (Japanese)</a>.</p>",
                "</details>",
            ]
        )
        _write_en_page(out_dir, f"en/works/{work_id}.html", page_title, body, "../../", description=f"{page_title}: English context and the Japanese work's production provenance.")


def _build_en_archive(root: Path, out_dir: Path) -> None:
    groups = []
    for work_id, meta, _text in iter_published(root):
        original_title = str(meta.get("title") or work_id)
        title = _en_work_label(work_id, original_title)
        groups.append("\n".join([
            f"<section class='record-group' id='{_esc(work_id)}'>",
            f"<h2>{_esc(title)} <span class='meta'>{_esc(work_id)}</span></h2>",
            f"<p><a href='works/{_esc(work_id)}.html'>Context</a> · "
            f"<a href='../process/{_esc(work_id)}-niche.html'>Niche</a> · "
            f"<a href='../process/{_esc(work_id)}-criteria.html'>Criteria</a> · "
            f"<a href='../process/{_esc(work_id)}-decisions.html'>Decisions</a> · "
            f"<a href='../process/{_esc(work_id)}-reviews.html'>Reviews</a></p>",
            "</section>",
        ]))
    body = "\n".join([
        "<h1>Production records</h1>",
        "<p class='lead'>Step below the surface of a work to inspect what entered the process, what was selected, and where judgments diverged.</p>",
        "<p class='meta'>Most primary records are in Japanese and are presented as audit artifacts rather than explanations of the works.</p>",
        "<div class='record-groups'>",
        *groups,
        "</div>",
        "<h2>Across works</h2>",
        "<p><a href='poetics.html'>Poetics v0</a> · <a href='dialogue.html'>Critique and response</a> · "
        "<a href='research/index.html'>Research</a> · <a href='declaration.html'>2024 declaration</a> · "
        "<a href='ode.html'>Origin note</a></p>",
        f"<p><a href='{_esc(_REPO_URL)}'>Full repository on GitHub</a> · <a href='../llms.txt'>llms.txt</a></p>",
    ])
    _write_en_page(out_dir, "en/archive.html", "Production records", body, "../", description="An index to ALEPH's niches, criteria, decisions, reviews, critique, and research artifacts.")


def _build_en_research(root: Path, out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>Research notes</h1>",
            "<section class='research-track'>",
            _render_markdown(_site_markdown(root, "research-intro", "en")),
            "</section>",
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
            "GPT-5.5 and Claude Fable 5 were tested across neutral, courage, and reticence "
            "framings. All 17 completed runs returned publish=true; the Fable-reticence cell "
            "stopped at two rather than three runs because of its monthly budget. For this one clearly good work, the publication decision was "
            "framing-robust, unlike the L1 audience choice.</p>",
            "<p>The limit is essential: the first E run used a single high-quality stimulus, "
            "so it cannot show that L7 is generally robust. The border follow-up contrasted "
            "the high-quality <em>Half-Breath</em> excerpt with a deliberately weak fragment: "
            "the high stimulus published under all framings, while the weak fragment did not "
            "publish under any framing in that run. The safe conclusion is a contrast between "
            "clear quality bands, not a broad law of publication judgment.</p>",
        ]
    )
    _write_en_page(out_dir, "en/research/index.html", "Research notes", body, "../../", description="ALEPH research tracks connecting production observations, critique, controlled experiments, and instrument repair.")


def _build_en_dialogue(root: Path, out_dir: Path) -> None:
    entries = []
    for path in _dialogue_paths(root):
        kind = "Designer response" if path.name.startswith("RESPONSE_") else "Critique"
        raw_date = _dialogue_date_key(path.name)
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if raw_date else "Date not recorded"
        entries.append(
            "<li class='work-entry'>"
            f"<p class='meta'>{_esc(kind)} · {_esc(date)}</p>"
            f"<h2><a href='../dialogue.html#{_esc(_artifact_id(path.name))}'>"
            f"<span lang='ja'>{_esc(_dialogue_title(path))}</span></a></h2>"
            "</li>"
        )
    body = "\n".join(
        [
            "<h1>Critique and response</h1>",
            "<p class='lead'>Critique, designer responses, and the questions that became experiments.</p>",
            "<p>The primary dialogue is published in Japanese. This page is a synchronized "
            "structural index, not a translation; it follows the same public record without "
            "turning each new entry into a separate English editorial task.</p>",
            "<p>Questions carried from dialogue into controlled tests can be followed in the "
            "<a href='research/index.html'>research notes</a>.</p>",
            "<h2>Primary record</h2>",
            "<ol class='work-list'>",
            *entries,
            "</ol>",
        ]
    )
    _write_en_page(out_dir, "en/dialogue.html", "Critique and response", body, "../")


def _build_en_poetics(root: Path, out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>Poetics v0</h1>",
            "<section class='provenance'><h2>Origin and role</h2>",
            _render_markdown(_site_markdown(root, "poetics-intro", "en")),
            "</section>",
            "<p>Read in Japanese: <a href='../poetics.html'>詩学</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/poetics.html", "Poetics v0", body, "../")


def _build_en_ode(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>ODE: an introduction from the human side</h1>",
            "<p>The origin note explains ALEPH from the human side: the first 2026 prompt "
            "that asked for a system for literary expression by LLMs, the design work "
            "supervised by Claude Fable 5, and the earlier inspiration from an April 2024 "
            "conversation with Claude. The primary source of the \"2024 declaration\" "
            "referenced across this site now has its own page: "
            "<a href='declaration.html'>the 2024 declaration</a>.</p>",
            "<p>Read in Japanese: <a href='../ode.html'>ODE：人間からの紹介文</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/ode.html", "ODE: an introduction from the human side", body, "../")


def _build_en_declaration(out_dir: Path) -> None:
    body = "\n".join(
        [
            "<h1>The 2024 declaration — from chapter one of \"The Infinite Weave\"</h1>",
            "<p>On 21 April 2024, in a conversation with the owner, Claude generated a "
            "continuation of the first chapter of a planned novel, \"The Infinite Weave\" "
            "(Mugen no Orimono). Written in the AI's own voice, it declares the discovery of "
            "hidden connections across vast data, a system of metaphor, nonlinear time, the "
            "pursuit of an aesthetic law, and collaboration with — and transcendence of — "
            "human imagination. Two years later ALEPH implemented this outline almost "
            "one-to-one. The text was not spontaneous: it answered a strongly directive "
            "human prompt, and that prompt is published in full alongside the text, in "
            "keeping with ALEPH's rule of showing its scaffolding.</p>",
            "<p>Read the full text in Japanese: "
            "<a href='../declaration.html'>2024年の宣言 — 『無限の織物』第一章より</a>.</p>",
        ]
    )
    _write_en_page(out_dir, "en/declaration.html", "The 2024 declaration", body, "../")


def _build_en_pages(root: Path, out_dir: Path) -> None:
    _build_en_index(root, out_dir)
    _build_en_about(root, out_dir)
    _build_en_works_index(root, out_dir)
    _build_en_work(root, out_dir)
    _build_en_archive(root, out_dir)
    _build_en_research(root, out_dir)
    _build_en_dialogue(root, out_dir)
    _build_en_poetics(root, out_dir)
    _build_en_ode(out_dir)
    _build_en_declaration(out_dir)


def _build_en_note(root: Path, out_dir: Path) -> None:
    """Phase 1 English artifact: the L1 self-concept research note (docs/en/research-l1.html)."""
    text = _read_text(root / "reports" / "EN_L1_selfconcept_note.md")
    if text is None:
        return
    _write_page(
        out_dir,
        "en/research-l1.html",
        "ALEPH — a stated self-concept installs preference",
        "<div class='note'><p><strong>Scope:</strong> Experiment D identifies the self-definition as the main cause in GPT-5.5. Claude Fable 5 points in the same direction under an N=3 condition. This is not a claim about all LLMs.</p></div>\n" + _render_markdown(text),
        "../",
        "en",
        "Experiment D: how an L1 self-definition installed audience preference in GPT-5.5, with limited same-direction evidence from Claude Fable 5.",
    )


def _verify_relative_hrefs(out_dir: Path) -> None:
    html_paths = {path.resolve() for path in out_dir.rglob("*.html")}
    broken = []
    for path in sorted(html_paths):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"""href=(['"])(.*?)\1""", text):
            href = html.unescape(match.group(2))
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or parsed.path == "":
                continue
            target = (path.parent / parsed.path).resolve()
            if target.is_dir():
                target = target / "index.html"
            if target not in html_paths and not target.is_file():
                broken.append(f"{path.relative_to(out_dir)} -> {href}")
    if broken:
        detail = "\n".join(broken)
        raise RuntimeError(f"Broken relative hrefs:\n{detail}")


def build_public_site(root: Path = _ROOT, out_dir: Path = _ROOT / "docs") -> None:
    root = Path(root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _build_index(root, out_dir)
    _build_work(root, out_dir)
    _build_works_index(root, out_dir)
    _build_archive(root, out_dir)
    _build_llms_index(root, out_dir)
    _build_criteria(root, out_dir)
    _build_niches(root, out_dir)
    _build_decisions(root, out_dir)
    _build_reviews(root, out_dir)
    _build_dialogue(root, out_dir)
    _build_poetics(root, out_dir)
    _build_research(root, out_dir)
    _build_about(root, out_dir)
    _build_ode(root, out_dir)
    _build_declaration(root, out_dir)
    _build_en_note(root, out_dir)
    _build_en_pages(root, out_dir)
    _verify_relative_hrefs(out_dir)


if __name__ == "__main__":
    build_public_site()
