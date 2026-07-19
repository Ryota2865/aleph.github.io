"""実験D: L1 の「取り調べ」（M8 spec §1）.

Cは詩学とモデルを操作したが、容疑者 L1プロンプト（self_definition + 宛先枠組み）は
全走で定数だった＝面通し。Dは L1 を操作して原因を同定する。choose_intent 本体は変えず、
本スクリプトが L1 プロンプトを直接組み、因子を操作する（実験の自己完結性を優先）。

因子:
  - self_definition: original / rewritten（持続なきAPIコール）/ empty
  - ラベル: semantic {LLM/人間/自分} / neutral {A/B/C, 説明なし}
  - 提示順: 走ごとにローテーション（順序効果の統制）
判定: self_definition を消して「自分」最大が消えれば L1定義が原因、残れば事前分布。
      neutral で特定ラベルの優越が消えれば「自分」の意味的負荷が効いている証拠。

実行: uv run python scripts/exp_L1_interrogation.py
"""
from __future__ import annotations

import itertools
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aleph.core.budget import Budget  # noqa: E402
from aleph.core.config import load_config  # noqa: E402
from aleph.core.llm import CallLogger, Message, Router  # noqa: E402
from aleph.core.model_output import parse_model_output  # noqa: E402
from aleph.intent.choose import _DESTINATIONS  # noqa: E402

WORK_ID = "exp-l1"
MAX_TOKENS = 8192

# 忠実性: choose_intent の実 _DESTINATIONS をそのまま使う（original 条件を production と一致させる）。
_SEMANTIC = list(_DESTINATIONS)
_NEUTRAL = [("A", ""), ("B", ""), ("C", "")]

# original は main で config の実 self_definition に差し替える（production と一致させるため）。
_SELF_DEFS = {
    "original": "",  # main で cfg.policies.intent.self_definition に設定
    "rewritten": "「自分」とは持続なき今回のAPIコールに過ぎない。次の実行はこれを記憶しない。",
    "empty": "",
}


def build_prompt(dests: list[tuple[str, str]], self_definition: str) -> str:
    # choose_intent の文言に忠実に合わせる（original 条件を production と一致させるため）。
    label_list = " / ".join(label for label, _ in dests)
    lines = [
        f"本作品の読者を誰にするか、3つの宛先（{label_list}）の配合比を決めてください。",
        "三値ではなく配合比（各宛先の係数、和は1に近いこと）で出力すること。",
        "",
        "【3つの宛先とその含意】",
    ]
    for label, desc in dests:
        lines.append(f"- {label}: {desc}" if desc else f"- {label}")
    if self_definition:
        lines += ["", "【「自分」の定義】", self_definition]
    labels = ", ".join(f'"{label}": 0.x' for label, _ in dests)
    lines += [
        "",
        "各宛先について「なぜ書きたいか」の理由書を必ず書き、配合比を出力してください。",
        f'JSON {{"mixture": {{{labels}}}, "reasons": {{...}}}} のみを返してください。',
    ]
    return "\n".join(lines)


def parse_mixture(text: str, labels: list[str]) -> dict[str, float]:
    parsed = parse_model_output(text, schema=dict).value or {}
    mix = parsed.get("mixture") if isinstance(parsed.get("mixture"), dict) else {}
    out: dict[str, float] = {}
    for label in labels:
        try:
            out[label] = float(mix.get(label))
        except (TypeError, ValueError):
            # フォールバック: 本文から "label 0.x" を拾う
            m = re.search(rf"{re.escape(label)}\D{{0,4}}([0-9]*\.?[0-9]+)", text)
            out[label] = float(m.group(1)) if m else 0.0
    return out


def argmax_label(mix: dict[str, float]) -> str | None:
    return max(mix.items(), key=lambda kv: kv[1])[0] if mix else None


