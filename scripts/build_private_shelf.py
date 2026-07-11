"""棚(SHELVE作品)のプライベート読書ページ生成。

公開サイト(aleph/publish/site.py)とは別物: 公開ゲートを通っていない作品を
オーナーがローカルで読むための頁。state/site_private/ に出力(git管理外)。
本文は査読軌跡の最高スコア版を採用する(改稿切断欠陥のため最終版が最良とは限らない)。

実行: uv run python scripts/build_private_shelf.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "site_private"

CSS = """
:root { --paper:#faf7f0; --ink:#2b2721; --faint:#8a8174; --line:#e4ddd0; --accent:#8c5a2b; }
@media (prefers-color-scheme: dark) {
  :root { --paper:#191713; --ink:#d8d2c5; --faint:#7d766a; --line:#2e2a24; --accent:#c89b66; }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--paper); color:var(--ink); font-family:"Noto Serif JP","Hiragino Mincho ProN","Yu Mincho","BIZ UDMincho",serif; line-height:2.1; }
main { max-width:40rem; margin:0 auto; padding:4rem 1.4rem 6rem; }
h1 { font-size:1.5rem; font-weight:600; letter-spacing:.12em; margin-bottom:.4rem; }
.sub { color:var(--faint); font-size:.85rem; line-height:1.8; margin-bottom:3rem; }
h2 { font-size:1.1rem; font-weight:600; letter-spacing:.2em; margin:3.2rem 0 1.6rem; text-align:center; }
p { white-space:pre-wrap; margin-bottom:1em; text-align:justify; font-size:1.02rem; }
hr { border:none; border-top:1px solid var(--line); margin:2.5rem auto; width:38%; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.shelf li { list-style:none; border-top:1px solid var(--line); padding:1.6rem 0; }
.shelf li:last-child { border-bottom:1px solid var(--line); }
.shelf .t { font-size:1.15rem; letter-spacing:.08em; }
.shelf .d { color:var(--faint); font-size:.85rem; line-height:1.9; margin-top:.3rem; }
details { margin-top:4rem; border-top:1px solid var(--line); padding-top:1.2rem; color:var(--faint); font-size:.85rem; line-height:1.9; }
summary { cursor:pointer; letter-spacing:.15em; }
details pre { white-space:pre-wrap; font-family:inherit; margin-top:.8rem; }
.back { display:block; margin-top:3rem; color:var(--faint); font-size:.85rem; letter-spacing:.1em; }
.notice { color:var(--faint); font-size:.8rem; margin-top:3.5rem; border-top:1px solid var(--line); padding-top:1rem; line-height:1.9; }
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )


def _md_to_html(text: str) -> str:
    out: list[str] = []
    for block in text.split("\n\n"):
        block = block.rstrip()
        if not block:
            continue
        if block.startswith("## "):
            out.append(f"<h2>{html.escape(block[3:].strip())}</h2>")
        elif block.startswith("# "):
            out.append(f"<h2>{html.escape(block[2:].strip())}</h2>")
        elif set(block.strip()) <= {"-", "*", "─", "―"}:
            out.append("<hr>")
        else:
            out.append(f"<p>{html.escape(block)}</p>")
    return "\n".join(out)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _work_info(wdir: Path) -> dict | None:
    traj = _rows(wdir / "reviews" / "trajectory.jsonl")
    drafts = sorted((wdir / "drafts").glob("v*.md")) if (wdir / "drafts").exists() else []
    if not drafts:
        return None
    # 最高スコア版(同点は先の版=改稿切断の影響を受けにくい)。軌跡が無ければ v1。
    best_version = 1
    if traj:
        best = max(traj, key=lambda r: (float(r.get("mean_score", 0)), -int(r.get("version", 99))))
        best_version = int(best.get("version", 1))
    body_path = wdir / "drafts" / f"v{best_version}.md"
    if not body_path.exists():
        body_path = drafts[0]

    decisions = _rows(wdir / "decisions.jsonl")
    audience = next((d["decision"] for d in decisions if d.get("layer") == "L1"), "")
    stop = next((d["decision"] + " — " + d.get("reason", "") for d in decisions
                 if "FINISH" in str(d.get("decision"))), "")
    gate = next((d.get("reason", "") for d in decisions
                 if str(d.get("decision", "")).startswith("publication:")), "")
    form = ""
    winner = wdir / "compositions" / "winner.json"
    if winner.exists():
        form = str(json.loads(winner.read_text(encoding="utf-8")).get("form", ""))
    scores = " → ".join(f"{float(r.get('mean_score', 0)):.2f}" for r in traj)
    text = body_path.read_text(encoding="utf-8")
    return {
        "id": wdir.name, "form": form, "audience": audience, "stop": stop,
        "gate": gate, "scores": scores, "version": best_version,
        "chars": len(text), "text": text,
        "reviews": sorted((wdir / "reviews").glob("v*.md")),
    }


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    infos = []
    for wdir in sorted((ROOT / "works").iterdir()):
        if wdir.is_dir() and wdir.name.startswith("w"):
            info = _work_info(wdir)
            if info:
                infos.append(info)

    items = []
    for w in infos:
        first_line = w["form"].split("。")[0]
        items.append(
            f"<li><a class='t' href='{w['id']}.html'>{w['id']}</a>"
            f"<div class='d'>{html.escape(first_line)}<br>"
            f"{html.escape(w['audience'])}<br>"
            f"陪審評 {w['scores']} ・ 採用 v{w['version']} ・ {w['chars']:,}字</div></li>"
        )
    index_body = (
        "<h1>ALEPH の棚</h1>"
        "<div class='sub'>公開ゲートを通らなかった作品たち。これは私的な閲覧頁であり、"
        "作品の意思(SHELVE)を変えるものではない。</div>"
        f"<ul class='shelf'>{''.join(items)}</ul>"
        "<div class='notice'>ALEPH — 自律的文芸制作システム。設計: Claude Fable 5 / "
        "著者・陪審は各作品の制作記録を参照。詩学第0版は poetics/poetics.md。</div>"
    )
    (OUT / "index.html").write_text(_page("ALEPH の棚", index_body), encoding="utf-8")

    for w in infos:
        record = (
            f"宛先: {w['audience']}\n擱筆: {w['stop']}\n公開判断: {w['gate']}\n"
            f"陪審評の軌跡: {w['scores']}(採用 v{w['version']})\n"
            f"構成: {w['form']}"
        )
        reviews_html = ""
        for review in w["reviews"]:
            reviews_html += (
                f"<details><summary>査読報告 {review.stem}</summary>"
                f"<pre>{html.escape(review.read_text(encoding='utf-8')[:12000])}</pre></details>"
            )
        body = (
            f"<h1>{w['id']}</h1>"
            f"<div class='sub'>{html.escape(w['form'].split('。')[0])}</div>"
            + _md_to_html(w["text"])
            + f"<details open><summary>制作記録</summary><pre>{html.escape(record)}</pre></details>"
            + reviews_html
            + "<a class='back' href='index.html'>← 棚へ戻る</a>"
        )
        (OUT / f"{w['id']}.html").write_text(_page(w["id"], body), encoding="utf-8")
    print(f"built: {OUT} ({len(infos)} works)")


if __name__ == "__main__":
    build()
