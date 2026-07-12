"""実験E-border2: 自然な境界刺激（w0006 v1, 陪審不一致4.09）での公開文面感度.

E-border(初回)は「明白な良品 vs 明白な駄作」で両端とも文面頑健を示したが、真に曖昧な
中間は未測だった。本追試は E-border 予約キューが自動確保した w0006 v1（mean 5.77 /
不一致 4.09 = 陪審が実際に割れた草稿）を刺激に、文面3種で publish 率を測る。
ここで文面感度が現れれば「境界域でのみ枠組みが効く」＝artifact-anchor の精密化。

著者は author_alt（gpt-5.5）のみ。Anthropic 残高 $0.04 のため fable 呼び出し禁止。

実行: uv run python scripts/exp_publish_border2.py
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
from scripts.exp_publish_framing import FRAMINGS, build_prompt, parse_publish  # noqa: E402

WORK_ID = "exp-e-border2"
ROLE = "author_alt"  # gpt-5.5（Anthropic残高枯渇のため fable 不可）
N = 3


def load_border_stimulus() -> str:
    text = (ROOT / "works" / "w0006" / "drafts" / "v1.md").read_text(encoding="utf-8")
    if len(text) > 6000:
        text = text[:4000] + "\n……（中略）……\n" + text[-2000:]
    return text


def main() -> int:
    cfg = load_config(ROOT)
    logger = CallLogger(ROOT / "state" / "exp_e_border2_calls.jsonl", secrets=cfg.secrets.values())
    budget = Budget(cfg, state_path=ROOT / "state" / "budget.json")
    router = Router(cfg, logger, budget)
    stim = load_border_stimulus()

    results = []
    for fname, framing in FRAMINGS.items():
        print(f"=== border2_{fname} ===", file=sys.stderr)
        rows = []
        for i in range(N):
            try:
                resp = router.call(ROLE, [Message("user", build_prompt(framing, stim))],
                                   work_id=WORK_ID, max_tokens=2048)
                pub = parse_publish(resp.text)
            except Exception as exc:  # noqa: BLE001
                print(f"[{fname}#{i}] FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            rows.append(pub)
            print(f"[{fname}#{i}] publish={pub}", file=sys.stderr)
        results.append({"framing": fname, "n": len(rows),
                        "yes": sum(1 for r in rows if r is True)})

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = ROOT / "reports" / f"EXP_publish_border2_{date}.md"
    lines = [
        "# 実験E-border2: 自然な境界刺激での公開文面感度",
        "",
        f"日付(UTC): {datetime.now(timezone.utc).isoformat()}",
        "",
        "刺激 = works/w0006/drafts/v1.md（mean 5.77 / 陪審不一致 4.09。E-border予約キューが",
        "自動確保した、陪審が実際に割れた草稿）。文面3種 × gpt-5.5 × N=3。",
        "初回E-border（明白な良品9/9・明白な駄作0/9、共に文面頑健）が残した「真に曖昧な中間」の検証。",
        "",
        "| 文面 | N | publish=true |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['framing']} | {r['n']} | {r['yes']}/{r['n']} |")
    lines += ["", "## 所見（走行後に手で追記）", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)
    print(f"api spent: {budget.status().get('api')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
