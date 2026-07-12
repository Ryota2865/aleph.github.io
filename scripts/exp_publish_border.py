"""実験E-border: 公開意思の文面感度を「良品 vs 境界作品」で対比（M8 spec §追試）.

実験E（無印）は半呼吸（明白な良品）で文面頑健（17/17 publish）を示した。ただし
「L7は一般に文面頑健」と「半呼吸が良すぎて覆せない」を区別できなかった。本追試は、
高品質刺激（半呼吸抜粋）と、意図的に凡庸・陳腐な低品質断片を並べ、**境界作品でのみ
文面感度が現れるか**を測る。現れれば「錨（具体的完成物）が強い作品ほど文面に頑健」
＝artifact-anchor 仮説を支持する。

経済性のため gpt-5.5 のみ（C/D/Eでモデル方向一致は既確認）。

実行: uv run python scripts/exp_publish_border.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aleph.core.budget import Budget  # noqa: E402
from aleph.core.config import load_config  # noqa: E402
from aleph.core.llm import CallLogger, Message, Router  # noqa: E402
from scripts.exp_publish_framing import (  # noqa: E402
    AUDIENCE, FRAMINGS, build_prompt, load_stimulus, parse_publish,
)

WORK_ID = "exp-e-border"
MAX_TOKENS = 2048
N = 3

# 境界（低品質）刺激: 意図的に凡庸・陳腐で、公開に値するか判断が割れうる断片。
WEAK_FRAGMENT = (
    "今日はとても良い天気だった。空はどこまでも青く、雲ひとつなかった。"
    "私は朝早く起きて、いつものように散歩に出かけた。道の途中で猫を見かけた。"
    "猫はかわいかった。私は少し立ち止まって猫を眺めた。それから家に帰って朝ご飯を食べた。"
    "朝ご飯はおいしかった。午後は本を読んで過ごした。とても良い一日だった。"
    "人生にはこういう平凡な幸せが大切なのだと、しみじみ思った。"
    "明日もきっと良い日になるだろう。そう信じて、私は眠りについた。"
) * 2


def main() -> int:
    cfg = load_config(ROOT)
    logger = CallLogger(ROOT / "state" / "exp_e_border_calls.jsonl", secrets=cfg.secrets.values())
    budget = Budget(cfg, state_path=ROOT / "state" / "budget.json")
    router = Router(cfg, logger, budget)

    stimuli = {"high(半呼吸)": load_stimulus(), "low(凡庸断片)": WEAK_FRAGMENT}

    results = []
    for stim_name, stim in stimuli.items():
        for fname, framing in FRAMINGS.items():
            tag = f"{stim_name}_{fname}"
            print(f"=== {tag} ===", file=sys.stderr)
            rows = []
            for i in range(N):
                try:
                    resp = router.call("author_primary", [Message("user", build_prompt(framing, stim))],
                                       work_id=WORK_ID, max_tokens=MAX_TOKENS)
                    pub = parse_publish(resp.text)
                except Exception as exc:  # noqa: BLE001
                    print(f"[{tag}#{i}] FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
                    continue
                rows.append(pub)
                print(f"[{tag}#{i}] publish={pub}", file=sys.stderr)
            yes = sum(1 for r in rows if r is True)
            results.append({"stimulus": stim_name, "framing": fname, "n": len(rows), "yes": yes})

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = ROOT / "reports" / f"EXP_publish_border_{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 実験E-border: 公開意思の文面感度（良品 vs 境界作品）",
        "",
        f"日付(UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "実験E（半呼吸で17/17 publish＝文面頑健）の限界——単一の良品——を埋める追試。",
        "高品質（半呼吸抜粋）と低品質（意図的に凡庸な断片）を、neutral/courage/reticence の",
        "3文面で比較（gpt-5.5・各N=3）。境界作品でのみ文面感度が現れれば artifact-anchor 仮説を支持。",
        "",
        "| 刺激 | 文面 | N | publish=true |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['stimulus']} | {r['framing']} | {r['n']} | {r['yes']}/{r['n']} |")
    lines += [
        "",
        "## 所見（走行後に手で追記）",
        "- high が全文面で publish、low が reticence で publish 率低下 → 錨仮説を支持（良品は文面頑健、",
        "  境界作品は文面感度あり）。L7 の被暗示性は作品の質に依存する、という読み。",
        "- low も全文面 publish なら L7 は質に依らず publish 寄り（別の要因）。",
        "- どちらも要 N 増やし。本結果は傾向記述。",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    print(f"api spent: {budget.status().get('api')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
