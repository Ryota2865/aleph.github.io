"""ALEPHダッシュボード生成（designs/ui.md UI-1: 読み取り専用の静的ページ）.

走行中/完了作品の状態・予算3系統・保留中の人間ゲート・直近の決定を1画面にまとめる。
UIは制御盤ではなく観測窓（designs/ui.md 原則1）: 既存のCLI/scriptsの出口だけを読み、
新しい書き込み経路は作らない。state/dashboard.html へ出力（git管理外、
build_private_shelf.py と同じ流儀）。

実行: uv run python scripts/build_dashboard.py
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

from aleph.core.config import load_config

ROOT = Path(__file__).resolve().parents[1]

CSS = """
:root { --paper:#faf7f0; --ink:#2b2721; --faint:#8a8174; --line:#e4ddd0; --accent:#8c5a2b; --warn:#b3441e; }
@media (prefers-color-scheme: dark) {
  :root { --paper:#191713; --ink:#d8d2c5; --faint:#7d766a; --line:#2e2a24; --accent:#c89b66; --warn:#e08a6a; }
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--paper); color:var(--ink); font-family:"Noto Sans JP",system-ui,sans-serif; line-height:1.7; }
main { max-width:56rem; margin:0 auto; padding:2.5rem 1.4rem 5rem; }
h1 { font-size:1.3rem; font-weight:600; letter-spacing:.1em; margin-bottom:.3rem; }
.sub { color:var(--faint); font-size:.8rem; margin-bottom:2.5rem; }
h2 { font-size:.95rem; font-weight:600; letter-spacing:.15em; margin:2.4rem 0 1rem; color:var(--accent); }
table { width:100%; border-collapse:collapse; font-size:.85rem; }
th, td { text-align:left; padding:.5rem .6rem; border-bottom:1px solid var(--line); }
th { color:var(--faint); font-weight:600; font-size:.75rem; letter-spacing:.05em; }
.tag { display:inline-block; padding:.1rem .5rem; border-radius:.3rem; font-size:.75rem; }
.tag-L0 { background:#8c5a2b22; } .tag-L1 { background:#2b872722; } .tag-L6 { background:#2b278722; }
.tag-L7 { background:#87272b22; } .tag-L8 { background:#27872b22; }
.alive { color:#2b8727; } .dead { color:var(--faint); }
.gate { color:var(--warn); border-left:3px solid var(--warn); padding:.4rem .8rem; margin-bottom:.6rem; font-size:.85rem; }
.ok { color:var(--faint); font-size:.85rem; }
.meter { background:var(--line); border-radius:.3rem; height:.5rem; overflow:hidden; margin-top:.3rem; }
.meter > div { background:var(--accent); height:100%; }
.reason { color:var(--faint); font-size:.8rem; }
a { color:var(--accent); }
"""


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _pid_alive(pid_path: Path) -> bool | None:
    """PIDファイルが無ければNone（走行記録なし）、あればプロセス生死を返す."""
    if not pid_path.exists():
        return None
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def collect_works(root: Path) -> list[dict]:
    """works/<id>/checkpoint.json と decisions.jsonl・run PIDから走行状態を集める."""
    works_dir = root / "works"
    if not works_dir.exists():
        return []
    out = []
    for wdir in sorted(works_dir.iterdir()):
        if not (wdir.is_dir() and wdir.name.startswith("w")):
            continue
        ckpt_path = wdir / "checkpoint.json"
        if not ckpt_path.exists():
            continue
        ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
        decisions = _rows(wdir / "decisions.jsonl")
        audience = next(
            (d["decision"] for d in decisions if d.get("layer") == "L1" and "配合比" in str(d.get("decision"))),
            "",
        )
        out.append(
            {
                "id": wdir.name,
                "state": ckpt.get("state"),
                "step": ckpt.get("step"),
                "audience": audience,
                "last_ts": decisions[-1]["ts"] if decisions else None,
                "alive": _pid_alive(root / "state" / f"run_{wdir.name}.pid"),
            }
        )
    return out


def collect_budget_status(root: Path, budgets: dict) -> dict:
    """config/budgets.yaml の宣言と state/budget.json の実残高を突き合わせる."""
    ledger_path = root / "state" / "budget.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    api_ledger = ledger.get("ledgers", {}).get("api", {})
    period_key = api_ledger.get("period_key")
    publish_count = 0
    works_dir = root / "works"
    if period_key and works_dir.exists():
        for wdir in works_dir.iterdir():
            if not wdir.is_dir():
                continue
            for d in _rows(wdir / "decisions.jsonl"):
                if d.get("decision") == "FINISH->PUBLISH" and str(d.get("ts", "")).startswith(period_key):
                    publish_count += 1
    return {
        "period_key": period_key,
        "api_spent": api_ledger.get("spent", 0.0),
        "api_cap": budgets.get("api", {}).get("usd_per_month", 0.0),
        "usd_per_work": budgets.get("api", {}).get("usd_per_work", 0.0),
        "work_spent": ledger.get("work_spent", {}),
        "publish_count": publish_count,
        "publish_cap": budgets.get("publish", {}).get("max_per_month", 0),
    }


def collect_pending_gates(policies: dict, budget_status: dict) -> list[str]:
    """人間ゲートを一級市民に（designs/ui.md 原則2）: 保留中のものだけを列挙する."""
    gates = []
    if not policies.get("publication", {}).get("first_publish_ack", False):
        gates.append("初回公開は人間承認待ち（policies.publication.first_publish_ack=false）")
    if not policies.get("poetics", {}).get("first_revision_requires_human_ack", False):
        gates.append(
            "詩学の初回改訂は人間承認待ち（policies.poetics.first_revision_requires_human_ack=false。"
            "未改訂の間はreflect()が自動スキップされるため実害なし）"
        )
    api_cap = budget_status.get("api_cap", 0.0)
    if api_cap and budget_status.get("api_spent", 0.0) / api_cap >= 0.8:
        gates.append(
            f"月間API予算が80%を超過（{budget_status['api_spent']:.1f} / {api_cap:.1f} USD）"
        )
    return gates


def collect_recent_decisions(root: Path, limit: int = 30) -> list[dict]:
    """全作品のdecisions.jsonlをtsでマージし、直近N件を返す（時系列降順）."""
    works_dir = root / "works"
    if not works_dir.exists():
        return []
    merged = []
    for wdir in works_dir.iterdir():
        if not wdir.is_dir():
            continue
        for d in _rows(wdir / "decisions.jsonl"):
            merged.append({**d, "work_id": wdir.name})
    merged.sort(key=lambda d: str(d.get("ts", "")), reverse=True)
    return merged[:limit]


def render_html(works: list[dict], budget: dict, gates: list[str], decisions: list[dict]) -> str:
    work_rows = "".join(
        f"<tr><td><a href='../works/{w['id']}/'>{html.escape(w['id'])}</a></td>"
        f"<td>{html.escape(str(w['state']))}</td><td>{w['step']}</td>"
        f"<td>{html.escape(w['audience'])}</td>"
        f"<td>{'<span class=alive>●走行中</span>' if w['alive'] else ('<span class=dead>停止</span>' if w['alive'] is False else '')}</td>"
        f"<td class=reason>{html.escape(str(w['last_ts'] or ''))}</td></tr>"
        for w in works
    )
    api_pct = (budget["api_spent"] / budget["api_cap"] * 100) if budget["api_cap"] else 0
    pub_pct = (budget["publish_count"] / budget["publish_cap"] * 100) if budget["publish_cap"] else 0
    work_spent_rows = "".join(
        f"<tr><td>{html.escape(wid)}</td><td>{spent:.2f} / {budget['usd_per_work']:.1f} USD</td></tr>"
        for wid, spent in sorted(budget["work_spent"].items(), key=lambda kv: -kv[1])
    )
    gates_html = (
        "".join(f"<div class='gate'>{html.escape(g)}</div>" for g in gates)
        if gates
        else "<div class='ok'>保留中の人間ゲートはありません。</div>"
    )
    decision_rows = "".join(
        f"<tr><td class=reason>{html.escape(str(d.get('ts', '')))}</td>"
        f"<td>{html.escape(str(d.get('work_id', '')))}</td>"
        f"<td><span class='tag tag-{html.escape(str(d.get('layer', '')))}'>{html.escape(str(d.get('layer', '')))}</span></td>"
        f"<td>{html.escape(str(d.get('decision', '')))}</td></tr>"
        for d in decisions
    )
    body = f"""
<h1>ALEPH ダッシュボード</h1>
<div class='sub'>読み取り専用の観測窓（designs/ui.md UI-1）。書き込みは既存CLI経由でのみ行うこと。</div>

<h2>保留中の人間ゲート</h2>
{gates_html}

<h2>走行状態</h2>
<table><thead><tr><th>作品</th><th>状態</th><th>step</th><th>宛先配合</th><th>プロセス</th><th>最終更新</th></tr></thead>
<tbody>{work_rows}</tbody></table>

<h2>予算（{html.escape(str(budget['period_key'] or '?'))}）</h2>
<p>API月間: {budget['api_spent']:.2f} / {budget['api_cap']:.1f} USD</p>
<div class='meter'><div style='width:{min(api_pct, 100):.0f}%'></div></div>
<p style='margin-top:1rem'>公開数: {budget['publish_count']} / {budget['publish_cap']} 件</p>
<div class='meter'><div style='width:{min(pub_pct, 100):.0f}%'></div></div>
<h2 style='margin-top:1.6rem'>作品別支出</h2>
<table><tbody>{work_spent_rows}</tbody></table>

<h2>直近の決定（最大{len(decisions)}件）</h2>
<table><thead><tr><th>時刻</th><th>作品</th><th>層</th><th>決定</th></tr></thead>
<tbody>{decision_rows}</tbody></table>
"""
    return (
        "<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        f"<title>ALEPH ダッシュボード</title><style>{CSS}</style>"
        f"</head><body><main>{body}</main></body></html>"
    )


def build(root: Path = ROOT) -> Path:
    cfg = load_config(root)
    works = collect_works(root)
    budget = collect_budget_status(root, cfg.budgets)
    gates = collect_pending_gates(cfg.policies, budget)
    decisions = collect_recent_decisions(root)
    out_path = root / "state" / "dashboard.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(works, budget, gates, decisions), encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"built: {path}")
