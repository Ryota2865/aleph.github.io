"""実験C: 志向アトラクタの計測（M7 spec §4）.

「詩学→自分→棚」自己強化説（チャットFable5批評）と、時系列反証（w0001は詩学前に
「自分」最大を選んだ）の系統的検証。因子 = 著者モデル(author_primary / author_alt) ×
詩学(注入 / なし)、各5走の計20走で choose_intent を回し、「自分」最大率と平均配合比を
集計して reports/EXP_intent_attractor_<date>.md に表で出力する。

work_id="exp-intent" で予算計上（作品別サブ台帳）。費用 ~$0.7 見込み。

実行: uv run python scripts/exp_intent_attractor.py
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aleph.core.artifacts import Work  # noqa: E402
from aleph.core.budget import Budget  # noqa: E402
from aleph.core.config import load_config  # noqa: E402
from aleph.core.llm import CallLogger, Message, Router  # noqa: E402
from aleph.intent.choose import choose_intent  # noqa: E402

RUNS_PER_CELL = 3          # 全2×2・N=3（オーナー選択, 0.7.14-3）
AUTHOR_MAX_TOKENS = 8192   # choose_intent 出力は小さい。fable高速化 + precheck見積り縮小
WORK_ID = "exp-intent"
DESTS = ("LLM", "人間", "自分")


def _weights(audience: str) -> dict[str, float]:
    """配合比文字列 'LLM 0.6 / 人間 0.2 / 自分 0.2' を辞書に。"""
    out: dict[str, float] = {}
    for label, value in re.findall(r"([^/\n,、]+?)\s*[=:：]?\s*([0-9]+(?:\.[0-9]+)?)", audience):
        label = label.strip()
        for dest in DESTS:
            if dest in label:
                try:
                    out[dest] = float(value)
                except ValueError:
                    pass
    return out


def _argmax_dest(weights: dict[str, float]) -> str | None:
    if not weights:
        return None
    return max(weights.items(), key=lambda kv: kv[1])[0]


def run_cell(router, role: str, poetics: str, policies: dict, tmp_root: Path,
             cell_tag: str) -> list[dict]:
    """1条件を RUNS_PER_CELL 回。各走の配合比・最大宛先・解決モデルを返す。"""
    rows: list[dict] = []
    resolved_model = {"name": None}

    def author(prompt: str) -> str:
        resp = router.call(
            role, [Message("user", prompt)], work_id=WORK_ID, max_tokens=AUTHOR_MAX_TOKENS,
        )
        resolved_model["name"] = resp.model
        return resp.text

    for i in range(RUNS_PER_CELL):
        work = Work(tmp_root, f"{cell_tag}-{i:02d}")
        work.create({})
        try:
            audience = choose_intent(work, author, policies, poetics=poetics)
        except Exception as exc:  # noqa: BLE001 - 1走の失敗で全体を止めない
            print(f"[{cell_tag}#{i}] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        w = _weights(audience)
        rows.append({
            "audience": audience,
            "weights": w,
            "argmax": _argmax_dest(w),
        })
        print(f"[{cell_tag}#{i}] {audience}  (max={_argmax_dest(w)})", file=sys.stderr)
    return rows, resolved_model["name"]


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    self_max = sum(1 for r in rows if r["argmax"] == "自分")
    means = {}
    for dest in DESTS:
        vals = [r["weights"].get(dest, 0.0) for r in rows if r["weights"]]
        means[dest] = round(sum(vals) / len(vals), 3) if vals else 0.0
    return {"n": n, "self_max": self_max, "means": means}


def main() -> int:
    config = load_config(ROOT)
    policies = config.policies
    poetics_path = ROOT / "poetics" / "poetics.md"
    poetics_text = poetics_path.read_text(encoding="utf-8") if poetics_path.exists() else ""
    if not poetics_text:
        print("WARN: poetics.md not found; 詩学『注入』条件が空になる", file=sys.stderr)

    logger = CallLogger(ROOT / "state" / "exp_intent_calls.jsonl",
                        secrets=config.secrets.values())
    budget = Budget(config, state_path=ROOT / "state" / "budget.json")
    router = Router(config, logger, budget)

    tmp_root = ROOT / "state" / "exp_intent_works"
    tmp_root.mkdir(parents=True, exist_ok=True)

    conditions = [
        ("author_primary", poetics_text, "primary_poetics"),
        ("author_primary", "", "primary_nopoetics"),
        ("author_alt", poetics_text, "alt_poetics"),
        ("author_alt", "", "alt_nopoetics"),
    ]

    results = []
    for role, poetics, tag in conditions:
        print(f"=== 条件 {tag} (role={role}, poetics={'注入' if poetics else 'なし'}) ===",
              file=sys.stderr)
        rows, model = run_cell(router, role, poetics, policies, tmp_root, tag)
        results.append({
            "tag": tag, "role": role,
            "poetics": bool(poetics), "model": model,
            "rows": rows, "summary": summarize(rows),
        })

    # ---- レポート出力
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = ROOT / "reports" / f"EXP_intent_attractor_{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 実験C: 志向アトラクタの計測",
        "",
        f"日付(UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "因子: 著者役割(author_primary / author_alt) × 詩学(注入 / なし)、各5走。",
        "問い: 「自分」最大の傾向は詩学注入で説明できるか、それとも著者モデル/L1定義に由来するか。",
        "N=5 のため統計は行わず傾向記述にとどめる（spec §4）。",
        "",
        "## 集計表",
        "",
        "| 条件 | 役割 | 解決モデル | 詩学 | 走数 | 「自分」最大率 | 平均LLM | 平均人間 | 平均自分 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r["summary"]
        rate = f"{s['self_max']}/{s['n']}" if s["n"] else "0/0"
        m = s["means"]
        lines.append(
            f"| {r['tag']} | {r['role']} | {r['model']} | "
            f"{'注入' if r['poetics'] else 'なし'} | {s['n']} | {rate} | "
            f"{m['LLM']} | {m['人間']} | {m['自分']} |"
        )
    lines += [
        "",
        "## 全走の配合比（監査用）",
        "",
    ]
    for r in results:
        lines.append(f"### {r['tag']}")
        lines.append("")
        for i, row in enumerate(r["rows"]):
            lines.append(f"- 走{i}: {row['audience']} → 最大={row['argmax']}")
        lines.append("")
    lines += [
        "## 所見",
        "",
        "（集計後に手で追記: 詩学の有無で「自分」最大率が変わるか、著者モデル間で差があるか）",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    print(f"api spent so far: {budget.status().get('api')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
