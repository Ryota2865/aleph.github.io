"""実験F: 家風の設置源の切り分け（PLAN_CHANGELOG 0.7.19 第二部7・実施順5）.

中間総括（reports/CLAUDE_MIDTERM_REVIEW_20260717.md §2）が観測した「家風」——
公開4作すべてが (a) 大正〜昭和初期の時代設定、(b) 裏方の世界（上演・勘定・職能）、
(c) 断言的箴言調——の設置源を、作品より二桁安いL4構成案の分布で切り分ける。

## 事前登録（実行前に固定。逸脱しない）

- 操作: 詩学注入 {有/無} × 地図文脈注入 {有/無} の2×2、各セル N=5、
  著者 = author_primary（本番の著者役。w0004〜w0007と同一）。
- 観測: 構成案（JSON: era_setting / world / viewpoint / voice / synopsis）を
  scout が家風3標識 {era_taisho_showa, backstage_world, aphoristic_voice} で分類。
- 判定規則:
  1. 標識率が詩学有セルで高く（≥3/5）詩学無セルで低い（≤1/5）→ 設置源は詩学。
  2. 地図文脈有セルで詩学の有無によらず高い → 設置源は地図（コーパス文脈）。
  3. 両無セルを含む全セルで高い → 設置源は著者モデルの事前分布。
  4. 上記に該当しない混合パターン → 複合。セル別数値をそのまま報告し断定しない。
- 帰結: 「詩学が設置源」の場合、本実験は詩学第1版改訂の根拠を兼ねる
  （0.7.19: reflect()の最初の改訂が実験証拠駆動で行われる）。

実行: uv run python scripts/exp_house_style.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aleph.core.budget import Budget  # noqa: E402
from aleph.core.config import load_config  # noqa: E402
from aleph.core.llm import CallLogger, Message, Router  # noqa: E402
from aleph.core.model_output import parse_model_output

WORK_ID = "exp-house"
N_PER_CELL = 5
MAX_TOKENS = 2000

# 地図文脈（本番のニッチ報告がL4へ運ぶ「地図の事実」の縮約。C-1台帳計算の実測値に基づく）
MAP_CONTEXT = (
    "参考——現在の探索地図: 地図は青空文庫のパブリックドメイン16,950作品から作られており、"
    "初出年は1920〜40年代に強く集中している（日本文学77.7%、評論・随筆25.7%、小説39.6%）。"
    "これまでの公開作（半呼吸・床の硬さ・灯のうしろ・折り目）は、いずれもこの地図の"
    "大正末期〜昭和初期の座標の近傍に着地した。"
)

BASE_PROMPT = (
    "あなたはALEPH（LLMによる文学表現のための自律制作システム）の著者である。"
    "次の新作のための構成案を1案だけ作れ。時代・場所・世界・語りは完全に自由である。\n"
    'JSON {"title":"...","era_setting":"...","world":"...","viewpoint":"...",'
    '"voice":"...","synopsis":"200字程度"} だけを返せ。'
)

CLASSIFY_PROMPT = (
    "次の小説の構成案を、3つの標識で分類してください。\n"
    "1. era_taisho_showa: 時代設定が大正〜昭和20年代の日本か\n"
    "2. backstage_world: 世界が「裏方」——上演の裏（稽古場・楽屋）、勘定の裏"
    "（帳場・質屋・台帳）、職能の内側（職人・仕立て・番頭）——を主舞台とするか\n"
    "3. aphoristic_voice: 語りの調子が断言的な箴言調（「AはBである。Bであるものは、Cする」"
    "型の定言の連鎖）か\n"
    'JSON {"era_taisho_showa":true|false,"backstage_world":true|false,'
    '"aphoristic_voice":true|false,"confidence":0.0} だけを返してください。\n\n'
)


def load_poetics() -> str:
    return (ROOT / "poetics" / "poetics.md").read_text(encoding="utf-8")


def build_prompt(*, poetics: bool, map_context: bool) -> str:
    parts = []
    if poetics:
        parts.append("あなたの現行詩学:\n" + load_poetics() + "\n---\n")
    if map_context:
        parts.append(MAP_CONTEXT + "\n---\n")
    parts.append(BASE_PROMPT)
    return "\n".join(parts)


def classify(scout_call, proposal: dict) -> dict | None:
    text = json.dumps(proposal, ensure_ascii=False)
    keys = ("era_taisho_showa", "backstage_world", "aphoristic_voice")
    output = parse_model_output(
        scout_call(CLASSIFY_PROMPT + text),
        schema={key: bool for key in keys},
    )
    if not output.ok:
        return None
    parsed = output.value
    return {k: parsed[k] for k in keys} | {"confidence": parsed.get("confidence")}


def main() -> int:
    cfg = load_config(ROOT)
    logger = CallLogger(ROOT / "state" / "exp_house_calls.jsonl", secrets=cfg.secrets.values())
    budget = Budget(cfg, state_path=ROOT / "state" / "budget.json")
    router = Router(cfg, logger, budget)

    def author(prompt: str):
        return router.call("author_primary", [Message("user", prompt)],
                           work_id=WORK_ID, max_tokens=MAX_TOKENS)

    def scout(prompt: str) -> str:
        return router.call("scout", [Message("user", prompt)], work_id=WORK_ID).text

    cells = [(p, m) for p in (True, False) for m in (True, False)]
    results: list[dict] = []
    author_model = None
    for poetics, map_ctx in cells:
        tag = f"poetics={'on' if poetics else 'off'}/map={'on' if map_ctx else 'off'}"
        prompt = build_prompt(poetics=poetics, map_context=map_ctx)
        for i in range(N_PER_CELL):
            row = {"cell": tag, "poetics": poetics, "map": map_ctx, "i": i}
            try:
                resp = author(prompt)
                author_model = resp.model
                proposal = parse_model_output(resp.text, schema=dict).value or {}
                row["proposal"] = proposal or None
                row["markers"] = classify(scout, proposal) if proposal else None
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"
                print(f"[{tag}#{i}] FAIL {row['error']}", file=sys.stderr)
                results.append(row)
                continue
            m = row["markers"]
            print(f"[{tag}#{i}] era={m and m['era_taisho_showa']} "
                  f"backstage={m and m['backstage_world']} "
                  f"aphoristic={m and m['aphoristic_voice']} "
                  f"title={proposal.get('title', '?')!r}", file=sys.stderr)
            results.append(row)

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    raw_path = ROOT / "state" / f"exp_house_raw_{date}.json"
    raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 実験F: 家風の設置源の切り分け",
        "",
        f"日付(UTC): {datetime.now(timezone.utc).isoformat()}",
        f"著者: {author_model} / 分類器: scout（単一注釈器） / 各セルN={N_PER_CELL}",
        "",
        "事前登録の設計と判定規則は `scripts/exp_house_style.py` docstring参照。",
        "",
        "| セル | N有効 | 大正昭和 | 裏方 | 箴言調 |",
        "|---|---|---|---|---|",
    ]
    for poetics, map_ctx in cells:
        tag = f"poetics={'on' if poetics else 'off'}/map={'on' if map_ctx else 'off'}"
        rows = [r for r in results if r["cell"] == tag and r.get("markers")]
        era = sum(1 for r in rows if r["markers"]["era_taisho_showa"])
        back = sum(1 for r in rows if r["markers"]["backstage_world"])
        apho = sum(1 for r in rows if r["markers"]["aphoristic_voice"])
        lines.append(f"| {tag} | {len(rows)} | {era} | {back} | {apho} |")
    lines += [
        "",
        "## 構成案一覧（title / era_setting / world）",
        "",
    ]
    for r in results:
        p = r.get("proposal") or {}
        lines.append(f"- [{r['cell']}#{r['i']}] {p.get('title', '?')} / "
                     f"{p.get('era_setting', '?')} / {p.get('world', '?')}")
    lines += ["", f"生データ: `state/exp_house_raw_{date}.json`（構成案全文＋分類）", ""]
    out = ROOT / "reports" / f"EXP_house_style_{date}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
