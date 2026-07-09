"""L8 静的サイト（PLAN §8）— 二層構造: 表層=final+制作ノート、深層=works/全記録へのリンク。

依存追加禁止（PLAN §10 M6）なので標準ライブラリでHTML文字列を組む。
final/ の無い作品はスキップする。

施工: M6。正典は `tests/test_m6_acceptance.py`。
"""
from __future__ import annotations

import html
import json
from pathlib import Path


def _iter_published(works_root: Path):
    """works_root 直下の final/meta.json + final/text.md を持つ作品を列挙する."""
    for meta_path in sorted(Path(works_root).glob("*/final/meta.json")):
        text_path = meta_path.parent / "text.md"
        if not text_path.exists():
            continue
        work_id = meta_path.parent.parent.name
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
    """表層サイトを生成する（PLAN §8 二層構造）.

    - out_dir/index.html: 全作品のタイトル一覧
    - out_dir/works/<work_id>.html: 作品ページ（本文・credits全モデル名・CC0・制作記録リンク）
    final/ の無い作品はスキップする。
    """
    works_root = Path(works_root)
    out_dir = Path(out_dir)
    (out_dir / "works").mkdir(parents=True, exist_ok=True)

    published = list(_iter_published(works_root))

    # --- index.html
    index_lines = [
        "<!DOCTYPE html>",
        "<html lang='ja'>",
        "<head><meta charset='utf-8'>",
        "<title>ALEPH works</title></head>",
        "<body>",
        "<h1>ALEPH works</h1>",
        "<ul>",
    ]
    for work_id, meta, _text in published:
        title = meta.get("title", work_id)
        index_lines.append(f"<li><a href='works/{_esc(work_id)}.html'>{_esc(title)}</a></li>")
    index_lines += ["</ul>", "</body>", "</html>", ""]
    (out_dir / "index.html").write_text("\n".join(index_lines), encoding="utf-8")

    # --- 作品ページ
    for work_id, meta, text in published:
        title = meta.get("title", work_id)
        names = _credit_names(meta.get("credits"))
        credit_html = ", ".join(_esc(n) for n in names) if names else "(関与モデル情報なし)"
        body_html = _body_to_html(text)
        page = [
            "<!DOCTYPE html>",
            "<html lang='ja'>",
            "<head><meta charset='utf-8'>",
            f"<title>{_esc(title)}</title></head>",
            "<body>",
            "<article>",
            f"<h1>{_esc(title)}</h1>",
            "<section class='credits'>",
            f"<p>関与モデル: {credit_html}</p>",
            "<p>ライセンス: CC0</p>",
            "</section>",
            "<section class='body'>",
            body_html,
            "</section>",
            "<footer>",
            # 深層アーカイブ（全制作記録）へのリンク（PLAN §8 二層構造）。
            f"<p><a href='{_esc(work_id)}/'>制作記録（深層アーカイブ）</a></p>",
            "</footer>",
            "</article>",
            "</body>",
            "</html>",
            "",
        ]
        (out_dir / "works" / f"{work_id}.html").write_text("\n".join(page), encoding="utf-8")
