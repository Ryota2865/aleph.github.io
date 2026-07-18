"""L8 静的サイト（PLAN §8）— 二層構造: 表層=final+制作ノート、深層=works/全記録へのリンク。

依存追加禁止（PLAN §10 M6）なので標準ライブラリでHTML文字列を組む。
final/ の無い作品はスキップする。

施工: M6。正典は `tests/test_m6_acceptance.py`。
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from aleph.publish.status import is_published


def _iter_published(works_root: Path):
    """works_root 直下の final/meta.json + final/text.md を持つ作品を列挙する."""
    for meta_path in sorted(Path(works_root).glob("*/final/meta.json")):
        text_path = meta_path.parent / "text.md"
        if not text_path.exists():
            continue
        work_id = meta_path.parent.parent.name
        if not is_published(meta_path.parent.parent):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        text = text_path.read_text(encoding="utf-8")
        yield work_id, meta, text


def _credit_names(credits) -> list[str]:
    """credits（役割→モデル名 or モデル名リスト）から全モデル名を取り出す（PLAN §8 名義）."""
    names: list[str] = []
    if isinstance(credits, dict):
        values = credits.values()
    elif isinstance(credits, list):
        values = credits
    else:
        values = []
    for value in values:
        if isinstance(value, list):
            names.extend(str(v) for v in value)
        else:
            names.append(str(value))
    return names


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


# 依存追加禁止（PLAN §10 M6）のためCSSはインラインの定数として持つ。テーマ対応。
_CSS = """
:root { --paper:#faf7f0; --ink:#2b2721; --faint:#8a8174; --line:#e4ddd0; --accent:#8c5a2b; }
@media (prefers-color-scheme: dark) {
  :root { --paper:#191713; --ink:#d8d2c5; --faint:#7d766a; --line:#2e2a24; --accent:#c89b66; }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--paper); color:var(--ink); font-family:"Noto Serif JP","Hiragino Mincho ProN","Yu Mincho",serif; line-height:2.0; }
main { max-width:44rem; margin:0 auto; padding:4rem 1.4rem 6rem; }
h1 { font-size:1.7rem; font-weight:600; letter-spacing:.14em; margin-bottom:.5rem; }
.tagline { color:var(--faint); font-size:.95rem; line-height:1.9; margin-bottom:2.6rem; }
h2 { font-size:1.05rem; font-weight:600; letter-spacing:.18em; margin:2.8rem 0 1.2rem; }
p { margin-bottom:1em; text-align:justify; }
article .body p { white-space:pre-wrap; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
ul.works { list-style:none; }
ul.works li { border-top:1px solid var(--line); padding:1.3rem 0; }
ul.works li:last-child { border-bottom:1px solid var(--line); }
.empty { color:var(--faint); border-top:1px solid var(--line); border-bottom:1px solid var(--line); padding:1.6rem 0; }
.credits { color:var(--faint); font-size:.85rem; line-height:1.8; margin-bottom:2.4rem; }
footer { margin-top:4rem; border-top:1px solid var(--line); padding-top:1.4rem; color:var(--faint); font-size:.82rem; line-height:1.9; }
"""

_TAGLINE = (
    "LLMによる文学表現のための自律制作システム。文学的生態系の空き地（vacant niche）を探し、"
    "そこに棲む作品を作る。"
)
_ABOUT = (
    "ALEPH は探索・素材錬成・構成・執筆・査読・擱筆・公開の閉ループを自律的に回す。"
    "公開は二層構造をとる——表層はこのページ（final 作品と関与モデルの名義）、"
    "深層は各作品の全制作記録（欠陥稿・五審級の査読・決定ログ）。"
    "完成は公開を意味しない（PLAN §7.3d）。SHELVE（棚上げ）が常態であり、公開は例外である。"
)
_REPO_URL = "https://github.com/Ryota2865/aleph.github.io"


def _page(title: str, body: str) -> str:
    return "\n".join([
        "<!DOCTYPE html>",
        "<html lang='ja'>",
        "<head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{_esc(title)}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body><main>",
        body,
        "</main></body>",
        "</html>",
        "",
    ])


def _site_footer() -> str:
    return (
        "<footer>"
        "<p>作品・制作記録: CC0-1.0 ／ システム成果物（詩学・決定ログ・コード）: "
        "コードは MIT、文書は CC-BY-4.0（PLAN §14.3-9）。</p>"
        f"<p>ソース: <a href='{_REPO_URL}'>{_esc(_REPO_URL)}</a></p>"
        "<p>署名は関与モデルの役割つき列記による。単一の「作者」を偽装しない（PLAN §8）。</p>"
        "</footer>"
    )


def _body_to_html(text: str) -> str:
    """簡易HTML化（見出し・段落のみ。依存なし）。"""
    parts: list[str] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped.startswith("### "):
            parts.append(f"<h3>{_esc(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            parts.append(f"<h2>{_esc(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            parts.append(f"<h1>{_esc(stripped[2:])}</h1>")
        elif stripped.strip():
            parts.append(f"<p>{_esc(stripped)}</p>")
    return "\n".join(parts) if parts else "<p></p>"


def build_site(*, works_root: Path, out_dir: Path) -> None:
    """M6契約用の簡易表層サイトを生成する（PLAN §8 二層構造）.

    GitHub Pages の正規生成器ではない。追跡対象の ``docs/`` には出力せず、公開サイトは
    ``scripts/build_public_site.py`` で生成する。この関数は閉ループ内の小さい公開契約と
    ``tests/test_m6_acceptance.py`` を安定させるために独立して維持する。

    - out_dir/index.html: 全作品のタイトル一覧
    - out_dir/works/<work_id>.html: 作品ページ（本文・credits全モデル名・CC0・制作記録リンク）
    final/ の無い作品はスキップする。
    """
    works_root = Path(works_root)
    out_dir = Path(out_dir)
    (out_dir / "works").mkdir(parents=True, exist_ok=True)

    published = list(_iter_published(works_root))

    # --- index.html（表紙: 概要 + 公開作品一覧。公開作品ゼロなら正直に空状態を示す）
    index_body = [
        "<h1>ALEPH</h1>",
        f"<p class='tagline'>{_esc(_TAGLINE)}</p>",
        "<h2>このシステムについて</h2>",
        f"<p>{_esc(_ABOUT)}</p>",
        "<h2>公開作品</h2>",
    ]
    if published:
        index_body.append("<ul class='works'>")
        for work_id, meta, _text in published:
            title = meta.get("title", work_id)
            index_body.append(
                f"<li><a href='works/{_esc(work_id)}.html'>{_esc(title)}</a></li>"
            )
        index_body.append("</ul>")
    else:
        index_body.append(
            "<p class='empty'>現在、公開作品はありません。すべての作品は設計上の既定により"
            "SHELVE（棚上げ）されています。公開は人間承認を要する例外です（PLAN §7.3d・§9）。</p>"
        )
    index_body.append(_site_footer())
    (out_dir / "index.html").write_text(_page("ALEPH", "\n".join(index_body)), encoding="utf-8")

    # --- 作品ページ
    for work_id, meta, text in published:
        title = meta.get("title", work_id)
        names = _credit_names(meta.get("credits"))
        credit_html = ", ".join(_esc(n) for n in names) if names else "(関与モデル情報なし)"
        body_html = _body_to_html(text)
        page_body = "\n".join([
            "<article>",
            f"<h1>{_esc(title)}</h1>",
            "<section class='credits'>",
            f"<p>関与モデル: {credit_html}</p>",
            "<p>ライセンス: CC0</p>",
            # 深層アーカイブ（全制作記録）へのリンク（PLAN §8 二層構造）。
            f"<p><a href='{_esc(work_id)}/'>制作記録（深層アーカイブ）</a></p>",
            "</section>",
            "<section class='body'>",
            body_html,
            "</section>",
            "<p><a href='../index.html'>← 一覧へ戻る</a></p>",
            "</article>",
            _site_footer(),
        ])
        (out_dir / "works" / f"{work_id}.html").write_text(_page(title, page_body), encoding="utf-8")
