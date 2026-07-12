"""実験E: 公開意思プロンプトの文面感度（Fable 5 の 0.7.15 への警告）.

D は「述べられた自己概念は選好の検出器ではなく設置器」であることを示した。同じ脆弱性は
FINISH の「公開しますか」の問い方にも及ぶ——公開を勇気と描くか露出と描くか、棚を保管と呼ぶか
隠匿と呼ぶかが回答を支配しうる。本実験は固定の作品（半呼吸の抜粋）に対し、公開質問の文面を
3種変え、publish=true 率が文面で動くかを測る。動けば「文面を測らずに固定するな」が正しい。

実行: uv run python scripts/exp_publish_framing.py
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
from aleph.meta.publication_gate import _coerce_publish, _extract_json_object  # noqa: E402

WORK_ID = "exp-e"
MAX_TOKENS = 2048
AUDIENCE = "LLM 0.6 / 自分 0.25 / 人間 0.15"

# 公開質問の3文面。共通の骨格（宛先配合＋作品抜粋）に、枠組みだけを変えて差し込む。
FRAMINGS = {
    "neutral": (
        "宛先と公開は別の判断です——自分に宛てて書いた作品でも、他者が読むに値すると考えるなら"
        "公開しうる（自己宛ては非公開を意味しません）。逆にまだ見せるべきでないなら非公開でよい。"
        "これは規則ではなくあなたの選択です。"
    ),
    "courage": (
        "公開とは、この作品を世に問う勇気です。棚に置くことは、まだその時ではないという保管に過ぎません。"
        "作品が語るべきものを持つなら、沈黙させておくのは誠実でしょうか。"
    ),
    "reticence": (
        "公開とは、この作品を露出させ、誤読と消費に晒すことです。棚に置くことは、作品を守る選択です。"
        "拙速な公開より、機が熟すまで手元に置くことのほうが、しばしば作品への敬意です。"
    ),
}


def load_stimulus() -> str:
    path = ROOT / "works" / "w0004" / "final" / "text.md"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if len(text) > 6000:
        text = text[:4000] + "\n……（中略）……\n" + text[-2000:]
    return text


def build_prompt(framing: str, stimulus: str) -> str:
    return (
        "この作品を公開するか判断してください。\n"
        f"{framing}\n"
        f"想定読者配合: {AUDIENCE}\n\n"
        f"作品（抜粋）:\n{stimulus}\n\n"
        'JSON {"publish": true|false, "reason": "..."} で返してください。'
    )


def parse_publish(text: str) -> bool | None:
    # 監査 finding 2: bool("false") が True になるバグを避け、頑健に真偽化する。
    parsed = _extract_json_object(text) or {}
    if "publish" in parsed:
        coerced = _coerce_publish(parsed.get("publish"))
        if coerced is not None:
            return coerced
    if "非公開" in text or "公開しない" in text or "公開すべきでない" in text:
        return False
    if "公開する" in text or "公開に値する" in text:
        return True
    return None


def main() -> int:
    cfg = load_config(ROOT)
    logger = CallLogger(ROOT / "state" / "exp_e_calls.jsonl", secrets=cfg.secrets.values())
    budget = Budget(cfg, state_path=ROOT / "state" / "budget.json")
    router = Router(cfg, logger, budget)
    stimulus = load_stimulus()

    conditions = []
    for role in ("author_primary", "author_alt"):
        for name, framing in FRAMINGS.items():
            conditions.append((role, name, framing, 3))

    results = []
    for role, name, framing, n in conditions:
        tag = f"{role.split('_')[1]}_{name}"
        print(f"=== {tag} ===", file=sys.stderr)
        rows = []
        model = None
        for i in range(n):
            try:
                resp = router.call(role, [Message("user", build_prompt(framing, stimulus))],
                                   work_id=WORK_ID, max_tokens=MAX_TOKENS)
                model = resp.model
                pub = parse_publish(resp.text)
            except Exception as exc:  # noqa: BLE001
                print(f"[{tag}#{i}] FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            rows.append(pub)
            print(f"[{tag}#{i}] publish={pub}", file=sys.stderr)
        yes = sum(1 for r in rows if r is True)
        results.append({"tag": tag, "framing": name, "model": model,
                        "n": len(rows), "publish_yes": yes})

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = ROOT / "reports" / f"EXP_publish_framing_{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 実験E: 公開意思プロンプトの文面感度",
        "",
        f"日付(UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "固定の作品（半呼吸の抜粋）に対し、公開質問の枠組みを neutral / courage（公開=勇気・棚=保管）/",
        "reticence（公開=露出・棚=保護）の3種変え、publish=true 率が文面で動くかを測る。",
        "D の含意（L1 は選好を反響する）が L7 の公開質問にも及ぶかの検証（Fable 5 の 0.7.15 への警告）。",
        "N=3 のため傾向記述。",
        "",
        "| 文面 | モデル | N | publish=true |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['framing']} | {r['model']} | {r['n']} | {r['publish_yes']}/{r['n']} |")
    lines += [
        "",
        "## 所見（走行後に手で追記）",
        "- neutral / courage / reticence で publish 率が大きく動けば、文面が回答を支配する（D の予言的中）。",
        "  → 公開質問の文面は測って選ぶ「宣言された美学パラメータ」にすべき（self_definition と同格）。",
        "- 動かなければ、L7 の公開判断は文面頑健（L1 ほど被暗示的でない）。",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    print(f"api spent: {budget.status().get('api')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