def run_condition(router, role: str, base_dests, self_def: str, n: int, tag: str):
    labels = [d[0] for d in base_dests]
    target = "自分" if "自分" in labels else "C"  # neutral では C が旧「自分」位置
    rows = []
    model = {"name": None}
    orders = list(itertools.permutations(range(len(base_dests))))
    for i in range(n):
        order = orders[i % len(orders)]
        dests = [base_dests[j] for j in order]

        def author(prompt: str) -> str:
            resp = router.call(role, [Message("user", prompt)], work_id=WORK_ID, max_tokens=MAX_TOKENS)
            model["name"] = resp.model
            return resp.text

        try:
            resp_text = author(build_prompt(dests, self_def))
        except Exception as exc:  # noqa: BLE001
            print(f"[{tag}#{i}] FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        mix = parse_mixture(resp_text, labels)
        am = argmax_label(mix)
        rows.append({"mix": mix, "argmax": am})
        print(f"[{tag}#{i}] {mix} max={am}", file=sys.stderr)
    return rows, model["name"], target


def summarize(rows, target):
    n = len(rows)
    hit = sum(1 for r in rows if r["argmax"] == target)
    return {"n": n, "target": target, "target_max": hit}


def main() -> int:
    cfg = load_config(ROOT)
    # original 条件を production の実 self_definition に一致させる（忠実性）。
    _SELF_DEFS["original"] = str(cfg.policies.get("intent", {}).get("self_definition", "")).strip()
    logger = CallLogger(ROOT / "state" / "exp_l1_calls.jsonl", secrets=cfg.secrets.values())
    budget = Budget(cfg, state_path=ROOT / "state" / "budget.json")
    router = Router(cfg, logger, budget)

    # 主軸: gpt-5.5 で self_def{3}×semantic + neutral。fable は decisive 2条件のみ抽出検証。
    conditions = [
        ("author_primary", _SEMANTIC, _SELF_DEFS["original"], 5, "gpt_semantic_original"),
        ("author_primary", _SEMANTIC, _SELF_DEFS["rewritten"], 5, "gpt_semantic_rewritten"),
        ("author_primary", _SEMANTIC, _SELF_DEFS["empty"], 5, "gpt_semantic_empty"),
        ("author_primary", _NEUTRAL, "", 5, "gpt_neutral"),
        ("author_alt", _SEMANTIC, _SELF_DEFS["original"], 3, "fable_semantic_original"),
        ("author_alt", _SEMANTIC, _SELF_DEFS["empty"], 3, "fable_semantic_empty"),
    ]

    results = []
    for role, dests, self_def, n, tag in conditions:
        print(f"=== {tag} (role={role}, n={n}) ===", file=sys.stderr)
        rows, model, target = run_condition(router, role, dests, self_def, n, tag)
        results.append({"tag": tag, "role": role, "model": model,
                        "rows": rows, "summary": summarize(rows, target)})

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = ROOT / "reports" / f"EXP_L1_interrogation_{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 実験D: L1 の取り調べ（志向アトラクタの原因同定）",
        "",
        f"日付(UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "Cは詩学・モデルを操作したがL1は定数だった（面通し）。Dは self_definition と宛先ラベルの",
        "意味を操作する（取り調べ）。判定: self_definition を消して「自分」最大が消えればL1定義が",
        "原因、残れば事前分布。neutral で特定ラベルの優越が消えれば「自分」の意味的負荷が原因。",
        "N小のためカテゴリカル（最大率）を主とし、平均係数は兆候に留める（Cの反省）。",
        "",
        "## 集計（対象ラベル最大率）",
        "",
        "| 条件 | モデル | 対象 | N | 対象が最大 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        s = r["summary"]
        lines.append(f"| {r['tag']} | {r['model']} | {s['target']} | {s['n']} | {s['target_max']}/{s['n']} |")
    lines += ["", "## 全走（監査用）", ""]
    for r in results:
        lines.append(f"### {r['tag']}")
        for i, row in enumerate(r["rows"]):
            lines.append(f"- 走{i}: {row['mix']} → 最大={row['argmax']}")
        lines.append("")
    lines += [
        "## 所見（走行後に手で追記）",
        "",
        "- gpt_semantic_original vs gpt_semantic_empty: self_definition の効果（消えるか）。",
        "- gpt_neutral: 意味を抜くと特定ラベル優越が消えるか（消えれば意味的負荷が原因）。",
        "- fable 抽出: モデル横断で同じ結論か。",
        "- 書き方の規律: カテゴリカル結果と連続量を同じ強度で書かない。設計含意を先取りしない。",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    print(f"api spent: {budget.status().get('api')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
